"""Model-conditional allocation robustness from the published Q2 LOO vectors.

Each published leave-one-trajectory-out vector is bound to the accepted IF3
validity box as a :class:`SensitivityClassicLaw`: a separately labelled,
in-memory parameter representation that carries no IF3 path, bytes or hash and
reports ``is_accepted_if3 = False``.  The byte-locked accepted IF3 object is
never copied or relabelled, so no modified fit can be mistaken for it.

Two references are provided.  The nominal accepted IF3 at full precision is the
canonical point estimate.  The published full fit, printed at the same six
significant digits as the LOO vectors, is the like-for-like reference: a LOO
vector that equals it at published precision is indistinguishable from the
nominal fit at the resolution of the released evidence.

Rounding materiality is assessed with the 32 corners of each vector's
half-unit rounding box.  Over boxes this small the allocation outputs are
effectively linear in the parameters, so the corners bound them to first order.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .loo import (
    PARAMETERS,
    PUBLISHED_FORMAT,
    LOORobustnessError,
    LOORobustnessEvidence,
    PublishedParameterVector,
    load_loo_robustness,
)

ROLE_NOMINAL = "nominal_accepted_if3"
ROLE_PUBLISHED_NOMINAL = "published_full_fit_reference"
ROLE_LOO = "loo_alternative_fit"


@dataclass(frozen=True)
class SensitivityClassicLaw:
    """A labelled classic-law parameter set for sensitivity only, never the accepted IF3."""

    label: str
    params: Mapping[str, float]
    validity_box: Mapping[str, tuple[float, float]]
    parameter_source: str
    precision: str
    is_accepted_if3: bool = False


@dataclass(frozen=True)
class LOOSensitivityModel:
    """One nominal, published-reference or leave-one-trajectory-out model."""

    label: str
    role: str
    dropped_trajectory_billions: str | None
    law: Any
    published_vector: PublishedParameterVector | None


def _sensitivity_law(classic: Any, vector: PublishedParameterVector, source: str) -> SensitivityClassicLaw:
    if tuple(vector.parameters) != PARAMETERS:
        raise LOORobustnessError("sensitivity parameters must be the complete ordered classic set")
    return SensitivityClassicLaw(
        label=vector.label,
        params={name: float(vector.parameters[name]) for name in PARAMETERS},
        validity_box=dict(classic.validity_box),
        parameter_source=source,
        precision="published to six significant digits (" + PUBLISHED_FORMAT + ")",
    )


def require_published_full_fit_matches(classic: Any, evidence: LOORobustnessEvidence) -> None:
    """Require the published full fit to be the accepted IF3 printed at six digits."""
    for name in PARAMETERS:
        printed = format(float(classic.params[name]), PUBLISHED_FORMAT)
        if printed != evidence.published_full_fit.published_strings[name]:
            raise LOORobustnessError(
                "published full fit " + name + " is not the accepted IF3 value at published precision"
            )


def build_loo_sensitivity_models(classic: Any, evidence: LOORobustnessEvidence) -> tuple[LOOSensitivityModel, ...]:
    """Return nominal, published full-fit reference and all eight LOO models, in order."""
    require_published_full_fit_matches(classic, evidence)
    models = [
        LOOSensitivityModel("nominal_accepted_if3", ROLE_NOMINAL, None, classic, None),
        LOOSensitivityModel(
            "published_full_fit", ROLE_PUBLISHED_NOMINAL, None,
            _sensitivity_law(classic, evidence.published_full_fit, "published Q2 full fit"),
            evidence.published_full_fit,
        ),
    ]
    for vector in evidence.vectors:
        models.append(LOOSensitivityModel(
            "loo_drop_" + vector.label + "B", ROLE_LOO, vector.label,
            _sensitivity_law(classic, vector, "published Q2 leave-one-trajectory-out fit"),
            vector,
        ))
    return tuple(models)


def load_loo_sensitivity_models(classic: Any, path: Path | None = None) -> tuple[LOOSensitivityModel, ...]:
    """Load the authorized LOO evidence and return every sensitivity model."""
    return build_loo_sensitivity_models(classic, load_loo_robustness(path))


def rounding_corner_laws(classic: Any, vector: PublishedParameterVector) -> tuple[SensitivityClassicLaw, ...]:
    """Return the 32 corners of a published vector's half-unit rounding box."""
    half = vector.half_units()
    corners: list[SensitivityClassicLaw] = []
    for signs in itertools.product((-1.0, 1.0), repeat=len(PARAMETERS)):
        params = {
            name: vector.parameters[name] + sign * half[name]
            for name, sign in zip(PARAMETERS, signs, strict=True)
        }
        corners.append(SensitivityClassicLaw(
            label=vector.label + "_rounding_corner",
            params=params,
            validity_box=dict(classic.validity_box),
            parameter_source="half-unit rounding corner of a published Q2 vector",
            precision="rounding-envelope probe only",
        ))
    return tuple(corners)


__all__ = [
    "LOOSensitivityModel",
    "ROLE_LOO",
    "ROLE_NOMINAL",
    "ROLE_PUBLISHED_NOMINAL",
    "SensitivityClassicLaw",
    "build_loo_sensitivity_models",
    "load_loo_sensitivity_models",
    "require_published_full_fit_matches",
    "rounding_corner_laws",
]
