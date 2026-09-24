"""Reproducible Q1a quality scoring and conflict analysis.

The fitted preprocessing is deliberately small and data-only: A1 empirical
rank maps are fitted once, then applied unchanged to A1, A2 and A3. No loss
column is read by this module.
"""
from __future__ import annotations

import json
import lzma
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Sequence

import numpy as np
from scipy.stats import rankdata as average_ranks

from . import scalarize as sc
from .diagnostics import require_finite_record

PROVISIONAL_DIRECTIONS = dict(sc.DIRECTIONS)
# Inherited provisional analyst choices, not certified scientific directions.
# In particular, the mean-word-length override needs reconsideration against
# interval-based literature. The tracked raw classifications remain in sc.
PROVISIONAL_DIRECTIONS.update({
    "rps_doc_unigram_entropy": "higher_better",
    "rps_lines_numerical_chars_fraction": "lower_better",
    "rps_doc_mean_word_length": "higher_better",
})
FAMILIES = {
    "dsir": ["dsir_books", "dsir_wiki", "dsir_math"],
    "rps": [n for n in sc.NATIVE_SCALARS if n.startswith("rps_")],
    "model_raters": list(sc.LIST_FIELDS),
}
QUALITY_DOMAINS = ["arxiv", "github", "stackexchange", "wikipedia", "book", "c4", "commoncrawl"]


def stream_quality(path: Path, domain: str | None = None) -> Iterator[dict]:
    with lzma.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if domain is not None:
                    if row.get('_source_domain', domain) != domain:
                        raise ValueError('quality record domain disagrees with its assigned file domain')
                    row["_source_domain"] = domain
                yield row


def _ecdf(sorted_values: np.ndarray, values: np.ndarray) -> np.ndarray:
    if not len(sorted_values) or not np.isfinite(values).all():
        raise ValueError("ECDF requires a nonempty finite reference and finite observations")
    return np.searchsorted(sorted_values, values, side="right") / len(sorted_values)


@dataclass
class QualityPreprocessor:
    indicators: List[str]
    sorted_values: Dict[str, np.ndarray]
    qurater_sorted: List[np.ndarray]
    directions: Dict[str, str]
    intervals: Dict[str, tuple[float, float]]
    ordinal_reduction: str

    @staticmethod
    def _desirable(value: float, interval: tuple[float, float]) -> float:
        lo, hi = interval
        return -max(lo - value, 0.0, value - hi)

    @staticmethod
    def _reduce(row, ecdfs, ordinal_reduction):
        require_finite_record(row)
        reduced = sc.scalarize_record(dict(row), ecdfs)
        if ordinal_reduction == 'argmax':
            for name in sc.LIST_FIELDS:
                if name.startswith('modernbert_'):
                    reduced[name] = sc.reduce_ordinal6_argmax(row[name])
        if not np.isfinite(list(reduced.values())).all():
            raise ValueError('non-finite scalarization result from finite raw input')
        return reduced

    @classmethod
    def fit(cls, rows: Iterable[Mapping[str, object]], *, directions: Mapping[str, str],
            intervals: Mapping[str, Sequence[float]] | None = None,
            ordinal_reduction: str = 'expected') -> "QualityPreprocessor":
        intervals = dict(intervals or {})
        if set(directions) != set(sc.INDICATORS):
            raise ValueError('explicit directions for exactly 22 indicators are required')
        if set(intervals) - set(sc.INDICATORS) or 'qurater' in intervals:
            raise ValueError('invalid desirability interval fields')
        for name, direction in directions.items():
            if direction not in {'higher_better', 'lower_better', 'non_monotone'}:
                raise ValueError('unknown direction')
            if (direction == 'non_monotone') != (name in intervals):
                raise ValueError('each non-monotone direction requires an explicit interval')
        for interval in intervals.values():
            if len(interval) != 2 or not np.isfinite(interval).all() or interval[0] >= interval[1]:
                raise ValueError('desirability intervals require finite ordered endpoints')
        if ordinal_reduction not in {'expected', 'argmax'}:
            raise ValueError('unknown ordinal reduction')
        values: Dict[str, List[float]] = {n: [] for n in sc.INDICATORS if n != "qurater"}
        qcols: List[List[float]] = [[], [], [], []]
        n_rows = 0
        for row in rows:
            reduced = cls._reduce(row, (), ordinal_reduction)
            for n in values:
                values[n].append(cls._desirable(reduced[n], intervals[n]) if n in intervals else reduced[n])
            for j, x in enumerate(row["qurater"]):  # type: ignore[index]
                qcols[j].append(float(x))
            n_rows += 1
        if not n_rows:
            raise ValueError("cannot fit quality preprocessing on no records")
        sorted_values = {n: np.sort(np.asarray(v, dtype=float)) for n, v in values.items()}
        return cls(list(sc.INDICATORS), sorted_values,
                   [np.sort(np.asarray(v, dtype=float)) for v in qcols],
                   dict(directions), {k: tuple(v) for k, v in intervals.items()}, ordinal_reduction)

    def transform_row(self, row: Mapping[str, object]) -> np.ndarray:
        ecdfs = [lambda x, a=a: float(_ecdf(a, np.asarray([x]))[0])
                 for a in self.qurater_sorted]
        reduced = self._reduce(row, ecdfs, self.ordinal_reduction)
        out = np.empty(len(self.indicators), dtype=float)
        for i, name in enumerate(self.indicators):
            if name == "qurater":
                out[i] = reduced[name]
            else:
                a = self.sorted_values[name]
                value = self._desirable(reduced[name], self.intervals[name]) if name in self.intervals else reduced[name]
                out[i] = float(_ecdf(a, np.asarray([value]))[0])
            if self.directions[name] == "lower_better":
                out[i] = 1.0 - out[i]
        return np.clip(out, 0.0, 1.0)

    def transform(self, rows: Iterable[Mapping[str, object]]) -> tuple[np.ndarray, List[str]]:
        matrix: List[np.ndarray] = []
        domains: List[str] = []
        for row in rows:
            matrix.append(self.transform_row(row))
            domains.append(str(row.get("_source_domain", "(none)")))
        if not matrix:
            raise ValueError("no quality rows to transform")
        arr = np.asarray(matrix, dtype=float)
        if arr.shape[1] != 22 or not np.isfinite(arr).all() or ((arr < 0) | (arr > 1)).any():
            raise ValueError("quality transform did not produce a finite 22-column [0,1] matrix")
        return arr, domains


def aggregate(matrix: np.ndarray, method: str, *, families: Mapping[str, Sequence[str]] | None = None) -> np.ndarray:
    if matrix.ndim != 2 or matrix.shape[1] != 22:
        raise ValueError("expected a records x 22 matrix")
    if not np.isfinite(matrix).all() or ((matrix < 0) | (matrix > 1)).any():
        raise ValueError("aggregation requires finite scores in [0,1]")
    if method == "equal_indicator":
        return matrix.mean(axis=1)
    if method == "robust_median":
        return np.median(matrix, axis=1)
    if method == "family_balanced":
        if not families or any(not names for names in families.values()):
            raise ValueError('family-balanced aggregation requires explicit nonempty families')
        names = [name for group in families.values() for name in group]
        if len(names) != 22 or set(names) != set(sc.INDICATORS):
            raise ValueError('families must partition all 22 indicators exactly once')
        idx = {n: i for i, n in enumerate(sc.INDICATORS)}
        family_scores = []
        for names in families.values():
            family_scores.append(matrix[:, [idx[n] for n in names]].mean(axis=1))
        return np.mean(np.vstack(family_scores), axis=0)
    raise ValueError(f"unknown aggregation method: {method}")


def rankdata(x: np.ndarray) -> np.ndarray:
    """Average tied ranks; row order must not create an association."""
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("rank input must be a finite vector")
    return average_ranks(x, method="average")


def rank_corr(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) != len(y):
        raise ValueError("rank inputs must have matching lengths")
    rx, ry = rankdata(x), rankdata(y)
    if len(rx) < 2 or np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def conflict_summary(matrix: np.ndarray, taus: Sequence[float]) -> dict:
    aggregate(matrix, "equal_indicator")  # Validate the normalized input.
    if not len(matrix) or not taus or any(not 0 <= t <= 1 for t in taus):
        raise ValueError("conflict requires records and thresholds in [0,1]")
    spread = matrix.max(axis=1) - matrix.min(axis=1)
    rates = {str(t): float(np.mean(spread >= t)) for t in taus}
    pairs = []
    undefined = []
    ranks = average_ranks(matrix, method='average', axis=0)
    varying = np.std(ranks, axis=0) > 0
    corr = np.full((22, 22), np.nan)
    if np.sum(varying) >= 2:
        corr[np.ix_(varying, varying)] = np.corrcoef(ranks[:, varying], rowvar=False)
    for i, left in enumerate(sc.INDICATORS):
        for j in range(i + 1, len(sc.INDICATORS)):
            r = float(corr[i, j])
            if not np.isfinite(r):
                undefined.append([left, sc.INDICATORS[j]])
                continue
            pairs.append((abs(r), r, left, sc.INDICATORS[j]))
    pairs.sort(reverse=True)
    return {
        "definition": "record conflict is max(normalized indicators)-min(normalized indicators)",
        "threshold_rate": rates,
        "most_antagonistic": [{"indicator_a": a, "indicator_b": b, "spearman": r}
                              for _, r, a, b in sorted(pairs, key=lambda z: z[1]) if r < 0][:10],
        "most_redundant": [{"indicator_a": a, "indicator_b": b, "spearman": r}
                           for _, r, a, b in pairs if r > 0][:10],
        "undefined_pairs": undefined,
        "all_pairs": [{'indicator_a': a, 'indicator_b': b, 'spearman': r}
                      for _, r, a, b in pairs],
        "spread_quantiles": {str(q): float(np.quantile(spread, q)) for q in (0.5, 0.9, 0.95)},
    }


def bootstrap_mean(values: np.ndarray, seed: int, replicates: int,
                   confidence: float) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("bootstrap requires a nonempty finite domain vector")
    if replicates < 2 or not 0 < confidence < 1:
        raise ValueError("invalid bootstrap replicate count or confidence")
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates, dtype=float)
    for i in range(replicates):
        draws[i] = float(np.mean(values[rng.integers(0, len(values), len(values))]))
    tail = (1 - confidence) / 2
    return float(np.mean(values)), float(np.quantile(draws, tail)), float(np.quantile(draws, 1 - tail))
