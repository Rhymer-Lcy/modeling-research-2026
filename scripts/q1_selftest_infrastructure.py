"""Synthetic-only Q1 infrastructure checks; no organizer model/results fitted.

All numerical choices here are test-fixture values, not analysis defaults.
Run: python scripts/q1_selftest_infrastructure.py
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.paths import CONFIGS, REPO_ROOT
from src.interfaces import Provenance
from src.quality import scalarize as sc
from src.quality.diagnostics import raw_issues, diagnostic_reduction
from src.quality.pipeline import QualityPreprocessor, aggregate, QUALITY_DOMAINS
from src.quality.analysis import domain_estimates, domain_ranking, conflict_analysis, overlapping_sample_comparison
from src.quality.handoff import build_if1, encode_if1
from src.mixture.data import MixtureTable, LossTable, check_decimal_grid
from src.mixture.model import fit_all, predict, substitution_effect
from src.mixture.validation import (select_training_model, prediction_matrix, evaluate,
                                    paired_scale_analysis, compare_estimated_reference)
from src.mixture.handoff import build_if2, encode_if2
from scripts.q1_mixture import render_validation
from scripts.q1_quality import render_quality
from scripts import q1_mixture, q1_quality


def seed():
    return yaml.safe_load((CONFIGS / 'default.yaml').read_text())['seed']


def row(value=1.):
    result = {n: value for n in sc.NATIVE_SCALARS}
    result.update({n: [value] * sc.EXPECTED_DIM[n] for n in sc.LIST_FIELDS})
    return result


def directions():
    return {name: 'higher_better' for name in sc.INDICATORS}


def families():
    return {'ordinal': [n for n in sc.INDICATORS if n.startswith('modernbert_')],
            'other': [n for n in sc.INDICATORS if not n.startswith('modernbert_')]}


class RawAndQualityChecks(unittest.TestCase):
    def test_defect_classes(self):
        bad = row()
        del bad['dsir_books']
        bad['dsir_wiki'] = None
        bad['dsir_math'] = 'NaN'
        bad['ad_en'] = [np.inf, -np.inf]
        bad['modernbert_cleanliness'] = [np.nan] * 6
        bad['fineweb_edu'] = []
        kinds = {item['kind'] for item in raw_issues(bad)}
        self.assertEqual(kinds, {'absent_field', 'null', 'non_numeric', 'positive_inf', 'negative_inf', 'nan', 'wrong_width'})
        for badfield in ('ad_en', 'modernbert_cleanliness'):
            fixture = row()
            fixture[badfield] = bad[badfield]
            with self.assertRaises(ValueError):
                QualityPreprocessor.fit([fixture], directions=directions())

    def test_nan_origin_and_argmax_trap(self):
        bad = row()
        bad['modernbert_reasoning'] = [float('nan')] * 6
        issues, created = diagnostic_reduction(bad)
        self.assertEqual(issues[0]['kind'], 'nan')
        self.assertEqual(issues[0]['components'], list(range(6)))
        self.assertEqual(created, [])
        # NumPy argmax alone manufactures a valid-looking zero on all-NaN logits.
        self.assertEqual(sc.reduce_ordinal6_argmax(bad['modernbert_reasoning']), 0)
        with self.assertRaises(ValueError):
            QualityPreprocessor.fit([bad], directions=directions(), ordinal_reduction='argmax')

    def test_transform_created_overflow(self):
        fixture = row()
        fixture['qurater'] = [1e308] * 4
        issues, created = diagnostic_reduction(fixture)
        self.assertEqual(issues, [])
        self.assertEqual(created, ['qurater'])

    def test_explicit_direction_contract(self):
        with self.assertRaises(TypeError):
            QualityPreprocessor.fit([row()])
        with self.assertRaises(ValueError):
            QualityPreprocessor.fit([row()], directions=sc.DIRECTIONS)
        missing = directions()
        missing.pop('qurater')
        with self.assertRaises(ValueError):
            QualityPreprocessor.fit([row()], directions=missing)

    def test_interval_and_reference_semantics(self):
        configured = directions()
        name = 'rps_doc_mean_word_length'
        configured[name] = 'non_monotone'
        reference = [row(x) for x in (1., 5., 50.)]
        prep = QualityPreprocessor.fit(reference, directions=configured, intervals={name: [3., 10.]})
        column = sc.INDICATORS.index(name)
        inside = prep.transform_row(row(6.))[column]
        self.assertEqual(inside, prep.transform_row(row(5.))[column])
        self.assertGreater(inside, prep.transform_row(row(50.))[column])
        self.assertEqual(len(prep.indicators), 22)
        # A2/A3 values are evaluated against the stored A1 reference, never refitted.
        original = prep.sorted_values['dsir_books'].copy()
        prep.transform([row(1000.)])
        np.testing.assert_array_equal(original, prep.sorted_values['dsir_books'])

    def test_families_are_explicit_and_not_indicator_counts(self):
        x = np.zeros((2, 22))
        x[:, -4:] = 1
        np.testing.assert_allclose(aggregate(x, 'family_balanced', families=families()), [.5, .5])
        np.testing.assert_allclose(aggregate(x, 'equal_indicator'), [4 / 22, 4 / 22])
        with self.assertRaises(ValueError):
            aggregate(x, 'family_balanced')
        with self.assertRaises(ValueError):
            aggregate(x, 'family_balanced', families={'bad': sc.INDICATORS + ['qurater']})

    def test_conflict_descriptive_and_effect(self):
        x = np.tile(np.linspace(0., 1., 12)[:, None], (1, 22))
        x[:, 0] = 1 - x[:, 0]
        report = conflict_analysis(x, thresholds=[.1, .5, .9], material_rho=.3, families=families())
        self.assertEqual(len(report['all_pairs']), 231)
        self.assertIn('antagonistic', {p['association'] for p in report['all_pairs']})
        rates = list(report['threshold_rate'].values())
        self.assertEqual(rates, sorted(rates, reverse=True))
        self.assertIn('by_conflict_threshold', report['aggregation_effect']['family_balanced'])

    def test_domain_uncertainty_and_overlap(self):
        q = np.array([.2, .4, .6, .8])
        settings = dict(seed=seed(), replicates=100, confidence=.95)
        estimates = domain_estimates(q, ['a', 'a', 'b', 'b'], **settings)
        self.assertEqual(estimates, domain_estimates(q, ['a', 'a', 'b', 'b'], **settings))
        self.assertEqual(estimates['domains']['a']['n'], 2)
        ranks = domain_ranking({'domains': {'a': {'q': .5}, 'b': {'q': .5}, 'c': {'q': .9}}})
        self.assertEqual(ranks['ranks'], {'a': 2.5, 'b': 2.5, 'c': 1.})
        paired = overlapping_sample_comparison(q, q, ['a', 'b', 'c', 'd'], ['a', 'b', 'c', 'd'], **settings)
        self.assertEqual(paired['difference_ci'], [0., 0.])
        self.assertEqual(paired['overlap_n'], 4)
        with self.assertRaises(ValueError):
            overlapping_sample_comparison(q, q / 2, ['a', 'b', 'c', 'd'], ['a', 'b', 'c', 'd'], **settings)


class ResponseChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(seed())
        p = rng.dirichlet(np.ones(3), 60)
        p[0] = [1., 0., 0.]
        cls.mix = MixtureTable('synthetic training', np.arange(len(p)), ['a', 'b', 'c'], p)
        y = 2 + p[:, 0] + 8 * p[:, 1] * p[:, 2]
        cls.loss = LossTable('synthetic training', cls.mix.indices, ['y'], y[:, None])
        cls.settings = dict(source_pair=('A4', 'A5'), seed=seed(), alphas=[1e-8, .01], folds=4,
                            candidates=['linear', 'pairwise_interactions'])
        cls.frozen = select_training_model(cls.mix, cls.loss, **cls.settings)
        p = rng.dirichlet(np.ones(3), 16)
        cls.test_mix = MixtureTable('synthetic validation', np.arange(16), ['a', 'b', 'c'], p)
        cls.test_loss = LossTable('synthetic validation', cls.test_mix.indices, ['y'],
                                  (2 + p[:, 0] + 8 * p[:, 1] * p[:, 2])[:, None])

    def test_controlled_nonlinearity_and_cv_determinism(self):
        self.assertEqual(self.frozen.kind, 'pairwise_interactions')
        again = select_training_model(self.mix, self.loss, **self.settings)
        self.assertEqual(self.frozen.model_sha256, again.model_sha256)
        self.assertEqual(self.frozen.cv, again.cv)
        valid = sum(self.frozen.cv['validation_indices'], [])
        self.assertEqual(sorted(valid), self.mix.indices.tolist())

    def test_role_separation(self):
        for pair in [('A6', 'A7'), ('A12', 'A13'), ('A14', 'A15')]:
            settings = {**self.settings, 'source_pair': pair}
            with self.assertRaises(ValueError):
                select_training_model(self.mix, self.loss, **settings)
        with self.assertRaises(ValueError):
            evaluate(self.frozen, self.test_mix, self.test_loss, partition='A13')
        with self.assertRaises(ValueError):
            evaluate(self.frozen, self.mix, self.loss, partition='A6_A7')

    def test_heldout_changes_cannot_change_frozen_fit(self):
        before = self.frozen.model_sha256
        first = evaluate(self.frozen, self.test_mix, self.test_loss, partition='A6_A7')
        shifted = replace(self.test_loss, values=self.test_loss.values + 10)
        second = evaluate(self.frozen, self.test_mix, shifted, partition='A6_A7')
        self.assertEqual(before, self.frozen.model_sha256)
        self.assertNotEqual(first['absolute'], second['absolute'])
        self.assertAlmostEqual(first['centered_shape']['macro']['rmse']['mean'], second['centered_shape']['macro']['rmse']['mean'])

    def test_frozen_mutation_detected(self):
        frozen = select_training_model(self.mix, self.loss, **self.settings)
        key = next(iter(frozen.fits[0].coefficients))
        frozen.fits[0].coefficients[key] += .1
        with self.assertRaises(ValueError):
            prediction_matrix(frozen, self.test_mix)

    def test_duplicate_designs_rejected_for_row_cv(self):
        duplicated = replace(self.mix, values=self.mix.values.copy())
        duplicated.values[-1] = duplicated.values[0]
        with self.assertRaises(ValueError):
            select_training_model(duplicated, self.loss, **self.settings)

    def test_storage_precision_and_rounding_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture.csv'
            path.write_text('index,a,b\n1,0.501,0.500\n')
            check_decimal_grid(path, 3, .001)
            with self.assertRaises(ValueError):
                check_decimal_grid(path, 3, .01)
            with self.assertRaises(ValueError):
                check_decimal_grid(path, 2, .001)

    def test_prediction_column_order_and_substitution(self):
        shuffled = replace(self.test_mix, domains=['c', 'a', 'b'], values=self.test_mix.values[:, [2, 0, 1]])
        np.testing.assert_allclose(prediction_matrix(self.frozen, self.test_mix), prediction_matrix(self.frozen, shuffled))
        fit = self.frozen.fits[0]
        domain = next(d for d in self.mix.domains if d != fit.reference)
        base = MixtureTable('fixture', np.array([0]), self.mix.domains, np.array([[1/3] * 3]))
        delta = .05
        effect = substitution_effect(fit, base, domain, delta)
        modified = base.values.copy()
        modified[:, base.domains.index(domain)] += delta
        modified[:, base.domains.index(fit.reference)] -= delta
        np.testing.assert_allclose(effect, predict(fit, replace(base, values=modified)) - predict(fit, base))
        with self.assertRaises(ValueError):
            substitution_effect(fit, base, domain, 2.)

    def test_paired_scale_and_reference_labels(self):
        shifted = replace(self.test_loss, values=.8 * self.test_loss.values + .1)
        paired = paired_scale_analysis(self.test_mix, self.test_loss, self.test_mix, shifted)
        self.assertAlmostEqual(paired['per_target']['y']['ordering_spearman'], 1.)
        badmix = replace(self.test_mix, indices=self.test_mix.indices[::-1])
        with self.assertRaises(ValueError):
            paired_scale_analysis(self.test_mix, self.test_loss, badmix, shifted)
        reference = compare_estimated_reference(self.test_loss, self.test_loss.values, source='A13')
        self.assertEqual(reference['role'], 'estimated_reference_NOT_validation')
        self.assertFalse(reference['fit_use'])


class InterfaceBuilderChecks(unittest.TestCase):
    def fixture(self):
        rng = np.random.default_rng(seed())
        domains = ['d' + str(i) for i in range(17)]
        p = rng.dirichlet(np.ones(17), 36)
        mix = MixtureTable('synthetic training', np.arange(36), domains, p)
        targets = ['metric/the_pile_' + d + '_val_loss' for d in domains[:13]]
        loss = LossTable('synthetic training', mix.indices, targets, 2 + p[:, :13])
        return rng, mix, loss

    def test_if1_complete_finite_and_deterministic(self):
        _, mix, _ = self.fixture()
        estimates = {'domains': {d: {'q': .5, 'ci': [.4, .6], 'n': 25} for d in QUALITY_DOMAINS}, 'unit': 'synthetic document'}
        mapping = {d: QUALITY_DOMAINS[j] if j < 6 else None for j, d in enumerate(mix.domains)}
        kinds = {d: 'direct' if mapping[d] else 'inferred' for d in mix.domains}
        notes = dict(q_definition='synthetic fixture', directions=directions(), normalization='fixture',
                     missing_signal_policy='reject', stability='fixture only; not organizer data')
        provenance = Provenance('reference', ['synthetic fixture'], 'Not a scientific result')
        interface = build_if1(estimates, mix, mapping, kinds, provenance=provenance, processing_notes=notes)
        interface.validate()
        self.assertEqual(encode_if1(interface), encode_if1(interface))
        self.assertEqual(len(json.loads(encode_if1(interface))['indicator_directions']), 22)
        estimates['domains']['arxiv']['ci'] = [np.nan, .6]
        with self.assertRaises(ValueError):
            build_if1(estimates, mix, mapping, kinds, provenance=provenance, processing_notes=notes)

    def test_if2_requires_all_roles_and_preserves_encoding(self):
        rng, mix, loss = self.fixture()
        frozen = select_training_model(mix, loss, source_pair=('A4', 'A5'), seed=seed(),
                                       alphas=[1e-8], folds=3, candidates=['linear'])
        p = rng.dirichlet(np.ones(17), 8)
        testmix = MixtureTable('synthetic validation', np.arange(8), mix.domains, p)
        testloss = LossTable('synthetic validation', testmix.indices, loss.columns, 2 + p[:, :13])
        validations = {key: evaluate(frozen, testmix, testloss, partition=key)
                       for key in ('A6_A7', 'A8_A9', 'A10_A11')}
        refs = {source: compare_estimated_reference(testloss, testloss.values, source=source) for source in ('A13', 'A15')}
        kwargs = dict(renormalisation='synthetic row division', provenance=Provenance('reference', ['synthetic fixture']))
        interface = build_if2(frozen, validations, refs, **kwargs)
        interface.validate()
        self.assertEqual(len(interface.domains_without_loss), 4)
        blob = encode_if2(interface)
        again = build_if2(frozen, validations, refs, **kwargs)
        self.assertEqual(hashlib.sha256(blob).hexdigest(), hashlib.sha256(encode_if2(again)).hexdigest())
        self.assertIn('__intercept__', next(iter(interface.coefficients.values())))
        text = render_validation(frozen, validations, {}, {})
        self.assertEqual(text, render_validation(frozen, validations, {}, {}))
        self.assertIn('A10_A11', text)
        self.assertIn(frozen.model_sha256, text)
        with self.assertRaises(ValueError):
            build_if2(frozen, {}, refs, **kwargs)
        refs['A13']['fit_use'] = True
        with self.assertRaises(ValueError):
            build_if2(frozen, validations, refs, **kwargs)

    def test_quality_report_fixture_and_configuration_gates(self):
        x = np.tile(np.linspace(0., 1., 6)[:, None], (1, 22))
        estimates = domain_estimates(aggregate(x, 'equal_indicator'), ['fixture'] * 6,
                                     seed=seed(), replicates=20, confidence=.95)
        report = {'fixture': {'aggregators': {'equal_indicator': estimates},
                              'conflict': conflict_analysis(x, thresholds=[.1], material_rho=.3, families=families())}}
        self.assertEqual(render_quality(report, {}, {'fixture': True}), render_quality(report, {}, {'fixture': True}))
        # Current no-config behavior is part of this pending-decision checkpoint.
        if not (CONFIGS / 'q1.yaml').exists():
            for name in ('q1_quality.py', 'q1_mixture.py'):
                result = subprocess.run([sys.executable, str(REPO_ROOT / 'scripts' / name)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('M1 configuration approval remains required', result.stderr)

    def test_mixture_entrypoint_on_synthetic_loader(self):
        rng, training, training_loss = self.fixture()
        p = rng.dirichlet(np.ones(17), 8)
        test = MixtureTable('synthetic validation', np.arange(8), training.domains, p)
        loss = LossTable('synthetic validation', test.indices, training_loss.columns, 2 + p[:, :13])
        pairs = {'A4': (training, training_loss), 'A6': (test, loss), 'A8': (test, loss), 'A10': (test, loss)}
        events = []
        def load_pair(_root, name, **_kwargs):
            events.append(name)
            return pairs[name]
        def select(*args, **kwargs):
            value = select_training_model(*args, **kwargs)
            events.append('frozen')
            return value
        settings = dict(row_sum_tolerance=.0085, stored_decimal_places=3, cv_folds=3,
                        ridge_alphas=[1e-8], candidates=['linear'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(q1_mixture, 'load_settings', return_value=(seed(), settings)), \
                 patch.object(q1_mixture, 'load_pair', side_effect=load_pair), \
                 patch.object(q1_mixture, 'select_training_model', side_effect=select), \
                 patch.object(q1_mixture, 'check_decimal_grid'), \
                 patch.object(q1_mixture, 'TABLES', root / 'tables'), \
                 patch.object(q1_mixture, 'REPO_ROOT', root):
                self.assertEqual(q1_mixture.main(), 0)
                output = root / 'tables' / 'q1-mixture-validation.md'
                before = output.read_bytes()
                self.assertEqual(events[:2], ['A4', 'frozen'])
                self.assertNotIn('A12', events)
                self.assertEqual(q1_mixture.main(), 0)
                self.assertEqual(before, output.read_bytes())

    def test_quality_entrypoint_rejects_raw_defect_before_output(self):
        settings = dict(bootstrap_replicates=20, confidence=.95, conflict_thresholds=[.1],
                        material_rank_correlation=.3, aggregators=['equal_indicator'], families=families(),
                        direction_overrides=directions(), desirability_intervals={}, missing_signal_policy='reject')
        bad = row()
        bad['modernbert_professionalism'] = [np.nan] * 6
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(q1_quality, 'load_settings', return_value=(seed(), settings)), \
                 patch.object(q1_quality, 'require', side_effect=lambda path: path), \
                 patch.object(q1_quality, 'stream_quality', return_value=iter([bad])), \
                 patch.object(q1_quality, 'TABLES', root / 'tables'):
                with self.assertRaisesRegex(ValueError, 'raw quality record'):
                    q1_quality.main()
                self.assertFalse((root / 'tables').exists())


if __name__ == '__main__':
    print('synthetic fixtures only; project seed:', seed())
    unittest.main()
