"""Score scale, direction and the macro aggregate.

Before any aggregate is formed, every C1 summary dimension's scale and direction
is checked against evidence rather than inferred from a 0-100 range:

* the organizer's own aggregate header carries the up-arrow ``⬆️`` marking
  higher as better, and the aggregate equals the equal-weight mean of the six
  dimensions, so each enters it with a positive sign;
* T-009 reproduced five of the six published dimensions from raw per-task
  accuracies with the monotone increasing rescale
  ``max(0, (raw - baseline) / (1 - baseline)) * 100``; MATH Lvl 5 is used only as
  its C1 summary value, and its C8 child records stay quarantined;
* every dimension correlates positively with the mean of the other five.

Only if all six pass is the equal-weight macro score used, and it is always
reported next to the dimension-level results.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd
from scipy.stats import spearmanr

from src.evolution.receipts import C_FILES, read_input
from src.panel.detail import QUARANTINED_DIMENSIONS, RECONCILED_DIMENSIONS
from src.paths import ATT_C

#: Panel column -> the organizer's dimension label.
DIMENSIONS: Dict[str, str] = {
    "score_ifeval": "IFEval",
    "score_bbh": "BBH",
    "score_math_lvl5": "MATH Lvl 5",
    "score_gpqa": "GPQA",
    "score_musr": "MUSR",
    "score_mmlu_pro": "MMLU-PRO",
}

#: Declared direction of every dimension; the audit must confirm each one.
DIRECTIONS: Dict[str, str] = {col: "higher_better" for col in DIMENSIONS}


class ScoreScaleError(ValueError):
    """The dimensions are not on one higher-is-better scale; no aggregate may be formed."""


def c1_average_header() -> str:
    with open(read_input(ATT_C / C_FILES["C1"]), encoding="utf-8") as handle:
        header = handle.readline()
    found = [c for c in header.strip().split(",") if c.startswith("Average")]
    if len(found) != 1:
        raise ScoreScaleError("C1 must carry exactly one Average column")
    return found[0]


def audit(panel: pd.DataFrame) -> pd.DataFrame:
    """One row per dimension with the evidence for its scale and direction."""
    header = c1_average_header()
    arrow_up = "⬆" in header
    mean6 = panel[list(DIMENSIONS)].mean(axis=1)
    avg_gap = float((panel["average"] - mean6).abs().max())
    rows: List[Dict[str, object]] = []
    for col, label in DIMENSIONS.items():
        others = panel[[c for c in DIMENSIONS if c != col]].mean(axis=1)
        rho = float(spearmanr(panel[col], others).statistic)
        if label in RECONCILED_DIMENSIONS:
            status = "reconciled to C8 raw accuracies (T-009)"
        elif label in QUARANTINED_DIMENSIONS:
            status = "C1 summary only; C8 children quarantined (T-009)"
        else:
            status = "unknown"
        ok = (bool(panel[col].min() >= 0.0) and bool(panel[col].max() <= 100.0)
              and arrow_up and avg_gap < 1e-9 and rho > 0.0 and status != "unknown")
        rows.append({
            "column": col, "dimension": label, "min": float(panel[col].min()),
            "max": float(panel[col].max()), "t009_status": status,
            "spearman_vs_other_five": rho, "declared_direction": DIRECTIONS[col],
            "verified": ok,
        })
    out = pd.DataFrame(rows)
    out.attrs["average_header_up_arrow"] = arrow_up
    out.attrs["average_minus_mean6_max_abs"] = avg_gap
    return out


def macro_score(frame: pd.DataFrame, directions: Dict[str, str] = DIRECTIONS,
                audit_table: pd.DataFrame | None = None) -> pd.Series:
    """Equal-weight macro score; refuses unless every dimension is verified higher-is-better."""
    bad = {k: v for k, v in directions.items() if v != "higher_better"}
    if bad or set(directions) != set(DIMENSIONS):
        raise ScoreScaleError("macro score refused: dimensions not all declared higher-is-better: " + repr(bad))
    if audit_table is not None and not bool(audit_table["verified"].all()):
        raise ScoreScaleError("macro score refused: scale audit failed for "
                              + repr(audit_table.loc[~audit_table["verified"], "dimension"].tolist()))
    return frame[list(DIMENSIONS)].mean(axis=1)


__all__ = ["DIMENSIONS", "DIRECTIONS", "ScoreScaleError", "audit", "macro_score", "c1_average_header"]
