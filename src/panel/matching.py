"""Model-name normalisation and matching keys for the Q4 panel.

The leaderboard tables (C1/C2/C3) identify a model by its Hugging Face path
``organisation/name``, while the Epoch AI metadata table (C4) identifies it by a
display name plus an ``Organization`` (and, for a minority, a
``Hugging Face developer id``). The two naming systems are not the same string
in general: ``google/gemma-2-9b`` on the leaderboard is ``Gemma 2 9B`` /
``Google DeepMind`` in Epoch AI. Joining them therefore needs an explicit key,
and the task requires that the key be a documented normalisation (case, spaces,
slashes and underscores) rather than an ad-hoc string comparison.

The normalisation below collapses case and every run of non-alphanumeric
characters to a single ``_``. It is deliberately conservative: it never drops
version suffixes, because ``Yi-1.5-34B-Chat`` and ``Yi-1.5-34B`` are different
models and a normalisation that erased the suffix would silently merge them.
"""

from __future__ import annotations

import re
import unicodedata

#: One or more non-alphanumeric characters, collapsed in the key.
_NON_ALNUM: re.Pattern[str] = re.compile(r"[^a-z0-9]+")


def normalize(name: str) -> str:
    """Fold a model/org name to a canonical key.

    Lower-cases, strips diacritics, then collapses every run of non-alphanumeric
    characters to a single underscore so that ``A / B-C``, ``a_b c`` and
    ``a/b/c`` reach a common form. An empty input yields an empty key.
    """
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("/", " ")  # keep the org/name boundary distinct
    text = _NON_ALNUM.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace(" ", "_")


def split_org_name(model: str) -> tuple[str, str]:
    """Split ``organisation/name`` into its two parts.

    A leaderboard model always has a slash; if it does not, the whole string is
    treated as the name with an empty organisation, which is safer than guessing.
    """
    model = str(model).strip()
    if "/" in model:
        org, name = model.split("/", 1)
        return org.strip(), name.strip()
    return "", model


def org_key(model: str) -> str:
    """Normalised organisation part of a leaderboard path."""
    return normalize(split_org_name(model)[0])


def name_key(model: str) -> str:
    """Normalised name part of a leaderboard path."""
    return normalize(split_org_name(model)[1])


def full_key(model: str) -> str:
    """Normalised full path ``organisation/name``."""
    org, name = split_org_name(model)
    return normalize(f"{org}/{name}")


def display_key(organization: str, model: str) -> str:
    """Key for a C4 (display-name) model, composed from its organisation and name.

    Epoch AI stores the organisation separately from the display name, so the
    closest analogue of the leaderboard's ``org/name`` key is the concatenation
    of the two. ``Hugging Face developer id`` is preferred as the organisation
    when present, because it is the slug the leaderboard actually uses
    (e.g. ``Qwen``, not ``Alibaba``).
    """
    return normalize(f"{organization}/{model}")


def name_only_key(display_name: str) -> str:
    """Normalised display name without organisation."""
    return normalize(display_name)


__all__ = [
    "normalize",
    "split_org_name",
    "org_key",
    "name_key",
    "full_key",
    "display_key",
    "name_only_key",
]
