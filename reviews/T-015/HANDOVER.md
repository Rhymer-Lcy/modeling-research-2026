# T-015 handover

| Field | Value |
| --- | --- |
| Task | T-015 — reproducible Python environment stabilization |
| Owner | M1 |
| Status | todo in `TASKS.md`; implementation complete, awaiting supervisory review |
| Timestamp | 2026-09-25T18:45:00+08:00 |
| Base | `96f3ff7` (main after the T-013 archival of `worklog/specs/T-015.md` v1; dispatch main was `191ba4e`) |
| HEAD | `67247b5` (the `environment.yml` change this package describes) |
| Branch / PR | `chore/m1-T015-pin-python-env` / Draft PR #14, base `main`; unmerged |

## Scope

Pin the declared direct scientific Python runtime to the versions that produced
the accepted T-007 and T-008 reproductions, and show that a fresh environment
created from the repository resolves that runtime and passes the accepted
read-only self-tests. Project-support work only: no scientific code, result or
dependency edge changes.

## Accepted runtime source

Both tracked reproduction records carry the same runtime dictionary, and it is
the authority for the pins:

- `results/tables/q1-reproduction.md`
- `results/tables/q2-reproduction.md`

```
{"numpy": "2.4.6", "pandas": "3.0.6", "python": "3.11.16", "pyyaml": "6.0.3", "scipy": "1.17.1"}
```

## Change

Old declaration:

```
- python=3.11
- pip
- numpy
- scipy
- pandas
- pyyaml
```

New direct pins:

```
- python=3.11.16
- pip
- numpy=2.4.6
- scipy=1.17.1
- pandas=3.0.6
- pyyaml=6.0.3
```

`pip` is left unpinned because no accepted record defines its version. Channels
are unchanged (`conda-forge`, `nodefaults`). The file's comments now say that
the pins come from the accepted reproductions and that they are not a full
platform/build-level lock. No other file declares dependencies.

## Evidence

**Clean-environment creation** (disposable name, never populated before):

```
conda env create -f environment.yml -n t015-verify -y
```

Exit 0: the exact pins solved from the declared channels. The environment was
created from `environment.yml` blob `442b515`, the committed one. Forty of its
packages were linked from the local package cache and one (`libexpat`) was
downloaded; the solve itself was fresh.

**Resolved direct runtime** (imported in the clean environment through
`conda run`; build and channel from its `conda-meta` records):

| Component | Version | conda build | Channel |
| --- | --- | --- | --- |
| Python | 3.11.16 | `hb12b558_2_cpython` | conda-forge |
| NumPy | 2.4.6 | `py311h65cb7f3_0` | conda-forge |
| SciPy | 1.17.1 | `py311h9c22a71_1` | conda-forge |
| pandas | 3.0.6 | `np2py311hd01f973_0` | conda-forge |
| PyYAML | 6.0.3 | `py311h3f79411_1` | conda-forge |

All five import. BLAS/LAPACK: `libblas`, `libcblas`, `liblapack` 3.11.0 on the
MKL variant (`11_*_mkl`), `mkl` 2026.1.0 `hac47afa_235`; no OpenBLAS present.
These are the same builds as in the accepted working environment. Across the
full package set, 40 of 41 packages match that environment in version, build
and md5. The exception is `libexpat`: 2.8.4 in the clean environment against
2.8.1 in the accepted one.

`conda list` labels SciPy as `pypi_0` in **both** environments. This is a display
artifact, not a pip install: the `.dist-info` records `INSTALLER` = `conda`,
`conda-meta` holds `scipy-1.17.1-py311h9c22a71_1`, and `conda list --explicit`
lists the conda-forge package.

**Commands actually run** in the clean environment, from the repository root:

```
conda run -n t015-verify --no-capture-output python scripts/selftest_quality.py
conda run -n t015-verify --no-capture-output python scripts/selftest_interfaces.py
conda run -n t015-verify --no-capture-output python scripts/selftest_q2_closure.py
```

| Self-test | Result | Accepted T-008 expectation |
| --- | --- | --- |
| `selftest_quality.py` | PASS 47 / FAIL 0, exit 0 | PASS 47 / FAIL 0 |
| `selftest_interfaces.py` | PASS (21 assertions), exit 0 | 21 assertions pass |
| `selftest_q2_closure.py` | PASS 73 / FAIL 0, exit 0 | PASS 73 / FAIL 0 |

None of the three scripts changed after the accepted T-008 merge (`b18967c`),
so the old counts apply unchanged.

## SciPy / L-BFGS-B runtime sanity

The original defect was scipy's L-BFGS-B dying with Windows code `0xc06d007f`
when BLAS/LAPACK resolved from another installation (`reviews/T-008/HANDOVER.md`).
In the clean environment, block [1] of `selftest_q2_closure.py` does a cold
L-BFGS-B refit of B1 through `src/scaling/law.py` and compares it with the
emitted classic IF3, and it passed. The same existing path was also run as a
read-only probe to expose the optimizer's state:

- 101 of 108 starts converged; objective `1.6978773583039564e-06`;
- relative deviation from the emitted IF3 parameters: `0.0`;
- no DLL, BLAS or LAPACK loading error and no process crash;
- the fitted parameters are bit-identical to the same probe run in the accepted
  environment.

This is runtime validation only, not a new scientific validation.

## Accepted working environment

Not mutated. It was only read (`conda list`, and imports through `conda run`).
Its explicit package list with md5s, and its `conda-meta` listing with sizes and
modification times, are byte-identical before and after this work. Its
transaction history still holds the same two entries.

## Scientific files changed

None. The branch diff against `main` is `environment.yml`,
`reviews/T-015/HANDOVER.md` and `worklog/M1.md`. Nothing under `src/`,
`scripts/`, `configs/`, `results/` or `paper/` changed, and neither did
`TASKS.md`.

## Limitations

The repository now pins the direct scientific Python runtime used by the
accepted Q1/Q2 reproduction.

This is not a full cross-platform lock of all transitive conda packages,
build strings, BLAS implementation, operating-system libraries or hardware.

Specifically:

- Transitive packages still float. `libexpat` has already drifted (2.8.1 to
  2.8.4) between the accepted environment and a fresh solve.
- Only win-64 was solved and tested, on one machine. Solvability and behaviour
  on other platforms were not checked.
- Build strings and the BLAS variant matched here because the solver chose
  them. Nothing in `environment.yml` requires them.
- `pip` is unpinned.
- The environment must still be invoked activated (`conda run` or
  `conda activate`). Pinning does not fix the DLL-search problem that
  occurs when the interpreter is called by path.
- Bit-identical L-BFGS-B output was shown on this machine only. It is not a
  claim of bitwise environment reproducibility elsewhere.

## Next action

Supervisory review of Draft PR #14 (M1 as supervisor). T-015 stays `todo`
until then, and T-010 and T-011 stay `todo` and paused until T-015 is accepted.
