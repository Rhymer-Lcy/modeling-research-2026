# AGENTS.md

Operating contract for any AI agent or automation working in this repository.
It is vendor-neutral and authoritative. Tool-specific adapters may add to it but
may not contradict it.

Read `README.md` for what the project is, this file for how to work in it, and
`TASKS.md` for what is currently owned by whom.

## 1. Before you start

1. Identify your task ID. All work is attached to a task in `TASKS.md`.
2. Read that task's row: owner, the paths it covers, and its status.
3. If no row covers what you were asked to do, stop and ask for one. Do not
   invent a task ID and do not work outside a task.

## 2. Ownership

**One task and one path have one active owner at a time.** The `Owner` column in
`TASKS.md` is the only record of who that is.

- You act on behalf of the owner of your task, and only within the paths listed
  on that task's row.
- To work on a path another member actively owns, ownership must first be
  transferred by editing `TASKS.md`, or the change must go through a pull
  request that owner reviews. There is no third route.
- Ownership transfer is a deliberate edit: change the `Owner` cell, update the
  date, and have the outgoing owner note the handoff in their worklog.
- Assignments change during the project. Re-read `TASKS.md` at the start of each
  session rather than relying on what was true last time.

## 3. Files you must not modify

- Any path owned by another active task.
- `paper/team.tex` and anything under `docs_local/`, `data_local/`, `scratch/`.
  These are local and private to each working copy.
- `paper/template/` — provisioned third-party material, not project source.
- `paper/main.tex`, `.gitignore`, `.gitattributes`, `environment.yml`, this
  file, and shared interfaces in `src/` are high-impact surfaces: propose a
  change through a pull request rather than editing directly.

## 4. Hard prohibitions

- **No secrets.** Never write a credential, token, key or password into any
  tracked file, in any form, including as an example.
- **No real identity in tracked files.** Author names, institution and any
  registration identifier belong in `paper/team.tex`, which is ignored.
- **No absolute paths.** Resolve everything through `src/paths.py` in Python and
  from the script's own location in PowerShell. A path naming a drive letter or
  a user directory must never appear in committed source.
- **No unapproved deletion.** Do not delete files outside your task's paths. If
  something looks redundant, report it; do not remove it. Show what you intend
  to delete before deleting it.
- **No third-party code copied into `src/`.** Reference material under
  `docs_local/` is for reading. Copying it into the project is plagiarism and a
  licensing problem, not reuse. Cite it in the manuscript instead.
- **No co-author trailers** in commit messages.

## 5. Code rules

- Python code resolves paths through `src/paths.py`.
- Seeds and shared constants come from `configs/`; do not hard-code a value that
  affects a reported result.
- `src/` holds importable modules with no side effects on import. `scripts/`
  holds entry points that produce artifacts.
- A script that draws random numbers must set the seed from the config and print
  the seed it used.
- Identifiers and comments in English. Chinese is acceptable where it genuinely
  improves clarity.

## 6. Generated files

- `results/figures/` and `results/tables/` hold small artifacts the manuscript
  cites. Everything there must be regenerable by a script in `scripts/`.
- If the manuscript does not reference it, it does not belong in `results/`.
  Exploratory output, sweeps and intermediate arrays go to `scratch/`.
- The manuscript reads generated figures from `results/figures/` in place. Never
  copy one into `paper/`; a second copy will drift.
- Input data is never committed. It lives under `data_local/`, and
  `data_local/raw/` is treated as read-only.

## 7. Validation before you report work as done

All of the following must hold, and you must have actually run them:

1. The script you changed runs from a clean state and produces its artifact.
2. Any figure or table you touched regenerates.
3. If you touched `paper/`, the manuscript builds via `scripts/build_paper.ps1`
   with no `Missing character` warning.
4. `scripts/check_public_safe.ps1 -Mode PreCommit` passes.

Do not report a task as done on the strength of inspection alone when an
executable check is available. If a check fails, report the failure; never
weaken the check to obtain a pass.

Verify the manuscript by looking at rendered pages. Text extracted from the
built PDF is unreliable for Chinese characters.

## 8. Worklog

Append one block to your member's file in `worklog/` for each task you advance.
Do not edit another member's file. The schema is at the top of each file.

Record effort as approximate active time at half-hour granularity. Hours, commit
counts, lines changed, and prompt or token counts are not contribution scores.

When a task used AI assistance, record which tool and, in the same line, how the
output was validated. The validation clause is the part that matters: the human
owner of the task remains its author and is accountable for the result.

## 9. Git discipline

Commit subject, one line, ASCII, at most 72 characters including the task ID:

```
type(scope): lowercase imperative [T-0xx]
```

- `type`: `feat`, `fix`, `exp`, `paper`, `docs`, `data`, `refactor`, `chore`
- `scope`: the directory the change belongs to
- One conceptual change per commit.
- No `update`, `final`, `misc`, `test123` style subjects, and no committing
  broken unrelated work.
- Never force-push `main`.

### Author email: required before your first commit

Git author metadata is permanent and public. It cannot be corrected later
without rewriting history, so this must be done **before** you commit anything.

1. Obtain your GitHub-provided noreply address from your own GitHub account
   (Settings, Emails). Do not ask anyone else for it and do not guess it.
2. Set it for this repository only:

   ```
   git config --local user.email "<your-github-noreply-address>"
   ```

3. Verify it:

   ```
   git config --local --get user.email
   ```

4. Confirm the value ends with `@users.noreply.github.com`.

`scripts/check_public_safe.ps1 -Mode PrePush` checks every author and committer
address in reachable history against `configs/git-email-policy.txt` and rejects
any address that no rule there permits. The GitHub noreply suffix is an
approved rule, so following the four steps above is always sufficient.

The gate exists to stop an unapproved mailbox from being published by accident,
not to forbid an address whose owner has deliberately chosen to publish it.
Publishing any other address therefore requires adding it to that tracked
policy file in a reviewable commit, so it can never happen silently. Note that
a squash or rebase merge performed on the GitHub side is authored from the
account's public profile email and committed by GitHub's web-flow bot, so those
addresses must be approved in the policy file for server-side merges to pass.

Routing:

| Change | Route |
| --- | --- |
| A path your task actively owns | Commit directly to `main` |
| Shared or high-impact surface | Short-lived branch, then pull request |
| A path another member actively owns | Transfer ownership, or pull request they review |

Branch names, when a branch is used: `type/m<n>-T0xx-short-slug`.

## 10. Time

Project dates and timestamps use UTC+8 (`Asia/Shanghai`). Write a date as
`YYYY-MM-DD` and a timestamp as ISO 8601 with an explicit offset. Do not trust a
machine's local clock to be in the project's zone; convert explicitly.

## 11. Scope

Do the task you were given. If you find a real problem outside your task's
paths, report it in your worklog and in `TASKS.md` rather than fixing it
silently in the same change.
