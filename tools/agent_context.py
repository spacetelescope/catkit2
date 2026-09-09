#!/usr/bin/env python3
"""Regenerate and validate the repository's derived agent-context index."""

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / 'docs' / 'agent' / 'REPO_ATLAS.md'
INDEX = ATLAS.with_name('repo_index.json')
FIELD_NAMES = ('Summary', 'Owner', 'Status', 'Docs', 'Tests', 'Related')
HEADER_NAMES = ('repo', 'visibility', 'source_commit', 'derived_from', 'authority')


def parse_atlas(text):
    """Extract the compact concept records from the human-readable atlas."""
    concepts = {}
    pattern = r'^## ([a-z][a-z_]+) — ([^\n]+)\n(.*?)(?=^## |\Z)'
    for match in re.finditer(pattern, text, re.MULTILINE | re.DOTALL):
        key, _title, body = match.groups()
        fields = {}
        field_pattern = r'^- (' + '|'.join(FIELD_NAMES) + r'): (.+)$'
        for label, value in re.findall(field_pattern, body, re.MULTILINE):
            fields.setdefault(label, []).append(value)

        read_first = re.findall(
            r'^- \*\*Read first:\*\* `([^`]+)` in `([^`]+)` — (.+)$',
            body,
            re.MULTILINE,
        )
        missing = [name for name in FIELD_NAMES if name not in fields]
        if not read_first:
            missing.append('Read first')
        if missing:
            raise ValueError('{} is missing: {}'.format(key, ', '.join(missing)))

        tests = re.findall(r'`([^`]+)`', fields['Tests'][0])
        concept = {
            'summary': fields['Summary'][0],
            'owner': fields['Owner'][0],
            'status': fields['Status'][0],
            'atlas_section': 'concept-' + key,
            'canonical_examples': [
                {'path': path, 'symbol': symbol, 'why': why}
                for symbol, path, why in read_first
            ],
            'docs': re.findall(r'`([^`]+)`', fields['Docs'][0]),
            'tests': tests,
        }
        if not tests:
            concept['coverage_note'] = fields['Tests'][0]
        concept['related_concepts'] = [
            item.strip() for item in fields['Related'][0].split(',')
        ]
        concepts[key] = concept

    if not concepts:
        raise ValueError('No atlas concepts found.')
    return concepts


def build_index(atlas_text):
    """Build a new index while preserving reviewed repository metadata."""
    if not INDEX.is_file():
        raise ValueError('repo_index.json is required for repository metadata.')
    previous = json.loads(INDEX.read_text(encoding='utf-8'))
    missing = [name for name in HEADER_NAMES if name not in previous]
    if missing:
        raise ValueError('Index metadata is missing: {}'.format(', '.join(missing)))

    result = {name: previous[name] for name in HEADER_NAMES[:4]}
    result['atlas_sha256'] = hashlib.sha256(ATLAS.read_bytes()).hexdigest()
    result['authority'] = previous['authority']
    result['concepts'] = parse_atlas(atlas_text)
    return result


def render_index(index):
    """Render compact, deterministic JSON with one line per concept."""
    header = {key: value for key, value in index.items() if key != 'concepts'}
    lines = ['{']
    for key, value in header.items():
        lines.append('  ' + json.dumps(key) + ': ' + json.dumps(value) + ',')
    lines.append('  "concepts": {')
    concepts = list(index['concepts'].items())
    for position, (key, value) in enumerate(concepts):
        suffix = ',' if position + 1 < len(concepts) else ''
        lines.append(
            '    ' + json.dumps(key) + ': '
            + json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            + suffix
        )
    lines.extend(['  }', '}'])
    return '\n'.join(lines) + '\n'


def validate(atlas_text, expected_text, concepts):
    """Check concept links, referenced files, Markdown links and generated JSON."""
    errors = []
    for key, concept in concepts.items():
        unknown = set(concept['related_concepts']) - set(concepts)
        if unknown:
            errors.append('{} has unknown related concepts: {}'.format(key, unknown))
        anchor = '<a id="{}"></a>'.format(concept['atlas_section'])
        if anchor not in atlas_text:
            errors.append('{} is missing its section anchor'.format(key))
        paths = concept['docs'] + concept['tests']
        paths += [item['path'] for item in concept['canonical_examples']]
        for relative_path in paths:
            if not (ROOT / relative_path).is_file():
                errors.append('{} references missing {}'.format(key, relative_path))

    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', atlas_text):
        if '://' not in target and not target.startswith('#'):
            if not (ATLAS.parent / target).resolve().exists():
                errors.append('Broken Markdown link: {}'.format(target))

    if not INDEX.is_file() or INDEX.read_text(encoding='utf-8') != expected_text:
        errors.append('repo_index.json is stale; run with generate.')
    if errors:
        raise ValueError('\n'.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('generate', 'check'))
    args = parser.parse_args()

    atlas_text = ATLAS.read_text(encoding='utf-8')
    index = build_index(atlas_text)
    expected_text = render_index(index)
    if args.command == 'generate':
        INDEX.write_text(expected_text, encoding='utf-8')
    validate(atlas_text, expected_text, index['concepts'])
    print('{}: {} concepts; {} passed'.format(index['repo'], len(index['concepts']), args.command))


if __name__ == '__main__':
    main()
