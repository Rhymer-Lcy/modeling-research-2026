"""Validation of the itemized Q3 provenance ledger.

Every load-bearing formula, coefficient, budget, context value, quality-cost
parameter, threshold and conclusion is one ledger item.  An item must name at
least one authorized source (with a file hash, Git reference or DOCX locator)
or derive from other ledger items, record its verified value or semantics and
the transformation that produced it, and carry a status and a limitation.

A source whose kind or path is a PDF, a screenshot, a manual transcription, a
cached extraction, a chat or an AI-produced intermediate is rejected outright,
so no item can rest on either quarantined PDF or on anecdotal material, whether
directly or relabelled.  Any ``UNVERIFIED`` item blocks acceptance.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

ALLOWED_SOURCE_KINDS = frozenset({
    "canonical_docx",
    "organizer_attachment",
    "organizer_manifest",
    "intake_receipt",
    "accepted_interface",
    "tracked_upstream_artifact",
    "tracked_q3_artifact",
})
FORBIDDEN_SOURCE_KINDS = frozenset({
    "pdf",
    "screenshot",
    "social_media",
    "manual_transcription",
    "cached_extraction",
    "ai_intermediate",
    "chat",
})
FORBIDDEN_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic")
STATUSES = frozenset({"VERIFIED", "DERIVED", "MODEL_CONDITIONAL", "UNVERIFIED"})
REQUIRED_FIELDS = ("id", "category", "value", "sources", "derivation", "status", "limitation")


class ProvenanceError(ValueError):
    """A ledger item lacks, or relies on forbidden, provenance."""


def _check_source(item_id: str, source: Mapping[str, Any]) -> None:
    kind = source.get("kind")
    if kind in FORBIDDEN_SOURCE_KINDS:
        raise ProvenanceError(item_id + ": forbidden provenance kind " + repr(kind))
    if kind not in ALLOWED_SOURCE_KINDS:
        raise ProvenanceError(item_id + ": unknown provenance kind " + repr(kind))
    path = str(source.get("path", ""))
    if path.casefold().endswith(FORBIDDEN_SUFFIXES):
        raise ProvenanceError(item_id + ": PDF or image path cannot carry load-bearing provenance")
    if not path or path.startswith("/") or ":" in path.split("/", 1)[0]:
        raise ProvenanceError(item_id + ": source path must be repository-relative")
    if not any(source.get(key) for key in ("sha256", "git_blob_sha1", "locator")):
        raise ProvenanceError(item_id + ": source needs a SHA-256, Git blob reference or locator")


def validate_ledger(items: Iterable[Mapping[str, Any]], *, require_all_verified: bool = True) -> int:
    """Validate every ledger item and return the item count."""
    seen: set[str] = set()
    items = list(items)
    identifiers = {str(item.get("id")) for item in items}
    for item in items:
        for field in REQUIRED_FIELDS:
            if field not in item or item[field] in (None, "", []):
                raise ProvenanceError(str(item.get("id")) + ": missing ledger field " + field)
        item_id = str(item["id"])
        if item_id in seen:
            raise ProvenanceError(item_id + ": duplicate ledger item")
        seen.add(item_id)
        if item["status"] not in STATUSES:
            raise ProvenanceError(item_id + ": unknown status " + repr(item["status"]))
        if require_all_verified and item["status"] == "UNVERIFIED":
            raise ProvenanceError(item_id + ": UNVERIFIED item blocks acceptance")
        sources = item["sources"]
        if not isinstance(sources, list):
            raise ProvenanceError(item_id + ": sources must be a list")
        for source in sources:
            if not isinstance(source, dict):
                raise ProvenanceError(item_id + ": each source must be an object")
            if source.get("kind") == "ledger_item":
                if source.get("id") not in identifiers:
                    raise ProvenanceError(item_id + ": derives from unknown ledger item " + repr(source.get("id")))
                continue
            _check_source(item_id, source)
        if all(source.get("kind") == "ledger_item" for source in sources) and item["status"] == "VERIFIED":
            raise ProvenanceError(item_id + ": a purely derived item must be DERIVED or MODEL_CONDITIONAL")
    return len(items)


__all__ = [
    "ALLOWED_SOURCE_KINDS",
    "FORBIDDEN_SOURCE_KINDS",
    "ProvenanceError",
    "validate_ledger",
]
