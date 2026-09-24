"""Domain mapping and partial-coverage quality calculations."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np

from .data import MixtureTable, normalised_proportions


def load_mapping(path: Path, expected_domains: Iterable[str]) -> tuple[Dict[str, Optional[str]], Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapping: Dict[str, Optional[str]] = {}
    mapping_type: Dict[str, str] = {}
    for row in rows:
        domain = row["mixture_domain"]
        target = row["quality_domain"].strip()
        kind = row["mapping_type"].strip()
        if domain in mapping or kind not in {"direct", "near_direct", "inferred", "unmapped", "none"}:
            raise ValueError("A16 contains duplicate domains or unknown mapping types")
        if kind in {"unmapped", "none"} and target not in {"", "(none)"}:
            raise ValueError("an unmapped domain cannot have a quality target")
        mapping[domain] = None if target in {"", "(none)"} else target
        mapping_type[domain] = kind
    expected = list(expected_domains)
    if set(mapping) != set(expected):
        raise ValueError("A16 mapping domains do not exactly match mixture table domains")
    return mapping, mapping_type


def mapped_quality(mixture: MixtureTable, mapping: Dict[str, Optional[str]], q_by_domain: Dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    numerator = np.zeros(len(mixture.indices), dtype=float)
    proportions = normalised_proportions(mixture)
    mass = np.zeros(len(mixture.indices), dtype=float)
    for j, domain in enumerate(mixture.domains):
        target = mapping[domain]
        if target is None:
            continue
        if target not in q_by_domain:
            raise ValueError(f"mapped quality domain has no Q score: {target}")
        score = q_by_domain[target]
        if not np.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("domain Q must be finite and in [0,1]")
        mass += proportions[:, j]
        numerator += proportions[:, j] * score
    usable = mass > 0
    values = np.full(len(mixture.indices), np.nan, dtype=float)
    values[usable] = numerator[usable] / mass[usable]
    return mass, values


def mass_weighted_coverage(mixture: MixtureTable, mapping: Dict[str, Optional[str]]) -> float:
    usable = np.asarray([mapping[d] is not None for d in mixture.domains], dtype=bool)
    # Each observed design has unit mass after row renormalisation.
    return float(np.mean(normalised_proportions(mixture)[:, usable].sum(axis=1)))
