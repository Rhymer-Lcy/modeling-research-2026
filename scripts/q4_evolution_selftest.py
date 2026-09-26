"""T-011 executable guards, with mutation fixtures that must fail.

Every guard the T-011 specification requires is either asserted on the real
inputs and outputs, or broken on purpose and asserted to be rejected - usually
both. A guard that has never been seen to reject anything proves nothing, so a
case expected to raise is checked for the specific exception it must raise.
The assertion count is fixed: a case silently dropped also fails the run.

Needs the outputs of ``scripts/q4_evolution_run.py`` (the emitted IF4 and the
generated tables).

Run:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q4_evolution_selftest.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import interfaces as ifc  # noqa: E402
from src.evolution import bridge, claims, compute, dynamics, population, receipts, scores  # noqa: E402
from src.evolution.config import (  # noqa: E402
    BRIDGE_PRIMARY_STRATUM, GROUP_LABELS, HISTORICAL_SCENARIO, IF4_FILENAME, MIN_BIN_N, SCENARIOS,
)
from src.panel.c4_link import link_c4  # noqa: E402
from src.panel.detail import QUARANTINED_DIMENSIONS, extract_subtasks  # noqa: E402
from src.panel.leaderboard import ModelRecord  # noqa: E402
from src.panel.sources import load_c1  # noqa: E402
from src.paths import ATT_B, ATT_C, PROBLEM_F_INTERFACES, TABLES  # noqa: E402
from src.scaling.units import UnitError, predict_natural  # noqa: E402

RESULTS: list[tuple[str, bool]] = []
EXPECTED = 78
#: The head of Draft PR #15 reviewed before the v3 correction; its table-row numbers must survive.
REVIEWED_HEAD = "7309fa633c39fe560ad9b8391b3de1075d012908"

T011_SOURCES = sorted((REPO / "src" / "evolution").glob("*.py")) + sorted((REPO / "scripts").glob("q4_evolution_*.py"))
T011_TABLES = ["q4-evolution-population.md", "q4-bridge.md", "q4-decomposition.md",
               "q4-frontier-forecast.md", "q4-forecast-robustness.md"]


def check(name: str, ok: bool) -> None:
    RESULTS.append((name, bool(ok)))
    print(f"  [{'ok' if ok else 'FAIL'}]  {name}")


def raises(exc, fn) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception as other:  # noqa: BLE001 - a different exception is a failed guard
        print(f"        unexpected {type(other).__name__}: {other}")
        return False
    return False


def source_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in T011_SOURCES if p.name != "q4_evolution_selftest.py")


print("T-011 guard self-test")
if3 = receipts.load_if3()
if3_raw = receipts.read_input(receipts.IF3_FILE).read_bytes()
if3_payload = json.loads(if3_raw.decode("utf-8"))
panel = receipts.load_panel()
pop = population.build(panel)
c5, c6 = bridge.load_tables()
anchors = bridge.match_anchors(bridge.stratify(c5, c6), panel, load_c1())
if4_path = PROBLEM_F_INTERFACES / IF4_FILENAME
if4_payload = json.loads(if4_path.read_text(encoding="utf-8"))
code = source_text()


def build_if4(payload) -> ifc.IF4LossBenchmarkBridge:
    kw = dict(payload)
    kw["provenance"] = ifc.Provenance(**payload["provenance"])
    return ifc.IF4LossBenchmarkBridge(**kw)


print(" 1 accepted classic IF3 hash")
check("IF3 hash equals the tracked T-008 record", if3.sha256 == receipts.accepted_if3_sha256())
flipped = bytearray(if3_raw)
flipped[100] ^= 0x01
check("one flipped byte is refused", raises(receipts.AcceptedInterfaceError, lambda: receipts.load_if3(bytes(flipped))))

print(" 2 classic IF3 validate()")
check("IF3ScalingLaw.validate passes", receipts.build_if3(if3_payload).validate() is None)
bad = copy.deepcopy(if3_payload)
bad["bootstrap"]["unit"] = "row"
check("a row-level bootstrap is rejected by the contract", raises(ifc.InterfaceError, lambda: receipts.build_if3(bad).validate()))

print(" 3 raw N / raw D units")
s1 = c5[c5["Loss_Comparability"].str.startswith("High")]
n_raw, d_raw = s1["N_params_B"].to_numpy(float) * 1e9, s1["D_tokens_B"].to_numpy(float) * 1e9
check("IF3 at raw (N, D) reproduces the C5 Pythia losses to 2e-4",
      float(np.max(np.abs(if3.predict(n_raw, d_raw) - s1["Val_Loss"].to_numpy(float)))) < 2e-4)
billions = copy.deepcopy(if3_payload)
billions["validity_box"]["N"] = [v / 1e9 for v in billions["validity_box"]["N"]]
check("a validity box in billions is rejected", raises(receipts.AcceptedInterfaceError, lambda: receipts.check_if3_contract(billions)))
check("N in billions falls outside the box and is refused",
      raises(receipts.OutsideValidityBox, lambda: if3.predict(n_raw / 1e9, d_raw)))

print(" 4 Q sentinel is not a quality value")
check("the Q interval is the [1, 1] sentinel", if3.box["Q"] == (1.0, 1.0))
qbox = copy.deepcopy(if3_payload)
qbox["validity_box"]["Q"] = [0.5, 1.0]
check("a real Q interval is rejected", raises(receipts.AcceptedInterfaceError, lambda: receipts.check_if3_contract(qbox)))
check("a Q value cannot be passed to the classic law", raises(UnitError, lambda: predict_natural(if3.params, n_raw, d_raw, q=0.5)))
gamma = copy.deepcopy(if3_payload)
gamma["params"]["gamma"] = 1.0
check("a quality exponent in IF3 is rejected", raises(receipts.AcceptedInterfaceError, lambda: receipts.check_if3_contract(gamma)))

print(" 5 no B8 consumption")
check("reading B8 is refused", raises(receipts.ForbiddenInput, lambda: receipts.read_input(ATT_B / "supplementary_NQ_experiment_large.csv")))
check("no T-011 source names Attachment B or its quality tables",
      not re.search(r"ATT_B|B_scaling_laws|supplementary_NQ_experiment", code))

print(" 6 no IF2 cross-scale composition use")
check("reading IF2 is refused", raises(receipts.ForbiddenInput, lambda: receipts.read_input(PROBLEM_F_INTERFACES / "q1-if2-mixture-response.json")))
check("no T-011 source loads or evaluates IF2", not re.search(r"q1-if2|IF2MixtureResponse|if2_predict|load_accepted\(", code))

print(" 7 T-009 panel row uniqueness")
check("the rebuilt panel passes the T-009 receipt", receipts.check_panel(panel)["rows"] == len(panel))
dup = pd.concat([panel, panel.iloc[[0]]], ignore_index=True)
check("a duplicated panel row is refused", raises(receipts.PanelReceiptError, lambda: receipts.check_panel(dup)))

print(" 8 accepted date-source semantics")
fr = pop.frame
check("primary-dated population rows come only from publication-date sources",
      set(fr.loc[fr["date_confidence"] == "primary", "date_source"]) <= {"pub_date", "c4_pub_date"})
relabel = panel.copy()
idx = relabel.index[relabel["date_source"] == "submission_date"][0]
relabel.loc[idx, "date_confidence"] = "primary"
check("a submission date relabelled as primary is refused", raises(receipts.PanelReceiptError, lambda: receipts.check_panel(relabel)))
late = pd.DataFrame({"submission_date": ["2024-06-01"], "analysis_date": [pd.Timestamp("2024-09-01")],
                     "date_confidence": ["primary"]})
check("a publication date 92 days after submission fails date consistency", not bool(population.date_consistent(late).iloc[0]))

print(" 9 no-date rows excluded where time is required")
nodate = set(panel.loc[panel["date_confidence"] == "none", "model"])
check("no undated model is in the population", fr["analysis_date"].notna().all() and not (set(fr["model"]) & nodate))
check("annotating an undated row is refused",
      raises(population.PopulationError, lambda: population.annotate(panel[panel["date_confidence"] == "none"].head(1), pop.anchor)))

print("10 MATH C8 children cannot enter a primary analysis")
check("T-009 keeps MATH Lvl 5 quarantined", QUARANTINED_DIMENSIONS == frozenset({"MATH Lvl 5"}))
check("no T-011 source reads C8 or requests quarantined subtasks",
      not re.search(r"detailed_results|include_quarantined\s*=\s*True|extract_subtasks", code))
check("reading a C8 record is refused",
      raises(receipts.ForbiddenInput, lambda: receipts.read_input(ATT_C / "detailed_results" / "x" / "results.json")))
fixture = {"results": {"leaderboard_bbh_boolean_expressions": {"acc_norm,none": 0.5},
                       "leaderboard_math_algebra_hard": {"exact_match,none": 0.0}},
           "configs": {}, "group_subtasks": {"leaderboard_bbh": ["leaderboard_bbh_boolean_expressions"],
                                             "leaderboard_math_hard": ["leaderboard_math_algebra_hard"]}}
rec = ModelRecord(model_name="f/one", directory="f/one", source_file="r.json", scores={})
check("the primary per-task extraction drops MATH", set(extract_subtasks([rec], {"f/one": fixture})["dimension"]) == {"BBH"})

print("11 C3 cannot become canonical panel rows")
c3_hist = {"GPT-3 (175B)", "LLaMA (65B)", "Pythia-12B"}
check("population rows are all T-009 panel models", set(fr["model"]) <= set(panel["model"]) and not (set(fr["model"]) & c3_hist))
intruder = pd.concat([fr, fr.iloc[[0]].assign(model="GPT-3 (175B)")], ignore_index=True)
check("a C3 historical row is refused as a population row", raises(population.PopulationError, lambda: population.validate(intruder, panel)))

print("12 ambiguous C4 identities remain unlinked")
amb = link_c4(pd.DataFrame({"model": ["x/apollo-7b"]}),
              pd.DataFrame({"c4_model": ["Apollo 7B", "Apollo-7B"], "c4_org": ["Meta AI", "Meta AI"], "c4_hf_id": ["", ""]}))
check("a duplicated C4 key stays unlinked", amb.iloc[0]["link_method"] == "unlinked")
mutated = panel.copy()
row = mutated.index[mutated["link_method"] == "unlinked"][0]
mutated.loc[row, "c4_compute_flop"] = 1e23
sub = compute.subset(mutated, pop.anchor, set(fr["model"]))
check("an unlinked row with a compute value never enters the compute subset",
      mutated.loc[row, "model"] not in set(sub["model"]) and (sub["link_method"] != "unlinked").all())

print("13 bridge anchors unique and deterministically matched")
check("every anchor links by exact path, one to one",
      (anchors["identity_tier"] == "exact").all() and not anchors["panel_model"].duplicated().any())
typo = c6.copy()
typo.loc[0, "Model"] = typo.loc[0, "Model"] + "x"
t_rows = bridge.stratify(c5.assign(Model=c5["Model"].where(c5.index != 0, typo.loc[0, "Model"])), typo)
check("a one-character typo does not link (no fuzzy matching)",
      bridge.match_anchors(t_rows, panel, load_c1()).iloc[0]["identity_tier"] == "unmatched")
check("a duplicated anchor row is refused", raises(bridge.BridgeError, lambda: bridge.stratify(c5, pd.concat([c6, c6.iloc[[0]]]))))
FUZZY = r"\bimport difflib\b|\bfrom difflib\b|rapidfuzz|fuzzywuzzy|thefuzz|\bLevenshtein\b|SequenceMatcher|get_close_matches"
check("no T-011 source imports or calls a fuzzy string matcher", not re.search(FUZZY, code))
check("the fuzzy-matcher scan does fire on such code", bool(re.search(FUZZY, "from difflib import get_close_matches")))

print("14 bridge primary stratum declared")
check("IF4 primary stratum is the predeclared one and is a declared stratum",
      if4_payload["primary_stratum"] == BRIDGE_PRIMARY_STRATUM and BRIDGE_PRIMARY_STRATUM in if4_payload["strata"])
p14 = copy.deepcopy(if4_payload)
p14["primary_stratum"] = "pooled"
check("an undeclared primary stratum is rejected", raises(ifc.InterfaceError, lambda: build_if4(p14).validate()))

print("15 bridge prediction error nonempty")
pe = if4_payload["prediction_error"]
check("IF4 carries a finite positive out-of-fold error", np.isfinite(pe["loao_rmse"]) and pe["loao_rmse"] > 0)
p15 = copy.deepcopy(if4_payload)
p15["prediction_error"] = {}
check("an empty prediction error is rejected", raises(ifc.InterfaceError, lambda: build_if4(p15).validate()))

print("16 IF4 validate() on the emitted object")
check("the emitted IF4 validates", build_if4(if4_payload).validate() is None)
recorded = re.findall(r"SHA-256: `([0-9a-f]{64})`", (TABLES / "q4-bridge.md").read_text(encoding="utf-8"))
check("the emitted IF4 bytes match the hash recorded in q4-bridge.md",
      recorded == [hashlib.sha256(if4_path.read_bytes()).hexdigest()])
p16 = copy.deepcopy(if4_payload)
p16["n_anchor_models"] = 0
check("zero anchors is rejected", raises(ifc.InterfaceError, lambda: build_if4(p16).validate()))

print("17 score direction explicit")
aud = scores.audit(panel)
check("all six dimensions verified higher-is-better", bool(aud["verified"].all()) and set(scores.DIRECTIONS.values()) == {"higher_better"})
flip = dict(scores.DIRECTIONS)
flip["score_gpqa"] = "lower_better"
check("a lower-is-better dimension blocks the macro score", raises(scores.ScoreScaleError, lambda: scores.macro_score(panel, flip)))

print("18 forecast anchor equals the final observed panel date")
check("anchor is the population's last analysis date", pop.anchor == fr["analysis_date"].max() and dynamics.check_anchor(fr, pop.anchor) is None)
check("the machine date is refused as an anchor", raises(dynamics.ForecastError, lambda: dynamics.check_anchor(fr, pd.Timestamp.now().normalize())))
future = fr[fr["group"] == "BC"].copy()
future.loc[future.index[0], "analysis_date"] = pop.anchor + pd.Timedelta(days=5)
check("a row after the anchor is refused", raises(dynamics.ForecastError, lambda: dynamics.forecast_table(future, pop.anchor, "x")))

print("19 12- and 24-month horizons from the anchor")
hd = dynamics.horizon_dates(pop.anchor)
check("horizons are anchor + 12 and + 24 calendar months",
      hd["primary_12m"] == pop.anchor + pd.DateOffset(months=12) and hd["stress_24m"] == pop.anchor + pd.DateOffset(months=24))
fc_text = (TABLES / "q4-frontier-forecast.md").read_text(encoding="utf-8")
check("the rendered forecast states both horizon dates and labels 24 months as stress",
      f"12-month primary horizon: {hd['primary_12m']:%Y-%m-%d}" in fc_text
      and f"24-month stress horizon: {hd['stress_24m']:%Y-%m-%d}" in fc_text
      and "24-month STRESS extrapolation" in fc_text)

print("20 bridge uncertainty enters bridge-based bands")
lo_s, hi_s = if4_payload["params"]["loss_support_min"], if4_payload["params"]["loss_support_max"]
mid = 0.5 * (lo_s + hi_s)
_, sd0 = bridge.bridge_predict(if4_payload, [mid], 0.0)
_, sd1 = bridge.bridge_predict(if4_payload, [mid], 0.2)
check("a bridge-based band is never narrower than the IF4 predictive SD",
      float(sd0[0]) == pe["predictive_sd"] and float(sd1[0]) >= pe["predictive_sd"])
p20 = copy.deepcopy(if4_payload)
p20["prediction_error"]["predictive_sd"] = 0.0
check("a band with the bridge error removed is refused", raises(bridge.BridgeError, lambda: bridge.bridge_predict(p20, [mid])))
check("a loss outside the bridge support is refused", raises(bridge.OutsideBridgeSupport, lambda: bridge.bridge_predict(if4_payload, [lo_s - 0.1])))

print("21 outside-box rows cannot enter the primary IF3 decomposition")
csub = compute.infer_nd(compute.subset(panel, pop.anchor, set(fr["model"])), if3)
inside = csub[csub["inside_if3_box"]]
check("the primary IF3 decomposition runs on inside-box rows", compute.if3_primary(inside, if3)["n"] == len(inside))
mixed = pd.concat([inside, csub[~csub["inside_if3_box"] & csub["d_inferred"].notna()].head(1)])
check("an outside-box row is refused", raises(receipts.OutsideValidityBox, lambda: compute.if3_primary(mixed, if3)))

print("22 compute-conditioned analysis reports its subset size")
result = compute.log_compute(csub[csub["stratum"] == "A"], "selftest")
result["sizes"] = compute.sizes(panel, csub, result["n"])
check("a sized result passes", compute.require_sizes(result) is None)
check("a result without its subset size is refused", raises(compute.SubsetSizeMissing, lambda: compute.require_sizes({"n": 5})))

print("   additional")
tiny = fr[fr["group"] == "BC"].copy()
sparse_month = tiny["month"].value_counts()
sparse_month = sparse_month[sparse_month < MIN_BIN_N].index[0]
check("a sparse month never contributes a frontier-set member",
      not dynamics.frontier_flags(tiny)[tiny["month"] == sparse_month].any())
PROHIBITED = [r"\btime causes\b", r"calendar coefficient equals", r"technical progress rate",
              r"efficiency improvement caused by time", r"caused by (calendar )?time"]


def causal_hits(text: str) -> list:
    return [p for p in PROHIBITED if re.search(p, text, re.I)]


check("no generated table uses prohibited causal language",
      all(not causal_hits((TABLES / t).read_text(encoding="utf-8")) for t in T011_TABLES))
check("the causal-language scan does fire on a prohibited sentence",
      bool(causal_hits("Here time causes technical progress at 5 points a year.")))
check("generated tables are LF-only with no trailing whitespace",
      all(b"\r" not in (TABLES / t).read_bytes()
          and all(line == line.rstrip() for line in (TABLES / t).read_text(encoding="utf-8").split("\n"))
          for t in T011_TABLES))

print("v3 claim language and downstream handoff")
fcast = (TABLES / "q4-frontier-forecast.md").read_text(encoding="utf-8")
robust = (TABLES / "q4-forecast-robustness.md").read_text(encoding="utf-8")
handover = (REPO / "reviews" / "T-011" / "HANDOVER.md").read_text(encoding="utf-8")
rows = [line for line in fcast.split("\n") if line.startswith("|")]
bc = claims.section(fcast, "## Group BC: " + GROUP_LABELS["BC"])

print(" v3.1 parameter-scale scenarios are never compute-growth scenarios")
param_keys = [k for k in SCENARIOS if k != HISTORICAL_SCENARIO]
param_rows = [r for r in rows if claims.PARAMETER_SCALE_LABEL in r]
check("every parameter-scale scenario key and rendered row is marked parameter-scale and never compute",
      param_rows and all(not claims.parameter_scale_label_errors(k) for k in param_keys)
      and all("compute" not in r.lower() for r in param_rows))
check("a compute-growth label on a parameter-scale scenario is refused",
      bool(claims.parameter_scale_label_errors("compute-growth scenario (x0.5)"))
      and bool(claims.parameter_scale_label_errors("slowdown_half")))
check("the retired 'compute slowdown = halved parameter-scale rate' wording is gone",
      not re.search(r"asks for slowing compute growth|compute growth, so the halved|primary `slowdown_half`",
                    code + fcast + robust))

print(" v3.2 compute-slowdown outputs are assumption-based and transferred")
comp_rows = [r for r in rows if "Compute-growth multiplier" not in r and r.count("|") > 4
             and ("compute-slowdown" in r.lower())]
comp_sections = [claims.section(claims.section(fcast, h), "### Compute-slowdown: " + claims.COMPUTE_SENSITIVITY_LABEL)
                 for h in ("## Group A: " + GROUP_LABELS["A"], "## Group BC: " + GROUP_LABELS["BC"])]
check("every compute-slowdown row and section is marked assumption-based / transferred, with no identified-effect claim",
      comp_rows and all(claims.COMPUTE_SENSITIVITY_LABEL in r for r in comp_rows)
      and all(s and not claims.compute_sensitivity_errors(s) for s in comp_sections))
check("an identified-effect claim or a missing marker is refused",
      bool(claims.compute_sensitivity_errors("assumption-based transferred: the empirically identified BC compute share gives 47.64"))
      and bool(claims.compute_sensitivity_errors("compute slowdown forecast 47.64")))

print(" v3.3 the direct-score 12-month point is the historical continuation")
bc_frame = fr[fr["group"] == "BC"]
q = dynamics.quantile_split(bc_frame)
h12 = dynamics.years_between(hd["primary_12m"], pop.anchor)
continuation = f"{q['level0'] + q['g_time'] * h12:.2f}"
head_row = [r for r in claims.section(bc, "### Headline forecast").split("\n")
            if r.startswith("| 12-month forecast") and claims.HISTORICAL_LABEL in r]
check("BC's 12-month historical-continuation row carries the recomputed direct-score point",
      len(head_row) == 1 and f"| {continuation} |" in head_row[0] and continuation == "50.89")
check("a slowdown / compute label on the continuation is refused",
      bool(claims.historical_label_errors("compute-slowdown forecast")) and not claims.historical_label_errors(claims.HISTORICAL_LABEL))

print(" v3.4 no bridge-based frontier forecast is emitted")


def bridge_forecast_rows(text: str) -> list:
    """Table rows presenting a bridge-based (loss -> score) forecast."""
    return [r for r in text.split("\n") if r.startswith("|")
            and re.search(r"bridge-based|bridge-conditional|via IF4|bridge translation", r, re.I)]


unc_rows = [r for r in rows if r.startswith("| primary_12m") or r.startswith("| stress_24m")]
check("no forecast row is bridge-based and every uncertainty row leaves IF3 and IF4 unused",
      not bridge_forecast_rows(fcast) and unc_rows and all(r.rstrip().endswith("| not used | not used |") for r in unc_rows)
      and "import bridge" not in (REPO / "src" / "evolution" / "dynamics.py").read_text(encoding="utf-8"))
check("a planted bridge-based forecast row is detected",
      bool(bridge_forecast_rows("| 12-month forecast | 2026-03-13 | bridge-based translation | 5.66 |")))

print(" v3.5-7 mandatory Q4 source coverage in the T-012 handoff")
check("the handoff contract carries the C3, C4 and C8 items", claims.downstream_contract_missing(handover) == [])


def without(text: str, item: str) -> str:
    """Remove one contract bullet (and its continuation lines) from the handover."""
    out, skip = [], False
    for line in text.split("\n"):
        if line.startswith("- **") or line.startswith("#") or not line.strip():
            skip = line.startswith("- **" + item)
        if not skip:
            out.append(line)
    return "\n".join(out)


body = claims.section(handover, claims.DOWNSTREAM_HEADING)
c8_block = next(b for b in re.split(r"\n(?=- \*\*)", "\n" + body) if b.lstrip("\n").startswith("- **C8"))
check("dropping the C3 item is detected (C3 manuscript requirement)",
      "C3" in claims.downstream_contract_missing(without(handover, "C3")))
check("dropping BBH / MUSR from the C8 item is detected (T-009 C8 requirement)",
      "C8" in claims.downstream_contract_missing(handover.replace(c8_block, c8_block.replace("MUSR", "MU-SR"))))
check("dropping the MATH prohibition from the C8 item is detected",
      "C8" in claims.downstream_contract_missing(handover.replace(c8_block, c8_block.replace("MATH", "M4TH"))))

print(" v3.8 the date-clock range sits with the headline forecast")
clock = {}
for line in robust.split("\n"):
    m = re.match(r"\| `(primary|publication_date_only|fallback_date_only)` \| BC \|.*\| ([\d.]+) \|$", line)
    if m:
        clock[m.group(1)] = m.group(2)
headings = [line for line in bc.split("\n") if line.startswith("### ")]
after_headline = headings[headings.index("### Headline forecast") + 1] if "### Headline forecast" in headings else ""
clock_section = claims.section(bc, "### Date-clock sensitivity of the headline")
check("the date-clock section directly follows the BC headline and carries all three clock points",
      len(clock) == 3 and after_headline == "### Date-clock sensitivity of the headline"
      and not claims.clock_values_missing(clock_section, list(clock.values())))
check("the handover states the three clock points in its forecast section",
      not claims.clock_values_missing(claims.section(handover, "### Frontier and forecast (`q4-frontier-forecast.md`)"),
                                      list(clock.values())))
check("a headline section without the clock table is detected",
      bool(claims.clock_values_missing(claims.section(bc, "### Headline forecast"), ["65.31"])))

print(" v3 numeric preservation")
NUM = re.compile(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:e[+-]?\d+)?%?")


def lost_numbers(old: str, new: str) -> Counter:
    rows_of = lambda s: "\n".join(line for line in s.split("\n") if line.startswith("|"))  # noqa: E731
    return Counter(NUM.findall(rows_of(old))) - Counter(NUM.findall(rows_of(new)))


reviewed = {t: subprocess.run(["git", "-C", str(REPO), "show", REVIEWED_HEAD + ":results/tables/" + t],
                              capture_output=True, text=True, encoding="utf-8", check=True).stdout for t in T011_TABLES}
check("every table-row number of the reviewed pre-v3 tables survives in the regenerated tables",
      all(not lost_numbers(reviewed[t], (TABLES / t).read_text(encoding="utf-8")) for t in T011_TABLES))
check("a changed reviewed number is detected",
      bool(lost_numbers(reviewed["q4-frontier-forecast.md"], reviewed["q4-frontier-forecast.md"].replace("50.89", "50.90"))))

print()
failed = [name for name, ok in RESULTS if not ok]
if len(RESULTS) != EXPECTED:
    print(f"RESULT: FAIL (expected {EXPECTED} assertions, ran {len(RESULTS)})")
    sys.exit(1)
if failed:
    print(f"RESULT: FAIL ({len(failed)} of {len(RESULTS)} assertions failed)")
    for name in failed:
        print("  - " + name)
    sys.exit(1)
print(f"RESULT: PASS ({len(RESULTS)} assertions)")
sys.exit(0)
