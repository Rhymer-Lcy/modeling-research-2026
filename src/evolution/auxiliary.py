"""C3 as an auxiliary source: audited, never folded into the panel.

T-009 established that C3 has no unique evaluation key (its repeated models
carry distinct score vectors), so it cannot supply panel observations. The
problem statement nevertheless requires C3 to be used. It is used here for what
it can support: which clock its ``Year`` field follows for the leaderboard
rows, and whether its historical (papers / reports) rows sit on the leaderboard
v2 scale at all.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.evolution.receipts import C_FILES, read_input
from src.paths import ATT_C

C3_DIMS = ["IFEval", "BBH", "MATH_Lvl5", "GPQA", "MUSR", "MMLU_PRO"]


def audit(panel: pd.DataFrame) -> Dict[str, object]:
    c3 = pd.read_csv(read_input(ATT_C / C_FILES["C3"]))
    lb = c3[c3["Source"] == "Open LLM Leaderboard"]
    hist = c3[c3["Source"] != "Open LLM Leaderboard"]
    p = panel.set_index("model")
    shared = lb[lb["Model"].isin(p.index)]
    sub_year = pd.to_datetime(p.loc[shared["Model"], "submission_date"]).dt.year.to_numpy()
    pub = pd.to_datetime(p.loc[shared["Model"], "pub_date"])
    pub_year = pub.dt.year.to_numpy()
    has_pub = pub.notna().to_numpy()
    year = shared["Year"].to_numpy()
    both = has_pub & ~np.isnan(sub_year.astype(float))
    gap = (hist["Average"] - hist[C3_DIMS].mean(axis=1)).abs()
    return {
        "rows": int(len(c3)),
        "leaderboard_rows": int(len(lb)),
        "historical_rows": int(len(hist)),
        "historical_years": (int(hist["Year"].min()), int(hist["Year"].max())),
        "leaderboard_rows_shared_with_panel": int(len(shared)),
        "year_equals_submission_year": float(np.mean(year[~np.isnan(sub_year.astype(float))]
                                                   == sub_year[~np.isnan(sub_year.astype(float))])),
        "rows_with_pub_and_submission": int(both.sum()),
        "year_equals_pub_year_where_they_differ": int(((year == pub_year) & (sub_year != pub_year) & both).sum()),
        "year_equals_sub_year_where_they_differ": int(((year == sub_year) & (sub_year != pub_year) & both).sum()),
        "duplicate_model_rows": int(c3["Model"].duplicated().sum()),
        "historical_models_in_panel": int(hist["Model"].isin(p.index).sum()),
        "historical_average_minus_mean6_max_abs": float(gap.max()),
        "historical_rows_average_not_mean6": int((gap > 1.0).sum()),
        "historical_rows_with_zero_filled_dimension": int((hist[C3_DIMS] == 0).any(axis=1).sum()),
    }


__all__ = ["audit"]
