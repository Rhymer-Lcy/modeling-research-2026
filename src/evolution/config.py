"""T-011 configuration, fixed before any outcome model was fitted.

Every value here shapes a reported Q4 result, so it lives in one place with the
reason it was chosen, never as a literal inside a script. The shared seed is
read from ``configs/default.yaml``; the Q4-specific choices follow the T-009
precedent of a task-owned configuration module (``src/panel/config.py``),
because ``configs/`` is a shared surface outside T-011's paths.

The choices below were made from provenance, comparability, completeness,
model type and date availability. None was tuned against a trend, a bridge
error or a forecast.
"""

from __future__ import annotations

from typing import Dict, Tuple

import yaml

from src.paths import CONFIGS

#: Shared random seed (month-block bootstrap resampling only).
SEED: int = int(yaml.safe_load((CONFIGS / "default.yaml").read_text(encoding="utf-8"))["seed"])

# ---------------------------------------------------------------------------
# Primary analysis population
# ---------------------------------------------------------------------------

#: Model-type strata retained in the primary population. T-009 strata are used
#: as they stand. D (model merges) is excluded because a merge combines the
#: weights of existing models without training of its own, so its score does
#: not mark a distinct model-development event; it is a predeclared
#: sensitivity. E (other / multimodal, 14 models) is heterogeneous and too small
#: to form a stratum.
PRIMARY_STRATA: Tuple[str, ...] = ("A", "B", "C")
EXCLUDED_STRATA: Dict[str, str] = {
    "D": "model merges: weight combinations of existing models, no training of their own",
    "E": "other / multimodal: heterogeneous, 14 models",
}

#: Analysis groups. The problem statement requires pretrained base models to be
#: kept apart from chat / fine-tuned models; T-009 strata B (chat) and C
#: (fine-tuned) are the two post-trained strata, so they form the second group
#: and are also reported separately as a sensitivity.
GROUPS: Dict[str, Tuple[str, ...]] = {
    "A": ("A",),
    "BC": ("B", "C"),
}
GROUP_LABELS: Dict[str, str] = {
    "A": "pretrained / continuously pretrained (T-009 stratum A)",
    "BC": "chat / fine-tuned (T-009 strata B and C)",
}

#: A model counts as open only on T-009's positive signal (permissive Hub
#: licence, Epoch open-weights "Yes", or unrestricted accessibility).
OPEN_WEIGHTS_REQUIRED: str = "yes"

#: Date consistency. A leaderboard model is public before it is evaluated, so a
#: publication date much later than the row's own leaderboard submission date
#: cannot be that model's release date: the panel observed the model's scores
#: first. C2's Epoch columns are, by the organizer's own manifest note,
#: fuzzy-matched, so such a date indicates a mismatched publication record. A
#: row is date-inconsistent when its primary date exceeds its submission date by
#: more than this tolerance. One month allows an upload a few weeks before a
#: formal announcement and equals the frontier bin width.
DATE_CONSISTENCY_TOLERANCE_DAYS: int = 30

# ---------------------------------------------------------------------------
# Time, frontier and decomposition
# ---------------------------------------------------------------------------

#: Days per year for the decimal-year time variable.
DAYS_PER_YEAR: float = 365.25

#: Frontier quantile. The upper frontier is the conditional 90th percentile of
#: the macro score; the observed maximum is a sensitivity only.
FRONTIER_QUANTILE: float = 0.9

#: Time bins for the descriptive frontier: calendar months, the finest cadence
#: the submission dates support. A bin's upper quantile is reported as a
#: frontier estimate only when the bin holds at least this many models;
#: otherwise the bin is flagged sparse and never used as a frontier point.
BIN_FREQ: str = "M"
MIN_BIN_N: int = 20

#: Frontier-estimator sensitivity: the mean of the top-k scores in a bin.
TOP_K: int = 10

#: Scale bands (billions of parameters) for the matched-scale diagnostic.
SCALE_BANDS_B: Tuple[Tuple[float, float], ...] = ((0.0, 3.0), (3.0, 10.0), (10.0, 35.0), (35.0, float("inf")))

#: A scale band's own time trend is estimated only when the band holds at
#: least this many models; otherwise it is reported as too sparse.
MIN_BAND_N: int = 30

#: Frontier set: models at or above their own month's upper-quantile score, in
#: non-sparse months only. Its exact least-squares decomposition splits the
#: frontier trend into scale-associated and non-scale-associated parts, and is
#: estimated only when the set holds at least this many models. (Adopted after
#: the additive quantile decomposition failed its own consistency check; see
#: ``dynamics`` and the T-011 handover.)
MIN_FRONTIER_SET_N: int = 30

#: The primary classic-IF3 decomposition needs at least this many compute-bearing
#: rows with inferred (N, D) inside the IF3 validity box: fewer cannot support a
#: two-covariate (scale index + time) regression. Below it the IF3 decomposition
#: is reported as not supported and outside-box rows appear only as an
#: extrapolation sensitivity.
MIN_IF3_PRIMARY_N: int = 10

#: Training compute is inverted to tokens with the first-party convention
#: C_train = 6 N D (problem statement, Q3) only for C4 rows whose recorded
#: estimation method includes operation counting, i.e. whose compute was itself
#: computed as 6 N D. Hardware-time estimates are not inverted.
COMPUTE_FLOP_PER_PARAM_TOKEN: float = 6.0
D_INFERENCE_METHOD: str = "Operation counting"

#: Month-block bootstrap: whole calendar months are resampled, so models
#: submitted in the same month (and sharing its leaderboard cadence) are never
#: treated as independent draws.
BOOTSTRAP_REPLICATES: int = 399
INTERVAL: Tuple[float, float] = (0.05, 0.95)

# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

#: Horizons in calendar months from the final observed panel date. The 12-month
#: forecast is primary; the 24-month one is a stress / longer-horizon
#: extrapolation and never co-equal evidence.
HORIZONS_MONTHS: Dict[str, int] = {"primary_12m": 12, "stress_24m": 24}

#: Parameter-scale-growth scenarios, as multipliers on the frontier's historical
#: parameter-count-associated (log N) improvement rate. They are NOT compute-growth
#: scenarios: parameter count is not training compute, which also grows with
#: training tokens (T-011 v3). A slower parameter-scale growth can only remove
#: parameter-scale-driven gains; when that historical component is not positive
#: (frontier models did not grow), the multiplier is not applied and the scenario
#: is reported as non-binding. The multiplier 1.0 row is the historical /
#: direct-score continuation baseline. The problem statement's compute-slowdown
#: request is answered separately by the assumption-based transferred
#: compute-slowdown sensitivity (``COMPUTE_SLOWDOWN_MULTIPLIERS``).
SCENARIOS: Dict[str, float] = {"param_scale_historical": 1.0, "param_scale_half": 0.5, "param_scale_frozen": 0.0}
HISTORICAL_SCENARIO: str = "param_scale_historical"

#: Compute-growth multipliers for the compute-slowdown sensitivity. No
#: representative training compute exists for the chat / fine-tuned frontier, so
#: the compute-associated share estimated on the small, non-representative
#: stratum-A C4 compute subset is transferred to each frontier by assumption and
#: the transferred share is slowed. A scenario sensitivity, never an identified
#: population effect.
COMPUTE_SLOWDOWN_MULTIPLIERS = (0.5, 0.0)

#: Rolling-origin validation. The longest horizon (months) is chosen by rule
#: from counts alone: every origin needs at least MIN_TRAIN_BINS non-sparse
#: frontier bins before it and a non-sparse target bin, and at least MIN_ORIGINS
#: such origins must exist.
MIN_TRAIN_BINS: int = 3
MIN_ORIGINS: int = 4

# ---------------------------------------------------------------------------
# Loss / benchmark bridge (IF4)
# ---------------------------------------------------------------------------

#: Comparability strata, declared from the organizer's own metadata before any
#: fit: the `Loss_Comparability` label, the `Loss_Source` text and the table a
#: row appears in (C5, or only in the expanded C6).
BRIDGE_STRATA: Dict[str, str] = {
    "S1_same_family_same_validation": "organizer label High: same model, same validation set (Pythia, Attachment B log)",
    "S2_cross_family_literature": "organizer label Medium in C5: report-derived loss, different validation sets, approximate",
    "S3_expanded_derivative_variants": "rows present only in the expanded C6: chat / instruct / long-context variants and relatives",
}
BRIDGE_PRIMARY_STRATUM: str = "S1_same_family_same_validation"

#: Candidate bridge forms, declared before any error was compared, in order of
#: simplicity. Each maps cross-entropy loss to the macro score and must be
#: non-increasing in loss (lower loss cannot mean a worse score).
BRIDGE_FORMS: Tuple[str, ...] = ("constant", "linear", "logit_linear")
BRIDGE_N_PARAMS: Dict[str, int] = {"constant": 1, "linear": 2, "logit_linear": 2}

#: Selection rule: a form with a slope is eligible only if its slope is off the
#: monotonicity boundary in the full fit and in every leave-one-anchor-out fold;
#: among eligible forms, take the one with the fewest parameters whose
#: out-of-fold RMSE is within one standard error of the best.
BRIDGE_ONE_SE: bool = True

#: Anchor identity ladder: exact model path, then the T-009 normalised key if it
#: is unique on both sides, then this explicit alias map. No fuzzy matching.
BRIDGE_ALIASES: Dict[str, str] = {}

IF4_FILENAME: str = "q4-if4-loss-benchmark-bridge.json"
