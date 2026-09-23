# worklog/specs

Canonical execution specifications. Tracked and public. Maintained by M1.

## What this is for

When a task stage is handed to an assistant or automated tool, the instruction
that defined it is part of how the result came about. If that instruction
exists only in someone's chat history, the work is not reproducible by anyone
else and cannot be audited later: two members running "the same" stage may have
been asked materially different things.

This directory holds the **canonical specification** of such a stage — the
objective, the constraints, the acceptance criteria, and the prompt as issued.
It is a reproducibility and governance artifact.

It is emphatically **not** a log of every interaction with a tool, and it is
**not** a contribution measure. A long specification file means a task had many
formal stages, nothing more.

## What gets archived: L1 / L2 / L3

**L1 — local operational prompts. Archiving not required.**
Debugging, explaining an error message, adding a local unit test, formatting,
adjusting a plot, narrow questions about a piece of code. These do not change
what the project concluded, and archiving them would bury the specifications
that matter.

**L2 — formal task-stage execution. Archiving expected.**
Experiment design, implementing a substantial stage of a task, comparing
models, producing an interface object, a formal task checkpoint.

**L3 — project-level or high-impact decisions. Archiving required, M1
controls.**
Changing the mathematical architecture, changing how data is interpreted,
changing task dependencies, changing an interface, crossing another member's
owned paths, or changing a major scientific conclusion.

The boundary that matters is not prompt length. It is whether someone auditing
the project later would need the instruction to understand why the result looks
as it does.

## Rules

**Only M1 creates or updates files here.** A task owner does not rewrite the
canonical specification after executing it. If execution revealed that the
specification was wrong, that belongs in the handover under Deviations, and M1
issues a new version block — the record of what was actually asked stays
intact.

**One append-only file per scientific task**, created when formal prompts for
that task begin:

```
worklog/specs/T-007.md
worklog/specs/T-008.md
...
```

Append new version blocks; do not edit earlier ones.

**Archiving starts prospectively.** Prompts issued before this convention
existed are not reconstructed from memory: a specification written after the
fact from recollection is worse than no specification, because it looks
authoritative and is not. The worklogs remain the record of earlier activity.

**Record the outcome pointer** once it is known — the commit, the pull request
or the review package the specification produced. A specification with no
outcome is an instruction nobody can check.

## Never store here

- API keys, tokens, credentials;
- relay or endpoint URLs, account identifiers;
- balances, quotas, spend or usage figures;
- private provider or vendor arrangements;
- private conversations;
- an assistant's private reasoning;
- arbitrary exploratory prompts.

Those are operational circumstances, not reproducibility requirements, and some
of them are secrets. A generic tool or model name may be recorded when it is
methodologically relevant — for example, that a stage was run with a
reasoning-oriented model and repeated with a different one to check the result
did not depend on the tool.

## Tool neutrality

No specific commercial tool is mandatory for anyone. Members may use different
assistants, and the repository contract stays vendor-neutral. What is fixed is
that the **human owner of the task validates the result and is accountable for
it**, whichever tool produced it.

Start from `PROMPT_SPEC_TEMPLATE.md`. The full contract is in `AGENTS.md`.
