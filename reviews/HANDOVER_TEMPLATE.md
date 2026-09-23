# T-0xx handover

Copy this file to `reviews/T-0xx/HANDOVER.md` and fill it in. Delete the
guidance in parentheses as you go. Drop any section that is genuinely not
applicable rather than writing "N/A" in all of them.

| Field | Value |
| --- | --- |
| Task | T-0xx |
| Owner | M? |
| Status | todo / wip / review / done / blocked / dropped |
| Timestamp | YYYY-MM-DDTHH:MM:SS+08:00 |
| Base | (commit this work started from) |
| HEAD | (commit this package describes) |
| Branch / PR | (if one was used; omit for direct commits to main) |

## Scope

(What this task was asked to do, in two or three sentences. If the scope
changed during execution, say so here and explain why under Deviations.)

## Completed work

(What is actually finished. Not what is planned. If a part is half-built, it
belongs under Known limitations, not here.)

## Evidence

(This is the section a reviewer reads first. Everything below must be
repository-relative and must exist at the stated HEAD.)

**Code**

- `src/...`
- `scripts/...`

**Regenerable artifacts**

- `results/tables/...`
- `results/figures/...`

**Commands actually run**

```
python scripts/...
powershell -File scripts/...
```

(Only commands you ran. State what each one printed or produced, not what it is
supposed to do.)

## Key results

(Only claims the evidence above supports. A number here must be traceable to a
tracked artifact or to a command listed above. If a result is interesting but
rests on data whose provenance limits it, say so in the same sentence rather
than in a footnote.)

## Validation

(How you know the work is right, and what was checked. Name the checks that
ran and their outcome. If a check failed and you fixed it, that is worth one
line — a check that has never failed is weak evidence that it can.)

## Interfaces and downstream impact

(Which interface objects this produces or consumes, and what a downstream task
can now rely on. Also what it must NOT rely on: a validity range, a provenance
limit, a stratum that did not reconcile.)

## Deviations from plan

(Where execution differed from what was agreed, and why. Omit the section if
there were none — do not pad it.)

## Negative results and rejected alternatives

(Only when materially useful: an approach tried and abandoned for a reason the
next person would otherwise rediscover. Omit otherwise.)

## Known limitations and open risks

(What this work does not establish. What could still be wrong. What a reviewer
should be sceptical about. Understating this section is the most expensive way
to use it.)

## Next action

(The single next thing, and who owns it.)
