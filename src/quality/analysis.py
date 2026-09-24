"""Quality summaries conditional on explicit preprocessing and aggregation.

No Loss target is accepted. All random/threshold settings come from callers.
"""
from __future__ import annotations

from typing import Mapping, Sequence
import numpy as np

from .pipeline import aggregate, bootstrap_mean, conflict_summary, rank_corr
from .pipeline import rankdata


def domain_ranking(summary: dict) -> dict:
    """Descending quality ranks with average ranks for ties."""
    names = sorted(summary['domains'])
    values = np.array([summary['domains'][name]['q'] for name in names])
    ranks = rankdata(-values)
    return {'ranks': dict(zip(names, map(float, ranks))),
            'order_with_lexical_tie_break': sorted(names, key=lambda name: (-summary['domains'][name]['q'], name))}


def domain_estimates(q: np.ndarray, domains: Sequence[str], *, seed: int,
                     replicates: int, confidence: float) -> dict:
    q = np.asarray(q, dtype=float)
    domain = np.asarray(domains)
    if q.ndim != 1 or q.shape != domain.shape or not len(q):
        raise ValueError('domain labels must align with nonempty scores')
    if not np.isfinite(q).all() or ((q < 0) | (q > 1)).any():
        raise ValueError('quality scores must be finite and in [0,1]')
    names = sorted(set(domains))
    child_seeds = np.random.SeedSequence(seed).spawn(len(names))
    estimates = {}
    for name, child in zip(names, child_seeds):
        values = q[domain == name]
        local_seed = int(child.generate_state(1)[0])
        mean, lo, hi = bootstrap_mean(values, local_seed, replicates, confidence)
        estimates[name] = {'q': mean, 'ci': [lo, hi], 'n': len(values), 'seed': local_seed}
    return {'domains': estimates, 'unit': 'document within domain', 'replicates': replicates,
            'confidence': confidence, 'seed': seed,
            'conditioning': 'fixed fitted A1 preprocessing and Q rule; not uncertainty in their selection'}


def conflict_analysis(matrix: np.ndarray, *, thresholds: Sequence[float], material_rho: float,
                      families: Mapping[str, Sequence[str]]) -> dict:
    if not np.isfinite(material_rho) or not 0 < material_rho < 1:
        raise ValueError('material correlation threshold must be in (0,1)')
    report = conflict_summary(matrix, thresholds)
    for pair in report['all_pairs']:
        rho = pair['spearman']
        pair['association'] = ('antagonistic' if rho <= -material_rho else
                               'redundant' if rho >= material_rho else 'weak')
    report['material_rho'] = material_rho
    report['inference'] = 'descriptive effect sizes; no significance tests or multiple-testing claims'
    baseline = aggregate(matrix, 'equal_indicator')
    family = aggregate(matrix, 'family_balanced', families=families)
    robust = aggregate(matrix, 'robust_median')
    spread = np.ptp(matrix, axis=1)
    report['aggregation_effect'] = {}
    for method, q in [('family_balanced', family), ('robust_median', robust)]:
        report['aggregation_effect'][method] = {
            'mean_change_from_equal': float(np.mean(q - baseline)),
            'mean_absolute_change_from_equal': float(np.mean(np.abs(q - baseline))),
            'rank_correlation_with_equal': rank_corr(q, baseline),
            'by_conflict_threshold': [
                {'threshold': float(t), 'n': int(np.sum(spread >= t)),
                 'mean_absolute_change': float(np.mean(np.abs(q[spread >= t] - baseline[spread >= t])))
                 if np.any(spread >= t) else None} for t in thresholds],
        }
    return report


def overlapping_sample_comparison(sample_q, extension_q, sample_keys, extension_keys, *,
                                  seed: int, replicates: int, confidence: float) -> dict:
    """Paired union-record bootstrap preserving overlap membership.

    A1 and extensions may share records. A draw of a shared identity contributes
    to both means, so this is not an independent two-sample bootstrap. Reference
    ECDFs are held fixed. Empty-membership draws are reported and excluded.
    """
    a, b = np.asarray(sample_q, float), np.asarray(extension_q, float)
    if a.shape != (len(sample_keys),) or b.shape != (len(extension_keys),) or not len(a) or not len(b):
        raise ValueError('sample scores and identities must align')
    if not np.isfinite(a).all() or not np.isfinite(b).all() or ((a < 0) | (a > 1)).any() or ((b < 0) | (b > 1)).any():
        raise ValueError('sample Q must be finite and in [0,1]')
    if len(set(sample_keys)) != len(a) or len(set(extension_keys)) != len(b):
        raise ValueError('duplicate source/record identities')
    if replicates < 2 or not 0 < confidence < 1:
        raise ValueError('invalid bootstrap settings')
    left, right = dict(zip(sample_keys, a)), dict(zip(extension_keys, b))
    overlap = set(left) & set(right)
    if any(left[key] != right[key] for key in overlap):
        raise ValueError('overlapping identities must have identical processed Q')
    union = list(dict.fromkeys([*sample_keys, *extension_keys]))
    in_a = np.array([key in left for key in union])
    in_b = np.array([key in right for key in union])
    qa = np.array([left.get(key, 0.) for key in union])
    qb = np.array([right.get(key, 0.) for key in union])
    rng = np.random.default_rng(seed)
    differences = []
    for _ in range(replicates):
        draw = rng.integers(0, len(union), len(union))
        na, nb = in_a[draw].sum(), in_b[draw].sum()
        if na and nb:
            differences.append(float(qb[draw].sum() / nb - qa[draw].sum() / na))
    if len(differences) < 2:
        raise ValueError('too few nonempty union bootstrap replicates')
    tail = (1 - confidence) / 2
    pooled_sd = float(np.sqrt((np.var(a) + np.var(b)) / 2))
    delta = float(b.mean() - a.mean())
    return {'sample_n': len(a), 'extension_n': len(b), 'overlap_n': len(overlap),
            'sample_mean': float(a.mean()), 'extension_mean': float(b.mean()),
            'extension_minus_sample': delta,
            'difference_ci': list(map(float, np.quantile(differences, [tail, 1 - tail]))),
            'descriptive_standardized_difference': delta / pooled_sd if pooled_sd else None,
            'seed': seed, 'replicates': replicates, 'nonempty_replicates': len(differences),
            'confidence': confidence, 'unit': 'union source/record identity with shared membership',
            'conditioning': 'fixed A1 preprocessing; same-source sampling stability, not external replication'}
