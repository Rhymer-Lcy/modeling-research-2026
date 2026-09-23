"""Q4 panel configuration.

Values that shape a reported result live here (or in ``configs/``), never as a
literal inside a script, so every number in ``results/`` can be traced back to
the setting that produced it. The seed is read from ``configs/default.yaml``,
the single shared source of truth.

The file is deliberately free of imports from the rest of ``src.panel`` so that
any module can import it without a cycle.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.paths import CONFIGS

# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

#: The shared random seed, read from ``configs/default.yaml``. The panel
#: pipeline itself is deterministic (joins, normalisation, aggregation draw no
#: random numbers), but the seed is loaded and printed by every entry point so
#: the reproducibility contract is honoured uniformly and any future
#: randomising step has an obvious place to plug in.
SEED: int = int(yaml.safe_load((CONFIGS / "default.yaml").read_text(encoding="utf-8"))["seed"])

# ---------------------------------------------------------------------------
# Leaderboard fields and dimensions
# ---------------------------------------------------------------------------

#: The six leaderboard dimensions, in the order the summary table reports them.
DIMENSIONS: tuple[str, ...] = (
    "IFEval",
    "BBH",
    "MATH Lvl 5",
    "GPQA",
    "MUSR",
    "MMLU-PRO",
)

#: Canonical column names for the six dimensions in the built panel. ``score_``
#: prefixes the published summary value (C1/C2); the per-task reconstruction is
#: kept separate and compared against it rather than overwriting it.
SCORE_COLUMNS: dict[str, str] = {
    "IFEval": "score_ifeval",
    "BBH": "score_bbh",
    "MATH Lvl 5": "score_math_lvl5",
    "GPQA": "score_gpqa",
    "MUSR": "score_musr",
    "MMLU-PRO": "score_mmlu_pro",
}

#: C3 names the same six dimensions with underscores; this maps them back to
#: the canonical labels so the timeseries table can be joined on the same axis.
C3_DIMENSION_ALIASES: dict[str, str] = {
    "IFEval": "IFEval",
    "BBH": "BBH",
    "MATH_Lvl5": "MATH Lvl 5",
    "GPQA": "GPQA",
    "MUSR": "MUSR",
    "MMLU_PRO": "MMLU-PRO",
}

# ---------------------------------------------------------------------------
# Model-type stratification
# ---------------------------------------------------------------------------

#: The organizer's own ``Type`` labels (C1) collapsed to a coarse axis used for
#: stratification. ``merge`` keeps the organizer's spelling of "moerges" intact
#: in the raw column and is only collapsed here.
C1_TYPE_TO_COARSE: dict[str, str] = {
    "🟢 pretrained": "base",
    "🟩 continuously pretrained": "base",
    "💬 chat models (RLHF, DPO, IFT, ...)": "chat",
    "🔶 fine-tuned on domain-specific datasets": "finetuned",
    "🤝 base merges and moerges": "merge",
    "🌸 multimodal": "multimodal",
    "❓ other": "other",
}

#: Keywords that refine a model's type from its *name*, used as an independent
#: inference alongside the organizer's ``Type``. Order matters: the first match
#: wins, so the more specific prefixes come first. A keyword is matched against
#: the lower-cased model name after ``/`` separators are turned into spaces.
NAME_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("chat", "chat"),
    ("instruct", "chat"),
    ("-it", "chat"),
    ("-dpo", "chat"),
    ("-sft", "chat"),
    ("-ift", "chat"),
    ("-rlhf", "chat"),
    ("-ppo", "chat"),
    ("-tulu", "chat"),
    ("-kto", "chat"),
    ("-simpo", "chat"),
    ("-orpo", "chat"),
    ("-cpt", "base"),
    ("continuously-pretrained", "base"),
    ("-base", "base"),
    ("-pretrained", "base"),
    ("-merge", "merge"),
    ("-moerge", "merge"),
    ("-slerp", "merge"),
    ("-ties", "merge"),
    ("-dare", "merge"),
)

# ---------------------------------------------------------------------------
# Model-type strata (A-E)
# ---------------------------------------------------------------------------

#: Coarse model class -> analytical stratum. The strata are the required A-E
#: axis; the coarse labels are an intermediate step only so that the raw
#: organizer ``Type`` can be collapsed to it without re-deriving the mapping.
COARSE_TO_STRATUM: dict[str, str] = {
    "base": "A",
    "chat": "B",
    "finetuned": "C",
    "merge": "D",
    "multimodal": "E",
    "other": "E",
}

#: Human-readable labels for the A-E strata.
STRATUM_LABELS: dict[str, str] = {
    "A": "pretrained / continuously pretrained",
    "B": "chat / instruction-tuned",
    "C": "fine-tuned",
    "D": "model merges",
    "E": "other / multimodal",
}

# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

#: Hub licenses that permit re-use and reproduction without a bespoke
#: proprietary agreement. Custom/restrictive licenses (``llama*``, ``gemma``,
#: ``other``, ``unknown``, blank) are *not* open for the purposes of the
#: open-weights eligibility rule. The blank majority is therefore conservatively
#: excluded and the count is reported, not silently dropped.
OPEN_LICENSES: frozenset[str] = frozenset({
    "apache-2.0",
    "mit",
    "bsd-2-clause",
    "bsd-3-clause",
    "bsd-3-clause-clear",
    "afl-3.0",
    "cc-by-4.0",
    "cc-by-sa-4.0",
    "gpl-3.0",
    "lgpl-3.0",
    "wtfpl",
    "unlicense",
    "zlib",
    "isc",
})

#: Model-name patterns treated as test/spam uploads rather than substantive
#: models. Case-insensitive. The organisers' own leaderboard includes several
#: ``DreadPoor/`` test-org entries and ad-hoc ``-test`` merges; these are
#: flagged in the eligibility column but not deleted from the panel.
TEST_MODEL_PATTERNS: tuple[str, ...] = (
    r"dreadpoor/",
    r"/.*test",
    r"-test$",
    r"-test-",
    r"_test",
    r"^test",
    r"debug",
    r"placeholder",
)

#: C4 ``Model accessibility`` values that indicate *open* weights. Only the
#: unrestricted form counts: "restricted use" and "non-commercial" licences do
#: not permit free re-use, so they are tracked separately rather than folded
#: into the open class.
OPEN_ACCESSIBILITY: frozenset[str] = frozenset({"Open weights (unrestricted)"})
RESTRICTED_ACCESSIBILITY: frozenset[str] = frozenset({
    "Open weights (restricted use)",
    "Open weights (non-commercial)",
})

#: Primary timeline axis for Q4. Chosen over ``Submission Date`` (which is when
#: a model was uploaded to the leaderboard, not when it was released) and over
#: the C8 internal version timestamp (which records the evaluation run, not the
#: model). See ``timeline_definition`` in ``src/panel/eligibility.py``.
TIMELINE_PRIMARY: str = "pub_date"

#: Fallback timeline axis when the primary (Epoch publication date) is absent
#: for a model that only exists on the leaderboard.
TIMELINE_FALLBACK: str = "submission_date"
