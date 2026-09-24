"""Date convention for the Q4 panel.

Q4 is time-dependent, so the date that a model sits on matters. The preferred
axis is an actual publication/release date from a trustworthy source: the Epoch
AI publication date, delivered through C2 (``pub_date``, pre-matched to the
leaderboard) or through C4 (``c4_pub_date``, for models linked to Epoch AI
metadata). Where neither is present, the leaderboard submission date is the
fallback. It is a *proxy* for release, not the release itself, and every row
carries which source its date came from so the distinction can never be erased
by later code.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd

#: Primary publication-date columns, in preference order. Both are the Epoch AI
#: publication date; the first is C2's pre-matched column, the second C4's raw
#: column, so a model linked only through C4 still gets a primary date.
PRIMARY_DATES: Tuple[str, ...] = ("pub_date", "c4_pub_date")
#: Fallback column: the leaderboard submission date.
FALLBACK_DATE = "submission_date"


def assign_dates(frame: pd.DataFrame) -> pd.DataFrame:
    """Add ``analysis_date``, ``date_source`` and ``date_confidence``.

    The hierarchy is primary (Epoch publication date, C2 then C4) then fallback
    (submission date). A row with none is left ``analysis_date = NaT`` with
    source/confidence ``none`` rather than fabricating a date.
    """
    out = frame.copy()

    def pick(row) -> Tuple[pd.Timestamp, str, str]:
        for col in PRIMARY_DATES:
            if col in row and pd.notna(row[col]):
                return pd.to_datetime(row[col], errors="coerce"), col, "primary"
        if FALLBACK_DATE in row and pd.notna(row[FALLBACK_DATE]):
            return pd.to_datetime(row[FALLBACK_DATE], errors="coerce"), FALLBACK_DATE, "fallback"
        return pd.NaT, "none", "none"

    picked = out.apply(pick, axis=1)
    out["analysis_date"] = [p[0] for p in picked]
    out["date_source"] = [p[1] for p in picked]
    out["date_confidence"] = [p[2] for p in picked]
    return out


def date_coverage(frame: pd.DataFrame) -> Dict[str, object]:
    """Fraction of rows on each date source, overall and per stratum."""
    n = len(frame)
    primary = int((frame["date_confidence"] == "primary").sum())
    fallback = int((frame["date_confidence"] == "fallback").sum())
    none = int((frame["date_confidence"] == "none").sum())
    summary: Dict[str, object] = {
        "primary_fraction": round(primary / n, 4) if n else 0.0,
        "fallback_fraction": round(fallback / n, 4) if n else 0.0,
        "none_fraction": round(none / n, 4) if n else 0.0,
        "primary_count": primary,
        "fallback_count": fallback,
        "none_count": none,
    }
    by_stratum: Dict[str, Dict[str, object]] = {}
    if "stratum" in frame:
        for code in sorted(frame["stratum"].unique()):
            sub = frame[frame["stratum"] == code]
            if sub.empty:
                continue
            sn = len(sub)
            by_stratum[code] = {
                "primary": int((sub["date_confidence"] == "primary").sum()),
                "fallback": int((sub["date_confidence"] == "fallback").sum()),
                "none": int((sub["date_confidence"] == "none").sum()),
                "primary_frac": round(float((sub["date_confidence"] == "primary").mean()), 3),
            }
    summary["by_stratum"] = by_stratum
    return summary
