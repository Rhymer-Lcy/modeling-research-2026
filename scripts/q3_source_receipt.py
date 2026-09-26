"""Freeze the auditable first-party Q3 compute-semantics receipt.

The canonical DOCX is the methodological authority.  C7 architecture metadata is
used only as observed empirical context support.  The quarantined PDF is never
read.  This script intentionally does not allocate N or D and does not select a
numeric quality baseline.

Writes:
    results/tables/q3-source-receipt.json
    results/tables/q3-source-receipt.md

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_source_receipt.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.paths import ATT_C, PROBLEM_F_SOURCE, TABLES, ensure, require  # noqa: E402


DOCX_SHA256 = "89f1b27c497c03ebf03335f5c9a738fa8a7f3525409bceb1ff8676794cf3b6a7"
DOCX_PATH = PROBLEM_F_SOURCE / "problem_statement.docx"
C7_RELATIVE_PATH = "C_efficiency_evolution/model_architecture_metadata.csv"
MANIFEST_PATH = ATT_C.parent / "source_manifest.json"

# These exact fragments are the source-backed semantic anchors.  A changed or
# incomplete canonical DOCX must stop receipt generation rather than silently
# producing a receipt for an unknown specification.
REQUIRED_DOCX_FRAGMENTS = (
    "Ctrain=6ND",
    "1024 FLOPs",
    "CQ=D [g(Q)−g(Q0)]+",
    "Cattn=ηNDLctx",
    "Lctxcrit=6/η",
    "g(Q)=γeλQ",
    "g(Q)=γQλ",
    "g(Q)=γln(1+λQ)",
)


class ReceiptError(RuntimeError):
    """Raised when required first-party evidence cannot support the receipt."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_relative(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def docx_paragraphs(path: Path) -> list[str]:
    """Read DOCX paragraph text with the standard library, without modifying it."""
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    return ["".join(node.itertext()).strip() for node in root.findall(".//w:p", namespace)
            if "".join(node.itertext()).strip()]


def paragraph_number(paragraphs: list[str], fragment: str) -> int:
    for index, paragraph in enumerate(paragraphs, 1):
        if fragment in paragraph:
            return index
    raise ReceiptError("Canonical DOCX is missing required fragment: " + repr(fragment))


def read_c7_context() -> tuple[dict[str, object], dict[str, object]]:
    """Return observed C7 context support and its matching manifest record."""
    context_path = require(ATT_C.parent / C7_RELATIVE_PATH)
    manifest_path = require(MANIFEST_PATH)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("files", manifest) if isinstance(manifest, dict) else manifest
    if not isinstance(records, list):
        raise ReceiptError("source_manifest.json must contain a list of source records")
    matching = [record for record in records if record.get("file") == C7_RELATIVE_PATH]
    if len(matching) != 1:
        raise ReceiptError("Expected exactly one C7 manifest record for " + C7_RELATIVE_PATH)
    manifest_record = matching[0]
    if int(manifest_record.get("bytes", -1)) != context_path.stat().st_size:
        raise ReceiptError("C7 metadata byte count differs from source manifest")

    with context_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "max_position_embeddings" not in rows[0]:
        raise ReceiptError("C7 metadata lacks max_position_embeddings")
    try:
        values = [int(row["max_position_embeddings"]) for row in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise ReceiptError("C7 context values must be positive integer token counts") from exc
    if any(value <= 0 for value in values):
        raise ReceiptError("C7 context values must be positive")
    expected_rows = re.search(r"(\d+)个主流", str(manifest_record.get("note", "")))
    if expected_rows and len(rows) != int(expected_rows.group(1)):
        raise ReceiptError("C7 row count differs from the organizer manifest note")

    counts = Counter(values)
    grid = sorted(counts)
    models_by_context: dict[int, list[str]] = {value: [] for value in grid}
    for row, value in zip(rows, values):
        model_name = row.get("model_name", "").strip()
        if not model_name:
            raise ReceiptError("C7 metadata has a context row without model_name")
        models_by_context[value].append(model_name)
    regimes = [
        {
            "context_tokens": value,
            "observed_model_count": counts[value],
            "observed_models": sorted(models_by_context[value]),
            "provenance_status": "observed",
        }
        for value in grid
    ]
    support = {
        "path": repo_relative(context_path),
        "sha256": sha256(context_path),
        "rows": len(rows),
        "field": "max_position_embeddings",
        "unit": "tokens",
        "observed_grid_tokens": grid,
        "observed_frequency": {str(value): counts[value] for value in grid},
        "observed_range_tokens": [grid[0], grid[-1]],
        "representative_operating_regimes": regimes,
        "regime_selection_rule": (
            "One observed regime per unique C7 context value; all source rows are retained. "
            "No preferred subset, interpolation, or extrapolation is inferred."
        ),
    }
    return support, manifest_record


def source_ref(path: Path, sha: str, paragraphs: list[int] | None = None) -> dict[str, object]:
    out: dict[str, object] = {"path": repo_relative(path), "sha256": sha}
    if paragraphs is not None:
        out["paragraphs"] = paragraphs
    return out


def build_receipt() -> dict[str, object]:
    docx_path = require(DOCX_PATH)
    docx_sha = sha256(docx_path)
    if docx_sha != DOCX_SHA256:
        raise ReceiptError(
            "Canonical DOCX SHA-256 differs from the provenance receipt: " + docx_sha
        )
    paragraphs = docx_paragraphs(docx_path)
    anchors = {fragment: paragraph_number(paragraphs, fragment)
               for fragment in REQUIRED_DOCX_FRAGMENTS}
    c7, c7_manifest = read_c7_context()

    p53 = anchors["Ctrain=6ND"]
    p55 = anchors["CQ=D [g(Q)−g(Q0)]+"]
    p58 = anchors["Cattn=ηNDLctx"]
    p69 = anchors["Lctxcrit=6/η"]
    p72 = anchors["g(Q)=γeλQ"]

    docx_source = source_ref(docx_path, docx_sha)
    c7_source = source_ref(ATT_C.parent / C7_RELATIVE_PATH, str(c7["sha256"]))
    manifest_source = source_ref(MANIFEST_PATH, sha256(MANIFEST_PATH))

    terms = [
        {
            "name": "base_training_compute",
            "definition": "C_train = 6 N D",
            "physical_unit": "FLOPs",
            "input_units": {"N": "raw parameter count", "D": "raw token count"},
            "supported_value_or_grid": {"coefficient": 6},
            "provenance_status": "specified",
            "analysis_role": "canonical",
            "source": {**docx_source, "paragraphs": [p53]},
        },
        {
            "name": "attention_compute",
            "definition": "C_attn = eta N D L_ctx",
            "physical_unit": "FLOPs",
            "input_units": {
                "N": "raw parameter count",
                "D": "raw token count",
                "L_ctx": "tokens",
                "eta": "FLOPs per parameter-token squared (dimensional consequence of the specified equation)",
            },
            "supported_value_or_grid": {"eta": 0.0002},
            "provenance_status": "specified",
            "analysis_role": "canonical",
            "source": {**docx_source, "paragraphs": [p58]},
        },
        {
            "name": "context_length",
            "definition": "L_ctx is an exogenously supplied context-window length; it is not an interior optimization variable.",
            "physical_unit": "tokens",
            "supported_value_or_grid": c7,
            "provenance_status": "observed",
            "analysis_role": "canonical sensitivity axis limited to the full observed C7 grid",
            "source": {
                "methodology": {**docx_source, "paragraphs": [p58, p69]},
                "empirical_support": c7_source,
                "manifest": manifest_source,
                "manifest_record": c7_manifest,
            },
            "limitation": (
                "C7 supplies observed architecture metadata. The DOCX requires feasible values to be based on C7, "
                "but neither source designates a preferred subset or an empirical optimum."
            ),
        },
        {
            "name": "compute_budget",
            "definition": "Total compute budget C subject to C_total <= C.",
            "physical_unit": "FLOPs",
            "supported_value_or_grid": {
                "representative_budgets_flops": ["1e19", "1e22", "1e24"],
                "source_language": "suggested representative low, medium, and high budgets",
            },
            "provenance_status": "specified",
            "analysis_role": "canonical source-supported budget grid",
            "source": {**docx_source, "paragraphs": [p53]},
        },
        {
            "name": "quality_preprocessing_compute",
            "definition": "C_Q = D [g(Q) - g(Q0)]_+",
            "physical_unit": "FLOPs",
            "input_units": {
                "D": "raw token count",
                "Q": "dimensionless quality coordinate in (0, 1]",
                "Q0": "dimensionless baseline quality coordinate",
                "g": "FLOPs per token (dimensional consequence of the specified equation)",
            },
            "supported_value_or_grid": {
                "positive_part": "[x]_+ = max(x, 0)",
                "same_D_rule": "The same D is used for training, quality processing, and attention.",
            },
            "provenance_status": "specified",
            "analysis_role": "quality-cost sensitivity only; no accepted classic-IF3 loss-benefit term",
            "source": {**docx_source, "paragraphs": [p55, p58, p69]},
        },
        {
            "name": "quality_cost_families",
            "definition": "Organizer-specified forms for g(Q) in C_Q.",
            "physical_unit": "g(Q): FLOPs per token; Q is dimensionless",
            "supported_value_or_grid": {
                "exponential": {"formula": "g(Q) = gamma exp(lambda Q)", "gamma": "1e7", "lambda": "6.0"},
                "power": {"formula": "g(Q) = gamma Q^lambda", "gamma": "5e9", "lambda": "4.0"},
                "logarithmic_asymptotic": {
                    "formula": "g(Q) = gamma ln(1 + lambda Q)", "gamma": "2e9", "lambda": "10.0"
                },
            },
            "provenance_status": "specified",
            "analysis_role": "quality-cost sensitivity only",
            "source": {**docx_source, "paragraphs": [p72, p72 + 1, p72 + 2]},
        },
        {
            "name": "quality_baseline_Q0",
            "definition": "Q0 is the baseline in the positive-part quality-cost expression.",
            "physical_unit": "dimensionless quality coordinate",
            "supported_value_or_grid": {
                "source_options": [
                    "Attachment A quality scoring",
                    "a reasonable declared assumption",
                ],
                "numeric_global_Q0": None,
            },
            "provenance_status": "specified semantic; numeric value not established",
            "analysis_role": "At Q = Q0, delta_g = 0 by the specified expression. Any non-baseline quality-cost scenario is blocked until Q0 is declared with provenance.",
            "source": {**docx_source, "paragraphs": [p55]},
            "limitation": (
                "No source-established global scalar Q0 is supplied here. IF1's partially mapped relative proxy is not "
                "substituted for Q0, and no unmapped mass is imputed."
            ),
        },
        {
            "name": "combined_compute_constraint",
            "definition": "C_total = D [(6 + eta L_ctx) N + [g(Q) - g(Q0)]_+] <= C",
            "physical_unit": "FLOPs",
            "input_units": {
                "kappa(L_ctx)": "FLOPs per parameter-token",
                "delta_g(Q)": "FLOPs per token",
            },
            "supported_value_or_grid": {
                "kappa": "6 + eta L_ctx",
                "delta_g": "[g(Q) - g(Q0)]_+",
            },
            "provenance_status": "derived exactly from specified source components",
            "analysis_role": "canonical at baseline Q = Q0; non-baseline Q is a separately labelled cost scenario",
            "source": {**docx_source, "paragraphs": [p53, p55, p58]},
        },
        {
            "name": "attention_cost_parity_identity",
            "definition": "L_ctx,parity = 6 / eta = 30000 tokens",
            "physical_unit": "tokens",
            "supported_value_or_grid": {"eta": 0.0002, "parity_tokens": 30000},
            "provenance_status": "derived exactly from specified source coefficient and eta",
            "analysis_role": "cost-parity identity only; not an empirical optimum, phase transition, or optimizer-regime claim",
            "source": {**docx_source, "paragraphs": [p58, p69]},
        },
    ]

    gates = {
        "canonical_baseline_nd_allocation": {
            "result": "PASS",
            "reason": (
                "The base, attention, context, budget, and baseline quality-cost semantics are established by permissible "
                "first-party evidence. At the source-defined baseline Q = Q0, delta_g(Q0) is exactly zero and no numeric "
                "global Q0 is needed to evaluate the classic N-D objective."
            ),
        },
        "nonbaseline_quality_cost_scenarios": {
            "result": "BLOCKED_UNTIL_Q0_DECLARED",
            "reason": (
                "The source defines Q0 semantically but supplies no global scalar value. A scenario may proceed only after a "
                "Q0 source or explicitly declared assumption is provided; no IF1 proxy substitution or unmapped-mass imputation "
                "is permitted."
            ),
        },
        "cross_scale_quality_benefit": {
            "result": "PROHIBITED",
            "reason": "Classic IF3 has no accepted quality-loss term; the receipt supplies a cost expression, not a cross-scale benefit model.",
        },
    }
    return {
        "schema_version": "q3-source-receipt-v1",
        "purpose": "T-010 first-party source receipt; not an allocation result",
        "methodological_authority": {
            **docx_source,
            "verification": "SHA-256 and required semantic anchors verified before receipt emission",
        },
        "quarantined_material": {
            "path": "docs_local/problem-f/source/data_description.original.pdf",
            "role": "audit/location aid only; never read by this script and never used as mathematical authority",
        },
        "terms": terms,
        "gates": gates,
    }


def markdown_receipt(receipt: dict[str, object]) -> str:
    lines = [
        "# Q3 source receipt",
        "",
        "Generated by `scripts/q3_source_receipt.py`. Do not edit by hand.",
        "",
        "This is a first-party source and semantics receipt, not an allocation result. The canonical DOCX is",
        "the methodological authority; C7 architecture metadata is observed empirical context support. The",
        "quarantined PDF is not read or used as mathematical authority.",
        "",
        "## Receipt gate",
        "",
        "| Lane | Result | Disposition |",
        "| --- | --- | --- |",
    ]
    gates = receipt["gates"]
    assert isinstance(gates, dict)
    for lane, gate in gates.items():
        assert isinstance(gate, dict)
        lines.append("| `" + str(lane) + "` | **" + str(gate["result"]) + "** | "
                     + str(gate["reason"]) + " |")
    lines += [
        "",
        "## Sources",
        "",
        "| Role | Path | SHA-256 |",
        "| --- | --- | --- |",
    ]
    authority = receipt["methodological_authority"]
    assert isinstance(authority, dict)
    lines.append("| Canonical methodology | `" + str(authority["path"]) + "` | `" + str(authority["sha256"]) + "` |")
    terms = receipt["terms"]
    assert isinstance(terms, list)
    context = next(term for term in terms if term["name"] == "context_length")
    assert isinstance(context, dict)
    context_source = context["source"]
    assert isinstance(context_source, dict)
    empirical = context_source["empirical_support"]
    assert isinstance(empirical, dict)
    lines.append("| C7 observed context metadata | `" + str(empirical["path"]) + "` | `" + str(empirical["sha256"]) + "` |")
    lines += [
        "",
        "## Terms",
        "",
        "| Term | Definition | Physical unit | Source status | Supported value / grid | Analysis role |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for term in terms:
        assert isinstance(term, dict)
        support = term["supported_value_or_grid"]
        support_text = json.dumps(support, ensure_ascii=False, sort_keys=True, separators=(",", "; "))
        lines.append("| `" + str(term["name"]) + "` | " + str(term["definition"]) + " | "
                     + str(term["physical_unit"]) + " | " + str(term["provenance_status"]) + " | "
                     + support_text.replace("|", "\\|") + " | " + str(term["analysis_role"]) + " |")
    c7_support = context["supported_value_or_grid"]
    assert isinstance(c7_support, dict)
    lines += [
        "",
        "## C7 observed context support",
        "",
        "C7 has " + str(c7_support["rows"]) + " observed architecture records. The full observed, source-supported",
        "sensitivity grid is " + ", ".join("`" + str(value) + "`" for value in c7_support["observed_grid_tokens"])
        + " tokens; observed range `" + str(c7_support["observed_range_tokens"][0]) + "`–`"
        + str(c7_support["observed_range_tokens"][1]) + "` tokens.",
        "",
        "| L_ctx (tokens) | Observed models |",
        "| ---: | ---: |",
    ]
    frequencies = c7_support["observed_frequency"]
    assert isinstance(frequencies, dict)
    for value in c7_support["observed_grid_tokens"]:
        lines.append("| " + str(value) + " | " + str(frequencies[str(value)]) + " |")
    lines += [
        "",
        "## Scope limitation",
        "",
        "The source defines the Q0 baseline but does not establish one global scalar Q0 in this receipt. Baseline",
        "classic N-D allocation at Q = Q0 is admissible because the source-defined positive part gives delta_g(Q0) = 0",
        "exactly. A non-baseline quality-cost scenario remains blocked until its Q0 is declared with provenance. IF1 is",
        "not substituted for Q0: it is a partial, relative domain proxy, and unmapped mixture mass is never imputed.",
        "",
        "The `30000`-token value is the source-required base/attention cost-parity identity from 6 / eta. It is not",
        "an empirical optimum, a phase transition, or an optimizer-regime result.",
        "",
        "Machine-readable receipt: `results/tables/q3-source-receipt.json`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        receipt = build_receipt()
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError, ReceiptError) as exc:
        print("SOURCE RECEIPT FAIL-CLOSED: " + str(exc), file=sys.stderr)
        return 1

    out_dir = ensure(TABLES)
    json_path = out_dir / "q3-source-receipt.json"
    markdown_path = out_dir / "q3-source-receipt.md"
    json_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    markdown_path.write_text(markdown_receipt(receipt), encoding="utf-8", newline="\n")
    print("wrote " + repo_relative(json_path))
    print("wrote " + repo_relative(markdown_path))
    print("canonical baseline N-D receipt gate: "
          + str(receipt["gates"]["canonical_baseline_nd_allocation"]["result"]))
    print("non-baseline quality-cost scenarios: "
          + str(receipt["gates"]["nonbaseline_quality_cost_scenarios"]["result"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
