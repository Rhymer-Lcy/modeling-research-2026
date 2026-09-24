"""Canonical loaders for the organizer's Attachment-C tables.

Each loader reads one raw CSV, renames its columns to a canonical snake_case
schema, and returns the frame with no further mutation. Provenance (the
source table and its repo-relative path) is recorded separately so that a
consumer never mistakes one table for an independent observation of another:
C2 is C1 with three Epoch columns appended, and C3 re-expresses the leaderboard
as a timeseries with mixed historical provenance.

Rows are never dropped here. Duplicates, missingness and coverage are facts to
report, not conditions to paper over, so every loader returns the frame exactly
as read (after renaming) and the analysis code quantifies what is there.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from src.paths import ATT_C, require

#: Canonical column names. The raw headers contain a ``#``, spaces and an emoji
#: arrow (``Average ⬆️``); these are folded to ASCII so downstream code does not
#: have to reproduce them.
C1_RENAME: Dict[str, str] = {
    "Model": "model",
    "#Params (B)": "params_b",
    "Submission Date": "submission_date",
    "Hub License": "hub_license",
    "Type": "type",
    "IFEval": "score_ifeval",
    "BBH": "score_bbh",
    "MATH Lvl 5": "score_math_lvl5",
    "GPQA": "score_gpqa",
    "MUSR": "score_musr",
    "MMLU-PRO": "score_mmlu_pro",
}

C2_EXTRA: Dict[str, str] = {
    "Epoch_AI_Publication_Date": "pub_date",
    "Epoch_AI_Organization": "org",
    "Epoch_AI_Open_Weights": "open_weights_epoch",
}

C3_RENAME: Dict[str, str] = {
    "Model": "model",
    "Year": "year",
    "Params_B": "params_b",
    "Average": "average",
    "IFEval": "score_ifeval",
    "BBH": "score_bbh",
    "MATH_Lvl5": "score_math_lvl5",
    "GPQA": "score_gpqa",
    "MUSR": "score_musr",
    "MMLU_PRO": "score_mmlu_pro",
    "Source": "source",
}

C4_RENAME: Dict[str, str] = {
    "Model": "c4_model",
    "Domain": "c4_domain",
    "Task": "c4_task",
    "Organization": "c4_org",
    "Authors": "c4_authors",
    "Publication date": "c4_pub_date",
    "Parameters": "c4_params",
    "Parameters notes": "c4_params_notes",
    "Training compute (FLOP)": "c4_compute_flop",
    "Training compute notes": "c4_compute_notes",
    "Training dataset size (total)": "c4_dataset_size",
    "Model accessibility": "c4_accessibility",
    "Hugging Face developer id": "c4_hf_id",
    "Open model weights?": "c4_open_weights",
    "Frontier model": "c4_frontier",
    "Base model": "c4_base_model",
    "Finetune compute (FLOP)": "c4_finetune_flop",
    "Organization categorization": "c4_org_category",
    "Country (of organization)": "c4_country",
    "Training compute estimation method": "c4_compute_method",
}

C7_RENAME: Dict[str, str] = {
    "model_name": "model",
    "n_layers": "n_layers",
    "n_heads": "n_heads",
    "d_model": "d_model",
    "vocab_size": "vocab_size",
    "max_position_embeddings": "ctx_len",
    "training_data_TB": "training_data_tb",
}

#: The six leaderboard dimensions in canonical order.
DIMENSIONS: List[str] = [
    "score_ifeval",
    "score_bbh",
    "score_math_lvl5",
    "score_gpqa",
    "score_musr",
    "score_mmlu_pro",
]

#: The `Average ⬆️` header, located by prefix because it carries an emoji.
def _average_column(raw: pd.DataFrame) -> str:
    for c in raw.columns:
        if c.startswith("Average"):
            return c
    raise KeyError("no Average column found")


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(require(path))


def load_c1() -> pd.DataFrame:
    """Load `leaderboard_cleaned.csv` (C1), the primary six-dimension summary."""
    raw = _read(ATT_C / "leaderboard_cleaned.csv")
    rename = dict(C1_RENAME)
    rename[_average_column(raw)] = "average"
    return raw.rename(columns=rename)


def load_c2() -> pd.DataFrame:
    """Load `leaderboard_enhanced.csv` (C2): C1 plus three Epoch columns."""
    raw = _read(ATT_C / "leaderboard_enhanced.csv")
    rename = dict(C1_RENAME)
    rename[_average_column(raw)] = "average"
    rename.update(C2_EXTRA)
    return raw.rename(columns=rename)


def load_c3() -> pd.DataFrame:
    """Load `leaderboard_extended_timeseries.csv` (C3), mixed provenance."""
    raw = _read(ATT_C / "leaderboard_extended_timeseries.csv")
    return raw.rename(columns=C3_RENAME)


def load_c4() -> pd.DataFrame:
    """Load `epoch_all_ai_models.csv` (C4), the Epoch AI metadata table.

    C4 has 57 columns; only the subset in ``C4_RENAME`` is canonical for the
    panel (identity, parameters, compute, dates, accessibility). The rest are
    per-row narrative fields (abstracts, citations, hardware notes) that the
    panel does not need, so they are dropped here rather than carried into every
    downstream table.
    """
    raw = _read(ATT_C / "epoch_all_ai_models.csv")
    keep = {k: v for k, v in C4_RENAME.items() if k in raw.columns}
    return raw[list(keep)].rename(columns=keep)


def load_c7() -> pd.DataFrame:
    """Load `model_architecture_metadata.csv` (C7), architecture metadata."""
    raw = _read(ATT_C / "model_architecture_metadata.csv")
    return raw.rename(columns=C7_RENAME)


@dataclass
class SourceFact:
    """One observed property of a loaded table, for the schema report."""

    label: str
    value: str


def schema_facts(frame: pd.DataFrame, name: str, key: str) -> List[SourceFact]:
    """Row/duplicate/missingness facts for one table, keyed on ``key``."""
    n = len(frame)
    facts: List[SourceFact] = [
        SourceFact("rows", f"{n:,}"),
        SourceFact("columns", f"{len(frame.columns):,}"),
        SourceFact("unique keys", f"{frame[key].nunique():,}"),
        SourceFact("duplicate key rows", f"{int(frame.duplicated(subset=[key]).sum()):,}"),
    ]
    for col in frame.columns:
        if col == key:
            continue
        missing = int(frame[col].isna().sum())
        if missing:
            facts.append(SourceFact(f"{col} missing", f"{missing:,}"))
    return facts


def relationship(c1: pd.DataFrame, c2: pd.DataFrame, c3: pd.DataFrame) -> Dict[str, object]:
    """Quantify how C1, C2 and C3 relate to one another.

    Returns a mapping of named facts, all derived from the loaded frames rather
    than assumed. The two non-trivial findings are that C2 differs from C1 only
    in floating-point rounding (same rows, same order) and that C3's leaderboard
    rows carry scores identical to C1's for the 4,494 shared models.
    """
    shared = [c for c in c1.columns if c in c2.columns and c != "model"]
    facts: Dict[str, object] = {
        "c1_rows": len(c1),
        "c2_rows": len(c2),
        "c3_rows": len(c3),
        "c1_c2_same_model_order": bool((c1["model"] == c2["model"]).all()),
        "c2_only_extra_columns": sorted(set(c2.columns) - set(c1.columns)),
    }

    # C1 vs C2 on shared value columns: differences are float rounding noise.
    a = c1[shared].reset_index(drop=True)
    b = c2[shared].reset_index(drop=True)
    diff_rows = int((~a.eq(b)).any(axis=1).sum())
    max_abs = 0.0
    for col in shared:
        if not pd.api.types.is_numeric_dtype(a[col]):
            continue
        both = a[col].notna() & b[col].notna()
        if both.any():
            max_abs = max(max_abs, float((a.loc[both, col] - b.loc[both, col]).abs().max()))
    facts["c1_c2_differing_rows"] = diff_rows
    facts["c1_c2_max_numeric_abs_delta"] = f"{max_abs:.3g}"

    # C1 vs C3.
    c1m, c3m = set(c1["model"]), set(c3["model"])
    facts["c1_models_absent_from_c3"] = sorted(c1m - c3m)
    facts["c3_models_absent_from_c1"] = sorted(c3m - c1m)

    # Score identity for shared leaderboard models.
    mapd = {
        "score_ifeval": "score_ifeval",
        "score_bbh": "score_bbh",
        "score_math_lvl5": "score_math_lvl5",
        "score_gpqa": "score_gpqa",
        "score_musr": "score_musr",
        "score_mmlu_pro": "score_mmlu_pro",
    }
    c1u = c1.drop_duplicates(subset="model", keep="first").set_index("model")
    c3lb = c3[c3["source"] == "Open LLM Leaderboard"].drop_duplicates(
        subset="model", keep="first").set_index("model")
    common = c1u.index.intersection(c3lb.index)
    mism = 0
    total = 0
    for m in common:
        for c in mapd:
            if m not in c3lb.index:
                continue
            va, vb = c1u.loc[m, c], c3lb.loc[m, c]
            if pd.isna(va) or pd.isna(vb):
                continue
            total += 1
            if not np.isclose(va, vb, atol=1e-9):
                mism += 1
    facts["c1_c3_shared_models"] = len(common)
    facts["c1_c3_score_mismatches"] = mism
    facts["c1_c3_score_comparisons"] = total
    return facts
