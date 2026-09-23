"""Self-test for the quality-aware scaling law's mathematics.

The signs and the domain boundary in `src/scaling/quality.py` are load-bearing:
a sign error in the iso-loss substitution inverts the recommendation the model
exists to make, and it inverts quietly, because the wrong answer is still a
plausible-looking number.

Every analytic derivative is therefore checked against a central finite
difference, and the final block deliberately feeds an INVALID parameter vector
to confirm the sign checks can actually fail. A check that has never failed is
weak evidence that it can.

Run from the repository root:

    python scripts/selftest_quality.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scaling.quality import (  # noqa: E402
    InfeasibleEquivalent,
    elasticities,
    equivalent_capacity,
    iso_loss_dn_dq,
    parameter_saving,
    partials,
    predict_q,
)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print("  PASS  " + name)
    else:
        FAILED += 1
        print("  FAIL  " + name + ("  [" + detail + "]" if detail else ""))


# A valid parameter vector in the log parameterisation:
# (log A, log B, log E, alpha, beta, gamma)
THETA = (np.log(400.0), np.log(410.0), np.log(1.69), 0.34, 0.28, 0.8)

# Evaluation points spanning three orders of magnitude in N and D.
N = np.array([1.0e8, 1.0e9, 1.0e10])
D = np.array([1.0e9, 1.0e10, 1.0e11])
Q = np.array([0.3, 0.6, 0.9])


def central_difference(f, x, h_rel=1e-6):
    h = np.abs(x) * h_rel
    return (f(x + h) - f(x - h)) / (2.0 * h)


def main() -> int:
    print("quality-aware scaling law self-test")
    print("")

    # ---- 1. algebraic consistency of the two written forms -----------------
    print("[1] functional form")
    a, b, e, alpha, beta, gamma = THETA
    direct = predict_q(THETA, N, D, Q)
    rewritten = (
        np.exp(e)
        + np.exp(a) * N ** (-alpha)
        + np.exp(b) * Q ** (-gamma * beta) * D ** (-beta)
    )
    check("L = E + A N^-alpha + B (Q^gamma D)^-beta equals its expanded form",
          np.allclose(direct, rewritten, rtol=1e-12),
          str(np.max(np.abs(direct - rewritten))))
    check("loss is strictly above the irreducible floor E",
          bool(np.all(direct > np.exp(e))))

    # ---- 2. monotonicity signs --------------------------------------------
    print("")
    print("[2] monotonicity in the valid parameter region")
    p = partials(THETA, N, D, Q)
    check("dL/dN < 0 (more parameters reduce loss)", bool(np.all(p["dL_dN"] < 0)))
    check("dL/dD < 0 (more tokens reduce loss)", bool(np.all(p["dL_dD"] < 0)))
    check("dL/dQ < 0 (better data reduces loss)", bool(np.all(p["dL_dQ"] < 0)))

    # ---- 3. analytic vs finite-difference derivatives ----------------------
    print("")
    print("[3] analytic derivatives against central finite differences")
    fd_n = central_difference(lambda x: predict_q(THETA, x, D, Q), N)
    fd_d = central_difference(lambda x: predict_q(THETA, N, x, Q), D)
    fd_q = central_difference(lambda x: predict_q(THETA, N, D, x), Q)
    check("dL/dN matches finite difference",
          np.allclose(p["dL_dN"], fd_n, rtol=1e-5),
          str(np.max(np.abs(p["dL_dN"] - fd_n))))
    check("dL/dD matches finite difference",
          np.allclose(p["dL_dD"], fd_d, rtol=1e-5),
          str(np.max(np.abs(p["dL_dD"] - fd_d))))
    check("dL/dQ matches finite difference",
          np.allclose(p["dL_dQ"], fd_q, rtol=1e-5),
          str(np.max(np.abs(p["dL_dQ"] - fd_q))))

    # ---- 4. elasticities are distinct quantities ---------------------------
    print("")
    print("[4] elasticities")
    el = elasticities(THETA, N, D, Q)
    check("total-loss elasticity is strictly smaller in magnitude than "
          "excess-loss elasticity (the floor E damps it)",
          bool(np.all(np.abs(el["dlogL_dlogN"]) < np.abs(el["dlogLex_dlogN"]))))
    check("excess-loss shares sum to 1",
          np.allclose(el["share_N"] + el["share_D"], 1.0, rtol=1e-12))
    check("all three log elasticities are negative",
          bool(np.all(el["dlogL_dlogN"] < 0) and np.all(el["dlogL_dlogD"] < 0)
               and np.all(el["dlogL_dlogQ"] < 0)))

    # ---- 5. iso-loss substitution sign -------------------------------------
    print("")
    print("[5] iso-loss substitution")
    dn_dq = iso_loss_dn_dq(THETA, N, D, Q)
    check("dN/dQ < 0 along iso-loss (better data needs FEWER parameters)",
          bool(np.all(dn_dq < 0)), str(dn_dq))

    # Verify it really holds the loss constant, to first order.
    base = predict_q(THETA, N, D, Q)
    dq = Q * 1e-7
    moved = predict_q(THETA, N + dn_dq * dq, D, Q + dq)
    check("moving along dN/dQ holds loss constant to first order",
          np.allclose(moved, base, rtol=1e-9),
          str(np.max(np.abs(moved - base) / base)))

    # ---- 6. parameter saving vs equivalent capacity ------------------------
    print("")
    print("[6] parameter saving and equivalent capacity")
    A = np.exp(a)
    headroom = A * N ** (-alpha)
    R = 0.25 * headroom          # comfortably inside the feasible region

    d_sub = parameter_saving(THETA, N, R)
    check("parameter saving is negative (fewer parameters needed)",
          bool(np.all(d_sub < 0)), str(d_sub))
    n_sub = N + d_sub
    check("parameter saving exactly offsets the reduction",
          np.allclose(A * n_sub ** (-alpha), headroom + R, rtol=1e-10))

    d_eq = equivalent_capacity(THETA, N, R)
    check("equivalent capacity is positive (extra parameters that would have "
          "bought the same gain)", bool(np.all(d_eq > 0)), str(d_eq))
    n_eq = N + d_eq
    check("equivalent capacity exactly reproduces the reduction",
          np.allclose(A * n_eq ** (-alpha), headroom - R, rtol=1e-10))

    # ---- 7. the feasibility boundary is a result, not a NaN ----------------
    print("")
    print("[7] equivalent-capacity feasibility boundary")
    grew = []
    for frac in (0.5, 0.9, 0.99):
        grew.append(float(equivalent_capacity(THETA, N, frac * headroom)[0]))
    check("equivalent capacity diverges as R approaches the N term's reach",
          grew[0] < grew[1] < grew[2], str(grew))

    raised = False
    try:
        equivalent_capacity(THETA, N, 1.0 * headroom)
    except InfeasibleEquivalent:
        raised = True
    check("R == A*N^(-alpha) raises InfeasibleEquivalent rather than "
          "returning NaN", raised)

    raised = False
    try:
        equivalent_capacity(THETA, N, 1.5 * headroom)
    except InfeasibleEquivalent:
        raised = True
    check("R beyond the reach also raises", raised)

    check("parameter saving remains finite past that boundary "
          "(it has no such limit)",
          bool(np.all(np.isfinite(parameter_saving(THETA, N, 5.0 * headroom)))))

    # ---- 8. mutation test: the sign checks must be able to fail -------------
    print("")
    print("[8] mutation test - feed an INVALID law and require the checks to fail")
    # gamma < 0 would mean better data increases loss. The sign check above
    # must reject it; if it does not, the check is decorative.
    bad = (a, b, e, alpha, beta, -0.8)
    bad_p = partials(bad, N, D, Q)
    check("dL/dQ > 0 is correctly detected for negative gamma",
          bool(np.all(bad_p["dL_dQ"] > 0)),
          "a negative gamma must make quality harmful, and be visible as such")
    bad_dn_dq = iso_loss_dn_dq(bad, N, D, Q)
    check("iso-loss dN/dQ flips sign for the invalid law",
          bool(np.all(bad_dn_dq > 0)),
          "if this stays negative the sign test cannot discriminate")

    # ---- 9. input validation ------------------------------------------------
    print("")
    print("[9] input validation")
    from src.scaling.quality import fit_quality_law
    raised = False
    try:
        fit_quality_law([1e9], [1e10], [0.0], [2.0])
    except ValueError:
        raised = True
    check("Q <= 0 is rejected rather than producing a complex power", raised)

    raised = False
    try:
        parameter_saving(THETA, N, -1.0)
    except ValueError:
        raised = True
    check("a negative reduction is rejected", raised)

    print("")
    print("PASS " + str(PASSED) + " / FAIL " + str(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
