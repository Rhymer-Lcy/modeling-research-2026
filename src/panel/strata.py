"""Deterministic model-type stratification (A-E).

The primary stratum label comes from the organizer's own ``Type`` field,
collapsed to a coarse class and then to the A-E axis. That is the most specific
source label available, and it is preserved verbatim in a separate column so it
is never silently merged away. A name-keyword inference is used *only* as a
fallback for rows that carry no organizer ``Type`` (the C3 historical models),
and it is labelled as such.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from src.panel.config import (
    C1_TYPE_TO_COARSE,
    COARSE_TO_STRATUM,
    NAME_TYPE_KEYWORDS,
    STRATUM_LABELS,
)

#: Columns a row must have for classification to be possible at all.
_TYPE_COLUMN = "type"
_MODEL_COLUMN = "model"


def coarse_from_type(type_label: str) -> str:
    """Map the organizer's raw ``Type`` to a coarse class, or ``unknown``."""
    if not isinstance(type_label, str):
        return "unknown"
    return C1_TYPE_TO_COARSE.get(type_label.strip(), "unknown")


def coarse_from_name(model: str) -> str:
    """Infer a coarse class from a model *name*, using ordered keywords."""
    text = str(model).lower().replace("/", " ")
    for needle, coarse in NAME_TYPE_KEYWORDS:
        if needle in text:
            return coarse
    return "unknown"


def stratum_from_coarse(coarse: str) -> str:
    """Coarse class -> A-E stratum, or ``unknown``."""
    return COARSE_TO_STRATUM.get(coarse, "unknown")


def classify(frame: pd.DataFrame) -> pd.DataFrame:
    """Add ``type_coarse``, ``stratum`` and ``stratum_source`` columns.

    Rows with an organizer ``Type`` use it as the source of truth; rows without
    one fall back to the name keywords and are labelled ``name-keywords``. A
    row that can be classified by neither stays ``unknown`` rather than being
    silently assigned a stratum.
    """
    out = frame.copy()
    coarses: List[str] = []
    sources: List[str] = []

    for _, row in out.iterrows():
        label = row.get(_TYPE_COLUMN)
        if isinstance(label, str) and label.strip():
            coarse = coarse_from_type(label)
            coarses.append(coarse)
            sources.append("organizer-type")
            continue
        coarse = coarse_from_name(row.get(_MODEL_COLUMN, ""))
        if coarse != "unknown":
            coarses.append(coarse)
            sources.append("name-keywords")
        else:
            coarses.append("unknown")
            sources.append("unknown")

    out["type_coarse"] = coarses
    out["stratum"] = [stratum_from_coarse(c) for c in coarses]
    out["stratum_source"] = sources
    return out


def stratum_label(stratum: str) -> str:
    """Human-readable label for a stratum code."""
    return STRATUM_LABELS.get(stratum, "unknown")


def stratum_coverage(frame: pd.DataFrame) -> Dict[str, Dict[str, object]]:
    """Per-stratum counts and the coverage of the key analytical fields.

    Coverage is measured on the *full* frame (including the C3 historical rows)
    so that the numbers answer "how much of the panel does each stratum have"
    rather than "how much of some hand-picked subset".
    """
    required = ["stratum", "params_b", "analysis_date"] if "analysis_date" in frame else ["stratum", "params_b"]
    out: Dict[str, Dict[str, object]] = {}
    total = len(frame)
    for code in sorted(STRATUM_LABELS):
        sub = frame[frame["stratum"] == code]
        if sub.empty:
            continue
        params_known = int(sub["params_b"].notna().sum()) if "params_b" in sub else 0
        date_known = int(sub["analysis_date"].notna().sum()) if "analysis_date" in sub else 0
        score_known = int(sub["score_ifeval"].notna().sum()) if "score_ifeval" in sub else 0
        out[code] = {
            "label": STRATUM_LABELS[code],
            "count": int(len(sub)),
            "pct_of_panel": round(100.0 * len(sub) / total, 2),
            "params_known": params_known,
            "date_known": date_known,
            "score_known": score_known,
        }
    return out
