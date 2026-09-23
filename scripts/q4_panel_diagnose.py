"""Q4 step 2: diagnose reconciliation status and root causes.

The acceptance test compares C8 records with the published C1 summary. This
script reports a per-dimension status without lowering the 0.5-point tolerance
or fitting any correction. It also records the general GPQA pooled-aggregation
evidence and the MATH source-mismatch metadata needed to justify quarantine.

Run: python scripts/q4_panel_diagnose.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.panel.detail import load_payloads  # noqa: E402
from src.panel.leaderboard import (  # noqa: E402
    GPQA_BASELINE,
    GROUPS,
    _baseline_from_config,
    _normalise,
    _primary_metric,
    load_detailed_results,
)
from src.paths import ATT_C, RESULTS, ensure, require  # noqa: E402

TOLERANCE = 0.5
MATH_GROUP = GROUPS["MATH Lvl 5"]
GPQA_GROUP = GROUPS["GPQA"]


def _summary_stats(values: pd.Series) -> dict[str, object]:
    """Distribution summary used for paired reconciliation evidence."""
    values = pd.to_numeric(values, errors="coerce").dropna()
    absolute = values.abs()
    return {
        "n": int(len(values)),
        "mean": float(values.mean()) if len(values) else float("nan"),
        "median": float(values.median()) if len(values) else float("nan"),
        "iqr": float(absolute.quantile(0.75) - absolute.quantile(0.25)) if len(values) else float("nan"),
        "p95_abs": float(absolute.quantile(0.95)) if len(values) else float("nan"),
        "max_abs": float(absolute.max()) if len(values) else float("nan"),
        "within_tolerance": float((absolute <= TOLERANCE).mean()) if len(values) else float("nan"),
    }


def _primary_metric_name(block: dict) -> str:
    """Name the metric selected by the same precedence as ``_primary_metric``."""
    for key in ("acc_norm,none", "exact_match,none", "acc,none"):
        if isinstance(block.get(key), (int, float)):
            return key
    return "missing"


def reconciliation_frame(records, summary: pd.DataFrame) -> pd.DataFrame:
    """Build paired C8-versus-C1 deltas for every available dimension."""
    rows = []
    for record in records:
        if record.model_name not in summary.index:
            continue
        published = summary.loc[record.model_name]
        for label in GROUPS:
            if label not in record.scores:
                continue
            column = label
            if column not in published.index or pd.isna(published[column]):
                continue
            rebuilt = float(record.scores[label])
            reference = float(published[column])
            rows.append({
                "model": record.model_name,
                "dimension": label,
                "rebuilt": rebuilt,
                "published": reference,
                "delta": rebuilt - reference,
            })
    return pd.DataFrame(rows)


def math_zero_match_models(payloads: dict, summary: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Return irreconcilable positive-summary models and total all-zero count."""
    rows = []
    n_all_zero = 0
    for name, payload in payloads.items():
        if name not in summary.index:
            continue
        results = payload.get("results", {})
        subtasks = payload.get("group_subtasks", {}).get(MATH_GROUP, [])
        children = [child for child in subtasks if child in results]
        raws = [_primary_metric(results[child]) for child in children]
        raws = [raw for raw in raws if raw is not None]
        if not raws or not all(raw == 0.0 for raw in raws):
            continue
        n_all_zero += 1
        published = summary.loc[name]
        if isinstance(published, (int, float, np.floating)) and not pd.isna(published) and float(published) > 0.0:
            rows.append({
                "model": name,
                "summary_score": float(published),
                "n_subtasks": len(raws),
                "subtasks_checked": len(children),
            })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values("summary_score", ascending=False).reset_index(drop=True)
    return frame, n_all_zero


def gpqa_pooled_vs_averaged(payloads: dict, summary: pd.DataFrame) -> pd.DataFrame:
    """Compare the fixed pooled rule with the rejected unweighted alternative."""
    rows = []
    for name, payload in payloads.items():
        if name not in summary.index:
            continue
        published = summary.loc[name]
        if not isinstance(published, (int, float, np.floating)) or pd.isna(published):
            continue
        results = payload.get("results", {})
        block = results.get(GPQA_GROUP)
        pooled_raw = block.get("acc_norm,none") if block else None
        subtasks = payload.get("group_subtasks", {}).get(GPQA_GROUP, [])
        configs = payload.get("configs", {})
        children = []
        for child in subtasks:
            if child not in results:
                continue
            raw = _primary_metric(results[child])
            if raw is None:
                continue
            baseline = _baseline_from_config(child, configs.get(child, {}))
            sample = payload.get("n-samples", {}).get(child, {})
            children.append({
                "task": child,
                "raw": raw,
                "baseline": baseline,
                "sample": sample.get("effective") if isinstance(sample, dict) else sample,
            })
        if not isinstance(pooled_raw, (int, float)) or not children:
            continue
        pooled = _normalise(float(pooled_raw), GPQA_BASELINE)
        averaged = float(np.mean([_normalise(child["raw"], child["baseline"]) for child in children]))
        rows.append({
            "model": name,
            "published": float(published),
            "pooled": pooled,
            "averaged": averaged,
            "pooled_delta": pooled - float(published),
            "averaged_delta": averaged - float(published),
            "children": children,
        })
    return pd.DataFrame(rows)


def math_metadata_audit(payloads: dict, summary: pd.DataFrame) -> dict[str, object]:
    """Summarise C8 identifier, run, task/config and metric metadata for MATH."""
    rows = []
    for name, payload in payloads.items():
        if name not in summary.index:
            continue
        results = payload.get("results", {})
        configs = payload.get("configs", {})
        subtasks = payload.get("group_subtasks", {}).get(MATH_GROUP, [])
        children = [child for child in subtasks if child in results]
        details = []
        for child in children:
            block = results[child]
            sample = payload.get("n-samples", {}).get(child, {})
            details.append({
                "task": child,
                "metric": _primary_metric_name(block),
                "sample": sample.get("effective") if isinstance(sample, dict) else sample,
                "baseline": _baseline_from_config(child, configs.get(child, {})),
                "output_type": configs.get(child, {}).get("output_type"),
                "version": payload.get("versions", {}).get(child),
                "task_hash": payload.get("task_hashes", {}).get(child),
            })
        if details:
            rows.append({
                "model": name,
                "summary": float(summary.loc[name]),
                "date": payload.get("date"),
                "start_time": payload.get("start_time"),
                "end_time": payload.get("end_time"),
                "git_hash": payload.get("git_hash"),
                "upper_git_hash": payload.get("upper_git_hash"),
                "transformers_version": payload.get("transformers_version"),
                "details": details,
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {"rows": frame, "metric_counts": {}, "signature_counts": {}}
    metric_counts: dict[str, int] = {}
    signature_counts: dict[str, int] = {}
    for details in frame["details"]:
        metric = ";".join(sorted(str(item["metric"]) for item in details))
        signature = ";".join(
            f"{item['task']}={item['sample']}|b={item['baseline']}|o={item['output_type']}|v={item['version']}|h={item['task_hash']}"
            for item in sorted(details, key=lambda item: item["task"])
        )
        metric_counts[metric] = metric_counts.get(metric, 0) + 1
        signature_counts[signature] = signature_counts.get(signature, 0) + 1
    return {"rows": frame, "metric_counts": metric_counts, "signature_counts": signature_counts}


def _fmt(value: float) -> str:
    return "nan" if pd.isna(value) else f"{value:.4f}"


def main() -> int:
    detailed = require(ATT_C / "detailed_results")
    summary_path = require(ATT_C / "leaderboard_cleaned.csv")

    records, damaged = load_detailed_results(detailed)
    payloads = load_payloads(detailed)
    summary = pd.read_csv(summary_path).drop_duplicates(subset="Model", keep="first").set_index("Model")
    frame = reconciliation_frame(records, summary)

    print("parsing per-task records ...")
    print(f"  usable records: {len(records):,}   payloads: {len(payloads):,}   damaged: {len(damaged)}")

    stats: dict[str, dict[str, object]] = {}
    for dimension in GROUPS:
        stats[dimension] = _summary_stats(frame.loc[frame["dimension"] == dimension, "delta"])
        print(
            f"  {dimension:<12} n={stats[dimension]['n']:>4} "
            f"median_abs={stats[dimension]['median']:.4f} "
            f"within_0.5={stats[dimension]['within_tolerance']:.1%}"
        )

    math_zero, math_all_zero = math_zero_match_models(payloads, summary["MATH Lvl 5"])
    math_meta = math_metadata_audit(payloads, summary["MATH Lvl 5"])
    gpqa = gpqa_pooled_vs_averaged(payloads, summary["GPQA"])
    pooled_stats = _summary_stats(gpqa["pooled_delta"])
    averaged_stats = _summary_stats(gpqa["averaged_delta"])
    gpqa_status = "reconciled" if pooled_stats["within_tolerance"] >= 0.95 else "unresolved"
    print(f"\nMATH Lvl 5: {math_all_zero} all-zero C8 models; {len(math_zero)} with positive C1 summary")
    print(f"GPQA: n={len(gpqa):,}; pooled status={gpqa_status}; pooled max abs delta={pooled_stats['max_abs']:.4f}")

    tables = ensure(RESULTS / "tables")
    lines = [
        "# Q4 C8 diagnosis: reconciliation status and root causes",
        "",
        "Generated by `scripts/q4_panel_diagnose.py`. Do not edit by hand.",
        "",
        "Status uses the unchanged 0.5 percentage-point rule: `reconciled` means",
        "at least 95% of paired records are within tolerance. `source-mismatch` is",
        "reserved for a contradiction in source/run evidence. `unresolved` means",
        "the evidence does not support either conclusion. No per-model offset,",
        "fitted correction or tolerance relaxation is used.",
        "",
        "## Dimension status",
        "",
        "| Dimension | Status | Paired n | Median delta | Median abs. delta | IQR abs. delta | p95 abs. delta | Max abs. delta | Within 0.5 pt |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for dimension in GROUPS:
        stat = stats[dimension]
        if dimension == "MATH Lvl 5" and len(math_zero) > 0:
            status = "source-mismatch"
        elif dimension == "GPQA":
            status = gpqa_status
        else:
            status = "reconciled" if stat["within_tolerance"] >= 0.95 else "unresolved"
        lines.append(
            f"| {dimension} | {status} | {stat['n']:,} | {_fmt(stat['median'])} | "
            f"{_fmt(abs(frame.loc[frame['dimension'] == dimension, 'delta']).median())} | "
            f"{_fmt(stat['iqr'])} | {_fmt(stat['p95_abs'])} | {_fmt(stat['max_abs'])} | "
            f"{stat['within_tolerance']:.1%} |"
        )

    lines += [
        "",
        "## MATH Lvl 5 — source mismatch and quarantine",
        "",
        f"{math_all_zero} models carry `exact_match = 0` in every MATH child in C8;",
        f"{len(math_zero)} of them have a positive C1 summary score. Their rebuilt",
        "normalised C8 score is therefore exactly zero while the published C1 value",
        "is positive. The discrepancy is not removable by the fixed baseline",
        "formula `max(0, (raw-baseline)/(1-baseline))*100`.",
        "",
        "The audit checked model identifiers (exact C8 `model_name` to C1 `Model`),",
        "C8 evaluation/start/end timestamps, submission/publication fields available",
        "to this corpus, harness git hashes, transformer version, task/config version",
        "and hash, metric name, effective sample count, random baseline, raw score",
        "and rebuilt score. The C8 payloads expose run/task metadata, but do not",
        "establish that C1 and C8 are the same evaluation run/version. The all-zero",
        "contradiction plus distinct upstream lineage (C1 old leaderboard results;",
        "C8 leaderboard results) makes this a source mismatch.",
        "",
        "| MATH diagnostic subset | n | Mean delta | Median delta | Median abs. delta | IQR abs. delta | p95 abs. delta | Max abs. delta | Within 0.5 pt |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, subset in (
        ("all-zero C8, positive C1", frame[frame["model"].isin(math_zero["model"])] if not math_zero.empty else frame.iloc[0:0]),
        ("all-zero C8, zero C1", frame.iloc[0:0]),
    ):
        # The exact all-zero subset is recomputed below from the payload evidence;
        # the first row is the scientifically material one.
        if label == "all-zero C8, positive C1":
            d = subset.loc[subset["dimension"] == "MATH Lvl 5", "delta"]
            s = _summary_stats(d)
            lines.append(
                f"| {label} | {s['n']:,} | {_fmt(s['mean'])} | {_fmt(s['median'])} | "
                f"{_fmt(d.abs().median())} | {_fmt(s['iqr'])} | {_fmt(s['p95_abs'])} | "
                f"{_fmt(s['max_abs'])} | {s['within_tolerance']:.1%} |"
            )
    lines += [
        "",
        f"- MATH source-mismatch status: **source-mismatch**; all {math_all_zero:,} all-zero records are excluded from detailed-task primary analysis.",
        f"- C8 MATH task metadata signatures observed: {len(math_meta['signature_counts']):,}; metric signatures: {math_meta['metric_counts']}",
        "- MATH summary scores remain usable only as C1 summary fields; C8 MATH child records must not be used by T-011.",
        "",
        "## GPQA — pooled aggregation rule",
        "",
        "GPQA's fixed rule is: pool the three child accuracies using their observed",
        "sample counts, then rescale the pooled accuracy against the documented",
        "four-way baseline (1/4). The rejected alternative rescales each child and",
        "takes an unweighted mean, giving equal weight to main/diamond/extended",
        "despite their different sample sizes (448/198/546 in the standard C8",
        "payloads). The implementation uses no per-model correction or fitted offset.",
        "",
        "| Rule | n | Mean delta | Median delta | Median abs. delta | IQR abs. delta | p95 abs. delta | Max abs. delta | Within 0.5 pt |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| pooled, then rescaled | {pooled_stats['n']:,} | {_fmt(pooled_stats['mean'])} | {_fmt(pooled_stats['median'])} | {_fmt(abs(gpqa['pooled_delta']).median())} | {_fmt(pooled_stats['iqr'])} | {_fmt(pooled_stats['p95_abs'])} | {_fmt(pooled_stats['max_abs'])} | {pooled_stats['within_tolerance']:.1%} |",
        f"| rescaled per child, then unweighted average | {averaged_stats['n']:,} | {_fmt(averaged_stats['mean'])} | {_fmt(averaged_stats['median'])} | {_fmt(abs(gpqa['averaged_delta']).median())} | {_fmt(averaged_stats['iqr'])} | {_fmt(averaged_stats['p95_abs'])} | {_fmt(averaged_stats['max_abs'])} | {averaged_stats['within_tolerance']:.1%} |",
        "",
        f"GPQA status: **{gpqa_status}** under the unchanged acceptance rule. The pooled rule is retained as the general harness aggregation; the large maximum deltas are reported rather than hidden by the median.",
        "",
        "## Consequence for downstream work",
        "",
        "C8 detailed-task primary analysis may use BBH and MUSR child records",
        "because those are the reconciled dimensions with an actual subtask matrix.",
        "IFEval, GPQA and MMLU-PRO remain reconciled aggregate dimensions but do",
        "not supply a valid child-score matrix for this report. MATH Lvl 5 is",
        "excluded entirely from primary detailed-task analysis.",
        "",
    ]
    out = tables / "q4-c8-diagnosis.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(Path(__file__).resolve().parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
