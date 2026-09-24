"""Validated loaders and diagnostics for Attachment-A mixture tables."""
from __future__ import annotations

import csv
from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

MIXTURE_PREFIX = "train_"
MIXTURE_FILES = {
    "A4": "train_mixture_1m.csv",
    "A6": "test_mixture_1m.csv",
    "A8": "test_mixture_60m.csv",
    "A10": "test_mixture_1B.csv",
    "A12": "est_mixture_10b.csv",
    "A14": "est_mixture_70b.csv",
}
LOSS_FILES = {
    "A4": "train_pile_loss_1m.csv",
    "A6": "test_pile_loss_1m.csv",
    "A8": "test_pile_loss_60m.csv",
    "A10": "test_pile_loss_1B.csv",
    "A12": "est_pile_loss_10b.csv",
    "A14": "est_pile_loss_70b.csv",
}

@dataclass(frozen=True)
class MixtureTable:
    name: str
    indices: np.ndarray
    domains: List[str]
    values: np.ndarray

@dataclass(frozen=True)
class LossTable:
    name: str
    indices: np.ndarray
    columns: List[str]
    values: np.ndarray


def normalised_proportions(mixture: MixtureTable) -> np.ndarray:
    """Return unit-mass rows while preserving the original stored matrix."""
    values = np.asarray(mixture.values, dtype=float)
    if values.ndim != 2 or values.shape != (len(mixture.indices), len(mixture.domains)):
        raise ValueError("mixture dimensions disagree with indices/domains")
    if not len(values) or not len(mixture.domains) or len(set(mixture.domains)) != len(mixture.domains):
        raise ValueError("mixture must be nonempty with unique domains")
    sums = values.sum(axis=1, keepdims=True)
    if not np.isfinite(values).all() or not np.isfinite(sums).all() or (values < 0).any() or (sums <= 0).any():
        raise ValueError("mixture must have finite nonnegative cells and positive row mass")
    return values / sums


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        names = reader.fieldnames or []
        if len(names) != len(set(names)) or "index" not in names:
            raise ValueError(f"{path.name}: missing index or duplicate column names")
        rows = list(reader)
        if any(None in row or any(v is None or not v.strip() for v in row.values()) for row in rows):
            raise ValueError(f"{path.name}: ragged rows or missing values")
        return rows


def load_mixture(path: Path, name: str, *, row_sum_tolerance: float) -> MixtureTable:
    rows = _read(path)
    if not rows:
        raise ValueError(f"{name}: empty mixture table")
    if not np.isfinite(row_sum_tolerance) or not 0 <= row_sum_tolerance < 1:
        raise ValueError("row-sum tolerance must be finite and in [0,1)")
    columns = [c for c in rows[0] if c != "index"]
    if any(not c.startswith("train_the_pile_") for c in columns):
        raise ValueError(f"{name}: unexpected mixture column naming")
    domains = [c.removeprefix("train_the_pile_") for c in columns]
    indices = np.asarray([int(r["index"]) for r in rows], dtype=int)
    values = np.asarray([[float(r[c]) for c in rows[0] if c != "index"] for r in rows], dtype=float)
    if len(np.unique(indices)) != len(indices):
        raise ValueError(f"{name}: duplicate mixture indices")
    if values.shape[1] != 17 or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError(f"{name}: invalid 17-domain mixture matrix")
    sums = values.sum(axis=1)
    if np.max(np.abs(sums - 1.0)) > row_sum_tolerance:
        raise ValueError(f"{name}: row sums outside tolerance, range={sums.min()}..{sums.max()}")
    return MixtureTable(name, indices, domains, values)


def load_loss(path: Path, name: str) -> LossTable:
    rows = _read(path)
    if not rows:
        raise ValueError(f"{name}: empty loss table")
    columns = [c for c in rows[0] if c != "index"]
    if len(columns) != 13 or any(not c.startswith("metric/the_pile_") or not c.endswith("_val_loss") for c in columns):
        raise ValueError(f"{name}: expected exactly 13 named validation-loss columns")
    indices = np.asarray([int(r["index"]) for r in rows], dtype=int)
    values = np.asarray([[float(r[c]) for c in columns] for r in rows], dtype=float)
    if len(np.unique(indices)) != len(indices) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError(f"{name}: duplicate indices, non-finite or negative losses")
    return LossTable(name, indices, columns, values)


def load_pair(root: Path, name: str, *, row_sum_tolerance: float) -> Tuple[MixtureTable, LossTable]:
    mixture = load_mixture(root / MIXTURE_FILES[name], f"{name} mixture", row_sum_tolerance=row_sum_tolerance)
    loss = load_loss(root / LOSS_FILES[name], f"{name} loss")
    if not np.array_equal(mixture.indices, loss.indices):
        raise ValueError(f"{name}: mixture/loss index join is not one-to-one and ordered")
    return mixture, loss


def check_decimal_grid(path: Path, decimal_places: int, row_sum_tolerance: float) -> None:
    """Verify the declared storage grid and its conditional rounding bound."""
    if not isinstance(decimal_places, int) or decimal_places < 0:
        raise ValueError('decimal places must be a nonnegative integer')
    rows = _read(path)
    if not rows:
        raise ValueError('empty mixture table')
    unit = Decimal(10) ** -decimal_places
    for row in rows:
        for column, value in row.items():
            if column != 'index':
                cell = Decimal(value)
                if not cell.is_finite() or cell % unit != 0:
                    raise ValueError('mixture value is not on the declared decimal grid')
    bound = (len(rows[0]) - 1) * unit / 2
    if Decimal(str(row_sum_tolerance)) > bound:
        raise ValueError('row-sum tolerance exceeds the declared nearest-rounding bound')


def diagnostics(pairs: Dict[str, Tuple[MixtureTable, LossTable]]) -> dict:
    out = {}
    for name, (mix, loss) in pairs.items():
        out[name] = {
            "n": int(len(mix.indices)),
            "loss_targets": len(loss.columns),
            "row_sum_min": float(mix.values.sum(axis=1).min()),
            "row_sum_max": float(mix.values.sum(axis=1).max()),
            "zero_fraction": float(np.mean(mix.values == 0.0)),
            "zero_fraction_by_domain": dict(zip(mix.domains, np.mean(mix.values == 0, axis=0).tolist())),
            "duplicate_designs": int(len(mix.indices) - len(np.unique(mix.values, axis=0))),
            "max_renormalisation": float(np.max(np.abs(mix.values.sum(axis=1) - 1.0))),
            "max_cell_adjustment": float(np.max(np.abs(mix.values / mix.values.sum(axis=1, keepdims=True) - mix.values))),
        }
    if "A6" in pairs and "A8" in pairs:
        a6, a8 = pairs["A6"][0], pairs["A8"][0]
        out["A6_vs_A8"] = {"same_indices": bool(np.array_equal(a6.indices, a8.indices)),
                            "same_design": bool(np.array_equal(a6.values, a8.values))}
    if "A12" in pairs and "A4" in pairs:
        out["A12_vs_A4"] = {"shared_rows": int(len(set(pairs["A12"][0].indices) & set(pairs["A4"][0].indices)))}
    if "A14" in pairs and "A4" in pairs:
        out["A14_vs_A4"] = {"shared_rows": int(len(set(pairs["A14"][0].indices) & set(pairs["A4"][0].indices)))}
    return out
