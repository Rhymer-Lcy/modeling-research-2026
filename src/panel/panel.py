"""Assemble the canonical Q4 panel from the organizer's C tables.

The panel is the single de-duplicated table that downstream Q4 analysis reads:
one row per leaderboard model, carrying its six published scores, its
publication/submission dates, its model-type stratum, its open-weights
eligibility fields, and — where the deterministic C4 linkage succeeds — its
Epoch AI metadata (parameters, training compute, accessibility).

The assembly is a sequence of documented transforms, each in its own module so
a downstream consumer can inspect every step:

* :func:`src.panel.sources.load_c2` — the leaderboard plus three Epoch columns;
* :func:`src.panel.c4_link.link_c4` — deterministic C4 metadata linkage;
* :func:`src.panel.strata.classify` — model-type strata A-E;
* :func:`src.panel.dates.assign_dates` — primary/fallback date;
* :func:`src.panel.eligibility.eligibility_fields` — open-model eligibility.

The base is C2, not C1: C2 is C1 plus the three Epoch AI columns and has the same
rows in the same order, so it is a strict superset (see ``relationship`` in
``sources``). C3's historical timeseries rows are a different, mixed-provenance
sample and are reported separately rather than folded into the leaderboard panel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.panel.c4_link import link_c4
from src.panel.dates import assign_dates
from src.panel.eligibility import eligibility_fields
from src.panel.sources import load_c2, load_c4
from src.panel.strata import classify
from src.paths import PROBLEM_F_DERIVED, ensure

#: The key a row is de-duplicated on: a leaderboard model path.
MODEL_KEY = "model"


def build_panel() -> pd.DataFrame:
    """Build the canonical panel, one row per unique leaderboard model."""
    c2 = load_c2()
    c4 = load_c4()

    # De-duplicate on the model path. C1/C2 carry a handful of repeated uploads
    # (the same path under more than one submission date); the panel keeps the
    # first occurrence and the duplicates are a fact reported elsewhere, not a
    # condition papered over here.
    base = c2.drop_duplicates(subset=MODEL_KEY, keep="first").reset_index(drop=True)

    linked = link_c4(base, c4)
    classified = classify(linked)
    dated = assign_dates(classified)
    panel = eligibility_fields(dated)
    return panel


def panel_columns(panel: pd.DataFrame) -> List[str]:
    """The panel columns in a stable reporting order."""
    return list(panel.columns)


def write_panel(panel: pd.DataFrame) -> Path:
    """Write the canonical panel CSV to the derived Problem-F location.

    The file is local-only (under ``data_local/``) and is the hand-off object
    the downstream Q4 task reads rather than re-deriving the panel.
    """
    out_dir = ensure(PROBLEM_F_DERIVED)
    path = out_dir / "q4-panel.csv"
    panel.to_csv(path, index=False)
    return path


def panel_shape(panel: pd.DataFrame) -> Dict[str, int]:
    """Row/column counts, for the schema report."""
    return {"rows": int(len(panel)), "columns": int(len(panel.columns))}


__all__ = ["MODEL_KEY", "build_panel", "write_panel", "panel_columns", "panel_shape"]
