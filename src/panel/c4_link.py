"""Conservative linkage of leaderboard models to Epoch AI metadata (C4).

The leaderboard identifies a model by its Hugging Face path ``org/name``; the
Epoch AI table (C4) identifies it by a display ``Model`` plus an
``Organization`` and, for a minority of rows, a ``Hugging Face developer id``
slug. Those two naming systems are not the same string, so joining them needs an
explicit key, and the task requires that the key be deterministic and auditable
rather than a fuzzy string comparison that inflates coverage.

The join is a strict priority ladder, applied per leaderboard model, first match
wins:

1. ``hf_id`` — the normalised leaderboard path equals ``Hugging Face developer
   id / Model`` normalised (the slug is the organisation the leaderboard itself
   uses, e.g. ``Qwen`` rather than ``Alibaba``);
2. ``org`` — the normalised leaderboard path equals ``Organization / Model``
   normalised;
3. ``name`` — the normalised leaderboard *name* equals the normalised C4
   ``Model``, and that name is unique on *both* sides (once in C4 and once on
   the leaderboard), so the match is unambiguous even though the organisations
   differ (``google/gemma-2-9b`` is ``Gemma 2 9B`` / ``Google DeepMind``);
4. ``alias`` — an explicit, hand-maintained alias map for known differences the
   normalisation cannot express. It is currently empty: the ``name`` tier
   already resolves every org-spelling near-miss whose C4 name is unique, and
   the handful of residual cases are third-party mirror re-uploads or duplicate
   C4 rows, where deciding which row is "the" model is a judgement the data
   alone does not support. Those stay unlinked and are counted, not guessed.

Rows are never dropped. A model that matches no tier is left unlinked and the
coverage is reported, so a low linkage is a finding rather than a silence.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from src.panel.matching import full_key, name_key, normalize

#: The ``Hugging Face developer id`` column as read from C4 (see sources.C4_RENAME).
_HF_ID = "c4_hf_id"
#: The display model name and organisation columns.
_C4_MODEL = "c4_model"
_C4_ORG = "c4_org"

#: Explicit alias map for the ``alias`` tier. Key: a normalised leaderboard
#: name key. Value: the normalised C4 ``Organization`` that disambiguates it.
#: This is the auditable place for a mapping normalisation cannot derive. It is
#: empty on purpose — see the module docstring for why the deterministic tiers
#: already cover every near-miss the data supports and the residual cases are
#: left unlinked rather than guessed.
C4_ALIASES: Dict[str, str] = {}


def _unique(values: pd.Series) -> "set[str]":
    """Normalised, non-blank values that occur exactly once."""
    counts: Dict[str, int] = {}
    for value in values:
        key = normalize(value)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return {key for key, n in counts.items() if n == 1}


def _positions(values: List[str]) -> Dict[str, List[int]]:
    """Map each non-blank normalised key to all C4 positions that carry it."""
    out: Dict[str, List[int]] = {}
    for pos, key in enumerate(values):
        if key:
            out.setdefault(key, []).append(pos)
    return out


def _unique_positions(values: List[str]) -> Dict[str, int]:
    """Map only one-to-one C4 keys to their sole position.

    A repeated C4 identity is not a reason to select the first row. It is an
    ambiguity that must be surfaced by the caller and left unlinked.
    """
    positions = _positions(values)
    return {key: matches[0] for key, matches in positions.items() if len(matches) == 1}


def _candidate_audit(leaderboard: pd.DataFrame, c4: pd.DataFrame) -> Dict[str, int]:
    """Sequentially count linkable, ambiguous and unmatched deterministic keys."""
    lb_full = [full_key(m) for m in leaderboard["model"]]
    lb_name = [name_key(m) for m in leaderboard["model"]]
    hf = c4[_HF_ID].fillna("").astype(str)
    c4_model = c4[_C4_MODEL].fillna("").astype(str)
    c4_org = c4[_C4_ORG].fillna("").astype(str)
    by_hf = _positions([normalize(f"{h}/{m}") for h, m in zip(hf, c4_model)])
    by_org = _positions([normalize(f"{o}/{m}") for o, m in zip(c4_org, c4_model)])
    by_name = _positions([normalize(m) for m in c4_model])
    lb_name_counts: Dict[str, int] = {}
    for key in lb_name:
        if key:
            lb_name_counts[key] = lb_name_counts.get(key, 0) + 1

    counts: Dict[str, int] = {}
    for full, name in zip(lb_full, lb_name):
        if full in by_hf:
            status = "hf_id" if len(by_hf[full]) == 1 else "ambiguous_hf_id"
        elif full in by_org:
            status = "org" if len(by_org[full]) == 1 else "ambiguous_org"
        elif name in by_name:
            if len(by_name[name]) != 1:
                status = "ambiguous_name_c4"
            elif lb_name_counts.get(name, 0) != 1:
                status = "ambiguous_name_leaderboard"
            else:
                status = "name"
        else:
            status = "unmatched"
        counts[status] = counts.get(status, 0) + 1
    return counts


def link_c4(leaderboard: pd.DataFrame, c4: pd.DataFrame) -> pd.DataFrame:
    """Return the leaderboard frame with C4 metadata joined, plus ``link_method``.

    ``leaderboard`` must carry a ``model`` column of ``org/name`` paths. ``c4``
    must carry the canonical C4 columns from :func:`src.panel.sources.load_c4`
    (``c4_model``, ``c4_org``, ``c4_hf_id`` and the other ``c4_*`` fields).

    The returned frame has one row per leaderboard row, in the same order, with
    every ``c4_*`` column present (``NaN`` where a model did not link) and a
    ``link_method`` column naming the tier that linked it, or ``unlinked``.
    """
    base = leaderboard.reset_index(drop=True).copy()
    n = len(base)

    # Normalised keys for both sides, positionally aligned.
    lb_full = [full_key(m) for m in base["model"]]
    lb_name = [name_key(m) for m in base["model"]]

    hf = c4[_HF_ID].fillna("").astype(str)
    c4_model = c4[_C4_MODEL].fillna("").astype(str)
    c4_org = c4[_C4_ORG].fillna("").astype(str)
    c4_full_hf = [normalize(f"{h}/{m}") for h, m in zip(hf, c4_model)]
    c4_full_org = [normalize(f"{o}/{m}") for o, m in zip(c4_org, c4_model)]
    c4_name = [normalize(m) for m in c4_model]
    c4_org_norm = [normalize(o) for o in c4_org]

    # Only unambiguous identity keys can resolve a row. The raw key-position
    # maps are retained separately by ``_candidate_audit`` for coverage reports.
    idx_hf = _unique_positions(c4_full_hf)
    idx_org = _unique_positions(c4_full_org)
    idx_name = _unique_positions(c4_name)

    # Alias tier: name -> C4 position whose organisation equals the aliased org.
    idx_alias: Dict[str, int] = {}
    for alias_name, canonical_org in C4_ALIASES.items():
        for pos in range(len(c4)):
            if c4_name[pos] == alias_name and c4_org_norm[pos] == canonical_org:
                idx_alias[alias_name] = pos
                break

    unique_c4_name = _unique(pd.Series(c4_model))
    unique_lb_name = _unique(pd.Series([name_key(m) for m in base["model"]]))

    methods: List[str] = []
    link_pos: List[Optional[int]] = []
    for i in range(n):
        pos: Optional[int] = None
        method = "unlinked"
        if lb_full[i] in idx_hf:
            method, pos = "hf_id", idx_hf[lb_full[i]]
        elif lb_full[i] in idx_org:
            method, pos = "org", idx_org[lb_full[i]]
        elif lb_name[i] in unique_c4_name and lb_name[i] in unique_lb_name:
            method, pos = "name", idx_name[lb_name[i]]
        elif lb_name[i] in idx_alias:
            method, pos = "alias", idx_alias[lb_name[i]]
        methods.append(method)
        link_pos.append(pos)

    c4_values = c4.reset_index(drop=True)
    for col in c4.columns:
        base[col] = [c4_values.iloc[link_pos[i]][col] if link_pos[i] is not None else pd.NA
                     for i in range(n)]
    base["link_method"] = methods
    return base


def link_summary(linked: pd.DataFrame, c4: Optional[pd.DataFrame] = None) -> Dict[str, int]:
    """Count linkage tiers; include sequential ambiguity audit when C4 is given."""
    counts = {str(k): int(v) for k, v in linked["link_method"].value_counts(dropna=False).to_dict().items()}
    if c4 is not None:
        audit = _candidate_audit(linked[["model"]], c4)
        for key, value in audit.items():
            counts[f"audit_{key}"] = value
    return counts


__all__ = ["C4_ALIASES", "link_c4", "link_summary"]
