"""Parse the published Q2 leave-one-trajectory-out vectors as labelled evidence.

The accepted Q2 robustness table releases eight complete leave-one-trajectory-out
fits of the five classic-law parameters, printed to six significant digits, and
the full-fit point estimate at the same precision.  No full-precision LOO object
was released or accepted, so Q3 propagates the published vectors and labels the
result "leave-one-trajectory-out robustness at published parameter precision".

These are deterministic alternative fits.  They are not bootstrap replicates,
posterior draws, confidence intervals or a sampling distribution, and nothing
here synthesizes joint draws from marginal intervals.  The exact printed
strings are retained so that each value's half-unit rounding interval is known.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .receipts import LOO_PATH, git_blob_sha1, repo_relative, require_authorized_q3_input

LOO_SOURCE_PATH = LOO_PATH
PRECISION_LABEL = "leave-one-trajectory-out robustness at published parameter precision"
LOO_HEADER = "| Trajectory dropped (N, billions) | E | A | alpha | B | beta |"
FULL_FIT_HEADER = (
    "| Parameter | Full fit | Bootstrap 95% CI | Bootstrap SD | Leave-one-out min "
    "| Leave-one-out max | Max relative shift |"
)
EXPECTED_DROPPED_TRAJECTORIES = (
    "0.070542",
    "0.162405",
    "0.409009",
    "1.040867",
    "1.416184",
    "2.782831",
    "6.86104",
    "11.965825",
)
PARAMETERS = ("E", "A", "alpha", "B", "beta")
PUBLISHED_SIGNIFICANT_DIGITS = 6
#: The formatter used by scripts/q2_uncertainty.py for every printed parameter.
PUBLISHED_FORMAT = ".6g"


class LOORobustnessError(ValueError):
    """The published Q2 LOO evidence is missing or structurally invalid."""


@dataclass(frozen=True)
class PublishedParameterVector:
    """One complete published parameter vector with its printed strings."""

    label: str
    parameters: Mapping[str, float]
    published_strings: Mapping[str, str]

    def half_units(self) -> Mapping[str, float]:
        """Half a unit in the sixth significant digit of each parameter.

        The Q2 generator prints with ``format(x, ".6g")``, which strips trailing
        zeros, so ``406.26`` stands for 406.260 and its half unit is 0.0005.
        """
        return {
            name: 0.5 * 10.0 ** (math.floor(math.log10(value)) - (PUBLISHED_SIGNIFICANT_DIGITS - 1))
            for name, value in self.parameters.items()
        }


@dataclass(frozen=True)
class LOORobustnessEvidence:
    """Complete published LOO vectors, the published full fit, and provenance."""

    path: Path
    relative_path: str
    sha256: str
    git_blob_sha1: str
    vectors: tuple[PublishedParameterVector, ...]
    published_full_fit: PublishedParameterVector
    precision_label: str
    limitation: str


def _cells(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise LOORobustnessError("LOO table row is not pipe-delimited Markdown")
    return tuple(cell.strip() for cell in stripped.strip("|").split("|"))


def _is_separator(cells: tuple[str, ...]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell) is not None for cell in cells)


def _table_rows(lines: list[str], header: str) -> list[tuple[str, ...]]:
    try:
        start = lines.index(header)
    except ValueError as exc:
        raise LOORobustnessError("published Q2 table header is missing: " + header[:40]) from exc
    rows: list[tuple[str, ...]] = []
    for line in lines[start + 1:]:
        if not line.startswith("|"):
            break
        cells = _cells(line)
        if not _is_separator(cells):
            rows.append(cells)
    return rows


def _number(text: str, label: str) -> float:
    if re.fullmatch(r"\d+(?:\.\d+)?", text) is None:
        raise LOORobustnessError("published Q2 value is not a plain positive decimal: " + label)
    value = float(text)
    if value <= 0.0:
        raise LOORobustnessError("published Q2 parameters must be strictly positive: " + label)
    if format(value, PUBLISHED_FORMAT) != text:
        raise LOORobustnessError(
            "published Q2 value is not canonical " + PUBLISHED_FORMAT + " output: " + label
        )
    return value


def _parse_vectors(markdown: str) -> tuple[tuple[PublishedParameterVector, ...], PublishedParameterVector]:
    lines = markdown.splitlines()
    vectors: list[PublishedParameterVector] = []
    for cells in _table_rows(lines, LOO_HEADER):
        if len(cells) != 6:
            raise LOORobustnessError("published Q2 LOO row does not have six cells")
        dropped = cells[0]
        if dropped not in EXPECTED_DROPPED_TRAJECTORIES:
            raise LOORobustnessError("unexpected dropped trajectory in Q2 LOO table: " + dropped)
        strings = dict(zip(PARAMETERS, cells[1:], strict=True))
        values = {name: _number(text, dropped + " " + name) for name, text in strings.items()}
        vectors.append(PublishedParameterVector(dropped, values, strings))
    if len(vectors) != len(EXPECTED_DROPPED_TRAJECTORIES):
        raise LOORobustnessError("Q2 LOO table must contain exactly eight complete vectors")
    if tuple(vector.label for vector in vectors) != EXPECTED_DROPPED_TRAJECTORIES:
        raise LOORobustnessError("Q2 LOO vectors must retain the published trajectory order")

    full_strings: dict[str, str] = {}
    for cells in _table_rows(lines, FULL_FIT_HEADER):
        if len(cells) != 7 or cells[0] not in PARAMETERS:
            raise LOORobustnessError("published Q2 full-fit row is malformed")
        full_strings[cells[0]] = cells[1]
    if tuple(full_strings) != PARAMETERS:
        raise LOORobustnessError("published Q2 full-fit column must list all five parameters in order")
    full_fit = PublishedParameterVector(
        "published_full_fit",
        {name: _number(text, "full fit " + name) for name, text in full_strings.items()},
        full_strings,
    )
    return tuple(vectors), full_fit


def load_loo_robustness(path: Path | None = None) -> LOORobustnessEvidence:
    """Load the published LOO vectors through the explicit Q3 input boundary."""
    source = require_authorized_q3_input(path or LOO_SOURCE_PATH)
    raw = source.read_bytes()
    try:
        markdown = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LOORobustnessError("cannot read published Q2 LOO evidence as UTF-8") from exc
    vectors, full_fit = _parse_vectors(markdown)
    return LOORobustnessEvidence(
        path=source,
        relative_path=repo_relative(source),
        sha256=hashlib.sha256(raw).hexdigest(),
        git_blob_sha1=git_blob_sha1(raw),
        vectors=vectors,
        published_full_fit=full_fit,
        precision_label=PRECISION_LABEL,
        limitation=(
            "Eight complete alternative fits, each omitting one training trajectory, printed to six "
            "significant digits. Their spread measures leave-one-trajectory-out sensitivity only; it is "
            "not a confidence interval, posterior interval, bootstrap interval or sampling distribution. "
            "The fits share B1, whose loss column is consistent with a deterministic evaluation of a "
            "published law, so the spread describes estimator/generator recovery on B1, not how "
            "precisely real model scaling is known."
        ),
    )


__all__ = [
    "EXPECTED_DROPPED_TRAJECTORIES",
    "LOORobustnessError",
    "LOORobustnessEvidence",
    "PARAMETERS",
    "PRECISION_LABEL",
    "PUBLISHED_FORMAT",
    "PUBLISHED_SIGNIFICANT_DIGITS",
    "PublishedParameterVector",
    "load_loo_robustness",
]
