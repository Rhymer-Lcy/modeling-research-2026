"""Claim-language contract for the Q4 forecast and the T-012 handoff (T-011 v3).

Parameter-count growth is not training-compute growth. The frontier forecast
therefore carries three distinct kinds of number, and each must say what it is:

* the **historical / direct-score continuation** of the direct frontier trend;
* **parameter-scale-growth scenarios**, which slow the frontier's log N
  component and are never compute-growth scenarios;
* the **assumption-based transferred compute-slowdown sensitivity**, which
  transfers a compute share estimated on a small, non-representative subset and
  is never an identified population effect.

The generator renders only these labels and checks its own output with the
functions below before writing; the self-test feeds them planted violations to
prove they fire. The same module checks that the T-011 review package keeps the
mandatory Q4 source-coverage items T-012 must carry into the manuscript.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

HISTORICAL_LABEL = "historical / direct-score continuation"
PARAMETER_SCALE_LABEL = "parameter-scale-growth scenario"
COMPUTE_SENSITIVITY_LABEL = "assumption-based transferred compute-slowdown sensitivity"
COMPUTE_TRANSFER_STATEMENT = (
    "Because representative historical compute is unavailable for this frontier, the compute-slowdown "
    "forecast transfers the compute-associated share estimated on the small pretrained C4 subset. It is "
    "therefore a scenario sensitivity, not an identified population effect.")

#: Phrases that would promote the transferred sensitivity to an identified effect.
FORBIDDEN_COMPUTE_CLAIMS = (
    r"directly observed (population )?(effect|forecast)",
    r"empirically identified (bc )?compute (share|effect)",
    r"causal compute effect",
    r"identified compute (share|effect) (for|of) (the )?(bc|panel|population)",
)

#: Mandatory Q4 source-coverage items of the T-012 handoff contract. Every
#: pattern must occur in that item's bullet of the review package.
DOWNSTREAM_ITEMS: Dict[str, Sequence[str]] = {
    "C3": (r"\bC3\b", r"auxiliary", r"duplicate", r"scale", r"manuscript"),
    "C4": (r"\bC4\b", r"\b94\b", r"\b62\b", r"representative", r"open"),
    "C8": (r"\bC8\b", r"T-009", r"BBH", r"MUSR", r"MATH", r"prohibit", r"manuscript"),
}
DOWNSTREAM_HEADING = "### T-012 must preserve: mandatory Q4 source coverage"


class ClaimError(ValueError):
    """Generated or handoff text violates the T-011 v3 claim-language contract."""


def parameter_scale_label_errors(label: str) -> List[str]:
    low = label.lower()
    errors = []
    if "parameter-scale" not in low and "param_scale" not in low:
        errors.append("label is not marked as parameter-scale")
    if "compute" in low:
        errors.append("a parameter-scale label may not mention compute")
    return errors


def historical_label_errors(label: str) -> List[str]:
    low = label.lower()
    errors = []
    if "historical" not in low or "continuation" not in low:
        errors.append("label is not marked as historical continuation")
    if "compute" in low or "slowdown" in low:
        errors.append("the historical continuation may not be labelled a slowdown / compute forecast")
    return errors


def compute_sensitivity_errors(text: str) -> List[str]:
    low = text.lower()
    errors = []
    for marker in ("assumption-based", "transferred"):
        if marker not in low:
            errors.append("compute-slowdown text lacks '" + marker + "'")
    for pattern in FORBIDDEN_COMPUTE_CLAIMS:
        if re.search(pattern, low):
            errors.append("forbidden claim: " + pattern)
    return errors


def section(text: str, heading: str) -> str:
    """Text from ``heading`` to the next heading of the same or higher level ('' if absent)."""
    lines = text.split("\n")
    level = len(heading) - len(heading.lstrip("#"))
    for i, line in enumerate(lines):
        if line.strip() == heading.strip():
            out = []
            for later in lines[i + 1:]:
                stripped = later.lstrip()
                hashes = len(stripped) - len(stripped.lstrip("#"))
                if stripped.startswith("#") and 0 < hashes <= level:
                    break
                out.append(later)
            return "\n".join(out)
    return ""


def downstream_contract_missing(handover: str) -> List[str]:
    """Items of the mandatory Q4 source-coverage contract that are absent or incomplete."""
    body = section(handover, DOWNSTREAM_HEADING)
    if not body:
        return sorted(DOWNSTREAM_ITEMS)
    bullets = re.split(r"\n(?=- \*\*)", "\n" + body)
    missing = []
    for item, patterns in DOWNSTREAM_ITEMS.items():
        block = next((b for b in bullets if b.lstrip("\n").startswith("- **" + item)), "")
        if not block or not all(re.search(p, block) for p in patterns):
            missing.append(item)
    return missing


def clock_values_missing(text: str, values: Sequence[str]) -> List[str]:
    """Formatted date-clock values that do not appear in ``text``."""
    return [v for v in values if v not in text]


def require(errors: List[str], where: str) -> None:
    if errors:
        raise ClaimError(where + ": " + "; ".join(errors))


__all__ = [
    "HISTORICAL_LABEL", "PARAMETER_SCALE_LABEL", "COMPUTE_SENSITIVITY_LABEL", "COMPUTE_TRANSFER_STATEMENT",
    "FORBIDDEN_COMPUTE_CLAIMS", "DOWNSTREAM_ITEMS", "DOWNSTREAM_HEADING", "ClaimError",
    "parameter_scale_label_errors", "historical_label_errors", "compute_sensitivity_errors", "section",
    "downstream_contract_missing", "clock_values_missing", "require",
]
