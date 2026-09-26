"""Frontier, scale / non-scale decomposition and frontier forecast.

**Frontier.** The upper frontier is the conditional 90th percentile of the macro
score, estimated by linear quantile regression on calendar time (its level at
the final observed panel date and its trend). A monthly binned upper quantile,
with counts and a sparse flag below the minimum bin size, is reported beside it
as the descriptive frontier; the bin maximum and top-k mean are sensitivities.

**Decomposition.** Three views are kept distinct.

* *Mean, all models* (exact). With ordinary least squares the time-only slope
  splits exactly, by the omitted-variable identity, into
  ``g_time = g_resid + b * s``: ``b`` is the score gradient in log10 N at fixed
  time, ``s`` the trend of log10 N, so ``b * s`` is the scale-associated and
  ``g_resid`` the non-scale-associated part of the change in mean score.
* *Frontier set* (exact). The same identity on the models at or above their
  own month's upper quantile, in non-sparse months only. A post-failure,
  model-conditional decomposition: adopted only after the predeclared additive
  quantile split failed its consistency check, and never presented as
  predeclared. It splits the continuation trend for the parameter-scale
  scenarios; the historical continuation itself does not depend on it.
* *Additive quantile* (predeclared, rejected). ``Q_0.9(score | log10 N, t)``
  with the frontier scale path ``Q_0.9(log10 N | t)``. Quantiles obey no exact
  identity, so its decomposed total is checked against the direct frontier
  trend; on this panel the check fails (a strong scale x time interaction, see
  the matched-scale diagnostic), so it is retained as a negative result only.

``g_resid`` is a conditional time association: it contains everything that
moved with calendar time at fixed parameter count, including training-data and
compute growth that parameter count does not capture. It is not a measured rate
of algorithmic progress, and nothing here establishes a causal effect of time.

**Forecast.** Level and trend come from the time-only frontier estimator,
anchored at the final observed panel date: that direct time trend is the
primary descriptive forecast trend, and its continuation is the historical /
direct-score continuation baseline. For the parameter-scale-growth scenarios
the trend is split by the frontier-set shares and a parameter-scale multiplier
``m`` scales a positive parameter-scale-associated component only. Parameter
count is not training compute; nothing here is a compute-growth scenario.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from src.evolution.config import (
    DAYS_PER_YEAR,
    FRONTIER_QUANTILE,
    HORIZONS_MONTHS,
    INTERVAL,
    MIN_BAND_N,
    MIN_BIN_N,
    MIN_FRONTIER_SET_N,
    MIN_ORIGINS,
    MIN_TRAIN_BINS,
    SCALE_BANDS_B,
    SCENARIOS,
    TOP_K,
)
from src.evolution.estimators import interval, month_block_bootstrap, ols, quantreg

Z90 = 1.6448536269514722  # two-sided 90% normal quantile
IDENTITY_TOL = 1.0e-8


class ForecastError(ValueError):
    """A forecast was requested against the anchoring or horizon rules."""


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

def years_between(later: pd.Timestamp, earlier: pd.Timestamp) -> float:
    return float((pd.Timestamp(later) - pd.Timestamp(earlier)).days) / DAYS_PER_YEAR


def month_mid(month: pd.Period) -> pd.Timestamp:
    start, end = month.start_time, month.end_time.normalize()
    return start + (end - start) / 2


def horizon_dates(anchor: pd.Timestamp) -> Dict[str, pd.Timestamp]:
    """Horizon dates, in calendar months counted from the final observed panel date."""
    return {k: pd.Timestamp(anchor) + pd.DateOffset(months=m) for k, m in HORIZONS_MONTHS.items()}


def check_anchor(frame: pd.DataFrame, anchor: pd.Timestamp) -> None:
    """The anchor must be the population's final observed date."""
    last = pd.to_datetime(frame["analysis_date"]).max()
    if pd.Timestamp(anchor) != last:
        raise ForecastError("forecast anchor " + str(anchor) + " is not the final observed panel date " + str(last))


# ---------------------------------------------------------------------------
# Descriptive frontier and the frontier set
# ---------------------------------------------------------------------------

def binned_frontier(frame: pd.DataFrame, anchor: pd.Timestamp, value: str = "macro") -> pd.DataFrame:
    rows = []
    for month in sorted(frame["month"].unique()):
        sub = frame.loc[frame["month"] == month]
        v = sub[value].to_numpy(float)
        p90 = float(np.quantile(v, FRONTIER_QUANTILE))
        top = sub.loc[sub[value] >= p90]
        rows.append({
            "month": month, "n": int(v.size), "sparse": bool(v.size < MIN_BIN_N),
            "p90": p90, "max": float(v.max()), "top_k_mean": float(np.sort(v)[::-1][:TOP_K].mean()),
            "median": float(np.median(v)), "n_frontier": int(len(top)),
            "frontier_median_params_b": float(top["params_b"].median()),
            "t_mid": years_between(month_mid(month), anchor),
        })
    return pd.DataFrame(rows)


def frontier_flags(frame: pd.DataFrame, value: str = "macro") -> pd.Series:
    """Frontier-set membership, fixed once on the observed data (never re-derived in a bootstrap)."""
    flags = pd.Series(False, index=frame.index)
    for month, sub in frame.groupby("month"):
        if len(sub) < MIN_BIN_N:
            continue
        p90 = np.quantile(sub[value].to_numpy(float), FRONTIER_QUANTILE)
        flags.loc[sub.index[sub[value] >= p90]] = True
    return flags


# ---------------------------------------------------------------------------
# Decomposition
# ---------------------------------------------------------------------------

def _x(*cols: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(cols[0]))] + list(cols))


def exact_split(frame: pd.DataFrame, value: str = "macro") -> Dict[str, float]:
    """OLS time slope split exactly into scale-associated and non-scale-associated parts."""
    t = frame["t_years"].to_numpy(float)
    ln = frame["log10_n"].to_numpy(float)
    y = frame[value].to_numpy(float)
    level, g_time = ols(_x(t), y)
    _, b, g = ols(_x(ln, t), y)
    _, s = ols(_x(t), ln)
    if abs(g_time - (g + b * s)) > IDENTITY_TOL * max(1.0, abs(g_time)):
        raise ArithmeticError("omitted-variable identity violated; the split would not be exact")
    return {
        "n": float(len(frame)), "months": float(frame["month"].nunique()),
        "level0": float(level), "g_time": float(g_time), "b_scale": float(b), "scale_growth": float(s),
        "scale_rate": float(b * s), "resid_rate": float(g),
        "share_scale": float(b * s / g_time) if g_time > 0 else float("nan"),
    }


def quantile_split(frame: pd.DataFrame, value: str = "macro", tau: float = FRONTIER_QUANTILE) -> Dict[str, float]:
    """The predeclared additive quantile decomposition, with its consistency gap."""
    t = frame["t_years"].to_numpy(float)
    ln = frame["log10_n"].to_numpy(float)
    y = frame[value].to_numpy(float)
    level, g_time = quantreg(_x(t), y, tau)
    _, b, g = quantreg(_x(ln, t), y, tau)
    _, s = quantreg(_x(t), ln, tau)
    total = b * s + g
    return {
        "level0": float(level), "g_time": float(g_time), "b_scale": float(b), "resid_rate": float(g),
        "scale_growth": float(s), "scale_rate": float(b * s), "decomposed_total": float(total),
        "consistency_gap": float(total - g_time),
        "consistent": bool(np.sign(total) == np.sign(g_time) and abs(total - g_time) <= 0.5 * abs(g_time)),
    }


def split_eligible(frame: pd.DataFrame) -> bool:
    """Size rule for the frontier-set split, applied once to the observed data."""
    fs = frame[frame["frontier_set"]]
    return len(fs) >= MIN_FRONTIER_SET_N and fs["month"].nunique() >= MIN_TRAIN_BINS


def components(frame: pd.DataFrame, value: str = "macro", split: bool | None = None) -> Dict[str, float]:
    """Everything the forecast and its bootstrap need, for one group.

    ``frame`` must carry a boolean ``frontier_set`` column from :func:`frontier_flags`.
    ``split`` is decided once on the observed data and passed unchanged to every
    bootstrap replicate, so resampling can never switch the split on or off.
    """
    q = quantile_split(frame, value)
    out: Dict[str, float] = {"level0": q["level0"], "g_time": q["g_time"]}
    out.update({"q_" + k: v for k, v in q.items() if k not in ("level0", "g_time")})
    out.update({"mean_" + k: v for k, v in exact_split(frame, value).items()})
    fs = frame[frame["frontier_set"]]
    out["fs_n"] = float(len(fs))
    out["fs_months"] = float(fs["month"].nunique())
    if split is None:
        split = split_eligible(frame)
    out["split_identified"] = float(split)
    out["frontier_scale_rate"] = float("nan")
    out["frontier_resid_rate"] = float("nan")
    if split:
        s = exact_split(fs, value)
        out.update({"fs_" + k: v for k, v in s.items() if k not in ("n", "months")})
        if np.isfinite(s["share_scale"]):
            out["frontier_scale_rate"] = float(q["g_time"] * s["share_scale"])
            out["frontier_resid_rate"] = float(q["g_time"] - out["frontier_scale_rate"])
    return out


def rate(comp: Dict[str, float], multiplier: float) -> Tuple[float, bool]:
    """Frontier improvement rate under a parameter-scale-growth multiplier, and whether it binds.

    NaN when the split was declared identified but this replicate's frontier-set
    time trend is not positive, so its shares are undefined; such replicates are
    counted as unusable rather than quietly given the time-only rate.
    """
    if not comp["split_identified"]:
        return comp["g_time"], False
    scale, resid = comp["frontier_scale_rate"], comp["frontier_resid_rate"]
    if not np.isfinite(scale):
        return float("nan"), False
    if scale > 0:
        return resid + multiplier * scale, multiplier != 1.0
    return resid + scale, False


def project(comp: Dict[str, float], h_years: float, multiplier: float) -> float:
    return comp["level0"] + rate(comp, multiplier)[0] * h_years


def band_index(params_b: np.ndarray) -> np.ndarray:
    out = np.full(len(params_b), -1)
    for k, (lo, hi) in enumerate(SCALE_BANDS_B):
        out[(params_b >= lo) & (params_b < hi)] = k
    return out


def band_label(k: int) -> str:
    lo, hi = SCALE_BANDS_B[k]
    return (f"{lo:g}-{hi:g}B" if np.isfinite(hi) else f">={lo:g}B")


def matched_scale(frame: pd.DataFrame, value: str = "macro") -> pd.DataFrame:
    """Time trend within fixed scale bands, for the frontier and the mean."""
    bands = band_index(frame["params_b"].to_numpy(float))
    rows = []
    for k in range(len(SCALE_BANDS_B)):
        sub = frame.loc[bands == k]
        row = {"band": band_label(k), "n": int(len(sub)), "months": int(sub["month"].nunique()) if len(sub) else 0,
               "frontier_time_trend": float("nan"), "mean_time_trend": float("nan"), "estimated": False}
        if len(sub) >= MIN_BAND_N and sub["month"].nunique() >= 2:
            t = sub["t_years"].to_numpy(float)
            y = sub[value].to_numpy(float)
            row["frontier_time_trend"] = float(quantreg(_x(t), y, FRONTIER_QUANTILE)[1])
            row["mean_time_trend"] = float(ols(_x(t), y)[1])
            row["estimated"] = True
        rows.append(row)
    return pd.DataFrame(rows)


def scale_spec_residual(frame: pd.DataFrame, spec: str, value: str = "macro") -> float:
    """Mean-level non-scale-associated time trend under an alternative scale specification."""
    t = frame["t_years"].to_numpy(float)
    ln = frame["log10_n"].to_numpy(float)
    y = frame[value].to_numpy(float)
    if spec == "linear_log10N":
        return float(ols(_x(ln, t), y)[2])
    if spec == "quadratic_log10N":
        return float(ols(_x(ln, ln ** 2, t), y)[3])
    if spec == "scale_band_fixed_effects":
        bands = band_index(frame["params_b"].to_numpy(float))
        dummies = [(bands == k).astype(float) for k in sorted(set(bands))[1:]]
        return float(ols(_x(*dummies, t), y)[-1])
    raise ValueError("undeclared scale specification " + spec)


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

def bin_noise_sd(bins: pd.DataFrame, comp: Dict[str, float]) -> float:
    """Scatter of non-sparse monthly frontier points around the fitted frontier line."""
    dense = bins[~bins["sparse"]]
    if len(dense) < 3:
        return float("nan")
    resid = dense["p90"].to_numpy(float) - (comp["level0"] + comp["g_time"] * dense["t_mid"].to_numpy(float))
    return float(np.std(resid, ddof=1))


def forecast_table(frame: pd.DataFrame, anchor: pd.Timestamp, label: str, value: str = "macro"):
    """Point components, bootstrap draws, binned frontier and scenario x horizon forecasts.

    ``anchor`` is the analysis population's final observed date; this group's
    own last date may be earlier but never later.
    """
    if pd.to_datetime(frame["analysis_date"]).max() > pd.Timestamp(anchor):
        raise ForecastError("a group row lies after the forecast anchor")
    frame = frame.copy()
    frame["frontier_set"] = frontier_flags(frame, value)
    split = split_eligible(frame)
    comp = components(frame, value, split)
    boot = month_block_bootstrap(frame, lambda f: components(f, value, split), label)
    bins = binned_frontier(frame, anchor, value)
    noise = bin_noise_sd(bins, comp)
    if not np.isfinite(noise):
        raise ForecastError("fewer than three non-sparse frontier bins; no predictive noise estimate")
    records = [r for r in boot.to_dict("records") if r and np.isfinite(r.get("level0", np.nan))]
    rows = []
    for horizon, date in horizon_dates(anchor).items():
        h = years_between(date, anchor)
        for scen, m in SCENARIOS.items():
            point = project(comp, h, m)
            usable = [r for r in records if np.isfinite(project(r, h, m))]
            levels = np.array([r["level0"] for r in usable])
            draws = np.array([project(r, h, m) for r in usable])
            sd_boot = float(np.std(draws, ddof=1))
            sd_total = float(np.sqrt(sd_boot ** 2 + noise ** 2))
            lo, hi = interval(draws, *INTERVAL)
            rows.append({
                "horizon": horizon, "date": date, "h_years": h, "scenario": scen, "multiplier": m,
                "binding": rate(comp, m)[1], "point": point,
                "time_only_point": comp["level0"] + comp["g_time"] * h,
                "boot_lo": lo, "boot_hi": hi, "sd_level": float(np.std(levels, ddof=1)),
                "sd_increment": float(np.std(draws - levels, ddof=1)), "sd_boot": sd_boot,
                "sd_bin_noise": noise, "sd_total": sd_total,
                "pred_lo": point - Z90 * sd_total, "pred_hi": point + Z90 * sd_total,
                "replicates_usable": len(usable),
            })
    return comp, boot, bins, pd.DataFrame(rows), frame


# ---------------------------------------------------------------------------
# Rolling-origin validation
# ---------------------------------------------------------------------------

def choose_backtest_horizon(bins: pd.DataFrame) -> Tuple[int, Dict[int, int]]:
    """Longest horizon (months) with enough origins, decided from bin counts alone."""
    dense = set(bins.loc[~bins["sparse"], "month"])
    all_months = pd.period_range(bins["month"].min(), bins["month"].max(), freq="M")
    feasible: Dict[int, int] = {}
    for h in range(1, 13):
        feasible[h] = sum(1 for origin in all_months
                          if origin + h in dense and sum(1 for m in dense if m <= origin) >= MIN_TRAIN_BINS)
    ok = [h for h, n in feasible.items() if n >= MIN_ORIGINS]
    return (max(ok) if ok else 0), feasible


def rolling_origin(frame: pd.DataFrame, anchor: pd.Timestamp, value: str = "macro"):
    """Pseudo-out-of-time errors of the predeclared forms at the chosen horizon."""
    bins = binned_frontier(frame, anchor, value)
    h, feasible = choose_backtest_horizon(bins)
    if h == 0:
        return 0, pd.DataFrame(), feasible
    dense = bins.loc[~bins["sparse"]].set_index("month")
    rows = []
    for origin in pd.period_range(bins["month"].min(), bins["month"].max(), freq="M"):
        target = origin + h
        if target not in dense.index or sum(1 for m in dense.index if m <= origin) < MIN_TRAIN_BINS:
            continue
        train = frame[frame["month"] <= origin]
        t_origin = years_between(origin.end_time.normalize(), anchor)
        t_target = float(dense.loc[target, "t_mid"])
        q = quantile_split(train, value)
        last_dense = dense.loc[[m for m in dense.index if m <= origin]].iloc[-1]
        level_origin = q["level0"] + q["g_time"] * t_origin
        forecasts = {
            "persistence": float(last_dense["p90"]),
            "time_only": q["level0"] + q["g_time"] * t_target,
            "additive_quantile": level_origin + q["decomposed_total"] * (t_target - t_origin),
        }
        observed = float(dense.loc[target, "p90"])
        for method, f in forecasts.items():
            rows.append({"origin": origin, "target": target, "method": method, "forecast": f,
                         "observed": observed, "error": f - observed, "train_n": int(len(train))})
    return h, pd.DataFrame(rows), feasible


__all__ = [
    "ForecastError", "Z90", "years_between", "horizon_dates", "check_anchor", "binned_frontier",
    "frontier_flags", "exact_split", "quantile_split", "split_eligible", "components", "rate", "project", "band_index",
    "band_label", "matched_scale", "scale_spec_residual", "bin_noise_sd", "forecast_table",
    "choose_backtest_horizon", "rolling_origin",
]
