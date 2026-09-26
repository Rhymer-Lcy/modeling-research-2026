"""Receipt-bound baseline Q3 compute semantics.

The Q3 source receipt is accepted only when it matches an independent
regeneration at the consumer boundary: the canonical DOCX is re-verified value
by value and the observed C7 grid is re-derived from the accepted C7 bytes, and
every receipt value must equal those authoritative values.  The accepted
classic IF3 law is allocated at its semantic baseline ``Q0`` only, so quality
preprocessing compute is exactly zero.

Two budget roles are kept distinct.  A *source-supported* budget is one of the
organizer's representative budgets.  A *model-conditional continuation* budget
is any value inside their declared span, admitted only through
:meth:`BaselineCompute.continuation` for continuous regime analysis and always
labelled as such; it is never a newly observed or organizer-specified budget.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.paths import TABLES, require

from .c7 import C7SupportError, derive_c7_support
from .classic import BaselineScopeError, SourceReceiptError, require_baseline_quality
from .sourcedocx import SourceVerificationError, verified_values, verify_source_values

RECEIPT_FILENAME = "q3-source-receipt.json"
RECEIPT_SCHEMA_VERSION = "q3-source-receipt-v3"
RECEIPT_PURPOSE = "T-010 first-party source receipt; not an allocation result"

SOURCE_SUPPORTED = "source_supported_representative_budget"
CONTINUATION = "model_conditional_continuation"


@dataclass(frozen=True)
class SourceReceipt:
    """The validated source-supported Q3 baseline compute lane."""

    path: Path
    payload: Mapping[str, Any]
    budgets_flops: tuple[float, ...]
    contexts_tokens: tuple[int, ...]
    base_coefficient: float
    eta: float
    parity_tokens: float
    quality_families: Mapping[str, Mapping[str, float]]
    quality_domain: Mapping[str, Any]

    @property
    def budget_span(self) -> tuple[float, float]:
        """The declared span of the organizer's representative budgets."""
        return self.budgets_flops[0], self.budgets_flops[-1]

    def require_budget(self, budget_flops: object) -> float:
        """Accept one exact source-supported representative compute budget."""
        value = _positive_finite(budget_flops, "compute budget")
        if not any(value == supported for supported in self.budgets_flops):
            raise SourceReceiptError(
                "compute budget " + repr(value) + " is not on the source-supported grid "
                + repr(self.budgets_flops)
            )
        return value

    def require_span_budget(self, budget_flops: object) -> float:
        """Accept a continuation budget only inside the declared budget span."""
        value = _positive_finite(budget_flops, "continuation budget")
        low, high = self.budget_span
        if not low <= value <= high:
            raise SourceReceiptError(
                "continuation budget " + repr(value) + " lies outside the declared span "
                + repr((low, high)) + "; continuation beyond the source-supported span is not authorized"
            )
        return value

    def require_context(self, context_tokens: object) -> int:
        """Accept one exact observed C7 context regime."""
        if isinstance(context_tokens, bool):
            raise SourceReceiptError("context length must be an observed integer token count")
        try:
            value = int(context_tokens)
        except (TypeError, ValueError) as exc:
            raise SourceReceiptError("context length must be an observed integer token count") from exc
        if value != context_tokens or value <= 0:
            raise SourceReceiptError("context length must be a positive integer token count")
        if value not in self.contexts_tokens:
            raise SourceReceiptError(
                "context length " + repr(value) + " is not on the observed C7 grid "
                + repr(self.contexts_tokens)
            )
        return value

    def kappa(self, context_tokens: object) -> float:
        """Compute source-defined ``6 + eta*L_ctx`` at an observed context."""
        context = self.require_context(context_tokens)
        return float(self.base_coefficient + self.eta * context)


@dataclass(frozen=True)
class BaselineCompute:
    """A receipt-supported baseline operating point with no Q-cost purchase."""

    receipt: SourceReceipt
    budget_flops: float
    context_tokens: int
    kappa: float
    budget_role: str = SOURCE_SUPPORTED
    quality_coordinate: str = "Q0"
    delta_g_flops_per_token: float = 0.0

    @classmethod
    def create(
        cls,
        receipt: SourceReceipt,
        budget_flops: object,
        context_tokens: object,
        *,
        quality: object | None = "Q0",
    ) -> "BaselineCompute":
        """Build one point at an organizer-specified representative budget."""
        require_baseline_quality(quality)
        budget = receipt.require_budget(budget_flops)
        context = receipt.require_context(context_tokens)
        return cls(receipt, budget, context, receipt.kappa(context), SOURCE_SUPPORTED)

    @classmethod
    def continuation(
        cls,
        receipt: SourceReceipt,
        budget_flops: object,
        context_tokens: object,
        *,
        quality: object | None = "Q0",
    ) -> "BaselineCompute":
        """Build a labelled model-conditional continuation point inside the span."""
        require_baseline_quality(quality)
        budget = receipt.require_span_budget(budget_flops)
        context = receipt.require_context(context_tokens)
        return cls(receipt, budget, context, receipt.kappa(context), CONTINUATION)


def _positive_finite(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise SourceReceiptError(label + " must be numeric")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise SourceReceiptError(label + " must be numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise SourceReceiptError(label + " must be finite and strictly positive")
    return numeric


def _terms_by_name(payload: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    terms = payload.get("terms")
    if not isinstance(terms, list):
        raise SourceReceiptError("source receipt terms must be a list")
    output: dict[str, Mapping[str, Any]] = {}
    for term in terms:
        if not isinstance(term, dict) or not isinstance(term.get("name"), str):
            raise SourceReceiptError("source receipt contains an invalid term")
        name = term["name"]
        if name in output:
            raise SourceReceiptError("source receipt repeats term " + repr(name))
        output[name] = term
    return output


def _support(term: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    support = term.get("supported_value_or_grid")
    if not isinstance(support, dict):
        raise SourceReceiptError("source receipt term " + name + " lacks structured support")
    return support


def _require_gate(payload: Mapping[str, Any], lane: str, expected: str) -> None:
    gates = payload.get("gates")
    if not isinstance(gates, dict) or not isinstance(gates.get(lane), dict):
        raise SourceReceiptError("source receipt lacks gate " + repr(lane))
    observed = gates[lane].get("result")
    if observed != expected:
        raise SourceReceiptError(
            "source receipt gate " + lane + " must be " + expected + "; got " + repr(observed)
        )


def _require_canonical_verification(recorded: object, canonical: Mapping[str, Any]) -> None:
    """Require the receipt's verification block to be the independent regeneration, exactly."""
    if not isinstance(recorded, dict) or set(recorded) != {"docx_sha256", "records"}:
        raise SourceReceiptError("receipt source verification is missing or has unexpected fields")
    if recorded["docx_sha256"] != canonical["docx_sha256"]:
        raise SourceReceiptError("receipt source verification is not bound to the accepted canonical DOCX")
    records = recorded["records"]
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise SourceReceiptError("receipt source verification records must be a list of objects")
    keys = [str(record.get("key")) for record in records]
    canonical_keys = [record["key"] for record in canonical["records"]]
    if keys != canonical_keys:
        duplicated = sorted({key for key in keys if keys.count(key) > 1})
        raise SourceReceiptError(
            "receipt verification keys differ from the independent DOCX verification: extra="
            + repr(sorted(set(keys) - set(canonical_keys))) + " missing="
            + repr(sorted(set(canonical_keys) - set(keys))) + " duplicated=" + repr(duplicated)
        )
    for record, expected in zip(records, canonical["records"]):
        if record != expected:
            fields = sorted(field for field in set(record) | set(expected) if record.get(field) != expected.get(field))
            raise SourceReceiptError(
                "receipt verification record " + expected["key"]
                + " differs from the independent DOCX verification in " + repr(fields)
            )


def _require_equal(label: str, observed: object, authoritative: object) -> None:
    if observed != authoritative:
        raise SourceReceiptError(
            "receipt " + label + " " + repr(observed)[:120] + " differs from the independently derived "
            + repr(authoritative)[:120]
        )


def load_source_receipt(path: Path | None = None) -> SourceReceipt:
    """Load the Q3 receipt only if it matches an independent regeneration from the sources.

    The receipt is never its own authority.  This consumer re-verifies the
    allowlisted canonical DOCX (accepted whole-file SHA-256 first, then every
    value at its paragraph and OMML locator) and re-derives the observed C7 grid
    from the accepted C7 bytes, then requires the receipt to agree with both.
    The returned lane is built from the independently derived values, not from
    receipt fields.  ``path`` selects which receipt bytes are checked; the
    authoritative sources are always the canonical allowlisted inputs.
    """
    try:
        canonical = verify_source_values()
        c7 = derive_c7_support()
    except (SourceVerificationError, C7SupportError) as exc:
        raise SourceReceiptError("authoritative Q3 sources cannot be verified: " + str(exc)) from exc
    values = verified_values(canonical)
    source = require(path or (TABLES / RECEIPT_FILENAME))
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceReceiptError("cannot read Q3 source receipt as UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise SourceReceiptError("Q3 source receipt must be a JSON object")
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise SourceReceiptError("Q3 source receipt schema version is not accepted")
    if payload.get("purpose") != RECEIPT_PURPOSE:
        raise SourceReceiptError("Q3 source receipt purpose is not accepted")
    _require_gate(payload, "canonical_baseline_nd_allocation", "PASS")
    _require_gate(payload, "nonbaseline_quality_cost_scenarios", "BLOCKED_UNTIL_Q0_DECLARED")
    _require_gate(payload, "cross_scale_quality_benefit", "PROHIBITED")
    _require_canonical_verification(payload.get("source_verification"), canonical)

    terms = _terms_by_name(payload)
    required = {
        "base_training_compute",
        "attention_compute",
        "context_length",
        "compute_budget",
        "quality_baseline_Q0",
        "quality_cost_families",
        "quality_domain",
        "attention_cost_parity_identity",
    }
    missing = required - set(terms)
    if missing:
        raise SourceReceiptError("Q3 source receipt is missing terms " + repr(sorted(missing)))

    base = _support(terms["base_training_compute"], "base_training_compute")
    attention = _support(terms["attention_compute"], "attention_compute")
    context = _support(terms["context_length"], "context_length")
    budget = _support(terms["compute_budget"], "compute_budget")
    baseline = _support(terms["quality_baseline_Q0"], "quality_baseline_Q0")
    families = _support(terms["quality_cost_families"], "quality_cost_families")
    parity = _support(terms["attention_cost_parity_identity"], "attention_cost_parity_identity")

    coefficient = values["base_training_coefficient"]
    eta = values["attention_eta"]
    budget_grid = (
        values["representative_budget_low"],
        values["representative_budget_medium"],
        values["representative_budget_high"],
    )
    family_values = {
        name: {"gamma": values["g_" + name + "_gamma"], "lambda": values["g_" + name + "_lambda"]}
        for name in ("exponential", "power", "logarithmic")
    }
    _require_equal("base coefficient", base.get("coefficient"), coefficient)
    _require_equal("eta", attention.get("eta"), eta)
    _require_equal("observed C7 context support", dict(context), c7)
    _require_equal("representative budgets", budget.get("representative_budgets_flops"), list(budget_grid))
    _require_equal("budget constraint", budget.get("constraint"), values["budget_inequality"])
    if baseline.get("numeric_global_Q0") is not None:
        raise SourceReceiptError("baseline-only receipt must not claim a numeric global Q0")
    _require_equal("Q0 source options", baseline.get("source_options"), values["q0_source_semantics"])
    _require_equal("quality-cost families", dict(families), family_values)
    _require_equal("quality domain", dict(_support(terms["quality_domain"], "quality_domain")), values["quality_domain"])
    _require_equal("parity context", parity.get("parity_tokens"), coefficient / eta)

    return SourceReceipt(
        path=source,
        payload=payload,
        budgets_flops=budget_grid,
        contexts_tokens=tuple(c7["observed_grid_tokens"]),
        base_coefficient=float(coefficient),
        eta=eta,
        parity_tokens=coefficient / eta,
        quality_families=family_values,
        quality_domain=values["quality_domain"],
    )


def cost_breakdown(
    compute: BaselineCompute,
    n_parameters: object,
    d_tokens: object,
) -> Mapping[str, float]:
    """Return baseline compute components in FLOPs with explicit denominators.

    ``*_share_of_spent`` divides by the compute actually spent; ``*_fraction_of_budget``
    divides by the requested budget.  They coincide only when the budget saturates.
    """
    n_value = _positive_finite(n_parameters, "N")
    d_value = _positive_finite(d_tokens, "D")
    base = compute.receipt.base_coefficient * n_value * d_value
    attention = compute.receipt.eta * compute.context_tokens * n_value * d_value
    quality = 0.0
    spent = base + attention + quality
    if not math.isfinite(spent) or spent <= 0.0:
        raise ValueError("baseline compute total must be finite and strictly positive")
    budget = compute.budget_flops
    return {
        "base_flops": float(base),
        "attention_flops": float(attention),
        "quality_flops": quality,
        "spent_flops": float(spent),
        "requested_budget_flops": float(budget),
        "unused_budget_flops": float(budget - spent),
        "compute_utilization": float(spent / budget),
        "base_share_of_spent": float(base / spent),
        "attention_share_of_spent": float(attention / spent),
        "quality_share_of_spent": quality,
        "base_fraction_of_budget": float(base / budget),
        "attention_fraction_of_budget": float(attention / budget),
        "quality_fraction_of_budget": quality,
        "unused_fraction_of_budget": float((budget - spent) / budget),
        "component_reconciliation_residual_flops": float(spent - (base + attention + quality)),
    }


__all__ = [
    "BaselineCompute",
    "BaselineScopeError",
    "CONTINUATION",
    "RECEIPT_FILENAME",
    "RECEIPT_SCHEMA_VERSION",
    "SOURCE_SUPPORTED",
    "SourceReceipt",
    "SourceReceiptError",
    "cost_breakdown",
    "load_source_receipt",
]
