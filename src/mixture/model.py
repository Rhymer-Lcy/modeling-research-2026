"""Simplex-safe Q1b response models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Sequence

import numpy as np
from scipy.stats import spearmanr

from .data import LossTable, MixtureTable, normalised_proportions

@dataclass
class FitResult:
    target: str
    reference: str
    coefficients: Dict[str, float]
    intercept: float
    alpha: float
    cv_rmse: float
    kind: str = 'linear'
    interactions: Dict[str, float] = field(default_factory=dict)


def choose_reference(mixture: MixtureTable) -> str:
    proportions = normalised_proportions(mixture)
    prevalence = np.mean(proportions > 0, axis=0)
    variation = np.std(proportions, axis=0)
    score = prevalence * variation
    # Stable tie-break follows the organizer column order.
    return mixture.domains[int(np.argmax(score))]


def contrast_matrix(mixture: MixtureTable, reference: str) -> np.ndarray:
    if reference not in mixture.domains:
        raise ValueError(f"unknown reference domain: {reference}")
    ref = mixture.domains.index(reference)
    return np.delete(normalised_proportions(mixture), ref, axis=1)


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    """Fit penalised least squares with an unpenalised intercept."""
    x_mean = x.mean(axis=0)
    y_mean = float(y.mean())
    centered = x - x_mean
    gram = centered.T @ centered + alpha * np.eye(x.shape[1])
    coef = np.linalg.solve(gram, centered.T @ (y - y_mean))
    return y_mean - float(x_mean @ coef), coef


def response_matrix(mixture: MixtureTable, reference: str, kind: str) -> tuple[np.ndarray, list[str]]:
    """Dropped-reference contrasts, optionally plus all pairwise products.

    Products include the reference domain. With the simplex identity these
    span the second-order mixture surface; coefficients are not absolute
    domain effects. No pseudocount, logarithm or data-dependent scaling.
    """
    x = contrast_matrix(mixture, reference)
    if kind == 'linear':
        return x, []
    if kind != 'pairwise_interactions':
        raise ValueError('unknown mixture model candidate')
    if any('*' in d for d in mixture.domains):
        raise ValueError('domain names cannot contain the interaction separator')
    p = normalised_proportions(mixture)
    pairs = [(i, j) for i in range(len(mixture.domains)) for j in range(i + 1, len(mixture.domains))]
    names = [mixture.domains[i] + '*' + mixture.domains[j] for i, j in pairs]
    products = np.column_stack([p[:, i] * p[:, j] for i, j in pairs])
    return np.column_stack((x, products)), names


def _folds(n: int, seed: int, folds: int) -> Iterable[tuple[np.ndarray, np.ndarray]]:
    if not 2 <= folds <= n:
        raise ValueError("too few training rows for cross-validation")
    order = np.random.default_rng(seed).permutation(n)
    for valid in np.array_split(order, folds):
        train = np.setdiff1d(np.arange(n), valid, assume_unique=True)
        yield train, valid


def fit_ridge_cv(mixture: MixtureTable, loss: LossTable, target_index: int,
                 reference: str, seed: int, alphas: Sequence[float], folds: int,
                 kind: str = 'linear') -> FitResult:
    if not np.array_equal(mixture.indices, loss.indices):
        raise ValueError("fit requires paired mixture/loss indices")
    if len(alphas) == 0 or any(not np.isfinite(a) or a <= 0 for a in alphas):
        raise ValueError("ridge candidates must be finite and positive")
    x, interaction_names = response_matrix(mixture, reference, kind)
    y = loss.values[:, target_index]
    if y.shape != (len(mixture.indices),) or not np.isfinite(y).all():
        raise ValueError('fit requires a finite paired target')
    best = None
    for alpha in alphas:
        errors = []
        for train, valid in _folds(len(y), seed, folds):
            intercept, coef = _ridge_fit(x[train], y[train], alpha)
            errors.extend((intercept + x[valid] @ coef - y[valid]) ** 2)
        score = float(np.sqrt(np.mean(errors)))
        if best is None or score < best[0]:
            best = (score, alpha)
    cv_rmse, alpha = best
    intercept, coef = _ridge_fit(x, y, alpha)
    names = [d for d in mixture.domains if d != reference]
    return FitResult(loss.columns[target_index], reference,
                     {name: float(value) for name, value in zip(names, coef[:len(names)])},
                     intercept, float(alpha), cv_rmse, kind,
                     dict(zip(interaction_names, map(float, coef[len(names):]))))


def predict(fit: FitResult, mixture: MixtureTable) -> np.ndarray:
    if set(mixture.domains) != set(fit.coefficients) | {fit.reference}:
        raise ValueError('prediction domains differ from the fitted model')
    x = contrast_matrix(mixture, fit.reference)
    names = [d for d in mixture.domains if d != fit.reference]
    coef = np.asarray([fit.coefficients[d] for d in names], dtype=float)
    out = fit.intercept + x @ coef
    p = normalised_proportions(mixture)
    lookup = {name: i for i, name in enumerate(mixture.domains)}
    for name, beta in fit.interactions.items():
        left, right = name.split('*')
        out += beta * p[:, lookup[left]] * p[:, lookup[right]]
    if not np.isfinite(out).all():
        raise ValueError('non-finite model prediction')
    return out


def metrics(observed: np.ndarray, predicted: np.ndarray) -> Dict[str, float | None]:
    observed, predicted = np.asarray(observed), np.asarray(predicted)
    if observed.ndim != 1 or observed.shape != predicted.shape or not len(observed):
        raise ValueError("metrics require nonempty paired vectors")
    if not np.isfinite(observed).all() or not np.isfinite(predicted).all():
        raise ValueError("metrics require finite values")
    residual = predicted - observed
    ss_res = float(np.sum(residual ** 2))
    centered = observed - np.mean(observed)
    ss_tot = float(np.sum(centered ** 2))
    rank = (float(spearmanr(observed, predicted).statistic)
            if len(observed) > 1 and np.std(observed) > 0 and np.std(predicted) > 0 else None)
    nonzero = np.all(observed != 0)
    return {
        "n": float(len(observed)),
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else None,
        "mean_relative_error": float(np.mean(residual / np.abs(observed))) if nonzero else None,
        "mean_absolute_relative_error": float(np.mean(np.abs(residual / observed))) if nonzero else None,
        "spearman": rank,
    }


def fit_all(mixture: MixtureTable, loss: LossTable, seed: int,
            alphas: Sequence[float], folds: int, kind: str = 'linear') -> tuple[str, list[FitResult]]:
    reference = choose_reference(mixture)
    fits = [fit_ridge_cv(mixture, loss, j, reference, seed, alphas, folds, kind) for j in range(loss.values.shape[1])]
    return reference, fits


def substitution_effect(fit: FitResult, mixture: MixtureTable, domain: str, delta: float) -> np.ndarray:
    """Finite change when adding delta to domain at the reference's expense."""
    if domain == fit.reference or domain not in mixture.domains or not np.isfinite(delta):
        raise ValueError('invalid reference-domain substitution')
    p = normalised_proportions(mixture)
    changed = p.copy()
    changed[:, mixture.domains.index(domain)] += delta
    changed[:, mixture.domains.index(fit.reference)] -= delta
    if (changed < 0).any():
        raise ValueError('substitution leaves the simplex')
    modified = MixtureTable(mixture.name, mixture.indices, mixture.domains, changed)
    return predict(fit, modified) - predict(fit, mixture)
