# 2026 LaTeX template decision

Decision record for the T-012 v3 template arbitration: the current
`gmcmthesis`-based build (CURRENT), the M3-contributed standalone
`ctexart`/XeLaTeX template (M3), and a hybrid of the two (HYBRID), judged
against the organizer's two official 2026 files.

**Decision: HYBRID** — keep the current audited build and add exactly one
element that M3 surfaced and that was then verified against the official
material: the 2026 four-logo cover row, drawn from local-only assets.

`paper/FORMAT_2026.md` remains the requirement-by-requirement conformance
audit; this file records only the comparison and the choice.

## Authority and evidence

1. Official 2026 textual format specification
   (`docs_local/gmcm-2026/source/paper_format_specification.official.docx`) —
   normative for typography, pagination and textual rules.
2. Official 2026 Word template
   (`docs_local/gmcm-2026/source/paper_template.official.doc`) — authoritative
   for cover structure and visible layout where (1) is silent.
3. Accepted T-014 evidence: `paper/FORMAT_2026.md`, `paper/format_2026.tex`.
4. The candidate implementations. 5. READMEs and defaults.

Both official files were re-delivered at the repository root for this stage.
Each was byte-identical (SHA-256 and size) to the canonical copy archived in
T-014, so the canonical copies were kept and the root copies removed. The M3
package matched the supervisor-inspected reference exactly (2,145,953 bytes,
SHA-256 `71f4b24c…586c`); it is archived locally as contributed, unofficial
implementation evidence and was extracted only into ignored audit space.

**M3 package inventory.** 33 members: 29 files after the top-level folder.
Source: `main.tex`, `setup.tex`, `config.tex`, `fonts.tex`,
`fonts-overleaf.tex`, `latexmkrc`, `README.md`, five `sections/*.tex`, four
`assets/*`, `fonts/README.md` (no font files are shipped). Build output and
duplicates, none used: `main.pdf`, `main.log`, `main.aux`, `main.out`, and a
`(1)` copy of eight files — seven byte-identical to their originals, and
`config(1).tex` empty.

**What the official textual specification actually states** (paraphrased):
title, abstract and keywords on the abstract page, body from the next page;
numbering from the abstract page, Arabic from 1, centred in the footer; no
running header and no identity marker; title Chinese size 3 Heiti, level-1
headings size 4 Heiti centred, other Chinese text small size 4 Songti, single
line spacing; abstract content items, normally at most two pages, no English
translation; bracketed numeric citations, book citations with pages,
references in order of first citation, with prescribed book / journal / web
patterns. It states **no** page margins, caption rules, equation-numbering
rules, appendix rules or AI-use rules.

## The logo-row question, resolved

T-014 dropped the class's cover logo row because that asset shows the previous
edition's host university and carries a hidden text layer, and it left the
missing row as a known deviation from the official cover.

M3 supplies four logo images. They were **not** adopted on their filenames:

| Asset | Relation to the official Word template | Stale edition / previous host | Text chunks or identity metadata |
| --- | --- | --- | --- |
| series mark (`cpipc.png`) | byte-identical to an embedded image | none | none |
| contest emblem (`modeling.png`) | byte-identical to an embedded image | none | none |
| sponsor mark (`huawei.jpeg`) | decoded pixels identical to the embedded JPEG; M3's file is that stream plus 17 trailing bytes copied from the Word record | none | XMP from the sponsor's 2018 artwork only; no team identity |
| host-university seal (`xjtu.png`) | pixel-identical to a lossless crop (0, 0, 835, 786) of the embedded seal-plus-wordmark composite, i.e. the seal the official cover displays | shows the **2026** host, Xi'an Jiaotong University | none |

The four local assets used by the build were then **extracted directly from the
official Word template**, not copied from M3 (`docs_local/gmcm-2026/cover-assets/`,
with the extraction script beside them). Pinned SHA-256 values are in
`scripts/build_paper.ps1`.

Geometry was checked, not assumed. Rendered at 300 dpi, the visible-ink extent
of each logo in the built cover was measured against the official template's
rendered cover: left edges agree within 0.7 mm, widths within 1.4 mm (largest
difference: the series mark, 34.5 mm against 35.9 mm), and the row's top is
1 mm higher.

## Requirement-by-requirement comparison

Status: **C** compliant, **N** non-compliant, **—** no official rule.

| # | Item | Official source | CURRENT | M3 | Decision (HYBRID) |
| --: | --- | --- | --- | --- | --- |
| 1 | Competition title and edition | template cover; spec document header | class title asset shows the 2026 edition in the template's decorative lettering; no text layer (re-tested) | typeset text; 华文新魏 absent here, falls back to Heiti | keep CURRENT (C; closer to the template's lettering) |
| 2 | Cover composition | template | logo row missing (T-014 compromise) | logo row, heading, identity table | CURRENT + official logo row (C) |
| 3 | Four-logo row | template | absent | four images, provenance unverified by M3 | drawn from assets extracted from the official template; verified above |
| 4 | Host-university identity | template | stale previous-host asset already excluded | correct 2026 host | correct 2026 host (C) |
| 5 | School / team number / three members | template | class table; values from ignored `team.tex` | `config.tex` macros | keep CURRENT (C) |
| 6 | Title placement | spec (abstract page) | `\makenametitle` on the abstract page | abstract page | keep CURRENT (C) |
| 7 | Anonymous body | spec | identity only on the cover | identity only on the cover | keep CURRENT (C) |
| 8 | Body identity leakage | spec | none; verified by page-wise text extraction | not tested beyond structure | keep CURRENT (C) |
| 9 | PDF metadata identity | spec (no identity) | title and author empty | sets a generic title, no author | CURRENT, plus explicit empty title/author/subject/keywords in `format_2026.tex` (C) |
| 10 | Abstract-page structure | spec + template | heading, 题目, 摘要, 关键词 | same items, plainer labels | keep CURRENT (C) |
| 11 | Abstract length | spec: normally at most two pages | content-time constraint | content-time constraint | content rule, checked at Stage B |
| 12 | English abstract | spec: not required | none | none | none (C) |
| 13 | Body right after the abstract page | spec | yes (TOC removed in T-014) | yes | keep CURRENT (C) |
| 14 | Table of contents | spec (implied by 13) | none | none | none (C) |
| 15 | Abstract page numbered 1 | spec | yes | yes | keep CURRENT (C) |
| 16 | Cover numbering | spec vs template `0` (T-014 finding B) | unnumbered | unnumbered | unchanged (C) |
| 17 | No running header | spec | yes (`format_2026.tex`) | yes | keep CURRENT (C) |
| 18 | Centred footer number | spec | yes | yes | keep CURRENT (C) |
| 19 | Title font and size | spec: size 3 Heiti | yes | yes | keep CURRENT (C) |
| 20 | Level-1 headings | spec: size 4 Heiti, centred | yes | yes | keep CURRENT (C) |
| 21 | Chinese body text | spec: small size 4 Songti | SimSun embedded | SimSun embedded | keep CURRENT (C) |
| 22 | English font | — | Times New Roman | Times New Roman, TeX Gyre fallback | keep CURRENT |
| 23 | Line spacing | spec: single | `\singlespacing` | `\linespread{1}` | keep CURRENT (C) |
| 24 | Paragraph indentation / spacing | — | ctex defaults (2 characters) | 2 em, 3 pt paragraph skip | keep CURRENT |
| 25 | Margins | — (not in the textual rules) | 30 / 25 / 22.5 / 22.5 mm | 30.02 / 18.49 / 22.51 / 22.47 mm, provenance not established | keep CURRENT; M3's values treated as unverified |
| 26 | Captions | — | class: Songti, small size 4 | Songti, small size 4 | keep CURRENT |
| 27 | Equation numbering | — | continuous `(n)` | continuous | keep CURRENT |
| 28 | Bibliography style | spec patterns | BibTeX + `gmcm.bst`; book pattern verified (T-014) | hand-written `thebibliography` placeholders | keep CURRENT (C for books; journal and web patterns re-checked when used) |
| 29 | First-citation ordering | spec | automatic, verified in T-014 | manual ordering by the author | keep CURRENT (C; lower error risk) |
| 30 | Book page information | spec | `pages` field required | manual | keep CURRENT (C) |
| 31 | Journal / web references | spec | style fields; rendered check pending real entries | manual | keep CURRENT; verify on the real list |
| 32 | Appendix | — | `\appendix` section | unnumbered appendices A/B | keep CURRENT |
| 33 | AI-use disclosure | official AI-use regulation — **not in the local archive** | appendix section prepared, content not written | placeholder fields modelled on that regulation | structure only; the regulation must be obtained and read before the section is filled |
| 34 | Build reproducibility | repository policy | pinned class + tracked overrides + build script | standalone, `latexmk` | keep CURRENT (C) |
| 35 | Compiler | — | XeLaTeX via `scripts/build_paper.ps1` | XeLaTeX | unchanged |
| 36 | Font availability / fallback | spec faces | class `windows` fontset; the decorative label face falls back to FandolHei when LiSu is absent | SimSun/SimHei or Fandol preview with a warning | keep CURRENT; `-Submission` now fails unless SimSun and SimHei are embedded |
| 37 | Hidden text layers | T-014 finding A | stale logo excluded; title asset has no text layer | raster PNG/JPEG, no text | row assets are raster; no text layer |
| 38 | Stale edition text | template | none on the cover or in the text layer | none | none |
| 39 | Stale logos / host | template | stale class logo excluded | correct | correct |
| 40 | Unsupported embedded metadata | — | none | generic PDF title | explicit empty metadata |
| 41 | Redistribution risk | repository policy | class and assets ignored | ZIP bundles organizer images | organizer images stay in ignored `docs_local/`; nothing organizer-owned is tracked |
| 42 | `paper/sections` compatibility | repository | native | different section layout | native |
| 43 | Generated result figures | repository | `\graphicspath` reaches `results/figures/` | manual paths | native |
| 44 | `scripts/build_paper.ps1` | repository | native | not used | native, plus `-Submission` |
| 45 | Clean-clone behaviour | repository | builds with placeholders | builds with placeholders | builds; without local assets the cover has **no** row (never a partial or stale one) and the log and build report say so |
| 46 | Final-submission reliability | — | depended on manual review | depended on manual review | `-Submission` enforces the logo row, real cover identity, embedded official fonts, empty metadata and no undefined references |

## Rationale

- Official compliance: CURRENT already met every explicit textual rule (T-014,
  re-tested here). Its one deviation from the official cover was the missing
  logo row.
- M3 surfaced a verifiable fix for exactly that deviation. It solves nothing
  else the official material requires: its geometry, typography and
  bibliography are either equivalent to CURRENT or rest on unverified values
  and manual ordering.
- ADOPT M3 CORE would replace an audited, reproducible build during the
  submission window for no compliance gain, add manual reference ordering, and
  lose the template's decorative competition lettering on machines without
  华文新魏. It is rejected.
- HYBRID is the minimum change: one optional macro inside the existing
  `format_2026.tex` patch, a guarded submission mode in the build script, and
  local-only assets whose bytes are traceable to the official template.

## Files changed by this decision

- `paper/format_2026.tex` — optional official logo row; explicit empty PDF
  metadata.
- `scripts/build_paper.ps1` — `-Submission` mode; submission-readiness report on
  every build.
- `paper/FORMAT_2026.md` — cover rows updated; T-014 history kept.
- this file.

Local-only, never tracked: `docs_local/gmcm-2026/contrib/` (M3 package and
provenance), `docs_local/gmcm-2026/audit/m3-latex-template/` (extraction and
fixture build), `docs_local/gmcm-2026/cover-assets/` (the four official images
and their extraction script).

## Final-build prerequisites

1. Run the extraction script in `docs_local/gmcm-2026/cover-assets/` against the
   archived official Word template, so the four cover images exist with the
   hashes pinned in `scripts/build_paper.ps1`.
2. Supply real cover fields in the git-ignored `paper/team.tex`.
3. Build with `powershell -File scripts/build_paper.ps1 -Submission` on a
   machine with SimSun and SimHei, and inspect every rendered page.
