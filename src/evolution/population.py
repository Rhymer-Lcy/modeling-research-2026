"""The T-011 analysis population, frozen from accepted T-009 fields.

The rules and their order were fixed before any outcome or time model was
fitted, from provenance, comparability, completeness, model type and date
availability. Each rule is a named predicate on T-009 columns; the population is
the conjunction, and a ledger records how many rows every rule removes, both in
sequence and on its own. The canonical time field is T-009's ``analysis_date``
with its ``date_source`` retained; a fallback submission date is never renamed a
publication date.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd

from src.evolution.config import (
    DATE_CONSISTENCY_TOLERANCE_DAYS,
    DAYS_PER_YEAR,
    GROUPS,
    OPEN_WEIGHTS_REQUIRED,
    PRIMARY_STRATA,
)


class PopulationError(ValueError):
    """A population violates the frozen definition or the panel's identity."""


def date_lag_days(panel: pd.DataFrame) -> pd.Series:
    """Primary (publication) date minus the row's own leaderboard submission date."""
    sub = pd.to_datetime(panel["submission_date"], errors="coerce")
    ana = pd.to_datetime(panel["analysis_date"], errors="coerce")
    return (ana - sub).dt.days


def date_consistent(panel: pd.DataFrame) -> pd.Series:
    """False only for a primary-dated row published long after it was evaluated."""
    lag = date_lag_days(panel)
    primary = panel["date_confidence"] == "primary"
    return ~(primary & lag.notna() & (lag > DATE_CONSISTENCY_TOLERANCE_DAYS))


Rule = Tuple[str, str, Callable[[pd.DataFrame], pd.Series]]


def _rules(strata: Tuple[str, ...] = PRIMARY_STRATA, open_rule: bool = True,
           consistency_rule: bool = True) -> List[Rule]:
    rules: List[Rule] = [
        ("R1_date", "analysis date available (a time-dependent analysis needs one)",
         lambda p: p["date_available"].astype(bool)),
        ("R2_params", "parameter count known and positive (the scale variable)",
         lambda p: p["params_known"].astype(bool)),
        ("R3_scores", "all six summary scores present (the macro score needs all six)",
         lambda p: p["score_available"].astype(bool)),
        ("R4_not_test", "not flagged by T-009 as a test / spam upload",
         lambda p: ~p["test_flag"].astype(bool)),
        ("R5_stratum", "T-009 stratum in " + "/".join(strata),
         lambda p: p["stratum"].isin(strata)),
    ]
    if open_rule:
        rules.append(("R6_open", "open weights on a positive T-009 signal",
                      lambda p: p["open_weights"] == OPEN_WEIGHTS_REQUIRED))
    if consistency_rule:
        rules.append(("R7_date_consistent",
                      "publication date not more than " + str(DATE_CONSISTENCY_TOLERANCE_DAYS)
                      + " days after the row's own submission", date_consistent))
    return rules


@dataclass
class Population:
    name: str
    frame: pd.DataFrame
    ledger: pd.DataFrame
    anchor: pd.Timestamp


def _ledger(panel: pd.DataFrame, rules: List[Rule]) -> Tuple[pd.Series, pd.DataFrame]:
    keep = pd.Series(True, index=panel.index)
    rows = []
    for code, text, fn in rules:
        mask = fn(panel).astype(bool)
        removed = int((keep & ~mask).sum())
        rows.append({"rule": code, "criterion": text, "fails_alone": int((~mask).sum()),
                     "removed_in_sequence": removed})
        keep &= mask
    return keep, pd.DataFrame(rows)


def group_of(stratum: str, groups: Dict[str, Tuple[str, ...]] = GROUPS) -> str:
    for name, members in groups.items():
        if stratum in members:
            return name
    return "none"


def annotate(frame: pd.DataFrame, anchor: pd.Timestamp,
             groups: Dict[str, Tuple[str, ...]] = GROUPS) -> pd.DataFrame:
    out = frame.copy()
    out["analysis_date"] = pd.to_datetime(out["analysis_date"])
    if out["analysis_date"].isna().any():
        raise PopulationError("a time-dependent population may not contain undated rows")
    out["group"] = out["stratum"].map(lambda s: group_of(s, groups))
    out["n_raw"] = out["params_b"].astype(float) * 1.0e9
    out["log10_n"] = np.log10(out["n_raw"])
    out["macro"] = out["average"].astype(float)
    out["t_years"] = (out["analysis_date"] - anchor).dt.days / DAYS_PER_YEAR
    out["month"] = out["analysis_date"].dt.to_period("M")
    return out


def build(panel: pd.DataFrame, name: str = "primary", *, strata: Tuple[str, ...] = PRIMARY_STRATA,
          open_rule: bool = True, consistency_rule: bool = True, date_confidence: str | None = None,
          groups: Dict[str, Tuple[str, ...]] = GROUPS, anchor: pd.Timestamp | None = None) -> Population:
    """Apply the frozen rules. ``anchor`` defaults to the population's own last date."""
    rules = _rules(strata, open_rule, consistency_rule)
    keep, ledger = _ledger(panel, rules)
    if date_confidence is not None:
        extra = panel["date_confidence"] == date_confidence
        ledger = pd.concat([ledger, pd.DataFrame([{
            "rule": "S_date_" + date_confidence, "criterion": "date_confidence == " + date_confidence,
            "fails_alone": int((~extra).sum()), "removed_in_sequence": int((keep & ~extra).sum())}])],
            ignore_index=True)
        keep &= extra
    frame = panel.loc[keep].copy()
    if frame.empty:
        raise PopulationError("population " + name + " is empty")
    last = pd.to_datetime(frame["analysis_date"]).max()
    out = annotate(frame, anchor if anchor is not None else last, groups)
    validate(out, panel)
    return Population(name=name, frame=out, ledger=ledger, anchor=anchor if anchor is not None else last)


def validate(frame: pd.DataFrame, panel: pd.DataFrame) -> None:
    """Every row must be one T-009 panel model, once; no undated rows."""
    if frame["model"].duplicated().any():
        raise PopulationError("population rows are not unique by model")
    unknown = set(frame["model"]) - set(panel["model"])
    if unknown:
        raise PopulationError(str(len(unknown)) + " population row(s) are not T-009 panel models "
                              "(C3 timeseries rows can never become panel observations)")
    if frame["analysis_date"].isna().any():
        raise PopulationError("undated rows present")


#: Predeclared alternatives, as keyword arguments to :func:`build`.
ALTERNATIVES: Dict[str, Dict[str, object]] = {
    "primary": {},
    "publication_date_only": {"date_confidence": "primary"},
    "fallback_date_only": {"date_confidence": "fallback"},
    "with_merges": {"strata": ("A", "B", "C", "D"), "groups": {"A": ("A",), "BC": ("B", "C", "D")}},
    "open_weights_relaxed": {"open_rule": False},
    "date_inconsistent_kept": {"consistency_rule": False},
}


__all__ = ["PopulationError", "Population", "build", "annotate", "validate", "date_lag_days",
           "date_consistent", "group_of", "ALTERNATIVES"]
