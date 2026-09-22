# CLAUDE.md

**`AGENTS.md` is authoritative and must be read first.** This file adds only
Claude-specific guidance and does not restate or override the contract there.

If anything here appears to conflict with `AGENTS.md`, `AGENTS.md` wins.

## Reading order

1. `README.md` — what the project is
2. `AGENTS.md` — how to work here, ownership, Git, validation, worklog
3. `TASKS.md` — what is currently owned by whom

## Tooling notes specific to this assistant

- **Write files with the file-writing tool, not through a shell heredoc.** A
  shell string adds escape layers, and a LaTeX or Windows path passed through
  them can silently arrive as a control character or a literal escape sequence.
  This repository is full of backslashes; use the direct file tools.
- **After editing a file that contains backslashes or whitespace literals,
  re-read the edited region in the file** rather than trusting the intended
  diff.
- **The shell tool's working directory persists between calls and drifts.** Use
  absolute invocations or `git -C <repo>` in any command whose output you intend
  to report as fact. Note that absolute paths belong in *commands*, never in
  committed source.
- **Inspect a built PDF by rendering pages to images and looking at them.**
  Structural checks and text extraction both pass on a document that is visibly
  wrong, and extraction is unreliable for Chinese here.
- **Prefer a script that asserts over a re-read that hopes.** When you add a
  check, prove it can fail before trusting it: break the input once and watch the
  check fail. A check that cannot fail is worse than no check, because it reports
  success.

## Reporting

State what you actually ran and what it returned. If a step was skipped or a
check failed, say so plainly. Do not describe work as complete on the strength
of inspection when an executable test was available.
