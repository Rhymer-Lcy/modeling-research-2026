"""Self-test for scripts/paper_figures.py: its checks must be able to fail.

Loads the accepted inputs, requires the unmodified data to validate, then plants
one error at a time in an in-memory copy and requires ``validate`` to reject each.
Nothing is written.

    conda run -n modeling-research-2026 --no-capture-output python scripts/paper_figures_selftest.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import paper_figures as pf  # noqa: E402


def first(rows, **match):
    hits = [r for r in rows if all(r.get(k) == v for k, v in match.items())]
    assert hits, match
    return hits[0]


def mutate_representative_row(d):
    first(d["q3_context"]["rows"], context_tokens=8192, budget_flops=1e22)["n_parameters_raw"] *= 1.01


def mutate_transition_allocation(d):
    a = first(d["q3_regimes"]["analyses"], context_tokens=4096)
    t = first(a["thresholds"], name="stationary_reaches_D_max")
    t["at"]["n_parameters_raw"] *= 1.001


def mutate_elasticity(d):
    a = first(d["q3_regimes"]["analyses"], context_tokens=2048)
    a["regime_map"][0]["analytic_n_elasticity"] += 1e-3


def mutate_upper_corner(d):
    first(d["q3_context"]["rows"], context_tokens=131072, budget_flops=1e24)["d_tokens_raw"] *= 1.0001


def mutate_quality_g1(d):
    d["q3_quality"]["raw_family_analysis"]["families"]["power"]["value_at_q_1_flops_per_token"] *= 1.0001


def mutate_quality_crossing(d):
    d["q3_quality"]["raw_family_analysis"]["pairs"][0]["crossings"][0]["q"] *= 1.001


def mutate_q4_point(d):
    d["q4"]["headline"][12]["point"] += 0.05


def mutate_q4_interval(d):
    d["q4"]["headline"][24]["with_backtest"] = (61.0, 72.28)


def mutate_q1_drop_row(d):
    d["q1"]["rows"].pop(5)


def mutate_q1_role(d):
    d["q1"]["rows"][0]["role"] = "held_out_same_scale_60M"


MUTANTS = [
    ("representative-budget allocation moved off the regime power law", mutate_representative_row),
    ("transition allocation moved", mutate_transition_allocation),
    ("regime elasticity changed", mutate_elasticity),
    ("upper corner differs between contexts", mutate_upper_corner),
    ("raw g(1) changed", mutate_quality_g1),
    ("crossing location changed", mutate_quality_crossing),
    ("12-month continuation not level + trend x t", mutate_q4_point),
    ("24-month interval no longer contains the point", mutate_q4_interval),
    ("one Question 1 row missing", mutate_q1_drop_row),
    ("unknown validation role", mutate_q1_role),
]


def main() -> int:
    data = pf.load_inputs()
    pf.validate(copy.deepcopy(data))
    print("baseline: accepted inputs validate")
    failures = 0
    for label, mutate in MUTANTS:
        d = copy.deepcopy(data)
        mutate(d)
        try:
            pf.validate(d)
        except AssertionError as exc:
            print(f"KILLED    {label}: {str(exc)[:110]}")
        else:
            failures += 1
            print(f"SURVIVED  {label}")
    print(f"mutants {len(MUTANTS)}, killed {len(MUTANTS) - failures}")
    print("RESULT: " + ("PASS" if failures == 0 else "FAIL"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
