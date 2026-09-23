"""Quality-aware generalisation of the classic N-D scaling law.

The candidate form is

    L(N, D, Q) = E + A * N^(-alpha) + B * (Q^gamma * D)^(-beta)
               = E + A * N^(-alpha) + B * Q^(-gamma*beta) * D^(-beta)

so that data quality acts as a multiplier on effective token count. It is a
model to be TESTED, not a truth to be forced: `fit_quality_law` reports whether
gamma is identifiable, and the caller is expected to check that before
believing it.

Three things this module deliberately does not do:

* It does not decide whether a table's quality variation is empirical. A fit to
  a semi-synthetic table recovers that table's generator; `quality_fingerprint`
  measures how close the recovery is, and the caller must carry that provenance
  into any claim.
* It does not silently return NaN at a domain boundary. The equivalent-capacity
  transform is undefined beyond a finite reduction, and that boundary is a
  result, so it raises with the binding quantity named.
* It does not rescale Q. Q arrives on the declared IF1 scale and is used as
  given, because refitting on a silently different Q scale changes what gamma
  means between fits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from src.scaling.law import HUBER_DELTA, _huber

#: Starting grid in the log parameterisation, extended with gamma.
_INIT_A = (0.0, 5.0, 10.0)
_INIT_B = (0.0, 5.0, 10.0)
_INIT_E = (-1.0, 0.0, 0.5)
_INIT_ALPHA = (0.3, 0.5)
_INIT_BETA = (0.3, 0.5)
_INIT_GAMMA = (0.2, 1.0, 2.0)


def predict_q(params: Sequence[float], n, d, q) -> np.ndarray:
    """L(N, D, Q) for the log-parameterised vector ``(a, b, e, alpha, beta, gamma)``."""
    a, b, e, alpha, beta, gamma = params
    n = np.asarray(n, dtype=float)
    d = np.asarray(d, dtype=float)
    q = np.asarray(q, dtype=float)
    return (
        np.exp(e)
        + np.exp(a) * np.power(n, -alpha)
        + np.exp(b) * np.power(np.power(q, gamma) * d, -beta)
    )


def _log_predict_q(params, log_n, log_d, log_q) -> np.ndarray:
    """log L by log-sum-exp, so no term can swamp the others numerically."""
    a, b, e, alpha, beta, gamma = params
    stack = np.vstack([
        np.full_like(log_n, e),
        a - alpha * log_n,
        b - beta * (gamma * log_q + log_d),
    ])
    return logsumexp(stack, axis=0)


@dataclass
class QualityFit:
    """A fitted quality-aware law plus what is needed to judge it."""

    params: Dict[str, float]
    objective: float
    n_obs: int
    converged: bool
    starts_tried: int
    starts_refined: int
    starts_converged: int
    validity_box: Dict[str, Tuple[float, float]]
    raw: Sequence[float] = field(repr=False, default=())

    def predict(self, n, d, q) -> np.ndarray:
        return predict_q(self.raw, n, d, q)


def _starts() -> List[np.ndarray]:
    out = []
    for a0 in _INIT_A:
        for b0 in _INIT_B:
            for e0 in _INIT_E:
                for al0 in _INIT_ALPHA:
                    for be0 in _INIT_BETA:
                        for ga0 in _INIT_GAMMA:
                            out.append(np.array([a0, b0, e0, al0, be0, ga0], float))
    return out


def fit_quality_law(
    n: Sequence[float],
    d: Sequence[float],
    q: Sequence[float],
    loss: Sequence[float],
    starts: Optional[Sequence[Sequence[float]]] = None,
) -> QualityFit:
    """Fit the quality-aware law by Huber loss on log L from a grid of starts.

    Q must be strictly positive and must already be on the declared scale.
    """
    n = np.asarray(n, float)
    d = np.asarray(d, float)
    q = np.asarray(q, float)
    loss = np.asarray(loss, float)
    if np.any(n <= 0) or np.any(d <= 0) or np.any(loss <= 0):
        raise ValueError("N, D and loss must all be strictly positive")
    if np.any(q <= 0):
        raise ValueError(
            "Q must be strictly positive: the law uses Q^gamma as a multiplier on "
            "effective tokens, which is undefined at or below zero"
        )

    log_n, log_d, log_q, log_l = np.log(n), np.log(d), np.log(q), np.log(loss)

    def objective(theta: np.ndarray) -> float:
        return _huber(_log_predict_q(theta, log_n, log_d, log_q) - log_l, HUBER_DELTA)

    grid = _starts() if starts is None else [np.asarray(s, float) for s in starts]

    bounds = [
        (-20.0, 40.0),   # log A
        (-20.0, 40.0),   # log B
        (-10.0, 3.0),    # log E
        (1e-3, 3.0),     # alpha
        (1e-3, 3.0),     # beta
        (1e-3, 10.0),    # gamma
    ]

    def run(start, ftol, gtol, maxiter):
        return minimize(
            objective, start, method="L-BFGS-B", bounds=bounds,
            options={"maxiter": maxiter, "ftol": ftol, "gtol": gtol},
        )

    # Two stages. The cold grid exists to locate the basin, and searching it at
    # final precision costs an order of magnitude for no change in the answer:
    # a start that is going to lose has already lost by the time the screen is
    # accurate to 1e-9. Only the best few starts are then refined to full
    # precision, and the reported objective always comes from that refinement.
    screened = []
    tried = 0
    for start in grid:
        tried += 1
        res = run(start, ftol=1e-9, gtol=1e-7, maxiter=2000)
        if np.isfinite(res.fun):
            screened.append((float(res.fun), res.x.copy()))

    if not screened:
        raise RuntimeError("no starting point produced a finite objective")

    screened.sort(key=lambda item: item[0])
    n_refine = max(3, min(12, len(screened)))

    best: Optional[Tuple[float, np.ndarray]] = None
    converged = 0
    for _value, theta0 in screened[:n_refine]:
        res = run(theta0, ftol=1e-15, gtol=1e-12, maxiter=20000)
        if res.success:
            converged += 1
        if np.isfinite(res.fun) and (best is None or res.fun < best[0]):
            best = (float(res.fun), res.x.copy())

    if best is None:
        raise RuntimeError("refinement produced no finite objective")

    value, theta = best
    a, b, e, alpha, beta, gamma = theta
    return QualityFit(
        params={
            "E": float(np.exp(e)),
            "A": float(np.exp(a)),
            "alpha": float(alpha),
            "B": float(np.exp(b)),
            "beta": float(beta),
            "gamma": float(gamma),
        },
        objective=value,
        n_obs=int(n.size),
        converged=converged > 0,
        starts_tried=tried,
        starts_refined=n_refine,
        starts_converged=converged,
        validity_box={
            "N": (float(n.min()), float(n.max())),
            "D": (float(d.min()), float(d.max())),
            "Q": (float(q.min()), float(q.max())),
        },
        raw=tuple(float(v) for v in theta),
    )


# ---------------------------------------------------------------------------
# Marginal effects
# ---------------------------------------------------------------------------

def partials(params: Sequence[float], n, d, q) -> Dict[str, np.ndarray]:
    """Analytic first partial derivatives of L with respect to N, D and Q.

    In the valid parameter region (A, B, alpha, beta, gamma all positive) all
    three are strictly negative: more parameters, more tokens and better data
    each reduce loss.
    """
    a, b, e, alpha, beta, gamma = params
    n = np.asarray(n, float)
    d = np.asarray(d, float)
    q = np.asarray(q, float)
    A, B = np.exp(a), np.exp(b)

    # The data/quality term written out: B * Q^(-gamma*beta) * D^(-beta)
    data_term = B * np.power(q, -gamma * beta) * np.power(d, -beta)

    return {
        "dL_dN": -alpha * A * np.power(n, -alpha - 1.0),
        "dL_dD": -beta * data_term / d,
        "dL_dQ": -gamma * beta * data_term / q,
    }


def elasticities(params: Sequence[float], n, d, q) -> Dict[str, np.ndarray]:
    """Log elasticities, and the same quantities against excess loss.

    Three quantities are easy to confuse and are therefore returned separately
    and named:

    * ``dlogL_dlogX``  - elasticity of TOTAL loss. Damped by the irreducible
      floor E, so it goes to zero as the model approaches E.
    * ``dlogLex_dlogX`` - elasticity of EXCESS (reducible) loss, L - E. This is
      the one that equals -alpha for N in the pure power-law limit.
    * ``share_X`` - the share of excess loss carried by that term.
    """
    a, b, e, alpha, beta, gamma = params
    n = np.asarray(n, float)
    d = np.asarray(d, float)
    q = np.asarray(q, float)
    A, B, E = np.exp(a), np.exp(b), np.exp(e)

    term_n = A * np.power(n, -alpha)
    term_d = B * np.power(np.power(q, gamma) * d, -beta)
    total = E + term_n + term_d
    excess = term_n + term_d

    return {
        "dlogL_dlogN": -alpha * term_n / total,
        "dlogL_dlogD": -beta * term_d / total,
        "dlogL_dlogQ": -gamma * beta * term_d / total,
        "dlogLex_dlogN": -alpha * term_n / excess,
        "dlogLex_dlogD": -beta * term_d / excess,
        "dlogLex_dlogQ": -gamma * beta * term_d / excess,
        "share_N": term_n / excess,
        "share_D": term_d / excess,
    }


# ---------------------------------------------------------------------------
# Iso-loss substitution
# ---------------------------------------------------------------------------

def iso_loss_dn_dq(params: Sequence[float], n, d, q) -> np.ndarray:
    """dN/dQ along a curve of constant loss.

    Along an iso-loss curve, dN/dQ = -L_Q / L_N. Both partials are negative in
    the valid region, so the ratio is negative: improving data quality REDUCES
    the parameter count needed for the same loss. The sign is load-bearing, and
    the common error is to report it positive.
    """
    p = partials(params, n, d, q)
    return -p["dL_dQ"] / p["dL_dN"]


class InfeasibleEquivalent(ValueError):
    """Raised when a loss reduction exceeds what the N term can ever supply.

    The equivalent-capacity transform asks what parameter count would have
    delivered a given reduction R through the N term alone. The N term's total
    reach is A * N^(-alpha); a reduction at or beyond that cannot be bought
    with any finite N. Returning NaN would hide the fact that the question
    itself has no finite answer.
    """


def parameter_saving(params: Sequence[float], n, reduction) -> np.ndarray:
    """Change in N that keeps loss constant when the data term falls by R.

    If better data removes R from the data/quality term, the N term may RISE by
    R without changing total loss, so fewer parameters are needed:

        N_sub   = [N^(-alpha) + R/A]^(-1/alpha)
        Delta_N = N_sub - N                      (negative)

    Always finite and always negative for R > 0.
    """
    a, _b, _e, alpha, _beta, _gamma = params
    A = np.exp(a)
    n = np.asarray(n, float)
    reduction = np.asarray(reduction, float)
    if np.any(reduction < 0):
        raise ValueError("reduction must be non-negative")
    n_sub = np.power(np.power(n, -alpha) + reduction / A, -1.0 / alpha)
    return n_sub - n


def equivalent_capacity(params: Sequence[float], n, reduction) -> np.ndarray:
    """Extra parameters that would have bought the same reduction R.

        N_eq    = [N^(-alpha) - R/A]^(-1/alpha)
        Delta_N = N_eq - N                       (positive)

    Finite only while R < A * N^(-alpha); at the boundary the required N
    diverges. Raises :class:`InfeasibleEquivalent` rather than returning NaN.
    """
    a, _b, _e, alpha, _beta, _gamma = params
    A = np.exp(a)
    n = np.asarray(n, float)
    reduction = np.asarray(reduction, float)
    if np.any(reduction < 0):
        raise ValueError("reduction must be non-negative")

    headroom = A * np.power(n, -alpha)
    if np.any(reduction >= headroom):
        worst = float(np.max(reduction / headroom))
        raise InfeasibleEquivalent(
            "reduction reaches or exceeds the N term's total reach "
            "A*N^(-alpha), so no finite parameter count is equivalent "
            f"(max R/headroom = {worst:.6g}; must be < 1)"
        )
    n_eq = np.power(np.power(n, -alpha) - reduction / A, -1.0 / alpha)
    return n_eq - n


# ---------------------------------------------------------------------------
# Provenance diagnostic
# ---------------------------------------------------------------------------

def quality_fingerprint(fit: QualityFit, n, d, q, loss, stored_dp: int) -> Dict[str, float]:
    """How close is this fit to exactly reproducing the table?

    Same logic as the classic generator-recovery diagnostic: compare the median
    absolute relative residual against the rounding quantum implied by the
    number of decimal places the source file stores. A ratio near 1 means the
    fit reproduces the table to its own storage precision, which is what
    recovering a generator looks like and is NOT evidence that real models obey
    the law.
    """
    pred = fit.predict(n, d, q)
    loss = np.asarray(loss, float)
    rel = np.abs(pred - loss) / loss
    median_rel = float(np.median(rel))
    quantum = float(0.5 * 10.0 ** (-stored_dp) / np.median(loss))
    return {
        "median_abs_rel_err": median_rel,
        "rounding_quantum": quantum,
        "ratio": median_rel / quantum if quantum > 0 else float("inf"),
        "max_abs_rel_err": float(np.max(rel)),
    }


__all__ = [
    "predict_q",
    "QualityFit",
    "fit_quality_law",
    "partials",
    "elasticities",
    "iso_loss_dn_dq",
    "parameter_saving",
    "equivalent_capacity",
    "InfeasibleEquivalent",
    "quality_fingerprint",
]
