"""Open-model eligibility fields for the Q4 frontier population.

T-011 needs a defensible frontier population, but T-009 must not yet pick it:
it defines the *fields and rules* that distinguish usable open models and
reports counts under clearly named criteria. The rules here are conservative
and encode ``unknown`` rather than guessing:

* open weights requires a positive signal — a permissive Hub licence, an
  Epoch ``Open model weights? == Yes``, or unrestricted weight access — never
  the mere fact of appearing on a public leaderboard;
* parameter count, evaluation score and a date are each required separately
  and reported as their own coverage number, so downstream can choose which
  combination of fields its population actually needs.

The fields are computed on the panel rows; the choice of a *primary scientific
population* remains a T-011 modelling decision.
"""

from __future__ import annotations

import re
from typing import Dict

import pandas as pd

from src.panel.config import (
    OPEN_ACCESSIBILITY,
    OPEN_LICENSES,
    TEST_MODEL_PATTERNS,
)

TEST_RE = re.compile("|".join(TEST_MODEL_PATTERNS), re.IGNORECASE)


def license_open(license_value) -> bool:
    """True when the Hub licence is in the permissive/open set."""
    if not isinstance(license_value, str):
        return False
    return license_value.strip().lower() in OPEN_LICENSES


def accessibility_open(value) -> bool:
    """True when C4 records unrestricted open weights."""
    return isinstance(value, str) and value.strip() in OPEN_ACCESSIBILITY


def is_test_model(model: str) -> bool:
    """True when the model name matches a test/spam pattern."""
    return bool(TEST_RE.search(str(model)))


def eligibility_fields(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the eligibility columns to a copy of the panel.

    Columns added (booleans, True/False/``unknown`` where the data cannot
    decide): ``open_weights``, ``params_known``, ``score_available``,
    ``date_available``, ``compute_available``, ``test_flag``. ``open_weights``
    is ``unknown`` (a string) when no source speaks either way, so a model
    with no licence and no Epoch row is not silently declared closed.
    """
    out = frame.copy()

    def open_row(row) -> str:
        # A positive signal for open weights: a permissive Hub licence, an Epoch
        # "Open model weights? == Yes" (C2 pre-matched or C4 raw), or unrestricted
        # weight access. Any one positive signal suffices.
        signals = []
        if license_open(row.get("hub_license")):
            signals.append("license")
        if isinstance(row.get("open_weights_epoch"), str) and row["open_weights_epoch"].strip().lower() == "yes":
            signals.append("epoch")
        if isinstance(row.get("c4_open_weights"), str) and row["c4_open_weights"].strip().lower() == "yes":
            signals.append("epoch")
        if accessibility_open(row.get("c4_accessibility")):
            signals.append("accessibility")
        if signals:
            return "yes"
        # A negative signal exists only if the data actually speaks: a licence
        # is present but not permissive, or Epoch says "No".
        has_license = isinstance(row.get("hub_license"), str) and row["hub_license"].strip() != ""
        epoch_no = (
            (isinstance(row.get("open_weights_epoch"), str) and row["open_weights_epoch"].strip().lower() == "no")
            or (isinstance(row.get("c4_open_weights"), str) and row["c4_open_weights"].strip().lower() == "no")
        )
        if has_license or epoch_no or isinstance(row.get("c4_accessibility"), str):
            return "no"
        return "unknown"

    out["open_weights"] = out.apply(open_row, axis=1)
    out["params_known"] = out["params_b"].notna() & (out["params_b"] > 0)
    out["score_available"] = out[[
        "score_ifeval", "score_bbh", "score_math_lvl5",
        "score_gpqa", "score_musr", "score_mmlu_pro",
    ]].notna().all(axis=1)
    out["date_available"] = out["analysis_date"].notna() if "analysis_date" in out else pd.Series(False, index=out.index)
    out["compute_available"] = out["c4_compute_flop"].notna() if "c4_compute_flop" in out else pd.Series(False, index=out.index)
    out["test_flag"] = out["model"].apply(is_test_model)
    return out


def eligibility_counts(frame: pd.DataFrame) -> Dict[str, object]:
    """Count models under each named eligibility criterion."""
    n = len(frame)
    by_decision = {}
    for decision in ("yes", "no", "unknown"):
        by_decision[decision] = int((frame["open_weights"] == decision).sum())
    return {
        "total_rows": n,
        "unique_models": int(frame["model"].nunique()),
        "open_weights": by_decision,
        "params_known": int(frame["params_known"].sum()),
        "score_available": int(frame["score_available"].sum()),
        "date_available": int(frame["date_available"].sum()),
        "compute_available": int(frame["compute_available"].sum()),
        "test_flag": int(frame["test_flag"].sum()),
        "open_and_params_and_score_and_date": int(
            ((frame["open_weights"] == "yes") & frame["params_known"]
             & frame["score_available"] & frame["date_available"]).sum()
        ),
    }
