"""IF2 construction without changing the shared interface schema."""
from __future__ import annotations

from dataclasses import asdict
import json
import numpy as np

from src.interfaces import IF2MixtureResponse, Provenance, SCHEMA_VERSION
from src.paths import PROBLEM_F_INTERFACES
from .validation import FrozenResponse, VALIDATION_ROLES


_SCOPE_LIMITATIONS = {
    'absolute_use_outside_1M': 'PROHIBITED',
    'scale_invariance_supported': False,
    'A8_A9_absolute_transfer_certified': False,
    'A10_A11_out_of_design_shape_certified': False,
    'fitted_10B_70B_extrapolation': 'NOT RELEASED',
}


def _require_scope_release(frozen: FrozenResponse, scope_release: dict) -> None:
    """Reject an IF2 export unless its narrow release receipt is complete."""
    if not isinstance(scope_release, dict):
        raise ValueError('IF2 requires an explicit 1M scope-release receipt')
    required = {
        'scope_release_pass': True,
        'fit_scale': '1M',
        'fit_sources': ['A4', 'A5'],
        'release_validation_partition': 'A6_A7',
        'release_validation_role': VALIDATION_ROLES['A6_A7'],
        'frozen_model_sha256': frozen.model_sha256,
        'broad_transfer_pass': False,
        'a8_a9_absolute_transfer_pass': False,
        'a10_a11_out_of_design_shape_pass': False,
    }
    for key, expected in required.items():
        if scope_release.get(key) != expected:
            raise ValueError('IF2 scope-release receipt is incomplete or inconsistent: ' + key)
    if scope_release.get('limitations') != _SCOPE_LIMITATIONS:
        raise ValueError('IF2 scope-release receipt omits required non-certification limits')


def build_if2(frozen: FrozenResponse, validation: dict, estimated_references: dict, *,
              renormalisation: str, provenance: Provenance, scope_release: dict) -> IF2MixtureResponse:
    frozen.check_unchanged()
    _require_scope_release(frozen, scope_release)
    if len(frozen.domains) != 17 or len(frozen.targets) != 13:
        raise ValueError('IF2 requires 17 mixture domains and 13 loss targets')
    for partition, role in VALIDATION_ROLES.items():
        report = validation.get(partition, {})
        if report.get('role') != role or report.get('model_sha256') != frozen.model_sha256:
            raise ValueError('all required validations must refer to the same frozen training model')
        if report.get('n', 0) <= 0 or set(report.get('absolute', {}).get('per_target', {})) != set(frozen.targets):
            raise ValueError('validation report lacks target-level results')
    if set(estimated_references) != {'A13', 'A15'}:
        raise ValueError('both estimated-reference comparisons must be explicit')
    for source, report in estimated_references.items():
        if report.get('source') != source or report.get('role') != 'estimated_reference_NOT_validation' or report.get('fit_use') is not False:
            raise ValueError('estimated reference was mislabelled or used for fitting')
        if set(report.get('comparison', {}).get('per_target', {})) != set(frozen.targets):
            raise ValueError('estimated reference lacks target-level comparisons')
    if not renormalisation:
        raise ValueError('renormalisation must be explicit')
    coefficients = {}
    for fit in frozen.fits:
        coefficients[fit.target] = {'__intercept__': fit.intercept, **fit.coefficients,
                                    **{'interaction:' + name: value for name, value in fit.interactions.items()}}
        if not np.isfinite(list(coefficients[fit.target].values())).all():
            raise ValueError('non-finite response coefficient')
    target_domains = {name.removeprefix('metric/the_pile_').removesuffix('_val_loss') for name in frozen.targets}
    notes = dict(validation)
    notes['scope_release'] = scope_release
    notes['estimated_reference_NOT_validation'] = estimated_references
    notes['fit'] = {'kind': frozen.kind, 'selection': frozen.cv,
                    'training_sha256': frozen.training_sha256, 'model_sha256': frozen.model_sha256,
                    'sources': ['A4', 'A5'],
                    'coefficient_encoding': 'intercept under __intercept__; contrast terms by domain; pairwise terms under interaction:left*right',
                    'interpretation': 'replace reference-domain mass; nonlinear substitution effects depend on the starting mixture'}
    result = IF2MixtureResponse(SCHEMA_VERSION, list(frozen.domains), list(frozen.targets),
                               frozen.reference, 'exact zeros are valid boundary proportions; no pseudocount',
                               renormalisation, coefficients, '1M', notes,
                               [d for d in frozen.domains if d not in target_domains], provenance)
    result.validate()
    json.dumps(asdict(result), allow_nan=False)
    return result


def encode_if2(interface: IF2MixtureResponse) -> bytes:
    interface.validate()
    return (json.dumps(asdict(interface), sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def write_if2(interface: IF2MixtureResponse):
    payload = encode_if2(interface)
    out = PROBLEM_F_INTERFACES / 'q1-if2-mixture-response.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    return out
