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
    "ensure",
]
