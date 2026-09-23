"""Mutation self-test for the Problem-F interface contracts.

A validator that has never been observed to reject anything is not a validator.
Each case below breaks exactly one rule and asserts that ``validate()`` raises,
and each contract is also exercised once in a well-formed state so the tests
cannot pass merely because everything raises.

Run:  python scripts/selftest_interfaces.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.interfaces import (  # noqa: E402
    SCHEMA_VERSION,
    IF1DomainQuality,
    IF2MixtureResponse,
    IF3ScalingLaw,
    IF4LossBenchmarkBridge,
    InterfaceError,
    Provenance,
)

RESULTS: list[tuple[str, bool]] = []


def expect_raise(name: str, obj) -> None:
    try:
        obj.validate()
    except InterfaceError:
        RESULTS.append((name, True))
        print(f"  [ok]   rejected: {name}")
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False))
        print(f"  [FAIL] {name}: raised {type(exc).__name__} instead of InterfaceError")
    else:
        RESULTS.append((name, False))
        print(f"  [FAIL] {name}: accepted an object that breaks its contract")


def expect_ok(name: str, obj) -> None:
    try:
        obj.validate()
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False))
        print(f"  [FAIL] {name}: rejected a valid object ({exc})")
    else:
        RESULTS.append((name, True))
        print(f"  [ok]   accepted: {name}")


OBS = Provenance(trust="observed", sources=["A1"])


def if1(**over):
    base = dict(
        schema_version=SCHEMA_VERSION,
        quality_domains=["arxiv", "github"],
        q_by_domain={"arxiv": 0.7, "github": 0.4},
        q_ci_by_domain={"arxiv": (0.66, 0.74), "github": (0.38, 0.42)},
        n_by_domain={"arxiv": 1419, "github": 10000},
        mixture_to_quality={"arxiv": "arxiv", "freelaw": None},
        mapping_type={"arxiv": "direct", "freelaw": "inferred"},
        coverage_fraction=0.35,
        indicator_directions={"fineweb_edu": "higher_better", "ad_en": "lower_better"},
        provenance=OBS,
    )
    base.update(over)
    return IF1DomainQuality(**base)


def if2(**over):
    base = dict(
        schema_version=SCHEMA_VERSION,
        mixture_domains=["arxiv", "github", "pile_cc"],
        loss_columns=["the_pile_arxiv_val_loss"],
        contrast_basis="pile_cc",
        zero_policy="keep-raw-proportions",
        renormalisation="row-sum-to-one",
        coefficients={"the_pile_arxiv_val_loss": {"arxiv": -0.4, "github": 0.2}},
        fit_scale="1M",
        validation={"out_of_design": "A10"},
        domains_without_loss=["nih_exporter"],
        provenance=OBS,
    )
    base.update(over)
    return IF2MixtureResponse(**base)


def if3(**over):
    base = dict(
        schema_version=SCHEMA_VERSION,
        functional_form="E + A*N**-alpha + B*(Q**gamma*D)**-beta",
        params={"E": 1.8, "A": 400.0, "alpha": 0.34, "B": 410.0, "beta": 0.28},
        param_cov=None,
        bootstrap={"unit": "model", "n_clusters": 8, "replicates": 2000},
        validity_box={"N": (0.07, 11.97), "D": (0.134, 299.893), "Q": (0.1, 1.0)},
        validation={"B5": "held out"},
        q_term_provenance=Provenance(trust="semi_synthetic", sources=["B6"]),
        provenance=OBS,
    )
    base.update(over)
    return IF3ScalingLaw(**base)


def if4(**over):
    base = dict(
        schema_version=SCHEMA_VERSION,
        strata={"high": 7, "medium": 68},
        primary_stratum="high",
        form="linear-in-loss",
        params={"a": -18.0, "b": 70.0},
        prediction_error={"rmse": 4.2},
        n_anchor_models=7,
        score_scale="leaderboard-normalised-0-100",
        provenance=Provenance(trust="mixed", sources=["C6"]),
    )
    base.update(over)
    return IF4LossBenchmarkBridge(**base)


print("interface contract mutation self-test")
print()

print(" Provenance")
expect_ok("provenance with a known trust class", OBS)
expect_raise("provenance with an invented trust class",
             Provenance(trust="pretty_good", sources=["A1"]))
expect_raise("provenance naming no source", Provenance(trust="observed", sources=[]))

print(" IF1 domain quality")
expect_ok("well-formed IF1", if1())
expect_raise("quality score outside [0,1]", if1(q_by_domain={"arxiv": 1.4, "github": 0.4}))
expect_raise("domain with no interval", if1(q_ci_by_domain={"arxiv": (0.6, 0.8)}))
expect_raise("domain with no sample size", if1(n_by_domain={"arxiv": 1419}))
expect_raise("coverage fraction above 1", if1(coverage_fraction=1.2))
expect_raise("indicator direction not declared",
             if1(indicator_directions={"fineweb_edu": "probably_up"}))

print(" IF2 mixture response")
expect_ok("well-formed IF2", if2())
expect_raise("undeclared contrast basis", if2(contrast_basis=""))
expect_raise("undeclared zero policy", if2(zero_policy=""))
expect_raise("coefficients missing a non-reference domain",
             if2(coefficients={"the_pile_arxiv_val_loss": {"arxiv": -0.4}}))

print(" IF3 scaling law")
expect_ok("well-formed IF3", if3())
expect_raise("row-level bootstrap instead of model-clustered",
             if3(bootstrap={"unit": "row", "replicates": 2000}))
expect_raise("validity box missing Q", if3(validity_box={"N": (0.07, 12.0), "D": (0.1, 300.0)}))
expect_raise("quality term with an unstated provenance class",
             if3(q_term_provenance=Provenance(trust="calibrated", sources=["B6"])))

print(" IF4 loss-benchmark bridge")
expect_ok("well-formed IF4", if4())
expect_raise("primary stratum not among the strata", if4(primary_stratum="low"))
expect_raise("bridge without a prediction error", if4(prediction_error={}))
expect_raise("bridge with no anchor models", if4(n_anchor_models=0))

print()
failed = [name for name, ok in RESULTS if not ok]
# 3 provenance + 6 IF1 + 4 IF2 + 4 IF3 + 4 IF4. Asserting the count matters:
# without it, a case silently dropped from the list still reports PASS.
EXPECTED = 21
if len(RESULTS) != EXPECTED:
    print(f"RESULT: FAIL (expected {EXPECTED} assertions, ran {len(RESULTS)})")
    sys.exit(1)
if failed:
    print(f"RESULT: FAIL ({len(failed)} of {len(RESULTS)} assertions failed)")
    for name in failed:
        print(f"  - {name}")
    sys.exit(1)
print(f"RESULT: PASS ({len(RESULTS)} assertions)")
sys.exit(0)
