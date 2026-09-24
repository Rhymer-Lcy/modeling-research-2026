"""Compact full-record loading and explicit missingness, without Loss access."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import lzma
from pathlib import Path

import numpy as np

from src.paths import REPO_ROOT
from . import scalarize as sc
from .diagnostics import raw_issues
from .pipeline import QualityPreprocessor, QUALITY_DOMAINS


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Population:
    name: str
    values: np.ndarray
    qurater: np.ndarray
    ordinal_argmax: np.ndarray
    domains: np.ndarray
    keys: list[str]
    clusters: np.ndarray
    missing: np.ndarray
    lines: np.ndarray
    defects: list[dict]
    source: str
    sha256: str

    @property
    def complete(self):
        return ~self.missing.any(axis=1)


def confirmed_nan_fields(row: dict, literal_nans: int, allowed_fields) -> set[str]:
    """Only complete six-NaN classifier vectors may take the exclusion path."""
    issues = raw_issues(row)
    if any(item['kind'] != 'nan' or item['field'] not in allowed_fields or
           item['components'] != list(range(sc.EXPECTED_DIM[item['field']]))
           for item in issues):
        raise ValueError('unapproved raw defect; only confirmed whole-vector NaNs allowed')
    if sum(len(item['components']) for item in issues) != literal_nans:
        raise ValueError('raw literal NaN tokens do not reconcile with required fields')
    return {item['field'] for item in issues}


def load_population(path: Path, name: str, allowed_fields, domain=None) -> Population:
    before = file_hash(path)
    source = path.relative_to(REPO_ROOT).as_posix()
    values, qurater, argmax, domains, keys, clusters, missing, lines, defects = ([] for _ in range(9))
    ordinal = [n for n in sc.INDICATORS if n.startswith('modernbert_')]
    with lzma.open(path, 'rb') as handle:
        for line_number, line in enumerate(handle, 1):
            constants = Counter()
            def constant(token):
                constants[token] += 1
                return float(token)
            row = json.loads(line, parse_constant=constant)
            if set(constants) - {'NaN'}:
                raise ValueError('unexpected raw nonfinite token')
            bad = confirmed_nan_fields(row, constants['NaN'], allowed_fields)
            assigned = domain or row['_source_domain']
            if assigned not in QUALITY_DOMAINS or row.get('_source_domain', assigned) != assigned:
                raise ValueError('unknown or inconsistent domain')
            # No raw replacement: only finite fields are passed to their reducers.
            reduced = []
            for field in sc.INDICATORS:
                if field in bad:
                    reduced.append(np.nan)
                elif field in sc.NATIVE_SCALARS:
                    reduced.append(float(row[field]))
                elif field == 'qurater':
                    reduced.append(sc.reduce_qurater(row[field]))
                else:
                    reduced.append(sc.REDUCERS[field](row[field]))
            mask = np.array([field in bad for field in sc.INDICATORS])
            if not np.isfinite(np.asarray(reduced)[~mask]).all():
                raise ValueError('transform-created nonfinite result from finite raw fields')
            values.append(reduced)
            qurater.append(row['qurater'])
            argmax.append([np.nan if field in bad else sc.reduce_ordinal6_argmax(row[field]) for field in ordinal])
            domains.append(assigned)
            identity = json.dumps([assigned, row['sub_path'], row['id']], separators=(',', ':'))
            keys.append(hashlib.sha256(identity.encode()).hexdigest())
            cluster = json.dumps([assigned, row['sub_path']], separators=(',', ':'))
            clusters.append(hashlib.sha256(cluster.encode()).hexdigest())
            missing.append(mask)
            lines.append(line_number)
            if bad:
                defects.append(dict(source=source, line=line_number, fields=sorted(bad),
                                    literal_raw_nans=constants['NaN'], raw_sha256=before,
                                    line_sha256=hashlib.sha256(line).hexdigest(),
                                    exclusion_reason='required scalar remains nonfinite from confirmed raw literal NaNs'))
    if len(set(keys)) != len(keys) or not keys:
        raise ValueError('empty population or duplicate source/record identities')
    if file_hash(path) != before:
        raise ValueError('raw input changed during read')
    return Population(name, np.array(values), np.array(qurater), np.array(argmax), np.array(domains),
                      keys, np.array(clusters), np.array(missing), np.array(lines), defects, source, before)


def mid_ecdf(reference: np.ndarray, observations: np.ndarray) -> np.ndarray:
    if not len(reference) or not np.isfinite(reference).all() or not np.isfinite(observations).all():
        raise ValueError('midrank ECDF requires finite observations and reference')
    return (np.searchsorted(reference, observations, 'left') +
            np.searchsorted(reference, observations, 'right')) / (2 * len(reference))


def fit_population(reference: Population, directions, intervals, *, ordinal='expected') -> QualityPreprocessor:
    """Fit on A1 complete cases only, including the four qurater ECDFs."""
    if reference.name != 'A1':
        raise ValueError('quality reference must be A1, never an extension')
    if set(directions) != set(sc.INDICATORS):
        raise ValueError('exactly 22 processing directions required')
    for name, direction in directions.items():
        if direction not in {'higher_better', 'lower_better', 'non_monotone'}:
            raise ValueError('invalid processing direction')
        if (direction == 'non_monotone') != (name in intervals):
            raise ValueError('non-monotone processing requires a declared interval')
    for lo, hi in intervals.values():
        if not np.isfinite([lo, hi]).all() or lo >= hi:
            raise ValueError('invalid interval')
    if ordinal not in {'expected', 'argmax'}:
        raise ValueError('invalid ordinal reduction')
    complete = reference.complete
    if not complete.any():
        raise ValueError('no complete A1 reference')
    values = reference.values[complete].copy()
    if ordinal == 'argmax':
        values[:, -4:] = reference.ordinal_argmax[complete]
    sorted_values = {}
    for j, name in enumerate(sc.INDICATORS):
        if name == 'qurater':
            continue
        column = values[:, j]
        if name in intervals:
            lo, hi = intervals[name]
            column = -np.maximum(np.maximum(lo - column, column - hi), 0)
        sorted_values[name] = np.sort(column)
    return QualityPreprocessor(list(sc.INDICATORS), sorted_values,
                               [np.sort(reference.qurater[complete, j]) for j in range(4)],
                               dict(directions), dict(intervals), ordinal)


def preprocessing_hash(prep: QualityPreprocessor) -> str:
    h = hashlib.sha256(json.dumps({'indicators': prep.indicators, 'directions': prep.directions,
                                   'intervals': prep.intervals, 'ordinal': prep.ordinal_reduction,
                                   'ecdf': 'midrank'}, sort_keys=True).encode())
    for name in prep.indicators:
        if name in prep.sorted_values:
            h.update(prep.sorted_values[name].astype('<f8').tobytes())
    for col in prep.qurater_sorted:
        h.update(col.astype('<f8').tobytes())
    return h.hexdigest()


def transform_population(prep, population, *, missing_value=None, neutral_fields=()):
    """Primary removes only confirmed defects; scenarios fill FINAL scores only."""
    if missing_value is not None and (not np.isfinite(missing_value) or not 0 <= missing_value <= 1):
        raise ValueError('sensitivity values must lie in [0,1]')
    mask = population.complete if missing_value is None else np.ones(len(population.values), dtype=bool)
    raw = population.values[mask].copy()
    missing = population.missing[mask]
    if prep.ordinal_reduction == 'argmax':
        raw[:, -4:] = population.ordinal_argmax[mask]
    out = np.empty_like(raw)
    for j, name in enumerate(prep.indicators):
        finite = ~missing[:, j]
        if not np.isfinite(raw[finite, j]).all():
            raise ValueError('nonfinite value outside confirmed missingness mask')
        if name == 'qurater':
            out[:, j] = np.column_stack([mid_ecdf(prep.qurater_sorted[k], population.qurater[mask, k])
                                        for k in range(4)]).mean(axis=1)
        else:
            v = raw[finite, j]
            if name in prep.intervals:
                lo, hi = prep.intervals[name]
                v = -np.maximum(np.maximum(lo - v, v - hi), 0)
            scores = mid_ecdf(prep.sorted_values[name], v)
            out[finite, j] = 1 - scores if prep.directions[name] == 'lower_better' else scores
        if name in neutral_fields:
            out[finite, j] = 0.5
        if (~finite).any():
            if missing_value is None:
                raise ValueError('primary analysis cannot impute')
            out[~finite, j] = missing_value
    if out.shape[1] != 22 or not np.isfinite(out).all() or ((out < 0) | (out > 1)).any():
        raise ValueError('invalid canonical standardized matrix')
    return out, mask
