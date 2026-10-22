"""The two step files, sent as a `batch` (their parsed object IS the batch arguments) and run with `solidcraft-cli run`
on the pinned 0.17.0 (no AI). Transcripts: out/steps/*.jsonl (the no-AI JSON card sources); run results: out/steps/."""
import json
import os
import subprocess

import pytest

import cells
from measure_box import measure_stl

LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
STEPS = os.path.join(LAB, 'steps')
OUT = os.path.join(LAB, 'out', 'steps')
A, B = 'shell-then-fillet', 'fillet-then-shell'


def load(name):
    with open(os.path.join(STEPS, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope='module')
def sent():
    os.makedirs(OUT, exist_ok=True)
    res = {}
    for name in (A, B):
        lab = cells.Lab(name, log_path=os.path.join(OUT, f'batch-{name}.jsonl'))
        lab.call('new_design', {'name': name})
        res[name] = lab.call_json('batch', load(name))
        lab.close()
    with open(os.path.join(OUT, 'batch-replies.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    return res


def logged_request(name):
    with open(os.path.join(OUT, f'batch-{name}.jsonl'), encoding='utf-8') as f:
        rows = [json.loads(l) for l in f]
    return next(r for r in rows if r['dir'] == 'client->server' and r['msg'].get('method') == 'tools/call'
                and r['msg']['params']['name'] == 'batch')


@pytest.mark.parametrize('name', [A, B])
def test_the_file_is_exactly_the_batch_arguments(sent, name):
    assert logged_request(name)['msg']['params']['arguments'] == load(name)


def test_shell_first_is_refused_at_the_fillet(sent):
    r = sent[A]
    assert r['isError'] is True and r['body']['ok'] is False
    assert r['body']['failed']['index'] == 5 and r['body']['failed']['command'] == 'solid.fillet'
    assert r['body']['failed']['error'].endswith('the largest radius that fits is 6.82 mm')
    assert r['body']['rolled_back'] is True and r['body']['undone'] == 5


def test_fillet_first_builds(sent):
    r = sent[B]
    assert r['isError'] is False and r['body']['ok'] is True and r['body']['completed'] == 6


def run_cli(name):
    stl = os.path.join(OUT, f'run-{name}.stl')
    if os.path.exists(stl):
        os.remove(stl)
    p = subprocess.run(['solidcraft-cli', 'run', os.path.join(STEPS, name + '.json'), '--out', stl],
                       capture_output=True, text=True, timeout=120)
    rec = {'argv': ['solidcraft-cli', 'run', f'steps/{name}.json', '--out', f'out/steps/run-{name}.stl'],
           'exit': p.returncode, 'stdout': p.stdout.strip()[-2000:], 'stderr': p.stderr.strip()[-2000:],
           'stl_written': os.path.exists(stl)}
    with open(os.path.join(OUT, f'run-{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    return rec, stl


def test_cli_run_refuses_the_shell_first_file_and_writes_nothing():
    rec, _ = run_cli(A)
    assert rec['exit'] != 0
    assert not rec['stl_written']
    assert '6.82' in rec['stdout'] + rec['stderr']


def test_cli_run_builds_the_fillet_first_file():
    rec, stl = run_cli(B)
    assert rec['exit'] == 0 and rec['stl_written']
    m = measure_stl(stl)
    assert m['size'] == pytest.approx([80, 60, 30], abs=0.01)
    assert m['corner_wall']['wall_mm'] == pytest.approx(2.0, abs=0.001)
    with open(os.path.join(OUT, f'run-{B}-measure.json'), 'w', encoding='utf-8') as f:
        json.dump(m, f, indent=1)
