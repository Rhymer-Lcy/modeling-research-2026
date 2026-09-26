"""Generate the Q3 budget regime map and structural-transition thresholds.

For each observed C7 context: the regime ``R(C)`` (saturation plus complete
active bound set) over the organizer's declared budget span, every candidate
threshold with its disposition, the verified below/at/above probes of each
retained transition, and each regime's analytic and numerical budget
elasticities of N* and D*.  Budgets other than the three representative values
are model-conditional continuation inside the declared span, not new
observations.  The C7 grid is not interpolated.

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_regime_analysis.py
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.alloc import (  # noqa: E402
    BaselineCompute,
    analyze_regime_thresholds,
    install_q3_input_guard,
    load_all_accepted_interfaces,
    load_classic_if3,
    load_source_receipt,
    solve_baseline,
)
from src.alloc.regime import (  # noqa: E402
    CATEGORY_ACTIVE_SET,
    CATEGORY_FEASIBILITY_ONSET,
    CATEGORY_SLACK_ONSET,
    CATEGORY_SUPPORT_BOUNDARY,
    ELASTICITY_STEP,
    EMPIRICAL_TRANSITION,
    PROBE_OFFSET,
)
from src.alloc.report import fmt, write_artifacts  # noqa: E402

ELASTICITY_TOLERANCE = 1e-6


def build_payload() -> dict[str, Any]:
    load_all_accepted_interfaces()
    classic = load_classic_if3()
    receipt = load_source_receipt()
    analyses = []
    for context in receipt.contexts_tokens:
        analysis = analyze_regime_thresholds(classic, receipt, context)
        for interval in analysis.regime_map:
            if (abs(interval.numeric_n_elasticity - interval.analytic_n_elasticity) > ELASTICITY_TOLERANCE
                    or abs(interval.numeric_d_elasticity - interval.analytic_d_elasticity) > ELASTICITY_TOLERANCE):
                raise RuntimeError("numerical elasticity disagrees with its regime at L_ctx=" + str(context))
        primary = []
        for budget in receipt.budgets_flops:
            result = solve_baseline(classic, BaselineCompute.create(receipt, budget, context))
            interval = next(item for item in analysis.regime_map if item.lower_flops <= budget <= item.upper_flops)
            primary.append({"budget_flops": budget, "regime": result.regime,
                            "regime_map_interval": [interval.lower_flops, interval.upper_flops]})
        by_name = {item.name: item for item in analysis.thresholds}
        low, _ = analysis.span_flops
        # The fixed explanatory sentences of the report are asserted here, so they cannot go stale.
        if not (analysis.c_min_flops < low and by_name["stationary_reaches_N_min"].budget_flops < low
                and by_name["stationary_reaches_N_max"].budget_flops > analysis.c_box_flops
                and by_name["stationary_reaches_D_min"].budget_flops < analysis.c_min_flops):
            raise RuntimeError("out-of-span candidate geometry changed at L_ctx=" + str(context))
        if [interval.regime for interval in analysis.regime_map] != [
            "SATURATED:interior", "SATURATED:D_max", "SLACK:N_max+D_max"
        ]:
            raise RuntimeError("regime sequence changed at L_ctx=" + str(context) + "; revise the report text")
        analyses.append({
            "context_tokens": analysis.context_tokens,
            "kappa_flops_per_parameter_token": analysis.kappa,
            "c_min_flops": analysis.c_min_flops,
            "c_box_flops": analysis.c_box_flops,
            "declared_span_flops": list(analysis.span_flops),
            "thresholds": [asdict(item) for item in analysis.thresholds],
            "retained_transitions": [item.name for item in analysis.retained],
            "regime_map": [asdict(item) for item in analysis.regime_map],
            "primary_grid": primary,
        })
    return {
        "schema_version": "q3-regime-thresholds-v2",
        "purpose": "T-010 budget regime map and structural-transition identification",
        "classic_if3_sha256": classic.sha256,
        "claim_level": "model-conditional continuation of the accepted classic IF3 law; not observation",
        "definition": {
            "regime": "R(C) = INFEASIBLE for C < C_min; otherwise (SATURATED or SLACK, complete active IF3 box-bound set)",
            "structural_transition": "a budget at which R(C) changes; equivalently a jump of the budget elasticities "
                                     "d log N*/d log C and d log D*/d log C",
            "identification": "candidates C_min, C_box and the budgets where the stationary path reaches each box "
                              "bound; retained only if the constrained optimizer changes regime between probes at "
                              "relative offsets -/+" + repr(PROBE_OFFSET) + " inside the declared span",
            "elasticity_check": "central finite difference at relative step " + repr(ELASTICITY_STEP)
                                + " at each interval's geometric midpoint, tolerance " + repr(ELASTICITY_TOLERANCE),
        },
        "categories": {
            CATEGORY_ACTIVE_SET: "validity-boundary active-set transition (model statement)",
            CATEGORY_SLACK_ONSET: "onset of budget slack at the validity ceiling C_box (model statement)",
            CATEGORY_FEASIBILITY_ONSET: "onset of feasibility at C_min (model statement)",
            CATEGORY_SUPPORT_BOUNDARY: "boundary of the declared analysis/source budget span",
            "empirical_physical_transition": EMPIRICAL_TRANSITION,
        },
        "source_supported_budgets_flops": list(receipt.budgets_flops),
        "observed_contexts_tokens": list(receipt.contexts_tokens),
        "cost_parity_identity": {"tokens": receipt.parity_tokens,
                                 "role": "base/attention cost parity only; not a regime threshold"},
        "analyses": analyses,
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Q3 budget regimes and structural transitions",
        "",
        "Generated by `scripts/q3_regime_analysis.py`. Do not edit by hand.",
        "",
        "**Definition.** At a fixed observed context, the regime of a budget `C` is `INFEASIBLE` when",
        "`C < C_min`, and otherwise the pair (budget `SATURATED` or `SLACK`, complete set of IF3 box",
        "bounds active at the optimum). A *structural transition* is a budget where the regime changes.",
        "Inside one regime the optimum is a fixed power law of `C`, so a transition is exactly a jump in",
        "the budget elasticities `d log N*/d log C` and `d log D*/d log C`.",
        "",
        "**Identification.** Candidates are `C_min = kappa N_min D_min`, `C_box = kappa N_max D_max`, and",
        "the budgets where the unconstrained stationary path reaches each box bound. A candidate is",
        "retained only if the constrained optimizer changes regime between probes at relative offsets",
        "`-/+1e-6` around it. Probes and the regime map use budgets inside the organizer's declared span",
        "`[1e19, 1e24]` only, as labelled model-conditional continuation; the three representative",
        "budgets remain the primary grid, and the C7 context grid is not interpolated.",
        "",
        "**What the transitions are.** The `D_max` transition and the slack onset at `C_box` are",
        "properties of the accepted law's validity box, the region where the law was identified. They",
        "are model statements, not observations, and " + EMPIRICAL_TRANSITION + ".",
        "",
        "## Regime map inside the declared span",
        "",
        "| L_ctx (tokens) | From C (FLOPs) | To C (FLOPs) | Regime | d log N*/d log C | d log D*/d log C | Upper edge |",
        "| ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for analysis in payload["analyses"]:
        for interval in analysis["regime_map"]:
            lines.append(
                "| " + str(analysis["context_tokens"]) + " | " + fmt(interval["lower_flops"])
                + " | " + fmt(interval["upper_flops"]) + " | `" + interval["regime"] + "`"
                + " | " + fmt(interval["analytic_n_elasticity"], 6) + " | " + fmt(interval["analytic_d_elasticity"], 6)
                + " | " + interval["upper_kind"] + " |"
            )
    lines += [
        "",
        "Elasticities are analytic for each regime (interior: `beta/(alpha+beta)` and `alpha/(alpha+beta)`;",
        "`D_max` active: 1 and 0; slack upper corner: 0 and 0) and agree with a numerical central",
        "difference to within 1e-6 at every interval midpoint.",
        "",
        "## Retained transitions and their verification",
        "",
        "| L_ctx (tokens) | Transition | Category | C (FLOPs) | Parameter-dependent | Just below | At | Just above |",
        "| ---: | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for analysis in payload["analyses"]:
        for item in analysis["thresholds"]:
            if item["disposition"] != "RETAINED_REGIME_TRANSITION":
                continue
            lines.append(
                "| " + str(analysis["context_tokens"]) + " | `" + item["name"] + "` | " + item["category"]
                + " | " + fmt(item["budget_flops"]) + " | " + ("yes" if item["parameter_dependent"] else "no")
                + " | `" + item["below"]["regime"] + "` | `" + item["at"]["regime"] + "` | `" + item["above"]["regime"] + "` |"
            )
    lines += [
        "",
        "## Candidates not analysed as transitions",
        "",
        "| L_ctx (tokens) | Candidate | C (FLOPs) | Disposition |",
        "| ---: | --- | ---: | --- |",
    ]
    for analysis in payload["analyses"]:
        for item in analysis["thresholds"]:
            if item["disposition"] == "RETAINED_REGIME_TRANSITION":
                continue
            lines.append("| " + str(analysis["context_tokens"]) + " | `" + item["name"] + "` | "
                         + fmt(item["budget_flops"]) + " | " + item["disposition"] + " |")
    lines += [
        "",
        "`C_min` and the budget where the stationary path leaves `N_min` lie below `1e19` at every observed",
        "context: every budget in the declared span is feasible, and genuine low-budget infeasibility does",
        "not occur there. The stationary path reaches `N_max` only above `C_box` and `D_min` only below",
        "`C_min`, so neither is a transition. Out-of-span candidates are recorded, not analysed.",
        "",
        "## Primary grid",
        "",
        "| L_ctx (tokens) | C = 1e19 | C = 1e22 | C = 1e24 |",
        "| ---: | --- | --- | --- |",
    ]
    for analysis in payload["analyses"]:
        cells = ["`" + item["regime"] + "`" for item in analysis["primary_grid"]]
        lines.append("| " + str(analysis["context_tokens"]) + " | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Across the three representative budgets the model-conditional allocation changes structurally",
        "twice at every observed context: from the interior power law to the `D_max`-bound regime, and",
        "from there to the upper corner with unused budget. `L_ctx = 6/eta = 30000` tokens is a",
        "base/attention cost-parity identity only and is not one of these thresholds. Parameter",
        "robustness of the `D_max` threshold is in `q3-loo-robustness.md`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    install_q3_input_guard()
    payload = build_payload()
    write_artifacts("q3-regime-thresholds", payload, markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
