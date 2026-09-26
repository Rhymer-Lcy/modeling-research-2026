"""Deterministic mutation validation of the T-010 Q3 detectors.

Proves that the checks which support T-010 acceptance can fail.  Everything
runs against the committed sources in a temporary detached Git worktree, so no
production file in the working tree is ever modified:

1. require the working tree's T-010 sources (``src/alloc``, ``scripts/q3_*``)
   to be committed, and record their Git blob ids;
2. create a detached worktree of ``HEAD`` in a temporary directory and give it
   copies of exactly the local-only allowlisted inputs (never a PDF);
3. regenerate the Q3 artifacts there and require a clean baseline self-test;
4. for each code mutant: apply its exact text replacement(s) to the worktree
   copy, run its detector (the self-test, or a data probe for defects only a
   forged input can reveal), record exit status and failed checks, restore the
   file and verify the restoration by SHA-256 and ``git diff``;
5. run data probes that feed forged receipts and altered inputs to the real
   allocation, receipt and LOO scripts, and require each to be rejected;
6. remove the worktree and verify the working tree's T-010 sources are unchanged.

Classification fails closed.  A self-test mutant is KILLED only when the
self-test exits nonzero with one of the mutant's declared detectors among the
failed checks, and SURVIVED_CLEAN only with exit 0, no failed check and a
complete, successful report of the baseline size; anything else is
INCONCLUSIVE.  A probe-detected mutant is KILLED when its declared-invalid input
is accepted, SURVIVED_CLEAN when the input is rejected with the exact expected
exception and unchanged outputs, and INCONCLUSIVE otherwise.  Unverified
restoration of any source, input or output is an INTEGRITY_FAILURE.  A mutant
passes only with its declared outcome; a ``REDUNDANT_SURVIVOR`` must survive
cleanly and its paired full-removal mutant must be killed, and only a layer with
an independent second defence may be declared redundant.  Runner self-checks
feed synthetic records through the same functions and must show that a bad
record cannot reach an overall PASS.  The DOCX whole-file SHA-256 pin is the
only accepted-source identity anchor: probe P14 runs the receipt generator
itself, so a generator that would record a changed DOCX hash is detected; the
consumer's receipt/DOCX hash comparison (probe P12) is receipt/source
consistency, not a second anchor.

Writes:
    results/tables/q3-mutation-validation.json
    results/tables/q3-mutation-validation.md

Run through the declared environment (takes several minutes):
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_mutation_validation.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.q3_selftest import FORGERIES, forged_receipt  # noqa: E402
from src.alloc import (  # noqa: E402
    AUTHORIZED_Q3_INPUTS,
    git_blob_sha1,
    install_q3_input_guard,
    require_authorized_q3_input,
)
from src.alloc.inputguard import LOG_ENVIRONMENT_VARIABLE  # noqa: E402
from src.alloc.report import write_artifacts  # noqa: E402

GENERATORS = (
    "q3_source_receipt.py",
    "q3_allocate.py",
    "q3_context_sensitivity.py",
    "q3_regime_analysis.py",
    "q3_quality_cost_sensitivity.py",
    "q3_loo_robustness.py",
    "q3_provenance_ledger.py",
)
SOURCE_PATHSPECS = ("src/alloc", "scripts/q3_*")
SELFTEST = "scripts/q3_selftest.py"
TIMEOUT = 1200
LINE = re.compile(r"^(PASS|FAIL) \[(\w+)\] (.*)$")

RECEIPT = "results/tables/q3-source-receipt.json"
RECEIPT_MD = "results/tables/q3-source-receipt.md"
ALLOCATION = "results/tables/q3-allocation.json"
CONTEXT = "results/tables/q3-context-sensitivity.json"
LOO_TABLE = "results/tables/q3-loo-robustness.json"
C7 = "data_local/problem-f/raw/real_attachments/C_efficiency_evolution/model_architecture_metadata.csv"
DOCX = "docs_local/problem-f/source/problem_statement.docx"
LOO_SOURCE = "results/tables/q2-uncertainty-robustness.md"


@dataclass(frozen=True)
class Mutant:
    identifier: str
    target: str
    invariant: str
    behavior: str
    replacements: tuple[tuple[str, str], ...]
    detectors: tuple[str, ...]
    probe: str | None = None
    expectation: str = "KILLED"
    note: str = ""


@dataclass(frozen=True)
class Probe:
    identifier: str
    forged_input: str
    consumer: str
    outputs: tuple[str, ...]
    expected: str
    expected_exception: str | None
    prepare: Callable[[Path], None] = field(repr=False)
    restore_paths: tuple[str, ...] = ()


D = '"'
MUTANTS: tuple[Mutant, ...] = (
    Mutant("M01", "src/alloc/inputguard.py", "the process-wide input guard intercepts file access",
           "the audit hook returns before inspecting any event",
           (('def _hook(event: str, args: tuple[Any, ...]) -> None:\n    if event == "open":',
             'def _hook(event: str, args: tuple[Any, ...]) -> None:\n    return\n    if event == "open":'),),
           ("guard: opening a PDF-named fixture is refused", "guard: hashing a PDF-named fixture is refused",
            "guard: opening B8 is refused before the filesystem is touched", "guard: listing a local input directory is refused")),
    Mutant("M02", "src/alloc/receipts.py", "IF1/IF2 content is inaccessible to Q3",
           "identity receipts return their payload instead of refusing",
           (("    def payload(self) -> Mapping[str, Any]:\n        raise IdentityOnlyInterfaceError(",
             "    def payload(self) -> Mapping[str, Any]:\n        return {}\n        raise IdentityOnlyInterfaceError("),),
           ("IF1 content cannot reach Q3", "IF2 content cannot reach Q3")),
    Mutant("M03", "src/alloc/validity.py", "budgets above C_box keep the feasible upper corner (inequality, not equality)",
           "the withdrawn equality-only rule: no allocation when no point can spend the whole budget",
           (("        n_upper = min(n_max, budget / (kappa * d_min))\n",
             "        if budget > c_box:\n            raise NoValidityBoxAllocation('no budget-saturating point')\n"
             "        n_upper = min(n_max, budget / (kappa * d_min))\n"),),
           ("1e24 is the upper corner with budget slack", "section 'budget inequality' completed",
            "section 'compute and closed form' completed", "guard: the workflow reaches the corrected 1e24 regime")),
    Mutant("M04", "src/alloc/receipts.py", "every *.pdf path is refused before access",
           "only the two quarantined file names are refused",
           (('return name in QUARANTINED_PDF_FILENAMES or name.endswith(".pdf")', "return name in QUARANTINED_PDF_FILENAMES"),),
           ("any PDF is rejected by the interface loader", "DOCX verification rejects a PDF path")),
    Mutant("M05", "src/alloc/solver.py", "the D_max saturation kink is a candidate optimum",
           "the kink candidate is dropped from the exact solver",
           (("    if box.contains_n(box.saturation_kink_n):\n        candidates.append(box.saturation_kink_n)\n", ""),),
           ("numerical search agrees at 1e+22", "1e22 at 4096 is D_max-bound and saturating",
            "brute-force 2-D grid never beats the solver at 1e+22")),
    Mutant("M06", "src/alloc/receipts.py", "IF2 is refused unless released as 1M-only",
           "the fit_scale check is skipped",
           (('    if payload.get("fit_scale") != "1M":\n        raise IF2ScopeError', "    if False:\n        raise IF2ScopeError"),),
           ("IF2 declared outside 1M is rejected",)),
    Mutant("M07", "src/alloc/provenance.py", "ledger sources must be authorized, repository-relative and identified",
           "the per-source check returns immediately",
           (("def _check_source(item_id: str, source: Mapping[str, Any]) -> None:\n",
             "def _check_source(item_id: str, source: Mapping[str, Any]) -> None:\n    return\n"),),
           ("ledger: PDF-only provenance is rejected", "ledger: screenshot-only provenance is rejected",
            "ledger: an absolute path is rejected")),
    Mutant("M08", "src/alloc/provenance.py", "forbidden provenance kinds are rejected",
           "the explicit forbidden-kind list is ignored",
           (("    if kind in FORBIDDEN_SOURCE_KINDS:\n", "    if False:\n"),),
           (), expectation="REDUNDANT_SURVIVOR",
           note="backstop: the allowed-kind list still rejects pdf, screenshot and ai_intermediate; M09 removes both"),
    Mutant("M09", "src/alloc/provenance.py", "forbidden provenance kinds are rejected",
           "both the forbidden-kind list and the allowed-kind list are ignored",
           (("    if kind in FORBIDDEN_SOURCE_KINDS:\n", "    if False:\n"),
            ("    if kind not in ALLOWED_SOURCE_KINDS:\n", "    if False:\n")),
           ("ledger: PDF-only provenance is rejected", "ledger: screenshot-only provenance is rejected",
            "ledger: an AI-produced intermediate is rejected")),
    Mutant("M10", "src/alloc/constraint.py", "the receipt is not its own authority (defect A)",
           "the consumer takes verified values from the receipt's own verification block",
           (("    _require_canonical_verification(payload.get(" + D + "source_verification" + D + "), canonical)\n",
             "    canonical = payload[" + D + "source_verification" + D + "]\n    values = verified_values(canonical)\n"),),
           ("A1 forged receipt rejected", "A2 forged receipt rejected", "A3 forged receipt rejected",
            "A4 forged receipt rejected", "A5 forged receipt rejected", "A8a forged receipt rejected")),
    Mutant("M11", "src/alloc/constraint.py", "the context grid is the grid derived from the accepted C7 bytes (defect A)",
           "the C7 comparison is dropped and the receipt's own grid is used",
           (("    _require_equal(" + D + "observed C7 context support" + D + ", dict(context), c7)\n", "\n"),
            ("        contexts_tokens=tuple(c7[" + D + "observed_grid_tokens" + D + "]),",
             "        contexts_tokens=tuple(context[" + D + "observed_grid_tokens" + D + "]),")),
           ("A6 forged receipt rejected", "A7 forged receipt rejected")),
    Mutant("M12", "src/alloc/constraint.py", "extra or duplicate verification records cannot shadow canonical ones (defect A)",
           "records are de-duplicated by key and unknown keys are dropped before comparison",
           (("    keys = [str(record.get(" + D + "key" + D + ")) for record in records]\n",
             "    records = list({str(r.get(" + D + "key" + D + ")): r for r in records if r.get(" + D + "key" + D
             + ") in {c[" + D + "key" + D + "] for c in canonical[" + D + "records" + D + "]}}.values())\n"
             "    keys = [str(record.get(" + D + "key" + D + ")) for record in records]\n"),),
           ("A8b forged receipt rejected",),
           note="A8a stays rejected under this mutant because values come from the independent regeneration"),
    Mutant("M13", "src/alloc/receipts.py", "tracked inputs resolve to the pinned Git blob (defect B)",
           "the accepted-commit, HEAD and working-tree identity comparison is skipped",
           (("    for where, identity in observed.items():\n        if identity != blob:\n",
             "    for where, identity in observed.items():\n        if False:\n"),),
           ("LOO: an existing blob other than the pinned one is rejected",)),
    Mutant("M14", "src/alloc/receipts.py", "a tracked input has no working-copy byte identity (defect B)",
           "tracked inputs may again be hashed from their working-copy bytes",
           (('    if entry.kind == "tracked_upstream_artifact":\n        raise TrackedInputIdentityError(',
             "    if False:\n        raise TrackedInputIdentityError("),),
           ("LOO: a tracked input has no working-copy byte identity",)),
    Mutant("M15", "src/alloc/receipts.py", "the LOO working copy must be the accepted blob (defect B)",
           "the working-tree identity is not checked",
           (('        "working tree": _git("hash-object", "--", relative).decode("ascii").strip(),\n', ""),),
           (), probe="P13"),
    Mutant("M16", "src/alloc/sourcedocx.py", "each parsed DOCX value must equal its expectation",
           "the parsed-value comparison is skipped",
           (("        if extracted != check.expected:\n", "        if False:\n"),),
           ("a parsed source value that differs from its expectation is rejected",)),
    Mutant("M17", "src/alloc/sourcedocx.py", "the DOCX must be the accepted whole file",
           "the whole-file SHA-256 pin is skipped",
           (("        if digest != ACCEPTED_DOCX_SHA256:\n", "        if False:\n"),),
           (), probe="P14",
           note="the pin is the only accepted-source identity anchor: the receipt generator uses the same verifier, "
                "so without the pin it records a changed DOCX hash; the consumer's receipt/DOCX hash comparison is "
                "receipt/source consistency, not a second anchor"),
    Mutant("M18", "src/alloc/sourcedocx.py + src/alloc/constraint.py", "the DOCX must be the accepted whole file",
           "both the SHA-256 pin and the consumer's receipt/source DOCX-hash consistency comparison are skipped",
           (("        if digest != ACCEPTED_DOCX_SHA256:\n", "        if False:\n"),
            ('    if recorded["docx_sha256"] != canonical["docx_sha256"]:\n', "    if False:\n")),
           (), probe="P12"),
    Mutant("M19", "src/alloc/regime.py", "a transition is retained only if the regime changes",
           "every probed candidate is reported as a regime change",
           (('    return below, at, above, below["regime"] != above["regime"]\n', "    return below, at, above, True\n"),),
           ("a budget inside one regime is not reported as a transition",)),
    Mutant("M20", "src/alloc/loo.py", "LOO values must be canonical .6g output",
           "the published-format check is skipped",
           (("    if format(value, PUBLISHED_FORMAT) != text:\n", "    if False:\n"),),
           ("LOO: a non-canonical printed value is rejected",)),
    Mutant("M21", "src/alloc/quality.py", "every raw g(Q) crossing is bracketed",
           "no root is bracketed on any monotone piece",
           (("            elif _sign(left_value) != _sign(right_value) and _sign(left_value) != 0:\n", "            elif False:\n"),),
           ("quality: independent dense-grid root finding", "quality: a hand-derived convex pair",
            "quality: a hand-placed crossing within 1e-9 of Q = 1 is found")),
    Mutant("M22", "src/alloc/solver.py", "at C = C_box the optimum is the saturating upper corner (defect D)",
           "a budget equal to C_box is labelled as slack",
           (('    saturation = "SATURATED" if saturated else "SLACK"\n',
             '    saturation = "SATURATED" if saturated and compute.budget_flops < box.c_box_flops * (1.0 - 1e-12) else "SLACK"\n'),),
           ("fixture C/kappa=36 gives hand-derived SATURATED:N_max+D_max", "fixture corners are exactly saturating")),
    Mutant("M23", "src/alloc/inputguard.py", "allowlisted inputs cannot be opened for writing",
           "the write-intent check is skipped",
           (("    if _write_intent(mode, flags):\n", "    if False:\n"),),
           ("guard: opening C7 for writing is refused",)),
    Mutant("M24", "src/alloc/inputguard.py", "automatic traversal of local input trees is refused",
           "directory listing and scanning events are ignored",
           (("    elif event in _TRAVERSAL_EVENTS:\n", "    elif False:\n"),),
           ("guard: listing a local input directory is refused", "guard: scanning a local input directory is refused")),
    Mutant("M25", "src/alloc/receipts.py", "only allowlisted inputs pass the input boundary",
           "an unlisted path is admitted with an ad hoc entry",
           (("    if entry is None:\n        raise UnauthorizedQ3Input(",
             "    if entry is None:\n        return AuthorizedInput(" + D + "unlisted" + D + ", Path(os.fspath(path)), "
             + D + "unlisted" + D + ", " + D + "unlisted" + D + ")\n        raise UnauthorizedQ3Input("),),
           ("B8 is not an authorized input", "a non-allowlisted tracked file is rejected")),
)


def _write_receipt(worktree: Path, case: str) -> None:
    path = worktree / RECEIPT
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(forged_receipt(case, payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _append_c7_row(worktree: Path) -> None:
    path = worktree / C7
    text = path.read_bytes().decode("utf-8")
    header = next(csv.reader(io.StringIO(text)))
    row = {name: "" for name in header}
    row.update(model_name="forged/model", max_position_embeddings="262144")
    buffer = io.StringIO()
    csv.DictWriter(buffer, fieldnames=header, lineterminator="\n").writerow(row)
    data = path.read_bytes()
    separator = b"" if data.endswith(b"\n") else b"\n"
    path.write_bytes(data + separator + buffer.getvalue().encode("utf-8"))


def _touch_docx(worktree: Path) -> None:
    with zipfile.ZipFile(worktree / DOCX, "a") as archive:
        archive.writestr("customXml/t010-probe.xml", "<probe/>")


def _alter_loo(worktree: Path) -> None:
    path = worktree / LOO_SOURCE
    data = path.read_bytes()
    row = b"| 0.070542 | 1.68983 | 406.636 |"
    if data.count(row) != 1:
        raise RuntimeError("LOO probe row is not unique in the working copy")
    path.write_bytes(data.replace(row, b"| 0.070542 | 1.68983 | 406.637 |"))


PROBES: tuple[Probe, ...] = (
    Probe("P00", "none (control)", "scripts/q3_allocate.py", (ALLOCATION,), "ACCEPTED", None, lambda wt: None),
) + tuple(
    Probe("P" + format(index, "02d"), "receipt forgery " + case + ": " + description, "scripts/q3_allocate.py", (ALLOCATION,),
          "REJECTED", "SourceReceiptError", lambda wt, case=case: _write_receipt(wt, case), (RECEIPT,))
    for index, (case, (description, _)) in enumerate(FORGERIES.items(), start=1)
) + (
    Probe("P10", "receipt forgery A6 (context 262144) fed to the context-sensitivity script", "scripts/q3_context_sensitivity.py",
          (CONTEXT,), "REJECTED", "SourceReceiptError", lambda wt: _write_receipt(wt, "A6"), (RECEIPT,)),
    Probe("P11", "C7 bytes altered: a model row with context 262144 appended", "scripts/q3_allocate.py", (ALLOCATION,),
          "REJECTED", "SourceReceiptError", _append_c7_row, (C7,)),
    Probe("P12", "DOCX bytes altered without changing any verified value, fed to the allocation consumer with the "
          "existing receipt (rejected by the accepted-DOCX SHA-256 pin; the receipt's recorded DOCX hash is only a "
          "receipt/source consistency check)", "scripts/q3_allocate.py", (ALLOCATION,),
          "REJECTED", "SourceReceiptError", _touch_docx, (DOCX,)),
    Probe("P13", "LOO working copy altered (trajectory 0.070542: A 406.636 -> 406.637)", "scripts/q3_loo_robustness.py", (LOO_TABLE,),
          "REJECTED", "TrackedInputIdentityError", _alter_loo, (LOO_SOURCE,)),
    Probe("P14", "DOCX bytes altered without changing any verified value, fed to the receipt generator itself",
          "scripts/q3_source_receipt.py", (RECEIPT, RECEIPT_MD), "REJECTED", "SourceVerificationError", _touch_docx, (DOCX,)),
)


def child_environment() -> dict[str, str]:
    """Child processes keep no guard log of their own and never write bytecode.

    Without bytecode caches a mutated or restored module is always compiled from
    its current bytes, so a stale ``.pyc`` can never mask a mutant.
    """
    environment = {key: value for key, value in os.environ.items() if key != LOG_ENVIRONMENT_VARIABLE}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def git(*args: str, cwd: Path = REPO, check: bool = True) -> str:
    completed = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if check and completed.returncode != 0:
        raise RuntimeError("git " + args[0] + " failed: " + completed.stderr.strip()[:300])
    return completed.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tested_sources() -> list[dict[str, str]]:
    listing = git("ls-tree", "-r", "HEAD", "--", "src/alloc", "scripts")
    output = []
    for line in listing.splitlines():
        meta, path = line.split("\t", 1)
        if path.startswith("src/alloc/") or re.fullmatch(r"scripts/q3_[^/]+\.py", path):
            output.append({"path": path, "git_blob_id": meta.split()[2]})
    return output


def run_script(worktree: Path, script: str, *extra: str) -> tuple[int, str, str]:
    completed = subprocess.run([sys.executable, str(worktree / script), *extra], cwd=worktree, capture_output=True, text=True,
                               env=child_environment(), timeout=TIMEOUT)
    return completed.returncode, completed.stdout, completed.stderr


FAIL_CLOSED = re.compile(r"FAIL-CLOSED: ([A-Za-z_]\w*):")
REDUNDANT_PAIRS = {"M08": "M09"}


def final_exception(stderr: str) -> str | None:
    """Class name of the exception that ended a consumer run, or None if none is identifiable."""
    for line in reversed(stderr.strip().splitlines()):
        text = line.strip()
        closed = FAIL_CLOSED.search(text)
        if closed:
            return closed.group(1)
        match = re.match(r"^([A-Za-z_][\w.]*)(?::|$)", text)
        if match and (match.group(1).endswith("Error") or match.group(1).endswith("Exception") or "." in match.group(1)):
            return match.group(1).rsplit(".", 1)[-1]
    return None


def selftest(worktree: Path) -> dict[str, Any]:
    """Run the self-test; return its exit code, FAIL lines and parsed report (None if absent or unreadable)."""
    report_path = worktree.parent / "selftest-report.json"
    report_path.unlink(missing_ok=True)
    code, stdout, _ = run_script(worktree, SELFTEST, "--report", str(report_path))
    failed = sorted(match.group(3) for match in map(LINE.match, stdout.splitlines()) if match and match.group(1) == "FAIL")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    report_path.unlink(missing_ok=True)
    return {"exit_code": code, "failed_checks": failed, "report": report}


def report_complete(report: Any, expected_checks: int) -> bool:
    """True only for a complete, successful self-test report of the expected size."""
    if not isinstance(report, dict) or not isinstance(report.get("checks"), list):
        return False
    checks = report["checks"]
    return (report.get("count_ok") is True and report.get("failures") == [] and len(checks) == expected_checks
            and all(isinstance(item, dict) and item.get("passed") is True for item in checks))


def run_probe(worktree: Path, probe: Probe) -> dict[str, Any]:
    """Run one probe and return its raw evidence.

    Both the altered inputs and the consumer's outputs are snapshotted, restored
    afterwards and verified by SHA-256, so an accepting consumer cannot leave a
    changed output behind for later runs.
    """
    paths = tuple(dict.fromkeys(probe.restore_paths + probe.outputs))
    originals = {relative: (worktree / relative).read_bytes() for relative in paths}
    try:
        probe.prepare(worktree)
        code, _, stderr = run_script(worktree, probe.consumer)
        outputs_unchanged = all(sha256(worktree / relative) == hashlib.sha256(originals[relative]).hexdigest()
                                for relative in probe.outputs)
    finally:
        for relative, data in originals.items():
            (worktree / relative).write_bytes(data)
    restored = all(sha256(worktree / relative) == hashlib.sha256(data).hexdigest() for relative, data in originals.items())
    return {
        "id": probe.identifier,
        "forged_input": probe.forged_input,
        "consumer": probe.consumer,
        "observed_command": "python " + probe.consumer + " (temporary worktree of the committed sources)",
        "expected": probe.expected,
        "expected_exception": probe.expected_exception,
        "exit_code": code,
        "exception": None if code == 0 else final_exception(stderr),
        "outputs_unchanged_by_run": outputs_unchanged,
        "inputs_and_outputs_restored_by_hash": restored,
    }


def classify_probe(evidence: dict[str, Any]) -> str:
    """ACCEPTED, REJECTED_AS_DECLARED, UNEXPECTED_REJECTION or INTEGRITY_FAILURE.

    A rejection counts as declared only with the exact expected exception and
    every consumer output unchanged by the run.
    """
    if evidence.get("inputs_and_outputs_restored_by_hash") is not True:
        return "INTEGRITY_FAILURE"
    if evidence.get("exit_code") == 0:
        return "ACCEPTED"
    if (evidence.get("expected_exception") is not None and evidence.get("exception") == evidence["expected_exception"]
            and evidence.get("outputs_unchanged_by_run") is True):
        return "REJECTED_AS_DECLARED"
    return "UNEXPECTED_REJECTION"


def probe_verdict(evidence: dict[str, Any]) -> dict[str, Any]:
    """Verdict of an unmutated data probe against its declared expectation."""
    classification = classify_probe(evidence)
    wanted = "ACCEPTED" if evidence.get("expected") == "ACCEPTED" else "REJECTED_AS_DECLARED"
    return {**evidence, "classification": classification, "verdict": "PASS" if classification == wanted else "FAIL"}


def _mutant_verdict(expectation: str, outcome: str) -> str:
    wanted = "KILLED" if expectation == "KILLED" else "SURVIVED_CLEAN"
    return "PASS" if outcome == wanted else "FAIL"


def classify_selftest_mutant(expectation: str, run: dict[str, Any], detectors: tuple[str, ...], restored: bool,
                             expected_checks: int) -> dict[str, Any]:
    """Fail-closed outcome of a self-test-detected mutant.

    KILLED needs a nonzero exit with at least one declared detector among the
    failed checks.  SURVIVED_CLEAN needs exit 0, no failed check and a complete
    successful report.  Anything else is INCONCLUSIVE; an unverified restoration
    is INTEGRITY_FAILURE.  An empty detector list never produces a survivor.
    """
    detected_by = sorted(name for name in run["failed_checks"] if any(name.startswith(item) for item in detectors))
    complete = report_complete(run.get("report"), expected_checks)
    if not restored:
        outcome = "INTEGRITY_FAILURE"
    elif run["exit_code"] != 0 and detected_by:
        outcome = "KILLED"
    elif run["exit_code"] == 0 and not run["failed_checks"] and complete:
        outcome = "SURVIVED_CLEAN"
    else:
        outcome = "INCONCLUSIVE"
    return {"failed_expected_detectors": detected_by, "report_complete": complete, "outcome": outcome,
            "killed": outcome == "KILLED", "verdict": _mutant_verdict(expectation, outcome)}


def classify_probe_mutant(expectation: str, evidence: dict[str, Any], restored: bool) -> dict[str, Any]:
    """Fail-closed outcome of a probe-detected mutant.

    The declared invalid input being accepted kills the mutant; a rejection with
    the exact expected exception and unchanged outputs is a clean survival; an
    unexpected exception or any integrity failure is never a pass.
    """
    classification = classify_probe(evidence)
    if not restored or classification == "INTEGRITY_FAILURE":
        outcome = "INTEGRITY_FAILURE"
    elif classification == "ACCEPTED":
        outcome = "KILLED"
    elif classification == "REJECTED_AS_DECLARED":
        outcome = "SURVIVED_CLEAN"
    else:
        outcome = "INCONCLUSIVE"
    return {"probe_classification": classification, "outcome": outcome, "killed": outcome == "KILLED",
            "verdict": _mutant_verdict(expectation, outcome)}


def run_mutant(worktree: Path, mutant: Mutant, expected_checks: int) -> dict[str, Any]:
    targets = [part.strip() for part in mutant.target.split("+")]
    originals = {target: (worktree / target).read_bytes() for target in targets}
    texts = {target: data.decode("utf-8") for target, data in originals.items()}
    for old, new in mutant.replacements:
        # The worktree is checked out with LF endings; matching stays correct if a checkout used CRLF.
        variants = {target: (old, new) if "\r\n" not in texts[target]
                    else (old.replace("\n", "\r\n"), new.replace("\n", "\r\n")) for target in targets}
        owners = [target for target in targets if texts[target].count(variants[target][0]) == 1]
        if len(owners) != 1:
            raise RuntimeError(mutant.identifier + ": replacement text must occur exactly once in exactly one target")
        texts[owners[0]] = texts[owners[0]].replace(*variants[owners[0]])
    probe = next((item for item in PROBES if item.identifier == mutant.probe), None) if mutant.probe else None
    if mutant.probe and (probe is None or probe.expected != "REJECTED"):
        raise RuntimeError(mutant.identifier + ": a probe detector must be a declared-invalid (REJECTED) probe")
    try:
        for target in targets:
            (worktree / target).write_bytes(texts[target].encode("utf-8"))
        if probe is None:
            run = selftest(worktree)
            command = "python " + SELFTEST + " (temporary worktree of the committed sources)"
        else:
            evidence = run_probe(worktree, probe)
            command = evidence["observed_command"] + " with probe " + probe.identifier
    finally:
        for target, data in originals.items():
            (worktree / target).write_bytes(data)
    restored = all(sha256(worktree / target) == hashlib.sha256(data).hexdigest() for target, data in originals.items())
    restored = restored and subprocess.run(["git", "-C", str(worktree), "diff", "--quiet", "HEAD", "--", *targets]).returncode == 0
    record: dict[str, Any] = {
        "id": mutant.identifier,
        "target": mutant.target,
        "invariant": mutant.invariant,
        "mutated_behavior": mutant.behavior,
        "replacements": [{"old": old, "new": new} for old, new in mutant.replacements],
        "expected_detectors": list(mutant.detectors) if probe is None else ["data probe " + probe.identifier],
        "expectation": mutant.expectation,
        "note": mutant.note,
        "observed_command": command,
        "sources_restored_by_hash_and_git": restored,
    }
    if probe is None:
        record.update(exit_code=run["exit_code"], failed_checks=run["failed_checks"],
                      report_present=run["report"] is not None,
                      **classify_selftest_mutant(mutant.expectation, run, mutant.detectors, restored, expected_checks))
    else:
        record.update(exit_code=evidence["exit_code"], probe_evidence=evidence,
                      **classify_probe_mutant(mutant.expectation, evidence, restored))
    return record


def overall_verdict(mutants: list[dict[str, Any]], probes: list[dict[str, Any]], redundancy: list[dict[str, Any]],
                    main_tree_unchanged: bool, baseline_ok: bool, runner_ok: bool) -> str:
    """PASS only if every mutant, probe, redundancy pair, runner check and integrity condition passes."""
    passed = (baseline_ok and runner_ok and main_tree_unchanged and bool(mutants) and bool(probes)
              and all(item.get("verdict") == "PASS" for item in mutants)
              and all(item.get("verdict") == "PASS" for item in probes)
              and all(item.get("survived") is True and item.get("paired_killed") is True for item in redundancy))
    return "PASS" if passed else "FAIL"


def runner_checks(expected_checks: int) -> list[dict[str, Any]]:
    """Synthetic cases proving the runner's own classification fails closed."""
    complete = {"checks": [{"name": "c", "category": "ORACLE", "passed": True}] * expected_checks,
                "count_ok": True, "failures": []}
    short = {"checks": complete["checks"][:-1], "count_ok": False, "failures": []}
    failing = {"checks": complete["checks"][:-1] + [{"name": "c", "category": "ORACLE", "passed": False}],
               "count_ok": True, "failures": ["c"]}
    rejected = {"id": "PX", "expected": "REJECTED", "expected_exception": "SourceReceiptError", "exit_code": 1,
                "exception": "SourceReceiptError", "outputs_unchanged_by_run": True, "inputs_and_outputs_restored_by_hash": True}
    wrong_exception = {**rejected, "exception": "KeyError"}
    accepted = {**rejected, "exit_code": 0, "exception": None}

    def selftest_case(expectation: str, code: int, failed: list[str], report: Any, detectors: tuple[str, ...],
                      restored: bool = True) -> str:
        run = {"exit_code": code, "failed_checks": failed, "report": report}
        return classify_selftest_mutant(expectation, run, detectors, restored, expected_checks)["verdict"]

    def probe_case(expectation: str, evidence: dict[str, Any], restored: bool = True) -> str:
        return classify_probe_mutant(expectation, evidence, restored)["verdict"]

    exit_one_empty = {"id": "MX", **classify_selftest_mutant("REDUNDANT_SURVIVOR", {"exit_code": 1, "failed_checks": [],
                                                                                      "report": None}, (), True, expected_checks)}
    good_mutant = {"id": "MY", **classify_selftest_mutant("KILLED", {"exit_code": 1, "failed_checks": ["d [no exception]"],
                                                                      "report": complete}, ("d",), True, expected_checks)}
    good_probe = probe_verdict(rejected)
    bad_probe = probe_verdict(wrong_exception)
    pair_ok = [{"survived": True, "paired_killed": True}]
    cases = [
        ("redundant survivor: exit 1, no report, empty detector list",
         selftest_case("REDUNDANT_SURVIVOR", 1, [], None, ()), "FAIL"),
        ("redundant survivor: exit 0 but no report", selftest_case("REDUNDANT_SURVIVOR", 0, [], None, ()), "FAIL"),
        ("redundant survivor: exit 0 with an incomplete report", selftest_case("REDUNDANT_SURVIVOR", 0, [], short, ()), "FAIL"),
        ("redundant survivor: exit 0 with a failed check in the report",
         selftest_case("REDUNDANT_SURVIVOR", 0, [], failing, ()), "FAIL"),
        ("redundant survivor: clean run with unverified restoration",
         selftest_case("REDUNDANT_SURVIVOR", 0, [], complete, (), restored=False), "FAIL"),
        ("killed mutant: exit 1 without a declared detector failing",
         selftest_case("KILLED", 1, ["unrelated [no exception]"], complete, ("declared",)), "FAIL"),
        ("probe mutant: rejection with the wrong exception", probe_case("KILLED", wrong_exception), "FAIL"),
        ("probe survivor: rejection with the wrong exception", probe_case("REDUNDANT_SURVIVOR", wrong_exception), "FAIL"),
        ("probe survivor: rejection with no identifiable exception",
         probe_case("REDUNDANT_SURVIVOR", {**rejected, "exception": None}), "FAIL"),
        ("probe survivor: rejection that changed a consumer output",
         probe_case("REDUNDANT_SURVIVOR", {**rejected, "outputs_unchanged_by_run": False}), "FAIL"),
        ("probe mutant: acceptance with an unrestored input",
         probe_case("KILLED", {**accepted, "inputs_and_outputs_restored_by_hash": False}), "FAIL"),
        ("probe mutant: acceptance with unrestored mutated sources", probe_case("KILLED", accepted, restored=False), "FAIL"),
        ("baseline probe: rejection with the wrong exception", bad_probe["verdict"], "FAIL"),
        ("overall: an exit-1/empty-report survivor cannot pass",
         overall_verdict([good_mutant, exit_one_empty], [good_probe], pair_ok, True, True, True), "FAIL"),
        ("overall: a wrong-exception probe cannot pass",
         overall_verdict([good_mutant], [good_probe, bad_probe], pair_ok, True, True, True), "FAIL"),
        ("control: a clean redundant survivor passes", selftest_case("REDUNDANT_SURVIVOR", 0, [], complete, ()), "PASS"),
        ("control: a mutant killed by its declared detector passes",
         selftest_case("KILLED", 1, ["declared [no exception]"], complete, ("declared",)), "PASS"),
        ("control: a probe mutant accepting the declared invalid input is killed", probe_case("KILLED", accepted), "PASS"),
        ("control: a probe survivor rejecting as declared passes", probe_case("REDUNDANT_SURVIVOR", rejected), "PASS"),
        ("control: all-passing records give an overall pass",
         overall_verdict([good_mutant], [good_probe], pair_ok, True, True, True), "PASS"),
    ]
    return [{"case": name, "expected": expected, "observed": observed, "passed": observed == expected}
            for name, observed, expected in cases]


def main() -> int:
    install_q3_input_guard()
    dirty = git("status", "--porcelain", "--", *SOURCE_PATHSPECS)
    if dirty.strip():
        print("MUTATION VALIDATION REFUSED: T-010 sources must be committed first:\n" + dirty, file=sys.stderr)
        return 1
    sources = tested_sources()
    temp = Path(tempfile.mkdtemp(prefix="t010-mutation-"))
    worktree = temp / "worktree"
    # Check out with LF endings so every tested file is byte-identical to its committed blob.
    git("-c", "core.autocrlf=false", "-c", "core.eol=lf", "worktree", "add", "--detach", str(worktree), "HEAD")
    try:
        if not all(git_blob_sha1((worktree / item["path"]).read_bytes()) == item["git_blob_id"] for item in sources):
            raise RuntimeError("worktree sources are not byte-identical to their committed blobs")
        for entry in AUTHORIZED_Q3_INPUTS:
            if entry.kind == "tracked_upstream_artifact":
                continue
            destination = worktree / entry.relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(require_authorized_q3_input(entry.path).read_bytes())
        for script in GENERATORS:
            code, _, stderr = run_script(worktree, "scripts/" + script)
            if code != 0:
                raise RuntimeError("baseline generator failed in the worktree: " + script + ": " + stderr.strip()[-300:])
        baseline = selftest(worktree)
        expected_checks = len(baseline["report"]["checks"]) if isinstance(baseline["report"], dict) else 0
        baseline_ok = (baseline["exit_code"] == 0 and not baseline["failed_checks"] and expected_checks > 0
                       and report_complete(baseline["report"], expected_checks))
        if not baseline_ok:
            raise RuntimeError("baseline self-test failed in the worktree: " + repr(baseline["failed_checks"][:5]))
        runner = runner_checks(expected_checks)
        mutants = [run_mutant(worktree, mutant, expected_checks) for mutant in MUTANTS]
        probes = [probe_verdict(run_probe(worktree, probe)) for probe in PROBES]
    finally:
        git("worktree", "remove", "--force", str(worktree), check=False)
        git("worktree", "prune", check=False)
        shutil.rmtree(temp, ignore_errors=True)
    main_tree_unchanged = not git("status", "--porcelain", "--", *SOURCE_PATHSPECS).strip() and tested_sources() == sources

    by_id = {item["id"]: item for item in mutants}
    declared = {item.identifier for item in MUTANTS if item.expectation == "REDUNDANT_SURVIVOR"}
    if declared != set(REDUNDANT_PAIRS):
        raise RuntimeError("every redundant survivor needs exactly one declared full-removal pair")
    redundancy = [{"survivor": survivor, "survived": by_id[survivor]["outcome"] == "SURVIVED_CLEAN",
                   "paired_full_removal": full, "paired_killed": by_id[full]["outcome"] == "KILLED"}
                  for survivor, full in REDUNDANT_PAIRS.items()]
    runner_ok = all(item["passed"] for item in runner)
    counts: dict[str, int] = {}
    for check in baseline["report"]["checks"]:
        counts[check["category"]] = counts.get(check["category"], 0) + 1
    outcomes: dict[str, int] = {}
    for item in mutants:
        outcomes[item["outcome"]] = outcomes.get(item["outcome"], 0) + 1
    overall = overall_verdict(mutants, probes, redundancy, main_tree_unchanged, baseline_ok, runner_ok)
    payload = {
        "schema_version": "q3-mutation-validation-v2",
        "purpose": "T-010 executable evidence that the acceptance checks detect production defects",
        "method": ("Mutants and probes run in a temporary detached Git worktree of the committed sources, supplied with "
                   "copies of the local-only allowlisted inputs; production files in the working tree are never modified. "
                   "Every mutated source, probed input and consumer output is restored and verified by SHA-256 (and git "
                   "diff for sources). Classification fails closed: a survivor needs a clean, complete run; an unexpected "
                   "exception, a changed output on rejection or an unverified restoration fails the run."),
        "tested_sources": sources,
        "baseline": {"generators": ["scripts/" + script for script in GENERATORS], "selftest_exit_code": baseline["exit_code"],
                     "selftest_checks": expected_checks, "selftest_report_complete": baseline_ok,
                     "selftest_category_counts": counts,
                     "selftest_checks_by_category": [{"name": item["name"], "category": item["category"]}
                                                     for item in baseline["report"]["checks"]]},
        "runner_checks": runner,
        "mutants": mutants,
        "redundant_defences": redundancy,
        "data_probes": probes,
        "main_tree_sources_unchanged": main_tree_unchanged,
        "summary": {
            "mutants": len(mutants),
            "expected_killed": sum(1 for item in MUTANTS if item.expectation == "KILLED"),
            "killed": outcomes.get("KILLED", 0),
            "outcomes": dict(sorted(outcomes.items())),
            "redundant_survivors": sorted(REDUNDANT_PAIRS),
            "unexpected_outcomes": [item["id"] for item in mutants if item["verdict"] != "PASS"],
            "data_probes": len(probes),
            "data_probes_passed": sum(1 for item in probes if item["verdict"] == "PASS"),
            "runner_checks": len(runner),
            "runner_checks_passed": sum(1 for item in runner if item["passed"]),
            "overall": overall,
        },
    }
    write_artifacts("q3-mutation-validation", payload, markdown(payload))
    summary = payload["summary"]
    print("mutants killed: " + str(summary["killed"]) + "/" + str(summary["mutants"]) + "; outcomes: "
          + json.dumps(summary["outcomes"], sort_keys=True) + "; data probes passed: " + str(summary["data_probes_passed"])
          + "/" + str(summary["data_probes"]) + "; runner checks passed: " + str(summary["runner_checks_passed"]) + "/"
          + str(summary["runner_checks"]) + "; overall: " + overall)
    return 0 if overall == "PASS" else 1


def markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Q3 mutation validation",
        "",
        "Generated by `scripts/q3_mutation_validation.py`. Do not edit by hand.",
        "",
        payload["method"],
        "",
        "Overall: **" + summary["overall"] + "**. Mutants: " + str(summary["mutants"]) + " (" + str(summary["expected_killed"])
        + " expected killed), outcomes " + ", ".join(key + " " + str(value) for key, value in summary["outcomes"].items())
        + "; intentionally redundant survivors: " + ", ".join(summary["redundant_survivors"]) + ". Data probes passed: "
        + str(summary["data_probes_passed"]) + "/" + str(summary["data_probes"]) + ". Runner self-checks passed: "
        + str(summary["runner_checks_passed"]) + "/" + str(summary["runner_checks"]) + ". Working-tree sources unchanged: "
        + ("yes" if payload["main_tree_sources_unchanged"] else "**NO**") + ".",
        "",
        "## Baseline self-test classification",
        "",
        "Baseline self-test exit code " + str(payload["baseline"]["selftest_exit_code"]) + "; "
        + str(payload["baseline"]["selftest_checks"]) + " checks; complete successful report: "
        + ("yes" if payload["baseline"]["selftest_report_complete"] else "**NO**") + ". `ORACLE` and `BOUNDARY` checks",
        "support acceptance; `CONSISTENCY` and `REGRESSION` checks detect regressions only; `ARTIFACT` checks guard",
        "generated tables.",
        "",
        "| Category | Checks |",
        "| --- | ---: |",
    ]
    for category, count in sorted(payload["baseline"]["selftest_category_counts"].items()):
        lines.append("| " + category + " | " + str(count) + " |")
    lines += [
        "",
        "## Runner self-checks",
        "",
        "Synthetic records run through the same classification functions as the real mutants and probes.",
        "",
        "| Case | Expected | Observed | Result |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload["runner_checks"]:
        lines.append("| " + item["case"] + " | " + item["expected"] + " | " + item["observed"] + " | "
                     + ("PASS" if item["passed"] else "**FAIL**") + " |")
    lines += [
        "",
        "## Code mutants",
        "",
        "| ID | Target | Invariant | Mutated behaviour | Expected detector | Expectation | Exit | Outcome | Verdict |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for item in payload["mutants"]:
        detail = item.get("probe_classification")
        lines.append("| " + item["id"] + " | `" + item["target"] + "` | " + item["invariant"] + " | " + item["mutated_behavior"]
                     + " | " + "; ".join(item["expected_detectors"]).replace("|", "\\|") + (" — " + item["note"] if item["note"] else "")
                     + " | " + item["expectation"] + " | " + str(item["exit_code"]) + " | " + item["outcome"]
                     + (" (probe " + detail + ")" if detail else "") + " | **" + item["verdict"] + "** |")
    lines += [
        "",
        "Failed checks per mutant, full probe evidence and the exact replacement text are in the JSON artifact.",
        "",
        "## Data probes through the real consumers",
        "",
        "| ID | Forged or altered input | Consumer | Expected | Exit | Exception | Outputs unchanged | Restored | Classification | Verdict |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for item in payload["data_probes"]:
        lines.append("| " + item["id"] + " | " + item["forged_input"] + " | `" + item["consumer"] + "` | " + item["expected"]
                     + " | " + str(item["exit_code"]) + " | " + (item["exception"] or "—") + " | "
                     + ("yes" if item["outputs_unchanged_by_run"] else "no") + " | "
                     + ("yes" if item["inputs_and_outputs_restored_by_hash"] else "**no**") + " | " + item["classification"]
                     + " | **" + item["verdict"] + "** |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
