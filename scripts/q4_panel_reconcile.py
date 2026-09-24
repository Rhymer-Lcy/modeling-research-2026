"""Q4 step 1: rebuild the six leaderboard dimensions from the per-task records
and reconcile them against the published summary table.

This is the acceptance test for the per-task pipeline. If the reconstruction
agrees with the summary, the parsing, the random baselines and the aggregation
are all correct and the per-task corpus can be trusted for finer analysis. If
it does not, the per-task work cannot be trusted either, and that has to be
visible rather than assumed.

The join is exact: each record carries its own ``model_name``, which matches
the summary table's key directly. No fuzzy matching is used; unmatched records
stay unmatched and are counted.

Run:  python scripts/q4_panel_reconcile.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.panel.leaderboard import GROUPS, load_detailed_results  # noqa: E402
from src.paths import ATT_C, RESULTS, ensure, require  # noqa: E402

TOLERANCE = 0.5  # percentage points


def main() -> int:
    detailed = require(ATT_C / "detailed_results")
    summary_path = require(ATT_C / "leaderboard_cleaned.csv")

    print("parsing per-task records ...")
    records, damaged = load_detailed_results(detailed)
    n_dirs = sum(1 for p in detailed.iterdir() if p.is_dir())
    print(f"  model directories      : {n_dirs:,}")
    print(f"  usable records         : {len(records):,}")
    print(f"  unparsable files       : {len(damaged)}")
    for entry in damaged:
        print(f"      {entry['directory']}/{entry['file']}  {entry['error'][:60]}")
    complete = [r for r in records if len(r.scores) == 6]
    print(f"  records with all six   : {len(complete):,}")
    print()

    summary = pd.read_csv(summary_path)
    print(f"summary table            : {len(summary):,} rows, "
          f"{summary['Model'].nunique():,} distinct models")

    # Exact join on the model identifier both sides already carry.
    summary_unique = summary.drop_duplicates(subset="Model", keep="first").set_index("Model")
    matched = [r for r in records if r.model_name in summary_unique.index]
    print(f"  exact-join matches       : {len(matched):,} of {len(records):,} records")
    print(f"  unmatched (left as such) : {len(records) - len(matched):,}")
    print()

    rows = []
    for record in matched:
        published = summary_unique.loc[record.model_name]
        for label in GROUPS:
            if label not in record.scores or label not in published.index:
                continue
            ref = published[label]
            if not isinstance(ref, (int, float, np.floating)) or pd.isna(ref):
                continue
            rows.append({
                "model": record.model_name,
                "dimension": label,
                "rebuilt": record.scores[label],
                "published": float(ref),
                "delta": record.scores[label] - float(ref),
            })

    frame = pd.DataFrame(rows)
    if frame.empty:
        print("RECONCILIATION FAILED: no comparable pairs were produced.")
        return 1

    print("reconciliation, rebuilt from per-task records vs published summary")
    print(f"(tolerance {TOLERANCE} percentage points)")
    print()
    print(f"  {'dimension':<12} {'n':>6} {'median |d|':>11} {'p95 |d|':>9} "
          f"{'max |d|':>9} {'within tol':>11}")
    overall_ok = 0
    overall_n = 0
    for label in GROUPS:
        sub = frame[frame["dimension"] == label]
        if sub.empty:
            continue
        absd = sub["delta"].abs()
        within = float((absd <= TOLERANCE).mean())
        overall_ok += int((absd <= TOLERANCE).sum())
        overall_n += len(sub)
        print(f"  {label:<12} {len(sub):>6,} {absd.median():>11.4f} "
              f"{absd.quantile(0.95):>9.4f} {absd.max():>9.4f} {within:>10.1%}")
    rate = overall_ok / overall_n
    print()
    print(f"  overall within tolerance : {overall_ok:,}/{overall_n:,} = {rate:.2%}")
    print()

    # Report per dimension. A single global threshold would hide that four of
    # the six reconcile exactly while two do not, and the useful question is
    # which dimensions the per-task corpus can currently carry.
    per_dim = {}
    for label in GROUPS:
        sub = frame[frame["dimension"] == label]
        if sub.empty:
            continue
        per_dim[label] = float((sub["delta"].abs() <= TOLERANCE).mean())
    reconciled = sorted(k for k, v in per_dim.items() if v >= 0.95)
    quarantined = sorted(k for k, v in per_dim.items() if v < 0.95)

    print(f"  reconciled  ({len(reconciled)}/6): {', '.join(reconciled)}")
    print(f"  quarantined ({len(quarantined)}/6): {', '.join(quarantined)}")
    print()
    verdict = "PASS" if not quarantined else "PARTIAL"
    if verdict == "PASS":
        print("ACCEPTANCE TEST PASS on all six dimensions.")
    else:
        print("ACCEPTANCE TEST PARTIAL. The dimensions listed as reconciled are")
        print("reproduced from the raw records to the published value, so for those")
        print("the parsing, the per-subtask baselines and the aggregation are all")
        print("confirmed. The quarantined dimensions are NOT usable for per-task")
        print("analysis until their cause is resolved, and the threshold is left")
        print("where it is rather than lowered to obtain a pass.")
        print()
        print("  Diagnosis so far:")
        print("   - MATH Lvl 5: 154 models carry raw exact_match = 0 in every math")
        print("     subtask; 119 of those are scored above zero by the summary (e.g.")
        print("     Qwen2.5-32B-Instruct: summary 62.5, raw 0.0), which no")
        print("     normalisation can reproduce. The two tables describe different")
        print("     evaluation runs/versions for these models.")
        print("     See results/tables/q4-c8-diagnosis.md.")
        print("   - GPQA: reconciled by rescaling the harness's pooled accuracy")
        print("     against the 4-way baseline instead of averaging per-subtask")
        print("     rescaled scores (the three subtasks have very different sample")
        print("     sizes, so the average weighted them wrongly by ~0.4 points).")
    print()

    worst = frame.reindex(frame["delta"].abs().sort_values(ascending=False).index).head(5)
    print("largest disagreements:")
    for _, row in worst.iterrows():
        print(f"  {row['dimension']:<12} {row['model'][:46]:<46} "
              f"rebuilt {row['rebuilt']:>7.3f}  published {row['published']:>7.3f}  "
              f"delta {row['delta']:+.3f}")
    print()

    tables = ensure(RESULTS / "tables")
    lines = [
        "# Q4 acceptance test: per-task records vs the published summary",
        "",
        "Generated by `scripts/q4_panel_reconcile.py`. Do not edit by hand.",
        "",
        "The task requires a per-task aggregation and forbids relying on the",
        "summary table alone. The per-task records hold **raw** accuracies while",
        "the summary holds scores rescaled against each task's random baseline, so",
        "the two are on different scales and reproducing one from the other is the",
        "test that the pipeline is right.",
        "",
        "Rescaling is `max(0, (raw - baseline) / (1 - baseline)) * 100`, with the",
        "baseline read from each subtask's own recorded configuration rather than",
        "from a hard-coded table: a multiple-choice subtask with k options has",
        "baseline 1/k, a generative one has baseline 0. Grouped tasks are",
        "normalised per subtask and then averaged, so subtasks with different",
        "numbers of choices reach a common scale before being combined.",
        "",
        "## Corpus",
        "",
        f"- model directories: {n_dirs:,}",
        f"- usable records: {len(records):,}",
        f"- unparsable files: {len(damaged)} (listed below, skipped and counted)",
        f"- records carrying all six dimensions: {len(complete):,}",
        f"- exact-join matches against the summary: {len(matched):,}",
        "",
        "The join is exact on the model identifier both sides already carry. No",
        "fuzzy matching is used and unmatched records stay unmatched.",
        "",
        "## Reconciliation",
        "",
        f"Tolerance {TOLERANCE} percentage points.",
        "",
        "| Dimension | n | Median abs. delta | p95 | Max | Within tolerance |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in GROUPS:
        sub = frame[frame["dimension"] == label]
        if sub.empty:
            continue
        absd = sub["delta"].abs()
        lines.append(
            f"| {label} | {len(sub):,} | {absd.median():.4f} | "
            f"{absd.quantile(0.95):.4f} | {absd.max():.4f} | "
            f"{(absd <= TOLERANCE).mean():.1%} |"
        )
    lines += [
        "",
        f"Overall within tolerance: {overall_ok:,}/{overall_n:,} = {rate:.2%}",
        "",
        f"- Reconciled ({len(reconciled)}/6): " + ", ".join(reconciled),
        f"- Quarantined ({len(quarantined)}/6): " + (", ".join(quarantined) or "none"),
        "",
        f"Verdict: **{verdict}**. The reconciled dimensions are reproduced from",
        "the raw records to the published value, confirming the parsing, the",
        "per-subtask baselines and the aggregation for those. The quarantined",
        "dimensions are not usable for per-task analysis until their cause is",
        "resolved. The tolerance is left where it is rather than lowered to",
        "obtain a pass.",
        "",
        "Diagnosis: MATH carries raw `exact_match = 0` in every math subtask for",
        "154 models; 119 of those are scored above zero by the summary (e.g.",
        "Qwen2.5-32B-Instruct, summary 62.5, raw 0.0), which no normalisation can",
        "reproduce — the two tables describe different evaluation runs, a source",
        "mismatch, not a normalisation error. GPQA is reconciled by rescaling the",
        "harness's pooled accuracy against the 4-way baseline instead of averaging",
        "per-subtask rescaled scores. The full diagnosis is in",
        "`results/tables/q4-c8-diagnosis.md`.",
        "",
        "## Unparsable files",
        "",
    ]
    if damaged:
        lines.append("| Directory | File | Error |")
        lines.append("| --- | --- | --- |")
        for entry in damaged:
            lines.append(f"| `{entry['directory']}` | `{entry['file']}` | {entry['error'][:70]} |")
    else:
        lines.append("None.")
    lines.append("")
    out = tables / "q4-c8-reconciliation.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(Path(__file__).resolve().parent.parent)}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
