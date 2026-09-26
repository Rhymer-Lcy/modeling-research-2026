"""Accepted classic-IF3 consumer boundary for T-010.

The interface is read as immutable producer output.  Its raw-byte SHA-256 is
checked before JSON parsing, then its shared contract and the stricter
baseline-only allocation contract are validated.  In particular, IF3's
``Q = [1, 1]`` validity interval is a no-quality sentinel, never a numerical
quality coordinate.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src import interfaces as ifc
from src.paths import PROBLEM_F_INTERFACES, require
from src.scaling.law import Fit, compute_optimal

ACCEPTED_CLASSIC_IF3_SHA256 = "720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514"
CLASSIC_IF3_FILENAME = "IF3_classic.json"
CLASSIC_FUNCTIONAL_FORM = "E + A*N**-alpha + B*D**-beta"
_REQUIRED_PARAMETERS = ("E", "A", "alpha", "B", "beta")


class ClassicIF3ContractError(ValueError):
    """The loaded IF3 object is not the accepted classic raw-unit law."""


class AcceptedIF3HashMismatch(ClassicIF3ContractError):
    """The local IF3 bytes differ from the accepted producer handoff."""


class BaselineScopeError(ValueError):
    """A caller attempted to leave the receipt-approved Q3 baseline lane."""


class SourceReceiptError(ValueError):
    """The frozen Q3 source receipt cannot support a requested computation."""


@dataclass(frozen=True)
class AcceptedClassicIF3:
    """A hash-validated classic IF3 object and its immutable source payload."""

    law: ifc.IF3ScalingLaw
    payload: Mapping[str, Any]
    path: Path
    sha256: str

    @property
    def params(self) -> Mapping[str, float]:
        """Classic-law parameters in their accepted raw N/D convention."""
        return self.law.params

    @property
    def validity_box(self) -> Mapping[str, tuple[float, float]]:
        """Raw N/D validity box; Q remains the verified no-quality sentinel."""
        return {
            key: (float(values[0]), float(values[1]))
            for key, values in self.law.validity_box.items()
        }


def _build_if3(payload: Mapping[str, Any]) -> ifc.IF3ScalingLaw:
    names = {field.name for field in dataclasses.fields(ifc.IF3ScalingLaw)}
    extra = set(payload) - names
    missing = names - set(payload)
    if extra or missing:
        raise ClassicIF3ContractError(
            "IF3 payload does not match the shared contract; extra="
            + repr(sorted(extra)) + " missing=" + repr(sorted(missing))
        )
    values = dict(payload)
    try:
        values["q_term_provenance"] = ifc.Provenance(**values["q_term_provenance"])
        values["provenance"] = ifc.Provenance(**values["provenance"])
        return ifc.IF3ScalingLaw(**values)
    except (KeyError, TypeError) as exc:
        raise ClassicIF3ContractError("IF3 provenance cannot reconstruct the shared contract") from exc


def _positive_finite(value: object, label: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ClassicIF3ContractError(label + " must be numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise ClassicIF3ContractError(label + " must be finite and strictly positive")
    return numeric


def _validate_classic_contract(law: ifc.IF3ScalingLaw) -> None:
    try:
        law.validate()
    except ifc.InterfaceError as exc:
        raise ClassicIF3ContractError("IF3 failed its shared contract: " + str(exc)) from exc
    if law.functional_form != CLASSIC_FUNCTIONAL_FORM:
        raise ClassicIF3ContractError(
            "IF3 functional form is not the accepted classic N-D law: "
            + repr(law.functional_form)
        )
    if set(law.params) != set(_REQUIRED_PARAMETERS):
        raise ClassicIF3ContractError(
            "classic IF3 parameters must be exactly " + repr(_REQUIRED_PARAMETERS)
        )
    for name in _REQUIRED_PARAMETERS:
        _positive_finite(law.params[name], "IF3 parameter " + name)
    for name in ("N", "D", "Q"):
        values = law.validity_box.get(name)
        if not isinstance(values, (list, tuple)) or len(values) != 2:
            raise ClassicIF3ContractError("IF3 validity box " + name + " must have two endpoints")
        low = _positive_finite(values[0], "IF3 validity-box " + name + " lower endpoint")
        high = _positive_finite(values[1], "IF3 validity-box " + name + " upper endpoint")
        if low > high:
            raise ClassicIF3ContractError("IF3 validity-box " + name + " has reversed endpoints")
    q_box = law.validity_box["Q"]
    if tuple(float(value) for value in q_box) != (1.0, 1.0):
        raise ClassicIF3ContractError(
            "classic IF3 Q validity box must be the [1, 1] no-quality sentinel"
        )


def load_classic_if3(
    path: Path | None = None,
    *,
    expected_sha256: str = ACCEPTED_CLASSIC_IF3_SHA256,
) -> AcceptedClassicIF3:
    """Load the accepted classic IF3 law, refusing altered bytes before parsing."""
    source = require(path or (PROBLEM_F_INTERFACES / CLASSIC_IF3_FILENAME))
    raw = source.read_bytes()
    observed_sha256 = hashlib.sha256(raw).hexdigest()
    if observed_sha256 != expected_sha256:
        raise AcceptedIF3HashMismatch(
            "classic IF3 SHA-256 " + observed_sha256 + " is not the accepted "
            + expected_sha256 + "; install the accepted producer bytes, do not regenerate"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClassicIF3ContractError("accepted classic IF3 bytes are not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ClassicIF3ContractError("classic IF3 payload must be a JSON object")
    law = _build_if3(payload)
    _validate_classic_contract(law)
    return AcceptedClassicIF3(law=law, payload=payload, path=source, sha256=observed_sha256)


def require_baseline_quality(quality: object | None = None) -> None:
    """Allow only the receipt's semantic baseline label, never a numeric Q input."""
    if quality is None or quality == "Q0":
        return
    raise BaselineScopeError(
        "classic IF3 has no quality coordinate; only the semantic baseline Q0 is permitted"
    )


def _positive_raw(value: object, label: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(label + " must be numeric raw units") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise ValueError(label + " must be finite and strictly positive raw units")
    return numeric


def classic_loss(classic: AcceptedClassicIF3, n_parameters: object, d_tokens: object) -> float:
    """Evaluate accepted classic IF3 in raw parameters and raw tokens."""
    n_value = _positive_raw(n_parameters, "N")
    d_value = _positive_raw(d_tokens, "D")
    p = classic.params
    return float(
        p["E"]
        + p["A"] * n_value ** (-p["alpha"])
        + p["B"] * d_value ** (-p["beta"])
    )


def baseline_closed_form(
    classic: AcceptedClassicIF3,
    budget_flops: object,
    kappa: object,
) -> tuple[float, float]:
    """Return the unconstrained pure-``kappa*N*D`` optimum in raw units."""
    budget = _positive_raw(budget_flops, "compute budget")
    kappa_value = _positive_raw(kappa, "kappa")
    p = classic.params
    exponent = 1.0 / (p["alpha"] + p["beta"])
    n_star = (
        (p["alpha"] * p["A"] / (p["beta"] * p["B"]))
        * (budget / kappa_value) ** p["beta"]
    ) ** exponent
    d_star = budget / (kappa_value * n_star)
    return float(n_star), float(d_star)


def pure_nd_oracle(
    classic: AcceptedClassicIF3,
    budget_flops: object,
    kappa: object,
) -> Mapping[str, float]:
    """Independently evaluate the baseline oracle in :mod:`src.scaling.law`."""
    budget = _positive_raw(budget_flops, "compute budget")
    kappa_value = _positive_raw(kappa, "kappa")
    p = classic.params
    raw = (math.log(p["A"]), math.log(p["B"]), math.log(p["E"]), p["alpha"], p["beta"])
    fit = Fit(
        params={key: float(value) for key, value in p.items()},
        objective=0.0,
        n_obs=0,
        n_clusters=0,
        converged=True,
        starts_tried=0,
        starts_converged=0,
        validity_box={key: tuple(value) for key, value in classic.validity_box.items()},
        raw=raw,
    )
    return compute_optimal(fit, budget, kappa_value)


__all__ = [
    "ACCEPTED_CLASSIC_IF3_SHA256",
    "AcceptedClassicIF3",
    "AcceptedIF3HashMismatch",
    "BaselineScopeError",
    "CLASSIC_FUNCTIONAL_FORM",
    "ClassicIF3ContractError",
    "SourceReceiptError",
    "baseline_closed_form",
    "classic_loss",
    "load_classic_if3",
    "pure_nd_oracle",
    "require_baseline_quality",
]
