"""Compute-aware decomposition on the C4-linked subset.

Only 94 of 4,497 panel models link deterministically to Epoch AI metadata (C4)
and only some of those carry a training-compute estimate; the linkage is
concentrated in pretrained base models and is not missing at random. Every
result here therefore travels with its subset size, strata distribution and a
selection-bias statement, and none is presented as representative of the panel.

Two analyses are kept distinct:

* **log-compute**: the benchmark score against log10 of C4's recorded training
  compute plus time. No scaling law is involved.
* **classic IF3**: the IF3 predicted loss at the model's (N, D) is used as a
  compute-aware scale index. N is C4's parameter count; D is inferred as
  ``C / (6 N)`` only where C4 records that its compute estimate was itself made
  by operation counting (the 6 N D convention the problem statement fixes), and
  never otherwise. The primary IF3 decomposition admits only rows inside the
  IF3 validity box; outside-box rows appear only as an extrapolation
  sensitivity.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.evolution.config import (
    COMPUTE_FLOP_PER_PARAM_TOKEN,
    D_INFERENCE_METHOD,
    MIN_IF3_PRIMARY_N,
)
from src.evolution.estimators import month_block_bootstrap, ols
from src.evolution.receipts import IF3Receipt, OutsideValidityBox


class SubsetSizeMissing(ValueError):
    """A compute-conditioned result was produced without its subset size."""


REQUIRED_SIZE_KEYS = ("n_panel", "n_linked", "n_compute", "n_used")


def subset(panel: pd.DataFrame, anchor: pd.Timestamp, primary_models: set) -> pd.DataFrame:
    """C4-linked rows with a training-compute estimate, a date and no test flag."""
    linked = panel["link_method"] != "unlinked"
    comp = pd.to_numeric(panel["c4_compute_flop"], errors="coerce")
    keep = linked & comp.notna() & panel["date_available"].astype(bool) & ~panel["test_flag"].astype(bool)
    f = panel.loc[keep].copy()
    if (f["link_method"] == "unlinked").any():
        raise ValueError("an unlinked row entered the compute subset")
    f["compute"] = pd.to_numeric(f["c4_compute_flop"], errors="coerce")
    f["n_c4"] = pd.to_numeric(f["c4_params"], errors="coerce")
    f["dataset_size"] = pd.to_numeric(f["c4_dataset_size"], errors="coerce")
    f["analysis_date"] = pd.to_datetime(f["analysis_date"])
    f["t_years"] = (f["analysis_date"] - anchor).dt.days / 365.25
    f["month"] = f["analysis_date"].dt.to_period("M")
    f["macro"] = f["average"].astype(float)
    f["log10_c"] = np.log10(f["compute"])
    f["in_primary"] = f["model"].isin(primary_models)
    return f


def sizes(panel: pd.DataFrame, f: pd.DataFrame, used: int) -> Dict[str, int]:
    return {
        "n_panel": int(len(panel)),
        "n_linked": int((panel["link_method"] != "unlinked").sum()),
        "n_compute": int(pd.to_numeric(panel["c4_compute_flop"], errors="coerce").notna().sum()),
        "n_subset": int(len(f)),
        "n_used": int(used),
    }


def infer_nd(f: pd.DataFrame, if3: IF3Receipt) -> pd.DataFrame:
    out = f.copy()
    method = out["c4_compute_method"].fillna("").astype(str)
    counted = method.str.contains(D_INFERENCE_METHOD, regex=False)
    ok = counted & out["n_c4"].gt(0) & out["compute"].gt(0)
    out["d_inferred"] = np.where(ok, out["compute"] / (COMPUTE_FLOP_PER_PARAM_TOKEN * out["n_c4"]), np.nan)
    out["d_rule"] = np.where(ok, "C/(6N), operation-counted", "not inferred")
    out["d_vs_dataset_size"] = out["d_inferred"] / out["dataset_size"]
    has = out["d_inferred"].notna()
    out["inside_if3_box"] = False
    out.loc[has, "inside_if3_box"] = if3.inside(out.loc[has, "n_c4"], out.loc[has, "d_inferred"])
    out["if3_loss"] = np.nan
    out.loc[has, "if3_loss"] = if3.predict(out.loc[has, "n_c4"], out.loc[has, "d_inferred"], allow_extrapolation=True)
    return out


def _fit(f: pd.DataFrame, xcol: str) -> Dict[str, float]:
    """``macro = a + k x + g t`` plus the exact omitted-variable split of the time-only slope.

    With ``x = c + s t`` fitted by OLS on the same rows, the time-only slope
    equals ``g + k s`` exactly, so ``k s`` is the part of the score trend that
    moved with the scale index and ``g`` the part that did not.
    """
    t = f["t_years"].to_numpy(float)
    x = f[xcol].to_numpy(float)
    y = f["macro"].to_numpy(float)
    one = np.ones(len(f))
    beta = ols(np.column_stack([one, x, t]), y)
    g_time = ols(np.column_stack([one, t]), y)[1]
    s = ols(np.column_stack([one, t]), x)[1]
    if abs(g_time - (beta[2] + beta[1] * s)) > 1e-8 * max(1.0, abs(g_time)):
        raise ArithmeticError("omitted-variable identity violated")
    return {"intercept": float(beta[0]), "slope_scale": float(beta[1]), "slope_time": float(beta[2]),
            "g_time": float(g_time), "scale_growth": float(s), "scale_rate": float(beta[1] * s),
            "share_scale": float(beta[1] * s / g_time) if g_time > 0 else float("nan")}


def log_compute(f: pd.DataFrame, label: str) -> Dict[str, object]:
    point = _fit(f, "log10_c")
    boot = month_block_bootstrap(f, lambda s: _fit(s, "log10_c"), label)
    return {"point": point, "boot": boot, "n": int(len(f)), "months": int(f["month"].nunique())}


def if3_primary(f: pd.DataFrame, if3: IF3Receipt) -> Dict[str, object]:
    """The primary IF3 decomposition. Refuses any row outside the validity box."""
    has = f["d_inferred"].notna()
    if not bool(if3.inside(f.loc[has, "n_c4"], f.loc[has, "d_inferred"]).all()) or not bool(has.all()):
        raise OutsideValidityBox("the primary IF3 decomposition admits only rows with inferred (N, D) inside the box")
    if len(f) < MIN_IF3_PRIMARY_N:
        return {"status": "not supported", "n": int(len(f)),
                "reason": "fewer than " + str(MIN_IF3_PRIMARY_N) + " inside-box rows"}
    return {"status": "estimated", "n": int(len(f)), "point": _fit(f, "if3_loss")}


def if3_extrapolation(f: pd.DataFrame) -> Dict[str, object]:
    """Extrapolation sensitivity over all D-inferred rows, inside or outside the box."""
    g = f[f["d_inferred"].notna()]
    return {"n": int(len(g)), "n_outside": int((~g["inside_if3_box"]).sum()), "point": _fit(g, "if3_loss")}


def require_sizes(result: Dict[str, object]) -> None:
    missing = [k for k in REQUIRED_SIZE_KEYS if k not in result.get("sizes", {})]
    if missing:
        raise SubsetSizeMissing("compute-conditioned result lacks subset size field(s) " + repr(missing))


__all__ = ["SubsetSizeMissing", "subset", "sizes", "infer_nd", "log_compute", "if3_primary",
           "if3_extrapolation", "require_sizes", "REQUIRED_SIZE_KEYS"]
