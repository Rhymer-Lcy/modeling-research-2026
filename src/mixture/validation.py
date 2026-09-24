"""Training-only selection and frozen validation for the Q1 response surface."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Sequence

import numpy as np

from .data import LossTable, MixtureTable, normalised_proportions
from .model import FitResult, fit_all, metrics, predict, response_matrix, _folds, _ridge_fit


VALIDATION_ROLES = {
    'A6_A7': 'held_out_same_scale_1M',
    'A8_A9': 'repeated_design_cross_scale_60M',
    'A10_A11': 'out_of_design_1B',
}


def _digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def _model_digest(fits) -> str:
    return _digest([asdict(fit) for fit in fits])


def _paired(mixture: MixtureTable, loss: LossTable) -> None:
    normalised_proportions(mixture)
    if not np.array_equal(mixture.indices, loss.indices):
        raise ValueError('mixture/loss indices must be paired')
    if len(np.unique(mixture.indices)) != len(mixture.indices):
        raise ValueError('duplicate paired indices')
    if loss.values.shape != (len(mixture.indices), len(loss.columns)) or not len(loss.columns):
        raise ValueError('loss schema/shape mismatch')
    if len(set(loss.columns)) != len(loss.columns) or not np.isfinite(loss.values).all() or (loss.values < 0).any():
        raise ValueError('loss targets must be unique, finite and nonnegative')


@dataclass(frozen=True)
class FrozenResponse:
    domains: tuple[str, ...]
    targets: tuple[str, ...]
    reference: str
    kind: str
    fits: tuple[FitResult, ...]
    model_sha256: str
    training_sha256: str
    training_designs: tuple[tuple[float, ...], ...]
    cv: dict

    def check_unchanged(self) -> None:
        if _model_digest(self.fits) != self.model_sha256:
            raise ValueError('frozen model coefficients changed after selection')


def select_training_model(mixture: MixtureTable, loss: LossTable, *,
                          source_pair: tuple[str, str], seed: int,
                          alphas: Sequence[float], folds: int,
                          candidates: Sequence[str], selection: dict | None = None) -> FrozenResponse:
    """No validation/reference data parameter exists on the tuning API.

    Each candidate tunes per-target ridge strength with identical deterministic
    folds. Candidate choice minimizes mean target RMSE / mean absolute training
    loss. Ties follow caller-declared candidate order. This is selection CV,
    not a nested/unbiased generalization estimate.
    """
    if source_pair != ('A4', 'A5'):
        raise ValueError('only A4/A5 may be used for model selection')
    _paired(mixture, loss)
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError('declare a nonempty unique candidate set')
    p = normalised_proportions(mixture)
    if len(np.unique(p, axis=0)) != len(p):
        raise ValueError('repeated training designs require grouped CV, not row-wise CV')
    scale = np.mean(np.abs(loss.values), axis=0)
    if (scale <= 0).any():
        raise ValueError('selection metric needs positive target scales')
    reports, fits_by_kind = {}, {}
    for kind in candidates:
        reference, fits = fit_all(mixture, loss, seed, alphas, folds, kind)
        x, _ = response_matrix(mixture, reference, kind)
        centered = x - x.mean(axis=0)
        rank = int(np.linalg.matrix_rank(centered))
        singular = np.linalg.svd(centered, compute_uv=False)
        reports[kind] = {
            'selection_score': float(np.mean([f.cv_rmse for f in fits] / scale)),
            'per_target': {f.target: {'alpha': f.alpha, 'cv_rmse': f.cv_rmse} for f in fits},
            'features': x.shape[1], 'centered_rank': rank,
            'smallest_singular_value': float(singular[-1]),
            'condition_number': float(singular[0] / singular[-1]) if rank == x.shape[1] else None,
        }
        if selection is not None:
            oof = np.empty_like(loss.values)
            fold_scores = []
            for training, valid in _folds(len(p), seed, folds):
                for j, fit in enumerate(fits):
                    intercept, coef = _ridge_fit(x[training], loss.values[training,j], fit.alpha)
                    oof[valid,j] = intercept + x[valid] @ coef
                fold_scores.append(float(np.mean(np.sqrt(np.mean((oof[valid]-loss.values[valid])**2,axis=0))/scale)))
            reports[kind]['fold_normalized_rmse'] = fold_scores
        fits_by_kind[kind] = fits
    chosen = min(candidates, key=lambda kind: reports[kind]['selection_score'])
    decision = {'rule':'minimum selection CV score (legacy synthetic infrastructure)'}
    if selection is not None:
        if list(candidates) != ['linear','pairwise_interactions']:
            raise ValueError('real selection requires the declared linear and pairwise family')
        minimum = selection['minimum_relative_gain']
        wins_required = selection['minimum_fold_wins']
        if not 0 <= minimum < 1 or not 1 <= wins_required <= folds:
            raise ValueError('invalid predeclared complexity guard')
        baseline = reports['linear']['selection_score']
        gain = 1-reports['pairwise_interactions']['selection_score']/baseline if baseline else 0.
        wins = int(np.sum(np.asarray(reports['pairwise_interactions']['fold_normalized_rmse']) <
                             np.asarray(reports['linear']['fold_normalized_rmse'])))
        chosen = 'pairwise_interactions' if gain >= minimum and wins >= wins_required else 'linear'
        decision = {'rule':'nonlinear requires relative CV improvement and fold consistency',
                    'minimum_relative_gain':minimum,'minimum_fold_wins':wins_required,
                    'observed_relative_gain':float(gain),'observed_fold_wins':wins,
                    'heldout_used':False}
    fits = tuple(fits_by_kind[chosen])
    cv = {
        'sources': ['A4', 'A5'], 'seed': int(seed), 'folds': int(folds),
        'alphas': list(map(float, alphas)), 'candidate_order': list(candidates),
        'metric': 'mean per-target CV RMSE divided by mean absolute A5 target',
        'warning': 'selection CV; not an unbiased nested-CV performance estimate',
        'validation_indices': [mixture.indices[valid].tolist() for _, valid in _folds(len(p), seed, folds)],
        'candidates': reports, 'chosen': chosen, 'decision':decision,
    }
    return FrozenResponse(tuple(mixture.domains), tuple(loss.columns), fits[0].reference,
                          chosen, fits, _model_digest(fits),
                          _digest({'indices': mixture.indices.tolist(), 'p': p.tolist(), 'y': loss.values.tolist()}),
                          tuple(map(tuple, p)), cv)


def prediction_matrix(frozen: FrozenResponse, mixture: MixtureTable) -> np.ndarray:
    frozen.check_unchanged()
    return np.column_stack([predict(fit, mixture) for fit in frozen.fits])


def target_metrics(loss: LossTable, predictions: np.ndarray, *, centered: bool = False) -> dict:
    if predictions.shape != loss.values.shape:
        raise ValueError('prediction/target matrix shape mismatch')
    per_target = {name: metrics(loss.values[:, j], predictions[:, j]) for j, name in enumerate(loss.columns)}
    if centered:
        for values in per_target.values():
            # Relative errors around centered zero have no loss-scale meaning.
            values.pop('mean_relative_error')
            values.pop('mean_absolute_relative_error')
    names = ('mae', 'rmse', 'r2', 'mean_absolute_relative_error', 'spearman')
    if centered:
        names = tuple(name for name in names if name != 'mean_absolute_relative_error')
    macro = {}
    for name in names:
        finite = [v[name] for v in per_target.values() if v[name] is not None]
        macro[name] = {'mean': float(np.mean(finite)) if finite else None, 'defined_targets': len(finite)}
    return {'per_target': per_target, 'macro': macro}


def evaluate(frozen: FrozenResponse, mixture: MixtureTable, loss: LossTable, *, partition: str) -> dict:
    if partition not in VALIDATION_ROLES:
        raise ValueError('only A6/A7, A8/A9 and A10/A11 are validation partitions')
    _paired(mixture, loss)
    if tuple(loss.columns) != frozen.targets or set(mixture.domains) != set(frozen.domains):
        raise ValueError('validation schema differs from training')
    p = normalised_proportions(mixture)
    p = p[:, [mixture.domains.index(d) for d in frozen.domains]]
    if set(map(tuple, p)) & set(frozen.training_designs):
        raise ValueError('validation contains a training composition')
    predicted = prediction_matrix(frozen, mixture)
    absolute = target_metrics(loss, predicted)
    centered = target_metrics(LossTable(loss.name, loss.indices, loss.columns,
                                       loss.values - loss.values.mean(axis=0)),
                              predicted - predicted.mean(axis=0), centered=True)
    return {'role': VALIDATION_ROLES[partition], 'sources': partition.split('_'),
            'model_sha256': frozen.model_sha256, 'n': len(mixture.indices),
            'absolute': absolute,
            'centered_shape': centered,
            'shape_note': 'test-set centering is descriptive shape analysis, not a fitted correction or absolute validation',
            'nonpositive_prediction_count': int(np.sum(predicted <= 0)),
            'mean_level_shift_by_target': dict(zip(loss.columns, map(float, np.mean(loss.values - predicted, axis=0))))}


def paired_scale_analysis(mix_1m: MixtureTable, loss_1m: LossTable,
                          mix_60m: MixtureTable, loss_60m: LossTable) -> dict:
    _paired(mix_1m, loss_1m)
    _paired(mix_60m, loss_60m)
    if (mix_1m.domains != mix_60m.domains or loss_1m.columns != loss_60m.columns
            or not np.array_equal(mix_1m.indices, mix_60m.indices)
            or not np.array_equal(mix_1m.values, mix_60m.values)):
        raise ValueError('paired scale analysis requires the exact A6/A8 repeated design')
    results = {}
    for j, target in enumerate(loss_1m.columns):
        small, large = loss_1m.values[:, j], loss_60m.values[:, j]
        results[target] = {
            'mean_loss_shift_60m_minus_1m': float(np.mean(large - small)),
            'ordering_spearman': metrics(small, large)['spearman'],
            'centered_difference_rmse': float(np.sqrt(np.mean(((large - large.mean()) - (small - small.mean())) ** 2))),
            'standard_deviation_ratio': float(np.std(large) / np.std(small)) if np.std(small) > 0 else None,
        }
    return {'sources': ['A6', 'A7', 'A8', 'A9'], 'paired_design': True,
            'interpretation': 'observed paired scale description; no correction fitted', 'per_target': results}


def compare_estimated_reference(loss: LossTable, predictions: np.ndarray, *, source: str) -> dict:
    if source not in {'A13', 'A15'}:
        raise ValueError('estimated references must be A13 or A15')
    return {'role': 'estimated_reference_NOT_validation', 'source': source,
            'fit_use': False, 'comparison': target_metrics(loss, predictions)}
