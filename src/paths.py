"""Repository-relative path resolution.

Every script and module resolves inputs and outputs through this module so that
no absolute, machine-specific path is ever written into committed source. The
repository root is derived from this file's own location, which makes the paths
correct regardless of the current working directory or the checkout location.

Typical use:

    from src.paths import FIGURES, TABLES, DATA_RAW

    fig.savefig(FIGURES / "q1-convergence.pdf")
"""

from __future__ import annotations

from pathlib import Path

#: Repository root, resolved from this file: src/paths.py -> repository root.
REPO_ROOT: Path = Path(__file__).resolve().parent.parent

# Tracked, published locations.
PAPER: Path = REPO_ROOT / "paper"
SECTIONS: Path = PAPER / "sections"
CONFIGS: Path = REPO_ROOT / "configs"
RESULTS: Path = REPO_ROOT / "results"
FIGURES: Path = RESULTS / "figures"
TABLES: Path = RESULTS / "tables"

# Local-only locations. These are git-ignored and are absent from a fresh
# clone; create them on demand rather than assuming they exist.
DATA_LOCAL: Path = REPO_ROOT / "data_local"
DATA_RAW: Path = DATA_LOCAL / "raw"
DATA_PROCESSED: Path = DATA_LOCAL / "processed"
DOCS_LOCAL: Path = REPO_ROOT / "docs_local"
SCRATCH: Path = REPO_ROOT / "scratch"

# --------------------------------------------------------------------------
# Problem F
# --------------------------------------------------------------------------
# The organizer's package is local-only and is never redistributed here. It is
# migrated into the layout below by the archive-intake task, and the raw tree is
# treated as READ-ONLY: derived material is written elsewhere and never
# overwrites an input. Attachment subdirectory names are the organizer's own and
# are deliberately left unchanged.

PROBLEM_F_DOCS: Path = DOCS_LOCAL / "problem-f"
PROBLEM_F_SOURCE: Path = PROBLEM_F_DOCS / "source"
PROBLEM_F_AUDIT: Path = PROBLEM_F_DOCS / "audit"

PROBLEM_F_RAW: Path = DATA_LOCAL / "problem-f" / "raw"
ATTACHMENTS: Path = PROBLEM_F_RAW / "real_attachments"
ATT_A: Path = ATTACHMENTS / "A_data_value"
ATT_B: Path = ATTACHMENTS / "B_scaling_laws"
ATT_C: Path = ATTACHMENTS / "C_efficiency_evolution"

#: Derived Problem-F products. Separate from the raw tree so that no processing
#: step can write back into an input.
PROBLEM_F_DERIVED: Path = DATA_LOCAL / "problem-f" / "derived"

#: Interface objects handed between questions (IF1-IF4). See src/interfaces.py.
PROBLEM_F_INTERFACES: Path = DATA_LOCAL / "problem-f" / "interfaces"


class RawDataMissing(FileNotFoundError):
    """Raised when a required local-only input is absent.

    A fresh clone has no ``data_local/``. Failing with an explicit message that
    names the missing path is better than a partial run over an empty
    directory, which would otherwise produce an empty result that looks like a
    finding.
    """


def require(path: Path) -> Path:
    """Return ``path``, or raise :class:`RawDataMissing` naming it."""
    if not path.exists():
        raise RawDataMissing(
            f"Required local input is missing: {path.relative_to(REPO_ROOT)}\n"
            "Problem-F inputs are local-only and are not distributed with this "
            "repository. Run the archive-intake task first."
        )
    return path


def ensure(path: Path) -> Path:
    """Create ``path`` as a directory if absent and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = [
    "REPO_ROOT",
    "PAPER",
    "SECTIONS",
    "CONFIGS",
    "RESULTS",
    "FIGURES",
    "TABLES",
    "DATA_LOCAL",
    "DATA_RAW",
    "DATA_PROCESSED",
    "DOCS_LOCAL",
    "SCRATCH",
    "PROBLEM_F_DOCS",
    "PROBLEM_F_SOURCE",
    "PROBLEM_F_AUDIT",
    "PROBLEM_F_RAW",
    "ATTACHMENTS",
    "ATT_A",
    "ATT_B",
    "ATT_C",
    "PROBLEM_F_DERIVED",
    "PROBLEM_F_INTERFACES",
    "RawDataMissing",
    "require",
    "ensure",
]
