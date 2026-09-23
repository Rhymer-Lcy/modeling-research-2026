# modeling-research-2026

A three-person mathematical modeling research project. The repository holds the
manuscript source, the code that produces the results, and the records that make
both reproducible and auditable.

## Repository map

| Path | Contents |
| --- | --- |
| `paper/` | LaTeX manuscript. `main.tex` is wiring only; prose lives in `paper/sections/`. |
| `src/` | Importable modules. No side effects on import. |
| `scripts/` | Command-line entry points that produce artifacts. |
| `configs/` | Seeds, shared constants, and the approved-email policy. |
| `results/` | Small, regenerable figures and tables that the manuscript cites. |
| `reviews/` | Task review packages: a concise evidence surface per task, pointing at tracked code, artifacts and commands. |
| `worklog/` | One append-only log per member. |
| `worklog/specs/` | Canonical execution specifications for formal task stages, maintained by M1. |
| `TASKS.md` | Task register and the record of who currently owns what. |
| `AGENTS.md` | Operating contract for AI agents and for anyone automating work here. |

Local-only directories are described below and are absent from a fresh clone.

## Setup

Requirements: a TeX distribution providing `xelatex` and `latexmk` on `PATH`,
and `conda`.

```
conda env create -f environment.yml
conda activate modeling-research-2026

powershell -File scripts/setup_template.ps1
powershell -File scripts/build_paper.ps1
```

`environment.yml` is the single canonical dependency definition. There is no
`requirements.txt`. Packages are added when a task first needs them, in that
task's own commit.

### The document class is provisioned, not committed

The manuscript uses a third-party LaTeX class whose redistribution terms are
unresolved, so `paper/template/` is ignored and each working copy provisions it
locally. `scripts/setup_template.ps1` fetches an explicit pinned revision; it
never fetches a moving branch tip. This is the one setup step a fresh clone
cannot skip.

## Building the manuscript

`scripts/build_paper.ps1` can be run from any working directory; it resolves
everything from its own location. Output goes to `paper/build/`, which is
ignored.

The build fails on XeLaTeX `Missing character` warnings. A glyph missing from a
font is dropped silently from the PDF, which can corrupt a formula or a numeric
value while the build still reports success.

Note that text extracted from the built PDF is not reliable for Chinese
characters, because the embedded font subset does not carry a complete
`ToUnicode` map. Verify the manuscript by looking at rendered pages, not by
grepping extracted text.

### Author identity

`paper/team.tex` holds real author details and is ignored. `paper/team.example.tex`
is tracked and holds placeholders. `main.tex` prefers `team.tex` when it exists
and falls back to the example otherwise, so a clean clone builds without any
manual file creation.

## Where things live

- Manuscript: `paper/main.tex` plus `paper/sections/*.tex`
- Generated figures and tables: `results/figures/`, `results/tables/`
- Hand-authored diagrams: `paper/figures/`
- Code: `src/` and `scripts/`

The manuscript reads generated figures directly from `results/figures/`. Never
copy a generated figure into `paper/` — a second copy will drift from the first.

## Reproducibility

- Paths are resolved through `src/paths.py`. No absolute path belongs in
  committed source.
- Seeds and shared constants live in `configs/`.
- Anything in `results/` must be regenerable by a script in `scripts/`.
- The raw data directory is treated as read-only; processed data must be
  derivable from it.
- Input data is not redistributed here. Place it under `data_local/raw/`.

## Collaboration

Tasks, owners and status live in `TASKS.md`. Each member appends to their own
file in `worklog/`.

One task or path has one active owner at a time. Ownership is transferred
explicitly by editing `TASKS.md`. Do not edit a path another member actively
owns: take ownership first, or open a pull request they review.

- Work on a path you actively own: commit directly to `main`.
- Shared or high-impact surfaces (`paper/main.tex`, `.gitignore`,
  `.gitattributes`, `AGENTS.md`, `environment.yml`, `configs/`, shared
  interfaces in `src/`): use a short-lived branch and a pull request.
- Branches are available when useful; they are not required for every task.

Commit subjects are one line, ASCII, at most 72 characters:

```
type(scope): lowercase imperative [T-0xx]
```

**Before your first commit**, set your GitHub noreply address for this
repository only, and verify it:

```
git config --local user.email "<your-github-noreply-address>"
git config --local --get user.email
```

Use your GitHub noreply address by default; the value should normally end with
`@users.noreply.github.com`. Author metadata is permanent, so this cannot be
fixed afterwards without rewriting history.

The pre-push gate rejects any author or committer address that is not
explicitly allowed by `configs/git-email-policy.txt`. A public non-noreply
address is permitted only when it has been deliberately approved in that file,
which is a reviewable change — so an unapproved mailbox cannot be published by
accident. See `AGENTS.md` for the full procedure.

AI assistance is allowed for any task. The human owner of the task remains its
author and is accountable for validating the output. How the output was
validated is recorded in the worklog entry.

Effort is recorded as approximate active time at half-hour granularity. Hours,
commit counts, lines changed, and prompt or token counts are not contribution
scores and are not used as such.

### Review packages and execution specifications

`reviews/T-0xx/HANDOVER.md` summarises a task for review: what was done, which
tracked artifacts and commands support it, and what it does not establish. It
points at evidence rather than reproducing it, so a result that already exists
under `results/` is cited, not pasted. A reviewer reads the repository, not a
report that the work is finished.

Review packages do **not** replace the local-only directories. `docs_local/`,
`data_local/` and `scratch/` stay ignored and stay local; nothing is copied out
of them into a review package, and a local input is referred to only by its
repository-relative convention such as `data_local/problem-f/raw/...`.

`worklog/specs/` holds the canonical specification of formal task stages, so a
result can be audited against the instruction that produced it. Only M1 writes
there.

When a package is required, who owns it, what may never go in it, and the
L1/L2/L3 archiving policy are all defined in `AGENTS.md`.

## Local-only directories

These are ignored and never pushed:

| Path | Contents |
| --- | --- |
| `docs_local/` | Reference material and machine-specific local notes |
| `data_local/` | Input and derived data |
| `scratch/` | Exploratory work, sweeps, dead ends |
| `paper/team.tex` | Real author details |
| `paper/template/` | Provisioned third-party document class |
| `paper/build/` | Build output |

Problem-F material supplied by the organizer is local-only and lives under
`docs_local/problem-f/` (the problem statement, the data description and the
audit record) and `data_local/problem-f/raw/` (the attachment package, treated
as read-only). None of it is redistributed here. A transitional intake
directory is ignored as well, so a re-delivery cannot be staged by accident.

## Never commit

Credentials, tokens or keys; real author or institutional identifiers; absolute
machine paths; input datasets; third-party reference material; build artifacts;
caches or virtual environments; files above a few megabytes.

`scripts/check_public_safe.ps1` enforces these before a commit and again before
a push. Run it rather than relying on inspection.
