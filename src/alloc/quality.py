"""Raw quality-cost family comparison over the source-supported Q domain.

Three questions are kept apart:

A. comparing the raw organizer functions g(Q) needs no numeric Q0 and is done here;
B. evaluating D [g(Q) - g(Q0)]_+ needs an established numeric Q0 and stays
   BLOCKED_UNTIL_Q0_DECLARED;
C. optimizing a nontrivial Q needs an accepted quality-benefit model, which the
   classic IF3 law does not contain.

Crossings are located with analytic support rather than a grid.  For a pair
(i, j) let ``phi = ln g_i - ln g_j`` on (0, 1] (every family is positive there):

- exponential vs power: ``phi'' = lambda_p / Q^2 > 0``, strictly convex, with
  its stationary point at ``Q = lambda_p / lambda_e``;
- exponential vs logarithmic: ``phi' = lambda_e - psi(Q)`` with
  ``psi(Q) = lambda_l / ((1 + lambda_l Q) ln(1 + lambda_l Q))`` strictly
  decreasing, so phi is strictly convex; its stationary point solves
  ``psi = lambda_e``;
- power vs logarithmic: ``Q phi' = lambda_p - x / ((1 + x) ln(1 + x))`` with
  ``x = lambda_l Q``; since ``(1 + x) ln(1 + x) > x`` the bracket exceeds
  ``lambda_p - 1 >= 0``, so phi is strictly increasing (requires lambda_p >= 1).

So (0, 1] splits into at most two strictly monotone pieces, each holding at most
one root.  A root exists on a piece exactly when phi has opposite signs at its
ends, where the Q -> 0+ end uses the analytic limit of phi.  Each root is then
refined by Brent's method on a sign-checked bracket.  ``Q = 0`` is outside the
domain and is never evaluated; its limit is reported separately.  Units: g is in
FLOPs per token, Q is dimensionless.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Callable, Mapping

from scipy.optimize import brentq

FAMILIES = ("exponential", "power", "logarithmic")
BRENT_XTOL = 1e-15
BRENT_RTOL = 4.0 * 2.0**-52
SCREEN_POINTS = 20001


def _g(family: str, gamma: float, lam: float, q: float) -> float:
    if family == "exponential":
        return gamma * math.exp(lam * q)
    if family == "power":
        return gamma * q**lam
    if family == "logarithmic":
        return gamma * math.log1p(lam * q)
    raise KeyError(family)


def _log_g(family: str, gamma: float, lam: float, q: float) -> float:
    if family == "exponential":
        return math.log(gamma) + lam * q
    if family == "power":
        return math.log(gamma) + lam * math.log(q)
    if family == "logarithmic":
        return math.log(gamma) + math.log(math.log1p(lam * q))
    raise KeyError(family)


def _psi(lam_l: float, q: float) -> float:
    x = lam_l * q
    return lam_l / ((1.0 + x) * math.log1p(x))


def _structure(left: str, right: str, p: Mapping[str, Mapping[str, float]]) -> tuple[str, float | None, float]:
    """Return (shape, interior stationary Q or None, sign of phi at 0+ as +/-1 or a finite value)."""
    pair = (left, right)
    if pair == ("exponential", "power"):
        stationary = p["power"]["lambda"] / p["exponential"]["lambda"]
        return "strictly convex", stationary if 0.0 < stationary < 1.0 else None, math.inf
    if pair == ("exponential", "logarithmic"):
        lam_e, lam_l = p["exponential"]["lambda"], p["logarithmic"]["lambda"]
        # psi decreases from +inf; psi(1) >= lam_e means phi' <= 0 on all of (0, 1].
        stationary = None
        if _psi(lam_l, 1.0) < lam_e:
            upper = 1.0
            lower = upper
            while _psi(lam_l, lower) <= lam_e:
                lower /= 2.0
            stationary = brentq(lambda q: _psi(lam_l, q) - lam_e, lower, upper, xtol=BRENT_XTOL, rtol=BRENT_RTOL)
        return "strictly convex", stationary, math.inf
    if pair == ("power", "logarithmic"):
        lam_p = p["power"]["lambda"]
        if lam_p < 1.0:
            raise ValueError("power-vs-logarithmic monotonicity argument requires lambda_p >= 1")
        if lam_p > 1.0:
            limit = -math.inf
        else:
            limit = math.log(p["power"]["gamma"] / p["logarithmic"]["gamma"]) - math.log(p["logarithmic"]["lambda"])
        return "strictly increasing", None, limit
    raise KeyError(pair)


def _sign(value: float) -> int:
    return (value > 0.0) - (value < 0.0)


def raw_family_analysis(parameters: Mapping[str, Mapping[str, float]], domain: Mapping[str, Any]) -> dict[str, Any]:
    """Compare the three raw g(Q) families on the verified domain without any Q0."""
    if set(parameters) != set(FAMILIES):
        raise ValueError("raw family analysis needs exactly the three organizer families")
    if domain != {"lower": 0.0, "lower_inclusive": False, "upper": 1.0, "upper_inclusive": True}:
        raise ValueError("raw family analysis is defined for the verified domain (0, 1] only")

    def phi_of(left: str, right: str) -> Callable[[float], float]:
        pl, pr = parameters[left], parameters[right]
        return lambda q: (_log_g(left, pl["gamma"], pl["lambda"], q) - _log_g(right, pr["gamma"], pr["lambda"], q))

    pairs: list[dict[str, Any]] = []
    all_roots: list[float] = []
    for left, right in combinations(FAMILIES, 2):
        phi = phi_of(left, right)
        shape, stationary, limit_at_zero = _structure(left, right, parameters)
        cuts = [0.0] + ([stationary] if stationary is not None else []) + [1.0]
        pieces: list[dict[str, Any]] = []
        roots: list[float] = []
        for a, b in zip(cuts, cuts[1:]):
            left_value = limit_at_zero if a == 0.0 else phi(a)
            right_value = phi(b)
            piece: dict[str, Any] = {
                "interval": [a, b],
                "left_end": "limit Q->0+" if a == 0.0 else "Q=" + repr(a),
                "phi_left": left_value if math.isfinite(left_value) else ("+inf" if left_value > 0 else "-inf"),
                "phi_right": right_value,
            }
            if right_value == 0.0:
                root = b
            elif _sign(left_value) != _sign(right_value) and _sign(left_value) != 0:
                bracket_left = a
                if a == 0.0:
                    bracket_left = b / 2.0
                    while _sign(phi(bracket_left)) != _sign(left_value):
                        bracket_left /= 2.0
                        if bracket_left < 1e-300:
                            raise RuntimeError("could not bracket a root near Q -> 0+")
                root = brentq(phi, bracket_left, b, xtol=BRENT_XTOL, rtol=BRENT_RTOL)
                piece["bracket"] = [bracket_left, b]
            else:
                root = None
            piece["root"] = root
            pieces.append(piece)
            if root is not None:
                roots.append(root)
        all_roots.extend(roots)
        pl, pr = parameters[left], parameters[right]
        pairs.append({
            "pair": [left, right],
            "log_difference_shape": shape,
            "interior_stationary_q": stationary,
            "monotone_pieces": pieces,
            "crossings": [
                {
                    "q": root,
                    "g_value_flops_per_token": _g(left, pl["gamma"], pl["lambda"], root),
                    "relative_residual": abs(
                        _g(left, pl["gamma"], pl["lambda"], root) - _g(right, pr["gamma"], pr["lambda"], root)
                    ) / _g(left, pl["gamma"], pl["lambda"], root),
                }
                for root in roots
            ],
            "crossing_count": len(roots),
            "crossing_count_is_exact": True,
        })

    breakpoints = sorted(set(all_roots))
    edges = [0.0] + breakpoints + [1.0]
    ordering = []
    for a, b in zip(edges, edges[1:]):
        probe = b / 2.0 if a == 0.0 else math.sqrt(a * b)
        values = {name: _g(name, parameters[name]["gamma"], parameters[name]["lambda"], probe) for name in FAMILIES}
        ordering.append({
            "interval": [a, b],
            "interval_form": "(" + repr(a) + ", " + repr(b) + ("]" if b == 1.0 else ")"),
            "ascending_by_raw_g": sorted(FAMILIES, key=lambda name: values[name]),
        })

    screen = [10.0 ** (-12.0 + 12.0 * index / (SCREEN_POINTS - 1)) for index in range(SCREEN_POINTS)]
    screen_counts = {}
    for left, right in combinations(FAMILIES, 2):
        phi = phi_of(left, right)
        signs = [_sign(phi(q)) for q in screen]
        screen_counts[left + "_vs_" + right] = sum(1 for s, t in zip(signs, signs[1:]) if s * t < 0)

    return {
        "domain": {"interval": "(0, 1]", "q_zero_admissible": False, "unit_q": "dimensionless",
                   "unit_g": "FLOPs per token"},
        "families": {
            name: {
                "gamma_flops_per_token": parameters[name]["gamma"],
                "lambda": parameters[name]["lambda"],
                "strictly_increasing_on_domain": True,
                "limit_q_to_0_plus_flops_per_token": parameters[name]["gamma"] if name == "exponential" else 0.0,
                "value_at_q_1_flops_per_token": _g(name, parameters[name]["gamma"], parameters[name]["lambda"], 1.0),
            }
            for name in FAMILIES
        },
        "pairs": pairs,
        "interval_ordering": ordering,
        "grid_screen_cross_check": {
            "points": SCREEN_POINTS,
            "range": "geometric 1e-12 to 1",
            "sign_changes": screen_counts,
            "role": "consistency check only; crossing counts rest on the analytic monotone-piece argument",
        },
        "method": (
            "Analytic monotone-piece decomposition of phi = ln g_i - ln g_j, sign test at each piece end "
            "(Q->0+ by its analytic limit), Brent root refinement with xtol " + repr(BRENT_XTOL)
            + " and rtol 4*eps; deterministic, no random numbers."
        ),
        "interpretation": (
            "Raw g(Q) comparison only. No numeric Q0, no delta_g(Q;Q0), no normalization or calibration, "
            "no quality allocation and no Q optimization. A raw-g ordering does not order delta_g, which "
            "depends on each family's increment between Q0 and Q, and no family is a loss-benefit model."
        ),
    }


__all__ = ["FAMILIES", "raw_family_analysis"]
