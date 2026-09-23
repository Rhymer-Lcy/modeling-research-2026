"""The classic Chinchilla-form scaling law: parameterisation, fit, inference.

    L(N, D) = E + A * N**(-alpha) + B * D**(-beta)

Three choices here are methodological rather than incidental, and each replaces
something that looks simpler but answers a different question.

**Fit by Huber loss on log L, not ordinary least squares on log-log.**
Linearising to ``log L ~ log N + log D`` silently assumes ``E = 0``: the
irreducible loss is exactly the term that makes the relation non-linear, so a
log-log regression cannot estimate it and instead absorbs it into the
exponents. Following Hoffmann et al. (2022), the objective is a Huber loss on
the residual in log space, optimised from a grid of starting points because the
surface has flat regions where a single start can stall.

**Optimise unconstrained logs of the positive parameters.** ``A``, ``B`` and
``E`` must be positive; fitting ``a = log A`` and exponentiating keeps them so
without constraints, and log-sum-exp evaluation of the model keeps the residual
numerically stable when the three terms differ by orders of magnitude.

**Resample models, not rows.** The principal fit data is a handful of long
trajectories. Rows within a trajectory are strongly dependent, so a row-level
bootstrap treats correlated checkpoints as independent evidence and reports an
interval far narrower than the data supports. The cluster unit is the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

#: Hoffmann et al. use a small Huber delta on the log-space residual.
HUBER_DELTA = 1e-3

#: Grid of starting points, in the log parameterisation.
_INIT_A = (0.0, 5.0, 10.0)
_INIT_B = (0.0, 5.0, 10.0)
_INIT_E = (-1.0, 0.0, 0.5)
_INIT_ALPHA = (0.3, 0.5)
_INIT_BETA = (0.3, 0.5)


def predict(params: Sequence[float], n: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Return L(N, D) for the log-parameterised vector ``(a, b, e, alpha, beta)``."""
    a, b, e, alpha, beta = params
    return np.exp(e) + np.exp(a) * np.power(n, -alpha) + np.exp(b) * np.power(d, -beta)


def _log_predict(params: Sequence[float], log_n: np.ndarray, log_d: np.ndarray) -> np.ndarray:
    """log L, evaluated by log-sum-exp so the three terms cannot swamp each other."""
    a, b, e, alpha, beta = params
    stack = np.vstack([
        np.full_like(log_n, e),
        a - alpha * log_n,
        b - beta * log_d,
    ])
    return logsumexp(stack, axis=0)


def _huber(residual: np.ndarray, delta: float = HUBER_DELTA) -> float:
    absr = np.abs(residual)
    quadratic = np.minimum(absr, delta)
    linear = absr - quadratic
    return float(np.sum(0.5 * quadratic ** 2 + delta * linear))


@dataclass
class Fit:
    """A fitted law plus everything needed to judge it."""

    params: Dict[str, float]
    objective: float
    n_obs: int
    n_clusters: int
    converged: bool
    starts_tried: int
    starts_converged: int
    validity_box: Dict[str, Tuple[float, float]]
    raw: Sequence[float] = field(repr=False, default=())

    def predict(self, n: np.ndarray, d: np.ndarray) -> np.ndarray:
        return predict(self.raw, np.asarray(n, float), np.asarray(d, float))


def _default_starts() -> List[np.ndarray]:
    out = []
    for a0 in _INIT_A:
        for b0 in _INIT_B:
            for e0 in _INIT_E:
                for al0 in _INIT_ALPHA:
                    for be0 in _INIT_BETA:
                        out.append(np.array([a0, b0, e0, al0, be0], dtype=float))
    return out


def fit_law(
    n: Sequence[float],
    d: Sequence[float],
    loss: Sequence[float],
    clusters: Optional[Sequence[str]] = None,
    starts: Optional[Sequence[Sequence[float]]] = None,
) -> Fit:
    """Fit the classic law by Huber loss on log L from a grid of starts.

    ``starts`` overrides the default grid. Bootstrap replicates pass a small
    warm-started set: the full grid exists to find the basin from cold, and
    repeating that search thousands of times buys nothing once the basin is
    known. The point estimate itself always uses the full grid.
    """
    n = np.asarray(n, dtype=float)
    d = np.asarray(d, dtype=float)
    loss = np.asarray(loss, dtype=float)
    if np.any(n <= 0) or np.any(d <= 0) or np.any(loss <= 0):
        raise ValueError("N, D and loss must all be strictly positive")

    log_n, log_d, log_l = np.log(n), np.log(d), np.log(loss)

    def objective(theta: np.ndarray) -> float:
        return _huber(_log_predict(theta, log_n, log_d) - log_l)

    grid = _default_starts() if starts is None else [np.asarray(s, float) for s in starts]

    best: Optional[Tuple[float, np.ndarray]] = None
    tried = 0
    converged_count = 0
    for start in grid:
        tried += 1
        res = minimize(
            objective,
            start,
            method="L-BFGS-B",
            bounds=[
                (-20.0, 40.0),   # log A
                (-20.0, 40.0),   # log B
                (-10.0, 3.0),    # log E
                (1e-3, 3.0),     # alpha
                (1e-3, 3.0),     # beta
            ],
            options={"maxiter": 20000, "ftol": 1e-15, "gtol": 1e-12},
        )
        if res.success:
            converged_count += 1
        if np.isfinite(res.fun) and (best is None or res.fun < best[0]):
            best = (float(res.fun), res.x.copy())

    if best is None:
        raise RuntimeError("no starting point produced a finite objective")

    value, theta = best
    a, b, e, alpha, beta = theta
    n_clusters = len(set(clusters)) if clusters is not None else 0
    return Fit(
        params={
            "E": float(np.exp(e)),
            "A": float(np.exp(a)),
            "alpha": float(alpha),
            "B": float(np.exp(b)),
            "beta": float(beta),
        },
        objective=value,
        n_obs=int(len(n)),
        n_clusters=n_clusters,
        converged=converged_count > 0,
        starts_tried=tried,
        starts_converged=converged_count,
        validity_box={
            "N": (float(n.min()), float(n.max())),
            "D": (float(d.min()), float(d.max())),
        },
        raw=theta,
    )


def cluster_bootstrap(
    n: Sequence[float],
    d: Sequence[float],
    loss: Sequence[float],
    clusters: Sequence[str],
    replicates: int = 400,
    seed: int = 20260923,
) -> Dict[str, Dict[str, float]]:
    """Resample whole models with replacement and refit.

    The unit is the model because the rows are checkpoints along a trajectory.
    With only a handful of clusters the resulting intervals are wide; that is
    the honest width, and narrowing it requires more models rather than a
    different resampling scheme.
    """
    n = np.asarray(n, float)
    d = np.asarray(d, float)
    loss = np.asarray(loss, float)
    clusters = np.asarray(clusters)

    unique = np.unique(clusters)
    if len(unique) < 3:
        raise ValueError(
            f"a clustered bootstrap needs several clusters; found {len(unique)}"
        )
    index_by_cluster = {c: np.flatnonzero(clusters == c) for c in unique}

    # Warm start the replicates from the full-data solution. The cold grid is
    # for finding the basin; once it is known, repeating that search per
    # replicate costs two orders of magnitude for no change in the answer.
    anchor = fit_law(n, d, loss).raw
    warm = [
        np.asarray(anchor, float),
        np.asarray(anchor, float) + np.array([0.5, 0.5, 0.1, 0.02, 0.02]),
        np.asarray(anchor, float) - np.array([0.5, 0.5, 0.1, 0.02, 0.02]),
    ]

    rng = np.random.default_rng(seed)
    draws: List[Dict[str, float]] = []
    failures = 0
    for _ in range(replicates):
        picked = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([index_by_cluster[c] for c in picked])
        if len(np.unique(n[idx])) < 3:
            # Fewer than three distinct parameter counts cannot identify
            # (A, alpha, E) jointly. Refitting anyway returns a blown-up
            # coefficient that would widen the interval for a reason that has
            # nothing to do with sampling.
            failures += 1
            continue
        try:
            fit = fit_law(n[idx], d[idx], loss[idx], starts=warm)
        except Exception:  # noqa: BLE001 - a degenerate resample is not fatal
            failures += 1
            continue
        draws.append(fit.params)

    if not draws:
        raise RuntimeError("every bootstrap replicate failed")

    out: Dict[str, Dict[str, float]] = {}
    for key in ("E", "A", "alpha", "B", "beta"):
        values = np.array([drw[key] for drw in draws], dtype=float)
        out[key] = {
            "mean": float(values.mean()),
            "sd": float(values.std(ddof=1)),
            "lo2.5": float(np.percentile(values, 2.5)),
            "hi97.5": float(np.percentile(values, 97.5)),
        }
    out["_meta"] = {
        "replicates_requested": float(replicates),
        "replicates_used": float(len(draws)),
        "replicates_failed": float(failures),
        "n_clusters": float(len(unique)),
        "seed": float(seed),
    }
    return out


def evaluate(fit: Fit, n: Sequence[float], d: Sequence[float], loss: Sequence[float]) -> Dict[str, float]:
    """Out-of-sample error of a fitted law on held-out points."""
    n = np.asarray(n, float)
    d = np.asarray(d, float)
    loss = np.asarray(loss, float)
    pred = fit.predict(n, d)
    resid = pred - loss
    rel = resid / loss
    return {
        "n": float(len(loss)),
        "rmse": float(np.sqrt(np.mean(resid ** 2))),
        "mae": float(np.mean(np.abs(resid))),
        "mean_rel_err": float(np.mean(rel)),
        "median_abs_rel_err": float(np.median(np.abs(rel))),
        "max_abs_rel_err": float(np.max(np.abs(rel))),
    }


#: Hoffmann et al. (2022), "Training Compute-Optimal Large Language Models",
#: Eq. 10: the published parametric fit, with N in parameters and D in tokens.
PUBLISHED_CHINCHILLA = {"E": 1.69, "A": 406.4, "alpha": 0.34, "B": 410.7, "beta": 0.28}


def generator_recovery_diagnostic(
    n: Sequence[float],
    d: Sequence[float],
    loss: Sequence[float],
    decimals: int,
    reference: Optional[Dict[str, float]] = None,
) -> Dict[str, object]:
    """Test whether a loss column is a measurement or a formula evaluation.

    A table can be declared as observed and still be generated. The test does
    not rely on that declaration: it asks whether the loss values lie on a
    published closed-form law to within the quantum imposed by their own
    stored precision. Measured losses cannot, because training noise is orders
    of magnitude larger than a rounding step. A generated column can, and will.

    ``decimals`` is how many decimal places the source file stores. The
    rounding quantum is half a unit in the last place, so the largest relative
    error attributable purely to rounding is about ``0.5 * 10**-decimals``
    divided by a typical loss. If the observed residuals sit at or below that,
    there is no room left for measurement noise.
    """
    reference = dict(reference or PUBLISHED_CHINCHILLA)
    n = np.asarray(n, float)
    d = np.asarray(d, float)
    loss = np.asarray(loss, float)

    theta = np.array([
        np.log(reference["A"]),
        np.log(reference["B"]),
        np.log(reference["E"]),
        reference["alpha"],
        reference["beta"],
    ])
    rel = (predict(theta, n, d) - loss) / loss
    median_abs = float(np.median(np.abs(rel)))
    quantum = 0.5 * 10.0 ** (-decimals) / float(np.median(loss))

    return {
        "reference": reference,
        "n": int(len(loss)),
        "stored_decimals": int(decimals),
        "median_abs_rel_err": median_abs,
        "max_abs_rel_err": float(np.max(np.abs(rel))),
        "rounding_quantum_rel": float(quantum),
        "ratio_to_quantum": float(median_abs / quantum) if quantum > 0 else float("inf"),
        "consistent_with_rounding_only": bool(median_abs <= 3.0 * quantum),
    }


def compute_optimal(fit: Fit, budget_flops: float, kappa: float = 6.0) -> Dict[str, float]:
    """Budget-optimal (N, D) under a pure ``kappa * N * D`` constraint.

    Valid only when no quality-upgrade cost is purchased. With a quality term
    the budget is ``D * (kappa * N + delta_g)`` and this closed form does not
    apply; the general case is a one-dimensional solve and belongs to Q3.
    """
    p = fit.params
    alpha, beta = p["alpha"], p["beta"]
    a, b = p["A"], p["B"]
    exponent = 1.0 / (alpha + beta)
    n_star = ((alpha * a) / (beta * b) * (budget_flops / kappa) ** beta) ** exponent
    d_star = budget_flops / (kappa * n_star)
    return {
        "budget_flops": float(budget_flops),
        "kappa": float(kappa),
        "N_star": float(n_star),
        "D_star": float(d_star),
        "D_over_N": float(d_star / n_star),
        "L_star": float(predict(fit.raw, np.array([n_star]), np.array([d_star]))[0]),
    }


__all__ = [
    "HUBER_DELTA",
    "PUBLISHED_CHINCHILLA",
    "Fit",
    "predict",
    "fit_law",
    "cluster_bootstrap",
    "evaluate",
    "generator_recovery_diagnostic",
    "compute_optimal",
]
