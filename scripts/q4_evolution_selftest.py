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
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import interfaces as ifc  # noqa: E402
from src.evolution import bridge, compute, dynamics, population, receipts, scores  # noqa: E402
from src.evolution.config import BRIDGE_PRIMARY_STRATUM, IF4_FILENAME, MIN_BIN_N  # noqa: E402
from src.panel.c4_link import link_c4  # noqa: E402
from src.panel.detail import QUARANTINED_DIMENSIONS, extract_subtasks  # noqa: E402
from src.panel.leaderboard import ModelRecord  # noqa: E402
from src.panel.sources import load_c1  # noqa: E402
from src.paths import ATT_B, ATT_C, PROBLEM_F_INTERFACES, TABLES  # noqa: E402
from src.scaling.units import UnitError, predict_natural  # noqa: E402

RESULTS: list[tuple[str, bool]] = []
EXPECTED = 60

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
