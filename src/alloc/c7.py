"""Independent derivation of the observed C7 context-length support.

The observed ``L_ctx`` grid is derived here from the accepted C7 bytes, never
read back from a receipt.  The C7 file and the organizer manifest are bound to
the accepted T-006 intake SHA-256 record, the byte count to the organizer
manifest, and the row count to the manifest's own note.  Both the receipt
generator and the receipt consumer call :func:`derive_c7_support`, so a receipt
whose context grid differs from the actual accepted C7 support cannot be loaded.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from typing import Any

from .receipts import (
    C7_PATH,
    INTAKE_MANIFEST_PATH,
    MANIFEST_PATH,
    repo_relative,
    require_authorized_q3_input,
    sha256_authorized_q3_input,
)

C7_MANIFEST_NAME = "C_efficiency_evolution/model_architecture_metadata.csv"
MANIFEST_INTAKE_NAME = "source_manifest.json"


class C7SupportError(ValueError):
    """The accepted C7 context support cannot be established from its sources."""


def read_intake_hashes() -> dict[str, tuple[int, str]]:
    """Return the T-006 intake ``relative_path -> (bytes, sha256)`` record."""
    source = require_authorized_q3_input(INTAKE_MANIFEST_PATH)
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows or set(rows[0]) != {"relative_path", "bytes", "sha256"}:
        raise C7SupportError("intake SHA-256 manifest has an unexpected header")
    return {row["relative_path"]: (int(row["bytes"]), row["sha256"]) for row in rows}


def derive_c7_support() -> dict[str, Any]:
    """Derive the observed C7 context support from the accepted C7 bytes."""
    context_path = require_authorized_q3_input(C7_PATH)
    manifest_path = require_authorized_q3_input(MANIFEST_PATH)
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw.decode("utf-8"))
    records = manifest.get("files", manifest) if isinstance(manifest, dict) else manifest
    if not isinstance(records, list):
        raise C7SupportError("source_manifest.json must contain a list of source records")
    matching = [record for record in records if record.get("file") == C7_MANIFEST_NAME]
    if len(matching) != 1:
        raise C7SupportError("expected exactly one C7 record in the organizer manifest")
    manifest_record = matching[0]

    raw = context_path.read_bytes()
    c7_sha256 = sha256_authorized_q3_input(context_path)
    manifest_sha256 = sha256_authorized_q3_input(manifest_path)
    intake = read_intake_hashes()
    if intake.get(C7_MANIFEST_NAME) != (len(raw), c7_sha256):
        raise C7SupportError("C7 bytes or SHA-256 differ from the accepted T-006 intake record")
    if intake.get(MANIFEST_INTAKE_NAME) != (len(manifest_raw), manifest_sha256):
        raise C7SupportError("organizer manifest differs from the accepted T-006 intake record")
    if int(manifest_record.get("bytes", -1)) != len(raw):
        raise C7SupportError("C7 byte count differs from the organizer manifest")

    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    if not rows or "max_position_embeddings" not in rows[0] or "model_name" not in rows[0]:
        raise C7SupportError("C7 metadata lacks max_position_embeddings or model_name")
    try:
        values = [int(row["max_position_embeddings"]) for row in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise C7SupportError("C7 context values must be integer token counts") from exc
    if any(value <= 0 for value in values):
        raise C7SupportError("C7 context values must be positive")
    expected_rows = re.search(r"(\d+)个主流", str(manifest_record.get("note", "")))
    if expected_rows is None or len(rows) != int(expected_rows.group(1)):
        raise C7SupportError("C7 row count differs from the organizer manifest note")

    counts = Counter(values)
    grid = sorted(counts)
    models: dict[int, list[str]] = {value: [] for value in grid}
    for row, value in zip(rows, values):
        name = row["model_name"].strip()
        if not name:
            raise C7SupportError("C7 metadata has a context row without model_name")
        models[value].append(name)
    return {
        "path": repo_relative(context_path),
        "sha256": c7_sha256,
        "bytes": len(raw),
        "rows": len(rows),
        "field": "max_position_embeddings",
        "unit": "tokens",
        "observed_grid_tokens": grid,
        "observed_frequency": {str(value): counts[value] for value in grid},
        "observed_range_tokens": [grid[0], grid[-1]],
        "representative_operating_regimes": [
            {"context_tokens": value, "observed_model_count": counts[value],
             "observed_models": sorted(models[value]), "provenance_status": "observed"}
            for value in grid
        ],
        "regime_selection_rule": (
            "One observed regime per unique C7 context value; all source rows are retained. "
            "No preferred subset, interpolation or extrapolation is inferred."
        ),
        "direct_data_provenance": {
            "organizer_manifest_record": manifest_record,
            "organizer_manifest": {"path": repo_relative(manifest_path), "sha256": manifest_sha256},
            "intake_record": {
                "path": repo_relative(INTAKE_MANIFEST_PATH),
                "sha256": sha256_authorized_q3_input(INTAKE_MANIFEST_PATH),
                "c7_bytes_and_sha256_match": True,
                "organizer_manifest_bytes_and_sha256_match": True,
            },
            "row_count_matches_manifest_note": True,
        },
    }


__all__ = ["C7SupportError", "C7_MANIFEST_NAME", "derive_c7_support", "read_intake_hashes"]
