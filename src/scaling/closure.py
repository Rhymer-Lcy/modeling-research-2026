"""Consumer-side helpers for the T-008 final closure.

T-008 consumes the accepted T-007 interfaces; it never regenerates them. Each
helper here exists to make one misuse impossible rather than merely unlikely:

* an interface object whose bytes differ from the accepted review record is
  refused, with the expected hash read from the tracked accepted summary
  table rather than typed into this file;
* IF2 is evaluated only at its released 1M scale;
* the composition diagnostic reads only the fitting partition, so no held-out
  partition can influence anything computed here;
* mapped-mass quality is undefined, never imputed, where a design has no
  mapped mass;
* a quality value on one axis cannot be fed to a law calibrated on another
  axis unless a first-party mapping between the two has been declared.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize

from src import interfaces as ifc
from src.paths import ATT_A, PROBLEM_F_INTERFACES, TABLES, require
from src.scaling.law import HUBER_DELTA, _huber
from src.scaling.quality import GAMMA_BOUNDS, _log_predict_q

# ---------------------------------------------------------------------------
# Accepted-interface receipt
# ---------------------------------------------------------------------------

#: Tracked accepted summary table that records each interface's hash.
ACCEPTED_SUMMARY = {
    "IF1": "q1-if1-summary.md",
    "IF2": "q1-if2-summary.md",
}

#: Canonical local interface file names, as the producer writes them.
INTERFACE_FILE = {
    "IF1": "q1-if1-domain-quality.json",
    "IF2": "q1-if2-mixture-response.json",
}

_CLASSES = {"IF1": ifc.IF1DomainQuality, "IF2": ifc.IF2MixtureResponse}


class AcceptedInterfaceError(ValueError):
    """The local interface object is not the accepted one, or fails its contract."""


class ScopeViolation(ValueError):
    """An interface was asked to answer outside its released scope."""


class UnsupportedScaleMapping(ValueError):
    """A quality value was offered to a law calibrated on a different axis."""


def accepted_sha256(kind: str) -> str:
    """Read the accepted object's SHA-256 from its tracked summary table.

    The summary is the accepted review record, so this binds the check to the
    reviewed artifact. Exactly one hash row is required.
    """
    path = require(TABLES / ACCEPTED_SUMMARY[kind])
    rows = re.findall(r"^\|\s*sha256\s*\|\s*([0-9a-f]{64})\s*\|\s*$",
                      path.read_text(encoding="utf-8"), flags=re.M)
    if len(rows) != 1:
        raise AcceptedInterfaceError(
            ACCEPTED_SUMMARY[kind] + " must record exactly one sha256 row; found " + str(len(rows)))
    return rows[0]


def build_interface(kind: str, payload: Mapping):
    """Construct the contract dataclass from a parsed payload, refusing extras."""
    cls = _CLASSES[kind]
    names = [f.name for f in dataclasses.fields(cls)]
    extra = set(payload) - set(names)
    missing = set(names) - set(payload)
    if extra or missing:
        raise AcceptedInterfaceError(
            kind + " payload does not match the contract; extra=" + repr(sorted(extra))
            + " missing=" + repr(sorted(missing)))
    kwargs = {}
    for name in names:
        value = payload[name]
        if name == "provenance":
            value = ifc.Provenance(**value)
        kwargs[name] = value
    return cls(**kwargs)


def check_if2_scope(payload: Mapping) -> Dict[str, object]:
    """Require the 1M-only scope receipt and every retained failure state.

    Returns the receipt. Any weakening - a different fit scale, a lifted
    prohibition, a certified transfer - raises.
    """
    if payload.get("fit_scale") != "1M":
        raise ScopeViolation("IF2 fit_scale must be '1M'; got " + repr(payload.get("fit_scale")))
    validation = payload.get("validation", {})
    receipt = validation.get("scope_release")
    if not isinstance(receipt, dict):
        raise ScopeViolation("IF2 carries no scope_release receipt")
    limits = receipt.get("limitations", {})
    required = {
        ("scope_release_pass",): True,
        ("fit_scale",): "1M",
        ("broad_transfer_pass",): False,
        ("a8_a9_absolute_transfer_pass",): False,
        ("a10_a11_out_of_design_shape_pass",): False,
    }
    for (key,), want in required.items():
        if receipt.get(key) != want:
            raise ScopeViolation("IF2 scope receipt " + key + " must be " + repr(want)
                                 + "; got " + repr(receipt.get(key)))
    required_limits = {
        "absolute_use_outside_1M": "PROHIBITED",
        "scale_invariance_supported": False,
        "A8_A9_absolute_transfer_certified": False,
        "A10_A11_out_of_design_shape_certified": False,
        "fitted_10B_70B_extrapolation": "NOT RELEASED",
    }
    for key, want in required_limits.items():
        if limits.get(key) != want:
            raise ScopeViolation("IF2 limitation " + key + " must be " + repr(want)
                                 + "; got " + repr(limits.get(key)))
    acceptance = validation.get("acceptance", {})
    if acceptance.get("release_pass") is not False:
        raise ScopeViolation("IF2 broad release_pass must remain false")
    return dict(receipt)


def load_accepted(kind: str):
    """Load, hash-check and validate an accepted interface. Returns (obj, payload, sha)."""
    if kind not in _CLASSES:
        raise KeyError(kind)
    path = require(PROBLEM_F_INTERFACES / INTERFACE_FILE[kind])
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    expected = accepted_sha256(kind)
    if sha != expected:
        raise AcceptedInterfaceError(
            kind + " object hash " + sha + " is not the accepted " + expected
            + "; install the producer's handoff bytes, do not regenerate")
    payload = json.loads(raw.decode("utf-8"))
    obj = build_interface(kind, payload)
    obj.validate()
    if kind == "IF2":
        check_if2_scope(payload)
    return obj, payload, sha


# ---------------------------------------------------------------------------
# IF2 evaluation, only at its released scale
# ---------------------------------------------------------------------------

def require_if2_scale(scale: str) -> None:
    if scale != "1M":
        raise ScopeViolation(
            "IF2 is released for absolute use at 1M only; a request at " + repr(scale)
            + " is prohibited (A8/A9 and A10/A11 transfer both failed)")


def if2_predict(payload: Mapping, proportions: np.ndarray, domains: Sequence[str],
                *, scale: str) -> Tuple[List[str], np.ndarray]:
    """Evaluate the frozen IF2 surface at normalised compositions.

    Uses the producer's encoding exactly: an uncentred intercept, dropped-
    reference contrast terms on the proportions, and all pairwise products
    including the reference. Returns (target names, predictions[n, targets]).
    """
    require_if2_scale(scale)
    domains = list(domains)
    if sorted(domains) != sorted(payload["mixture_domains"]):
        raise ScopeViolation("composition domains differ from the IF2 mixture domains")
    p = np.asarray(proportions, dtype=float)
    if p.ndim != 2 or p.shape[1] != len(domains):
        raise ValueError("proportions must be [designs, domains]")
    if np.any(p < 0) or np.max(np.abs(p.sum(axis=1) - 1.0)) > 1e-9:
        raise ValueError("proportions must be non-negative unit-mass rows")
    col = {d: i for i, d in enumerate(domains)}
    reference = payload["contrast_basis"]
    targets = list(payload["coefficients"])
    out = np.empty((p.shape[0], len(targets)))
    for t, target in enumerate(targets):
        coef = payload["coefficients"][target]
        pred = np.full(p.shape[0], float(coef["__intercept__"]))
        for key, value in coef.items():
            if key == "__intercept__":
                continue
            if key.startswith("interaction:"):
                left, right = key[len("interaction:"):].split("*")
                pred += float(value) * p[:, col[left]] * p[:, col[right]]
            else:
                if key == reference:
                    raise AcceptedInterfaceError("reference domain carries a main-effect coefficient")
                pred += float(value) * p[:, col[key]]
        out[:, t] = pred
    return targets, out


# ---------------------------------------------------------------------------
# Fitting partition only
# ---------------------------------------------------------------------------

#: The only partition the composition diagnostic may read. A4/A5 is IF2's
#: fitting and selection source; A6-A11 are its validation partitions and
#: A12-A15 are estimated references. None of those may enter anything here.
FITTING_PARTITIONS = ("A4",)


def load_fitting_mixture(name: str, row_sum_tolerance: float):
    if name not in FITTING_PARTITIONS:
        raise ScopeViolation(
            "partition " + repr(name) + " is not a fitting partition; held-out and "
            "reference partitions may not enter the T-008 composition diagnostic")
    from src.mixture.data import MIXTURE_FILES, load_mixture
    return load_mixture(ATT_A / "regmix_tables" / MIXTURE_FILES[name], name + " mixture",
                        row_sum_tolerance=row_sum_tolerance)


# ---------------------------------------------------------------------------
# Mapped-mass quality Q(p)
# ---------------------------------------------------------------------------

def mapped_quality(proportions: np.ndarray, domains: Sequence[str],
                   if1) -> Tuple[np.ndarray, np.ndarray]:
    """Mapped mass m(p) and mapped-mass conditional quality Q(p).

    Q(p) = sum over mapped domains of p_d * Q_d, divided by m(p). Where m(p) is
    zero, Q(p) is undefined and returned as NaN: no corpus-wide or imputed
    quality is ever substituted, and unmapped domains carry no quality at all.
    """
    p = np.asarray(proportions, dtype=float)
    q_col = np.zeros(len(domains))
    mapped = np.zeros(len(domains), dtype=bool)
    for i, d in enumerate(domains):
        target = if1.mixture_to_quality.get(d)
        if target:
            if target not in if1.q_by_domain:
                raise AcceptedInterfaceError("mapping points at a domain without a quality value")
            q_col[i] = float(if1.q_by_domain[target])
            mapped[i] = True
    mass = p[:, mapped].sum(axis=1)
    weighted = p[:, mapped] @ q_col[mapped]
    q = np.full(p.shape[0], np.nan)
    positive = mass > 0
    q[positive] = weighted[positive] / mass[positive]
    return mass, q


# ---------------------------------------------------------------------------
# Quality-axis binding
# ---------------------------------------------------------------------------

#: The two quality axes that exist in this project, as they are defined.
QUALITY_AXES = {
    "IF1_Q": ("relative midrank score against the pooled A1 reference; the pooled "
              "reference sits at 0.5 by construction; derived from observed "
              "A-attachment quality signals"),
    "B7_Q_score": ("design variable of an organizer-labelled semi-synthetic N-D-Q "
                   "table; values 0.1-1.0; no construction, anchor or direction is "
                   "defined in the organizer material"),
}

#: First-party mappings between different axes. Empty: none has been
#: established. Adding one requires first-party evidence, not convenience.
DECLARED_MAPPINGS: Dict[Tuple[str, str], str] = {}


def bind_quality_axis(law_axis: str, input_axis: str) -> str:
    """Permit feeding ``input_axis`` values to a law calibrated on ``law_axis``."""
    for axis in (law_axis, input_axis):
        if axis not in QUALITY_AXES:
            raise UnsupportedScaleMapping("unknown quality axis " + repr(axis))
    if law_axis == input_axis:
        return "identity"
    key = (law_axis, input_axis)
    if key in DECLARED_MAPPINGS:
        return DECLARED_MAPPINGS[key]
    raise UnsupportedScaleMapping(
        "no first-party mapping from " + input_axis + " to " + law_axis
        + "; a monotone relation, a similar range or a convenient normalisation "
        "does not establish scale equivalence")


# ---------------------------------------------------------------------------
# Quality-table diagnostics
# ---------------------------------------------------------------------------

def q_direction(frame) -> Dict[str, float]:
    """Sign of d logL / d logQ in EVERY (N, D) cell of a quality table."""
    slopes = []
    for _key, sub in frame.groupby(["N_params_B", "D_tokens_B"]):
        if len(sub) < 3:
            continue
        qv = sub["Q_score"].to_numpy(float)
        lv = sub["val_loss"].to_numpy(float)
        slopes.append(float(np.polyfit(np.log(qv), np.log(lv), 1)[0]))
    slopes = np.asarray(slopes)
    if slopes.size == 0:
        raise ValueError("no (N, D) cell has three or more Q levels")
    return {
        "cells": int(slopes.size),
        "negative": int((slopes < 0).sum()),
        "positive": int((slopes > 0).sum()),
        "median": float(np.median(slopes)),
        "min": float(slopes.min()),
        "max": float(slopes.max()),
    }


def quality_objective(theta: Sequence[float], n, d, q, loss) -> float:
    return _huber(_log_predict_q(np.asarray(theta, float), np.log(n), np.log(d),
                                 np.log(q)) - np.log(loss), HUBER_DELTA)


_BOUNDS = [(-20.0, 40.0), (-20.0, 40.0), (-10.0, 3.0), (1e-3, 3.0), (1e-3, 3.0), GAMMA_BOUNDS]


def profile_gamma(n, d, q, loss, anchor: Sequence[float],
                  gammas: Iterable[float]) -> List[Dict[str, float]]:
    """Profile the objective in gamma, re-optimising the other five parameters.

    Starts from the full-fit anchor and from two perturbations of it, and keeps
    the best, so a single start cannot mistake a local basin for the profile.
    """
    n, d, q, loss = (np.asarray(v, float) for v in (n, d, q, loss))
    anchor = np.asarray(anchor, float)
    free = [0, 1, 2, 3, 4]
    step = np.array([0.3, 0.3, 0.05, 0.02, 0.02])
    rows = []
    for g in gammas:
        g = float(g)
        if not (GAMMA_BOUNDS[0] <= g <= GAMMA_BOUNDS[1]):
            continue

        def obj(x, g=g):
            theta = np.empty(6)
            theta[free] = x
            theta[5] = g
            return quality_objective(theta, n, d, q, loss)

        best = None
        for start in (anchor[free], anchor[free] + step, anchor[free] - step):
            res = minimize(obj, np.clip(start, [b[0] for b in _BOUNDS[:5]], [b[1] for b in _BOUNDS[:5]]),
                           method="L-BFGS-B", bounds=_BOUNDS[:5],
                           options={"maxiter": 20000, "ftol": 1e-15, "gtol": 1e-12})
            if best is None or res.fun < best.fun:
                best = res
        rows.append({"gamma": g, "objective": float(best.fun), "beta": float(best.x[4]),
                     "gamma_times_beta": g * float(best.x[4])})
    return rows


def ols_r2(y: np.ndarray, columns: Sequence[np.ndarray]) -> Tuple[float, np.ndarray]:
    """R^2 and coefficients of an intercept-plus-columns least-squares fit."""
    y = np.asarray(y, float)
    x = np.column_stack([np.ones_like(y)] + [np.asarray(c, float) for c in columns])
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ coef
    tss = float(np.sum((y - y.mean()) ** 2))
    return (1.0 - float(np.sum(resid ** 2)) / tss if tss > 0 else float("nan")), coef


__all__ = [
    "ACCEPTED_SUMMARY",
    "AcceptedInterfaceError",
    "DECLARED_MAPPINGS",
    "FITTING_PARTITIONS",
    "INTERFACE_FILE",
    "QUALITY_AXES",
    "ScopeViolation",
    "UnsupportedScaleMapping",
    "accepted_sha256",
    "bind_quality_axis",
    "build_interface",
    "check_if2_scope",
    "if2_predict",
    "load_accepted",
    "load_fitting_mixture",
    "mapped_quality",
    "ols_r2",
    "profile_gamma",
    "q_direction",
    "quality_objective",
    "require_if2_scale",
]
