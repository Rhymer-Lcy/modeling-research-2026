"""Baseline-only Q3 allocation consumer for the accepted classic IF3 law.

This package deliberately exposes no quality-coordinate optimizer.  The frozen
Q3 receipt permits canonical allocation only at its semantic baseline ``Q0``,
where the specified positive-part quality cost is exactly zero.
"""

from .classic import (
    ACCEPTED_CLASSIC_IF3_SHA256,
    AcceptedClassicIF3,
    AcceptedIF3HashMismatch,
    BaselineScopeError,
    ClassicIF3ContractError,
    SourceReceiptError,
    classic_loss,
    load_classic_if3,
)
from .constraint import (
    BaselineCompute,
    SourceReceipt,
    cost_breakdown,
    load_source_receipt,
)
from .solver import AllocationResult, SolverAgreement, solve_baseline, solve_baseline_numeric
from .uncertainty import AllocationUncertaintyEvidence, describe_allocation_uncertainty
from .validity import AllocationBox, NoValidityBoxAllocation

__all__ = [
    "ACCEPTED_CLASSIC_IF3_SHA256",
    "AcceptedClassicIF3",
    "AcceptedIF3HashMismatch",
    "AllocationBox",
    "AllocationResult",
    "AllocationUncertaintyEvidence",
    "BaselineCompute",
    "BaselineScopeError",
    "ClassicIF3ContractError",
    "NoValidityBoxAllocation",
    "SolverAgreement",
    "SourceReceipt",
    "SourceReceiptError",
    "classic_loss",
    "cost_breakdown",
    "describe_allocation_uncertainty",
    "load_classic_if3",
    "load_source_receipt",
    "solve_baseline",
    "solve_baseline_numeric",
]
