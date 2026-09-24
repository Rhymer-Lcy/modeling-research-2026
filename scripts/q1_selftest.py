"""Failure-first checks for inherited Q1 implementation repairs.

Run from the repository root: python scripts/q1_selftest.py
Fixtures are synthetic; no organizer input is changed.
"""
from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy.stats import spearmanr
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.paths import CONFIGS
from src.quality import scalarize as sc
from src.quality.pipeline import QualityPreprocessor, PROVISIONAL_DIRECTIONS, aggregate, bootstrap_mean, conflict_summary, rank_corr, rankdata
from src.mixture.data import MixtureTable, LossTable, load_mixture, load_loss
from src.mixture.mapping import mapped_quality, mass_weighted_coverage, load_mapping
from src.mixture.model import contrast_matrix, fit_all, metrics, predict


def record() -> dict:
    row = {n: 1.0 for n in sc.NATIVE_SCALARS}
    row.update({n: [0.0] * sc.EXPECTED_DIM[n] for n in sc.LIST_FIELDS})
    row['_source_domain'] = 'arxiv'
    return row


class QualityChecks(unittest.TestCase):
    def test_ties_and_constants(self):
        np.testing.assert_array_equal(rankdata(np.array([2., 2., 4.])), [1.5, 1.5, 3.])
        self.assertIsNone(rank_corr(np.ones(5), np.arange(5)))
        x, y = np.array([1., 1., 2., 3.]), np.array([3., 2., 2., 1.])
        self.assertAlmostEqual(rank_corr(x, y), spearmanr(x, y).statistic)
        perm = [2, 0, 3, 1]
        self.assertAlmostEqual(rank_corr(x[perm], y[perm]), rank_corr(x, y))

    def test_schema_and_nonfinite_fail_closed(self):
        row = record()
        prep = QualityPreprocessor.fit([row], directions=PROVISIONAL_DIRECTIONS)
        matrix, domains = prep.transform([row])
        self.assertEqual(matrix.shape, (1, 22))
        self.assertEqual(domains, ['arxiv'])
        malformed = record()
        malformed['qurater'] = [0., 0., 0.]
        with self.assertRaises(ValueError):
            QualityPreprocessor.fit([malformed], directions=PROVISIONAL_DIRECTIONS)
        for field in ('dsir_books', 'qurater'):
            bad = record()
            bad[field] = float('nan') if field == 'dsir_books' else [0., 0., 0., float('nan')]
            with self.assertRaises(ValueError):
                QualityPreprocessor.fit([bad], directions=PROVISIONAL_DIRECTIONS)
            with self.assertRaises(ValueError):
                prep.transform([bad])

    def test_conflict_categories(self):
        x = np.tile(np.linspace(0, 1, 8)[:, None], (1, 22))
        x[:, 1] = 1 - x[:, 0]
        report = conflict_summary(x, [0., .5, 1.])
        self.assertTrue(all(p['spearman'] < 0 for p in report['most_antagonistic']))
        self.assertTrue(all(p['spearman'] > 0 for p in report['most_redundant']))
        self.assertEqual(report['threshold_rate']['0.0'], 1.)
        self.assertEqual(len(conflict_summary(np.ones((3, 22)), [.5])['undefined_pairs']), 231)
        with self.assertRaises(ValueError):
            aggregate(np.full((2, 22), np.nan), 'equal_indicator')
        with self.assertRaises(ValueError):
            conflict_summary(x, [1.1])

    def test_bootstrap_reproducible(self):
        seed = yaml.safe_load((CONFIGS / 'default.yaml').read_text())['seed']
        values = np.arange(10) / 10
        first = bootstrap_mean(values, seed, 100, .95)
        self.assertEqual(first, bootstrap_mean(values, seed, 100, .95))
        self.assertLessEqual(first[1], first[0])
        self.assertGreaterEqual(first[2], first[0])
        with self.assertRaises(ValueError):
            bootstrap_mean(np.array([np.nan]), seed, 100, .95)


class MixtureChecks(unittest.TestCase):
    def test_mapping_partial_and_zero_mass(self):
        mix = MixtureTable('fixture', np.arange(3), ['known', 'unknown'],
                           np.array([[0., 1.], [.25, .75], [.501, .501]]))
        mapping = {'known': 'q', 'unknown': None}
        mass, q = mapped_quality(mix, mapping, {'q': .8})
        np.testing.assert_allclose(mass, [0., .25, .5])
        self.assertTrue(np.isnan(q[0]))
        np.testing.assert_allclose(q[1:], [.8, .8])
        self.assertAlmostEqual(mass_weighted_coverage(mix, mapping), .25)
        invalid = MixtureTable('fixture', np.array([0]), ['known', 'unknown'], np.zeros((1, 2)))
        with self.assertRaises(ValueError):
            mapped_quality(invalid, mapping, {'q': .8})

    def test_explicit_unmapped_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mapping.csv'
            path.write_text('mixture_domain,quality_domain,mapping_type\na,(none),unmapped\n')
            mapping, kinds = load_mapping(path, ['a'])
            self.assertIsNone(mapping['a'])
            self.assertEqual(kinds['a'], 'unmapped')

    def test_loaders_reject_invalid_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mixture.csv'
            names = ['index'] + ['train_the_pile_d' + str(j) for j in range(17)]
            def write(values, header=names):
                with path.open('w', newline='') as handle:
                    writer = csv.writer(handle)
                    writer.writerow(header)
                    writer.writerows(values)
            valid = [1, 1.] + [0.] * 16
            write([valid])
            self.assertEqual(load_mixture(path, 'fixture', row_sum_tolerance=.0085).values.shape, (1, 17))
            for rows in ([valid, valid], [[1, .99] + [0.] * 16], [[1, float('nan')] + [0.] * 16]):
                write(rows)
                with self.assertRaises(ValueError):
                    load_mixture(path, 'fixture', row_sum_tolerance=.0085)
            write([valid], ['index'] + ['train_the_pile_d'] * 17)
            with self.assertRaises(ValueError):
                load_mixture(path, 'fixture', row_sum_tolerance=.0085)
            path.write_text('index,metric/the_pile_d_val_loss\n1,1\n')
            with self.assertRaises(ValueError):
                load_loss(path, 'fixture')

    def test_contrast_and_metrics(self):
        mix = MixtureTable('fixture', np.arange(2), ['a', 'b'], np.array([[.501, .501], [0., 1.]]))
        np.testing.assert_allclose(contrast_matrix(mix, 'b')[:, 0], [.5, 0.])
        m = metrics(np.ones(3), np.arange(3))
        self.assertIsNone(m['spearman'])
        self.assertIsNone(m['r2'])
        self.assertGreater(m['mean_absolute_relative_error'], abs(m['mean_relative_error']))
        self.assertIsNone(metrics(np.array([0., 1.]), np.array([1., 1.]))['mean_relative_error'])

    def test_ridge_deterministic_and_index_guard(self):
        seed = yaml.safe_load((CONFIGS / 'default.yaml').read_text())['seed']
        p = np.linspace(0., 1., 20)
        mix = MixtureTable('fixture', np.arange(20), ['a', 'b'], np.column_stack((p, 1 - p)))
        loss = LossTable('fixture', mix.indices, ['y'], (2 + p)[:, None])
        ref, fits = fit_all(mix, loss, seed, [1e-8, .1], 4)
        self.assertEqual((ref, fits), fit_all(mix, loss, seed, [1e-8, .1], 4))
        np.testing.assert_allclose(predict(fits[0], mix), loss.values[:, 0], atol=1e-7)
        bad = LossTable('fixture', mix.indices[::-1], ['y'], loss.values)
        with self.assertRaises(ValueError):
            fit_all(mix, bad, seed, [1e-8], 4)


if __name__ == '__main__':
    print('seed:', yaml.safe_load((CONFIGS / 'default.yaml').read_text())['seed'])
    unittest.main()
