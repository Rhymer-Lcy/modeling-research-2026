"""Mutation self-test for the Q4 panel pipeline.

A check that has never been observed to reject anything is not a check. Each
case below either asserts a well-formed invariant holds, or breaks exactly one
rule and asserts the pipeline rejects it. The count of assertions is fixed, so a
case silently dropped from the list still fails.

The checks are the load-bearing invariants of the panel:

* name normalisation collapses case/spacing/punctuation but never drops a
  version suffix;
* the score rescaling never turns a zero raw score into a nonzero one;
* the C4 linkage is exact — a mutated name must not link (no fuzzy matching);
* the built panel is one row per model with valid stratum/date/open-weight
  values.

Run:  python scripts/q4_panel_selftest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.panel.c4_link import link_c4  # noqa: E402
from src.panel.leaderboard import _normalise  # noqa: E402
from src.panel.matching import normalize  # noqa: E402
from src.panel.panel import build_panel  # noqa: E402
from src.panel.sources import load_c4  # noqa: E402
from src.panel.strata import stratum_from_coarse  # noqa: E402

RESULTS: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    RESULTS.append((name, bool(ok)))
    print(f"  [{'ok' if ok else 'FAIL'}]  {name}")


def expect_true(name: str, fn) -> None:
    check(name, fn() is True)


def expect_false(name: str, fn) -> None:
    check(name, fn() is False)


print("Q4 panel pipeline mutation self-test")
print()

print(" name normalisation")
expect_true("collapses case and separators",
            lambda: normalize("A / B-C") == normalize("a_b c"))
expect_true("collapses repeated punctuation",
            lambda: normalize("meta--llama//3") == normalize("meta llama 3"))
expect_false("does not drop a version suffix",
             lambda: normalize("Yi-1.5-34B-Chat") == normalize("Yi-1.5-34B"))

print(" score rescaling")
expect_true("zero raw stays zero",
            lambda: _normalise(0.0, 1 / 4) == 0.0)
expect_true("random guess maps to zero",
            lambda: _normalise(1 / 4, 1 / 4) == 0.0)
expect_true("perfect generative score is 100",
            lambda: _normalise(1.0, 0.0) == 100.0)
expect_true("monotonic in the raw score",
            lambda: _normalise(0.6, 0.25) > _normalise(0.5, 0.25))

print(" stratum mapping")
expect_true("base maps to A", lambda: stratum_from_coarse("base") == "A")
expect_true("chat maps to B", lambda: stratum_from_coarse("chat") == "B")
expect_true("finetuned maps to C", lambda: stratum_from_coarse("finetuned") == "C")
expect_true("merge maps to D", lambda: stratum_from_coarse("merge") == "D")
expect_true("multimodal maps to E", lambda: stratum_from_coarse("multimodal") == "E")

print(" C4 linkage (deterministic, no fuzzy)")
c4 = load_c4()
linked = link_c4(pd.DataFrame({"model": ["google/gemma-2-9b", "meta-llama/Llama-3.1-8B-Instruct",
                                         "not-a-real-org/definitely-not-a-model-xyzzy"]}), c4)
real_links = int((linked["link_method"] != "unlinked").sum())


def real_model_links() -> bool:
    # At least one of the two well-known models must link deterministically.
    return real_links >= 1


expect_true("a known model links deterministically", real_model_links)
expect_true("an unknown model stays unlinked",
            lambda: linked.iloc[2]["link_method"] == "unlinked")


def typo_does_not_link() -> bool:
    # Mutate a *linked* model's name by one character: if the join were fuzzy it
    # would still match, so this failing is the proof the join is exact.
    panel = build_panel()
    linked_row = panel[panel["link_method"] != "unlinked"].iloc[0]
    mutated = linked_row["model"] + "x"
    probe = link_c4(pd.DataFrame({"model": [mutated]}), c4)
    return probe.iloc[0]["link_method"] == "unlinked"


expect_true("a mutated name does not link (exact join)", typo_does_not_link)

print(" panel invariants")
panel = build_panel()
expect_true("one row per model",
            lambda: int(panel["model"].nunique()) == len(panel))
expect_true("no duplicate model paths",
            lambda: int(panel.duplicated(subset=["model"]).sum()) == 0)
expect_true("every stratum is a known code",
            lambda: set(panel["stratum"].unique()) <= {"A", "B", "C", "D", "E", "unknown"})
expect_true("every open_weights value is yes/no/unknown",
            lambda: set(panel["open_weights"].unique()) <= {"yes", "no", "unknown"})
expect_true("every date_confidence is primary/fallback/none",
            lambda: set(panel["date_confidence"].unique()) <= {"primary", "fallback", "none"})

print()
failed = [name for name, ok in RESULTS if not ok]
EXPECTED = 20
if len(RESULTS) != EXPECTED:
    print(f"RESULT: FAIL (expected {EXPECTED} assertions, ran {len(RESULTS)})")
    sys.exit(1)
if failed:
    print(f"RESULT: FAIL ({len(failed)} of {len(RESULTS)} assertions failed)")
    for name in failed:
        print(f"  - {name}")
    sys.exit(1)
print(f"RESULT: PASS ({len(RESULTS)} assertions)")
sys.exit(0)
