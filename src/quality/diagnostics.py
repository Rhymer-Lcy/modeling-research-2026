"""Raw-signal diagnostics, with no missing-value treatment or quality fitting."""
from __future__ import annotations

import math
from numbers import Real
from typing import Mapping

import numpy as np

from . import scalarize as sc


def raw_issues(row: Mapping[str, object]) -> list[dict]:
    """Locate missing, malformed and non-finite components before reduction.

    Component indices are zero-based; scalar fields use index zero. No raw
    content or record identifiers are included. A null is distinct from NaN.
    """
    issues = []
    for name in sc.INDICATORS:
        if name not in row:
            issues.append({'field': name, 'kind': 'absent_field', 'components': []})
            continue
        value = row[name]
        expected = sc.EXPECTED_DIM.get(name)
        if expected is not None:
            if not isinstance(value, (list, tuple)):
                issues.append({'field': name, 'kind': 'null_list' if value is None else 'malformed_list', 'components': []})
                continue
            if len(value) != expected:
                issues.append({'field': name, 'kind': 'wrong_width', 'components': [], 'observed_width': len(value)})
            values = value
        else:
            values = [value]
        categories = {}
        for index, component in enumerate(values):
            if component is None:
                kind = 'null'
            elif isinstance(component, bool) or not isinstance(component, Real):
                kind = 'non_numeric'
            elif math.isnan(component):
                kind = 'nan'
            elif math.isinf(component):
                kind = 'positive_inf' if component > 0 else 'negative_inf'
            else:
                continue
            categories.setdefault(kind, []).append(index)
        issues.extend({'field': name, 'kind': kind, 'components': indices}
                      for kind, indices in categories.items())
    return issues


def require_finite_record(row: Mapping[str, object]) -> None:
    issues = raw_issues(row)
    if issues:
        labels = ', '.join(f"{x['field']}:{x['kind']}" for x in issues)
        raise ValueError(f'raw quality record is not complete and finite: {labels}')


def diagnostic_reduction(row: Mapping[str, object]) -> tuple[list[dict], list[str]]:
    """Separate raw defects from non-finiteness created by a transform."""
    issues = raw_issues(row)
    structural = {'absent_field', 'null_list', 'malformed_list', 'wrong_width', 'null', 'non_numeric'}
    if any(x['kind'] in structural for x in issues):
        return issues, []
    with np.errstate(invalid='ignore', over='ignore', divide='ignore'):
        reduced = sc.scalarize_record(dict(row))
    bad_raw_fields = {x['field'] for x in issues}
    created = [name for name, value in reduced.items()
               if not np.isfinite(value) and name not in bad_raw_fields]
    return issues, created
