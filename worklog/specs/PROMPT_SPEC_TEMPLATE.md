# T-0xx execution specifications

One file per scientific task. **Append** a new version block for each formal
(L2 or L3) stage; never edit a block that has already been executed. Only M1
writes here.

---

## v1 — short title of this stage

| Field | Value |
| --- | --- |
| Task | T-0xx |
| Prompt version | v1 |
| Level | L2 / L3 |
| Issued by | M1 |
| Issued | YYYY-MM-DDTHH:MM:SS+08:00 |
| Execution role | (optional: the class of tool this is written for, e.g. a reasoning-oriented coding assistant. Omit unless it matters methodologically. Never a provider account or endpoint.) |

### Objective

(What this stage must achieve, in a few sentences. The scientific goal, not the
keystrokes.)

### Prerequisites

(What must already exist: interface objects, upstream tasks at a given status,
artifacts, local inputs named by their repository-relative convention such as
`data_local/problem-f/raw/...`.)

### Allowed paths

(The paths this stage may write. Should match the task's row in `TASKS.md`.)

### Forbidden paths and safety constraints

(What must not be touched, and any standing constraints that apply — read-only
raw data, another member's owned paths, shared surfaces that need a pull
request, checks that must not be weakened to obtain a pass.)

### Acceptance criteria

(How the result will be judged, written so that it can fail. "Runs without
error" is not an acceptance criterion. Name the check, the artifact, or the
number that has to come out right, and say what outcome would mean the stage
did not succeed.)

### Canonical execution prompt

```text
(The prompt as issued, verbatim. This is the auditable part: what was actually
asked, not a tidied-up paraphrase written afterwards.)
```

### Outcome

(Filled in once known. Point at evidence, do not summarise it.)

- Commit / PR:
- Review package: `reviews/T-0xx/HANDOVER.md`
- Result: accepted / delta specification issued as v2 / abandoned, and one line
  on why.

---

## v2 — ...

(Next block. Append; do not rewrite v1.)
