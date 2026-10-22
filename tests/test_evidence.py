"""The files the video cites say what the script will say (PLAN v2 5.1):
- every number in video/*.txt is in out/evidence/numbers.json, and every value there is recomputed here from out/;
- terminal excerpts <= 8 rows x 44 cols; JSON view cards <= 12 rows at 44 cols (an approximation of the engine's
  layout; pr-plan --check is the authority); the focusKey value is the captured one;
- panel-sources.json: every pinned file exists and its sha256 matches;
- no host paths, user names or tokens in anything under out/, video/, steps/, claude-run/."""
import glob
import hashlib
import json
import os
import re

import pytest

LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
P = lambda *a: os.path.join(LAB, *a)  # noqa: E731


def jload(*a):
    with open(P(*a), encoding='utf-8') as f:
        return json.load(f)


NUMBERS = P('out', 'evidence', 'numbers.json')


def numbers():
    return jload('out', 'evidence', 'numbers.json')


def probe(cell):
    return jload('out', 'probe', '0.17.0', cell, 'summary.json')


def test_numbers_are_recomputed_from_out():
    n = numbers()
    fs10, sf6, off, fs6 = probe('FS-10-1'), probe('SF-6-1'), probe('SF-offered-1'), probe('FS-6-1')
    assert n['fs10_sc_volume'] == f"{fs10['sc_volume_mm3']:.2f}"
    assert n['fs10_expected_volume'] == f"{fs10['expected_volume']:.2f}"
    assert n['sf6_wall_stl'] == f"{sf6['stl']['wall_mm']:.4f}"
    assert n['sf6_wall_sc'] == f"{sf6['sc_wall']['radius_minus_axis_mm']:.4f}"
    assert n['offered_radius'] == '6.82' and '6.82 mm' in probe('SF-10-1')['batch2']['failed']['error']
    assert n['offered_wall_stl'] == f"{off['stl']['wall_mm']:.4f}"
    assert n['offered_wall_sc'] == f"{off['sc_wall']['radius_minus_axis_mm']:.4f}"
    assert n['fs_wall'] == f"{fs6['stl']['wall_mm']:.4f}" == f"{fs10['stl']['wall_mm']:.4f}"
    scores = jload('out', 'runs', 'SCORES.json')
    total = sum(r['cost_usd'] for r in scores['runs'])
    assert n['runs_total_usd'] == f'{total:.2f}'
    assert n['runs'] == str(len(scores['runs']))


def tokens(text):
    return re.findall(r'(?<![\w.])\d+(?:\.\d+)?(?![\w.])', text)


ALWAYS = {'0', '1', '2', '3', '4', '5', '6', '8', '10', '15', '30', '44', '60', '80', '0.17', '0.17.0'}


@pytest.mark.parametrize('path', sorted(glob.glob(P('video', '*.txt'))))
def test_every_number_in_panel_text_is_evidence(path):
    allowed = set(ALWAYS) | {str(v) for v in numbers().values()}
    allowed |= {t for v in numbers().values() for t in tokens(str(v))}
    with open(path, encoding='utf-8') as f:
        bad = [t for t in tokens(f.read()) if t not in allowed]
    assert not bad, f'{os.path.basename(path)}: {bad}'


@pytest.mark.parametrize('path', sorted(glob.glob(P('video', 'terminal-*.txt'))))
def test_terminal_excerpts_fit_a_phone(path):
    with open(path, encoding='utf-8') as f:
        rows = f.read().rstrip('\n').split('\n')
    assert len(rows) <= 8 and max(len(r) for r in rows) <= 44, path


def layout(value, cols, indent=0, key=None):
    """Pretty layout rows: a container that does not fit is broken one member per row, indented by 2 (code-panel 3b)."""
    head = ' ' * indent + (json.dumps(key) + ': ' if key is not None else '')
    one = head + json.dumps(value, ensure_ascii=False)
    if len(one) + 1 <= cols or not isinstance(value, (dict, list)):
        return [one]
    rows = [head + ('{' if isinstance(value, dict) else '[')]
    items = value.items() if isinstance(value, dict) else [(None, v) for v in value]
    for k, v in items:
        rows += layout(v, cols, indent + 2, k)
    rows.append(' ' * indent + ('}' if isinstance(value, dict) else ']'))
    return rows


def pointer(doc, ptr):
    for part in [p for p in ptr.split('/') if p]:
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def test_json_view_cards_fit_and_focus_the_captured_value():
    cards = jload('video', 'json-cards.json')
    assert cards
    for c in cards:
        path, line = c['src'].rsplit('#L', 1)
        with open(P(path), encoding='utf-8') as f:
            row = json.loads(f.read().split('\n')[int(line) - 1])
        if 'view' in c:
            sub = pointer(row, c['view']['at'])
            if 'items' in c['view']:
                a, b = c['view']['items']
                sub = sub[a:b + 1]
            rows = layout(sub, c['view']['cols'])
            folds = 1 if 'items' in c['view'] and (c['view']['items'][0] > 0) else 0
            assert c['view']['cols'] <= 44
            assert len(rows) + folds + 1 <= 12, (c['id'], len(rows))      # + the path row
        if 'focusKey' in c:
            assert pointer(row, c['focusKey']) == c['focusValue'], c['id']


def test_panel_sources_are_pinned():
    for s in jload('video', 'panel-sources.json')['sources']:
        with open(P(s['path']), 'rb') as f:
            assert hashlib.sha256(f.read()).hexdigest() == s['sha256'], s['path']


# Host paths (they carry the account name), API keys and bearer tokens. Extra names to look for can be passed in
# LAB_PRIVATE_WORDS (comma-separated) so the public repo never has to spell them out.
_EXTRA = [re.escape(w.strip()) for w in os.environ.get('LAB_PRIVATE_WORDS', '').split(',') if w.strip()]
SECRET = re.compile('|'.join([r'C:[/\\]+Users', r'/c/Users', r'sk-ant-', r'Bearer [A-Za-z0-9]', r'ANTHROPIC_API_KEY=\S'] + _EXTRA), re.I)


def test_no_host_paths_names_or_tokens():
    bad = []
    for top in ('out', 'video', 'steps', 'claude-run', 'probe'):
        for path in glob.glob(P(top, '**', '*'), recursive=True):
            if os.path.isdir(path) or path.endswith(('.png', '.stl')):
                continue
            with open(path, encoding='utf-8', errors='replace') as f:
                if SECRET.search(f.read()):
                    bad.append(os.path.relpath(path, LAB))
    assert not bad, bad
