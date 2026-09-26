"""Shared, deterministic serialization for the Q3 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.paths import REPO_ROOT, TABLES, ensure

from .solver import AllocationResult


def fmt(value: float, digits: int = 8) -> str:
    """Format a number to a fixed count of significant digits."""
    return format(float(value), "." + str(digits) + "g")


def unused_text(record: Mapping[str, Any]) -> str:
    """Unused budget for display: a saturated row shows its rounding residual as such."""
    cost = record["cost"]
    if record["saturation"] == "SATURATED":
        residual = cost["unused_budget_flops"] / cost["requested_budget_flops"]
        return "0" if residual == 0.0 else "0 (rounding " + format(residual, ".1e") + " C)"
    return fmt(cost["unused_budget_flops"])


def write_artifacts(stem: str, payload: Mapping[str, Any], markdown: str) -> tuple[Path, Path]:
    """Write ``results/tables/<stem>.json`` and ``.md`` as UTF-8 with LF endings."""
    out_dir = ensure(TABLES)
    json_path = out_dir / (stem + ".json")
    markdown_path = out_dir / (stem + ".md")
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
    for path in (json_path, markdown_path):
        print("wrote " + path.relative_to(REPO_ROOT).as_posix())
    return json_path, markdown_path


def allocation_record(result: AllocationResult) -> dict[str, Any]:
    """The standard machine-readable record of one valid allocation."""
    compute = result.compute
    return {
        "status": "VALID_ALLOCATION",
        "budget_flops": compute.budget_flops,
        "budget_role": compute.budget_role,
        "context_tokens": compute.context_tokens,
        "kappa_flops_per_parameter_token": compute.kappa,
        "n_parameters_raw": result.n_parameters,
        "d_tokens_raw": result.d_tokens,
        "predicted_loss": result.predicted_loss,
        "regime": result.regime,
        "saturation": result.saturation,
        "active_bounds": list(result.active_bounds),
        "budget_geometry": result.budget_geometry,
        "c_min_flops": result.allocation_box.c_min_flops,
        "c_box_flops": result.allocation_box.c_box_flops,
        "stationary_residual_relative": result.stationary_residual_relative,
        "cost": dict(result.cost),
        "stationary_point_diagnostic": {
            "role": "unconstrained equality-slice stationary point; diagnostic only when outside the box",
            "n_parameters_raw": result.stationary_n_parameters,
            "d_tokens_raw": result.stationary_d_tokens,
            "predicted_loss": result.stationary_predicted_loss,
            "inside_validity_box": result.stationary_point_in_validity_box,
        },
        "quality_coordinate": compute.quality_coordinate,
        "quality_flops": 0.0,
    }


def infeasible_record(budget: float, context: int, reason: str) -> dict[str, Any]:
    """The record of a budget below ``C_min`` (no affordable box point)."""
    return {
        "status": "INFEASIBLE_BELOW_C_MIN",
        "budget_flops": budget,
        "context_tokens": context,
        "reason": reason,
    }


__all__ = ["allocation_record", "fmt", "infeasible_record", "unused_text", "write_artifacts"]
