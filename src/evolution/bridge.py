"""IF4: the loss-to-benchmark bridge, built only from anchors that genuinely link.

An anchor is a C5/C6 row pairing a model's cross-entropy loss with its
leaderboard scores. The construction is deliberately conservative:

* **Identity.** An anchor links to the T-009 panel by the exact model path,
  then by the T-009 normalised key if that key is unique on both sides, then by
  an explicit (empty) alias map. Nothing else links; there is no fuzzy match,
  and two anchors may never claim one panel model.
* **Score record.** The benchmark value used is the accepted T-009 panel score.
  Where C1 carries more than one evaluation row for the same model path with
  different score vectors, the anchor is flagged rather than silently resolved.
* **Strata.** Comparability classes come from the organizer's own metadata (the
  comparability label, the loss source and the table a row appears in), fixed
  before any fit. Only the primary stratum is fitted; the others are carried as
  counts and as a diagnostic, never pooled into the release.
* **Forms.** A small set of monotone forms, declared in ``config`` before any
  error was compared, is scored by leave-one-anchor-out error and chosen by a
  fixed one-standard-error rule.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from src import interfaces as ifc
from src.evolution.config import (
    BRIDGE_ALIASES,
    BRIDGE_FORMS,
    BRIDGE_N_PARAMS,
    BRIDGE_PRIMARY_STRATUM,
    BRIDGE_STRATA,
)
from src.evolution.receipts import C_FILES, IF3Receipt, read_input
from src.panel.matching import normalize, split_org_name
from src.paths import ATT_C
from src.scaling.law import PUBLISHED_CHINCHILLA
from src.scaling.units import predict_natural

SCORE_PAIRS: Dict[str, str] = {
    "LB_IFEval": "score_ifeval", "LB_BBH": "score_bbh", "LB_MATH": "score_math_lvl5",
    "LB_GPQA": "score_gpqa", "LB_MUSR": "score_musr", "LB_MMLU_PRO": "score_mmlu_pro",
    "LB_Average": "average",
}
SCORE_TOL = 1.0e-9
SLOPE_BOUNDARY = 1.0e-9

SCORE_SCALE = ("Open LLM Leaderboard v2 macro score: equal-weight mean of the six C1 summary "
               "dimensions (IFEval, BBH, MATH Lvl 5, GPQA, MUSR, MMLU-PRO), each baseline-rescaled "
               "max(0,(raw-baseline)/(1-baseline))*100; range 0-100; higher is better; C1 column Average")


class BridgeError(ValueError):
    """The bridge data or an anchor violates the construction rules."""


class OutsideBridgeSupport(ValueError):
    """The bridge was asked to translate a loss outside the anchors' loss range."""


# ---------------------------------------------------------------------------
# Anchors and strata
# ---------------------------------------------------------------------------

def load_tables() -> Tuple[pd.DataFrame, pd.DataFrame]:
    c5 = pd.read_csv(read_input(ATT_C / C_FILES["C5"]))
    c6 = pd.read_csv(read_input(ATT_C / C_FILES["C6"]))
    return c5, c6


def loss_kind(source: str) -> str:
    """The kind of loss a source reports, read from the organizer's own source text."""
    text = str(source).lower()
    if "attachment b" in text:
        return "Attachment-B training log (final checkpoint)"
    if "validation loss" in text:
        return "report: validation loss"
    if "training loss" in text:
        return "report: training loss"
    if "final loss" in text:
        return "report: final loss"
    return "report: loss kind unspecified"


def stratify(c5: pd.DataFrame, c6: pd.DataFrame) -> pd.DataFrame:
    """Union of C5 and C6 with a provenance stratum per row.

    C6 must contain every C5 row with identical values; otherwise the two tables
    disagree about the same anchor and nothing is built.
    """
    if c5["Model"].duplicated().any() or c6["Model"].duplicated().any():
        raise BridgeError("duplicate model rows in C5 or C6")
    if list(c5.columns) != list(c6.columns):
        raise BridgeError("C5 and C6 schemas differ")
    shared = c5.merge(c6, on="Model", how="left", suffixes=("", "_c6"), indicator=True)
    if (shared["_merge"] != "both").any():
        raise BridgeError("a C5 row is missing from C6")
    for col in c5.columns:
        if col == "Model":
            continue
        a, b = shared[col], shared[col + "_c6"]
        if not bool(((a == b) | (a.isna() & b.isna())).all()):
            raise BridgeError("C5 and C6 disagree on " + col)
    rows = c6.copy()
    rows["in_c5"] = rows["Model"].isin(set(c5["Model"]))
    strata = []
    for _, r in rows.iterrows():
        label = str(r["Loss_Comparability"])
        if not r["in_c5"]:
            strata.append("S3_expanded_derivative_variants")
        elif label.startswith("High") and "attachment b" in str(r["Loss_Source"]).lower():
            strata.append("S1_same_family_same_validation")
        elif label.startswith("Medium"):
            strata.append("S2_cross_family_literature")
        else:
            raise BridgeError("unclassifiable bridge row " + str(r["Model"]) + ": " + label)
    rows["stratum"] = strata
    rows["loss_kind"] = rows["Loss_Source"].map(loss_kind)
    rows["org"] = rows["Model"].map(lambda m: split_org_name(m)[0])
    if set(rows["stratum"]) - set(BRIDGE_STRATA):
        raise BridgeError("undeclared stratum")
    return rows


def match_anchors(rows: pd.DataFrame, panel: pd.DataFrame, c1: pd.DataFrame) -> pd.DataFrame:
    """Deterministic identity ladder plus a score-record audit against C1."""
    panel_models = list(panel["model"])
    exact = set(panel_models)
    norm_counts: Dict[str, List[str]] = {}
    for m in panel_models:
        norm_counts.setdefault(normalize(m), []).append(m)
    anchor_norm_counts = rows["Model"].map(normalize).value_counts().to_dict()
    tiers, targets = [], []
    for model in rows["Model"]:
        key = normalize(model)
        if model in exact:
            tiers.append("exact"); targets.append(model)
        elif len(norm_counts.get(key, [])) == 1 and anchor_norm_counts.get(key, 0) == 1:
            tiers.append("normalized"); targets.append(norm_counts[key][0])
        elif model in BRIDGE_ALIASES and BRIDGE_ALIASES[model] in exact:
            tiers.append("alias"); targets.append(BRIDGE_ALIASES[model])
        else:
            tiers.append("unmatched"); targets.append(None)
    out = rows.copy()
    out["identity_tier"] = tiers
    out["panel_model"] = targets
    linked = out["panel_model"].dropna()
    if linked.duplicated().any():
        raise BridgeError("two anchors claim the same panel model: " + repr(sorted(linked[linked.duplicated()])))

    by_model = panel.set_index("model")
    status, macro, stratum_t009 = [], [], []
    for _, r in out.iterrows():
        if pd.isna(r["panel_model"]):
            status.append("unmatched"); macro.append(np.nan); stratum_t009.append(None)
            continue
        prow = by_model.loc[r["panel_model"]]
        macro.append(float(prow["average"]))
        stratum_t009.append(prow["stratum"])
        panel_equal = all(abs(float(r[a]) - float(prow[b])) <= SCORE_TOL for a, b in SCORE_PAIRS.items())
        c1_rows = c1[c1["model"] == r["panel_model"]]
        distinct_vectors = c1_rows[list(SCORE_PAIRS.values())].drop_duplicates().shape[0]
        if panel_equal and distinct_vectors <= 1:
            status.append("panel_match")
        elif distinct_vectors > 1:
            matches_other = any(all(abs(float(r[a]) - float(cr[b])) <= SCORE_TOL for a, b in SCORE_PAIRS.items())
                                for _, cr in c1_rows.iterrows())
            status.append("duplicate_evaluation" + ("" if matches_other else "_unmatched"))
        else:
            status.append("score_mismatch")
    out["score_record"] = status
    out["panel_macro"] = macro
    out["t009_stratum"] = stratum_t009
    return out


def loss_reuse(rows: pd.DataFrame) -> pd.Series:
    """True where another model's row carries the identical loss and parameter count."""
    key = rows["Val_Loss"].astype(str) + "|" + rows["N_params_B"].astype(str)
    return key.map(key.value_counts()) > 1


def s1_fingerprint(rows: pd.DataFrame, if3: IF3Receipt) -> pd.DataFrame:
    """Primary-stratum losses against the published Chinchilla law and the classic IF3."""
    s1 = rows[rows["stratum"] == BRIDGE_PRIMARY_STRATUM]
    n = s1["N_params_B"].to_numpy(float) * 1e9
    d = s1["D_tokens_B"].to_numpy(float) * 1e9
    published = predict_natural(PUBLISHED_CHINCHILLA, n, d)
    inside = if3.inside(n, d)
    fitted = if3.predict(n, d, allow_extrapolation=True)
    return pd.DataFrame({
        "model": s1["Model"].to_numpy(), "n_raw": n, "d_raw": d, "val_loss": s1["Val_Loss"].to_numpy(float),
        "published_law": published, "classic_if3": fitted, "inside_if3_box": inside,
    })


# ---------------------------------------------------------------------------
# Candidate forms
# ---------------------------------------------------------------------------

def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_form(form: str, loss: np.ndarray, score: np.ndarray) -> Tuple[Dict[str, float], bool]:
    """Least-squares fit in score space; returns (params, slope_at_boundary)."""
    loss = np.asarray(loss, float)
    score = np.asarray(score, float)
    if form == "constant":
        return {"c": float(score.mean())}, False
    if form == "linear":
        slope, intercept = np.polyfit(loss, score, 1)
        if slope > 0:
            return {"a": float(score.mean()), "b": 0.0}, True
        return {"a": float(intercept), "b": float(slope)}, bool(abs(slope) <= SLOPE_BOUNDARY)
    if form == "logit_linear":
        b0, a0 = np.polyfit(loss, _logit(score / 100.0), 1)
        b0 = min(b0, -1e-3)

        def resid(theta):
            a, b = theta
            return 100.0 / (1.0 + np.exp(-(a + b * loss))) - score

        sol = least_squares(resid, x0=[a0, b0], bounds=([-np.inf, -np.inf], [np.inf, 0.0]), method="trf")
        a, b = (float(v) for v in sol.x)
        return {"a": a, "b": b}, bool(abs(b) <= 1e-6)
    raise BridgeError("undeclared bridge form " + form)


def predict_form(form: str, params: Dict[str, float], loss) -> np.ndarray:
    loss = np.asarray(loss, float)
    if form == "constant":
        return np.full_like(loss, params["c"], dtype=float)
    if form == "linear":
        return params["a"] + params["b"] * loss
    if form == "logit_linear":
        return 100.0 / (1.0 + np.exp(-(params["a"] + params["b"] * loss)))
    raise BridgeError("undeclared bridge form " + form)


@dataclass
class FormResult:
    form: str
    params: Dict[str, float]
    at_boundary: bool
    fold_pred: np.ndarray
    fold_params: List[Dict[str, float]]
    fold_boundary: List[bool]
    errors: np.ndarray

    @property
    def rmse(self) -> float:
        return float(np.sqrt(np.mean(self.errors ** 2)))

    @property
    def rmse_se(self) -> float:
        sq = self.errors ** 2
        if self.rmse == 0:
            return 0.0
        return float(np.std(sq, ddof=1) / math.sqrt(len(sq)) / (2.0 * self.rmse))

    @property
    def stable(self) -> bool:
        if self.form == "constant":
            return True
        slopes = [p["b"] for p in self.fold_params]
        return (not self.at_boundary and not any(self.fold_boundary)
                and all(s < 0 for s in slopes))


def leave_one_out(form: str, loss: np.ndarray, score: np.ndarray) -> FormResult:
    params, boundary = fit_form(form, loss, score)
    preds, fparams, fbound = [], [], []
    for i in range(len(loss)):
        keep = np.arange(len(loss)) != i
        p, b = fit_form(form, loss[keep], score[keep])
        preds.append(float(predict_form(form, p, loss[i:i + 1])[0]))
        fparams.append(p)
        fbound.append(b)
    preds = np.asarray(preds)
    return FormResult(form, params, boundary, preds, fparams, fbound, preds - score)


def select(results: List[FormResult]) -> Tuple[FormResult, Dict[str, object]]:
    """The predeclared rule: eligible forms, then fewest parameters within one SE of the best."""
    eligible = [r for r in results if r.stable]
    if not eligible:
        raise BridgeError("no eligible bridge form")
    best = min(eligible, key=lambda r: r.rmse)
    threshold = best.rmse + best.rmse_se
    within = [r for r in eligible if r.rmse <= threshold + 1e-12]
    order = {f: i for i, f in enumerate(BRIDGE_FORMS)}
    chosen = min(within, key=lambda r: (BRIDGE_N_PARAMS[r.form], order[r.form]))
    return chosen, {"best_form": best.form, "best_rmse": best.rmse, "one_se_threshold": threshold,
                    "eligible": [r.form for r in eligible], "within_one_se": [r.form for r in within]}


def leave_one_org_out(form: str, frame: pd.DataFrame) -> Dict[str, float]:
    """Family (organisation) block-out error: a diagnostic for strata whose families repeat."""
    errs = []
    for org in sorted(frame["org"].unique()):
        test = frame["org"] == org
        if test.all():
            continue
        p, _ = fit_form(form, frame.loc[~test, "Val_Loss"].to_numpy(float), frame.loc[~test, "panel_macro"].to_numpy(float))
        pred = predict_form(form, p, frame.loc[test, "Val_Loss"].to_numpy(float))
        errs.extend(list(pred - frame.loc[test, "panel_macro"].to_numpy(float)))
    e = np.asarray(errs)
    return {"n": int(len(e)), "rmse": float(np.sqrt(np.mean(e ** 2))), "mae": float(np.mean(np.abs(e)))}


# ---------------------------------------------------------------------------
# IF4
# ---------------------------------------------------------------------------

def build_if4(chosen: FormResult, primary: pd.DataFrame, strata_counts: Dict[str, int],
              notes: str) -> ifc.IF4LossBenchmarkBridge:
    loss = primary["Val_Loss"].to_numpy(float)
    e = chosen.errors
    form_text = {
        "constant": "score = c",
        "linear": "score = a + b*loss, b <= 0",
        "logit_linear": "score = 100 / (1 + exp(-(a + b*loss))), b <= 0",
    }[chosen.form]
    params = dict(chosen.params)
    params["loss_support_min"] = float(loss.min())
    params["loss_support_max"] = float(loss.max())
    obj = ifc.IF4LossBenchmarkBridge(
        schema_version=ifc.SCHEMA_VERSION,
        strata=dict(strata_counts),
        primary_stratum=BRIDGE_PRIMARY_STRATUM,
        form=form_text + "; defined only for loss in [loss_support_min, loss_support_max] "
             "(params), on the Attachment-B / Pythia validation-loss scale; evaluation outside "
             "that interval is not supported",
        params=params,
        prediction_error={
            "loao_rmse": chosen.rmse,
            "loao_mae": float(np.mean(np.abs(e))),
            "loao_max_abs_error": float(np.max(np.abs(e))),
            "loao_mean_error": float(np.mean(e)),
            "loao_rmse_se": chosen.rmse_se,
            "predictive_sd": chosen.rmse,
            "n_folds": float(len(e)),
        },
        n_anchor_models=int(len(primary)),
        score_scale=SCORE_SCALE,
        provenance=ifc.Provenance(
            trust="observed",
            sources=[
                "C5 loss_benchmark_bridge.csv: organizer-labelled High rows (loss column)",
                "C1 leaderboard_cleaned.csv via the accepted T-009 panel (benchmark scores)",
            ],
            notes=notes,
        ),
    )
    obj.validate()
    return obj


def bridge_predict(if4: Dict[str, object], loss, loss_sd=0.0) -> Tuple[np.ndarray, np.ndarray]:
    """Translate loss to score with the bridge's own prediction error always included.

    Returns (mean, sd). ``sd`` is the root sum of squares of the bridge's
    out-of-fold predictive SD and the propagated loss uncertainty; the bridge
    term can never be dropped. A loss outside the anchors' support is refused.
    """
    params = dict(if4["params"])  # type: ignore[arg-type]
    lo, hi = params.pop("loss_support_min"), params.pop("loss_support_max")
    loss = np.atleast_1d(np.asarray(loss, float))
    if np.any(loss < lo) or np.any(loss > hi):
        raise OutsideBridgeSupport("loss outside the bridge support [" + repr(lo) + ", " + repr(hi) + "]")
    form = str(if4["form"]).split(";")[0]
    kind = {"score = c": "constant", "score = a + b*loss, b <= 0": "linear",
            "score = 100 / (1 + exp(-(a + b*loss))), b <= 0": "logit_linear"}[form]
    mean = predict_form(kind, params, loss)
    bridge_sd = float(if4["prediction_error"]["predictive_sd"])  # type: ignore[index]
    if not bridge_sd > 0:
        raise BridgeError("bridge predictive error missing or zero; a bridge-based band would omit it")
    h = 1e-6
    slope = (predict_form(kind, params, loss + h) - predict_form(kind, params, loss - h)) / (2 * h)
    sd = np.sqrt(bridge_sd ** 2 + (slope * np.asarray(loss_sd, float)) ** 2)
    return mean, sd


__all__ = [
    "SCORE_SCALE", "BridgeError", "OutsideBridgeSupport", "load_tables", "loss_kind", "stratify",
    "match_anchors", "loss_reuse", "s1_fingerprint", "fit_form", "predict_form", "FormResult",
    "leave_one_out", "select", "leave_one_org_out", "build_if4", "bridge_predict",
]
