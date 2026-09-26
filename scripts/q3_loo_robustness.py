"""Propagate the published Q2 leave-one-trajectory-out vectors through the Q3 allocation.

The nominal accepted IF3, the published full fit (the nominal at the same six
significant digits as the LOO table) and all eight complete published LOO
vectors are solved at every source-supported budget and observed context, and
the parameter-dependent regime threshold is recomputed for each.  Results are
reported as leave-one-trajectory-out robustness ranges at published parameter
precision: not confidence, bootstrap or posterior intervals.  The half-unit
rounding box of every published vector is propagated through its 32 corners to
judge whether each LOO spread is resolved at the released precision.

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_loo_robustness.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.alloc import (  # noqa: E402
    BaselineCompute,
    build_loo_sensitivity_models,
    install_q3_input_guard,
    load_all_accepted_interfaces,
    load_classic_if3,
    load_loo_robustness,
    load_source_receipt,
    rounding_corner_laws,
    solve_baseline,
    stationary_threshold,
)
from src.alloc.report import fmt, write_artifacts  # noqa: E402
from src.alloc.robustness import ROLE_LOO, ROLE_NOMINAL, ROLE_PUBLISHED_NOMINAL  # noqa: E402

OUTPUTS = ("n_parameters_raw", "d_tokens_raw", "predicted_loss")


def outcome(law: Any, receipt: Any, budget: float, context: int) -> dict[str, Any]:
    result = solve_baseline(law, BaselineCompute.create(receipt, budget, context))
    return {"n_parameters_raw": result.n_parameters, "d_tokens_raw": result.d_tokens,
            "predicted_loss": result.predicted_loss, "regime": result.regime}


def span(values: list[float]) -> dict[str, float]:
    return {"minimum": min(values), "maximum": max(values)}


def resolution(loo_values: list[float], corner_envelopes: list[tuple[float, float]]) -> dict[str, Any]:
    """Compare the LOO spread with the largest single-vector rounding envelope."""
    loo_spread = max(loo_values) - min(loo_values)
    rounding_width = max(high - low for low, high in corner_envelopes)
    if loo_spread == 0.0 and rounding_width == 0.0:
        verdict = "DEGENERATE_FIXED_BY_BOUNDS"
    elif loo_spread > 2.0 * rounding_width:
        verdict = "RESOLVED_AT_PUBLISHED_PRECISION"
    else:
        verdict = "NOT_RESOLVED_AT_PUBLISHED_PRECISION"
    return {
        "loo_spread": loo_spread,
        "max_single_vector_rounding_width": rounding_width,
        "rounding_widened_loo_range": {"minimum": min(low for low, _ in corner_envelopes),
                                       "maximum": max(high for _, high in corner_envelopes)},
        "verdict": verdict,
    }


def build_payload() -> dict[str, Any]:
    load_all_accepted_interfaces()
    classic = load_classic_if3()
    receipt = load_source_receipt()
    evidence = load_loo_robustness()
    models = build_loo_sensitivity_models(classic, evidence)
    loo_models = [model for model in models if model.role == ROLE_LOO]
    published = [model for model in models if model.published_vector is not None]
    corners = {model.label: rounding_corner_laws(classic, model.published_vector) for model in published}

    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for budget in receipt.budgets_flops:
        for context in receipt.contexts_tokens:
            by_model = {model.label: outcome(model.law, receipt, budget, context) for model in models}
            for model in models:
                rows.append({"budget_flops": budget, "context_tokens": context, "model_label": model.label,
                             "role": model.role, **by_model[model.label]})
            corner_outcomes = {label: [outcome(law, receipt, budget, context) for law in laws]
                               for label, laws in corners.items()}
            nominal = by_model["nominal_accepted_if3"]
            reference = by_model["published_full_fit"]
            summary: dict[str, Any] = {
                "budget_flops": budget,
                "context_tokens": context,
                "nominal": nominal,
                "published_full_fit": reference,
                "regimes": sorted({by_model[model.label]["regime"] for model in models}),
                "regime_agreement": len({by_model[model.label]["regime"] for model in models}) == 1,
            }
            for field in OUTPUTS:
                loo_values = [by_model[model.label][field] for model in loo_models]
                envelopes = [(min(item[field] for item in corner_outcomes[label]),
                              max(item[field] for item in corner_outcomes[label])) for label in corners]
                summary[field] = {
                    "loo_range": span(loo_values),
                    "loo_relative_spread": (max(loo_values) - min(loo_values)) / nominal[field],
                    "nominal_minus_published_full_fit_relative": (nominal[field] - reference[field]) / nominal[field],
                    "rounding": resolution(loo_values, envelopes),
                }
            summaries.append(summary)

    thresholds: list[dict[str, Any]] = []
    for context in receipt.contexts_tokens:
        kappa = receipt.kappa(context)
        box = classic.validity_box
        for label, coordinate, bound in (("stationary_reaches_D_max", "D", box["D"][1]),
                                         ("stationary_reaches_N_min", "N", box["N"][0])):
            values = {model.label: stationary_threshold(model.law.params, kappa, coordinate, bound) for model in models}
            loo_values = [values[model.label] for model in loo_models]
            envelopes = []
            for model_label, laws in corners.items():
                corner_values = [stationary_threshold(law.params, kappa, coordinate, bound) for law in laws]
                envelopes.append((min(corner_values), max(corner_values)))
            thresholds.append({
                "context_tokens": context,
                "threshold": label,
                "retained_inside_declared_span": label == "stationary_reaches_D_max",
                "nominal_flops": values["nominal_accepted_if3"],
                "published_full_fit_flops": values["published_full_fit"],
                "loo_values_flops": {model.label: values[model.label] for model in loo_models},
                "loo_range_flops": span(loo_values),
                "loo_relative_spread": (max(loo_values) - min(loo_values)) / values["nominal_accepted_if3"],
                "rounding": resolution(loo_values, envelopes),
                "primary_budgets_crossed_by_loo_range": [
                    budget for budget in receipt.budgets_flops if min(loo_values) <= budget <= max(loo_values)
                ],
            })
        thresholds.append({
            "context_tokens": context,
            "threshold": "C_box",
            "retained_inside_declared_span": True,
            "nominal_flops": kappa * box["N"][1] * box["D"][1],
            "parameter_dependent": False,
            "note": "geometry only (fixed box and receipt kappa); no parameter uncertainty",
        })

    return {
        "schema_version": "q3-loo-robustness-v3",
        "purpose": "T-010 leave-one-trajectory-out robustness of the baseline allocation and its thresholds",
        "label": evidence.precision_label,
        "classic_if3_sha256": classic.sha256,
        "claim_level": "model-conditional robustness ranges; not confidence, bootstrap or posterior intervals",
        "quality_coordinate": "Q0",
        "loo_evidence": {
            "path": evidence.relative_path,
            "sha256": evidence.sha256,
            "git_blob_sha1": evidence.git_blob_sha1,
            "published_format": "format(x, '.6g') in scripts/q2_uncertainty.py",
            "dropped_trajectories_billions": [vector.label for vector in evidence.vectors],
            "limitation": evidence.limitation,
        },
        "models": [
            {"label": model.label, "role": model.role, "dropped_trajectory_billions": model.dropped_trajectory_billions,
             "parameters": dict(model.law.params),
             "is_accepted_if3": model.role == ROLE_NOMINAL,
             "published_strings": dict(model.published_vector.published_strings) if model.published_vector else None}
            for model in models
        ],
        "reference_roles": {
            ROLE_NOMINAL: "accepted IF3 at full precision; the canonical point estimate",
            ROLE_PUBLISHED_NOMINAL: "accepted IF3 printed at six significant digits; like-for-like LOO reference",
            ROLE_LOO: "published alternative fit omitting one trajectory; in-memory sensitivity law, not IF3",
        },
        "rounding_method": "each published vector's half-unit box (six significant digits) propagated through "
                           "its 32 corners; first-order envelope. RESOLVED means the LOO spread exceeds twice "
                           "the widest single-vector rounding envelope.",
        "rows": rows,
        "summaries": summaries,
        "thresholds": thresholds,
        "not_merged_with": "bootstrap marginal intervals and profile ratios (see q3-allocation.json and "
                           "results/tables/q2-uncertainty-robustness.md); no joint draws are synthesized",
    }


def markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Q3 leave-one-trajectory-out robustness",
        "",
        "Generated by `scripts/q3_loo_robustness.py`. Do not edit by hand.",
        "",
        "**" + payload["label"].capitalize() + ".** The eight complete parameter vectors of the accepted",
        "`results/tables/q2-uncertainty-robustness.md` (SHA-256 `" + payload["loo_evidence"]["sha256"] + "`) are each",
        "bound to the fixed accepted IF3 validity box as a separately labelled sensitivity law and solved",
        "with the same corrected `kappa N D <= C` optimizer at every representative budget and observed",
        "context. Ranges are min/max over the eight LOO fits. They are robustness ranges, not confidence,",
        "bootstrap or posterior intervals, and no joint draws are synthesized from marginal intervals.",
        "",
        "Two references: the nominal accepted IF3 at full precision, and the published full fit (the same",
        "law printed at six significant digits, like the LOO vectors). A rounding verdict compares each LOO",
        "spread with the widest envelope obtained by moving one published vector through the 32 corners",
        "of its half-unit rounding box.",
        "",
        payload["loo_evidence"]["limitation"],
        "",
        "## Allocation ranges",
        "",
        "| C (FLOPs) | L_ctx | Regime (all fits) | Nominal N* | LOO N* range | N verdict | Nominal D* | LOO D* range | D verdict | Nominal loss | LOO loss range | Loss verdict |",
        "| ---: | ---: | --- | ---: | --- | --- | ---: | --- | --- | ---: | --- | --- |",
    ]
    for item in payload["summaries"]:
        regime = item["regimes"][0] if item["regime_agreement"] else "DISAGREE: " + ", ".join(item["regimes"])
        cells = ["| " + fmt(item["budget_flops"]), str(item["context_tokens"]), "`" + regime + "`"]
        for field in OUTPUTS:
            data = item[field]
            cells += [fmt(item["nominal"][field]),
                      fmt(data["loo_range"]["minimum"]) + " – " + fmt(data["loo_range"]["maximum"]),
                      data["rounding"]["verdict"]]
        lines.append(" | ".join(cells) + " |")
    lines += [
        "",
        "`DEGENERATE_FIXED_BY_BOUNDS`: the output is fixed for every fit by the active bounds (at the slack",
        "upper corner) or by `D_max` and the saturated budget (`N* = C/(kappa D_max)`), which is legitimate;",
        "the predicted loss can still vary.",
        "`NOT_RESOLVED_AT_PUBLISHED_PRECISION`: the LOO spread is no larger than twice what rounding a",
        "single published vector to six significant digits can move the same output, so the released",
        "precision cannot distinguish the LOO fits for that output. Rounding-widened ranges are in the JSON.",
        "",
        "## Parameter-dependent threshold ranges",
        "",
        "| L_ctx | Threshold | Inside declared span | Nominal C (FLOPs) | LOO range (FLOPs) | LOO relative spread | Verdict | Primary budgets inside LOO range |",
        "| ---: | --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for item in payload["thresholds"]:
        if "loo_range_flops" not in item:
            continue
        lines.append(
            "| " + str(item["context_tokens"]) + " | `" + item["threshold"] + "` | "
            + ("yes" if item["retained_inside_declared_span"] else "no (below 1e19)")
            + " | " + fmt(item["nominal_flops"]) + " | " + fmt(item["loo_range_flops"]["minimum"]) + " – "
            + fmt(item["loo_range_flops"]["maximum"]) + " | " + fmt(item["loo_relative_spread"], 3)
            + " | " + item["rounding"]["verdict"] + " | "
            + (", ".join(fmt(value) for value in item["primary_budgets_crossed_by_loo_range"]) or "none") + " |"
        )
    crossed = [item for item in payload["thresholds"]
               if item.get("retained_inside_declared_span") and item.get("primary_budgets_crossed_by_loo_range")]
    agreement = all(item["regime_agreement"] for item in payload["summaries"])
    lines += [
        "",
        "`C_min` and `C_box` depend only on the fixed box and the receipt `kappa`, so they carry no parameter",
        "uncertainty. "
        + ("No LOO range of the retained `D_max` threshold contains a representative budget. "
           if not crossed else "Some LOO ranges of the retained `D_max` threshold contain a representative budget. ")
        + ("All nine fits place every representative budget in the same regime."
           if agreement else "The fits disagree on the regime of at least one representative budget."),
        "",
        "## Individual outcomes",
        "",
        "| C (FLOPs) | L_ctx | Model | Role | N* | D* | Predicted loss | Regime |",
        "| ---: | ---: | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| " + fmt(row["budget_flops"]) + " | " + str(row["context_tokens"]) + " | `" + row["model_label"]
            + "` | " + row["role"] + " | " + fmt(row["n_parameters_raw"]) + " | " + fmt(row["d_tokens_raw"])
            + " | " + fmt(row["predicted_loss"], 10) + " | `" + row["regime"] + "` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    install_q3_input_guard()
    payload = build_payload()
    if not all(item["regime_agreement"] for item in payload["summaries"]):
        print("note: LOO fits disagree on a primary-grid regime", file=sys.stderr)
    write_artifacts("q3-loo-robustness", payload, markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
