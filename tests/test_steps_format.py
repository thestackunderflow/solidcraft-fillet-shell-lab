"""PT3: the two step files (no SolidCraft). SolidCraft's script format (docs/scripts.md): an object
{"commands": [{"command": ..., "params": ...}, ...]}, the same object a `batch` call takes as its arguments.
Card budget: <= 12 rows, <= 64 columns, the same row count, differing only in the shell / fillet block."""
import json
import os

STEPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'steps')
A = os.path.join(STEPS, 'shell-then-fillet.json')
B = os.path.join(STEPS, 'fillet-then-shell.json')


def lines(p):
    with open(p, encoding='utf-8') as f:
        return f.read().rstrip('\n').split('\n')


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def test_pt3_script_format():
    for p in (A, B):
        obj = load(p)
        assert list(obj) == ['commands']
        for step in obj['commands']:
            assert set(step) == {'command', 'params'}


def test_pt3_same_commands_two_swapped():
    a, b = load(A)['commands'], load(B)['commands']
    assert [s['command'] for s in a][:-2] == [s['command'] for s in b][:-2]
    assert a[:-2] == b[:-2]
    assert [s['command'] for s in a][-2:] == ['solid.shell', 'solid.fillet']
    assert [s['command'] for s in b][-2:] == ['solid.fillet', 'solid.shell']
    assert a[-2] == b[-1] and a[-1] == b[-2]   # the same two steps, swapped


def test_pt3_the_hero_numbers():
    b = load(B)['commands']
    fillet = next(s for s in b if s['command'] == 'solid.fillet')
    shell = next(s for s in b if s['command'] == 'solid.shell')
    assert fillet['params']['radius'] == 10
    assert len(fillet['params']['edges']) == 4
    assert shell['params']['thickness'] == 2
    assert shell['params']['faces'] == [[0, 0, 30]]


def test_pt3_card_budget():
    la, lb = lines(A), lines(B)
    assert len(la) == len(lb) <= 12
    assert max(len(x) for x in la + lb) <= 64
    changed = [i for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    # only the shell / fillet block differs, and it is contiguous
    assert changed and changed == list(range(changed[0], changed[-1] + 1))
    assert all('solid.' in la[i] or la[i].startswith('  ') for i in changed)
    assert la[:changed[0]] == lb[:changed[0]] and la[changed[-1] + 1:] == lb[changed[-1] + 1:]
