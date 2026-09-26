"""Generate the itemized Q3 provenance ledger.

Every load-bearing formula, coefficient, budget, context value, quality-cost
parameter, threshold and conclusion is one item.  Values are read from the
source-verified receipt, the accepted interfaces and the generated Q3 artifacts,
never typed here.  Each item names its authorized source (repository-relative
path plus SHA-256, Git blob or DOCX locator) or the ledger items it derives
from, the verified value, the transformation, a status and its limitation.
:func:`src.alloc.validate_ledger` rejects the ledger if any item lacks
provenance, rests on a PDF, screenshot or other forbidden source, or is
UNVERIFIED.

Run after the other Q3 generators:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_provenance_ledger.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.alloc import (  # noqa: E402
    install_q3_input_guard,
    load_all_accepted_interfaces,
    load_classic_if3,
    load_loo_robustness,
    load_source_receipt,
    repo_relative,
    validate_ledger,
)
from src.alloc.report import fmt, write_artifacts  # noqa: E402
from src.paths import TABLES  # noqa: E402


def artifact(name: str) -> tuple[dict[str, Any], str]:
    path = TABLES / name
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def build_ledger() -> list[dict[str, Any]]:
    receipt = load_source_receipt()
    interfaces = load_all_accepted_interfaces()
    classic = load_classic_if3()
    loo = load_loo_robustness()
    payload = receipt.payload
    records = {record["key"]: record for record in payload["source_verification"]["records"]}
    docx = payload["methodological_authority"]
    terms = {term["name"]: term for term in payload["terms"]}
    c7 = terms["context_length"]["supported_value_or_grid"]
    provenance = c7["direct_data_provenance"]

    def docx_source(*keys: str) -> list[dict[str, Any]]:
        return [{"kind": "canonical_docx", "path": docx["path"], "sha256": docx["sha256"],
                 "locator": records[key].get("math_locator", records[key]["locator"])} for key in keys]

    def verified(key: str) -> Any:
        return records[key]["verified_value"]

    def derived(*ids: str) -> list[dict[str, Any]]:
        return [{"kind": "ledger_item", "id": item} for item in ids]

    def q3(name: str, locator: str) -> dict[str, Any]:
        _, digest = artifact(name)
        return {"kind": "tracked_q3_artifact", "path": "results/tables/" + name, "sha256": digest, "locator": locator}

    if3 = {"kind": "accepted_interface", "path": repo_relative(classic.path), "sha256": classic.sha256,
           "locator": "params; validity_box"}
    allocation, _ = artifact("q3-allocation.json")
    regimes, _ = artifact("q3-regime-thresholds.json")
    robustness, _ = artifact("q3-loo-robustness.json")
    quality, _ = artifact("q3-quality-cost-sensitivity.json")
    by_budget = {row["budget_flops"]: row for row in allocation["allocations"]}

    items: list[dict[str, Any]] = [
        {"id": "S1", "category": "formula", "value": verified("budget_inequality"),
         "sources": docx_source("budget_inequality", "total_budget_three_parts"),
         "derivation": "organizer wording 'total cost does not exceed C' verified at its paragraph",
         "status": "VERIFIED", "limitation": "an inequality; saturation holds only for C < C_box"},
        {"id": "S2", "category": "coefficient", "value": verified("base_training_coefficient"),
         "sources": docx_source("base_training_coefficient", "flops_unit_definition"),
         "derivation": "parsed from structured OMML {C}_{train}=6ND", "status": "VERIFIED",
         "limitation": "the organizer calls it the Chinchilla approximation"},
        {"id": "S3", "category": "coefficient", "value": verified("attention_eta"),
         "sources": docx_source("attention_compute_form", "attention_eta"),
         "derivation": "parsed from structured OMML eta=2x{10}^{-4}", "status": "VERIFIED",
         "limitation": "the organizer calls C_attn a simplified compute proxy"},
        {"id": "S4", "category": "budget", "value": [verified("representative_budget_low"),
                                                      verified("representative_budget_medium"),
                                                      verified("representative_budget_high")],
         "sources": docx_source("representative_budget_low", "representative_budget_medium", "representative_budget_high"),
         "derivation": "parsed from structured OMML {10}^{19}, {10}^{22}, {10}^{24} (FLOPs)", "status": "VERIFIED",
         "limitation": "suggested representative budgets; other budgets are model-conditional continuation"},
        {"id": "S5", "category": "formula", "value": "C_Q = D [g(Q) - g(Q0)]_+",
         "sources": docx_source("quality_cost_increment", "appendix_b_quality_cost", "quality_cost_optional_form"),
         "derivation": "structured OMML with positive-part subscript verified in two places", "status": "VERIFIED",
         "limitation": "stated conditionally ('if the incremental form is adopted')"},
        {"id": "S6", "category": "quality_domain", "value": verified("quality_domain"),
         "sources": docx_source("quality_domain"), "derivation": "parsed from structured OMML Q in (0,1]",
         "status": "VERIFIED", "limitation": "Q = 0 is not admissible"},
        {"id": "S7", "category": "quality_baseline", "value": verified("q0_source_semantics"),
         "sources": docx_source("q0_source_semantics"), "derivation": "organizer wording verified at its paragraph",
         "status": "VERIFIED", "limitation": "no global numeric Q0 is given; nonbaseline cost scenarios are blocked"},
    ]
    for index, family in enumerate(("exponential", "power", "logarithmic"), start=8):
        items.append({
            "id": "S" + str(index), "category": "quality_cost_parameter",
            "value": {"family": family, "gamma_flops_per_token": verified("g_" + family + "_gamma"),
                      "lambda": verified("g_" + family + "_lambda")},
            "sources": docx_source("g_" + family + "_form", "g_" + family + "_gamma", "g_" + family + "_lambda"),
            "derivation": "gamma and lambda parsed from structured OMML in Appendix B.1", "status": "VERIFIED",
            "limitation": "a cost expression, not a loss-benefit model",
        })
    items += [
        {"id": "S11", "category": "semantics", "value": "L_ctx exogenous, from C7, not an interior optimization variable",
         "sources": docx_source("exogenous_context", "exogenous_context_appendix"),
         "derivation": "organizer wording verified in the Q3 text and Appendix A", "status": "VERIFIED",
         "limitation": "the observed grid is not interpolated or extended"},
        {"id": "S12", "category": "requirement", "value": "define and identify structural transfer as C spans magnitudes",
         "sources": docx_source("structural_transition_requirement", "q3_title_structural_transfer"),
         "derivation": "organizer wording verified", "status": "VERIFIED",
         "limitation": "answered by a model-conditional regime map, not an empirical finding"},
        {"id": "S13", "category": "semantics", "value": "training, quality processing and attention share D",
         "sources": docx_source("same_d_rule"), "derivation": "organizer wording verified", "status": "VERIFIED",
         "limitation": "a default stated by the organizer"},
        {"id": "C1", "category": "context_value", "value": c7["observed_grid_tokens"],
         "sources": [
             {"kind": "organizer_attachment", "path": c7["path"], "sha256": c7["sha256"], "locator": "max_position_embeddings"},
             {"kind": "organizer_manifest", "path": provenance["organizer_manifest"]["path"],
              "sha256": provenance["organizer_manifest"]["sha256"], "locator": "record " + c7["path"].split("real_attachments/")[1]},
             {"kind": "intake_receipt", "path": provenance["intake_record"]["path"],
              "sha256": provenance["intake_record"]["sha256"], "locator": "C7 row"},
         ],
         "derivation": "unique values of max_position_embeddings over all " + str(c7["rows"]) + " C7 rows",
         "status": "VERIFIED", "limitation": "observed architecture metadata; no preferred context"},
        {"id": "C2", "category": "formula", "value": "kappa(L_ctx) = 6 + eta L_ctx",
         "sources": derived("S2", "S3", "C1"), "derivation": "sum of the two per-parameter-token cost terms",
         "status": "DERIVED", "limitation": "Q = Q0, so delta_g = 0"},
        {"id": "C3", "category": "threshold", "value": receipt.parity_tokens,
         "sources": derived("S2", "S3") + docx_source("critical_context_identity"),
         "derivation": "L_ctx^crit = 6 / eta", "status": "DERIVED",
         "limitation": "base/attention cost parity only; not an optimum, transition or optimizer threshold"},
        {"id": "I1", "category": "interface", "value": {"sha256": interfaces["IF1"].sha256, **interfaces["IF1"].scope},
         "sources": [{"kind": "accepted_interface", "path": repo_relative(interfaces["IF1"].path),
                      "sha256": interfaces["IF1"].sha256},
                     {"kind": "tracked_upstream_artifact", "path": "results/tables/q1-if1-summary.md",
                      "locator": "sha256 row"}],
         "derivation": "hash, shared contract and partial coverage verified; content withheld",
         "status": "VERIFIED", "limitation": "identity only; no IF1 quality enters Q3"},
        {"id": "I2", "category": "interface", "value": {"sha256": interfaces["IF2"].sha256, **interfaces["IF2"].scope},
         "sources": [{"kind": "accepted_interface", "path": repo_relative(interfaces["IF2"].path),
                      "sha256": interfaces["IF2"].sha256},
                     {"kind": "tracked_upstream_artifact", "path": "results/tables/q1-if2-summary.md",
                      "locator": "sha256 row"}],
         "derivation": "hash, shared contract and 1M-only scope receipt verified; content withheld",
         "status": "VERIFIED", "limitation": "identity only; 1M-only; no IF2 coefficient enters Q3"},
        {"id": "I3", "category": "formula", "value": {"law": "E + A N^-alpha + B D^-beta", "params": dict(classic.params),
                                                      "validity_box": {k: list(v) for k, v in classic.validity_box.items()}},
         "sources": [if3, {"kind": "tracked_upstream_artifact", "path": "results/tables/q2-final-closure.md",
                           "locator": "SHA-256 row"}],
         "derivation": "accepted bytes hash-checked and shared contract validated; Q=[1,1] is a no-quality sentinel",
         "status": "VERIFIED", "limitation": "B1 generator recovery; not precise empirical knowledge of real scaling"},
        {"id": "L1", "category": "robustness_input", "value": [vector.label for vector in loo.vectors],
         "sources": [{"kind": "tracked_upstream_artifact", "path": loo.relative_path, "sha256": loo.sha256,
                      "git_blob_sha1": loo.git_blob_sha1, "locator": "Per-trajectory detail"}],
         "derivation": "eight complete five-parameter vectors parsed at their printed .6g precision",
         "status": "VERIFIED", "limitation": "robustness ranges only; published precision limits the loss ranges"},
    ]
    for budget, row in sorted(by_budget.items()):
        items.append({
            "id": "R-alloc-" + fmt(budget, 3), "category": "conclusion",
            "value": {"budget_flops": budget, "context_tokens": row["context_tokens"], "regime": row["regime"],
                      "n_parameters_raw": row["n_parameters_raw"], "d_tokens_raw": row["d_tokens_raw"],
                      "predicted_loss": row["predicted_loss"], "compute_utilization": row["cost"]["compute_utilization"]},
            "sources": derived("S1", "S4", "C2", "I3") + [q3("q3-allocation.json", "allocations[budget=" + fmt(budget, 3) + "]")],
            "derivation": "exact candidate-set solution of min L s.t. kappa N D <= C in the IF3 box; numerical check PASS",
            "status": "MODEL_CONDITIONAL",
            "limitation": "consequence of the accepted law inside its box; not an observation or developer guidance",
        })
    for analysis in regimes["analyses"]:
        context = analysis["context_tokens"]
        for threshold in analysis["thresholds"]:
            if threshold["name"] not in ("C_min", "C_box", "stationary_reaches_D_max"):
                continue
            items.append({
                "id": "T-" + threshold["name"] + "-" + str(context), "category": "threshold",
                "value": {"context_tokens": context, "budget_flops": threshold["budget_flops"],
                          "disposition": threshold["disposition"], "category": threshold["category"]},
                "sources": derived("C2", "I3") + [q3("q3-regime-thresholds.json",
                                                     "analyses[L=" + str(context) + "].thresholds." + threshold["name"])],
                "derivation": threshold["derivation"],
                "status": "DERIVED" if not threshold["parameter_dependent"] else "MODEL_CONDITIONAL",
                "limitation": ("box geometry; no parameter uncertainty" if not threshold["parameter_dependent"]
                               else "depends on IF3 parameters; LOO range in q3-loo-robustness"),
            })
    items += [
        {"id": "R-regimes", "category": "conclusion",
         "value": sorted({interval["regime"] for analysis in regimes["analyses"] for interval in analysis["regime_map"]}),
         "sources": derived("S12", "C1") + [q3("q3-regime-thresholds.json", "analyses[*].regime_map")],
         "derivation": "regime R(C) changes verified by below/at/above probes inside the declared span",
         "status": "MODEL_CONDITIONAL", "limitation": "no empirical physical transition is established"},
        {"id": "R-loo", "category": "conclusion",
         "value": {"regime_agreement_all_primary_points": all(item["regime_agreement"] for item in robustness["summaries"]),
                   "loss_ranges_resolved": sorted({item["predicted_loss"]["rounding"]["verdict"]
                                                   for item in robustness["summaries"]})},
         "sources": derived("L1", "I3") + [q3("q3-loo-robustness.json", "summaries; thresholds")],
         "derivation": "each published LOO vector solved with the corrected optimizer; 32-corner rounding envelopes",
         "status": "MODEL_CONDITIONAL", "limitation": "robustness ranges, not confidence intervals"},
        {"id": "R-quality-raw", "category": "conclusion",
         "value": [item["q"] for pair in quality["raw_family_analysis"]["pairs"] for item in pair["crossings"]],
         "sources": derived("S6", "S8", "S9", "S10") + [q3("q3-quality-cost-sensitivity.json", "raw_family_analysis.pairs")],
         "derivation": "analytic monotone-piece decomposition and Brent refinement", "status": "DERIVED",
         "limitation": "raw g(Q) only; says nothing about delta_g ordering or allocation"},
        {"id": "R-quality-gates", "category": "conclusion",
         "value": {"nonbaseline": payload["gates"]["nonbaseline_quality_cost_scenarios"]["result"],
                   "cross_scale_benefit": payload["gates"]["cross_scale_quality_benefit"]["result"],
                   "baseline_quality_flops": 0.0},
         "sources": derived("S5", "S7", "I1", "I3"),
         "derivation": "[g(Q0) - g(Q0)]_+ = 0; no numeric Q0; classic IF3 has no quality term", "status": "DERIVED",
         "limitation": "does not assert that data quality is unimportant in reality"},
    ]
    return items


def markdown(items: list[dict[str, Any]]) -> str:
    lines = [
        "# Q3 provenance ledger",
        "",
        "Generated by `scripts/q3_provenance_ledger.py`. Do not edit by hand.",
        "",
        "One row per load-bearing item. `VERIFIED` values were checked against an authorized source at the",
        "stated locator; `DERIVED` items follow exactly from other items; `MODEL_CONDITIONAL` items are",
        "consequences of the accepted classic IF3 law. No item rests on either PDF, a screenshot, a manual",
        "transcription or an AI-produced intermediate, and no item is `UNVERIFIED`; the generator refuses",
        "to write a ledger that violates either rule. Hashes and full values are in the JSON.",
        "",
        "| Item | Category | Value | Source / locator | Status | Limitation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        sources = []
        for source in item["sources"]:
            if source["kind"] == "ledger_item":
                sources.append(source["id"])
            else:
                sources.append("`" + source["path"] + "`" + (" `" + source["locator"] + "`" if source.get("locator") else ""))
        value = json.dumps(item["value"], ensure_ascii=False, sort_keys=True)
        if len(value) > 120:
            value = value[:117] + "..."
        lines.append("| " + item["id"] + " | " + item["category"] + " | `" + value.replace("|", "\\|") + "` | "
                     + "; ".join(sources) + " | " + item["status"] + " | " + item["limitation"] + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    install_q3_input_guard()
    items = build_ledger()
    count = validate_ledger(items)
    payload = {
        "schema_version": "q3-provenance-ledger-v1",
        "purpose": "T-010 itemized provenance of every load-bearing Q3 value, threshold and conclusion",
        "item_count": count,
        "pdf_dependent_items": 0,
        "unverified_items": 0,
        "items": items,
    }
    write_artifacts("q3-provenance-ledger", payload, markdown(items))
    print("ledger items: " + str(count) + "; all validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
