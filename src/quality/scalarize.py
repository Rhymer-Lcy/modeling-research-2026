"""The canonical 22-indicator quality representation.

The organizer defines 22 quality indicators: 14 stored as scalars and 8 stored
as multi-dimensional lists that must be compressed to one scalar each before
modelling. That count is the contract. It would be easy to expand the
four-element ``qurater`` field into four features and arrive at 25, which is
the number of underlying signals in the upstream dataset, but doing so silently
redefines the official indicator system. Component-level views belong in
sensitivity analysis, never in the primary pipeline.

Element semantics come from the upstream dataset's own documentation rather
than from the field names. That matters most for the two binary classifiers:
``ad_en`` is ordered ``[has_ad, no_ad]``, so its **second** element is the
desirable one and the field is already higher-is-better once reduced. Reading
"ad" in the name and assuming the first element is the good one would invert
the indicator, and nothing downstream would look wrong.

Where the upstream documentation recommends ``argmax`` to obtain a rating, this
module uses the softmax expected value instead and keeps ``argmax`` as a
declared sensitivity. The reason is stated rather than assumed: ``argmax``
discards the distribution and collapses a six-level ordinal rating to an
integer, which throws away most of the resolution the classifier provides and
makes the indicator far coarser than the loss it will be regressed against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence

import numpy as np

#: The 14 indicators stored as plain scalars.
NATIVE_SCALARS: List[str] = [
    "dsir_books",
    "dsir_wiki",
    "dsir_math",
    "rps_doc_word_count",
    "rps_doc_num_sentences",
    "rps_doc_unigram_entropy",
    "rps_doc_frac_unique_words",
    "rps_doc_frac_no_alph_words",
    "rps_doc_frac_chars_top_2gram",
    "rps_doc_frac_chars_top_3gram",
    "rps_lines_uppercase_letter_fraction",
    "rps_lines_ending_with_terminal_punctution_mark",
    "rps_lines_numerical_chars_fraction",
    "rps_doc_mean_word_length",
]

#: The 8 indicators stored as lists, each compressed to exactly one scalar.
LIST_FIELDS: List[str] = [
    "fineweb_edu",
    "fluency_en",
    "ad_en",
    "qurater",
    "modernbert_cleanliness",
    "modernbert_readability",
    "modernbert_reasoning",
    "modernbert_professionalism",
]

INDICATORS: List[str] = NATIVE_SCALARS + LIST_FIELDS

#: Direction of the *reduced* indicator, before normalisation.
#: "higher_better", "lower_better" or "non_monotone".
DIRECTIONS: Dict[str, str] = {
    # DSIR importance weights: log-likelihood ratios against a target corpus.
    "dsir_books": "higher_better",
    "dsir_wiki": "higher_better",
    "dsir_math": "higher_better",
    # Length-like counts. Longer is not better without bound, but within this
    # corpus the short tail is boilerplate, so a monotone reading is retained
    # and the bell-shaped alternative is a declared sensitivity.
    "rps_doc_word_count": "higher_better",
    "rps_doc_num_sentences": "higher_better",
    # Lexical richness.
    "rps_doc_unigram_entropy": "non_monotone",
    "rps_doc_frac_unique_words": "higher_better",
    # Degeneracy measures: more non-alphabetic content and more repeated
    # n-grams both indicate boilerplate or machine-generated filler.
    "rps_doc_frac_no_alph_words": "lower_better",
    "rps_doc_frac_chars_top_2gram": "lower_better",
    "rps_doc_frac_chars_top_3gram": "lower_better",
    "rps_lines_uppercase_letter_fraction": "lower_better",
    "rps_lines_ending_with_terminal_punctution_mark": "higher_better",
    "rps_lines_numerical_chars_fraction": "non_monotone",
    "rps_doc_mean_word_length": "non_monotone",
    # Model-based ratings, all framed by their authors as desirable qualities.
    "fineweb_edu": "higher_better",
    "fluency_en": "higher_better",
    "ad_en": "higher_better",          # reduced to P(no ad); see module docstring
    "qurater": "higher_better",
    "modernbert_cleanliness": "higher_better",
    "modernbert_readability": "higher_better",
    "modernbert_reasoning": "higher_better",
    "modernbert_professionalism": "higher_better",
}


def softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    shifted = x - np.max(x, axis=-1, keepdims=True)
    e = np.exp(shifted)
    return e / np.sum(e, axis=-1, keepdims=True)


# --------------------------------------------------------------------------
# The eight reductions
# --------------------------------------------------------------------------

def reduce_fineweb_edu(v: Sequence[float]) -> float:
    """Single-element educational-value regression score; already a scalar."""
    return float(v[0])


def reduce_fluency(v: Sequence[float]) -> float:
    """``[not_fluent_logit, fluent_logit]`` -> P(fluent)."""
    return float(softmax(np.asarray(v, float))[1])


def reduce_ad(v: Sequence[float]) -> float:
    """``[has_ad_logit, no_ad_logit]`` -> P(no ad).

    Index 1 is the desirable class, so the reduced value is already
    higher-is-better and no complement is applied. This is the field the task
    statement names as its negative-direction example; the direction is handled
    here, at the reduction, rather than twice.
    """
    return float(softmax(np.asarray(v, float))[1])


def reduce_qurater(v: Sequence[float], ecdf: Sequence[Callable[[float], float]] = ()) -> float:
    """``[writing style, required expertise, facts and trivia, educational value]``.

    Four separately calibrated latent scores, not a distribution: they do not
    sum to one and their observed ranges differ. A raw mean would therefore
    assume a comparability the data does not show, so each criterion is first
    mapped through its own empirical CDF and the four uniforms are averaged
    with equal weight. Unit weights are the right default for several
    positively correlated indicators of one construct: robust, and with no free
    parameter this data could identify.

    Without fitted CDFs, falls back to the raw mean and the caller is expected
    to treat that as the declared sensitivity rather than the canonical value.
    """
    values = np.asarray(v, dtype=float)
    if not ecdf:
        return float(values.mean())
    return float(np.mean([f(x) for f, x in zip(ecdf, values)]))


def reduce_ordinal6(v: Sequence[float]) -> float:
    """Six logits for levels 0-5 -> softmax expected rating, in [0, 5].

    The upstream card recommends ``argmax``; the expected value is used instead
    because it retains the distribution. ``argmax`` is kept as a sensitivity.
    """
    p = softmax(np.asarray(v, float))
    return float(np.dot(p, np.arange(len(p), dtype=float)))


def reduce_ordinal6_argmax(v: Sequence[float]) -> float:
    """Declared sensitivity alternative for the four ordinal fields."""
    return float(np.argmax(np.asarray(v, float)))


REDUCERS: Dict[str, Callable[[Sequence[float]], float]] = {
    "fineweb_edu": reduce_fineweb_edu,
    "fluency_en": reduce_fluency,
    "ad_en": reduce_ad,
    "qurater": reduce_qurater,
    "modernbert_cleanliness": reduce_ordinal6,
    "modernbert_readability": reduce_ordinal6,
    "modernbert_reasoning": reduce_ordinal6,
    "modernbert_professionalism": reduce_ordinal6,
}

EXPECTED_DIM: Dict[str, int] = {
    "fineweb_edu": 1,
    "fluency_en": 2,
    "ad_en": 2,
    "qurater": 4,
    "modernbert_cleanliness": 6,
    "modernbert_readability": 6,
    "modernbert_reasoning": 6,
    "modernbert_professionalism": 6,
}


@dataclass(frozen=True)
class ScalarizationRecord:
    """The documented contract for one list-valued field."""

    field: str
    raw_dim: int
    semantics: str
    transform: str
    scalar_range: str
    raw_desirability: str
    final_direction: str
    sensitivity: str
    evidence: str


RECORDS: List[ScalarizationRecord] = [
    ScalarizationRecord(
        "fineweb_edu", 1,
        "FineWeb-Edu educational-value regression score, trained against 0-5 LLM ratings",
        "identity: take element 0",
        "approximately [-0.4, 4.1] observed; nominal 0-5",
        "higher score = more educational value",
        "higher_better",
        "clip to [0, 5]",
        "SlimPajama-Meta-rater dataset card: single-element educational value score",
    ),
    ScalarizationRecord(
        "fluency_en", 2,
        "WanJuan-CC binary fluency classifier, ordered [not_fluent, fluent]",
        "softmax, then take P(fluent) = element 1",
        "(0, 1)",
        "element 1 is the desirable class",
        "higher_better",
        "raw logit difference (rank-identical under ECDF normalisation)",
        "Meta-rater card: '[not_fluent_logit, fluent_logit]'; WanJuan-CC reports [label_0, label_1]",
    ),
    ScalarizationRecord(
        "ad_en", 2,
        "WanJuan-CC binary advertisement classifier, ordered [has_ad, no_ad]",
        "softmax, then take P(no ad) = element 1",
        "(0, 1)",
        "element 0 is advertising and undesirable; element 1 is the desirable class",
        "higher_better",
        "raw logit difference (rank-identical under ECDF normalisation)",
        "Meta-rater card: '[has_ad_logit, no_ad_logit]', argmax 0=ad present, 1=no ad",
    ),
    ScalarizationRecord(
        "qurater", 4,
        "QuRating criteria [writing style, required expertise, facts and trivia, educational value]",
        "per-criterion ECDF to [0,1], then unweighted mean of the four",
        "[0, 1]",
        "all four framed by their authors as desirable; 'required expertise' is the arguable one",
        "higher_better",
        "raw mean; sign-fixed PC1; educational-value only; drop or invert required expertise",
        "Meta-rater card gives the four-element order; QuRating defines the criteria",
    ),
    ScalarizationRecord(
        "modernbert_cleanliness", 6,
        "PRRC cleanliness, six logits for rating levels 0-5",
        "softmax, then expected rating sum(k * p_k)",
        "[0, 5]",
        "higher rating = cleaner",
        "higher_better",
        "argmax rating (the upstream card's own recommendation)",
        "Meta-rater: one ModernBERT-base classifier per PRRC dimension, 0-5 labels",
    ),
    ScalarizationRecord(
        "modernbert_readability", 6,
        "PRRC readability, six logits for rating levels 0-5",
        "softmax, then expected rating sum(k * p_k)",
        "[0, 5]",
        "higher rating = more readable",
        "higher_better",
        "argmax rating",
        "Meta-rater PRRC framework",
    ),
    ScalarizationRecord(
        "modernbert_reasoning", 6,
        "PRRC reasoning, six logits for rating levels 0-5",
        "softmax, then expected rating sum(k * p_k)",
        "[0, 5]",
        "higher rating = more reasoning content",
        "higher_better",
        "argmax rating",
        "Meta-rater PRRC framework",
    ),
    ScalarizationRecord(
        "modernbert_professionalism", 6,
        "PRRC professionalism, six logits for rating levels 0-5",
        "softmax, then expected rating sum(k * p_k)",
        "[0, 5]",
        "higher rating = more professional",
        "higher_better",
        "argmax rating",
        "Meta-rater PRRC framework",
    ),
]


def scalarize_record(
    record: Dict[str, object],
    qurater_ecdf: Sequence[Callable[[float], float]] = (),
) -> Dict[str, float]:
    """Reduce one JSON record to exactly the 22 canonical scalar indicators."""
    out: Dict[str, float] = {}
    for name in NATIVE_SCALARS:
        out[name] = float(record[name])  # type: ignore[arg-type]
    for name in LIST_FIELDS:
        raw = record[name]
        if not isinstance(raw, (list, tuple)):
            raise TypeError(f"{name} should be a list, found {type(raw)!r}")
        if len(raw) != EXPECTED_DIM[name]:
            raise ValueError(
                f"{name} has dimension {len(raw)}, expected {EXPECTED_DIM[name]}; "
                "the reduction depends on element order, so an unexpected width "
                "must stop the run rather than be reduced anyway"
            )
        if name == "qurater":
            out[name] = reduce_qurater(raw, qurater_ecdf)
        else:
            out[name] = REDUCERS[name](raw)
    if len(out) != 22:
        raise AssertionError(
            f"canonical representation must hold exactly 22 indicators, built {len(out)}"
        )
    return out


__all__ = [
    "NATIVE_SCALARS",
    "LIST_FIELDS",
    "INDICATORS",
    "DIRECTIONS",
    "EXPECTED_DIM",
    "RECORDS",
    "ScalarizationRecord",
    "softmax",
    "reduce_fineweb_edu",
    "reduce_fluency",
    "reduce_ad",
    "reduce_qurater",
    "reduce_ordinal6",
    "reduce_ordinal6_argmax",
    "scalarize_record",
]
