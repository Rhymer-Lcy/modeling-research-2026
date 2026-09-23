"""Q4 step 2: root-cause the two dimensions that did not reconcile.

``q4_panel_reconcile.py`` shows that four of the six dimensions reproduce the
published summary from the raw per-task records and two did not: MATH Lvl 5
(quarantined) and GPQA (since resolved). This script pins down *why*, from the
data, so the quarantine is a diagnosed source problem rather than an unexplained
failure. It writes ``results/tables/q4-c8-diagnosis.md``.

The two causes are different in kind and this script keeps them separate:

* **GPQA** was a normalisation error in the first pass. GPQA is a grouped task
  whose three subtasks have very different sample sizes; the harness pools their
  accuracy into one number and rescales that against the 4-way baseline. The
  first pass rescale-and-average instead, weighting the subtasks equally and
  shifting the score by ~0.4 points. The fix (pool, then rescale) reproduces the
  published value, so GPQA is reconciled and only recorded here for the record.

* **MATH Lvl 5** is a genuine source mismatch. 154 models carry ``exact_match =
  0`` in every math subtask of C8 while the summary scores them up to 62.5. No
  normalisation turns a zero exact-match into a nonzero score, so the two tables
  describe different evaluation runs. The data description records that C1 comes
  from ``open-llm-leaderboard-old/results`` and C8 from ``open-llm-leaderboard
  /results`` — two different upstream datasets.

Run:  python scripts/q4_panel_diagnose.py
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

MATH_GROUP = GROUPS["MATH Lvl 5"]


def math_zero_match_models(payloads: dict, summary: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Models whose every MATH subtask has ``exact_match = 0``.

    Returns ``(frame, n_all_zero)``:

    * ``frame`` — the *irreconcilable* subset: zero in C8 and *nonzero* in the
      summary, sorted by summary score descending. No normalisation turns a zero
      exact-match into a nonzero score, so these cannot be reconciled.
    * ``n_all_zero`` — the total number of models that are zero in every MATH
      subtask, including those that are also zero in the summary (and are
      therefore consistent rather than mismatched).
    """
    rows = []
    n_all_zero = 0
    for name, payload in payloads.items():
        if name not in summary.index:
            continue
        published = summary.loc[name]
        results = payload.get("results", {})
        subtasks = payload.get("group_subtasks", {}).get(MATH_GROUP, [])
        children = [c for c in subtasks if c in results]
        if not children:
            continue
        raws = [_primary_metric(results[c]) for c in children]
        raws = [r for r in raws if r is not None]
        if not raws:
            continue
        if not all(r == 0.0 for r in raws):
            continue
        n_all_zero += 1
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
    """Compare pooled-rescale (correct) against rescale-and-average for GPQA.

    Returns ``(model, published, pooled, averaged, pooled_delta, averaged_delta)``
    for the models that expose both a pooled GPQA accuracy and per-subtask GPQA
    accuracies, so the ~0.4-point shift is quantified directly.
    """
    rows = []
    for name, payload in payloads.items():
        if name not in summary.index:
            continue
        published = summary.loc[name]
        if not isinstance(published, (int, float, np.floating)) or pd.isna(published):
            continue
        results = payload.get("results", {})
        block = results.get("leaderboard_gpqa")
        pooled_raw = block.get("acc_norm,none") if block else None
        subtasks = payload.get("group_subtasks", {}).get("leaderboard_gpqa", [])
        per_sub = []
        configs = payload.get("configs", {})
        for child in subtasks:
            if child not in results:
                continue
            raw = _primary_metric(results[child])
            if raw is None:
                continue
            base = _baseline_from_config(child, configs.get(child, {}))
            per_sub.append(_normalise(raw, base))
        if not isinstance(pooled_raw, (int, float)) or not per_sub:
            continue
        pooled = _normalise(float(pooled_raw), GPQA_BASELINE)
        averaged = float(np.mean(per_sub))
        rows.append({
            "model": name,
            "published": float(published),
            "pooled": pooled,
            "averaged": averaged,
            "pooled_delta": pooled - float(published),
            "averaged_delta": averaged - float(published),
        })
    return pd.DataFrame(rows)


def main() -> int:
    detailed = require(ATT_C / "detailed_results")
    summary_path = require(ATT_C / "leaderboard_cleaned.csv")

    print("parsing per-task records ...")
    records, damaged = load_detailed_results(detailed)
    payloads = load_payloads(detailed)
    print(f"  usable records         : {len(records):,}")
    print(f"  payloads loaded        : {len(payloads):,}")

    summary = pd.read_csv(summary_path)
    summary = summary.drop_duplicates(subset="Model", keep="first").set_index("Model")

    math_col = "MATH Lvl 5"
    gpqa_col = "GPQA"

    # --- MATH root cause ----------------------------------------------------
    math_zero, math_all_zero = math_zero_match_models(payloads, summary[math_col])
    print(f"\nMATH Lvl 5: {math_all_zero} models with all-zero C8 exact_match; "
          f"{len(math_zero)} of those are nonzero in the summary (irreconcilable)")
    if not math_zero.empty:
        print("  top examples (summary score -> C8 all-zero):")
        for _, row in math_zero.head(8).iterrows():
            print(f"    {row['model'][:48]:<48} summary {row['summary_score']:>6.1f}  "
                  f"C8 exact_match=0 in {row['n_subtasks']} subtasks")

    # --- GPQA root cause ----------------------------------------------------
    gpqa = gpqa_pooled_vs_averaged(payloads, summary[gpqa_col])
    print(f"\nGPQA: {len(gpqa)} models expose both pooled and per-subtask accuracies")
    if not gpqa.empty:
        pd_med = gpqa["pooled_delta"].abs().median()
        av_med = gpqa["averaged_delta"].abs().median()
        pd_within = float((gpqa["pooled_delta"].abs() <= 0.5).mean())
        av_within = float((gpqa["averaged_delta"].abs() <= 0.5).mean())
        print(f"  median |delta|  pooled-rescale {pd_med:.4f}  rescale-and-average {av_med:.4f}")
        print(f"  within 0.5pt    pooled-rescale {pd_within:.1%}  rescale-and-average {av_within:.1%}")

    # --- write the diagnosis ------------------------------------------------
    tables = ensure(RESULTS / "tables")
    lines = [
        "# Q4 C8 diagnosis: why MATH and GPQA initially failed reconciliation",
        "",
        "Generated by `scripts/q4_panel_diagnose.py`. Do not edit by hand.",
        "",
        "The acceptance test in `q4-c8-reconciliation.md` rebuilds the six",
        "dimensions from the raw per-task records and compares them to the",
        "published summary. Four reproduce exactly; this page is the root-cause",
        "analysis for the two that did not, and why the tolerance was not lowered",
        "to make them pass.",
        "",
        "## MATH Lvl 5 — a source mismatch, not a normalisation error",
        "",
        f"{math_all_zero} models carry `exact_match = 0` in every MATH subtask of",
        f"C8. {len(math_zero)} of those are scored **above zero** by the summary,",
        "which is irreconcilable: no normalisation turns a zero exact-match into a",
        "nonzero score — the formula is `max(0, (raw - baseline) / (1 - baseline))",
        "* 100`, which is zero whenever `raw` is zero. The remaining",
        f"{math_all_zero - len(math_zero)} are zero in the summary too, so they are",
        "consistent rather than mismatched.",
        "",
        "The data description records the upstream sources: C1 is built from",
        "`open-llm-leaderboard-old/results` and C8 from `open-llm-leaderboard",
        "/results`, two different Hugging Face datasets. MATH Lvl 5 is therefore",
        "**quarantined** for per-task analysis: its summary score is retained, but",
        "the per-subtask MATH records are not used as evidence about any model's",
        "math ability.",
        "",
    ]
    if not math_zero.empty:
        lines.append("| Model | Summary MATH | C8 subtasks all zero |")
        lines.append("| --- | ---: | ---: |")
        for _, row in math_zero.head(10).iterrows():
            lines.append(f"| `{row['model']}` | {row['summary_score']:.1f} | {row['n_subtasks']} |")
    else:
        lines.append("(No zero-exact-match models found — nothing to quarantine.)")
    lines += [
        "",
        "## GPQA — a normalisation error, since fixed",
        "",
        "GPQA is a grouped task (main / diamond / extended) whose three subtasks",
        "have very different sample sizes. The harness **pools** their accuracy",
        "into one number and rescales that against the 4-way random baseline; the",
        "first pass instead rescale-and-average the subtasks individually, which",
        "weights them equally and shifts the result by about 0.4 points.",
        "",
    ]
    if not gpqa.empty:
        lines += [
            f"| Metric | median \\|delta\\| | within 0.5 pt |",
            "| --- | ---: | ---: |",
            f"| pooled, then rescaled | {gpqa['pooled_delta'].abs().median():.4f} | "
            f"{(gpqa['pooled_delta'].abs() <= 0.5).mean():.1%} |",
            f"| rescaled per subtask, then averaged | {gpqa['averaged_delta'].abs().median():.4f} | "
            f"{(gpqa['averaged_delta'].abs() <= 0.5).mean():.1%} |",
            "",
        ]
    lines += [
        "Using the harness's own pooled accuracy closes the gap, so GPQA is",
        "**reconciled** and is not quarantined.",
        "",
        "## Consequence for downstream work",
        "",
        "Five of six dimensions are usable for per-task analysis (IFEval, BBH,",
        "GPQA, MUSR, MMLU-PRO). MATH Lvl 5's *summary* score is usable, but its",
        "per-subtask records are not, because they describe a different evaluation",
        "run than the score they are compared against.",
        "",
    ]
    out = tables / "q4-c8-diagnosis.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"\nwrote {out.relative_to(Path(__file__).resolve().parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
