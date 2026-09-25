"""Unit conventions for external scaling-law interfaces (gate G2-U).

The externally consumed IF3 convention is fixed: N is a raw parameter count
and D is a raw token count. An internal fit may use scaled coordinates for
numerical conditioning. This module owns the conversion between the two, so
that parameters, validity boxes and predictions are always transformed
together. Converting one of them without the others is precisely the failure
the gate exists to catch, and it cannot be seen in the parameters alone: a
consistent rescaling of N and D is absorbed into A and B, so both parameter
sets look equally plausible. Only a prediction at a fixed physical point can
tell them apart.

For internal coordinates N_int = N_raw / s_N and D_int = D_raw / s_D, the law

    L = E + A_raw N_raw^(-alpha) + B_raw D_raw^(-beta)

is reproduced exactly by

    L = E + A_int N_int^(-alpha) + B_int D_int^(-beta)

with

    A_int = A_raw * s_N^(-alpha)        A_raw = A_int * s_N^(alpha)
    B_int = B_raw * s_D^(-beta)         B_raw = B_int * s_D^(beta)

Q is dimensionless, so the quality-aware candidate
L = E + A N^(-alpha) + B (Q^gamma D)^(-beta) transforms B exactly as above and
leaves gamma unchanged. E, alpha and beta never change.

The scale factors are not assumed. They are read off the organizer's column
names, which state the stored unit; an unknown column raises rather than
guessing a factor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence

import numpy as np

#: Stored unit of each organizer column, from the suffix the column name carries.
#: "_B" means billions. Anything not listed is refused.
_COLUMN_SCALE = {
    "N_params_B": 1.0e9,
    "D_tokens_B": 1.0e9,
}

#: Relative tolerance for raw/internal prediction equality.
#:
#: Justification. Machine epsilon for float64 is 2.22e-16. A converted
#: prediction passes through a handful of correctly-rounded operations (one
#: power and one product to convert A or B, one product to rescale N or D, one
#: power and one product per term, and a sum of three positive terms, which
#: cannot cancel). The only amplification is the power applied to a rescaled
#: coordinate, whose representation error is multiplied by the exponent, and
#: every fitted exponent is bounded by 3 (alpha, beta) or by gamma * beta. A
#: conservative bound is therefore a few tens of epsilon, of order 1e-14. The
#: tolerance below leaves two orders of magnitude of margin over that bound and
#: is still six orders below the 1e-6 relative resolution at which any tracked
#: table reports a loss, so it cannot hide a real unit error: a missing factor
#: of s^alpha changes a term by a factor of order 1e3.
INVARIANCE_RTOL = 1.0e-12

_PARAMS_CLASSIC = ("E", "A", "alpha", "B", "beta")
_PARAMS_QUALITY = _PARAMS_CLASSIC + ("gamma",)


class UnitError(ValueError):
    """Raised when a unit convention is unknown, invalid or inconsistent."""


def column_scale(column: str) -> float:
    """Return the factor that turns a stored column value into a raw count."""
    if column not in _COLUMN_SCALE:
        raise UnitError(
            "no declared unit for column " + repr(column)
            + "; add it to the declared table rather than assuming a factor"
        )
    return _COLUMN_SCALE[column]


@dataclass(frozen=True)
class UnitConvention:
    """How internal coordinates relate to raw counts: raw = internal * s."""

    name: str
    s_n: float
    s_d: float

    def __post_init__(self) -> None:
        for label, value in (("s_n", self.s_n), ("s_d", self.s_d)):
            if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
                raise UnitError(label + " must be a positive finite scale factor")


#: The external IF3 convention.
RAW = UnitConvention("raw parameter count / raw token count", 1.0, 1.0)


def convention_for_columns(n_column: str, d_column: str) -> UnitConvention:
    """The internal convention implied by fitting directly on these columns."""
    return UnitConvention(
        "internal: " + n_column + " / " + d_column,
        column_scale(n_column),
        column_scale(d_column),
    )


def _param_names(params: Mapping[str, float]) -> Sequence[str]:
    keys = set(params)
    if keys == set(_PARAMS_CLASSIC):
        return _PARAMS_CLASSIC
    if keys == set(_PARAMS_QUALITY):
        return _PARAMS_QUALITY
    raise UnitError("unexpected parameter set " + repr(sorted(keys)))


def params_to_raw(params: Mapping[str, float], conv: UnitConvention) -> Dict[str, float]:
    """Internal-coordinate parameters -> raw-count parameters."""
    names = _param_names(params)
    out = {k: float(params[k]) for k in names}
    out["A"] = float(params["A"]) * conv.s_n ** float(params["alpha"])
    out["B"] = float(params["B"]) * conv.s_d ** float(params["beta"])
    return out


def params_to_internal(params: Mapping[str, float], conv: UnitConvention) -> Dict[str, float]:
    """Raw-count parameters -> internal-coordinate parameters."""
    names = _param_names(params)
    out = {k: float(params[k]) for k in names}
    out["A"] = float(params["A"]) * conv.s_n ** (-float(params["alpha"]))
    out["B"] = float(params["B"]) * conv.s_d ** (-float(params["beta"]))
    return out


def _scaled_box(box: Mapping[str, Sequence[float]], fn, fd) -> Dict[str, list]:
    missing = {"N", "D"} - set(box)
    if missing:
        raise UnitError("validity box is missing " + repr(sorted(missing)))
    out: Dict[str, list] = {}
    for key, value in box.items():
        lo, hi = float(value[0]), float(value[1])
        if key == "N":
            out[key] = [fn(lo), fn(hi)]
        elif key == "D":
            out[key] = [fd(lo), fd(hi)]
        else:
            # Q and any other dimensionless axis are unit-free.
            out[key] = [lo, hi]
    return out


def box_to_raw(box: Mapping[str, Sequence[float]], conv: UnitConvention) -> Dict[str, list]:
    return _scaled_box(box, lambda x: x * conv.s_n, lambda x: x * conv.s_d)


def box_to_internal(box: Mapping[str, Sequence[float]], conv: UnitConvention) -> Dict[str, list]:
    return _scaled_box(box, lambda x: x / conv.s_n, lambda x: x / conv.s_d)


def predict_natural(params: Mapping[str, float], n, d, q: Optional[object] = None) -> np.ndarray:
    """L(N, D[, Q]) from natural (not log) parameters, in the parameters' units.

    With a quality exponent present, Q is required; without one, Q must be
    omitted. Mixing the two would silently evaluate a different law.
    """
    names = _param_names(params)
    n = np.asarray(n, dtype=float)
    d = np.asarray(d, dtype=float)
    if np.any(n <= 0) or np.any(d <= 0):
        raise UnitError("N and D must be strictly positive")
    data_scale = d
    if names is _PARAMS_QUALITY:
        if q is None:
            raise UnitError("a quality-aware parameter set needs Q")
        q = np.asarray(q, dtype=float)
        if np.any(q <= 0):
            raise UnitError("Q must be strictly positive")
        data_scale = np.power(q, float(params["gamma"])) * d
    elif q is not None:
        raise UnitError("a classic parameter set takes no Q")
    return (float(params["E"])
            + float(params["A"]) * np.power(n, -float(params["alpha"]))
            + float(params["B"]) * np.power(data_scale, -float(params["beta"])))


def box_corners(box: Mapping[str, Sequence[float]]) -> Dict[str, np.ndarray]:
    """Every corner of the N x D (x Q) box, as parallel coordinate arrays."""
    axes = [k for k in ("N", "D", "Q") if k in box]
    grids = np.meshgrid(*[np.asarray(box[k], dtype=float) for k in axes], indexing="ij")
    return {k: g.ravel() for k, g in zip(axes, grids)}


def interior_points(box: Mapping[str, Sequence[float]], per_axis: int = 4) -> Dict[str, np.ndarray]:
    """Deterministic interior points: geometric for N and D, linear for Q."""
    if per_axis < 1:
        raise UnitError("per_axis must be positive")
    fractions = (np.arange(per_axis) + 1.0) / (per_axis + 1.0)
    out = {}
    for key in ("N", "D", "Q"):
        if key not in box:
            continue
        lo, hi = float(box[key][0]), float(box[key][1])
        if key in ("N", "D"):
            out[key] = np.exp(np.log(lo) + fractions * (np.log(hi) - np.log(lo)))
        else:
            out[key] = lo + fractions * (hi - lo)
    grids = np.meshgrid(*[out[k] for k in out], indexing="ij")
    return {k: g.ravel() for k, g in zip(out, grids)}


def invariance_check(params_internal: Mapping[str, float], conv: UnitConvention,
                     points_internal: Mapping[str, np.ndarray]) -> Dict[str, float]:
    """Predict the same physical points in both conventions and compare.

    ``points_internal`` holds N and D in internal units (and Q when the law has
    one). The raw-side prediction uses parameters converted by
    :func:`params_to_raw` and coordinates converted by the same factors.
    """
    params_raw = params_to_raw(params_internal, conv)
    n_int = np.asarray(points_internal["N"], dtype=float)
    d_int = np.asarray(points_internal["D"], dtype=float)
    q = points_internal.get("Q")
    pred_int = predict_natural(params_internal, n_int, d_int, q)
    pred_raw = predict_natural(params_raw, n_int * conv.s_n, d_int * conv.s_d, q)
    rel = np.abs(pred_raw - pred_int) / np.abs(pred_int)
    return {
        "points": int(rel.size),
        "max_rel_error": float(np.max(rel)),
        "pass": bool(rel.size > 0 and np.max(rel) <= INVARIANCE_RTOL),
    }


def round_trip_error(params: Mapping[str, float], box: Mapping[str, Sequence[float]],
                     conv: UnitConvention) -> Dict[str, float]:
    """Internal -> raw -> internal, for both parameters and validity box."""
    back = params_to_internal(params_to_raw(params, conv), conv)
    p_err = max(abs(back[k] - float(params[k])) / abs(float(params[k])) for k in back)
    box_back = box_to_internal(box_to_raw(box, conv), conv)
    b_err = max(abs(box_back[k][i] - float(box[k][i])) / abs(float(box[k][i]))
                for k in box_back for i in (0, 1))
    return {"param_max_rel_error": float(p_err), "box_max_rel_error": float(b_err),
            "pass": bool(p_err <= INVARIANCE_RTOL and b_err <= INVARIANCE_RTOL)}


__all__ = [
    "INVARIANCE_RTOL",
    "RAW",
    "UnitConvention",
    "UnitError",
    "box_corners",
    "box_to_internal",
    "box_to_raw",
    "column_scale",
    "convention_for_columns",
    "interior_points",
    "invariance_check",
    "params_to_internal",
    "params_to_raw",
    "predict_natural",
    "round_trip_error",
]
