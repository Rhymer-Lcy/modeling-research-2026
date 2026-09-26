"""Receipts for everything T-011 consumes, checked before anything is computed.

Each helper makes one misuse impossible rather than merely unlikely:

* T-011 reads a local input only through :func:`read_input`, which refuses any
  path outside an explicit allowlist. IF2, IF1, Attachment B (which holds B8)
  and the C8 per-task records are not on it, so the Q2 quality/composition
  quarantines and the C8 MATH quarantine cannot be crossed by accident;
* every Attachment-C file T-011 reads is hashed against the intake manifest,
  and the manifest itself against the hash its intake receipt records;
* the classic IF3 is refused unless its bytes hash to the value recorded in
  the tracked T-008 closure table, its contract validates, its external units
  are raw counts and its Q interval is the no-quality sentinel;
* the panel is rebuilt only through the accepted T-009 code path and must match
  the facts the accepted T-009 tables record.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd

from src import interfaces as ifc
from src.paths import (
    ATT_C,
    PROBLEM_F_INTERFACES,
    PROBLEM_F_RAW,
    REPO_ROOT,
    TABLES,
    require,
)
from src.scaling.units import predict_natural

# ---------------------------------------------------------------------------
# Input allowlist
# ---------------------------------------------------------------------------

#: Attachment-C files T-011 reads directly, keyed by the organizer's C number.
C_FILES: Dict[str, str] = {
    "C1": "leaderboard_cleaned.csv",
    "C2": "leaderboard_enhanced.csv",
    "C3": "leaderboard_extended_timeseries.csv",
    "C4": "epoch_all_ai_models.csv",
    "C5": "loss_benchmark_bridge.csv",
    "C6": "loss_benchmark_bridge_expanded.csv",
}

IF3_FILE: Path = PROBLEM_F_INTERFACES / "IF3_classic.json"
MANIFEST: Path = PROBLEM_F_RAW / "attachment_sha256_manifest.tsv"
INTAKE_RECEIPT: Path = PROBLEM_F_RAW / "INTAKE_RECEIPT.md"
IF3_SUMMARY: Path = TABLES / "q2-final-closure.md"

ALLOWED_INPUTS: Tuple[Path, ...] = tuple(
    [ATT_C / name for name in C_FILES.values()] + [IF3_FILE, MANIFEST, INTAKE_RECEIPT, IF3_SUMMARY]
)


class ForbiddenInput(PermissionError):
    """T-011 was asked to read an input outside its allowlist."""


class SourceMismatch(ValueError):
    """A local input's bytes differ from its recorded intake hash."""


class AcceptedInterfaceError(ValueError):
    """An interface object is not the accepted one, or breaks its contract."""


class OutsideValidityBox(ValueError):
    """The classic IF3 was evaluated outside its validity box without consent."""


class PanelReceiptError(ValueError):
    """The rebuilt T-009 panel does not match the accepted T-009 record."""


def read_input(path: Path) -> Path:
    """Return ``path`` if T-011 may read it; refuse anything else."""
    resolved = Path(path).resolve()
    if resolved not in {p.resolve() for p in ALLOWED_INPUTS}:
        raise ForbiddenInput(
            "T-011 may not read " + _rel(resolved) + "; its inputs are the allowlisted "
            "Attachment-C tables, the classic IF3 and the intake records only")
    return require(resolved)


def _rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Source surface
# ---------------------------------------------------------------------------

def manifest_sha_from_receipt() -> str:
    """The manifest hash recorded in the intake receipt (exactly one)."""
    text = read_input(INTAKE_RECEIPT).read_text(encoding="utf-8")
    found = re.findall(r"rows, SHA-256 `([0-9a-f]{64})`", text)
    if len(found) != 1:
        raise SourceMismatch("the intake receipt must record exactly one manifest hash")
    return found[0]


def manifest_rows() -> Dict[str, Tuple[int, str]]:
    """``relative_path -> (bytes, sha256)`` from the intake manifest."""
    path = read_input(MANIFEST)
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return {r["relative_path"]: (int(r["bytes"]), r["sha256"]) for r in rows}


def verify_sources(c_keys: Sequence[str] = tuple(C_FILES)) -> List[Dict[str, object]]:
    """Hash each consumed Attachment-C file against the manifest; raise on any mismatch."""
    recorded = manifest_sha_from_receipt()
    actual = sha256_file(read_input(MANIFEST))
    if actual != recorded:
        raise SourceMismatch("attachment manifest hash " + actual + " != intake receipt " + recorded)
    rows = manifest_rows()
    out: List[Dict[str, object]] = []
    for key in c_keys:
        rel = "C_efficiency_evolution/" + C_FILES[key]
        path = read_input(ATT_C / C_FILES[key])
        size, want = rows[rel]
        got = sha256_file(path)
        ok = got == want and path.stat().st_size == size
        out.append({"key": key, "path": "data_local/problem-f/raw/real_attachments/" + rel,
                    "bytes": size, "sha256": got, "match": ok})
        if not ok:
            raise SourceMismatch(rel + " does not match the intake manifest")
    return out


def verify_c_tree() -> Dict[str, int]:
    """Hash every file of the restored Attachment-C tree against the manifest."""
    rows = {k: v for k, v in manifest_rows().items() if k.startswith("C_efficiency_evolution/")}
    root = ATT_C.parent
    on_disk = {p.relative_to(root).as_posix() for p in ATT_C.rglob("*") if p.is_file()}
    missing = sorted(set(rows) - on_disk)
    extra = sorted(on_disk - set(rows))
    bad = [rel for rel, (size, want) in rows.items()
           if rel in on_disk and ((root / rel).stat().st_size != size or sha256_file(root / rel) != want)]
    return {"manifest_rows": len(rows), "on_disk": len(on_disk), "missing": len(missing),
            "extra": len(extra), "mismatched": len(bad)}


# ---------------------------------------------------------------------------
# Classic IF3
# ---------------------------------------------------------------------------

CLASSIC_FORM = "E + A*N**-alpha + B*D**-beta"
CLASSIC_PARAMS = frozenset({"E", "A", "alpha", "B", "beta"})
#: A box expressed in billions would put its lower N and D bounds below one;
#: raw counts put them far above this floor. Used only to detect the unit
#: regime, never as a model constant.
RAW_COUNT_FLOOR = 1.0e6
BOX_RTOL = 1.0e-9


def accepted_if3_sha256() -> str:
    """Read the accepted classic IF3 hash from the tracked T-008 closure table."""
    text = read_input(IF3_SUMMARY).read_text(encoding="utf-8")
    rows = re.findall(r"^\|\s*SHA-256\s*\|\s*`([0-9a-f]{64})`\s*\|\s*$", text, flags=re.M)
    if len(rows) != 1:
        raise AcceptedInterfaceError("q2-final-closure.md must record exactly one IF3 SHA-256 row")
    return rows[0]


def check_if3_contract(payload: Mapping) -> None:
    """Raise unless the payload is the classic, raw-unit, no-quality IF3."""
    if payload.get("functional_form") != CLASSIC_FORM:
        raise AcceptedInterfaceError("IF3 functional form is not the classic N-D law")
    if set(payload.get("params", {})) != CLASSIC_PARAMS:
        raise AcceptedInterfaceError("IF3 parameters must be exactly the classic five; a quality exponent is not accepted")
    box = payload.get("validity_box", {})
    if [float(v) for v in box.get("Q", [])] != [1.0, 1.0]:
        raise AcceptedInterfaceError("IF3 Q interval must be the [1, 1] no-quality sentinel")
    for axis in ("N", "D"):
        lo, hi = (float(v) for v in box[axis])
        if not (RAW_COUNT_FLOOR < lo < hi):
            raise AcceptedInterfaceError("IF3 " + axis + " box is not in raw counts (lower bound " + repr(lo) + ")")
    if payload.get("bootstrap", {}).get("unit") != "model":
        raise AcceptedInterfaceError("IF3 bootstrap unit must be 'model'")


@dataclass(frozen=True)
class IF3Receipt:
    sha256: str
    params: Dict[str, float]
    box: Dict[str, Tuple[float, float]]
    provenance_notes: str

    def inside(self, n, d) -> np.ndarray:
        n = np.asarray(n, dtype=float)
        d = np.asarray(d, dtype=float)
        (n_lo, n_hi), (d_lo, d_hi) = self.box["N"], self.box["D"]
        return ((n >= n_lo * (1 - BOX_RTOL)) & (n <= n_hi * (1 + BOX_RTOL))
                & (d >= d_lo * (1 - BOX_RTOL)) & (d <= d_hi * (1 + BOX_RTOL)))

    def predict(self, n, d, *, allow_extrapolation: bool = False) -> np.ndarray:
        """Classic IF3 loss at raw (N, D). Refuses any outside-box point by default.

        No Q argument exists: the accepted law has no quality dimension, and
        ``predict_natural`` itself refuses a Q for classic parameters.
        """
        inside = self.inside(n, d)
        if not allow_extrapolation and not bool(np.all(inside)):
            raise OutsideValidityBox(str(int((~inside).sum())) + " point(s) lie outside the IF3 validity box")
        return predict_natural(self.params, n, d)


def build_if3(payload: Mapping) -> ifc.IF3ScalingLaw:
    names = [f.name for f in dataclasses.fields(ifc.IF3ScalingLaw)]
    if set(payload) != set(names):
        raise AcceptedInterfaceError("IF3 payload does not match the IF3ScalingLaw contract")
    kwargs = dict(payload)
    kwargs["provenance"] = ifc.Provenance(**payload["provenance"])
    kwargs["q_term_provenance"] = ifc.Provenance(**payload["q_term_provenance"])
    return ifc.IF3ScalingLaw(**kwargs)


def load_if3(raw: bytes | None = None, expected_sha: str | None = None) -> IF3Receipt:
    """Hash-check, validate and unit-check the accepted classic IF3.

    ``raw`` exists so the self-test can offer deliberately corrupted bytes; in
    production the object is always read from its canonical local path.
    """
    if raw is None:
        raw = read_input(IF3_FILE).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    want = expected_sha or accepted_if3_sha256()
    if sha != want:
        raise AcceptedInterfaceError("IF3 hash " + sha + " is not the accepted " + want)
    payload = json.loads(raw.decode("utf-8"))
    obj = build_if3(payload)
    obj.validate()
    check_if3_contract(payload)
    box = {k: (float(v[0]), float(v[1])) for k, v in payload["validity_box"].items()}
    return IF3Receipt(sha256=sha, params={k: float(v) for k, v in payload["params"].items()},
                      box=box, provenance_notes=payload["provenance"]["notes"])


# ---------------------------------------------------------------------------
# T-009 panel
# ---------------------------------------------------------------------------

DATE_SOURCES = {"pub_date": "primary", "c4_pub_date": "primary", "submission_date": "fallback", "none": "none"}


def accepted_panel_facts() -> Dict[str, int]:
    """Facts recorded by the accepted T-009 tables, parsed rather than typed."""
    schema = require(TABLES / "q4-panel-schema.md").read_text(encoding="utf-8")
    dates = require(TABLES / "q4-date-coverage.md").read_text(encoding="utf-8")
    meta = require(TABLES / "q4-c4-metadata-coverage.md").read_text(encoding="utf-8")

    def one(pattern: str, text: str) -> int:
        found = re.findall(pattern, text, flags=re.M)
        if len(found) != 1:
            raise PanelReceiptError("accepted T-009 table lacks a unique match for " + pattern)
        return int(found[0].replace(",", ""))

    return {
        "rows": one(r"^Rows: ([\d,]+) \(unique models\)", schema),
        "columns": one(r"Columns: ([\d,]+)\.", schema),
        "c4_linked": one(r"C4-linked rows: ([\d,]+)\.", schema),
        "primary_dates": one(r"^- primary \(Epoch publication date\): ([\d,]+)", dates),
        "fallback_dates": one(r"^- fallback \(submission date\): ([\d,]+)", dates),
        "no_date": one(r"^- none: ([\d,]+)", dates),
        "training_compute": one(r"^- training compute \(FLOP\) non-null: ([\d,]+)", meta),
    }


def panel_facts(panel: pd.DataFrame) -> Dict[str, int]:
    return {
        "rows": int(len(panel)),
        "columns": int(panel.shape[1]),
        "c4_linked": int((panel["link_method"] != "unlinked").sum()),
        "primary_dates": int((panel["date_confidence"] == "primary").sum()),
        "fallback_dates": int((panel["date_confidence"] == "fallback").sum()),
        "no_date": int((panel["date_confidence"] == "none").sum()),
        "training_compute": int(panel["c4_compute_flop"].notna().sum()),
    }


def check_panel(panel: pd.DataFrame) -> Dict[str, int]:
    """Row uniqueness, date-source semantics and agreement with the accepted record."""
    if int(panel["model"].duplicated().sum()) != 0:
        raise PanelReceiptError("T-009 panel rows are not unique by model")
    bad_source = set(panel["date_source"].unique()) - set(DATE_SOURCES)
    if bad_source:
        raise PanelReceiptError("unknown date_source values: " + repr(sorted(bad_source)))
    implied = panel["date_source"].map(DATE_SOURCES)
    if not bool((implied == panel["date_confidence"]).all()):
        raise PanelReceiptError("date_confidence disagrees with date_source (a fallback labelled primary?)")
    none = panel["date_confidence"] == "none"
    if bool(panel.loc[none, "analysis_date"].notna().any()) or bool(panel.loc[~none, "analysis_date"].isna().any()):
        raise PanelReceiptError("analysis_date presence disagrees with date_confidence")
    facts = panel_facts(panel)
    accepted = accepted_panel_facts()
    diff = {k: (facts[k], accepted[k]) for k in accepted if facts[k] != accepted[k]}
    if diff:
        raise PanelReceiptError("rebuilt panel differs from the accepted T-009 record: " + repr(diff))
    return facts


def load_panel() -> pd.DataFrame:
    """Rebuild the accepted panel through the T-009 code path and check it."""
    from src.panel.panel import build_panel

    panel = build_panel()
    check_panel(panel)
    return panel


def panel_fingerprint(panel: pd.DataFrame) -> str:
    """SHA-256 of the panel serialised with LF line endings (platform-independent)."""
    return hashlib.sha256(panel.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


__all__ = [
    "C_FILES", "ALLOWED_INPUTS", "IF3_FILE", "ForbiddenInput", "SourceMismatch",
    "AcceptedInterfaceError", "OutsideValidityBox", "PanelReceiptError", "read_input",
    "sha256_file", "verify_sources", "verify_c_tree", "accepted_if3_sha256", "check_if3_contract",
    "IF3Receipt", "load_if3", "accepted_panel_facts", "panel_facts", "check_panel", "load_panel",
    "panel_fingerprint", "DATE_SOURCES",
]
