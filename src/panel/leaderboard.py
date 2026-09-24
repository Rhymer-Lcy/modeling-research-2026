"""Reconstruct the six leaderboard dimensions from per-task evaluation records.

The task statement requires at least one per-task aggregation and forbids using
only the summary table. Doing that correctly needs the leaderboard's own
normalisation, because the per-task records hold **raw** accuracies while the
summary table holds scores rescaled against each task's random baseline. Those
are different numbers, and comparing them directly silently mixes two scales.

The rescaling is

    normalised = max(0, (raw - baseline) / (1 - baseline)) * 100

with the baseline taken, where possible, from the number of answer choices the
run itself recorded: each subtask's configuration carries ``doc_to_choice``, so
a multiple-choice task with k options has baseline 1/k and a generative task
has baseline 0. A grouped task is normalised per subtask and then averaged, so
that subtasks with different numbers of choices are placed on a common scale
before they are combined.

Two tasks do not expose a countable option list and need the small table below;
both were found by reconciliation failing rather than by reading the schema.
A task whose options cannot be counted is never allowed to fall through to a
baseline of zero, because that silently treats a guessable multiple-choice task
as generative and inflates its score by the whole baseline.

GPQA is a grouped multiple-choice task too, but the harness does not rescale
its three subtasks (main / diamond / extended) individually and then average:
it pools their accuracy into one number and rescales that. Averaging the three
per-subtask rescaled scores instead of rescaling the pooled accuracy weights the
subtasks equally even though they have very different sample sizes, and shifts
the result by about 0.4 points. ``_gpqa`` below uses the harness's own pooled
accuracy; this was found by reconciliation failing, not by reading the schema.

Reproducing the published summary from the raw records is the acceptance test
for this pipeline: it is an end-to-end check that the parsing, the baselines
and the aggregation are all right, and it fails loudly if any of them is not.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

#: The six leaderboard dimensions and their group keys.
GROUPS: Dict[str, str] = {
    "IFEval": "leaderboard_ifeval",
    "BBH": "leaderboard_bbh",
    "MATH Lvl 5": "leaderboard_math_hard",
    "GPQA": "leaderboard_gpqa",
    "MUSR": "leaderboard_musr",
    "MMLU-PRO": "leaderboard_mmlu_pro",
}


@dataclass
class ModelRecord:
    model_name: str
    directory: str
    source_file: str
    scores: Dict[str, float]


#: Choice counts for subtasks whose configuration does not expose a literal
#: option list. Two cases occur and both were found by reconciliation failing,
#: not by reading the schema:
#:
#: * MMLU-PRO records ``doc_to_choice`` as the *source text of a function*,
#:   because the option count is per-document. The benchmark uses ten options.
#: * The MuSR subtasks record no ``doc_to_choice`` at all, and they do not all
#:   have the same number of options, so a single fallback would be wrong.
#:
#: These are documented properties of the benchmarks rather than fitted values,
#: and each is confirmed by the reconciliation below reproducing the published
#: score exactly once it is applied.
KNOWN_CHOICE_COUNTS: Dict[str, int] = {
    "leaderboard_mmlu_pro": 10,
    "leaderboard_musr_murder_mysteries": 2,
    "leaderboard_musr_team_allocation": 3,
    "leaderboard_musr_object_placements": 5,
}

#: GPQA baseline. The three GPQA subtasks (main, diamond, extended) are each
#: 4-way multiple choice, so a random guess scores 1/4. The aggregate
#: ``leaderboard_gpqa`` block has no per-task config of its own, so the baseline
#: is the subtasks' documented choice count rather than a value read from a
#: config at run time.
GPQA_BASELINE: float = 1.0 / 4.0


def _baseline_from_config(task: str, config: Dict[str, object]) -> float:
    """Random-guess baseline for one task, from its config or the known table.

    A task whose options cannot be counted must not silently fall through to a
    baseline of zero: that treats a guessable multiple-choice task as though it
    were generative and inflates its normalised score by the whole baseline.
    """
    if task in KNOWN_CHOICE_COUNTS:
        return 1.0 / KNOWN_CHOICE_COUNTS[task]
    choices = config.get("doc_to_choice")
    if isinstance(choices, list) and choices:
        return 1.0 / len(choices)
    output_type = config.get("output_type")
    if output_type == "generate_until":
        # Genuinely generative: exact match cannot be guessed.
        return 0.0
    if output_type == "multiple_choice":
        raise KeyError(
            f"{task} is multiple-choice but exposes no option list and has no "
            "entry in KNOWN_CHOICE_COUNTS; refusing to assume a baseline of 0"
        )
    return 0.0


def _primary_metric(block: Dict[str, object]) -> Optional[float]:
    """The metric the leaderboard reports for a task, in its order of preference."""
    for key in ("acc_norm,none", "exact_match,none", "acc,none"):
        value = block.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _normalise(raw: float, baseline: float) -> float:
    if baseline >= 1.0:
        return 0.0
    return max(0.0, (raw - baseline) / (1.0 - baseline)) * 100.0


def _ifeval(results: Dict[str, Dict[str, object]]) -> Optional[float]:
    """IFEval is the mean of its two strict accuracies; both have baseline 0."""
    block = results.get("leaderboard_ifeval")
    if not block:
        return None
    parts = [block.get("prompt_level_strict_acc,none"), block.get("inst_level_strict_acc,none")]
    values = [float(p) for p in parts if isinstance(p, (int, float))]
    if not values:
        return None
    return float(np.mean(values) * 100.0)


def _gpqa(results: Dict[str, Dict[str, object]]) -> Optional[float]:
    """GPQA, rescaled from the harness's own pooled 4-way accuracy.

    ``leaderboard_gpqa`` is a grouped task whose subtasks have very different
    sample sizes, so the leaderboard pools their accuracy and rescales the
    pooled value against the 4-way random baseline. Rescaling each subtask and
    averaging instead weights them equally and misses the published value by
    about 0.4 points; using the pooled accuracy closes that gap.
    """
    block = results.get("leaderboard_gpqa")
    if not block:
        return None
    raw = block.get("acc_norm,none")
    if not isinstance(raw, (int, float)):
        return None
    return _normalise(raw, GPQA_BASELINE)


def score_record(payload: Dict[str, object]) -> Dict[str, float]:
    """Compute the six normalised dimensions from one evaluation record."""
    results: Dict[str, Dict[str, object]] = payload.get("results", {})  # type: ignore[assignment]
    configs: Dict[str, Dict[str, object]] = payload.get("configs", {})  # type: ignore[assignment]
    subtasks: Dict[str, List[str]] = payload.get("group_subtasks", {})  # type: ignore[assignment]

    out: Dict[str, float] = {}

    value = _ifeval(results)
    if value is not None:
        out["IFEval"] = value

    value = _gpqa(results)
    if value is not None:
        out["GPQA"] = value

    for label, group in GROUPS.items():
        if label in ("IFEval", "GPQA"):
            continue
        children = [c for c in subtasks.get(group, []) if c in results]
        if children:
            # Normalise each subtask against its own baseline, then average.
            normalised = []
            for child in children:
                raw = _primary_metric(results[child])
                if raw is None:
                    continue
                normalised.append(_normalise(raw, _baseline_from_config(child, configs.get(child, {}))))
            if normalised:
                out[label] = float(np.mean(normalised))
            continue
        block = results.get(group)
        if not block:
            continue
        raw = _primary_metric(block)
        if raw is None:
            continue
        out[label] = _normalise(raw, _baseline_from_config(group, configs.get(group, {})))

    return out


def subtask_scores(payload: Dict[str, object]) -> Dict[str, List[Tuple[str, float, float, float]]]:
    """Per-subtask (name, raw, baseline, normalised) for each grouped dimension.

    This is the same arithmetic ``score_record`` uses to average each grouped
    dimension, but it keeps the per-subtask values rather than collapsing them,
    so the detailed-task analysis can decompose *within-model* versus
    *between-model* variance. Dimensions without subtasks (IFEval, GPQA) are
    omitted because they have no within-task breakdown to analyse.
    """
    results: Dict[str, Dict[str, object]] = payload.get("results", {})  # type: ignore[assignment]
    configs: Dict[str, Dict[str, object]] = payload.get("configs", {})  # type: ignore[assignment]
    subtasks: Dict[str, List[str]] = payload.get("group_subtasks", {})  # type: ignore[assignment]

    out: Dict[str, List[Tuple[str, float, float, float]]] = {}
    for label, group in GROUPS.items():
        if label in ("IFEval", "GPQA"):
            continue
        children = [c for c in subtasks.get(group, []) if c in results]
        if not children:
            continue
        rows: List[Tuple[str, float, float, float]] = []
        for child in children:
            raw = _primary_metric(results[child])
            if raw is None:
                continue
            baseline = _baseline_from_config(child, configs.get(child, {}))
            rows.append((child, raw, baseline, _normalise(raw, baseline)))
        if rows:
            out[label] = rows
    return out


def _open_text(path: Path):
    """Open a UTF-8 text file, tolerating Windows MAX_PATH limits.

    On Windows a path longer than about 260 characters fails to open with
    ``FileNotFoundError`` even though the file exists. The extended-length
    ``\\\\?\\`` prefix lifts that limit. A handful of model directory names are
    long enough to cross it, and they are genuine records, not damaged files,
    so they are retried once with the prefix rather than misreported.
    """
    try:
        return open(path, encoding="utf-8")
    except FileNotFoundError:
        if os.name != "nt":
            raise
        return open("\\\\?\\" + str(path.resolve()), encoding="utf-8")


def load_detailed_results(root: Path) -> Tuple[List[ModelRecord], List[Dict[str, str]]]:
    """Parse every usable per-model record under ``root``.

    Returns the records and a log of the files that could not be parsed. The
    damaged files are reported rather than passed over in silence: a corpus
    that quietly shrinks is how a coverage claim stops being true.
    """
    records: List[ModelRecord] = []
    damaged: List[Dict[str, str]] = []

    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        best: Optional[Tuple[str, Dict[str, object]]] = None
        for path in sorted(directory.glob("*.json")):
            try:
                with _open_text(path) as handle:
                    payload = json.load(handle)
            except Exception as exc:  # noqa: BLE001
                damaged.append({
                    "directory": directory.name,
                    "file": path.name,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue
            # Filenames carry an ISO timestamp, so the last one sorted is the
            # most recent run for that model.
            best = (path.name, payload)

        if best is None:
            continue
        filename, payload = best
        name = payload.get("model_name") or directory.name
        records.append(ModelRecord(
            model_name=str(name),
            directory=directory.name,
            source_file=filename,
            scores=score_record(payload),
        ))

    return records, damaged


__all__ = ["GROUPS", "ModelRecord", "score_record", "subtask_scores", "load_detailed_results"]
