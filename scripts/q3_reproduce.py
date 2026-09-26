"""Reproduce the receipt-gated Q3 allocation artifacts deterministically.

Runs the source receipt and every Q3 generator twice, requiring byte-identical
artifacts, LF-only output, and no mutation of the local source inputs or IF
interfaces.  It does not authorize nonbaseline quality scenarios: every pass
remains on the receipt-approved semantic baseline ``Q0``.

Writes:
    results/tables/q3-reproduction.json
    results/tables/q3-reproduction.md

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_reproduce.py
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Mapping

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.alloc import ACCEPTED_CLASSIC_IF3_SHA256, load_classic_if3  # noqa: E402
from src.paths import (  # noqa: E402
    ATT_C,
    PROBLEM_F_INTERFACES,
    PROBLEM_F_SOURCE,
    TABLES,
    ensure,
    require,
)

GENERATORS = (
    "q3_source_receipt.py",
    "q3_allocate.py",
    "q3_context_sensitivity.py",
    "q3_quality_cost_sensitivity.py",
)

ARTIFACTS = (
    TABLES / "q3-source-receipt.json",
    TABLES / "q3-source-receipt.md",
    TABLES / "q3-allocation.json",
    TABLES / "q3-allocation.md",
    TABLES / "q3-context-sensitivity.json",
    TABLES / "q3-context-sensitivity.md",
    TABLES / "q3-quality-cost-sensitivity.json",
    TABLES / "q3-quality-cost-sensitivity.md",
)

SOURCE_TREES = (
    PROBLEM_F_SOURCE,
    ATT_C,
)
SOURCE_FILES = (
    ATT_C.parent / "source_manifest.json",
)
INTERFACE_PATHS = {
    "IF1": PROBLEM_F_INTERFACES / "q1-if1-domain-quality.json",
    "IF2": PROBLEM_F_INTERFACES / "q1-if2-mixture-response.json",
    "IF3": PROBLEM_F_INTERFACES / "IF3_classic.json",
}


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of one immutable or generated file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_tree(root: Path) -> dict[str, Mapping[str, object]]:
    """Snapshot files under one relevant local source tree without writing to it."""
    source = require(root)
    output: dict[str, Mapping[str, object]] = {}
    for path in sorted(source.rglob("*")):
        if path.is_file():
            stat = path.stat()
            output[path.relative_to(REPO).as_posix()] = {
                "sha256": sha256(path),
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
    if not output:
        raise RuntimeError("required Q3 source tree is empty: " + root.relative_to(REPO).as_posix())
    return output


def source_snapshot() -> dict[str, Mapping[str, object]]:
    """Snapshot all source-receipt inputs used by the Q3 receipt generator."""
    output: dict[str, Mapping[str, object]] = {}
    for root in SOURCE_TREES:
        overlap = set(output) & set(snapshot_tree(root))
        if overlap:
            raise RuntimeError("Q3 source snapshot roots overlap: " + repr(sorted(overlap)))
        output.update(snapshot_tree(root))
    for path in SOURCE_FILES:
        source = require(path)
        stat = source.stat()
        key = source.relative_to(REPO).as_posix()
        if key in output:
            raise RuntimeError("Q3 source snapshot repeats " + key)
        output[key] = {
            "sha256": sha256(source),
            "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    return output


def interface_snapshot() -> dict[str, Mapping[str, object]]:
    """Record IF1/IF2 absence or bytes and require an accepted immutable IF3."""
    require(PROBLEM_F_INTERFACES)
    output: dict[str, Mapping[str, object]] = {}
    for name, path in INTERFACE_PATHS.items():
        if path.exists():
            stat = path.stat()
            output[name] = {
                "status": "PRESENT",
                "path": path.relative_to(REPO).as_posix(),
                "sha256": sha256(path),
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        else:
            output[name] = {"status": "NOT_PRESENT"}
    if output["IF3"].get("status") != "PRESENT":
        raise RuntimeError("accepted IF3 interface is missing")
    if output["IF3"].get("sha256") != ACCEPTED_CLASSIC_IF3_SHA256:
        raise RuntimeError("accepted IF3 interface hash is not the required producer handoff")
    return output


def public_source_summary(
    snapshot: Mapping[str, Mapping[str, object]], unchanged: bool
) -> dict[str, object]:
    """Expose aggregate source verification without an input-file inventory."""
    return {
        "file_count": len(snapshot),
        "content_size_mtime_unchanged": unchanged,
    }


def public_interface_summary(
    snapshot: Mapping[str, Mapping[str, object]], unchanged: bool
) -> dict[str, Mapping[str, object]]:
    """Expose only interface verification outcomes, never local input metadata."""
    output: dict[str, Mapping[str, object]] = {}
    for name, record in snapshot.items():
        summary: dict[str, object] = {
            "status": record["status"],
            "content_size_mtime_unchanged": unchanged,
        }
        if name == "IF3":
            summary["accepted_sha256"] = ACCEPTED_CLASSIC_IF3_SHA256
        output[name] = summary
    return output


def has_carriage_return(path: Path) -> bool:
    """Return whether an artifact violates the required LF-only serialization."""
    return b"\r" in path.read_bytes()


def run_pass(label: str) -> tuple[dict[str, str], list[str]]:
    """Run the full Q3 generator surface once and hash declared artifacts."""
    for script in GENERATORS:
        print(label + ": " + script, flush=True)
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / script)],
            cwd=REPO,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    hashes = {
        path.relative_to(REPO).as_posix(): sha256(require(path))
        for path in ARTIFACTS
    }
    with_cr = [
        path.relative_to(REPO).as_posix()
        for path in ARTIFACTS
        if has_carriage_return(path)
    ]
    return hashes, with_cr


def runtime_versions() -> Mapping[str, str]:
    """Return the declared direct-runtime package versions."""
    import numpy
    import pandas
    import scipy
    import yaml

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "pandas": pandas.__version__,
        "pyyaml": yaml.__version__,
    }


def markdown_report(
    payload: Mapping[str, object],
) -> str:
    """Render the deterministic reproduction receipt as a reviewable table."""
    artifacts = payload["artifact_sha256"]
    assert isinstance(artifacts, Mapping)
    interfaces = payload["interface_verification"]
    assert isinstance(interfaces, Mapping)
    lines = [
        "# Q3 reproduction",
        "",
        "Generated by `scripts/q3_reproduce.py`. Do not edit by hand.",
        "",
        "The receipt and all baseline-only Q3 generators ran in two complete passes. Hashes",
        "are of generated bytes; every declared artifact is required to be LF-only. The",
        "reproduction check preserves the semantic `Q0` baseline and runs no numerical",
        "nonbaseline quality-cost scenario.",
        "",
        "Runtime: `" + json.dumps(payload["runtime"], sort_keys=True) + "`.",
        "",
        "Deterministic seed policy: " + str(payload["seed_policy"]),
        "",
        "| Artifact | SHA-256, pass 1 | Pass 2 identical |",
        "| --- | --- | --- |",
    ]
    for path, digest in artifacts.items():
        lines.append(
            "| `" + str(path) + "` | `" + str(digest) + "` | "
            + ("yes" if payload["two_passes_byte_identical"] else "**NO**") + " |"
        )
    lines += [
        "",
        "Generators, in order: "
        + ", ".join("`scripts/" + script + "`" for script in GENERATORS) + ".",
        "",
        "Two complete passes byte-identical: **"
        + ("PASS" if payload["two_passes_byte_identical"] else "FAIL") + "**.",
        "",
        "Every declared artifact LF-only in both passes: **"
        + ("PASS" if payload["lf_only"] else "FAIL") + "**.",
        "",
        "Source-receipt inputs unchanged in content, size, and modification time: **"
        + ("PASS" if payload["source_inputs_unchanged"] else "FAIL") + "** ("
        + str(payload["source_input_file_count"]) + " files).",
        "",
        "Interface snapshot unchanged in content, size, and modification time: **"
        + ("PASS" if payload["interfaces_unchanged"] else "FAIL") + "**.",
        "",
        "| Interface | State | Content/size/mtime unchanged | Accepted SHA-256 |",
        "| --- | --- | --- | --- |",
    ]
    for name, record in interfaces.items():
        assert isinstance(record, Mapping)
        lines.append(
            "| `" + str(name) + "` | " + str(record["status"])
            + " | " + ("yes" if record["content_size_mtime_unchanged"] else "**NO**")
            + " | "
            + ("`" + str(record["accepted_sha256"]) + "`" if "accepted_sha256" in record else "—")
            + " |"
        )
    lines += [
        "",
        "IF1 and IF2 are not Q3 inputs. If absent, their retained `NOT_PRESENT` status is",
        "checked across both passes rather than replaced or fabricated. IF3 is required to",
        "remain the accepted immutable classic-law byte sequence.",
        "",
        "No numerical nonbaseline quality scenario ran. Cross-scale quality benefit remains",
        "prohibited because the accepted classic IF3 law has no quality-loss term.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    before_sources = source_snapshot()
    before_interfaces = interface_snapshot()
    load_classic_if3()
    first_hashes, first_cr = run_pass("pass 1")
    second_hashes, second_cr = run_pass("pass 2")
    after_sources = source_snapshot()
    after_interfaces = interface_snapshot()
    load_classic_if3()

    identical = first_hashes == second_hashes
    lf_only = not first_cr and not second_cr
    sources_unchanged = before_sources == after_sources
    interfaces_unchanged = before_interfaces == after_interfaces
    payload = {
        "schema_version": "q3-reproduction-v1",
        "purpose": "T-010 deterministic baseline-only Q3 regeneration receipt",
        "runtime": runtime_versions(),
        "seed_policy": (
            "Q3 generators draw no random values. The accepted IF3 bootstrap seed is retained "
            "as descriptive uncertainty provenance only; no allocation uncertainty resampling runs."
        ),
        "generators": ["scripts/" + script for script in GENERATORS],
        "artifact_sha256": second_hashes,
        "two_passes_byte_identical": identical,
        "lf_only": lf_only,
        "source_input_verification": public_source_summary(after_sources, sources_unchanged),
        "source_input_file_count": len(after_sources),
        "source_inputs_unchanged": sources_unchanged,
        "interface_verification": public_interface_summary(after_interfaces, interfaces_unchanged),
        "interfaces_unchanged": interfaces_unchanged,
        "accepted_classic_if3_sha256": ACCEPTED_CLASSIC_IF3_SHA256,
    }
    out_dir = ensure(TABLES)
    json_path = out_dir / "q3-reproduction.json"
    markdown_path = out_dir / "q3-reproduction.md"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(markdown_report(payload), encoding="utf-8", newline="\n")
    print("wrote " + json_path.relative_to(REPO).as_posix())
    print("wrote " + markdown_path.relative_to(REPO).as_posix())
    print(
        "two passes identical: " + str(identical)
        + "; LF-only: " + str(lf_only)
        + "; source inputs unchanged: " + str(sources_unchanged)
        + "; interfaces unchanged: " + str(interfaces_unchanged)
    )
    return 0 if identical and lf_only and sources_unchanged and interfaces_unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
