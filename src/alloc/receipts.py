"""Strict Q3 input and accepted-interface receipt boundary.

This module is the only Q3 boundary for immutable local inputs and accepted
IF1/IF2/IF3 handoffs.  Every production input is named in one explicit
allowlist with a recorded role.  Quarantined PDFs are rejected lexically,
before any filesystem metadata or content access.  Accepted interfaces are
hash-checked before parsing and then validated against the shared contract.

IF1 and IF2 are released to Q3 as identity receipts only: their bytes are
verified, their contracts and scope limits are checked, and their content is
then withheld.  Q3 therefore has no code path through which IF1 quality values
or IF2 composition coefficients could enter an allocation.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src import interfaces as ifc
from src.paths import (
    ATT_B,
    ATT_C,
    ATTACHMENTS,
    PROBLEM_F_INTERFACES,
    PROBLEM_F_RAW,
    PROBLEM_F_SOURCE,
    REPO_ROOT,
    TABLES,
    require,
)


ACCEPTED_INTERFACE_SHA256 = {
    "IF1": "b8ec99ca38f2e466b427fd1a7d88858048924cc590bbe881a966d141eb9bdeb8",
    "IF2": "9f2a83da45633858822c8416b5fa70a9537a06b07ac9056e50d871492b16ff91",
    "IF3": "720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514",
}

INTERFACE_FILENAMES = {
    "IF1": "q1-if1-domain-quality.json",
    "IF2": "q1-if2-mixture-response.json",
    "IF3": "IF3_classic.json",
}

#: Tracked upstream receipts that publish each accepted interface hash.  The
#: constants above are cross-checked against them rather than trusted alone.
ACCEPTED_INTERFACE_RECEIPTS = {
    "IF1": TABLES / "q1-if1-summary.md",
    "IF2": TABLES / "q1-if2-summary.md",
    "IF3": TABLES / "q2-final-closure.md",
}

QUARANTINED_PDF_FILENAMES = frozenset({
    "data_description.original.pdf",
    "data_description.sanitized.m2.pdf",
})

DOCX_PATH = PROBLEM_F_SOURCE / "problem_statement.docx"
C7_PATH = ATT_C / "model_architecture_metadata.csv"
MANIFEST_PATH = ATTACHMENTS / "source_manifest.json"
INTAKE_MANIFEST_PATH = PROBLEM_F_RAW / "attachment_sha256_manifest.tsv"
LOO_PATH = TABLES / "q2-uncertainty-robustness.md"

#: B8 is never a Q3 input.  Its canonical location is named here only so that
#: tests can prove the boundary rejects it; nothing in Q3 opens it.
B8_PATH = ATT_B / "supplementary_NQ_experiment_large.csv"


class ForbiddenQ3Input(ValueError):
    """A quarantined PDF, a traversal, or a write was offered to a Q3 boundary."""


class UnauthorizedQ3Input(ValueError):
    """A file is outside the explicit Q3 production input allowlist."""


class AcceptedInterfaceError(ValueError):
    """An accepted IF1/IF2/IF3 handoff is missing, altered, or invalid."""


class AcceptedInterfaceHashMismatch(AcceptedInterfaceError):
    """An accepted interface's immutable raw bytes do not match its receipt."""


class IF2ScopeError(AcceptedInterfaceError):
    """IF2 was not retained as the released 1M-only object."""


class IdentityOnlyInterfaceError(AcceptedInterfaceError):
    """IF1/IF2 content was requested through the Q3 identity-only boundary."""


@dataclass(frozen=True)
class AuthorizedInput:
    """One explicitly authorized Q3 production input and its recorded role."""

    key: str
    path: Path
    kind: str
    role: str

    @property
    def relative_path(self) -> str:
        """Canonical repository-relative spelling, independent of platform case."""
        return self.path.relative_to(REPO_ROOT).as_posix()


AUTHORIZED_Q3_INPUTS: tuple[AuthorizedInput, ...] = (
    AuthorizedInput(
        "canonical_problem_statement_docx", DOCX_PATH, "organizer_source",
        "canonical methodological authority for every Q3 formula, coefficient, budget and domain",
    ),
    AuthorizedInput(
        "c7_model_architecture_metadata", C7_PATH, "organizer_source",
        "direct observed data: the C7 context-length grid (max_position_embeddings)",
    ),
    AuthorizedInput(
        "organizer_source_manifest", MANIFEST_PATH, "organizer_source",
        "organizer description, byte count and row count of the C7 file",
    ),
    AuthorizedInput(
        "intake_sha256_manifest", INTAKE_MANIFEST_PATH, "intake_receipt",
        "accepted T-006 intake SHA-256 record for the C7 file and the organizer manifest",
    ),
    AuthorizedInput(
        "accepted_if1", PROBLEM_F_INTERFACES / INTERFACE_FILENAMES["IF1"], "accepted_interface",
        "identity and contract receipt only; content withheld from Q3",
    ),
    AuthorizedInput(
        "accepted_if2", PROBLEM_F_INTERFACES / INTERFACE_FILENAMES["IF2"], "accepted_interface",
        "identity, contract and 1M-scope receipt only; content withheld from Q3",
    ),
    AuthorizedInput(
        "accepted_if3", PROBLEM_F_INTERFACES / INTERFACE_FILENAMES["IF3"], "accepted_interface",
        "sole canonical loss law and validity box",
    ),
    AuthorizedInput(
        "accepted_q2_loo_evidence", LOO_PATH, "tracked_upstream_artifact",
        "published Q2 leave-one-trajectory-out parameter vectors for robustness propagation",
    ),
)


def _key(path: Path | str) -> str:
    """Normalized comparison key; never used as a recorded spelling."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


_AUTHORIZED_BY_KEY = {_key(entry.path): entry for entry in AUTHORIZED_Q3_INPUTS}


def is_forbidden_path(path: Path | str) -> bool:
    """Return whether a path is a quarantined or any other PDF, lexically."""
    name = Path(os.fspath(path)).name.casefold()
    return name in QUARANTINED_PDF_FILENAMES or name.endswith(".pdf")


def reject_forbidden_q3_input(path: Path | str) -> Path:
    """Reject a PDF before stat, open, hash, parse, or traversal."""
    if is_forbidden_path(path):
        raise ForbiddenQ3Input(
            "PDF material is not an authorized automated Q3 input: " + Path(os.fspath(path)).name
        )
    return Path(os.fspath(path))


def authorized_q3_input_paths() -> Mapping[str, Path]:
    """Return the complete, explicit set of immutable Q3 production inputs."""
    return {entry.key: entry.path for entry in AUTHORIZED_Q3_INPUTS}


def authorized_input(path: Path | str) -> AuthorizedInput:
    """Return the allowlist entry for a path after PDF rejection, before any read."""
    reject_forbidden_q3_input(path)
    entry = _AUTHORIZED_BY_KEY.get(_key(path))
    if entry is None:
        raise UnauthorizedQ3Input(
            "Q3 production input is not in the explicit authorized allowlist: "
            + Path(os.fspath(path)).name
        )
    require(entry.path)
    return entry


def require_authorized_q3_input(path: Path | str) -> Path:
    """Return the canonical allowlisted path, or fail before opening anything."""
    return authorized_input(path).path


def repo_relative(path: Path | str) -> str:
    """Return a repository-relative POSIX path, using the allowlist spelling if any."""
    entry = _AUTHORIZED_BY_KEY.get(_key(path))
    source = entry.path if entry is not None else Path(os.fspath(path))
    return source.relative_to(REPO_ROOT).as_posix()


def sha256_authorized_q3_input(path: Path | str) -> str:
    """Hash one explicit authorized input after its pre-read authorization check."""
    source = require_authorized_q3_input(path)
    return hashlib.sha256(source.read_bytes()).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    """Return the Git blob object id of ``data`` (a tracked-file content reference)."""
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


@dataclass(frozen=True)
class AcceptedInterface:
    """The accepted IF3 handoff: immutable bytes, payload and shared contract."""

    kind: str
    path: Path
    sha256: str
    payload: Mapping[str, Any]
    interface: ifc.IF3ScalingLaw


@dataclass(frozen=True)
class InterfaceIdentityReceipt:
    """An IF1/IF2 identity receipt whose content is deliberately inaccessible."""

    kind: str
    path: Path
    sha256: str
    contract_validated: bool
    scope: Mapping[str, Any]

    @property
    def payload(self) -> Mapping[str, Any]:
        raise IdentityOnlyInterfaceError(
            self.kind + " is released to Q3 as an identity receipt only; its content cannot "
            "enter Q3 allocation, quality coordinates or cross-scale composition"
        )

    @property
    def interface(self) -> object:
        return self.payload


def _build_interface(kind: str, payload: Mapping[str, Any]):
    classes = {
        "IF1": ifc.IF1DomainQuality,
        "IF2": ifc.IF2MixtureResponse,
        "IF3": ifc.IF3ScalingLaw,
    }
    cls = classes[kind]
    fields = {field.name for field in dataclasses.fields(cls)}
    extra = set(payload) - fields
    missing = fields - set(payload)
    if extra or missing:
        raise AcceptedInterfaceError(
            kind + " payload does not match the shared contract; extra="
            + repr(sorted(extra)) + " missing=" + repr(sorted(missing))
        )
    values = dict(payload)
    try:
        values["provenance"] = ifc.Provenance(**values["provenance"])
        if kind == "IF3":
            values["q_term_provenance"] = ifc.Provenance(**values["q_term_provenance"])
        return cls(**values)
    except (KeyError, TypeError) as exc:
        raise AcceptedInterfaceError(kind + " provenance cannot reconstruct shared contract") from exc


def require_if2_1m_scope(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Require every released IF2 1M-only restriction before identity use."""
    if payload.get("fit_scale") != "1M":
        raise IF2ScopeError("IF2 fit_scale must be '1M'")
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise IF2ScopeError("IF2 lacks validation metadata")
    scope = validation.get("scope_release")
    if not isinstance(scope, dict):
        raise IF2ScopeError("IF2 lacks a 1M scope-release receipt")
    required_scope = {
        "scope_release_pass": True,
        "fit_scale": "1M",
        "broad_transfer_pass": False,
        "a8_a9_absolute_transfer_pass": False,
        "a10_a11_out_of_design_shape_pass": False,
    }
    for key, expected in required_scope.items():
        if scope.get(key) != expected:
            raise IF2ScopeError("IF2 scope receipt " + key + " must be " + repr(expected))
    limits = scope.get("limitations")
    if not isinstance(limits, dict):
        raise IF2ScopeError("IF2 scope receipt lacks limitations")
    required_limits = {
        "absolute_use_outside_1M": "PROHIBITED",
        "scale_invariance_supported": False,
        "A8_A9_absolute_transfer_certified": False,
        "A10_A11_out_of_design_shape_certified": False,
        "fitted_10B_70B_extrapolation": "NOT RELEASED",
    }
    for key, expected in required_limits.items():
        if limits.get(key) != expected:
            raise IF2ScopeError("IF2 limitation " + key + " must be " + repr(expected))
    acceptance = validation.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("release_pass") is not False:
        raise IF2ScopeError("IF2 broad release_pass must remain false")
    return {
        "fit_scale": "1M",
        "absolute_use_outside_1M": "PROHIBITED",
        "scale_invariance_supported": False,
        "fitted_10B_70B_extrapolation": "NOT RELEASED",
        "q3_use": "identity receipt only; no IF2 coefficient enters Q3",
    }


def require_if1_partial_unimputed(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Require IF1 to remain a partial-coverage proxy with unmapped domains unimputed."""
    coverage = payload.get("coverage_fraction")
    mapping = payload.get("mixture_to_quality")
    if not isinstance(coverage, (int, float)) or not math.isfinite(coverage) or not 0.0 < coverage < 1.0:
        raise AcceptedInterfaceError("IF1 coverage_fraction must remain a partial fraction in (0, 1)")
    if not isinstance(mapping, dict) or not mapping:
        raise AcceptedInterfaceError("IF1 lacks its mixture-to-quality mapping")
    unmapped = sorted(domain for domain, target in mapping.items() if target is None)
    if not unmapped:
        raise AcceptedInterfaceError("IF1 must retain unmapped mixture domains without imputed quality")
    return {
        "mixture_domains": len(mapping),
        "unmapped_mixture_domains": len(unmapped),
        "coverage_fraction": float(coverage),
        "q3_use": "identity receipt only; no IF1 quality is a Q3 quality coordinate or imputed",
    }


def load_accepted_interface(
    kind: str,
    path: Path | None = None,
    *,
    expected_sha256: str | None = None,
) -> AcceptedInterface | InterfaceIdentityReceipt:
    """Hash-check, parse, and shared-contract validate one immutable handoff.

    Production callers use the canonical allowlisted path.  An explicit path is
    accepted only for narrow mutation fixtures and is still PDF-checked first.
    IF3 is returned with its payload; IF1 and IF2 only as identity receipts.
    """
    if kind not in INTERFACE_FILENAMES:
        raise KeyError("unknown accepted interface kind: " + repr(kind))
    if path is None:
        source = require_authorized_q3_input(PROBLEM_F_INTERFACES / INTERFACE_FILENAMES[kind])
    else:
        source = reject_forbidden_q3_input(path)
        if not source.is_file():
            raise AcceptedInterfaceError(kind + " interface is missing: " + source.name)
    raw = source.read_bytes()
    observed_sha256 = hashlib.sha256(raw).hexdigest()
    expected = expected_sha256 or ACCEPTED_INTERFACE_SHA256[kind]
    if observed_sha256 != expected:
        raise AcceptedInterfaceHashMismatch(
            kind + " SHA-256 " + observed_sha256 + " is not the accepted " + expected
            + "; install the accepted producer bytes, do not regenerate"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptedInterfaceError(kind + " bytes are not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise AcceptedInterfaceError(kind + " payload must be a JSON object")
    interface = _build_interface(kind, payload)
    try:
        interface.validate()
    except ifc.InterfaceError as exc:
        raise AcceptedInterfaceError(kind + " failed shared interface validation: " + str(exc)) from exc
    if kind == "IF3":
        return AcceptedInterface(kind, source, observed_sha256, payload, interface)
    scope = require_if2_1m_scope(payload) if kind == "IF2" else require_if1_partial_unimputed(payload)
    return InterfaceIdentityReceipt(kind, source, observed_sha256, True, scope)


def load_all_accepted_interfaces() -> Mapping[str, AcceptedInterface | InterfaceIdentityReceipt]:
    """Verify all required accepted handoffs before a Q3 execution begins."""
    return {kind: load_accepted_interface(kind) for kind in ("IF1", "IF2", "IF3")}


def verify_accepted_hash_receipts(
    receipts: Mapping[str, Path] | None = None,
) -> Mapping[str, str]:
    """Require each accepted hash to be published in its tracked upstream receipt."""
    output: dict[str, str] = {}
    for kind, receipt in (receipts or ACCEPTED_INTERFACE_RECEIPTS).items():
        text = require(receipt).read_text(encoding="utf-8")
        if ACCEPTED_INTERFACE_SHA256[kind] not in text:
            raise AcceptedInterfaceError(
                kind + " accepted SHA-256 is not published in its tracked receipt " + receipt.name
            )
        output[kind] = receipt.relative_to(REPO_ROOT).as_posix()
    return output


__all__ = [
    "ACCEPTED_INTERFACE_RECEIPTS",
    "ACCEPTED_INTERFACE_SHA256",
    "AUTHORIZED_Q3_INPUTS",
    "AcceptedInterface",
    "AcceptedInterfaceError",
    "AcceptedInterfaceHashMismatch",
    "AuthorizedInput",
    "B8_PATH",
    "C7_PATH",
    "DOCX_PATH",
    "ForbiddenQ3Input",
    "IF2ScopeError",
    "INTAKE_MANIFEST_PATH",
    "INTERFACE_FILENAMES",
    "IdentityOnlyInterfaceError",
    "InterfaceIdentityReceipt",
    "LOO_PATH",
    "MANIFEST_PATH",
    "QUARANTINED_PDF_FILENAMES",
    "UnauthorizedQ3Input",
    "authorized_input",
    "authorized_q3_input_paths",
    "git_blob_sha1",
    "is_forbidden_path",
    "load_accepted_interface",
    "load_all_accepted_interfaces",
    "reject_forbidden_q3_input",
    "repo_relative",
    "require_authorized_q3_input",
    "require_if1_partial_unimputed",
    "require_if2_1m_scope",
    "sha256_authorized_q3_input",
    "verify_accepted_hash_receipts",
]
