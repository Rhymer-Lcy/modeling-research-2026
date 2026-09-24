"""Load-bearing closure guards; fixtures are synthetic, not scientific evidence."""
from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.quality import scalarize as sc
from src.quality.configuration import load_settings
from src.quality.realdata import Population, confirmed_nan_fields, fit_population, transform_population, preprocessing_hash, mid_ecdf
from src.quality.uncertainty import structured_estimates
from src.quality.handoff import build_if1
from src.quality.pipeline import QUALITY_DOMAINS
from src.mixture.data import MixtureTable, LossTable, normalised_proportions
from src.mixture.validation import select_training_model, evaluate
from src.mixture.closure import acceptance_checks, limited_extrapolation, scope_release_receipt, validation_intervals
from src.interfaces import Provenance


def fixture():
    values = np.tile(np.arange(1., 6.)[:,None],(1,22))
    missing = np.zeros_like(values,dtype=bool)
    missing[-1,-1] = True
    values[-1,-1] = np.nan
    return Population('A1',values,np.tile(np.arange(5.)[:,None],(1,4)),
                      np.tile(np.arange(5.)[:,None],(1,4)),np.array(['arxiv']*5),
                      list('abcde'),np.array(['one']*5),missing,np.arange(1,6),[], 'fixture', 'fixture')


class ClosureChecks(unittest.TestCase):
    def test_only_confirmed_nan_exclusion_allowed(self):
        row = {n:1. for n in sc.NATIVE_SCALARS}
        row.update({n:[1.]*sc.EXPECTED_DIM[n] for n in sc.LIST_FIELDS})
        row['modernbert_reasoning'] = [float('nan')]*6
        self.assertEqual(confirmed_nan_fields(row,6,['modernbert_reasoning']),{'modernbert_reasoning'})
        for literal in (0,5,7):
            with self.assertRaises(ValueError):
                confirmed_nan_fields(row,literal,['modernbert_reasoning'])
        row['modernbert_reasoning'][0]=0.
        with self.assertRaises(ValueError):
            confirmed_nan_fields(row,5,['modernbert_reasoning'])
        row['modernbert_reasoning']=[float('inf')]*6
        with self.assertRaises(ValueError):
            confirmed_nan_fields(row,0,['modernbert_reasoning'])
        row['modernbert_reasoning']=[1.]*5
        with self.assertRaises(ValueError):
            confirmed_nan_fields(row,0,['modernbert_reasoning'])

    def test_complete_cases_and_final_score_sensitivity(self):
        pop=fixture()
        directions={n:'higher_better' for n in sc.INDICATORS}
        prep=fit_population(pop,directions,{})
        before=preprocessing_hash(prep)
        primary,mask=transform_population(prep,pop)
        self.assertEqual(primary.shape,(4,22))
        self.assertEqual(mask.tolist(),[True,True,True,True,False])
        for value in (0.,.5,1.):
            matrix,mask=transform_population(prep,pop,missing_value=value)
            self.assertEqual(matrix.shape,(5,22))
            self.assertEqual(matrix[-1,-1],value)
            np.testing.assert_array_equal(matrix[:4],primary)
            self.assertTrue(np.isfinite(matrix).all())
            self.assertTrue(((matrix>=0)&(matrix<=1)).all())
        self.assertEqual(before,preprocessing_hash(prep))
        self.assertTrue(np.isnan(pop.values[-1,-1]))
        with self.assertRaises(ValueError):
            transform_population(prep,pop,missing_value=1.1)
        with self.assertRaises(ValueError):
            fit_population(replace(pop,name='A2'),directions,{})

    def test_common_midrank_reference_and_ties(self):
        np.testing.assert_allclose(mid_ecdf(np.array([1.,1.]),np.array([0.,1.,2.])),[0.,.5,1.])
        with self.assertRaises(ValueError):
            mid_ecdf(np.array([1.]),np.array([np.nan]))
        pop=fixture()
        directions={n:'higher_better' for n in sc.INDICATORS}
        directions['dsir_books']='lower_better'
        directions['rps_doc_mean_word_length']='non_monotone'
        prep=fit_population(pop,directions,{'rps_doc_mean_word_length':[3.,10.]})
        extension=replace(pop,name='A2',values=pop.values.copy())
        extension.values[:,0]=1000
        matrix,_=transform_population(prep,extension)
        np.testing.assert_array_equal(matrix[:,0],0.)
        self.assertEqual(len(prep.indicators),22)

    def test_if1_native_directions_cannot_be_overridden_by_processing(self):
        _,settings=load_settings('quality')
        processing={**sc.DIRECTIONS,**settings['direction_overrides']}
        mix=MixtureTable('fixture',np.arange(2),['d'+str(i) for i in range(17)],
                         np.array([[1.]+[0.]*16,[0.,1.]+[0.]*15]))
        mapping={d:('arxiv' if i==0 else None) for i,d in enumerate(mix.domains)}
        estimates={'domains':{d:{'q':.5,'ci':[.4,.6],'n':10} for d in QUALITY_DOMAINS}}
        interface=build_if1(estimates,mix,mapping,{d:'direct' if mapping[d] else 'inferred' for d in mapping},
                             provenance=Provenance('reference',['synthetic']),processing_notes={
                                 'q_definition':'fixture','directions':processing,'normalization':'fixture',
                                 'missing_signal_policy':'fixture','stability':'fixture'})
        interface.validate()
        self.assertEqual(interface.indicator_directions,sc.DIRECTIONS)
        self.assertEqual(interface.coverage_fraction,.5)
        self.assertEqual(interface.indicator_directions['rps_doc_unigram_entropy'],'non_monotone')
        self.assertIn('final_indicator_interpretation',interface.provenance.notes)

    def test_cluster_precision_is_not_raw_count(self):
        seed,_=load_settings('quality')
        result=structured_estimates(np.arange(10)/10,['a']*10,['x']*9+['y'],seed=seed,replicates=30,confidence=.95)
        self.assertEqual(result['domains']['a']['source_shards'],2)
        self.assertLess(result['domains']['a']['effective_source_count_kish'],2)
        self.assertEqual(result,structured_estimates(np.arange(10)/10,['a']*10,['x']*9+['y'],seed=seed,replicates=30,confidence=.95))

    def test_training_selection_guard_and_no_heldout_mutation(self):
        seed,_=load_settings('mixture')
        rng=np.random.default_rng(seed)
        p=rng.dirichlet(np.ones(3),60)
        mix=MixtureTable('training',np.arange(60),['a','b','c'],p)
        loss=LossTable('training',mix.indices,['y'],(2+p[:,0])[:,None])
        kwargs=dict(source_pair=('A4','A5'),seed=seed,alphas=[1e-8,.1],folds=5,
                    candidates=['linear','pairwise_interactions'],selection={'minimum_relative_gain':.05,'minimum_fold_wins':4})
        first=select_training_model(mix,loss,**kwargs)
        again=select_training_model(mix,loss,**kwargs)
        self.assertEqual(first.kind,'linear')
        self.assertEqual(first.model_sha256,again.model_sha256)
        self.assertFalse(first.cv['decision']['heldout_used'])
        test=MixtureTable('validation',np.arange(8),mix.domains,rng.dirichlet(np.ones(3),8))
        y=LossTable('validation',test.indices,['y'],(2+test.values[:,0])[:,None])
        a=evaluate(first,test,y,partition='A10_A11')
        b=evaluate(first,test,replace(y,values=y.values+10),partition='A10_A11')
        self.assertNotEqual(a['absolute'],b['absolute'])
        self.assertEqual(first.model_sha256,again.model_sha256)
        with self.assertRaises(ValueError):
            select_training_model(mix,loss,**{**kwargs,'source_pair':('A12','A13')})

    def test_scientific_release_gates_can_fail(self):
        seed,settings=load_settings('mixture')
        rng=np.random.default_rng(seed)
        p=rng.dirichlet(np.ones(3),60)
        train=MixtureTable('training',np.arange(60),['a','b','c'],p)
        loss=LossTable('training',train.indices,['y'],(2+p[:,0])[:,None])
        fit=select_training_model(train,loss,source_pair=('A4','A5'),seed=seed,
                                  alphas=[1e-8],folds=5,candidates=['linear'])
        test=MixtureTable('validation',np.arange(20),train.domains,rng.dirichlet(np.ones(3),20))
        y=LossTable('validation',test.indices,['y'],(2+test.values[:,0])[:,None])
        reports={p:evaluate(fit,test,y,partition=p) for p in ('A6_A7','A8_A9','A10_A11')}
        baseline=deepcopy(reports)
        pairs={'A10':(test,y)}
        self.assertTrue(acceptance_checks(fit,reports,baseline,pairs,settings)['release_pass'])
        acceptance = acceptance_checks(fit,reports,baseline,pairs,settings)
        scope = scope_release_receipt(fit, reports, acceptance)
        self.assertFalse(scope['scope_release_pass'])
        self.assertEqual(scope['fit_scale'], '1M')
        self.assertEqual(scope['release_validation_partition'], 'A6_A7')
        invalid_scope = deepcopy(reports)
        invalid_scope['A6_A7']['role'] = 'wrong-role'
        with self.assertRaises(ValueError):
            scope_release_receipt(fit, invalid_scope, acceptance)
        invalid_acceptance = dict(acceptance)
        invalid_acceptance['in_design_pass'] = False
        self.assertFalse(scope_release_receipt(fit, reports, invalid_acceptance)['scope_release_pass'])
        invalid_acceptance = dict(acceptance)
        invalid_acceptance['release_pass'] = False
        invalid_acceptance['absolute_transfer_pass'] = {
            'A6_A7': True, 'A8_A9': False, 'A10_A11': False,
        }
        invalid_acceptance['out_of_design_shape_pass'] = False
        invalid_acceptance['scale_invariance_supported'] = False
        self.assertTrue(scope_release_receipt(fit, reports, invalid_acceptance)['scope_release_pass'])
        invalid=deepcopy(reports)
        invalid['A6_A7']['absolute']['macro']['r2']['mean']=-1.
        self.assertFalse(acceptance_checks(fit,invalid,baseline,pairs,settings)['release_pass'])
        invalid=deepcopy(reports)
        invalid['A10_A11']['absolute']['macro']['spearman']['mean']=-1.
        self.assertFalse(acceptance_checks(fit,invalid,baseline,pairs,settings)['release_pass'])
        with self.assertRaises(ValueError):
            limited_extrapolation(fit,{'A13':(test,y)},settings)
        with self.assertRaises(ValueError):
            validation_intervals(y.values,y.values*np.nan,seed=seed,replicates=10,confidence=.95)


if __name__=='__main__':
    print('synthetic closure guard tests; seed:',load_settings('quality')[0])
    unittest.main()
