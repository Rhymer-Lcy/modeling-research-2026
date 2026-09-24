"""Re-verify canonical A1-A16 without fitting Q or a Loss model.

All raw inputs are read-only. Writes only the regenerable Q1 audit table.
No dataset text, identifiers or individual records enter that table.
"""
from __future__ import annotations

from collections import Counter
import csv
from decimal import Decimal
import hashlib
import json
import lzma
from pathlib import Path
import sys
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.paths import ATT_A, PROBLEM_F_SOURCE, REPO_ROOT, TABLES, require, ensure
from src.quality import scalarize as sc
from src.quality.pipeline import QUALITY_DOMAINS
from src.quality.diagnostics import diagnostic_reduction
from src.mixture.data import MIXTURE_FILES, LOSS_FILES, load_pair, diagnostics
from src.mixture.mapping import load_mapping, mass_weighted_coverage


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def rounding_bound(path: Path) -> tuple[int, float, int]:
    """Audit the table's finest decimal grid; do not infer a model tolerance.

    Bound assumes each stored cell was rounded to the nearest grid point.
    A future model configuration must explicitly adopt or reject that policy.
    """
    with path.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    cells = [[Decimal(v) for k, v in row.items() if k != 'index'] for row in rows]
    if any(not v.is_finite() for row in cells for v in row):
        raise ValueError('non-finite mixture cell')
    exponent = min(v.as_tuple().exponent for row in cells for v in row)
    grid = Decimal(10) ** exponent
    bound = len(cells[0]) * grid / 2
    if any(abs(sum(row) - 1) > bound for row in cells):
        raise ValueError(f'{path.name}: sums exceed nearest-rounding bound')
    # Preserve the inherited threshold failure in exact decimal arithmetic.
    old_failures = sum(abs(sum(row) - 1) > Decimal('0.002') for row in cells)
    return -exponent, float(bound), old_failures


def audit_quality(path: Path, assigned_domain: str | None, reference: dict | None):
    counts = Counter()
    widths = {name: Counter() for name in sc.LIST_FIELDS}
    seen = set()
    matched, mismatched = 0, 0
    retained = {}
    nonfinite = Counter()
    affected_domains = Counter()
    affected_records = 0
    raw_kinds, literal_constants = Counter(), Counter()
    defects = []
    transform_created = Counter()
    with lzma.open(path, 'rb') as handle:
        for line_number, line in enumerate(handle, 1):
            tokens = Counter()
            def parse_constant(token):
                tokens[token] += 1
                return float(token)
            row = json.loads(line, parse_constant=parse_constant)
            literal_constants.update(tokens)
            issues, created = diagnostic_reduction(row)
            transform_created.update(created)
            bad_fields = {issue['field'] for issue in issues} | set(created)
            for name in sc.LIST_FIELDS:
                widths[name][len(row[name])] += 1
                if not np.isfinite(row[name]).all():
                    bad_fields.add(name)
            domain = assigned_domain or row['_source_domain']
            if domain not in QUALITY_DOMAINS:
                raise ValueError('unexpected quality domain')
            if assigned_domain and row.get('_source_domain', assigned_domain) != assigned_domain:
                raise ValueError('extension domain metadata disagrees with assigned domain')
            nonfinite.update(bad_fields)
            if bad_fields:
                affected_records += 1
                affected_domains[domain] += 1
                for issue in issues:
                    raw_kinds[issue['kind']] += 1
                    defects.append({'line': line_number, 'domain': domain, **issue,
                                    'line_sha256': hashlib.sha256(line).hexdigest(),
                                    'literal_constants': dict(tokens)})
            # Source and ID together avoid conflating IDs from different shards.
            key = (domain, row['sub_path'], row['id'])
            if key in seen:
                raise ValueError(f'{path.name}: duplicate source/record identity')
            seen.add(key)
            counts[domain] += 1
            if domain in {'arxiv', 'github'}:
                signature = tuple(json.dumps(row[n], separators=(',', ':')) for n in sc.INDICATORS)
                if reference is None:
                    retained[key] = signature
                elif key in reference:
                    matched += 1
                    mismatched += signature != reference[key]
    if not seen or any(set(widths[n]) != {sc.EXPECTED_DIM[n]} for n in widths):
        raise ValueError('empty input or unexpected list width')
    if mismatched:
        raise ValueError('A1/extension quality signals disagree on shared identities')
    print(path.name, 'records', len(seen), 'domains', dict(counts), 'A1 overlap', matched,
          'nonfinite fields', dict(nonfinite), flush=True)
    return {'n': len(seen), 'counts': counts, 'overlap': matched,
            'nonfinite': nonfinite, 'affected_records': affected_records,
            'affected_domains': affected_domains, 'defects': defects,
            'raw_kinds': raw_kinds, 'literal_constants': literal_constants,
            'transform_created': transform_created}, retained


def main() -> int:
    docx = require(PROBLEM_F_SOURCE / 'problem_statement.docx')
    with ZipFile(docx) as package:
        if package.testzip() is not None:
            raise ValueError('problem statement DOCX ZIP integrity failed')
        ET.fromstring(package.read('word/document.xml'))
    paths = {'A1': require(ATT_A / 'slimpajama_quality_signal_sample.jsonl.xz')}
    for aid, domain in [('A2', 'arxiv'), ('A3', 'github')]:
        candidates = sorted((ATT_A / 'slimpajama_quality_extended').glob(domain + '_*.jsonl.xz'))
        if len(candidates) != 1:
            raise ValueError(f'{aid}: expected exactly one canonical {domain} extension file')
        paths[aid] = candidates[0]
    for aid, filename in MIXTURE_FILES.items():
        paths[aid] = require(ATT_A / 'regmix_tables' / filename)
        paths['A' + str(int(aid[1:]) + 1)] = require(ATT_A / 'regmix_tables' / LOSS_FILES[aid])
    paths['A16'] = require(ATT_A / 'domain_mapping_guide.csv')
    before = {aid: sha256(path) for aid, path in paths.items()}
    docx_hash = sha256(docx)
    quality = {}
    quality['A1'], reference = audit_quality(paths['A1'], None, None)
    if set(quality['A1']['counts']) != set(QUALITY_DOMAINS) or quality['A1']['n'] != 51230:
        raise ValueError('A1 differs from the scalarization checkpoint population')
    for aid, domain in [('A2', 'arxiv'), ('A3', 'github')]:
        quality[aid], _ = audit_quality(paths[aid], domain, reference)
    pairs, precision = {}, {}
    for aid in MIXTURE_FILES:
        precision[aid] = rounding_bound(paths[aid])
        pairs[aid] = load_pair(ATT_A / 'regmix_tables', aid, row_sum_tolerance=precision[aid][1])
    train = pairs['A4'][0]
    for mix, loss in pairs.values():
        if mix.domains != train.domains or loss.columns != pairs['A4'][1].columns:
            raise ValueError('domain/target schema differs across tables')
    d = diagnostics(pairs)
    if not d['A6_vs_A8']['same_design'] or not d['A6_vs_A8']['same_indices']:
        raise ValueError('A6/A8 repeated design assumption failed')
    for aid in ('A12', 'A14'):
        mix = pairs[aid][0]
        by_index = dict(zip(train.indices, train.values))
        if not all(i in by_index and np.array_equal(v, by_index[i]) for i, v in zip(mix.indices, mix.values)):
            raise ValueError(f'{aid}: not an exact indexed subset of A4')
    train_designs = set(map(tuple, train.values))
    overlaps = {aid: len(train_designs & set(map(tuple, pairs[aid][0].values))) for aid in ('A6', 'A10')}
    if any(overlaps.values()) or d['A4']['duplicate_designs']:
        raise ValueError('train/test design overlap or duplicated training design')
    mapping, kinds = load_mapping(paths['A16'], train.domains)
    if any(target not in QUALITY_DOMAINS for target in mapping.values() if target is not None):
        raise ValueError('A16 quality target is outside A1 domains')
    mapped = np.array([mapping[name] is not None for name in train.domains])
    masses = (train.values / train.values.sum(axis=1, keepdims=True))[:, mapped].sum(axis=1)
    after = {aid: sha256(path) for aid, path in paths.items()}
    if before != after or sha256(docx) != docx_hash:
        raise ValueError('raw input bytes changed during verification')
    lines = ['# Q1 canonical input audit', '',
             'Generated by `python scripts/q1_audit_inputs.py`. No Q or Loss model was fitted.', '',
             'A1-A16 are data-description identifiers. Inputs remain local-only and read-only.',
             'DOCX ZIP/XML integrity passed; this is not a rendered-layout certification.',
             f'Official DOCX SHA-256: `{docx_hash}`.', '',
             '## Complete quality-file checks', '',
             '| Input | Records | Domains | Shared A1 identities with identical signals |',
             '| --- | ---: | --- | ---: |']
    for aid, item in quality.items():
        domains = ', '.join(f'{k}: {v}' for k, v in sorted(item['counts'].items()))
        lines.append(f"| {aid} | {item['n']} | {domains} | {item['overlap'] if aid != 'A1' else 'reference'} |")
    failed = any(item['affected_records'] for item in quality.values())
    lines += ['', 'All records have the canonical 14 scalar + 8 reduced list fields.',
              'List widths are 1/2/2/4/6/6/6/6.',
              'The extension domain is assigned from its file; extension records have no',
              '`_source_domain` field. A2/A3 are same-source extensions, not independent replications.', '',
              '### Finiteness gate', '',
              '**FAIL: Q1a scoring stopped; no deletion or imputation performed.**' if failed else '**PASS**', '',
              '| Input | Affected records | Non-finite fields (record counts) | Affected domains |',
              '| --- | ---: | --- | --- |']
    for aid, item in quality.items():
        fields = ', '.join(f'{k}: {v}' for k, v in sorted(item['nonfinite'].items())) or 'none'
        domains = ', '.join(f'{k}: {v}' for k, v in sorted(item['affected_domains'].items())) or 'none'
        lines.append(f"| {aid} | {item['affected_records']} | {fields} | {domains} |")
    lines += ['', '### Cause and exact record locators', '',
              'Raw fields are inspected before scalarization. JSON parser callbacks distinguish',
              'literal non-standard numeric constants from missing fields, nulls, strings,',
              'wrong list widths and non-finiteness created only by a transformation.', '',
              '| Input | Literal NaN tokens | Literal +inf tokens | Literal -inf tokens | Raw issue kinds (field occurrences) | Transform-created non-finite fields |',
              '| --- | ---: | ---: | ---: | --- | --- |']
    for aid, item in quality.items():
        tokens = item['literal_constants']
        kinds_description = ', '.join(f'{k}: {v}' for k, v in sorted(item['raw_kinds'].items())) or 'none'
        created = ', '.join(f'{k}: {v}' for k, v in sorted(item['transform_created'].items())) or 'none'
        lines.append(f"| {aid} | {tokens['NaN']} | {tokens['Infinity']} | {tokens['-Infinity']} | {kinds_description} | {created} |")
    lines += ['', 'The following are derived locators, not copies of raw records. Lines are',
              'one-based physical lines in the decompressed file. Component indices are zero-based.',
              'Each fingerprint hashes the exact decompressed line bytes, including its terminator.',
              'Together with the input-file fingerprints below, these identify every affected record',
              'without publishing text or source record IDs.', '',
              '| Input | Line | Domain | Indicator | Raw issue | Components | Line SHA-256 |',
              '| --- | ---: | --- | --- | --- | --- | --- |']
    for aid, item in quality.items():
        for issue in item['defects']:
            components = ','.join(map(str, issue['components'])) or 'field structure'
            lines.append(f"| {aid} | {issue['line']} | {issue['domain']} | {issue['field']} | {issue['kind']} | {components} | `{issue['line_sha256']}` |")
    lines += ['', 'The existing scalarization script checks dimensions, but does not reject',
              'these non-finite values. Its successful run is not a finiteness certificate.',
              'The repaired quality preprocessor rejects them before fitting an ECDF.',
              'The raw-input audit remains failed. The approved complete-case and flagged',
              'sensitivity policy is evaluated separately by scripts/q1_quality.py.', '',
              '## Mixture structure', '',
              'Every mixture/loss pair has unique, exactly aligned indices, 17 consistently',
              'named domains and 13 finite nonnegative Loss targets. Original values are retained.', '',
              '| Mixture | Rows | Sum min | Sum max | Decimal places | Rounding bound | Rows exceeding 0.002 (decimal arithmetic) | Max cell normalization change | Duplicate designs |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for aid in MIXTURE_FILES:
        item = d[aid]
        places, bound, failures = precision[aid]
        lines.append(f"| {aid} | {item['n']} | {item['row_sum_min']:.6f} | {item['row_sum_max']:.6f} | {places} | {bound:.6f} | {failures} | {item['max_cell_adjustment']:.6f} | {item['duplicate_designs']} |")
    lines += ['', 'The arithmetic bound is half the finest observed decimal grid times 17,',
              'conditional on nearest rounding. This audit accepts that bound solely to',
              'inspect structural relationships; it does not authorize a model tolerance.',
              'Normalization divides each row by its observed sum; exact zeros stay zero.', '',
              'A6 and A8 have identical indices and values. A12 and A14 are exact indexed',
              'subsets of A4. A4 has zero exact design overlap with A6 or A10. Indices are',
              'local to each table: overlapping index labels alone do not identify repeated designs.', '',
              '| Domain | A4 zero fraction | A6 | A8 | A10 | A12 | A14 |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in train.domains:
        lines.append('| ' + name + ' | ' + ' | '.join(f"{d[aid]['zero_fraction_by_domain'][name]:.6f}" for aid in MIXTURE_FILES) + ' |')
    lines += ['', '## Mapping coverage', '',
              f'Usable mappings: {sum(mapped)}/17 domains (a count, not mass coverage).',
              f'A4 reference mass coverage: **{mass_weighted_coverage(train, mapping):.6f}**.',
              f'Per-design mapped mass: min {masses.min():.6f}, median {np.median(masses):.6f}, max {masses.max():.6f}.',
              'Reference aggregation is the mean covered mass after normalizing each observed',
              'training design to unit mass. No whole-corpus Q is implied. At zero mapped',
              'mass, Q_mapped is undefined. No scores are invented for `(none)` mappings.', '',
              '| Mixture domain | Quality domain | Original mapping type |',
              '| --- | --- | --- |']
    for name in train.domains:
        lines.append(f'| {name} | {mapping[name] or "none"} | {kinds[name]} |')
    lines += ['', '## Reproducibility fingerprints', '',
              'All 16 inputs and the DOCX were hashed before and after the audit; no bytes changed.', '',
              '| Input | Canonical path | SHA-256 |', '| --- | --- | --- |']
    for aid in sorted(paths, key=lambda a: int(a[1:])):
        lines.append(f'| {aid} | `{paths[aid].relative_to(REPO_ROOT).as_posix()}` | `{before[aid]}` |')
    lines += ['', 'A13/A15 are estimated/extrapolated references, not independent validation.',
              'This audit examines their schema and finiteness only; no reference Loss is used for fitting.', '']
    out = ensure(TABLES) / 'q1-input-audit.md'
    out.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print('wrote', out.relative_to(REPO_ROOT).as_posix(), flush=True)
    print('raw input fingerprints unchanged; mixture structure PASS', flush=True)
    print('raw-input audit: KNOWN INPUT DEFECT; scientific pipeline acceptance is separate' if failed else 'quality finiteness PASS', flush=True)
    return 2 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
