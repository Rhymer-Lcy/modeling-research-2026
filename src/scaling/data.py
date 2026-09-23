"""Loaders for the attachment-B scaling data, with provenance attached.

Every loader returns a frame plus an explicit trust class, because the B family
mixes directly observed training logs with semi-synthetic, interpolated and
model-estimated tables that are structurally identical. Nothing here decides
what a table may be used for; it records what the table *is* so the caller
cannot lose that by the time it fits something.

Two non-obvious facts about this data are enforced rather than commented:

* The principal training log is a small number of long trajectories, not a
  large sample of independent runs. Its ``run_id`` column is a row counter, so
  the cluster key has to be reconstructed from the parameter count.
* The cross-family baseline contains rows from the same family as the principal
  fit data, at nearly the same endpoints. Using it whole as a blind test leaks,
  so the family filter is part of the loader rather than left to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from src.paths import ATT_B, require


@dataclass(frozen=True)
class Table:
    """A loaded table together with the trust class of its loss column."""

    name: str
    frame: pd.DataFrame
    trust: str
    note: str = ""

    def __len__(self) -> int:
        return len(self.frame)


def _read(filename: str) -> pd.DataFrame:
    return pd.read_csv(require(ATT_B / filename))


def load_pythia_log() -> Table:
    """B1: the principal fit data. Real Pythia training checkpoints.

    A ``model_id`` column is added from the parameter count. The file's own
    ``run_id`` is a per-row counter with one row per value, so it identifies
    nothing and must never be used as a cluster key: doing so would treat every
    checkpoint as an independent model.
    """
    frame = _read("pythia_training_log_existing.csv")
    frame = frame.copy()
    frame["model_id"] = frame["N_params_B"].round(6).astype(str)
    n_models = frame["model_id"].nunique()
    if n_models >= len(frame):
        raise ValueError(
            "the cluster key resolved to one model per row, which would make a "
            "clustered bootstrap identical to a row bootstrap"
        )
    return Table(
        name="B1 pythia_training_log_existing",
        frame=frame,
        trust="observed",
        note=f"{len(frame)} checkpoints from {n_models} distinct models",
    )


def load_cerebras_log() -> Table:
    """B2: declared semi-synthetic, calibrated on a real law plus noise."""
    return Table(
        name="B2 cerebras_training_log",
        frame=_read("cerebras_training_log.csv"),
        trust="semi_synthetic",
        note="calibrated trajectories, not direct observation",
    )


def load_cross_family(exclude_families: Optional[List[str]] = None) -> Table:
    """B4: convergence points across model families.

    ``exclude_families`` defaults to excluding Pythia. Those rows sit at nearly
    the same parameter counts and final losses as the principal fit data, so a
    model fitted on B1 and 'validated' on the whole of B4 is partly validated
    against its own training data. The exclusion is the default so that the
    leaking version has to be asked for explicitly.
    """
    if exclude_families is None:
        exclude_families = ["Pythia"]
    frame = _read("scaling_baseline.csv")
    before = len(frame)
    mask = ~frame["family"].isin(exclude_families)
    frame = frame.loc[mask].reset_index(drop=True)
    return Table(
        name="B4 scaling_baseline",
        frame=frame,
        trust="observed",
        note=(
            f"{len(frame)} of {before} rows; excluded families: "
            f"{exclude_families or 'none'}"
        ),
    )


def load_published() -> Table:
    """B5: convergence points collected from the published literature.

    The most independent validation available: different families, different
    laboratories, and a parameter range extending far beyond the fit data.
    """
    return Table(
        name="B5 published_scaling_data",
        frame=_read("published_scaling_data.csv"),
        trust="observed",
        note="literature values, independent of the fit data",
    )


def load_nq(which: str = "base") -> Table:
    """B6/B7/B8: the only tables carrying a quality score.

    All are semi-synthetic. B8 additionally labels its own rows as
    ``calibrated`` or ``extrapolated`` and must be used stratified, so the
    column is preserved rather than collapsed.
    """
    filenames = {
        "base": ("supplementary_NQ_experiment.csv", "B6"),
        "expanded": ("supplementary_NQ_experiment_expanded.csv", "B7"),
        "large": ("supplementary_NQ_experiment_large.csv", "B8"),
    }
    if which not in filenames:
        raise KeyError(f"unknown NQ table {which!r}; expected one of {sorted(filenames)}")
    filename, code = filenames[which]
    frame = _read(filename)
    trust = "mixed" if "data_type" in frame.columns else "semi_synthetic"
    note = "semi-synthetic; a fit here largely recovers the generator"
    if "data_type" in frame.columns:
        counts = frame["data_type"].value_counts().to_dict()
        note += f"; row provenance {counts} - use stratified"
    return Table(name=f"{code} {filename}", frame=frame, trust=trust, note=note)


def load_large_model_estimates() -> Table:
    """B10: losses produced by an already-fitted law, not measured.

    Comparing a new fit against these values is estimate against estimate. It
    can bound disagreement; it cannot validate.
    """
    return Table(
        name="B10 supplementary_large_baseline",
        frame=_read("supplementary_large_baseline.csv"),
        trust="estimated",
        note="loss values are model output; not independent validation",
    )


__all__ = [
    "Table",
    "load_pythia_log",
    "load_cerebras_log",
    "load_cross_family",
    "load_published",
    "load_nq",
    "load_large_model_estimates",
]
