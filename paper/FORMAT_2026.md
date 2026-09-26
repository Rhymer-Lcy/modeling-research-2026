# 2026 manuscript-format conformance

Requirement-by-requirement audit of this repository's LaTeX build against the
organizer's official 2026 manuscript-format material.

## Source authority

1. the organizer's 2026 **textual manuscript-format specification** — normative
   for typography and pagination;
2. the organizer's 2026 **Word manuscript template** — authoritative for
   structural and layout intent that the textual specification does not
   contradict;
3. this repository's tracked manuscript policy;
4. the third-party `gmcmthesis` document class — an implementation mechanism
   only, and **not** authoritative where it conflicts with 1-2.

Both official files are archived, with SHA-256 and byte size verified, under
the git-ignored local area `docs_local/gmcm-2026/source/`, together with a
provenance record. They are never tracked, converted in place, or redistributed
through this repository. Requirements below are **paraphrased**, not copied.

Where the class already satisfies a requirement it is left alone. Overrides are
concentrated in `paper/format_2026.tex`, loaded after the class, so the
third-party class stays ignored and unmodified.

## Conformance matrix

| # | Requirement | Official source | Current LaTeX behaviour | Status | Implementation decision | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Title, abstract and keywords appear on the abstract page | spec text | `\makenametitle` renders title, 题目, 摘要 and 关键词 on one page | compliant | none | rendered page 2 inspected |
| 2 | The page after the abstract page begins the body | spec text | a table of contents sat between them, pushing the body one page later | **non-compliant** | removed `\tableofcontents` from the competition build in `main.tex` | rendered page 3 is 问题重述 |
| 3 | Numbering starts on the abstract page at Arabic 1 | spec text | class sets `\setcounter{page}{1}` on the abstract page; cover is `\thispagestyle{empty}` | compliant | none | rendered page 2 shows 1; cover unnumbered |
| 4 | Page numbers centred in the footer | spec text | body pages printed the number in the **top right** | **non-compliant** | redefined `\ps@plain` to an empty head and a centred foot | every rendered page inspected |
| 5 | No running header | spec text | body pages carried a running header holding the section name | **non-compliant** | same `\ps@plain` redefinition; `\pagestyle{plain}` asserted at `\begin{document}` | every rendered page inspected |
| 6 | No identity marker inside the paper body | spec text | identity appears only on the cover, from the ignored `paper/team.tex`; a tracked placeholder file is used otherwise | compliant | none | rendered body pages carry no identity |
| 7 | Paper title: Chinese size 3, Heiti | spec text | `\zihao{3}\heiti` on the title field | compliant | none | class source plus rendered page 2 |
| 8 | Level-1 headings: Chinese size 4, Heiti, centred | spec text | `\zihao{4}\heiti` with `\centering` | compliant | none | class source plus rendered pages 3-5 |
| 9 | Other Chinese body text: small size 4, Songti | spec text | class loads `ctexart` with `zihao=-4`; Songti is the ctex default body family | compliant | none | rendered body text |
| 10 | Single line spacing | spec text | class sets `\baselinestretch` to 1.38 | **non-compliant** | `\singlespacing` (the class already loads `setspace`) | rendered line pitch compared before and after |
| 11 | Abstract covers modelling idea, methods, models, results and conclusions, innovations, keywords | spec text | placeholder abstract already has this shape | compliant (structure) | none — content is owned by T-012 | rendered page 2 |
| 12 | Abstract normally at most two pages | spec text | placeholder abstract is well under one page | compliant | none; a content-time constraint | rendered page 2 |
| 13 | No English translation of the abstract required | spec text | none present | compliant | none | rendered page 2 |
| 14 | Bracketed numeric citations in the text | spec text | `natbib` with the `numbers` option and the `gmcm` style yields `[1]` | compliant | none | rendered page 3 shows `[1]` |
| 15 | References ordered by first citation | spec text | `gmcm.bst` numbers by first citation, not alphabetically | compliant | none | two-entry fixture: an author sorting last alphabetically, cited first, received `[1]` |
| 16 | Book citations include page information | spec text | the placeholder book entry carried no page range, so the rendered reference omitted it | **non-compliant** | added a `pages` field to the tracked example, and a note in `references.bib` that book entries must carry one | rendered reference now reads `... Press, 127-134, 2004.` |
| 17 | Book / journal / web reference formats | spec text | `gmcm.bst` renders the prescribed field order for books | compliant | none; journal and web entries are not yet exercised | rendered reference compared with the specification's pattern |
| 18 | Cover shows the correct 2026 competition edition | Word template, and the cover of the spec document | the class's title asset **does** carry the correct 2026 edition | compliant | none — see ambiguity A below for the asset that was not; the 2026 logo row is covered in the section below | title asset rendered and read directly |
| 19 | Four-question manuscript structure | problem statement | `main.tex` wired Q1-Q3 only | **non-compliant** | added `paper/sections/05-4-model-q4.tex`, wired after Q3 and before validation | rendered page 4 shows section 8 问题四 |

## 2026 update: the cover logo row (T-012 v3)

The findings below are the historical T-014 record. One of their consequences
has since changed; the full comparison is in `paper/TEMPLATE_DECISION_2026.md`.

- **Historical T-014 finding (still true):** the class's own logo asset is
  stale and carries a hidden stale text layer, so it is never drawn.
- **New evidence:** the four images of the official 2026 cover row were
  extracted from the organizer's Word template itself — two byte-identical to
  the embedded images, the sponsor mark as its exact embedded stream, the
  host-university seal as a lossless crop of the embedded composite. They show
  the 2026 host and carry no text layer. They are organizer material and stay in
  the git-ignored `docs_local/gmcm-2026/cover-assets/`.
- **Selected implementation:** `paper/format_2026.tex` now replaces the stale
  class row with the official row when all four local images are present, and
  with **no row** otherwise, logging a warning. Rendered at 300 dpi, the row's
  logo positions agree with the official cover within 0.7 mm and its widths
  within 1.4 mm. `scripts/build_paper.ps1 -Submission` exits non-zero (the PDF
  is still written, for inspection only) when the row is missing or its images
  do not match their pinned hashes, when real cover identity is absent, when
  SimSun or SimHei is not embedded, when the PDF title/author metadata are not
  empty, or when a reference is undefined.

Retained ambiguity 1 below is therefore resolved for a local submission build.
A clean public clone still builds without the row, and says so.

## Findings that required judgement

### A. The cover logo row was stale, and carried a hidden stale text layer

The session began from the expectation that the pinned class's **title** asset
would be stale. It is not: rendered and read directly, it shows the correct
2026 edition, so it was left alone under the minimal-implementation principle.

The defect is in the neighbouring **logo** asset, and it is worse than a stale
picture:

- its host-university seal is the **previous** edition's host, whereas the
  organizer's 2026 template shows this year's host university;
- it carries an **invisible text layer**. The seal art is what renders, but the
  asset also contains selectable text naming the **previous** edition of the
  competition plus a duplicate set of identity labels. Extracting the text of a
  manuscript built with it therefore reported the wrong competition edition
  while the visible cover was correct.

This was established empirically, by building two minimal documents that each
included exactly one of the two assets and extracting the text of each.

Clipping the asset would hide the wrong seal but not the text layer, because
clipping is a visual operation and leaves the text operators in the content
stream. The asset is third-party and git-ignored, so editing it in place is
also excluded.

**Decision.** The logo row is dropped from the cover, by patching the class's
cover macro from `paper/format_2026.tex`. The patch fails loudly if the
expected call is not found, so a future class revision cannot silently restore
the stale asset.

**Consequence, recorded rather than hidden.** The competition cover now carries
no logo row. The organizer's own 2026 logo row cannot be redistributed through
this repository, and showing the previous host's seal would be a factual error
on the cover of a 2026 submission. Verified after the change: the built PDF's
text layer contains no competition-edition string at all.

### B. The Word template numbers its cover "0"; the specification does not

The official template's identity cover shows a centred `0` in the footer, and
its abstract page shows `1`. The textual specification says numbering **starts
on the abstract page** at Arabic 1.

Per the authority hierarchy, the explicit textual rule governs normative
pagination. The class already leaves the cover unnumbered and starts the
abstract page at 1, which satisfies the textual rule, so this was **not**
changed to imitate the template's incidental `0`.

## Retained ambiguities

1. **Cover logo row.** *Resolved for local submission builds by the 2026
   update above; kept here as the T-014 record.* Finding A above. Omission is the least-wrong option
   available under the redistribution constraint, but it is a visible deviation
   from the official template's cover, and a reviewer may prefer a manually
   supplied 2026 logo row placed in local-only space. That choice is left open
   rather than guessed.
2. **Decorative label fonts.** The official template sets the cover and
   abstract labels (题目, 摘要, 关键词) in a decorative face, while the textual
   specification says other Chinese characters are small size 4 Songti. Read
   strictly the two disagree. The specification's sentence is most naturally
   read as governing body text rather than the template's own structural
   labels, and the class follows the template here. Left as the class has it,
   and recorded as a discrepancy rather than silently normalised.
3. **Journal and web reference formats.** Requirement 17 is only exercised for
   a book entry, because the bibliography currently holds one. The journal and
   web patterns are unverified against a rendered example.

## Effect on the build

The placeholder manuscript went from 8 pages to 5. Two of those pages were the
removed table of contents; the rest follows from single line spacing. The
decomposition beyond that was not measured separately and is not claimed.

## Reproducing this audit

```powershell
powershell -File scripts/build_paper.ps1 -Clean
```

Then render `paper/build/main.pdf` to page images and inspect every page.
Chinese text extraction from the PDF is **not** a substitute: during this audit
the extracted text of the abstract page was mojibake while the page itself
rendered correctly, and separately the extracted text reported a competition
edition that the visible cover did not show. Both were resolved by looking at
rendered images, not by parsing.
