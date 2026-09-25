"""T-008 final closure: accepted IF1/IF2 consumption, generalized-law adoption
gates, Q(p) diagnostics, unit equivalence (G2-U) and the final IF3 decision.

Writes `results/tables/q2-final-closure.md`. Regenerate; do not edit by hand.

    conda run -n modeling-research-2026 --no-capture-output python scripts/q2_final_closure.py

Run it through `conda run`, not by calling the environment's interpreter
directly: without activation the environment's own DLL directory is not on
PATH, and scipy's L-BFGS-B then loads an incompatible BLAS/LAPACK from another
installation and the process dies inside the optimiser.

Every adoption criterion below was fixed in this file before any fit in it was
run. The decision is computed from them; it is not chosen afterwards.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import interfaces as ifc  # noqa: E402
from src.paths import ATT_B, PROBLEM_F_INTERFACES, REPO_ROOT, TABLES, ensure, require  # noqa: E402
from src.quality.configuration import load_settings  # noqa: E402
from src.scaling import closure as cl  # noqa: E402
from src.scaling import law  # noqa: E402
from src.scaling import units as un  # noqa: E402
from src.scaling.quality import GAMMA_BOUNDS, bound_status, fit_quality_law  # noqa: E402

# ---------------------------------------------------------------------------
# Predeclared adoption criteria (fixed before any fit below was run)
# ---------------------------------------------------------------------------

#: GQ3: the candidate must beat the no-Q baseline under leave-one-Q-level-out.
GQ3_MIN_ERROR_REDUCTION = 0.0
#: GQ4(b): moving gamma by 10% either way must raise the objective by >= 1%.
GQ4_PROFILE_MIN_RATIO = 1.01
#: GQ4(c): leave-one-Q-level-out gamma range, relative to the full fit.
GQ4_MAX_LOO_RELATIVE_RANGE = 0.5
#: Section 9: a Q(p)-only summary leaves a LARGE residual composition effect
#: when its mean per-target R2 on the frozen 1M surface is below this.
RESIDUAL_LARGE_BELOW_R2 = 0.5
#: Profile grid, as multiples of the full-fit gamma.
PROFILE_FACTORS = (0.5, 0.75, 0.9, 0.95, 1.0, 1.05, 1.1, 1.25, 1.5, 2.0)
#: Parameter bounds used by the quality fitter (alpha, beta; gamma from quality.py).
EXPONENT_BOUNDS = (1e-3, 3.0)

#: Where the accepted T-007 review records are read from. Deliberately a
#: separate name from the output directory, so redirecting this script's output
#: can never redirect an accepted input.
ACCEPTED_TABLES = TABLES

QUALITY_TABLE = "supplementary_NQ_experiment_expanded.csv"   # B7 (contains B6 exactly)
QUARANTINED_TABLE = "supplementary_NQ_experiment_large.csv"   # B8
N_COL, D_COL = "N_params_B", "D_tokens_B"


def fmt(x, digits=4):
    if x is None:
        return "-"
    if isinstance(x, (bool, np.bool_)):
        return "yes" if x else "no"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    x = float(x)
    if not np.isfinite(x):
        return "undefined"
    return format(x, "." + str(digits) + "g")


def verdict(ok):
    return "**PASS**" if ok else "**FAIL**"


def log_residuals(pred, obs):
    return np.log(np.asarray(pred, float)) - np.log(np.asarray(obs, float))


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def accepted_interfaces():
    if1, p1, sha1 = cl.load_accepted("IF1")
    if2, p2, sha2 = cl.load_accepted("IF2")
    receipt = cl.check_if2_scope(p2)
    notes_head, _, notes_tail = p1["provenance"]["notes"].partition("\n")
    embedded = json.loads(notes_tail)
    pooled_q = embedded["uncertainty"]["overall"]["q"]
    directions = {}
    for v in if1.indicator_directions.values():
        directions[v] = directions.get(v, 0) + 1
    acc = p2["validation"]["acceptance"]
    return {
        "if1": if1, "if1_payload": p1, "if1_sha": sha1,
        "if2": if2, "if2_payload": p2, "if2_sha": sha2,
        "receipt": receipt,
        "if1_pooled_q": float(pooled_q),
        "if1_domain_q": {k: float(v) for k, v in if1.q_by_domain.items()},
        "if1_mapped": sorted(k for k, v in if1.mixture_to_quality.items() if v),
        "if1_unmapped": sorted(k for k, v in if1.mixture_to_quality.items() if not v),
        "if1_directions": directions,
        "if2_roles": {k: p2["validation"][k]["role"] for k in ("A6_A7", "A8_A9", "A10_A11")},
        "if2_nrmse": float(acc["out_design_macro_centered_nrmse"]),
        "if2_nrmse_max": float(acc["thresholds"]["out_design_max_centered_nrmse"]),
        "if2_release_pass": acc["release_pass"],
    }


def classic_if3():
    path = require(PROBLEM_F_INTERFACES / "IF3_classic.json")
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    obj = ifc.IF3ScalingLaw(
        schema_version=payload["schema_version"],
        functional_form=payload["functional_form"],
        params=payload["params"],
        param_cov=payload["param_cov"],
        bootstrap=payload["bootstrap"],
        validity_box=payload["validity_box"],
        validation=payload["validation"],
        q_term_provenance=ifc.Provenance(**payload["q_term_provenance"]),
        provenance=ifc.Provenance(**payload["provenance"]),
    )
    obj.validate()
    return obj, payload, hashlib.sha256(raw).hexdigest(), path


def g2u(params_internal, conv, box_internal, extra_internal=None):
    """Invariance over corners, interior points and any supplied benchmark points."""
    pts = {k: [] for k in box_internal}
    for source in (un.box_corners(box_internal), un.interior_points(box_internal, 4)):
        for k in pts:
            pts[k].extend(np.asarray(source[k]).tolist())
    if extra_internal is not None:
        for k in pts:
            pts[k].extend(np.asarray(extra_internal[k]).tolist())
    pts = {k: np.asarray(v, float) for k, v in pts.items()}
    inv = un.invariance_check(params_internal, conv, pts)
    rt = un.round_trip_error(params_internal, box_internal, conv)
    return inv, rt


def candidate_section(frame):
    n = frame[N_COL].to_numpy(float)
    d = frame[D_COL].to_numpy(float)
    q = frame["Q_score"].to_numpy(float)
    loss = frame["val_loss"].to_numpy(float)

    full = fit_quality_law(n, d, q, loss)
    p = full.params

    # GQ1 - parameter domain.
    status = {
        "alpha": bound_status(p["alpha"], EXPONENT_BOUNDS),
        "beta": bound_status(p["beta"], EXPONENT_BOUNDS),
        "gamma": bound_status(p["gamma"], GAMMA_BOUNDS),
    }

    def distance(v, b):
        return min((v - b[0]) / (b[1] - b[0]), (b[1] - v) / (b[1] - b[0]))

    dist = {"alpha": distance(p["alpha"], EXPONENT_BOUNDS),
            "beta": distance(p["beta"], EXPONENT_BOUNDS),
            "gamma": distance(p["gamma"], GAMMA_BOUNDS)}
    gq1 = (full.converged and all(p[k] > 0 for k in ("E", "A", "B"))
           and all(s == "interior" for s in status.values()))

    # GQ2 - direction on the usable quality table.
    direction = cl.q_direction(frame)
    gq2 = direction["negative"] == direction["cells"]

    # GQ3 - leave-one-Q-level-out, candidate against the no-Q baseline.
    levels = sorted(frame["Q_score"].unique())
    res_c, res_b, rel_c, rel_b, folds = [], [], [], [], []
    for level in levels:
        tr = q != level
        te = ~tr
        fc = fit_quality_law(n[tr], d[tr], q[tr], loss[tr])
        fb = law.fit_law(n[tr], d[tr], loss[tr])
        pc = fc.predict(n[te], d[te], q[te])
        pb = fb.predict(n[te], d[te])
        rc, rb = log_residuals(pc, loss[te]), log_residuals(pb, loss[te])
        res_c.extend(rc.tolist())
        res_b.extend(rb.tolist())
        rel_c.extend((np.abs(pc - loss[te]) / loss[te]).tolist())
        rel_b.extend((np.abs(pb - loss[te]) / loss[te]).tolist())
        folds.append({"level": float(level), "rows": int(te.sum()),
                      "rmse_c": float(np.sqrt(np.mean(rc ** 2))),
                      "rmse_b": float(np.sqrt(np.mean(rb ** 2))),
                      "gamma": fc.params["gamma"], "beta": fc.params["beta"],
                      "bound": bound_status(fc.params["gamma"], GAMMA_BOUNDS)})
    rmse_c = float(np.sqrt(np.mean(np.square(res_c))))
    rmse_b = float(np.sqrt(np.mean(np.square(res_b))))
    reduction = 1.0 - rmse_c / rmse_b
    gq3 = reduction > GQ3_MIN_ERROR_REDUCTION

    # GQ4 - identifiability and stability.
    def block_out(col):
        out = []
        for level in sorted(frame[col].unique()):
            tr = frame[col].to_numpy(float) != level
            f = fit_quality_law(n[tr], d[tr], q[tr], loss[tr])
            out.append({"level": float(level), "gamma": f.params["gamma"],
                        "bound": bound_status(f.params["gamma"], GAMMA_BOUNDS)})
        return out

    lon = block_out(N_COL)
    lod = block_out(D_COL)
    loq_g = np.array([f["gamma"] for f in folds])
    loq_range = float((loq_g.max() - loq_g.min()) / p["gamma"])
    all_interior = all(f["bound"] == "interior" for f in folds + lon + lod)
    profile = cl.profile_gamma(n, d, q, loss, full.raw,
                               [p["gamma"] * f for f in PROFILE_FACTORS])
    base_obj = min(r["objective"] for r in profile if abs(r["gamma"] / p["gamma"] - 1) < 1e-12)
    for r in profile:
        r["ratio"] = r["objective"] / base_obj
    at = {round(r["gamma"] / p["gamma"], 6): r["ratio"] for r in profile}
    profile_rises = at.get(0.9, 0) >= GQ4_PROFILE_MIN_RATIO and at.get(1.1, 0) >= GQ4_PROFILE_MIN_RATIO
    gq4 = all_interior and profile_rises and loq_range <= GQ4_MAX_LOO_RELATIVE_RANGE

    return {
        "fit": full, "n": n, "d": d, "q": q, "loss": loss,
        "status": status, "distance": dist, "gq1": gq1,
        "direction": direction, "gq2": gq2,
        "folds": folds, "rmse_c": rmse_c, "rmse_b": rmse_b,
        "mre_c": float(np.median(rel_c)), "mre_b": float(np.median(rel_b)),
        "reduction": reduction, "gq3": gq3,
        "lon": lon, "lod": lod, "loq_range": loq_range, "all_interior": all_interior,
        "profile": profile, "profile_at": at, "profile_rises": profile_rises, "gq4": gq4,
    }


def composition_section(acc):
    seed, settings = load_settings("mixture")
    a4 = cl.load_fitting_mixture("A4", settings["row_sum_tolerance"])
    from src.mixture.data import normalised_proportions
    from src.mixture.model import FitResult, predict as producer_predict

    p = normalised_proportions(a4)
    domains = list(a4.domains)
    targets, pred = cl.if2_predict(acc["if2_payload"], p, domains, scale="1M")

    # The consumer evaluator must reproduce the producer's own predictor.
    worst = 0.0
    ref = acc["if2_payload"]["contrast_basis"]
    for t, target in enumerate(targets):
        coef = acc["if2_payload"]["coefficients"][target]
        fr = FitResult(target, ref,
                       {k: float(v) for k, v in coef.items()
                        if k != "__intercept__" and not k.startswith("interaction:")},
                       float(coef["__intercept__"]), 0.0, 0.0, "pairwise_interactions",
                       {k[len("interaction:"):]: float(v) for k, v in coef.items()
                        if k.startswith("interaction:")})
        worst = max(worst, float(np.max(np.abs(producer_predict(fr, a4) - pred[:, t]))))

    mass, qp = cl.mapped_quality(p, domains, acc["if1"])
    keep = mass > 0
    macro = pred.mean(axis=1)

    per_target = []
    for t, target in enumerate(targets):
        y = pred[keep, t]
        r2_q, coef_q = cl.ols_r2(y, [qp[keep]])
        r2_qm, _ = cl.ols_r2(y, [qp[keep], mass[keep]])
        rho = float(spearmanr(qp[keep], y).statistic)
        per_target.append({"target": target.replace("metric/the_pile_", "").replace("_val_loss", ""),
                           "r2_q": r2_q, "r2_qm": r2_qm, "slope": float(coef_q[1]), "rho": rho})

    r2_macro_q, coef_macro = cl.ols_r2(macro[keep], [qp[keep]])
    r2_macro_qm, _ = cl.ols_r2(macro[keep], [qp[keep], mass[keep]])
    rho_macro = float(spearmanr(qp[keep], macro[keep]).statistic)

    cuts = np.quantile(mass[keep], [1.0 / 3.0, 2.0 / 3.0])
    tercile = np.digitize(mass[keep], cuts)
    terciles = []
    for k in range(3):
        sel = tercile == k
        r2, _ = cl.ols_r2(macro[keep][sel], [qp[keep][sel]])
        terciles.append({"k": k + 1, "rows": int(sel.sum()),
                         "mass_lo": float(mass[keep][sel].min()), "mass_hi": float(mass[keep][sel].max()),
                         "rho": float(spearmanr(qp[keep][sel], macro[keep][sel]).statistic),
                         "r2": r2})
    gq5 = rho_macro < 0 and all(t["rho"] < 0 for t in terciles)

    return {
        "designs": int(len(mass)), "zero_mass": int((~keep).sum()), "used": int(keep.sum()),
        "mass_mean": float(mass.mean()), "q_range": (float(np.nanmin(qp)), float(np.nanmax(qp))),
        "producer_max_abs_diff": worst, "targets": len(targets),
        "per_target": per_target,
        "r2_macro_q": r2_macro_q, "r2_macro_qm": r2_macro_qm, "rho_macro": rho_macro,
        "slope_macro": float(coef_macro[1]),
        "terciles": terciles, "gq5": gq5,
        "mean_r2_q": float(np.mean([r["r2_q"] for r in per_target])),
        "mean_r2_qm": float(np.mean([r["r2_qm"] for r in per_target])),
        "neg_slopes": sum(1 for r in per_target if r["slope"] < 0),
    }


def compatibility_section(cand, classic_payload):
    """GQ7: identifying-support intersection and N-D compatibility on the overlap."""
    conv = un.convention_for_columns(N_COL, D_COL)
    fit = cand["fit"]
    cand_box_raw = un.box_to_raw(fit.validity_box, conv)
    cbox = classic_payload["validity_box"]
    inter = {k: [max(cand_box_raw[k][0], cbox[k][0]), min(cand_box_raw[k][1], cbox[k][1])]
             for k in ("N", "D")}
    inter["Q"] = list(cand_box_raw["Q"])
    nonempty = all(inter[k][0] < inter[k][1] for k in ("N", "D"))

    v = classic_payload["validation"]
    tolerance = max(v["B5_literature"]["median_abs_rel_err"],
                    v["B4_cross_family_excl_pythia"]["median_abs_rel_err"])

    # Direction 1: the accepted law on the quality table where the candidate
    # reduces to an N-D law (Q^gamma = 1 at Q = 1).
    q = cand["q"]
    top = q == q.max()
    classic_params = {k: float(classic_payload["params"][k]) for k in ("E", "A", "alpha", "B", "beta")}
    pc = un.predict_natural(classic_params, cand["n"][top] * conv.s_n, cand["d"][top] * conv.s_d)
    mre_classic_on_b7 = float(np.median(np.abs(pc - cand["loss"][top]) / cand["loss"][top]))

    # Direction 2: the candidate's N-D component on the observed external tables.
    from src.scaling import data as bdata
    cand_raw = un.params_to_raw(fit.params, conv)
    ext = {}
    for label, table in (("B5_literature", bdata.load_published()),
                         ("B4_cross_family_excl_pythia", bdata.load_cross_family())):
        f = table.frame
        pr = un.predict_natural(cand_raw, f[N_COL].to_numpy(float) * conv.s_n,
                                f[D_COL].to_numpy(float) * conv.s_d, np.ones(len(f)))
        obs = f["val_loss"].to_numpy(float)
        ext[label] = float(np.median(np.abs(pr - obs) / obs))
    compatible = mre_classic_on_b7 <= tolerance and all(x <= tolerance for x in ext.values())
    return {
        "cand_box_raw": cand_box_raw, "intersection": inter, "nonempty": nonempty,
        "tolerance": tolerance, "classic_on_b7_top_q": mre_classic_on_b7,
        "top_q": float(q.max()), "top_rows": int(top.sum()),
        "candidate_on_external": ext, "classic_external": {
            "B5_literature": v["B5_literature"]["median_abs_rel_err"],
            "B4_cross_family_excl_pythia": v["B4_cross_family_excl_pythia"]["median_abs_rel_err"]},
        "gq7": nonempty and compatible,
    }


def b6_within_b7(b7):
    """True when every B6 design point appears in B7 with a bit-identical loss."""
    b6 = pd.read_csv(require(ATT_B / "supplementary_NQ_experiment.csv"))
    key = [N_COL, D_COL, "Q_score"]
    merged = b6.merge(b7, on=key, how="left", suffixes=("_b6", "_b7"))
    return bool(len(merged) == len(b6) and merged["val_loss_b7"].notna().all()
                and (merged["val_loss_b6"] == merged["val_loss_b7"]).all())


def runtime_match():
    """Compare this interpreter's runtime with the one the accepted T-007 run recorded."""
    import platform
    import numpy
    import pandas
    import scipy
    import yaml
    text = require(ACCEPTED_TABLES / "q1-reproduction.md").read_text(encoding="utf-8")
    line = [ln for ln in text.splitlines() if ln.startswith("Runtime: ")]
    if len(line) != 1:
        raise ValueError("q1-reproduction.md must record exactly one Runtime line")
    recorded = json.loads(line[0][len("Runtime: "):])
    here = {"python": platform.python_version(), "numpy": numpy.__version__,
            "scipy": scipy.__version__, "pandas": pandas.__version__, "pyyaml": yaml.__version__}
    return here, recorded, all(here.get(k) == v for k, v in recorded.items())


def quarantine_section():
    b8 = pd.read_csv(require(ATT_B / QUARANTINED_TABLE))
    out = {}
    for stratum in ("calibrated", "extrapolated"):
        f = b8.loc[b8["data_type"] == stratum]
        dd = cl.q_direction(f)
        lo = float(f["val_loss"].min())
        out[stratum] = {"rows": int(len(f)), "cells": dd["cells"], "positive": dd["positive"],
                        "floor": lo, "at_floor": int((f["val_loss"] == lo).sum())}
    return out


def unit_section(cand, classic_payload):
    conv = un.convention_for_columns(N_COL, D_COL)
    # Candidate: fitted internally in billions.
    fit = cand["fit"]
    bench = {"N": np.array([0.41, 2.8, 11.97]), "D": np.array([50.0, 150.0, 600.0]),
             "Q": np.array([0.5, 0.7, 0.9])}
    inv_c, rt_c = g2u(fit.params, conv, fit.validity_box, bench)
    # Classic: emitted in raw counts; test it through the internal convention.
    cp = {k: float(classic_payload["params"][k]) for k in ("E", "A", "alpha", "B", "beta")}
    cbox_raw = {k: classic_payload["validity_box"][k] for k in ("N", "D")}
    cp_int = un.params_to_internal(cp, conv)
    cbox_int = un.box_to_internal(cbox_raw, conv)
    from src.scaling import data as bdata
    ext = {"N": [], "D": []}
    for table in (bdata.load_published(), bdata.load_cross_family()):
        ext["N"].extend(table.frame[N_COL].tolist())
        ext["D"].extend(table.frame[D_COL].tolist())
    inv_k, rt_k = g2u(cp_int, conv, cbox_int, {k: np.asarray(v) for k, v in ext.items()})
    # The serialised classic box must be the fit data's own range in raw counts.
    b1 = bdata.load_pythia_log().frame
    expect = {"N": [b1[N_COL].min() * conv.s_n, b1[N_COL].max() * conv.s_n],
              "D": [b1[D_COL].min() * conv.s_d, b1[D_COL].max() * conv.s_d]}
    serial_raw = all(abs(classic_payload["validity_box"][k][i] - expect[k][i]) <= un.INVARIANCE_RTOL * expect[k][i]
                     for k in ("N", "D") for i in (0, 1))
    return {"conv": conv, "inv_c": inv_c, "rt_c": rt_c, "inv_k": inv_k, "rt_k": rt_k,
            "serial_raw": serial_raw,
            "passed": inv_c["pass"] and rt_c["pass"] and inv_k["pass"] and rt_k["pass"] and serial_raw}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    acc = accepted_interfaces()

    try:
        cl.bind_quality_axis("B7_Q_score", "IF1_Q")
        mapping_established = True
        mapping_note = "declared"
    except cl.UnsupportedScaleMapping as exc:
        mapping_established = False
        mapping_note = str(exc)

    classic, classic_payload, classic_sha, classic_path = classic_if3()
    frame = pd.read_csv(require(ATT_B / QUALITY_TABLE))
    cand = candidate_section(frame)
    comp = composition_section(acc)
    compat = compatibility_section(cand, classic_payload)
    quarantine = quarantine_section()
    units = unit_section(cand, classic_payload)
    b6_subset = b6_within_b7(frame)
    runtime_here, runtime_recorded, runtime_same = runtime_match()

    gates = [
        ("GQ1", "parameter domain", cand["gq1"]),
        ("GQ2", "directional stability", cand["gq2"]),
        ("GQ3", "internal predictive usefulness", cand["gq3"]),
        ("GQ4", "robustness / identifiability", cand["gq4"]),
        ("GQ5", "real 1M consistency (diagnostic)", comp["gq5"]),
        ("GQ7", "validity discipline", compat["gq7"]),
    ]
    adopted = all(ok for _, _, ok in gates) and mapping_established
    if adopted:
        raise SystemExit(
            "STOP: every generalized-adoption gate passed and a quality-axis mapping is "
            "declared. This checkpoint was written against evidence that does not reach "
            "Case A, so it does not emit a generalized IF3 automatically; the emission "
            "path must be implemented and reviewed first.")
    if not units["passed"]:
        raise SystemExit("STOP: G2-U raw/internal unit equivalence failed; T-008 cannot close")

    failed = [code for code, _, ok in gates if not ok]
    classic_rel = classic_path.relative_to(REPO_ROOT).as_posix()

    # ------------------------------------------------------------------ render
    L = []
    W = L.append
    W("# Q2 final closure: generalized-law decision and final IF3")
    W("")
    W("Generated by `scripts/q2_final_closure.py`. Do not edit by hand.")
    W("")
    W("## Decision")
    W("")
    W("**Generalized quality-aware IF3: NOT ADOPTED.** The classic N-D IF3 is the")
    W("final, canonical T-008 scaling interface for downstream use.")
    W("")
    W("Reasons, each computed below:")
    W("")
    reasons = []
    if not mapping_established:
        reasons.append(
            "**No first-party mapping binds the candidate's quality axis to IF1's.** The "
            "candidate's Q is B7's `Q_score`; the only real quality any downstream task can "
            "supply is IF1's Q, a relative midrank score whose pooled reference is "
            + fmt(acc["if1_pooled_q"]) + " by construction. The binding guard refuses the "
            "pairing (" + mapping_note + "). This is a v4 STOP condition for the generalized "
            "route; it does not affect the classic IF3.")
    if failed:
        reasons.append("**Adoption gate(s) failed: " + ", ".join(failed) + ".** Details below.")
    for i, text in enumerate(reasons, 1):
        W(str(i) + ". " + text)
    W("")
    W("Adoption rule, fixed in the script before any fit ran: adopt only if GQ1-GQ5")
    W("and GQ7 all pass **and** a first-party mapping binds the quality axis. GQ6 is a")
    W("requirement on an emitted object, not evidence, and is reported for completeness.")
    W("")

    W("## Accepted T-007 interfaces consumed")
    W("")
    W("Both objects are the producer's handoff bytes, installed without reserialisation.")
    W("Expected hashes are read from the tracked accepted summaries, not typed here.")
    W("")
    W("| Interface | SHA-256 | Contract | Scope |")
    W("| --- | --- | --- | --- |")
    W("| IF1 | `" + acc["if1_sha"] + "` | validate PASS | " + str(len(acc["if1_domain_q"]))
      + " quality domains; mapped mass " + fmt(acc["if1"].coverage_fraction, 10) + "; "
      + str(len(acc["if1_mapped"])) + " mixture domains mapped, " + str(len(acc["if1_unmapped"]))
      + " unmapped |")
    W("| IF2 | `" + acc["if2_sha"] + "` | validate PASS; 1M scope receipt PASS | fit scale "
      + acc["receipt"]["fit_scale"] + "; fit and selection "
      + "/".join(acc["receipt"]["fit_sources"]) + " only |")
    W("")
    W("IF1 indicator directions (native, before standardisation): "
      + ", ".join(k + " " + str(v) for k, v in sorted(acc["if1_directions"].items())) + ".")
    W("")
    W("IF2 retained negative evidence, carried unchanged:")
    W("")
    W("| Partition | Role | Outcome |")
    W("| --- | --- | --- |")
    W("| A6/A7 | " + acc["if2_roles"]["A6_A7"] + " | release validation passed |")
    W("| A8/A9 | " + acc["if2_roles"]["A8_A9"] + " | absolute transfer **failed**, not certified |")
    W("| A10/A11 | " + acc["if2_roles"]["A10_A11"] + " | centred normalised RMSE "
      + repr(acc["if2_nrmse"]) + " > predeclared " + fmt(acc["if2_nrmse_max"])
      + "; **failed** |")
    W("")
    W("Broad `release_pass` = " + str(acc["if2_release_pass"]).lower()
      + "; `scale_invariance_supported` = false; absolute use outside 1M: PROHIBITED;")
    W("fitted 10B/70B extrapolation: NOT RELEASED.")
    W("")

    W("## Quality-axis semantics (the load-bearing finding)")
    W("")
    W("| Axis | Definition | Observed values |")
    W("| --- | --- | --- |")
    W("| IF1 Q | " + cl.QUALITY_AXES["IF1_Q"] + " | domain Q "
      + fmt(min(acc["if1_domain_q"].values())) + " - " + fmt(max(acc["if1_domain_q"].values()))
      + "; pooled " + fmt(acc["if1_pooled_q"]) + " |")
    W("| B7 `Q_score` | " + cl.QUALITY_AXES["B7_Q_score"] + " | levels "
      + ", ".join(fmt(x) for x in sorted(frame["Q_score"].unique())) + " |")
    W("")
    W("First-party mappings declared: " + (str(len(cl.DECLARED_MAPPINGS)) if cl.DECLARED_MAPPINGS else "none")
      + ". A monotone relation, a similar numeric range or a convenient normalisation")
    W("would not establish one, so none is assumed. Consequently B7's gamma cannot be")
    W("read as an elasticity of IF1 Q, and any comparison between the two axes below")
    W("is a diagnostic alignment only.")
    W("")

    W("## Classic IF3 - canonical final interface")
    W("")
    cp = classic_payload
    W("| Property | Value |")
    W("| --- | --- |")
    W("| Path | `" + classic_rel + "` (local-only) |")
    W("| SHA-256 | `" + classic_sha + "` |")
    W("| Functional form | `" + cp["functional_form"] + "` |")
    W("| Parameters | " + ", ".join(k + " " + fmt(cp["params"][k], 6) for k in ("E", "A", "alpha", "B", "beta")) + " |")
    W("| External units | N = raw parameter count; D = raw token count |")
    W("| Validity box | N " + fmt(cp["validity_box"]["N"][0]) + " - " + fmt(cp["validity_box"]["N"][1])
      + "; D " + fmt(cp["validity_box"]["D"][0]) + " - " + fmt(cp["validity_box"]["D"][1])
      + "; Q [1, 1] = sentinel for 'no quality dimension', not a value on IF1's scale |")
    W("| Uncertainty | bootstrap unit `" + cp["bootstrap"]["unit"] + "`, "
      + str(cp["bootstrap"]["n_clusters"]) + " clusters, " + str(cp["bootstrap"]["replicates"])
      + " replicates; see `q2-uncertainty-robustness.md` for leave-one-trajectory-out and profile |")
    W("| Contract | `.validate()` PASS; schema " + cp["schema_version"] + " |")
    W("")
    W("B1 remains labelled observed by the organizer, and its loss column is")
    W("consistent with deterministic evaluation of the published law to about storage")
    W("precision. The fit therefore supports estimator/generator recovery, not precise")
    W("empirical knowledge of real scaling. Its empirical external support is B5")
    W("(median abs. rel. error " + fmt(cp["validation"]["B5_literature"]["median_abs_rel_err"])
      + ") and B4 with the overlapping Pythia rows excluded ("
      + fmt(cp["validation"]["B4_cross_family_excl_pythia"]["median_abs_rel_err"]) + ").")
    W("")

    W("## G2-U unit equivalence (hard gate)")
    W("")
    W("Internal convention derived from the column names: N_int = N_raw / "
      + fmt(units["conv"].s_n) + ", D_int = D_raw / " + fmt(units["conv"].s_d)
      + ". Tolerance " + fmt(un.INVARIANCE_RTOL) + " (justified in `src/scaling/units.py`).")
    W("")
    W("| Object | Points compared | Max rel. prediction difference | Param round trip | Box round trip | Result |")
    W("| --- | ---: | ---: | ---: | ---: | --- |")
    for label, inv, rt in (("B7 candidate (fitted in billions)", units["inv_c"], units["rt_c"]),
                           ("Classic IF3 (serialised raw)", units["inv_k"], units["rt_k"])):
        W("| " + label + " | " + str(inv["points"]) + " | " + fmt(inv["max_rel_error"], 3)
          + " | " + fmt(rt["param_max_rel_error"], 3) + " | " + fmt(rt["box_max_rel_error"], 3)
          + " | " + verdict(inv["pass"] and rt["pass"]) + " |")
    W("")
    W("Points: every validity-box corner, a deterministic 4-per-axis interior grid,")
    W("and accepted benchmark points (the substitution evaluation points for the")
    W("candidate; every B4 and B5 row for the classic law). The serialised classic")
    W("validity box equals B1's own range in raw counts: " + verdict(units["serial_raw"]) + ".")
    W("**G2-U: PASS.**")
    W("")

    W("## Generalized candidate on B7")
    W("")
    W("Form `L = E + A N^(-alpha) + B (Q^gamma D)^(-beta)`, fitted on B7 in billions.")
    W("B6 is contained in B7 with bit-identical losses: " + verdict(b6_subset)
      + " (so B6 adds no independent evidence).")
    W("B8 is never read by any fit in this script.")
    W("")
    fp = cand["fit"].params
    W("| Parameter | Estimate (internal units) | Bounds | Bound status | Distance to nearest bound (fraction of span) |")
    W("| --- | ---: | --- | --- | ---: |")
    for k in ("E", "A", "B"):
        W("| " + k + " | " + fmt(fp[k], 6) + " | positive by parameterisation | - | - |")
    for k, b in (("alpha", EXPONENT_BOUNDS), ("beta", EXPONENT_BOUNDS), ("gamma", GAMMA_BOUNDS)):
        W("| " + k + " | " + fmt(fp[k], 6) + " | [" + fmt(b[0]) + ", " + fmt(b[1]) + "] | "
          + cand["status"][k] + " | " + fmt(cand["distance"][k], 3) + " |")
    W("")
    W("Implied quality elasticity of the data term, gamma * beta = " + fmt(fp["gamma"] * fp["beta"])
      + ". The fit does not reproduce B7 to its storage precision (see")
    W("`q2-quality-data-audit.md`), so this is an approximation under the current fit,")
    W("not a recovered generator constant.")
    W("")

    W("### Leave-one-Q-level-out (GQ3 and GQ4)")
    W("")
    W("| Held-out Q | Rows | RMSE log L, candidate | RMSE log L, no-Q baseline | gamma | beta | gamma bound |")
    W("| ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for f in cand["folds"]:
        W("| " + fmt(f["level"]) + " | " + str(f["rows"]) + " | " + fmt(f["rmse_c"]) + " | "
          + fmt(f["rmse_b"]) + " | " + fmt(f["gamma"]) + " | " + fmt(f["beta"]) + " | " + f["bound"] + " |")
    W("")
    W("Pooled over all held-out rows: RMSE(log L) candidate " + fmt(cand["rmse_c"])
      + " vs baseline " + fmt(cand["rmse_b"]) + " (error reduction " + fmt(cand["reduction"]) + ");")
    W("median abs. rel. error " + fmt(cand["mre_c"]) + " vs " + fmt(cand["mre_b"]) + ".")
    W("This measures approximate usefulness **inside a semi-synthetic table**; it does")
    W("not convert B7 into observed evidence about real models.")
    W("")
    W("### Profile of gamma (GQ4)")
    W("")
    W("| gamma / gamma_hat | gamma | Objective / minimum | beta re-optimised | gamma * beta |")
    W("| ---: | ---: | ---: | ---: | ---: |")
    for r in cand["profile"]:
        W("| " + fmt(r["gamma"] / fp["gamma"], 3) + " | " + fmt(r["gamma"]) + " | " + fmt(r["ratio"])
          + " | " + fmt(r["beta"]) + " | " + fmt(r["gamma_times_beta"]) + " |")
    W("")
    g_vals = [r["gamma"] for r in cand["profile"]]
    gb_vals = [r["gamma_times_beta"] for r in cand["profile"]]
    b_vals = [r["beta"] for r in cand["profile"]]
    beta_falls = all(b_vals[i] >= b_vals[i + 1] for i in range(len(b_vals) - 1))
    W("Across this profile gamma spans a factor of " + fmt(max(g_vals) / min(g_vals), 3)
      + " while gamma * beta spans a factor of " + fmt(max(gb_vals) / min(gb_vals), 3)
      + (", with beta falling monotonically as gamma rises" if beta_falls else "")
      + ": the table constrains the")
    W("product - the data term's quality elasticity - far more tightly than gamma itself.")
    W("")
    lon_g = [f["gamma"] for f in cand["lon"]]
    lod_g = [f["gamma"] for f in cand["lod"]]
    W("Block-out stability of gamma: leave-one-Q-level-out range / gamma_hat = "
      + fmt(cand["loq_range"]) + "; leave-one-N-level-out " + fmt(min(lon_g)) + " - " + fmt(max(lon_g))
      + " (" + str(len(lon_g)) + " fits); leave-one-D-level-out " + fmt(min(lod_g)) + " - " + fmt(max(lod_g))
      + " (" + str(len(lod_g)) + " fits). Every block-out gamma interior: " + fmt(cand["all_interior"]) + ".")
    W("")

    W("## Q(p) and residual composition at 1M")
    W("")
    W("Q(p) is built only from the A16 mapping and IF1's values: the mapped-mass")
    W("conditional mean of the mapped domains' Q. It is undefined, never imputed, where")
    W("mapped mass is zero. Only the A4 fitting partition is read; no held-out partition")
    W("enters, and IF2 is evaluated only at its released 1M scale.")
    W("")
    W("Designs: " + str(comp["designs"]) + " (A4); zero mapped mass, Q(p) undefined: "
      + str(comp["zero_mass"]) + "; used: " + str(comp["used"]) + ". Mean mapped mass "
      + fmt(comp["mass_mean"]) + "; Q(p) range " + fmt(comp["q_range"][0]) + " - " + fmt(comp["q_range"][1]) + ".")
    W("The consumer's IF2 evaluator reproduces the producer's own predictor to a")
    W("maximum absolute difference of " + fmt(comp["producer_max_abs_diff"], 3) + " over all "
      + str(comp["targets"]) + " targets.")
    W("")
    W("| Target | R2, L ~ Q(p) | R2, L ~ Q(p) + mass | Q(p) slope | Spearman(Q(p), L) |")
    W("| --- | ---: | ---: | ---: | ---: |")
    for r in comp["per_target"]:
        W("| " + r["target"] + " | " + fmt(r["r2_q"], 3) + " | " + fmt(r["r2_qm"], 3) + " | "
          + fmt(r["slope"], 3) + " | " + fmt(r["rho"], 3) + " |")
    W("| **macro mean of 13 targets** | " + fmt(comp["r2_macro_q"], 3) + " | " + fmt(comp["r2_macro_qm"], 3)
      + " | " + fmt(comp["slope_macro"], 3) + " | " + fmt(comp["rho_macro"], 3) + " |")
    W("")
    W("Mean per-target share of the 1M surface's variation explained by Q(p): "
      + fmt(comp["mean_r2_q"], 3) + " (" + fmt(comp["mean_r2_qm"], 3) + " with mapped mass added).")
    W("Q(p) slope negative for " + str(comp["neg_slopes"]) + " of " + str(len(comp["per_target"])) + " targets.")
    W("")
    W("| Mapped-mass tercile | Designs | Mass range | Spearman(Q(p), macro L) | R2 |")
    W("| ---: | ---: | --- | ---: | ---: |")
    for t in comp["terciles"]:
        W("| " + str(t["k"]) + " | " + str(t["rows"]) + " | " + fmt(t["mass_lo"], 3) + " - " + fmt(t["mass_hi"], 3)
          + " | " + fmt(t["rho"], 3) + " | " + fmt(t["r2"], 3) + " |")
    W("")
    if comp["mean_r2_q"] < RESIDUAL_LARGE_BELOW_R2:
        W("**Finding.** Q(p) is **not** a sufficient summary of composition at 1M: on")
        W("average it explains " + fmt(comp["mean_r2_q"], 3) + " of a target's variation across the")
        W("fitting designs (predeclared threshold for a large residual: R2 below "
          + fmt(RESIDUAL_LARGE_BELOW_R2) + "), so most")
        W("of the frozen surface is residual composition structure that Q(p) does not capture.")
    else:
        W("**Finding.** Q(p) explains most of the frozen surface's variation across the")
        W("fitting designs (mean R2 " + fmt(comp["mean_r2_q"], 3) + ", at or above the predeclared "
          + fmt(RESIDUAL_LARGE_BELOW_R2) + ").")
    W("This is a 1M descriptive finding about the frozen surface, not evidence of")
    W("causal mediation, and not a cross-scale result.")
    W("Per-target associations are also confounded by domain matching: raising a")
    W("domain's share lowers that domain's own validation loss whatever its quality.")
    W("No 1M IF2 coefficient is exported as a cross-scale composition effect, and p")
    W("enters the final IF3 **not at all**.")
    W("")

    W("## Adoption gates")
    W("")
    W("| Gate | Criterion (predeclared) | Evidence | Result |")
    W("| --- | --- | --- | --- |")
    W("| GQ1 parameter domain | E, A, B > 0; alpha, beta, gamma strictly inside bounds; fit converged | "
      + "; ".join(k + " " + cand["status"][k] for k in ("alpha", "beta", "gamma")) + " | " + verdict(cand["gq1"]) + " |")
    d = cand["direction"]
    W("| GQ2 directional stability | dL/dQ < 0 in every cell of the usable quality table, B8 excluded | "
      + str(d["negative"]) + " of " + str(d["cells"]) + " B7 cells negative | " + verdict(cand["gq2"]) + " |")
    W("| GQ3 internal usefulness | leave-one-Q-level-out error reduction over the no-Q baseline > "
      + fmt(GQ3_MIN_ERROR_REDUCTION) + " | reduction " + fmt(cand["reduction"]) + " | " + verdict(cand["gq3"]) + " |")
    W("| GQ4 robustness / identifiability | every block-out gamma interior; profile ratio >= "
      + fmt(GQ4_PROFILE_MIN_RATIO) + " at 0.9x and 1.1x; LOQO range / gamma_hat <= " + fmt(GQ4_MAX_LOO_RELATIVE_RANGE)
      + " | interior " + fmt(cand["all_interior"]) + "; profile ratio "
      + fmt(cand["profile_at"].get(0.9)) + " at 0.9x, " + fmt(cand["profile_at"].get(1.1))
      + " at 1.1x; range " + fmt(cand["loq_range"]) + " | " + verdict(cand["gq4"]) + " |")
    W("| GQ5 real 1M consistency (diagnostic) | Spearman(Q(p), macro 1M loss) < 0 overall and in every mapped-mass tercile | overall "
      + fmt(comp["rho_macro"], 3) + "; terciles " + ", ".join(fmt(t["rho"], 3) for t in comp["terciles"])
      + " | " + verdict(comp["gq5"]) + " |")
    W("| GQ6 provenance discipline | an emitted generalized IF3 must record semi-synthetic identification | "
      + "satisfiable; nothing is emitted | not applicable |")
    W("| GQ7 validity discipline | non-empty identifying intersection, and the Q-identifying table's N-D structure "
      + "agrees with the accepted N-D law within that law's own worst external error ("
      + fmt(compat["tolerance"]) + ") in both directions | see below | " + verdict(compat["gq7"]) + " |")
    W("")
    W("GQ7 detail. Identifying intersection (raw counts): N " + fmt(compat["intersection"]["N"][0]) + " - "
      + fmt(compat["intersection"]["N"][1]) + ", D " + fmt(compat["intersection"]["D"][0]) + " - "
      + fmt(compat["intersection"]["D"][1]) + ", Q " + fmt(compat["intersection"]["Q"][0]) + " - "
      + fmt(compat["intersection"]["Q"][1]) + " on B7's axis.")
    if compat["cand_box_raw"]["D"][0] > cp["validity_box"]["D"][0]:
        W("The Q term was identified only for D >= " + fmt(compat["cand_box_raw"]["D"][0])
          + " tokens, above the classic lower bound of " + fmt(cp["validity_box"]["D"][0])
          + ", so the classic D range could not be inherited.")
    W("")
    W("| Compatibility check | Median abs. rel. error | Tolerance |")
    W("| --- | ---: | ---: |")
    W("| Accepted classic law on B7 at Q = " + fmt(compat["top_q"]) + " (" + str(compat["top_rows"])
      + " rows), where the candidate reduces to an N-D law | " + fmt(compat["classic_on_b7_top_q"]) + " | "
      + fmt(compat["tolerance"]) + " |")
    for label, value in compat["candidate_on_external"].items():
        W("| Candidate N-D component (Q = 1) on " + label + " | " + fmt(value) + " | "
          + fmt(compat["tolerance"]) + " (classic: " + fmt(compat["classic_external"][label]) + ") |")
    W("")
    W("B8 is not used for any gate. Its Q range is not included in any box.")
    W("")

    W("## B8 quarantine")
    W("")
    W("| Stratum | Rows | Cells with dL/dQ > 0 | Loss floor | Rows on the floor |")
    W("| --- | ---: | --- | ---: | ---: |")
    for stratum, qd in quarantine.items():
        W("| " + stratum + " | " + str(qd["rows"]) + " | " + str(qd["positive"]) + " of " + str(qd["cells"])
          + " | " + fmt(qd["floor"]) + " | " + str(qd["at_floor"]) + " |")
    W("")
    opposite = all(qd["positive"] == qd["cells"] for qd in quarantine.values())
    W(("B8's `Q_score` runs opposite to B7's in every audited cell." if opposite else
       "B8's `Q_score` direction is mixed across cells.")
      + " The reversal diagnostic is in `q2-quality-data-audit.md`; the semantics")
    W("remain unresolved by the available provenance. **B8 stays quarantined.**")
    W("")

    W("## Evidence hierarchy (unchanged)")
    W("")
    W("| Table | Role |")
    W("| --- | --- |")
    W("| B1 | principal fit; organizer label observed; fingerprint consistent with formula evaluation; estimator/generator recovery |")
    W("| B4, Pythia excluded | observed external validation |")
    W("| B5 | observed external validation (literature) |")
    W("| B4, Pythia included | leakage contrast only |")
    W("| B6/B7 | organizer-labelled semi-synthetic quality calibration"
      + ("; B7 contains B6 exactly" if b6_subset else "") + " |")
    W("| B8 | quarantined |")
    W("| B9 | specification / metadata, not validation |")
    W("| B10 | organizer-provided model output; cannot validate a fit trained against itself |")
    W("")

    W("## Downstream contract")
    W("")
    W("**For T-010.**")
    W("")
    W("- Canonical scaling interface: the classic IF3 at `" + classic_rel + "`, SHA-256 `" + classic_sha[:16] + "...`.")
    W("- External units: N raw parameter count, D raw token count. Never billions.")
    W("- Validity box: N " + fmt(cp["validity_box"]["N"][0]) + " - " + fmt(cp["validity_box"]["N"][1])
      + ", D " + fmt(cp["validity_box"]["D"][0]) + " - " + fmt(cp["validity_box"]["D"][1])
      + ". Anything outside is extrapolation and must be declared.")
    W("- Q dependence is **not** part of the accepted scaling law. The Q interval [1, 1] is a sentinel, not a")
    W("  quality value, and must not be read as IF1 Q = 1.")
    W("- Quality and composition information that remains available: IF1 (domain Q with its conditional")
    W("  intervals, partial mapping) and IF2 (absolute use at 1M only). Both are scenario-only inputs for")
    W("  any Q3 quality/compute trade-off; neither may be combined with the scaling law into an")
    W("  empirically validated cross-scale quality law.")
    W("- Prohibited: using IF2 outside 1M; feeding IF1 Q into B7's gamma; treating the tested quality-aware")
    W("  mathematics (`src/scaling/quality.py`) as an adopted law - it is analytical and sensitivity")
    W("  machinery only; using B8; extrapolating the classic law past its box without declaring it.")
    W("")
    W("**For T-011.**")
    W("")
    W("- Scaling predictions that may be compared with historical or frontier data: classic IF3 predictions")
    W("  in raw N and D, inside its box, carrying its interval families and the B1 provenance caveat.")
    W("- The Q-aware term is **absent** from the accepted interface; B7-based quality behaviour is")
    W("  semi-synthetic and diagnostic only.")
    W("- B8 is quarantined.")
    W("- The 1M IF2 does not establish cross-scale composition transfer (A8/A9 and A10/A11 failed).")
    W("")

    W("## Reproduction")
    W("")
    W("Environment: the declared project environment `modeling-research-2026`, invoked through")
    W("`conda run`.")
    W("")
    W("| Package | This run | Accepted T-007 runtime |")
    W("| --- | --- | --- |")
    for k in sorted(runtime_recorded):
        W("| " + k + " | " + str(runtime_here.get(k)) + " | " + str(runtime_recorded[k]) + " |")
    W("")
    W("Runtime identical to the accepted T-007 reproduction: " + verdict(runtime_same) + ".")
    W("")

    out = ensure(TABLES) / "q2-final-closure.md"
    while L and L[-1] == "":
        L.pop()
    out.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("wrote " + (out.relative_to(REPO_ROOT).as_posix() if out.is_relative_to(REPO_ROOT)
                      else out.name))
    print("decision: generalized IF3 NOT ADOPTED; failed gates: " + (", ".join(failed) or "none")
          + "; axis mapping established: " + str(mapping_established))
    print("G2-U: PASS; canonical IF3 sha256 " + classic_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
