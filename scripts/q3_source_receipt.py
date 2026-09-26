"""Freeze the auditable first-party Q3 compute-semantics receipt.

The canonical DOCX is the methodological authority.  Every load-bearing value
(budget inequality, representative budgets, coefficient 6, eta, the three g(Q)
families' coefficients, the Q domain, Q0 semantics, exogenous-context semantics
and the structural-transition requirement) is verified at its exact DOCX
paragraph and OMML math zone before the receipt is emitted, and the receipt
carries those verification records.  C7 is observed direct data, identified by
the organizer manifest and the T-006 intake SHA-256 record.  Only the explicit
Q3 allowlist is read, under the process-wide input guard; neither PDF is
opened for any purpose.  This script allocates nothing and selects no numeric Q0.

Writes:
    results/tables/q3-source-receipt.json
    results/tables/q3-source-receipt.md

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_source_receipt.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.alloc import (  # noqa: E402
    ACCEPTED_INTERFACE_SHA256,
    AUTHORIZED_Q3_INPUTS,
    DOCX_PATH,
    SourceVerificationError,
    input_identity,
    install_q3_input_guard,
    load_all_accepted_interfaces,
    repo_relative,
    verified_values,
    verify_source_values,
)
from src.alloc.c7 import C7SupportError, derive_c7_support  # noqa: E402
from src.alloc.report import write_artifacts  # noqa: E402


class ReceiptError(RuntimeError):
    """Raised when required first-party evidence cannot support the receipt."""


def docx_source(keys: list[str], sha: str) -> dict[str, Any]:
    return {"path": repo_relative(DOCX_PATH), "sha256": sha, "verification_keys": keys}


def build_receipt() -> dict[str, Any]:
    verification = verify_source_values()
    values = verified_values(verification)
    docx_sha = verification["docx_sha256"]
    c7 = derive_c7_support()
    interfaces = load_all_accepted_interfaces()
    if {kind: item.sha256 for kind, item in interfaces.items()} != ACCEPTED_INTERFACE_SHA256:
        raise ReceiptError("accepted interface identities changed")

    eta = values["attention_eta"]
    coefficient = values["base_training_coefficient"]
    families = {
        name: {"gamma": values["g_" + name + "_gamma"], "lambda": values["g_" + name + "_lambda"]}
        for name in ("exponential", "power", "logarithmic")
    }
    terms = [
        {
            "name": "base_training_compute",
            "definition": "C_train = 6 N D",
            "physical_unit": "FLOPs",
            "input_units": {"N": "raw parameter count", "D": "raw training-token count"},
            "supported_value_or_grid": {"coefficient": coefficient},
            "provenance_status": "specified",
            "analysis_role": "canonical",
            "source": docx_source(["base_training_coefficient", "flops_unit_definition"], docx_sha),
        },
        {
            "name": "attention_compute",
            "definition": "C_attn = eta N D L_ctx",
            "physical_unit": "FLOPs",
            "input_units": {"N": "raw parameter count", "D": "raw token count", "L_ctx": "tokens",
                            "eta": "FLOPs per parameter-token-context-token (dimensional consequence)"},
            "supported_value_or_grid": {"eta": eta},
            "provenance_status": "specified",
            "analysis_role": "canonical",
            "source": docx_source(["attention_compute_form", "attention_eta"], docx_sha),
        },
        {
            "name": "context_length",
            "definition": "L_ctx is exogenous, taken from C7, and never an interior optimization variable.",
            "physical_unit": "tokens",
            "supported_value_or_grid": c7,
            "provenance_status": "observed",
            "analysis_role": "exogenous sensitivity axis limited to the full observed C7 grid",
            "source": docx_source(["exogenous_context", "exogenous_context_appendix", "attention_compute_form"],
                                  docx_sha),
            "limitation": "Neither source designates a preferred context; the grid is not interpolated or extended.",
        },
        {
            "name": "compute_budget",
            "definition": "Total compute budget C; the allocation must satisfy C_total <= C.",
            "physical_unit": "FLOPs",
            "supported_value_or_grid": {
                "representative_budgets_flops": [
                    values["representative_budget_low"],
                    values["representative_budget_medium"],
                    values["representative_budget_high"],
                ],
                "constraint": values["budget_inequality"],
                "source_language": "suggested low, medium and high representative budgets; other levels "
                                   "may be chosen but at least three magnitudes must be examined",
            },
            "provenance_status": "specified",
            "analysis_role": "primary presentation grid; continuous-C analysis only inside its declared span",
            "source": docx_source(["budget_inequality", "total_budget_three_parts", "representative_budget_low",
                                   "representative_budget_medium", "representative_budget_high"], docx_sha),
        },
        {
            "name": "quality_preprocessing_compute",
            "definition": "C_Q = D [g(Q) - g(Q0)]_+",
            "physical_unit": "FLOPs",
            "input_units": {"D": "raw token count", "Q": "dimensionless", "g": "FLOPs per token"},
            "supported_value_or_grid": {"positive_part": "[x]_+ = max(x, 0)",
                                        "stated_form": "if the incremental form is adopted",
                                        "same_D_rule": "training, quality processing and attention share D"},
            "provenance_status": "specified",
            "analysis_role": "zero at the canonical baseline Q = Q0; nonbaseline use blocked without numeric Q0",
            "source": docx_source(["quality_cost_increment", "quality_cost_optional_form", "appendix_b_quality_cost",
                                   "same_d_rule"], docx_sha),
        },
        {
            "name": "quality_cost_families",
            "definition": "exponential gamma e^(lambda Q); power gamma Q^lambda; logarithmic gamma ln(1 + lambda Q)",
            "physical_unit": "g(Q): FLOPs per token; Q dimensionless",
            "supported_value_or_grid": families,
            "provenance_status": "specified",
            "analysis_role": "raw-family comparison only",
            "source": docx_source(["quality_family_choice", "g_exponential_form", "g_exponential_gamma",
                                   "g_exponential_lambda", "g_power_form", "g_power_gamma", "g_power_lambda",
                                   "g_logarithmic_form", "g_logarithmic_gamma", "g_logarithmic_lambda"], docx_sha),
        },
        {
            "name": "quality_domain",
            "definition": "Q in (0, 1]",
            "physical_unit": "dimensionless",
            "supported_value_or_grid": values["quality_domain"],
            "provenance_status": "specified",
            "analysis_role": "domain of the raw-family comparison; Q = 0 is not admissible",
            "source": docx_source(["quality_domain"], docx_sha),
        },
        {
            "name": "quality_baseline_Q0",
            "definition": "Q0 is the baseline in C_Q = D [g(Q) - g(Q0)]_+.",
            "physical_unit": "dimensionless",
            "supported_value_or_grid": {"source_options": values["q0_source_semantics"], "numeric_global_Q0": None},
            "provenance_status": "specified semantics; numeric value not established",
            "analysis_role": "At Q = Q0, delta_g = 0 exactly. Nonbaseline cost scenarios are blocked until a "
                             "numeric Q0 is declared with provenance.",
            "source": docx_source(["q0_source_semantics"], docx_sha),
            "limitation": "IF1's partially mapped relative proxy is not substituted for Q0 and no unmapped "
                          "mixture mass is imputed.",
        },
        {
            "name": "combined_compute_constraint",
            "definition": "C_total = D [(6 + eta L_ctx) N + [g(Q) - g(Q0)]_+] <= C",
            "physical_unit": "FLOPs",
            "input_units": {"kappa(L_ctx)": "FLOPs per parameter-token", "delta_g(Q)": "FLOPs per token"},
            "supported_value_or_grid": {"kappa": "6 + eta L_ctx", "delta_g": "[g(Q) - g(Q0)]_+",
                                        "constraint": values["budget_inequality"]},
            "provenance_status": "derived exactly from verified source components",
            "analysis_role": "canonical at Q = Q0, where it reduces to kappa N D <= C",
            "source": docx_source(["budget_inequality", "base_training_coefficient", "attention_eta",
                                   "quality_cost_increment", "same_d_rule"], docx_sha),
        },
        {
            "name": "attention_cost_parity_identity",
            "definition": "L_ctx^crit = 6 / eta, where attention and base training compute are equal",
            "physical_unit": "tokens",
            "supported_value_or_grid": {"eta": eta, "parity_tokens": coefficient / eta},
            "provenance_status": "derived exactly from the verified coefficient and eta",
            "analysis_role": "base/attention cost-parity identity only; not an optimum, phase transition, "
                             "or optimizer-regime threshold",
            "source": docx_source(["critical_context_identity", "base_training_coefficient", "attention_eta"], docx_sha),
        },
        {
            "name": "structural_transition_requirement",
            "definition": "Decide whether the optimal allocation changes qualitatively as C spans magnitudes, "
                          "with an explicit mathematical definition and identification method.",
            "physical_unit": "not applicable",
            "supported_value_or_grid": {"requirement": "definition and identification method"},
            "provenance_status": "specified requirement",
            "analysis_role": "answered by the budget regime map in results/tables/q3-regime-thresholds.md",
            "source": docx_source(["structural_transition_requirement", "q3_title_structural_transfer"], docx_sha),
        },
    ]
    gates = {
        "canonical_baseline_nd_allocation": {
            "result": "PASS",
            "reason": "Base, attention, context, budget and baseline quality-cost semantics are verified at their "
                      "canonical DOCX spans. At Q = Q0, delta_g(Q0) = 0 exactly and no numeric Q0 is needed.",
        },
        "nonbaseline_quality_cost_scenarios": {
            "result": "BLOCKED_UNTIL_Q0_DECLARED",
            "reason": "The source defines Q0 semantically (Attachment A quality scores or a reasonable assumption) "
                      "but gives no global scalar. No IF1 substitution or unmapped-mass imputation is permitted.",
        },
        "cross_scale_quality_benefit": {
            "result": "PROHIBITED",
            "reason": "Classic IF3 has no quality-loss term; g(Q) is a cost expression, not a benefit model.",
        },
    }
    return {
        "schema_version": "q3-source-receipt-v3",
        "purpose": "T-010 first-party source receipt; not an allocation result",
        "methodological_authority": {
            "path": repo_relative(DOCX_PATH),
            "sha256": docx_sha,
            "verification": "whole-file SHA-256 plus " + str(len(verification["records"]))
                            + " value/wording checks at exact DOCX paragraph and OMML locators",
        },
        "source_verification": verification,
        "authorized_inputs": [
            {"key": entry.key, "path": entry.relative_path, "kind": entry.kind, "role": entry.role,
             "identity": input_identity(entry)}
            for entry in AUTHORIZED_Q3_INPUTS
        ],
        "quarantined_material": {
            "status": "NOT_CONSUMED",
            "enforcement": "Any *.pdf path is rejected lexically at the Q3 input boundary and by the process-wide "
                           "audit-hook guard before open, stat-through-open, hashing or parsing.",
            "paths_metadata_only": [
                {"path": "docs_local/problem-f/source/data_description.original.pdf",
                 "role": "quarantined original; zero evidentiary weight; forbidden automated input"},
                {"path": "docs_local/problem-f/audit/data_description.sanitized.m2.pdf",
                 "role": "non-authoritative derivative; forbidden load-bearing input"},
            ],
        },
        "terms": terms,
        "gates": gates,
    }


def markdown_receipt(receipt: dict[str, Any]) -> str:
    verification = receipt["source_verification"]
    lines = [
        "# Q3 source receipt",
        "",
        "Generated by `scripts/q3_source_receipt.py`. Do not edit by hand.",
        "",
        "First-party source and semantics receipt, not an allocation result. The canonical DOCX is the",
        "methodological authority. Each load-bearing value below was verified at its exact paragraph",
        "(`w:body/w:p[i]`) and Office Math zone (`m:oMath[j]`) with exponent structure preserved, after",
        "the whole-file SHA-256 check. C7 is observed direct data. Neither PDF was opened.",
        "",
        "This receipt is not its own authority. Its consumer (`load_source_receipt`, used by every",
        "allocation script) re-verifies the canonical DOCX and re-derives the C7 grid from the accepted",
        "C7 bytes, and rejects the receipt on any difference, including extra, duplicate or relocated",
        "verification records. Local-only inputs are identified by SHA-256; the tracked upstream input",
        "is identified by its accepted Git blob, never by working-copy bytes.",
        "",
        "## Gates",
        "",
        "| Lane | Result | Disposition |",
        "| --- | --- | --- |",
    ]
    for lane, gate in receipt["gates"].items():
        lines.append("| `" + lane + "` | **" + gate["result"] + "** | " + gate["reason"] + " |")
    lines += [
        "",
        "## Authorized inputs (complete Q3 allowlist)",
        "",
        "| Key | Path | Kind | Role | Identity |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in receipt["authorized_inputs"]:
        identity = entry["identity"]
        shown = ("SHA-256 `" + identity["sha256"] + "`" if "sha256" in identity
                 else "Git blob `" + identity["git_blob_id"] + "` (accepted at `" + identity["accepted_commit"][:7] + "`)")
        lines.append("| `" + entry["key"] + "` | `" + entry["path"] + "` | " + entry["kind"] + " | "
                     + entry["role"] + " | " + shown + " |")
    lines += [
        "",
        "Allowlisted files: " + str(len(receipt["authorized_inputs"])) + ". No directory is traversed. The historical",
        "whole-tree snapshot of the reviewed checkpoint is not carried forward as current evidence.",
        "",
        "## Value-level source verification",
        "",
        "| Key | Locator | Structured math | Verified value | Statement | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in verification["records"]:
        math = record.get("structured_math")
        value = record.get("verified_value")
        lines.append(
            "| `" + record["key"] + "` | `" + record.get("math_locator", record["locator"]) + "` | "
            + ("`" + math.replace("|", "\\|") + "`" if math else "—") + " | "
            + ("`" + json.dumps(value, ensure_ascii=False) + "`" if value is not None else "—") + " | "
            + record["description"] + " | " + record["status"] + " |"
        )
    c7 = next(term for term in receipt["terms"] if term["name"] == "context_length")["supported_value_or_grid"]
    lines += [
        "",
        "## C7 observed context support",
        "",
        "`" + c7["path"] + "` (SHA-256 `" + c7["sha256"] + "`, " + str(c7["bytes"]) + " bytes, "
        + str(c7["rows"]) + " rows) matches the organizer manifest byte count and row count and the T-006",
        "intake SHA-256 record. The observed grid is "
        + ", ".join("`" + str(value) + "`" for value in c7["observed_grid_tokens"]) + " tokens.",
        "",
        "| L_ctx (tokens) | Observed models |",
        "| ---: | ---: |",
    ]
    for value in c7["observed_grid_tokens"]:
        lines.append("| " + str(value) + " | " + str(c7["observed_frequency"][str(value)]) + " |")
    lines += [
        "",
        "## Scope",
        "",
        "`Q0` is defined semantically (Attachment A quality scores or a reasonable assumption) but no global",
        "scalar is established; nonbaseline quality-cost scenarios remain blocked and IF1 is not substituted.",
        "`L_ctx = 6 / eta = 30000` tokens is the base/attention cost-parity identity only. Budgets other than",
        "the three representative values enter only as labelled model-conditional continuation inside the",
        "declared span.",
        "",
        "Machine-readable receipt: `results/tables/q3-source-receipt.json`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    install_q3_input_guard()
    try:
        receipt = build_receipt()
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError, ReceiptError, SourceVerificationError,
            C7SupportError) as exc:
        print("SOURCE RECEIPT FAIL-CLOSED: " + str(exc), file=sys.stderr)
        return 1
    write_artifacts("q3-source-receipt", receipt, markdown_receipt(receipt))
    print("value-level source checks: " + str(len(receipt["source_verification"]["records"])) + " VERIFIED")
    print("canonical baseline N-D gate: " + receipt["gates"]["canonical_baseline_nd_allocation"]["result"])
    print("nonbaseline quality-cost scenarios: " + receipt["gates"]["nonbaseline_quality_cost_scenarios"]["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
