"""Detailed-task analysis of the C8 per-task evaluation records.

The reconciliation script determines which C8 dimensions are safe to use below
the published summary-table level.  This module keeps the per-subtask scores for
those *reconciled* dimensions rather than averaging them away, then separates
variation that is between models from variation that is within a model across
subtasks.

MATH Lvl 5 is intentionally absent from the primary extraction: its C8 records
are source-mismatched with the C1 summary (see ``q4-c8-diagnosis.md``).  A
caller must explicitly opt into diagnostic extraction to obtain it, which makes
it impossible for a downstream analysis to consume quarantined MATH subtasks by
accident.  GPQA child scores are retained descriptively only after its pooled
aggregation rule has reconciled: the published GPQA dimension is still computed
from the harness's pooled accuracy, not by averaging these children.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.panel.leaderboard import ModelRecord, subtask_scores, _open_text

#: Dimensions whose C8 records have cleared the reconciliation acceptance test.
#: GPQA is included because its pooled harness rule is reconciled, even though
#: it cannot supply a valid child-score average for the detailed table.
RECONCILED_DIMENSIONS = frozenset({"IFEval", "BBH", "GPQA", "MUSR", "MMLU-PRO"})
#: C8 MATH subtask records describe a different source/run from the C1 summary.
QUARANTINED_DIMENSIONS = frozenset({"MATH Lvl 5"})


def extract_subtasks(
    records: List[ModelRecord],
    payloads: Dict[str, dict],
    *,
    include_quarantined: bool = False,
) -> pd.DataFrame:
    """Long-form ``[model, dimension, subtask, raw, baseline, normalised]``.

    The primary default includes only dimensions whose C8 records reconciled to
    C1.  ``include_quarantined=True`` is reserved for a clearly-labelled source
    diagnostic; it must never be used to produce a downstream task-level result.
    ``records`` are parsed model records and ``payloads`` maps model names to raw
    JSON payloads, so the breakdown can be re-read without another corpus scan.
    """
    allowed = RECONCILED_DIMENSIONS | (QUARANTINED_DIMENSIONS if include_quarantined else frozenset())
    rows: List[Dict[str, object]] = []
    for record in records:
        payload = payloads.get(record.model_name)
        if not payload:
            continue
        for dimension, subtasks in subtask_scores(payload).items():
            if dimension not in allowed:
                continue
            for subtask, raw, baseline, normalised in subtasks:
                rows.append({
                    "model": record.model_name,
                    "dimension": dimension,
                    "subtask": subtask,
                    "raw": raw,
                    "baseline": baseline,
                    "normalised": normalised,
                })
    return pd.DataFrame(rows)


def subtask_profile(frame: pd.DataFrame, expected_models: int) -> pd.DataFrame:
    """Describe score availability and dispersion for each retained subtask.

    Missingness is relative to the parsed C8 record corpus, not the C1 panel;
    that denominator makes absent task results visible.  The variance and SD are
    across models, while median/IQR describe the subtask's normalised-score
    distribution without assuming it is Gaussian.
    """
    rows: List[Dict[str, object]] = []
    for (dimension, subtask), sub in frame.groupby(["dimension", "subtask"], sort=True):
        values = sub["normalised"].dropna()
        observed = int(values.shape[0])
        missing = max(0, expected_models - observed)
        rows.append({
            "dimension": dimension,
            "subtask": subtask,
            "n_models": observed,
            "missing_models": missing,
            "missing_rate": missing / expected_models if expected_models else float("nan"),
            "median": float(values.median()),
            "q1": float(values.quantile(0.25)),
            "q3": float(values.quantile(0.75)),
            "iqr": float(values.quantile(0.75) - values.quantile(0.25)),
            "variance": float(values.var(ddof=1)) if observed > 1 else float("nan"),
            "sd": float(values.std(ddof=1)) if observed > 1 else float("nan"),
        })
    return pd.DataFrame(rows)


def within_model_imbalance(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-dimension distribution of model-level subtask standard deviations."""
    rows: List[Dict[str, object]] = []
    for dimension, sub in frame.groupby("dimension", sort=True):
        per_model = sub.groupby("model")["normalised"].agg(["count", "std"])
        values = per_model.loc[per_model["count"] >= 2, "std"].dropna()
        if values.empty:
            continue
        rows.append({
            "dimension": dimension,
            "n_models": int(values.shape[0]),
            "median_within_sd": float(values.median()),
            "q1_within_sd": float(values.quantile(0.25)),
            "q3_within_sd": float(values.quantile(0.75)),
            "iqr_within_sd": float(values.quantile(0.75) - values.quantile(0.25)),
        })
    return pd.DataFrame(rows)


def _icc(values: np.ndarray, groups: np.ndarray) -> Tuple[float, float, float, float, int, int]:
    """One-way variance decomposition of ``values`` by ``groups``.

    Returns ``(icc, between_ss, within_ss, total_ss, n_groups, n_obs)`` where
    ``icc`` is the fraction of total sum of squares explained by the group mean
    (between-group SS / total SS), the intraclass correlation of the one-way
    design.
    """
    grand = float(np.mean(values))
    between = 0.0
    within = 0.0
    n_groups = 0
    for g in np.unique(groups):
        idx = groups == g
        gv = values[idx]
        between += float(len(gv) * (np.mean(gv) - grand) ** 2)
        within += float(np.sum((gv - np.mean(gv)) ** 2))
        n_groups += 1
    total = float(np.sum((values - grand) ** 2))
    icc = between / total if total > 0 else float("nan")
    return icc, between, within, total, n_groups, len(values)


def variance_decomposition(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-dimension one-way variance decomposition of subtask normalised scores.

    ``frame`` is the long form from :func:`extract_subtasks`. Only models with at
    least two subtask scores in a dimension contribute (a model with one subtask
    cannot have a within-model component), and that requirement is reported.
    """
    rows: List[Dict[str, object]] = []
    for dimension in sorted(frame["dimension"].unique()):
        sub = frame[frame["dimension"] == dimension].dropna(subset=["normalised"])
        # Keep only models that contribute more than one subtask, so the
        # within-model term is defined.
        counts = sub.groupby("model")["subtask"].transform("nunique")
        sub = sub[counts >= 2]
        if sub.empty:
            continue
        icc, between, within, total, n_groups, n_obs = _icc(
            sub["normalised"].to_numpy(), sub["model"].to_numpy()
        )
        n_subtasks = int(sub["subtask"].nunique())
        rows.append({
            "dimension": dimension,
            "n_models": n_groups,
            "n_observations": n_obs,
            "n_subtasks": n_subtasks,
            "grand_mean": float(sub["normalised"].mean()),
            "between_ss": between,
            "within_ss": within,
            "total_ss": total,
            "icc": icc,
        })
    return pd.DataFrame(rows)


def load_payloads(root: Path) -> Dict[str, dict]:
    """Map model name -> raw JSON payload, using the same parse as the loader.

    The payloads are read once so the detailed analysis can ask the same corpus
    the reconciliation asked without re-deriving the parse order.
    """
    payloads: Dict[str, dict] = {}
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        best: Tuple[str, dict] | None = None
        for path in sorted(directory.glob("*.json")):
            try:
                with _open_text(path) as handle:
                    payload = json.load(handle)
            except Exception:  # noqa: BLE001
                continue
            best = (path.name, payload)
        if best is None:
            continue
        name = best[1].get("model_name") or directory.name
        payloads[str(name)] = best[1]
    return payloads


__all__ = [
    "RECONCILED_DIMENSIONS",
    "QUARANTINED_DIMENSIONS",
    "extract_subtasks",
    "subtask_profile",
    "within_model_imbalance",
    "variance_decomposition",
    "load_payloads",
]
