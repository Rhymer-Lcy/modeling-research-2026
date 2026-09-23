# reviews

Task review and handover packages. Tracked and public.

## What this is for

A reviewer should be able to judge a task from the repository alone: from what
is committed here, what is committed under `src/`, `scripts/` and `results/`,
and what the commands in the package actually produce when run.

Without this directory the evidence for a task lives in places a reviewer
cannot reach — a chat transcript, an ignored local directory, or an assistant's
summary of its own work. None of those are reviewable. A review package is the
small tracked surface that closes that gap.

It is a **synthesis that points at evidence**, not the evidence itself. The
code is already in the repository; the artifacts are already in `results/`. The
package says what was done, what it shows, what it does not show, and how to
re-run it.

## Layout

```
reviews/
  README.md                this file
  HANDOVER_TEMPLATE.md     copy this to start a package
  T-007/HANDOVER.md        one directory per task
  T-008/HANDOVER.md
  ...
```

A task's review directory is owned by that task's **current active owner**, as
recorded in `TASKS.md`. The same ownership rule applies here as to any other
path: to write in a directory someone else owns, take ownership first or open a
pull request they review.

Empty directories are not created in advance and need no placeholder file. A
task's directory appears when it has something to hand over.

## When a package is required

- when requesting formal supervisory review;
- before a task moves to `review`;
- before a task moves to `done`;
- at a checkpoint that materially changes a downstream interface or a
  scientific conclusion.

Not for routine commits. A package per commit would make the directory a change
log, which Git already is, and would stop anyone reading it.

Update the package in place when a task reaches a new checkpoint. Git history
preserves the previous version, so do not create timestamped copies unless some
real need for one appears.

## What belongs in a package

Concise synthesis. Claims that the listed evidence supports, and no others.

Point at repository-relative paths rather than pasting their contents: if a
result already exists as a tracked artifact under `results/`, cite it instead of
reproducing the table. Commands should be repo-relative and runnable as written.

## What must never go in

- dataset copies, or any content from an ignored directory;
- secrets, credentials, tokens, keys, account identifiers, provider names,
  quotas or balances;
- real names or institutional identifiers;
- absolute machine paths — a local input is named only by its canonical
  repository-relative convention, such as `data_local/problem-f/raw/...`, never
  by drive letter;
- raw AI conversation dumps or an assistant's private reasoning;
- token counts, prompt counts or lines changed presented as contribution
  measures.

These are enforced for the whole repository by
`scripts/check_public_safe.ps1`; run it rather than relying on inspection.

## A note on what a package is evidence *of*

The reviewer evaluates the repository, not an assistant's report that the work
is finished. A task is not `done` because a tool said so. Normally completion
means implementation, a reproducible artifact where one is meaningful,
validation that was actually run, and a current package — plus the relevant
interface objects where a task produces one. A documentation-only task needs
none of the artifacts that would be meaningless for it.

The full contract is in `AGENTS.md`.
