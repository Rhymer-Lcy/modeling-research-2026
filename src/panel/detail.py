"""Detailed-task analysis of the C8 per-task evaluation records.

The reconciliation script proves that the six summary dimensions are reproduced
from the raw records; this module goes one level deeper. For each grouped
dimension that actually records per-subtask results (BBH, MATH Lvl 5, MUSR) it
keeps the per-subtask normalised score instead of averaging it away, and then
asks a single, well-posed question of that matrix: how much of the variance in a
subtask score is *between models* (a model's overall standing) versus *within a
model* (that model's unevenness across the subtasks of one benchmark)?

That decomposition is the one genuinely detailed task-level aggregation the task
requires. It is a one-way variance decomposition (model is the grouping factor),
reported as the fraction of variance explained by the model identity — the
intraclass correlation. A dimension whose ICC is high is one where a model's
average subtask score predicts its individual subtask scores; a low ICC is a
benchmark whose subtasks are so heterogeneous that they measure different
things.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.panel.leaderboard import ModelRecord, load_detailed_results, subtask_scores, _open_text


def extract_subtasks(records: List[ModelRecord], payloads: Dict[str, dict]) -> pd.DataFrame:
    """Long-form ``[model, dimension, subtask, raw, baseline, normalised]``.

    ``records`` are the parsed model records and ``payloads`` maps a model name
    to its raw JSON payload, so the per-subtask breakdown can be re-read without
    re-parsing the corpus.
    """
    rows: List[Dict[str, object]] = []
    for record in records:
        payload = payloads.get(record.model_name)
        if not payload:
            continue
        for dimension, subtasks in subtask_scores(payload).items():
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


__all__ = ["extract_subtasks", "variance_decomposition", "load_payloads"]
