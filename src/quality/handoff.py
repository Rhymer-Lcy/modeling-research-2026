"""Build IF1 using the unchanged shared schema; never infer missing domain Q."""
from __future__ import annotations

from dataclasses import asdict
import json
import numpy as np

from src.interfaces import IF1DomainQuality, Provenance, SCHEMA_VERSION
from src.paths import PROBLEM_F_INTERFACES
from src.mixture.data import MixtureTable, normalised_proportions
from src.mixture.mapping import mass_weighted_coverage
from . import scalarize as sc
from .pipeline import QUALITY_DOMAINS


def build_if1(estimates: dict, training: MixtureTable, mapping: dict, mapping_type: dict,
              *, provenance: Provenance, processing_notes: dict) -> IF1DomainQuality:
    """Require explicit processing provenance and complete finite estimates.

    No output is written here. A fixture object is not an emitted scientific
    interface. Real callers must finish the specified stability/sensitivity
    checks before invoking the writer.
    """
    domains = estimates['domains']
    if set(domains) != set(QUALITY_DOMAINS):
        raise ValueError('IF1 requires all seven quality domains')
    if set(mapping) != set(training.domains) or set(mapping_type) != set(mapping):
        raise ValueError('IF1 mapping must cover every mixture domain explicitly')
    if not {'q_definition', 'directions', 'normalization', 'missing_signal_policy', 'stability'} <= set(processing_notes):
        raise ValueError('IF1 requires complete processing provenance')
    if set(processing_notes['directions']) != set(sc.INDICATORS):
        raise ValueError('IF1 requires 22 processing directions')
    for domain, entry in domains.items():
        q, interval, n = entry['q'], entry['ci'], entry['n']
        if len(interval) != 2 or not np.isfinite([q, *interval]).all():
            raise ValueError('non-finite or malformed domain uncertainty')
        if not 0 <= interval[0] <= interval[1] <= 1 or not 0 <= q <= 1:
            raise ValueError('domain Q and interval must be in [0,1]')
        if not isinstance(n, (int, np.integer)) or n <= 0:
            raise ValueError('domain sample sizes must be positive integers')
    for domain, target in mapping.items():
        kind = mapping_type[domain]
        if target is not None and target not in domains:
            raise ValueError('mapping has no corresponding quality estimate')
        if kind not in {'direct', 'near_direct', 'inferred', 'unmapped', 'none'}:
            raise ValueError('unknown A16 mapping type')
        if kind in {'unmapped', 'none'} and target is not None:
            raise ValueError('unmapped mapping cannot carry a target')
    p = normalised_proportions(training)
    covered = p[:, [mapping[d] is not None for d in training.domains]].sum(axis=1)
    notes = dict(processing_notes)
    notes['raw_directions'] = dict(sc.DIRECTIONS)
    notes['coverage'] = {'reference': 'mean covered mass across unit-mass A4 training designs',
                         'minimum': float(covered.min()), 'maximum': float(covered.max()),
                         'zero_coverage_designs': int(np.sum(covered == 0)),
                         'warning': 'Q_mapped divides by mapped mass; not whole-corpus quality'}
    notes['uncertainty'] = {k: v for k, v in estimates.items() if k != 'domains'}
    evidence = Provenance(provenance.trust, list(provenance.sources),
                          provenance.notes + '\n' + json.dumps(notes, sort_keys=True, allow_nan=False))
    result = IF1DomainQuality(SCHEMA_VERSION, list(QUALITY_DOMAINS),
                             {d: float(domains[d]['q']) for d in QUALITY_DOMAINS},
                             {d: list(map(float, domains[d]['ci'])) for d in QUALITY_DOMAINS},
                             {d: int(domains[d]['n']) for d in QUALITY_DOMAINS},
                             dict(mapping), dict(mapping_type), mass_weighted_coverage(training, mapping),
                             dict(processing_notes['directions']), evidence)
    result.validate()
    return result


def encode_if1(interface: IF1DomainQuality) -> bytes:
    interface.validate()
    return (json.dumps(asdict(interface), sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def write_if1(interface: IF1DomainQuality):
    """Only the canonical local interface location is writable by this API."""
    payload = encode_if1(interface)
    out = PROBLEM_F_INTERFACES / 'q1-if1-domain-quality.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    return out
