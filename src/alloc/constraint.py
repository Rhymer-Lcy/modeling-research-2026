"""Receipt-bound baseline Q3 compute semantics.

Only the frozen receipt may supply the Q3 budget grid, C7 context grid and
compute coefficients.  The accepted classic IF3 law is allocated at its
semantic baseline ``Q0`` only, so quality preprocessing compute is exactly zero.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.paths import TABLES, require

from .classic import BaselineScopeError, SourceReceiptError, require_baseline_quality

RECEIPT_FILENAME = "q3-source-receipt.json"
RECEIPT_SCHEMA_VERSION = "q3-source-receipt-v1"
RECEIPT_PURPOSE = "T-010 first-party source receipt; not an allocation result"


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

    def require_budget(self, budget_flops: object) -> float:
        """Accept one exact source-supported representative compute budget."""
        value = _positive_finite(budget_flops, "compute budget")
        if not any(value == supported for supported in self.budgets_flops):
            raise SourceReceiptError(
                "compute budget " + repr(value) + " is not on the source-supported grid "
                + repr(self.budgets_flops)
            )
        return value

    def require_context(self, context_tokens: object) -> int:
        """Accept one exact observed C7 context regime."""
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
        require_baseline_quality(quality)
        budget = receipt.require_budget(budget_flops)
        context = receipt.require_context(context_tokens)
        return cls(
            receipt=receipt,
            budget_flops=budget,
            context_tokens=context,
            kappa=receipt.kappa(context),
        )


def _positive_finite(value: object, label: str) -> float:
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


def load_source_receipt(path: Path | None = None) -> SourceReceipt:
    """Load and validate the frozen receipt before any canonical allocation."""
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

    terms = _terms_by_name(payload)
    required = {
        "base_training_compute",
        "attention_compute",
        "context_length",
        "compute_budget",
        "quality_baseline_Q0",
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
    parity = _support(terms["attention_cost_parity_identity"], "attention_cost_parity_identity")

    if base.get("coefficient") != 6:
        raise SourceReceiptError("Q3 source receipt must specify base coefficient 6")
    eta = _positive_finite(attention.get("eta"), "receipt eta")
    contexts = context.get("observed_grid_tokens")
    if not isinstance(contexts, list) or not contexts:
        raise SourceReceiptError("Q3 source receipt has no observed context grid")
    try:
        context_grid = tuple(int(value) for value in contexts)
    except (TypeError, ValueError) as exc:
        raise SourceReceiptError("receipt context grid must contain integer token counts") from exc
    if tuple(sorted(set(context_grid))) != context_grid or any(value <= 0 for value in context_grid):
        raise SourceReceiptError("receipt context grid must be sorted, unique positive integers")
    budgets = budget.get("representative_budgets_flops")
    if not isinstance(budgets, list) or not budgets:
        raise SourceReceiptError("Q3 source receipt has no supported budget grid")
    budget_grid = tuple(_positive_finite(value, "receipt budget") for value in budgets)
    if tuple(sorted(set(budget_grid))) != budget_grid:
        raise SourceReceiptError("receipt budget grid must be sorted and unique")
    if baseline.get("numeric_global_Q0") is not None:
        raise SourceReceiptError("baseline-only receipt must not claim a numeric global Q0")
    parity_tokens = _positive_finite(parity.get("parity_tokens"), "receipt parity context")
    expected_parity = float(base["coefficient"]) / eta
    if not math.isclose(parity_tokens, expected_parity, rel_tol=0.0, abs_tol=1e-12):
        raise SourceReceiptError("receipt cost-parity identity does not equal 6 / eta")

    return SourceReceipt(
        path=source,
        payload=payload,
        budgets_flops=budget_grid,
        contexts_tokens=context_grid,
        base_coefficient=float(base["coefficient"]),
        eta=eta,
        parity_tokens=parity_tokens,
    )


def cost_breakdown(
    compute: BaselineCompute,
    n_parameters: object,
    d_tokens: object,
) -> Mapping[str, float]:
    """Return exact baseline base/attention/quality shares in FLOPs."""
    n_value = _positive_finite(n_parameters, "N")
    d_value = _positive_finite(d_tokens, "D")
    base = compute.receipt.base_coefficient * n_value * d_value
    attention = compute.receipt.eta * compute.context_tokens * n_value * d_value
    quality = 0.0
    total = base + attention + quality
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("baseline compute total must be finite and strictly positive")
    return {
        "base_flops": float(base),
        "attention_flops": float(attention),
        "quality_flops": quality,
        "total_flops": float(total),
        "base_share": float(base / total),
        "attention_share": float(attention / total),
        "quality_share": quality,
        "budget_residual_flops": float(compute.budget_flops - total),
    }


__all__ = [
    "BaselineCompute",
    "RECEIPT_FILENAME",
    "SourceReceipt",
    "SourceReceiptError",
    "cost_breakdown",
    "load_source_receipt",
]
