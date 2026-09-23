"""Q1 step 1: build the canonical 22-indicator representation and record it.

Streams the quality-signal files rather than loading them, asserts the schema
it depends on, and emits the scalarization contract as a table the manuscript
can cite. Also runs the secondary empirical check on the two binary classifier
orientations: the orientation itself is settled by first-party documentation,
and the data is used only to confirm it, not to decide it.

Run:  python scripts/q1_scalarize.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import lzma
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.paths import ATT_A, RESULTS, ensure, require  # noqa: E402
from src.quality import scalarize as sc  # noqa: E402

SAMPLE = "slimpajama_quality_signal_sample.jsonl.xz"


def stream(path: Path, limit: int | None = None) -> Iterator[dict]:
    with lzma.open(path, "rt", encoding="utf-8") as handle:
        for i, line in enumerate(handle):
            if limit is not None and i >= limit:
                return
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="read only the first N records (development aid)")
    args = parser.parse_args()

    path = require(ATT_A / SAMPLE)
    print(f"source: {path.name}")
    print(f"limit : {args.limit if args.limit else 'none (full file)'}")
    print()

    # ------------------------------------------------ pass 1: schema + ECDF
    # qurater's reduction needs the marginal distribution of each criterion, so
    # the criteria are collected first and the CDFs fitted before any record is
    # reduced. Doing it in one pass would make the first records use a CDF
    # estimated from almost nothing.
    qurater_cols: List[List[float]] = [[], [], [], []]
    domains: Counter = Counter()
    n_records = 0
    dim_seen: Dict[str, Counter] = {name: Counter() for name in sc.LIST_FIELDS}

    for record in stream(path, args.limit):
        n_records += 1
        domains[record.get("_source_domain", "(none)")] += 1
        for name in sc.LIST_FIELDS:
            dim_seen[name][len(record[name])] += 1
        for j, value in enumerate(record["qurater"]):
            qurater_cols[j].append(float(value))

    print(f"records read      : {n_records:,}")
    print(f"domains           : {dict(domains.most_common())}")
    print()
    print("list-field widths observed (the reductions depend on element order,")
    print("so a second width would invalidate the contract, not just a record):")
    for name in sc.LIST_FIELDS:
        widths = dict(dim_seen[name])
        expected = sc.EXPECTED_DIM[name]
        ok = list(widths) == [expected]
        print(f"  {name:<30} {widths}  expected {expected}  {'OK' if ok else '*** UNEXPECTED ***'}")
        if not ok:
            raise SystemExit(f"{name} has more than one width; stopping")
    print()

    sorted_cols = [np.sort(np.asarray(c, dtype=float)) for c in qurater_cols]

    def make_ecdf(sorted_values: np.ndarray):
        total = len(sorted_values)

        def ecdf(x: float) -> float:
            return float(np.searchsorted(sorted_values, x, side="right") / total)

        return ecdf

    qurater_ecdf = [make_ecdf(c) for c in sorted_cols]
    print("qurater criteria, marginal summaries (this is why a raw mean is not")
    print("the canonical reduction: the four are not on a common scale):")
    names = ["writing style", "required expertise", "facts and trivia", "educational value"]
    for name, col in zip(names, sorted_cols):
        print(f"  {name:<20} min {col[0]:>8.3f}  median {np.median(col):>8.3f}  "
              f"max {col[-1]:>8.3f}  sd {col.std(ddof=1):>7.3f}")
    corr = np.corrcoef(np.vstack([np.asarray(c) for c in qurater_cols]))
    print("  rank-free Pearson correlation between criteria:")
    for i, name in enumerate(names):
        print(f"    {name:<20} " + "  ".join(f"{corr[i, j]:+.3f}" for j in range(4)))
    print()

    # ------------------------------------------- pass 2: reduce to 22 scalars
    reduced_rows: List[Dict[str, float]] = []
    domain_of: List[str] = []
    for record in stream(path, args.limit):
        reduced_rows.append(sc.scalarize_record(record, qurater_ecdf))
        domain_of.append(record.get("_source_domain", "(none)"))

    matrix = np.array([[row[k] for k in sc.INDICATORS] for row in reduced_rows], dtype=float)
    print(f"canonical representation: {matrix.shape[0]:,} records x {matrix.shape[1]} indicators")
    if matrix.shape[1] != 22:
        raise SystemExit(f"expected 22 indicators, built {matrix.shape[1]}")
    print("  14 native scalars + 8 compressed list fields = 22, as the task defines.")
    print("  (The upstream dataset has 25 underlying signals because qurater packs")
    print("   four criteria. Expanding it would be a different indicator system and")
    print("   is kept for sensitivity only.)")
    print()

    # --------------------------------- secondary check on classifier orientation
    print("classifier orientation: settled by first-party documentation, confirmed")
    print("here as a secondary check only.")
    dom = np.array(domain_of)
    for field, claim in (("ad_en", "P(no ad) should be LOWER on web-crawl than on curated text"),
                         ("fluency_en", "P(fluent) should be LOWER on code than on prose")):
        col = matrix[:, sc.INDICATORS.index(field)]
        by_domain = {d: float(np.mean(col[dom == d])) for d in sorted(set(domain_of))}
        print(f"  {field}: {claim}")
        for d, v in sorted(by_domain.items(), key=lambda kv: kv[1]):
            print(f"      {d:<16} {v:.4f}")
        if field == "ad_en":
            web = by_domain.get("commoncrawl", by_domain.get("c4"))
            curated = by_domain.get("wikipedia")
            verdict = (web is not None and curated is not None and web < curated)
        else:
            code = by_domain.get("github")
            prose = by_domain.get("wikipedia")
            verdict = (code is not None and prose is not None and code < prose)
        print(f"      -> consistent with the documented order: {verdict}")
    print()

    # ------------------------------------------------------------- artifacts
    tables = ensure(RESULTS / "tables")
    lines = [
        "# Q1 scalarization contract: the canonical 22 indicators",
        "",
        "Generated by `scripts/q1_scalarize.py`. Do not edit by hand.",
        "",
        "The task defines **22** quality indicators: 14 stored as scalars and 8",
        "stored as multi-dimensional lists that must each be compressed to one",
        "scalar before modelling. That count is the contract. The upstream dataset",
        "carries 25 underlying signals because `qurater` packs four criteria into",
        "one field; expanding it would silently redefine the official indicator",
        "system, so component-level views are sensitivity analysis only.",
        "",
        "Element semantics are taken from the upstream dataset's own documentation,",
        "not inferred from field names. The clearest case is `ad_en`: it is ordered",
        "`[has_ad, no_ad]`, so its **second** element is the desirable one and the",
        "reduced indicator is already higher-is-better. Assuming the first element",
        "was the good one would invert the indicator with nothing downstream",
        "looking wrong.",
        "",
        "## The eight compressed fields",
        "",
        "| Field | Raw dim | Semantics | Transform | Range | Raw desirability | Final | Sensitivity |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for rec in sc.RECORDS:
        lines.append(
            f"| `{rec.field}` | {rec.raw_dim} | {rec.semantics} | {rec.transform} | "
            f"{rec.scalar_range} | {rec.raw_desirability} | {rec.final_direction} | "
            f"{rec.sensitivity} |"
        )
    lines += [
        "",
        "Evidence for each reduction:",
        "",
    ]
    for rec in sc.RECORDS:
        lines.append(f"- `{rec.field}`: {rec.evidence}")
    lines += [
        "",
        "## Why `qurater` is not a raw mean",
        "",
        "Its four criteria are separately calibrated latent scores, not a",
        "distribution: they do not sum to one and their marginals differ.",
        "",
        "| Criterion | Min | Median | Max | SD |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, col in zip(names, sorted_cols):
        lines.append(f"| {name} | {col[0]:.3f} | {np.median(col):.3f} | "
                     f"{col[-1]:.3f} | {col.std(ddof=1):.3f} |")
    lines += [
        "",
        "Each criterion is therefore mapped through its own empirical CDF before",
        "the four are averaged with equal weight. Unit weights are the right",
        "default for several positively correlated indicators of one construct:",
        "robust, and with no free parameter this data could identify.",
        "",
        "## Direction of all 22 indicators",
        "",
        "Every indicator must reach the model on a common higher-is-better scale.",
        "Three are judged genuinely non-monotone and are flagged here rather than",
        "forced into a direction; their desirability transform is fitted in the",
        "aggregation step and reported with it.",
        "",
        "| Indicator | Direction |",
        "| --- | --- |",
    ]
    for name in sc.INDICATORS:
        lines.append(f"| `{name}` | {sc.DIRECTIONS[name]} |")
    counts = Counter(sc.DIRECTIONS[n] for n in sc.INDICATORS)
    lines += [
        "",
        f"Totals: {counts['higher_better']} higher-is-better, "
        f"{counts['lower_better']} lower-is-better, "
        f"{counts['non_monotone']} non-monotone. "
        f"Sum {sum(counts.values())} = 22.",
        "",
    ]
    out = tables / "q1-scalarization-contract.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(Path(__file__).resolve().parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
