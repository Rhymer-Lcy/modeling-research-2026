# T-014 handover

| Field | Value |
| --- | --- |
| Task | T-014 |
| Owner | M1 |
| Status | review |
| Timestamp | 2026-09-23T14:20:00+08:00 |
| Base | `345bf97` (main) |
| HEAD | `b00c963` |
| Branch / PR | `chore/m1-T014-format-conformance` |

## Scope

Ingest the organizer's official 2026 manuscript-format sources, archive them as
local-only material with proven integrity, audit this repository's LaTeX
implementation against them, and make only the corrections the official
material requires.

T-014 is infrastructure and manuscript conformance. It is deliberately outside
the Problem-F scientific dependency graph and does not block T-007, T-008 or
T-009. No scientific path was touched.

## Completed work

- Both organizer originals archived under the git-ignored local area with
  byte-for-byte integrity proven, and removed from the repository root.
- A requirement-by-requirement conformance matrix, `paper/FORMAT_2026.md`,
  covering 19 requirements: 14 already compliant, 5 non-compliant and fixed.
- A tracked 2026 compatibility layer, `paper/format_2026.tex`, loaded after the
  third-party class. The class itself remains ignored and unmodified.
- The structural Q4 section, wired after Q3 and before validation.
- The tracked book reference given the page range the specification requires.

## Evidence

**Source archive (local-only, never tracked)**

`docs_local/gmcm-2026/source/`

| Canonical name | SHA-256 | Bytes |
| --- | --- | --- |
| `paper_format_specification.official.docx` | `46d2e2a87e90608ace764203d5326d7c7e41f01a5eb79986724a6f159fd70e16` | 93167 |
| `paper_template.official.doc` | `195b06cf670ec1aeb796bfd07e6d3e98e36d16db119308dcf4d0756319fe2e29` | 894976 |

Hashes were computed at the source, again at the destination, required equal
before the root copies were deleted, and recomputed after deletion. A derived
PDF of the template is under `docs_local/gmcm-2026/audit/`, labelled derived;
the canonical original's hash was re-checked after that conversion and was
unchanged. Provenance and the authority classification are in
`docs_local/gmcm-2026/source/PROVENANCE.md`.

**Tracked code and documents**

- `paper/format_2026.tex`
- `paper/main.tex`
- `paper/FORMAT_2026.md`
- `paper/sections/05-4-model-q4.tex`
- `paper/references.bib`
- `worklog/specs/T-014.md`
- `TASKS.md`

**Commands actually run**

```
powershell -File scripts/build_paper.ps1 -Clean
powershell -File scripts/check_public_safe.ps1 -Mode PreCommit
powershell -File scripts/check_public_safe.ps1 -Mode PrePush
git diff --check
```

The build exits 0, writes `paper/build/main.pdf`, and reports no
`Missing character` warning. The safety gate passes in both modes. `git diff
--check` reports nothing.

## Key results

The five non-compliances found and fixed:

1. **A table of contents sat between the abstract and the body**, pushing the
   body one page later than the rule allows. Removed from the competition
   build.
2. **Body pages carried a running header** holding the current section name.
   The specification forbids a running header.
3. **Body page numbers were printed in the top-right corner**, not centred in
   the footer.
4. **Line spacing was 1.38**, not single.
5. **The tracked book reference carried no page range**, which the
   specification requires of book citations.

Two findings needed judgement and are argued in `paper/FORMAT_2026.md`:

- **The stale asset was not the one expected.** The pinned class's title asset
  was suspected of naming the previous competition edition. Rendered and read,
  it names the correct 2026 edition, so it was left alone. The defect is in the
  neighbouring logo asset, which shows the **previous** edition's host
  university **and** carries an invisible text layer naming the previous
  edition plus duplicate identity labels. Extraction of the built manuscript
  reported the wrong edition while the visible cover was correct. Established
  empirically by building two minimal documents that each included exactly one
  asset. Clipping would hide the seal but not the text layer, and the asset is
  ignored third-party material that must not be edited in place, so the logo
  row is dropped by a loudly-failing patch. After the change the built PDF's
  text layer contains no competition-edition string at all.
- **The official template numbers its cover `0`; the specification says
  numbering starts at 1 on the abstract page.** The class already leaves the
  cover unnumbered and starts the abstract at 1, satisfying the textual rule,
  so the template's incidental `0` was deliberately not imitated.

## Validation

Every page of the built PDF was rendered to an image and inspected. Confirmed
visually: cover carries the correct 2026 edition and no page number; abstract
page is numbered `1` centred in the footer; the body begins on the immediately
following page; page numbers run `1,2,3,4` consecutively, all centred in the
footer; no page carries a running header; level-1 headings are centred Heiti;
body text is single spaced; no clipping, overlap or misplaced footer.

Checks that actually failed during this task, and were fixed rather than
loosened:

- A first pass of the machine-path scanner was **mutation-tested against a
  string known to contain a drive letter and did not detect it** — the shell
  escape layer had collapsed a character class so it matched only forward
  slashes. The scanner was rewritten and re-mutation-tested before any clean
  result from it was believed.
- Adding the required page range to `references.bib` **broke the build**: the
  explanatory comment contained an at-sign, and BibTeX has no comment syntax,
  so it read the comment as an entry. Caught by rebuilding immediately.
- The claim that the bibliography style orders by first citation was asserted
  before being checked, and the style does contain `SORT`. It was then verified
  with a two-entry fixture in which the author sorting last alphabetically was
  cited first and received `[1]`. The matrix now cites that test rather than an
  assumption about the style's internals.

Chinese text extraction was **not** used as visual verification. During this
task the extracted text of the abstract page was mojibake while the page
rendered correctly, and separately the extracted text named a competition
edition the visible cover did not show.

## Interfaces and downstream impact

No interface object is produced or consumed. No scientific path, raw data, or
result was touched, and the ownership and status of T-007, T-008 and T-009 are
unchanged.

Downstream manuscript work can now rely on: a build whose pagination,
headers, spacing and headings conform to the 2026 specification; a Q4 section
already wired in the right position; and `paper/FORMAT_2026.md` as the record
of which requirements are enforced by the class and which by the override.

It must **not** rely on the cover carrying a logo row — see the limitation
below.

## Deviations from plan

The task anticipated a stale **title** asset and a possible need to render the
2026 competition title from LaTeX. Inspection showed the title asset is already
correct for 2026, so under the minimal-implementation principle it was left
untouched and no LaTeX title was written. The real defect was in the logo
asset, which the plan did not anticipate.

The task also expected the class to be already compliant on headers and
pagination. It is not; both were non-compliant and were fixed.

## Known limitations and open risks

1. **The competition cover now carries no logo row.** This is a visible
   deviation from the official template. The organizer's 2026 logo row cannot
   be redistributed through this repository, and displaying the previous host
   university would be a factual error on a 2026 submission, so omission is the
   least-wrong option available — but a reviewer may prefer a manually supplied
   2026 logo row placed in local-only space. The choice is left open.
2. **Journal and web reference formats are unverified.** The bibliography holds
   one book entry, so only the book pattern was exercised against a rendered
   example.
3. **Decorative label fonts are a recorded discrepancy, not a resolved one.**
   The template sets the cover and abstract labels in a decorative face while
   the specification says other Chinese text is small size 4 Songti. The class
   follows the template; this was left as-is and documented.
4. **Abstract length and content requirements are structural only** at this
   stage. Whether the finished abstract stays within two pages and covers every
   prescribed element is a content-time check owned by T-012.
5. The conformance matrix reflects the class at its **currently pinned**
   revision. The logo patch fails loudly if that revision changes, but the rest
   of the matrix would need re-auditing.

## Next action

M1 merges this branch to `main` after review, then proceeds to T-008. Item 1
above is the only open decision and does not block the merge.
