"""Conditional uncertainty with explicit source-shard and domain structure."""
from __future__ import annotations

import numpy as np

from .pipeline import bootstrap_mean


def mean_with_structure(values, clusters, *, seed, replicates, confidence):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all() or values.shape != np.asarray(clusters).shape:
        raise ValueError('invalid scores or cluster labels')
    _, codes = np.unique(clusters, return_inverse=True)
    counts = np.bincount(codes)
    sums = np.bincount(codes, weights=values)
    k = len(counts)
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates)
    if k == 1:
        for i in range(replicates):
            draws[i] = values[rng.integers(0, len(values), len(values))].mean()
        unit = 'document conditional on the single observed source shard'
    else:
        for i in range(replicates):
            ix = rng.integers(0, k, k)
            draws[i] = sums[ix].sum() / counts[ix].sum()
        unit = 'source shard; all records within each drawn shard retained'
    tail = (1 - confidence) / 2
    entry = {'q': float(values.mean()), 'ci': list(map(float, np.quantile(draws, [tail, 1-tail]))),
             'n': len(values), 'source_shards': k,
             'effective_source_count_kish': float(counts.sum()**2 / np.square(counts).sum()),
             'resampling_unit': unit,
             'limitation': 'conditional on A1 normalization and Q rule; cross-source variation unidentified with one shard'}
    return entry, draws


def structured_estimates(q, domains, clusters, *, seed, replicates, confidence):
    q, domains, clusters = np.asarray(q), np.asarray(domains), np.asarray(clusters)
    if q.shape != domains.shape or q.shape != clusters.shape or ((q < 0) | (q > 1)).any():
        raise ValueError('misaligned or out-of-range Q')
    names = sorted(set(domains))
    children = np.random.SeedSequence(seed).spawn(len(names))
    result, draws = {}, []
    for name, child in zip(names, children):
        mask = domains == name
        entry, sample = mean_with_structure(q[mask], clusters[mask], seed=int(child.generate_state(1)[0]),
                                            replicates=replicates, confidence=confidence)
        result[name] = entry
        draws.append(sample)
    weights = np.array([result[name]['n'] for name in names]) / len(q)
    combined = weights @ np.array(draws)
    tail = (1-confidence)/2
    return {'domains': result,
            'overall': {'q': float(q.mean()), 'ci': list(map(float, np.quantile(combined, [tail, 1-tail]))),
                        'n': len(q), 'domain_weights': dict(zip(names, map(float, weights))),
                        'equal_domain_q_sensitivity': float(np.mean([result[n]['q'] for n in names]))},
            'seed': seed, 'replicates': replicates, 'confidence': confidence,
            'conditioning': 'fixed A1 complete-case ECDFs and aggregation; observed domain shares fixed',
            'unit': 'source shard within domain, conditional document fallback for single-shard domains'}
