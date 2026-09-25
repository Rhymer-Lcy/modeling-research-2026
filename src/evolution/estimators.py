"""Low-complexity estimators used by the Q4 decomposition and forecast.

Quantile regression is solved exactly as the standard linear programme

    min  sum_i tau * u_i+ + (1 - tau) * u_i-   s.t.  X beta + u+ - u- = y,  u+/- >= 0

with SciPy's HiGHS solver, because the pinned environment carries no
statistics package and a hand-rolled iterative scheme would add a convergence
question the LP does not have. Uncertainty comes from a month-block bootstrap:
whole calendar months are resampled, so models dated in the same month are
never treated as independent draws. Each bootstrap stream is seeded from the
shared seed and a stable label, so a result never depends on call order.
"""

from __future__ import annotations

import zlib
from typing import Callable, Dict, List, Sequence

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog

from src.evolution.config import BOOTSTRAP_REPLICATES, SEED


class EstimationError(RuntimeError):
    """A fit failed to solve; never silently replaced by a default."""


def quantreg(X: np.ndarray, y: np.ndarray, tau: float) -> np.ndarray:
    """Linear quantile regression coefficients at quantile ``tau``."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, p = X.shape
    if n <= p:
        raise EstimationError("quantile regression needs more rows than coefficients")
    c = np.concatenate([np.zeros(p), np.full(n, tau), np.full(n, 1.0 - tau)])
    eye = sparse.identity(n, format="csr")
    a_eq = sparse.hstack([sparse.csr_matrix(X), eye, -eye], format="csr")
    bounds = [(None, None)] * p + [(0, None)] * (2 * n)
    res = linprog(c, A_eq=a_eq, b_eq=y, bounds=bounds, method="highs")
    if res.status != 0:
        raise EstimationError("quantile regression LP failed: " + str(res.message))
    return np.asarray(res.x[:p], float)


def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    if X.shape[0] <= X.shape[1]:
        raise EstimationError("OLS needs more rows than coefficients")
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def rng_for(label: str) -> np.random.Generator:
    """A generator seeded from the shared seed and a stable label."""
    return np.random.default_rng([SEED, zlib.crc32(label.encode("utf-8"))])


def month_block_bootstrap(frame: pd.DataFrame, stat: Callable[[pd.DataFrame], Dict[str, float]],
                          label: str, replicates: int = BOOTSTRAP_REPLICATES,
                          block: str = "month") -> pd.DataFrame:
    """Resample whole ``block`` groups with replacement; one row of ``stat`` per replicate.

    A replicate whose fit fails is recorded as NaN and counted, never dropped
    silently: the caller reports how many replicates were usable.
    """
    rng = rng_for(label)
    blocks = sorted(frame[block].unique())
    index = {b: frame.index[frame[block] == b] for b in blocks}
    rows: List[Dict[str, float]] = []
    for _ in range(replicates):
        pick = rng.integers(0, len(blocks), size=len(blocks))
        idx = np.concatenate([index[blocks[k]] for k in pick])
        sample = frame.loc[idx].reset_index(drop=True)
        try:
            rows.append(stat(sample))
        except EstimationError:
            rows.append({})
    out = pd.DataFrame(rows)
    out.attrs["blocks"] = len(blocks)
    out.attrs["replicates"] = replicates
    return out


def interval(values: Sequence[float], lo: float, hi: float) -> tuple[float, float]:
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return (float("nan"), float("nan"))
    return (float(np.quantile(v, lo)), float(np.quantile(v, hi)))


__all__ = ["EstimationError", "quantreg", "ols", "rng_for", "month_block_bootstrap", "interval"]
