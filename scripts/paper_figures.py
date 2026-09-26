"""Manuscript result figures, rendered from accepted tracked result tables.

Every plotted number is read from a committed artifact under ``results/tables/``;
nothing is recomputed from raw data and no value is typed here. Before drawing,
``validate`` checks that what will be drawn is the accepted content:

* Question 3 allocation curves are drawn as straight log-log segments between
  accepted allocations of the same regime. Inside one regime the optimum is a
  fixed power law of the budget, so such a segment is the model curve, not an
  interpolation. The check requires every segment's slope to equal the accepted
  regime elasticity and every accepted representative-budget row to lie on the
  drawn curve.
* The raw quality-cost curves use the three organizer forms with the
  source-verified coefficients; the check requires them to reproduce the
  accepted ``g(1)``, the ``Q -> 0+`` limits and every accepted crossing.
* The Question 4 continuation line uses the accepted frontier level and trend;
  the check requires it to reproduce the accepted 12- and 24-month points to
  the precision at which level and trend are published.

Outputs (vector PDF, byte-reproducible) go to ``results/figures/paper-*.pdf``;
a receipt with the input and output SHA-256 values goes to
``results/tables/paper-figures.md``. Regenerate; do not edit by hand.

    conda run -n modeling-research-2026 --no-capture-output python scripts/paper_figures.py

Fonts: Chinese labels use SimSun and Latin text Times New Roman, the manuscript's
own body fonts; the script stops if either is unavailable.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import matplotlib  # noqa: E402

matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from src.paths import FIGURES, TABLES  # noqa: E402

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

INPUTS = {
    "q1_validation": TABLES / "q1-mixture-validation.md",
    "q3_context": TABLES / "q3-context-sensitivity.json",
    "q3_regimes": TABLES / "q3-regime-thresholds.json",
    "q3_quality": TABLES / "q3-quality-cost-sensitivity.json",
    "q4_frontier": TABLES / "q4-frontier-forecast.md",
}

FIGURE_INPUTS = {
    "paper-q1-transfer.pdf": ("q1_validation",),
    "paper-q3-allocation.pdf": ("q3_context", "q3_regimes"),
    "paper-q3-regimes.pdf": ("q3_context", "q3_regimes"),
    "paper-q3-quality-cost.pdf": ("q3_quality",),
    "paper-q4-frontier.pdf": ("q4_frontier",),
}

RECEIPT = TABLES / "paper-figures.md"

# Display names of the thirteen Question 1 targets (labels only).
TARGET_NAMES = {
    "arxiv": "ArXiv", "freelaw": "FreeLaw", "pubmed_central": "PubMed Central",
    "wikipedia_en": "Wikipedia (en)", "dm_mathematics": "DM Mathematics",
    "github": "GitHub", "stackexchange": "StackExchange",
    "gutenberg_pg_19": "Gutenberg (PG-19)", "pile_cc": "Pile-CC",
    "ubuntu_irc": "Ubuntu IRC", "hackernews": "HackerNews",
    "pubmed_abstracts": "PubMed Abstracts", "uspto_backgrounds": "USPTO Backgrounds",
}
ROLES = (
    ("held_out_same_scale_1M", "1M 同规模留出集"),
    ("repeated_design_cross_scale_60M", "60M 同一设计重复"),
    ("out_of_design_1B", "1B 规模与设计均改变"),
)

# ---------------------------------------------------------------------------
# Style: print-safe. Identity never rests on colour alone: every series also
# differs in marker, line style or fill texture, and lightness varies with order.
# ---------------------------------------------------------------------------

INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e6e5e1"
CATEGORICAL = ("#2a78d6", "#eb6834", "#1baf7a")
ORDINAL = ("#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b")
MARKERS = ("o", "s", "^", "D", "v")
REGIME_STYLE = {
    "SATURATED:interior": ("#cde2fb", None, "预算用尽，内点最优"),
    "SATURATED:D_max": ("#6da7ec", "////", "预算用尽，数据量取上界"),
    "SLACK:N_max+D_max": ("#e6e5e1", "....", "预算有剩余，取上角点"),
}
PDF_METADATA = {"CreationDate": None, "Creator": None}


def configure_matplotlib() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    missing = [f for f in ("Times New Roman", "SimSun") if f not in available]
    if missing:
        raise SystemExit("required font(s) not available: " + ", ".join(missing))
    plt.rcParams.update({
        "font.family": ["Times New Roman", "SimSun", "STIXGeneral"],
        "mathtext.fontset": "stix",
        "font.size": 9,
        "axes.titlesize": 9,
        "axes.labelsize": 9,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.unicode_minus": False,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK,
        "axes.linewidth": 0.6,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "text.color": INK,
        "lines.linewidth": 1.4,
        "lines.markersize": 5,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "svg.hashsalt": "paper-figures",
    })


def lf_sha256(path: Path) -> str:
    """SHA-256 of a text artifact with line endings normalized to LF."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def md_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every pipe table in a Markdown document, as (header, rows)."""
    tables, block = [], []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            block.append([c.strip().strip("`") for c in line.strip().strip("|").split("|")])
            continue
        if len(block) >= 2:
            tables.append((block[0], block[2:]))
        block = []
    return tables


def find_table(tables, *columns: str):
    hits = [t for t in tables if all(c in t[0] for c in columns)]
    if len(hits) != 1:
        raise AssertionError(f"expected one table with columns {columns}, found {len(hits)}")
    return hits[0]


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start: nxt if nxt >= 0 else len(text)]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_q1(path: Path) -> dict:
    header, rows = find_table(md_tables(path.read_text(encoding="utf-8")), "Partition", "Role", "Target", "Spearman")
    col = {h: i for i, h in enumerate(header)}
    out = []
    for r in rows:
        m = re.fullmatch(r"metric/the_pile_(.+)_val_loss", r[col["Target"]])
        if m is None:
            raise AssertionError("unexpected target " + r[col["Target"]])
        out.append({
            "role": r[col["Role"]], "target": m.group(1), "n": int(r[col["n"]]),
            "mare": float(r[col["Mean absolute relative error"]]),
            "spearman": float(r[col["Spearman"]]),
        })
    return {"rows": out}


def load_q4(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    anchor = re.search(r"\*\*Anchor: (\d{4}-\d{2}-\d{2})\*\*", text).group(1)
    bc = section(text, "## Group BC")
    tables = md_tables(bc)
    hist_h, hist_r = find_table(tables, "Month", "Models", "Sparse", "P90")
    hc = {h: i for i, h in enumerate(hist_h)}
    history = [{"month": r[hc["Month"]], "models": int(r[hc["Models"]]),
                "sparse": r[hc["Sparse"]] == "yes", "p90": float(r[hc["P90"]])} for r in hist_r]
    m = re.search(r"Frontier level at the anchor ([0-9.]+) \[([0-9.]+), ([0-9.]+)\]; direct frontier trend "
                  r"([0-9.]+) \[([0-9.]+), ([0-9.]+)\] pts/yr", bc)
    level, trend = float(m.group(1)), float(m.group(4))
    fh, fr = find_table(tables, "Horizon", "Date", "Forecast kind", "Point")
    fc = {h: i for i, h in enumerate(fh)}

    def interval(cell: str) -> tuple[float, float]:
        a, b = re.fullmatch(r"\[(-?[0-9.]+), (-?[0-9.]+)\]", cell).groups()
        return float(a), float(b)

    headline = {}
    for r in fr:
        if r[fc["Forecast kind"]] != "historical / direct-score continuation":
            continue
        key = 12 if r[fc["Horizon"]].startswith("12-month") else 24
        headline[key] = {"date": r[fc["Date"]], "point": float(r[fc["Point"]]),
                         "predictive": interval(r[fc["Predictive 90%"]]),
                         "with_backtest": interval(r[fc["Predictive 90% incl. backtest error"]])}
    dh, dr = find_table(tables, "Date clock", "12-month point")
    dc = {h: i for i, h in enumerate(dh)}
    clocks = {r[dc["Population"]]: float(r[dc["12-month point"]]) for r in dr}
    ch, cr = find_table(tables, "Horizon", "Compute-growth multiplier", "Point")
    cc = {h: i for i, h in enumerate(ch)}
    compute = []
    for r in cr:
        compute.append({"horizon": 12 if r[cc["Horizon"]].startswith("12-month") else 24,
                        "multiplier": float(r[cc["Compute-growth multiplier"]]),
                        "point": float(r[cc["Point"]]),
                        "range": interval(r[cc["Range over the transferred share interval"]])})
    return {"anchor": anchor, "history": history, "level": level, "trend": trend,
            "headline": headline, "clocks": clocks, "compute": compute}


def load_inputs() -> dict:
    for p in INPUTS.values():
        if not p.exists():
            raise SystemExit("missing accepted artifact: " + p.relative_to(REPO).as_posix())
    return {
        "q1": load_q1(INPUTS["q1_validation"]),
        "q3_context": json.loads(INPUTS["q3_context"].read_text(encoding="utf-8")),
        "q3_regimes": json.loads(INPUTS["q3_regimes"].read_text(encoding="utf-8")),
        "q3_quality": json.loads(INPUTS["q3_quality"].read_text(encoding="utf-8")),
        "q4": load_q4(INPUTS["q4_frontier"]),
    }


# ---------------------------------------------------------------------------
# Derivations that are checked, never assumed
# ---------------------------------------------------------------------------

REL_TOL = 1e-6


def allocation_paths(data: dict) -> dict[int, list[dict]]:
    """Accepted allocations per context, ordered by budget, with their regime."""
    rows = data["q3_context"]["rows"]
    paths = {}
    for analysis in data["q3_regimes"]["analyses"]:
        ctx = analysis["context_tokens"]
        pts = [{"c": r["budget_flops"], "n": r["n_parameters_raw"], "d": r["d_tokens_raw"],
                "kind": "representative", "regime": r["regime"]}
               for r in rows if r["context_tokens"] == ctx]
        for t in analysis["thresholds"]:
            if t["disposition"] == "RETAINED_REGIME_TRANSITION":
                at = t["at"]
                pts.append({"c": at["budget_flops"], "n": at["n_parameters_raw"], "d": at["d_tokens_raw"],
                            "kind": "transition", "regime": at["regime"], "name": t["name"]})
        lo, hi = analysis["declared_span_flops"]
        pts.append({"c": hi, "kind": "span_end"})  # filled in from the regime map below
        pts.sort(key=lambda p: p["c"])
        paths[ctx] = pts
    return paths


def regime_at(analysis: dict, c: float) -> dict:
    hits = [m for m in analysis["regime_map"] if m["lower_flops"] * (1 - REL_TOL) <= c <= m["upper_flops"] * (1 + REL_TOL)]
    if not hits:
        raise AssertionError(f"budget {c:.6g} outside the regime map")
    return hits


def validate_q3(data: dict) -> dict:
    contexts = data["q3_context"]["rows"]
    analyses = {a["context_tokens"]: a for a in data["q3_regimes"]["analyses"]}
    observed = sorted({r["context_tokens"] for r in contexts})
    if observed != sorted(analyses) or len(observed) != 5:
        raise AssertionError(f"context grids disagree: {observed} vs {sorted(analyses)}")
    budgets = sorted({r["budget_flops"] for r in contexts})
    if len(budgets) != 3 or len(contexts) != 15:
        raise AssertionError("expected 3 representative budgets x 5 contexts")
    slack = [r for r in contexts if r["regime"] == "SLACK:N_max+D_max"]
    n_max = {r["n_parameters_raw"] for r in slack}
    d_max = {r["d_tokens_raw"] for r in slack}
    if len(n_max) != 1 or len(d_max) != 1 or len(slack) != 5:
        raise AssertionError("upper corner differs between contexts")
    n_max, d_max = n_max.pop(), d_max.pop()
    paths = allocation_paths(data)
    checked_segments = 0
    for ctx, pts in paths.items():
        a = analyses[ctx]
        end = pts[-1]
        assert end["kind"] == "span_end"
        last = [p for p in pts if p["kind"] != "span_end"][-1]
        if last["regime"] != "SLACK:N_max+D_max" or last["c"] != end["c"]:
            raise AssertionError(f"context {ctx}: span end is not the accepted slack row")
        pts.pop()
        kinds = [p["kind"] for p in pts]
        if kinds.count("representative") != 3 or kinds.count("transition") != 2:
            raise AssertionError(f"context {ctx}: expected 3 representative rows and 2 transitions")
        for p, q in zip(pts, pts[1:]):
            common = [m for m in regime_at(a, p["c"]) if m in regime_at(a, q["c"])]
            if len(common) != 1:
                raise AssertionError(f"context {ctx}: segment {p['c']:.6g}-{q['c']:.6g} spans regimes")
            m = common[0]
            dl = math.log(q["c"] / p["c"])
            sn = math.log(q["n"] / p["n"]) / dl
            sd = math.log(q["d"] / p["d"]) / dl
            if abs(sn - m["analytic_n_elasticity"]) > 1e-5 or abs(sd - m["analytic_d_elasticity"]) > 1e-5:
                raise AssertionError(f"context {ctx}: segment slope ({sn:.7f}, {sd:.7f}) differs from the "
                                     f"accepted elasticity ({m['analytic_n_elasticity']:.7f}, {m['analytic_d_elasticity']:.7f})")
            checked_segments += 1
        for p in pts:
            if p["n"] > n_max * (1 + REL_TOL) or p["d"] > d_max * (1 + REL_TOL):
                raise AssertionError(f"context {ctx}: allocation outside the validity box")
    return {"paths": paths, "n_max": n_max, "d_max": d_max, "budgets": budgets,
            "segments": checked_segments}


FAMILIES = {
    "exponential": lambda g, lam, q: g * math.exp(lam * q),
    "power": lambda g, lam, q: g * q ** lam,
    "logarithmic": lambda g, lam, q: g * math.log1p(lam * q),
}


def validate_quality(data: dict) -> dict:
    raw = data["q3_quality"]["raw_family_analysis"]
    fams = raw["families"]
    if sorted(fams) != sorted(FAMILIES):
        raise AssertionError("unexpected family set " + str(sorted(fams)))
    for name, f in fams.items():
        g1 = FAMILIES[name](f["gamma_flops_per_token"], f["lambda"], 1.0)
        if abs(g1 / f["value_at_q_1_flops_per_token"] - 1) > 1e-12:
            raise AssertionError(f"{name}: form does not reproduce the accepted g(1)")
        g0 = FAMILIES[name](f["gamma_flops_per_token"], f["lambda"], 1e-300)
        if abs(g0 - f["limit_q_to_0_plus_flops_per_token"]) > 1e-6 * max(1.0, f["limit_q_to_0_plus_flops_per_token"]):
            raise AssertionError(f"{name}: form does not reproduce the accepted Q -> 0+ limit")
    crossings = []
    for pair in raw["pairs"]:
        i, j = pair["pair"]
        if pair["crossing_count"] != 1 or len(pair["crossings"]) != 1:
            raise AssertionError(f"{i}/{j}: expected exactly one crossing")
        x = pair["crossings"][0]
        gi = FAMILIES[i](fams[i]["gamma_flops_per_token"], fams[i]["lambda"], x["q"])
        gj = FAMILIES[j](fams[j]["gamma_flops_per_token"], fams[j]["lambda"], x["q"])
        if abs(gi / gj - 1) > 1e-9 or abs(gi / x["g_value_flops_per_token"] - 1) > 1e-9:
            raise AssertionError(f"{i}/{j}: accepted crossing is not a crossing of the drawn curves")
        crossings.append({"pair": (i, j), "q": x["q"], "g": x["g_value_flops_per_token"]})
    if len(crossings) != 3:
        raise AssertionError("expected three pairwise crossings")
    return {"families": fams, "crossings": sorted(crossings, key=lambda c: c["q"])}


def years_between(a: str, b: str) -> float:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days / 365.25


def validate_q4(data: dict) -> dict:
    q4 = data["q4"]
    if sorted(q4["headline"]) != [12, 24]:
        raise AssertionError("continuation rows missing")
    for h, row in q4["headline"].items():
        t = years_between(q4["anchor"], row["date"])
        line = q4["level"] + q4["trend"] * t
        tol = 0.005 * (1 + t) + 1e-9  # level and trend are published to 0.01
        if abs(line - row["point"]) > tol:
            raise AssertionError(f"{h}-month continuation {row['point']} is not level + trend x t ({line:.3f})")
        lo, hi = row["with_backtest"]
        if not lo <= row["predictive"][0] <= row["point"] <= row["predictive"][1] <= hi:
            raise AssertionError(f"{h}-month intervals are not nested around the point")
    if len(q4["compute"]) != 4 or sorted({c["multiplier"] for c in q4["compute"]}) != [0.0, 0.5]:
        raise AssertionError("expected halved and stopped compute sensitivities at both horizons")
    for c in q4["compute"]:
        if not c["range"][0] <= c["point"] <= c["range"][1]:
            raise AssertionError("compute sensitivity point outside its range")
    if sorted(q4["clocks"]) != ["fallback_date_only", "primary", "publication_date_only"]:
        raise AssertionError("unexpected date clocks")
    if abs(q4["clocks"]["primary"] - q4["headline"][12]["point"]) > 1e-9:
        raise AssertionError("primary clock differs from the headline")
    if len(q4["history"]) < 10:
        raise AssertionError("history too short")
    return {"non_sparse": sum(not r["sparse"] for r in q4["history"])}


def validate_q1(data: dict) -> dict:
    rows = data["q1"]["rows"]
    roles = [r for r, _ in ROLES]
    if sorted({r["role"] for r in rows}) != sorted(roles):
        raise AssertionError("unexpected validation roles")
    targets = sorted({r["target"] for r in rows})
    if targets != sorted(TARGET_NAMES) or len(rows) != 3 * len(TARGET_NAMES):
        raise AssertionError(f"expected 13 targets x 3 roles, found {len(rows)} rows over {len(targets)} targets")
    for role in roles:
        if len({r["n"] for r in rows if r["role"] == role}) != 1:
            raise AssertionError("row count differs between targets within a role")
    return {"targets": len(targets)}


def validate(data: dict) -> dict:
    return {"q1": validate_q1(data), "q3": validate_q3(data),
            "quality": validate_quality(data), "q4": validate_q4(data)}


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def style_axes(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)


def save(fig, name: str) -> Path:
    out = FIGURES / name
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.02, metadata=PDF_METADATA)
    plt.close(fig)
    return out


def figure_q1(data: dict) -> Path:
    rows = data["q1"]["rows"]
    by = {(r["target"], r["role"]): r for r in rows}
    order = sorted(TARGET_NAMES, key=lambda t: by[(t, ROLES[0][0])]["mare"], reverse=True)
    y = range(len(order))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.3, 3.3), sharey=True,
                                   gridspec_kw={"width_ratios": [1.35, 1], "wspace": 0.08})
    for k, (role, label) in enumerate(ROLES):
        ax1.scatter([by[(t, role)]["mare"] * 100 for t in order], y, marker=MARKERS[k], s=22,
                    facecolor=CATEGORICAL[k], edgecolor="white", linewidth=0.6, zorder=3, label=label)
        ax2.scatter([by[(t, role)]["spearman"] for t in order], y, marker=MARKERS[k], s=22,
                    facecolor=CATEGORICAL[k], edgecolor="white", linewidth=0.6, zorder=3)
    ax1.set_xscale("log")
    ax1.set_xlabel("平均绝对相对误差（%，对数刻度）")
    ax2.set_xlabel("Spearman 秩相关系数")
    ax1.set_yticks(list(y), [TARGET_NAMES[t] for t in order])
    ax1.set_title("(a) 损失水平的预测误差", loc="left")
    ax2.set_title("(b) 设计间排序的一致性", loc="left")
    ax2.set_xlim(0.6, 1.0)
    for ax in (ax1, ax2):
        style_axes(ax)
    fig.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.04), handletextpad=0.3, columnspacing=1.2)
    return save(fig, "paper-q1-transfer.pdf")


def ctx_label(ctx: int) -> str:
    return r"$L_{\mathrm{ctx}}=" + f"{ctx}$"


def figure_q3_allocation(data: dict, q3: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.9), gridspec_kw={"wspace": 0.28})
    for k, (ctx, pts) in enumerate(sorted(q3["paths"].items())):
        cs = [p["c"] for p in pts]
        for ax, key in zip(axes, ("n", "d")):
            vals = [p[key] for p in pts]
            ax.plot(cs, vals, color=ORDINAL[k], linewidth=1.3, zorder=2)
            rep = [p for p in pts if p["kind"] == "representative"]
            tra = [p for p in pts if p["kind"] == "transition"]
            ax.scatter([p["c"] for p in rep], [p[key] for p in rep], marker=MARKERS[k], s=24,
                       facecolor=ORDINAL[k], edgecolor="white", linewidth=0.6, zorder=4)
            ax.scatter([p["c"] for p in tra], [p[key] for p in tra], marker=MARKERS[k], s=22,
                       facecolor="white", edgecolor=ORDINAL[k], linewidth=1.0, zorder=4)
    for ax, bound, label in ((axes[0], q3["n_max"], "参数量上界"), (axes[1], q3["d_max"], "数据量上界")):
        ax.axhline(bound, color=INK2, linewidth=0.8, linestyle=(0, (4, 2)), zorder=1)
        ax.text(1.3e19, bound / 1.25, "有效域" + label, color=INK2, fontsize=8, va="top")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(7e18, 1.4e24)
        ax.set_xlabel("算力预算 \U0001D436（FLOPs）")
        style_axes(ax)
    axes[0].set_ylabel("参数量 \U0001D441*（个）")
    axes[1].set_ylabel("数据量 \U0001D437*（Token）")
    axes[0].set_title("(a) 最优参数量", loc="left")
    axes[1].set_title("(b) 最优数据量", loc="left")
    handles = [Line2D([], [], color=ORDINAL[k], marker=MARKERS[k], markersize=4.5, markeredgecolor="white",
                      label=ctx_label(ctx)) for k, ctx in enumerate(sorted(q3["paths"]))]
    handles += [Line2D([], [], color="none", marker="o", markerfacecolor=INK2, markeredgecolor="white",
                       markersize=4.5, label="代表性预算下的解"),
                Line2D([], [], color="none", marker="o", markerfacecolor="white", markeredgecolor=INK2,
                       markersize=4.5, label="区间转换点")]
    fig.legend(handles=handles, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.13),
               handletextpad=0.3, columnspacing=1.0)
    return save(fig, "paper-q3-allocation.pdf")


def figure_q3_regimes(data: dict, q3: dict) -> Path:
    analyses = sorted(data["q3_regimes"]["analyses"], key=lambda a: a["context_tokens"])
    fig, ax = plt.subplots(figsize=(6.3, 2.35))
    for k, a in enumerate(analyses):
        for m in a["regime_map"]:
            face, hatch, _ = REGIME_STYLE[m["regime"]]
            lo, hi = math.log10(m["lower_flops"]), math.log10(m["upper_flops"])
            ax.barh(k, hi - lo, left=lo, height=0.62, color=face, hatch=hatch, edgecolor="white",
                    linewidth=1.5, zorder=2)
        for t in a["thresholds"]:
            if t["disposition"] == "RETAINED_REGIME_TRANSITION":
                x = math.log10(t["budget_flops"])
                ax.plot([x, x], [k - 0.36, k + 0.36], color=INK, linewidth=0.9, zorder=3)
    for c in q3["budgets"]:
        x = math.log10(c)
        ax.axvline(x, color=INK2, linewidth=0.8, linestyle=(0, (1, 2)), zorder=4)
    ax.set_yticks(range(len(analyses)), [str(a["context_tokens"]) for a in analyses])
    ax.set_ylabel("上下文长度（Token）")
    ax.set_xlim(18.9, 24.1)
    ax.set_xticks(range(19, 25), [f"$10^{{{e}}}$" for e in range(19, 25)])
    ax.set_xlabel("算力预算 \U0001D436（FLOPs）")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    handles = [Patch(facecolor=f, hatch=h, edgecolor=INK2, linewidth=0.4, label=l) for f, h, l in REGIME_STYLE.values()]
    handles.append(Line2D([], [], color=INK, linewidth=0.9, label="区间转换点"))
    handles.append(Line2D([], [], color=INK2, linewidth=0.7, linestyle=(0, (1, 2)), label="代表性预算"))
    ax.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.33), handletextpad=0.4,
              columnspacing=1.0)
    return save(fig, "paper-q3-regimes.pdf")


FAMILY_LABEL = {"exponential": "指数型", "power": "幂函数型", "logarithmic": "对数渐近型"}
FAMILY_STYLE = {"exponential": (CATEGORICAL[0], "-"), "power": (CATEGORICAL[1], (0, (5, 2))),
                "logarithmic": (CATEGORICAL[2], (0, (1.2, 1.4)))}


def figure_q3_quality(data: dict, quality: dict) -> Path:
    fams = quality["families"]
    lo_q = 1e-4
    qs = [10 ** (math.log10(lo_q) + i * (0 - math.log10(lo_q)) / 800) for i in range(801)]
    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    for name in ("exponential", "power", "logarithmic"):
        f = fams[name]
        color, ls = FAMILY_STYLE[name]
        ax.plot(qs, [FAMILIES[name](f["gamma_flops_per_token"], f["lambda"], q) for q in qs],
                color=color, linestyle=ls, linewidth=1.5, label=FAMILY_LABEL[name], zorder=2)
    for x in quality["crossings"]:
        ax.scatter([x["q"]], [x["g"]], s=26, facecolor="white", edgecolor=INK, linewidth=0.9, zorder=4)
        offset = (-62, -3) if x["q"] > 0.9 else (5, -11)
        ax.annotate(f"\U0001D444 = {x['q']:.3g}", (x["q"], x["g"]), xytext=offset, textcoords="offset points",
                    fontsize=8, color=INK)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo_q, 1.0)
    ax.set_ylim(1e5, 2e10)
    ax.set_xlabel("质量水平 \U0001D444（无量纲，对数刻度）")
    ax.set_ylabel("原始成本 \U0001D454(\U0001D444)（FLOPs/Token）")
    style_axes(ax)
    ax.legend(loc="upper left", handlelength=2.6)
    return save(fig, "paper-q3-quality-cost.pdf")


def month_mid(month: str) -> float:
    y, m = (int(v) for v in month.split("-"))
    return y + (m - 0.5) / 12.0


def decimal_year(iso: str) -> float:
    d = date.fromisoformat(iso)
    start, end = date(d.year, 1, 1), date(d.year + 1, 1, 1)
    return d.year + (d - start).days / (end - start).days


def figure_q4(data: dict) -> Path:
    q4 = data["q4"]
    first_dense = min(month_mid(r["month"]) for r in q4["history"] if not r["sparse"])
    shown = [r for r in q4["history"] if month_mid(r["month"]) >= first_dense - 1.0]
    fig = plt.figure(figsize=(6.3, 4.6))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.25, 1], hspace=0.55, wspace=0.08)
    ax = fig.add_subplot(grid[0, :])
    dense = [r for r in shown if not r["sparse"]]
    sparse = [r for r in shown if r["sparse"]]
    ax.scatter([month_mid(r["month"]) for r in dense], [r["p90"] for r in dense], marker="o", s=22,
               facecolor=CATEGORICAL[0], edgecolor="white", linewidth=0.6, zorder=3, label="月度第 90 百分位（样本充足）")
    ax.scatter([month_mid(r["month"]) for r in sparse], [r["p90"] for r in sparse], marker="o", s=20,
               facecolor="white", edgecolor=CATEGORICAL[0], linewidth=0.9, zorder=3, label="月度第 90 百分位（稀疏月份）")
    t0 = decimal_year(q4["anchor"])

    def line(t: float) -> float:
        return q4["level"] + q4["trend"] * (t - t0)

    ax.plot([first_dense, t0], [line(first_dense), line(t0)], color=INK, linewidth=1.3, zorder=2,
            label="前沿趋势（条件第 90 分位数回归）")
    h24 = q4["headline"][24]
    t24 = decimal_year(h24["date"])
    ax.plot([t0, t24], [line(t0), line(t24)], color=INK, linewidth=1.3, linestyle=(0, (4, 2)), zorder=2,
            label="历史延续基线")
    for h in (12, 24):
        row = q4["headline"][h]
        t = decimal_year(row["date"])
        lo, hi = row["with_backtest"]
        ax.errorbar([t], [row["point"]], yerr=[[row["point"] - lo], [hi - row["point"]]], fmt="D", ms=4.5,
                    color=INK, mfc="white", mec=INK, elinewidth=1.0, capsize=3, zorder=4)
    ax.axvline(t0, color=INK2, linewidth=0.7, linestyle=(0, (1, 2)), zorder=1)
    ax.text(t0 + 0.03, 3, "预测锚点 " + q4["anchor"], color=INK2, fontsize=8)
    ax.set_ylim(0, 92)
    ax.set_yticks([0, 20, 40, 60, 80])
    ax.set_xlim(min(month_mid(r["month"]) for r in shown) - 0.15, t24 + 0.25)
    ax.set_xticks([2023, 2024, 2025, 2026, 2027])
    ax.set_xticklabels(["2023", "2024", "2025", "2026", "2027"])
    ax.set_ylabel("综合得分 \U0001D446（0–100）")
    ax.set_title("(a) 对话与微调模型组：历史前沿与延续基线", loc="left")
    style_axes(ax)
    handles, labels = ax.get_legend_handles_labels()
    handles.append(Line2D([], [], color=INK, linewidth=1.0, marker="D", markerfacecolor="white", markersize=4.5))
    labels.append("延续预测及含回测误差的 90% 预测区间")
    ax.legend(handles, labels, loc="upper left", ncol=2, fontsize=7.5, handletextpad=0.3, columnspacing=1.0)

    compute = {(c["horizon"], c["multiplier"]): c for c in q4["compute"]}
    for col, h in enumerate((12, 24)):
        axh = fig.add_subplot(grid[1, col])
        row = q4["headline"][h]
        items = [("历史延续基线", row["point"], row["with_backtest"], "interval"),
                 ("算力增长减半（转移敏感性）", compute[(h, 0.5)]["point"], compute[(h, 0.5)]["range"], "range"),
                 ("算力增长停止（转移敏感性）", compute[(h, 0.0)]["point"], compute[(h, 0.0)]["range"], "range")]
        if h == 12:
            items += [("时间口径：仅发布日期", q4["clocks"]["publication_date_only"], None, "clock"),
                      ("时间口径：仅提交日期", q4["clocks"]["fallback_date_only"], None, "clock")]
        for i, (label, point, span, kind) in enumerate(items):
            yy = -i
            if span is not None:
                axh.plot(span, [yy, yy], color=INK if kind == "interval" else CATEGORICAL[1],
                         linewidth=1.0 if kind == "interval" else 2.2, solid_capstyle="butt", zorder=2)
            marker = {"interval": "D", "range": "s", "clock": "^"}[kind]
            face = {"interval": "white", "range": CATEGORICAL[1], "clock": CATEGORICAL[2]}[kind]
            axh.scatter([point], [yy], marker=marker, s=26, facecolor=face,
                        edgecolor=INK if kind == "interval" else "white", linewidth=0.8, zorder=3)
        axh.set_yticks([-i for i in range(len(items))], [it[0] for it in items] if col == 0 else [""] * len(items))
        axh.set_ylim(-4.6, 0.6)
        axh.set_xlim(35, 75)
        axh.set_xlabel("综合得分 \U0001D446")
        axh.set_title("(b) 12 个月（" + row["date"] + "）" if h == 12 else "(c) 24 个月压力外推（" + row["date"] + "）",
                      loc="left")
        style_axes(axh)
        if col == 1:
            axh.tick_params(axis="y", length=0)
    fig.legend(handles=[
        Line2D([], [], color=INK, linewidth=1.0, marker="D", markerfacecolor="white", markersize=4.5,
               label="延续基线（含回测误差的 90% 预测区间）"),
        Line2D([], [], color=CATEGORICAL[1], linewidth=2.2, marker="s", markeredgecolor="white",
               markersize=5, label="转移敏感性（转移占比区间所致范围）"),
        Line2D([], [], color="none", marker="^", markerfacecolor=CATEGORICAL[2], markeredgecolor="white",
               markersize=5.5, label="时间口径敏感性")],
        loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=3, fontsize=7.5, handletextpad=0.4, columnspacing=1.2)
    return save(fig, "paper-q4-frontier.pdf")


# ---------------------------------------------------------------------------

def receipt(outputs: dict[str, Path], summary: dict) -> str:
    lines = ["# Manuscript figures: inputs, outputs and checks", "",
             "Generated by `scripts/paper_figures.py`. Do not edit by hand.", "",
             "Every plotted number is read from the accepted artifacts below; none is typed into the",
             "script or recomputed from raw data. Input identities are SHA-256 of the file with line",
             "endings normalized to LF (the committed bytes); outputs are vector PDFs whose bytes are",
             "reproducible.", "",
             "| Figure | Inputs | Output SHA-256 |", "| --- | --- | --- |"]
    for name, out in outputs.items():
        ins = "<br>".join(f"`{INPUTS[k].relative_to(REPO).as_posix()}`" for k in FIGURE_INPUTS[name])
        lines.append(f"| `results/figures/{name}` | {ins} | `{hashlib.sha256(out.read_bytes()).hexdigest()}` |")
    lines += ["", "| Input | SHA-256 (LF) |", "| --- | --- |"]
    for key, p in INPUTS.items():
        lines.append(f"| `{p.relative_to(REPO).as_posix()}` | `{lf_sha256(p)}` |")
    q3 = summary["q3"]
    lines += ["", "## Checks run before drawing", "",
              f"- Question 1: {summary['q1']['targets']} targets x 3 validation roles read; roles and row counts consistent.",
              f"- Question 3 allocation: {q3['segments']} log-log segments over 5 contexts; every slope equals the accepted "
              "regime elasticity within 1e-5, and every accepted representative-budget row and retained transition is a "
              "vertex of the drawn curve; the upper corner is identical across contexts.",
              f"- Question 3 raw quality cost: 3 families reproduce the accepted g(1) and Q -> 0+ limits; "
              f"{len(summary['quality']['crossings'])} accepted crossings are crossings of the drawn curves (relative 1e-9).",
              f"- Question 4: the continuation line reproduces the accepted 12- and 24-month points from the published "
              f"level and trend; intervals nest around the points; {summary['q4']['non_sparse']} non-sparse months.",
              "", "The 30000-token cost-parity identity is not drawn as a regime boundary.", ""]
    return "\n".join(lines)


def main() -> int:
    configure_matplotlib()
    data = load_inputs()
    summary = validate(copy.deepcopy(data))
    q3 = validate_q3(copy.deepcopy(data))
    quality = validate_quality(data)
    FIGURES.mkdir(parents=True, exist_ok=True)
    outputs = {
        "paper-q1-transfer.pdf": figure_q1(data),
        "paper-q3-allocation.pdf": figure_q3_allocation(data, q3),
        "paper-q3-regimes.pdf": figure_q3_regimes(data, q3),
        "paper-q3-quality-cost.pdf": figure_q3_quality(data, quality),
        "paper-q4-frontier.pdf": figure_q4(data),
    }
    RECEIPT.write_bytes(receipt(outputs, summary).encode("utf-8"))
    for name, out in outputs.items():
        print(f"{name}  {hashlib.sha256(out.read_bytes()).hexdigest()}")
    print("receipt", RECEIPT.relative_to(REPO).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
