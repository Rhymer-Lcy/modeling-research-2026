"""Self-test for the T-008 final-closure guards.

Covers the v4 guards that `scripts/selftest_quality.py` does not: classic
baseline reproduction, B8 quarantine, two-sided gamma bound detection, IF1 and
IF2 contract validation, the IF2 1M-only scope receipt, the prohibition on
cross-scale IF2 use, the IF1-Q / B7-Q axis guard, undefined Q(p) at zero mapped
mass, raw/internal unit invariance, validity-box round trip, final IF3
validation, deterministic regeneration, no raw-data writes, no held-out
partition in model selection, and the audit's handling of a failed fit.

Almost every guard is paired with a deliberately invalid fixture that must
make it fail. A guard that has never been seen to fail is weak evidence that it
can.

    conda run -n modeling-research-2026 --no-capture-output python scripts/selftest_q2_closure.py
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src import interfaces as ifc  # noqa: E402
from src.paths import ATT_A, ATT_B, PROBLEM_F_INTERFACES  # noqa: E402
from src.quality.configuration import load_settings  # noqa: E402
from src.scaling import closure as cl  # noqa: E402
from src.scaling import data as bdata  # noqa: E402
from src.scaling import law  # noqa: E402
from src.scaling import units as un  # noqa: E402
from src.scaling.quality import GAMMA_BOUNDS, bound_status, fit_quality_law  # noqa: E402

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print("  PASS  " + name)
    else:
        FAILED += 1
        print("  FAIL  " + name + ("  [" + str(detail) + "]" if detail else ""))


def raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return True
    except Exception as other:  # noqa: BLE001 - a different exception is a failure
        print("        (raised " + type(other).__name__ + ": " + str(other)[:90] + ")")
        return False
    return False


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tree_digest(roots):
    """sha256 + size + mtime of every file under the given roots."""
    out = {}
    for root in roots:
        for p in sorted(Path(root).rglob("*")):
            if p.is_file():
                st = p.stat()
                out[str(p)] = (hashlib.sha256(p.read_bytes()).hexdigest(), st.st_size, st.st_mtime_ns)
    return out


def main():
    print("T-008 final-closure guard self-test")

    # ------------------------------------------------------------------ 1
    print("")
    print("[1] classic baseline reproduction")
    b1 = bdata.load_pythia_log().frame
    n = b1["N_params_B"].to_numpy(float) * 1e9
    d = b1["D_tokens_B"].to_numpy(float) * 1e9
    loss = b1["val_loss"].to_numpy(float)
    refit = law.fit_law(n, d, loss)
    emitted = json.loads((PROBLEM_F_INTERFACES / "IF3_classic.json").read_text(encoding="utf-8"))
    worst = max(abs(refit.params[k] - emitted["params"][k]) / abs(emitted["params"][k])
                for k in ("E", "A", "alpha", "B", "beta"))
    check("a cold refit of B1 reproduces the emitted classic parameters", worst <= 1e-9, worst)
    diag = law.generator_recovery_diagnostic(n, d, loss, decimals=4)
    check("B1 fingerprint still sits at the rounding quantum",
          diag["consistent_with_rounding_only"], diag["ratio_to_quantum"])

    # ------------------------------------------------------------------ 6
    print("")
    print("[6] B8 quarantine")
    b8 = pd.read_csv(ATT_B / "supplementary_NQ_experiment_large.csv")
    for stratum in ("calibrated", "extrapolated"):
        dd = cl.q_direction(b8[b8["data_type"] == stratum])
        check("B8 " + stratum + ": no cell supports dL/dQ < 0, so it cannot pass GQ2",
              dd["negative"] == 0 and dd["positive"] == dd["cells"], dd)
    closure = load_script("q2_final_closure")
    check("the closure's candidate table is B7, not B8",
          closure.QUALITY_TABLE == "supplementary_NQ_experiment_expanded.csv"
          and closure.QUALITY_TABLE != closure.QUARANTINED_TABLE)
    b7 = pd.read_csv(ATT_B / closure.QUALITY_TABLE)
    dd7 = cl.q_direction(b7)
    check("B7 passes the direction rule", dd7["negative"] == dd7["cells"], dd7)
    mutated = cl.q_direction(b7.assign(Q_score=1.1 - b7["Q_score"]))
    check("mutation: reversing B7's Q makes it fail the same rule",
          mutated["negative"] < mutated["cells"], mutated)

    # ------------------------------------------------------------------ 7
    print("")
    print("[7] gamma bound detection, both ends")
    lo, hi = GAMMA_BOUNDS
    check("value on the lower bound -> lower", bound_status(lo) == "lower")
    check("value on the upper bound -> upper", bound_status(hi) == "upper")
    check("value just inside the upper tolerance -> upper", bound_status(hi - 1e-4 * (hi - lo)) == "upper")
    check("interior value -> interior", bound_status(1.19) == "interior")
    one_sided = (lambda v: "lower" if v <= lo + 1e-3 * (hi - lo) else "interior")
    check("mutation: a lower-only detector calls the ceiling 'interior'",
          one_sided(hi) == "interior" and bound_status(hi) != "interior")

    # ------------------------------------------------------------------ 9 / 10
    print("")
    print("[9, 10] accepted IF1 / IF2 contracts")
    if1, p1, sha1 = cl.load_accepted("IF1")
    if2, p2, sha2 = cl.load_accepted("IF2")
    check("IF1 hash equals the accepted summary's hash", sha1 == cl.accepted_sha256("IF1"))
    check("IF2 hash equals the accepted summary's hash", sha2 == cl.accepted_sha256("IF2"))
    bad1 = copy.deepcopy(p1)
    bad1["q_by_domain"][next(iter(bad1["q_by_domain"]))] = 1.5
    check("mutation: IF1 with Q outside [0,1] fails validate()",
          raises(ifc.InterfaceError, lambda: cl.build_interface("IF1", bad1).validate()))
    bad1b = copy.deepcopy(p1)
    bad1b["q_ci_by_domain"].pop(next(iter(bad1b["q_ci_by_domain"])))
    check("mutation: IF1 with a domain missing its interval fails validate()",
          raises(ifc.InterfaceError, lambda: cl.build_interface("IF1", bad1b).validate()))
    bad2 = copy.deepcopy(p2)
    bad2["contrast_basis"] = ""
    check("mutation: IF2 without a contrast basis fails validate()",
          raises(ifc.InterfaceError, lambda: cl.build_interface("IF2", bad2).validate()))
    check("mutation: a payload with an extra field is refused",
          raises(cl.AcceptedInterfaceError, cl.build_interface, "IF1", dict(p1, extra=1)))

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "q1-if1-summary.md"
        fake.write_text("| sha256 | " + "0" * 64 + " |\n", encoding="utf-8")
        original = cl.TABLES
        try:
            cl.TABLES = Path(tmp)
            check("mutation: bytes that differ from the accepted record are refused",
                  raises(cl.AcceptedInterfaceError, cl.load_accepted, "IF1"))
        finally:
            cl.TABLES = original

    # ------------------------------------------------------------------ 11
    print("")
    print("[11] IF2 1M-only scope receipt")
    receipt = cl.check_if2_scope(p2)
    check("accepted receipt passes", receipt["fit_scale"] == "1M")
    check("IF2 was fitted and selected on A4/A5 only", receipt.get("fit_sources") == ["A4", "A5"],
          receipt.get("fit_sources"))
    mutations = {
        "fit_scale 60M": lambda x: x.__setitem__("fit_scale", "60M"),
        "use outside 1M allowed": lambda x: x["validation"]["scope_release"]["limitations"].__setitem__(
            "absolute_use_outside_1M", "ALLOWED"),
        "scale invariance claimed": lambda x: x["validation"]["scope_release"]["limitations"].__setitem__(
            "scale_invariance_supported", True),
        "10B/70B released": lambda x: x["validation"]["scope_release"]["limitations"].__setitem__(
            "fitted_10B_70B_extrapolation", "RELEASED"),
        "A8/A9 certified": lambda x: x["validation"]["scope_release"].__setitem__(
            "a8_a9_absolute_transfer_pass", True),
        "broad release claimed": lambda x: x["validation"]["acceptance"].__setitem__("release_pass", True),
    }
    for label, apply in mutations.items():
        bad = copy.deepcopy(p2)
        apply(bad)
        check("mutation: " + label + " -> ScopeViolation", raises(cl.ScopeViolation, cl.check_if2_scope, bad))

    # ------------------------------------------------------------------ 12
    print("")
    print("[12] no cross-scale IF2 use")
    seed, settings = load_settings("mixture")
    a4 = cl.load_fitting_mixture("A4", settings["row_sum_tolerance"])
    from src.mixture.data import normalised_proportions
    p = normalised_proportions(a4)
    targets, pred = cl.if2_predict(p2, p, a4.domains, scale="1M")
    check("IF2 evaluates at 1M", pred.shape == (len(a4.indices), 13), pred.shape)
    for scale in ("60M", "1B", "10B", "70B"):
        check("IF2 refuses scale " + scale,
              raises(cl.ScopeViolation, cl.if2_predict, p2, p, a4.domains, scale=scale))

    # ------------------------------------------------------------------ 13
    print("")
    print("[13] no silent IF1-Q / B7-Q scale equivalence")
    check("identity binding is allowed", cl.bind_quality_axis("IF1_Q", "IF1_Q") == "identity")
    check("IF1 Q cannot be fed to a B7-calibrated law",
          raises(cl.UnsupportedScaleMapping, cl.bind_quality_axis, "B7_Q_score", "IF1_Q"))
    check("an unknown axis is refused",
          raises(cl.UnsupportedScaleMapping, cl.bind_quality_axis, "B7_Q_score", "B8_Q_score"))
    try:
        cl.DECLARED_MAPPINGS[("B7_Q_score", "IF1_Q")] = "fixture"
        check("mutation: the guard is exactly the declared-mapping table (a fixture entry opens it)",
              cl.bind_quality_axis("B7_Q_score", "IF1_Q") == "fixture")
    finally:
        cl.DECLARED_MAPPINGS.pop(("B7_Q_score", "IF1_Q"), None)
    check("the fixture entry was removed again", not cl.DECLARED_MAPPINGS)

    # ------------------------------------------------------------------ 14
    print("")
    print("[14] Q(p) undefined at zero mapped mass")
    mass, qp = cl.mapped_quality(p, a4.domains, if1)
    zero = mass == 0
    coverage = json.loads(
        (REPO / "results" / "tables" / "q1-a16-coverage.md").read_text(encoding="utf-8")
        .split("Per-design coverage summaries: ", 1)[1].split("\n", 1)[0])
    check("zero-mass design count equals the accepted A16 coverage record",
          int(zero.sum()) == coverage["A4"]["zero_mass_n"], (int(zero.sum()), coverage["A4"]["zero_mass_n"]))
    check("Q(p) is NaN on every zero-mass design", bool(np.all(np.isnan(qp[zero]))))
    check("Q(p) is finite wherever mass is positive", bool(np.all(np.isfinite(qp[~zero]))))
    check("mean mapped mass equals the accepted IF1 coverage fraction",
          abs(float(mass.mean()) - if1.coverage_fraction) < 1e-12, (float(mass.mean()), if1.coverage_fraction))
    mapped = [dname for dname in a4.domains if if1.mixture_to_quality.get(dname)]
    unmapped = [dname for dname in a4.domains if not if1.mixture_to_quality.get(dname)]
    probe = np.zeros((2, len(a4.domains)))
    probe[0, a4.domains.index(unmapped[0])] = 1.0
    probe[1, a4.domains.index(mapped[0])] = 0.25
    probe[1, a4.domains.index(unmapped[0])] = 0.75
    pm, pq = cl.mapped_quality(probe, a4.domains, if1)
    expect = if1.q_by_domain[if1.mixture_to_quality[mapped[0]]]
    check("an all-unmapped design gets no quality", np.isnan(pq[0]) and pm[0] == 0)
    check("a partly mapped design gets the mapped-mass conditional Q, not a diluted one",
          abs(pq[1] - expect) < 1e-15 and abs(pm[1] - 0.25) < 1e-15, (pq[1], expect))

    # ------------------------------------------------------------------ 15 / 16
    print("")
    print("[15, 16] raw/internal unit invariance and validity-box round trip")
    conv = un.convention_for_columns("N_params_B", "D_tokens_B")
    check("the internal scale is read from the column names (1e9)", conv.s_n == 1e9 and conv.s_d == 1e9)
    check("an undeclared column is refused", raises(un.UnitError, un.column_scale, "N_params_M"))
    params_int = {"E": 0.41357, "A": 0.5539, "alpha": 0.27405, "B": 2.0809, "beta": 0.069884, "gamma": 1.1887}
    box_int = {"N": [0.07, 11.97], "D": [10.0, 600.0], "Q": [0.1, 1.0]}
    pts = un.interior_points(box_int, 4)
    inv = un.invariance_check(params_int, conv, pts)
    check("candidate predictions are unit-invariant", inv["pass"], inv)
    rt = un.round_trip_error(params_int, box_int, conv)
    check("parameters and box survive internal -> raw -> internal", rt["pass"], rt)
    classic_raw = {k: float(emitted["params"][k]) for k in ("E", "A", "alpha", "B", "beta")}
    inv_k = un.invariance_check(un.params_to_internal(classic_raw, conv), conv,
                                un.interior_points(un.box_to_internal(
                                    {k: emitted["validity_box"][k] for k in ("N", "D")}, conv), 4))
    check("classic IF3 predictions are unit-invariant", inv_k["pass"], inv_k)
    wrong = dict(un.params_to_raw(params_int, conv))
    wrong["B"] = params_int["B"]                       # forgot to convert B
    pred_int = un.predict_natural(params_int, pts["N"], pts["D"], pts["Q"])
    pred_bad = un.predict_natural(wrong, pts["N"] * conv.s_n, pts["D"] * conv.s_d, pts["Q"])
    err = float(np.max(np.abs(pred_bad - pred_int) / pred_int))
    check("mutation: forgetting to convert B breaks invariance by far more than the tolerance",
          err > 1e3 * un.INVARIANCE_RTOL, err)
    bad_box = un.box_to_raw(box_int, conv)
    bad_box["D"] = list(box_int["D"])                 # forgot to convert D
    back = un.box_to_internal(bad_box, conv)
    check("mutation: a half-converted box fails the round trip",
          abs(back["D"][0] - box_int["D"][0]) / box_int["D"][0] > 1e3 * un.INVARIANCE_RTOL)
    check("a classic set rejects Q and a quality set requires it",
          raises(un.UnitError, un.predict_natural, classic_raw, [1e9], [1e10], [0.5])
          and raises(un.UnitError, un.predict_natural, params_int, [1.0], [10.0]))

    # ------------------------------------------------------------------ 17
    print("")
    print("[17] final IF3 validate()")
    def build_if3(payload):
        return ifc.IF3ScalingLaw(
            schema_version=payload["schema_version"], functional_form=payload["functional_form"],
            params=payload["params"], param_cov=payload["param_cov"], bootstrap=payload["bootstrap"],
            validity_box=payload["validity_box"], validation=payload["validation"],
            q_term_provenance=ifc.Provenance(**payload["q_term_provenance"]),
            provenance=ifc.Provenance(**payload["provenance"]))
    build_if3(emitted).validate()
    check("the canonical classic IF3 validates", True)
    check("the canonical IF3 carries raw units (N lower bound above 1e6)",
          emitted["validity_box"]["N"][0] > 1e6, emitted["validity_box"]["N"])
    check("the Q sentinel is documented in q_term_provenance",
          "SENTINEL" in emitted["q_term_provenance"]["notes"])
    bad3 = copy.deepcopy(emitted)
    bad3["bootstrap"]["unit"] = "row"
    check("mutation: a row-level bootstrap unit fails validate()",
          raises(ifc.InterfaceError, lambda: build_if3(bad3).validate()))
    bad3b = copy.deepcopy(emitted)
    bad3b["validity_box"].pop("Q")
    check("mutation: a validity box without Q fails validate()",
          raises(ifc.InterfaceError, lambda: build_if3(bad3b).validate()))

    # ------------------------------------------------------------------ 18
    print("")
    print("[18] deterministic regeneration of the closure's computations")
    sub = b7[b7["Q_score"].isin([0.3, 0.6, 0.9])]
    args = [sub[c].to_numpy(float) for c in ("N_params_B", "D_tokens_B", "Q_score", "val_loss")]
    f1, f2 = fit_quality_law(*args), fit_quality_law(*args)
    check("two cold quality fits are bit-identical", f1.raw == f2.raw)
    _, pred2 = cl.if2_predict(p2, p, a4.domains, scale="1M")
    _, qp2 = cl.mapped_quality(p, a4.domains, if1)
    check("IF2 evaluation is bit-identical across calls", pred.tobytes() == pred2.tobytes())
    check("Q(p) is bit-identical across calls", qp.tobytes() == qp2.tobytes())
    prof1 = cl.profile_gamma(*args, f1.raw, [f1.params["gamma"] * 1.1])
    prof2 = cl.profile_gamma(*args, f1.raw, [f1.params["gamma"] * 1.1])
    check("the gamma profile is bit-identical across calls", prof1 == prof2)

    # ------------------------------------------------------------------ 19
    print("")
    print("[19] no raw-data writes")
    roots = [ATT_B, ATT_A / "regmix_tables"]
    before = tree_digest(roots)
    check("the raw trees are non-empty", len(before) > 10, len(before))
    closure.composition_section(closure.accepted_interfaces())
    closure.quarantine_section()
    closure.b6_within_b7(b7)
    after = tree_digest(roots)
    check("closure sections leave every raw file byte- and mtime-identical", before == after)
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "x.csv"
        f.write_text("a\n1\n", encoding="utf-8")
        snap = tree_digest([tmp])
        f.write_text("a\n2\n", encoding="utf-8")
        check("mutation: the digest detects a modified file", snap != tree_digest([tmp]))

    # ------------------------------------------------------------------ 20
    print("")
    print("[20] no held-out partition in model selection")
    for name in ("A6", "A8", "A10", "A12", "A14"):
        check("partition " + name + " is refused by the fitting loader",
              raises(cl.ScopeViolation, cl.load_fitting_mixture, name, settings["row_sum_tolerance"]))
    check("only A4 is a fitting partition", cl.FITTING_PARTITIONS == ("A4",))

    # ------------------------------------------------------------------ audit
    print("")
    print("[audit] a failed reversal fit is never rendered as a bound verdict")
    audit = load_script("q2_audit_quality_data")

    def fake_fingerprint(label, frame):
        class F:
            n_obs = len(frame)
            params = {"gamma": 1.0, "alpha": 0.3, "beta": 0.3}
        return label, F(), {"median_abs_rel_err": 0.01, "rounding_quantum": 1e-5, "ratio": 1000.0}

    def failing_fit(*a, **k):
        raise RuntimeError("fixture: no starting point produced a finite objective")

    with tempfile.TemporaryDirectory() as tmp:
        audit.TABLES = Path(tmp)
        audit.fit_and_fingerprint = fake_fingerprint
        audit.fit_quality_law = failing_fit
        audit.main()
        text = (Path(tmp) / "q2-quality-data-audit.md").read_text(encoding="utf-8")
    flat = " ".join(text.split())
    check("a numerically failed fit is reported as FAILED", "reversed fit FAILED" in flat)
    check("and no bound verdict is drawn from it", "parked on a" not in flat)
    check("and the permitted conclusion is 'remains ambiguous'",
          "Permitted conclusion.** The result remains ambiguous" in flat)

    def broken_fit(*a, **k):
        raise NameError("fixture: a programming error")

    with tempfile.TemporaryDirectory() as tmp:
        audit.TABLES = Path(tmp)
        audit.fit_quality_law = broken_fit
        check("a programming error in the reversal path crashes instead of rendering",
              raises(NameError, audit.main))

    print("")
    print("PASS " + str(PASSED) + " / FAIL " + str(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
