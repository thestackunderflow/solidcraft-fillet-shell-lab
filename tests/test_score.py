"""The agent-run scorer (claude-run/score.py) on synthetic transcripts: the order of the successful fillet / shell, the
recovery after a refusal, the 'neither' route, and the budget log."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'claude-run'))
import score  # noqa: E402

SHELL = {'command': 'solid.shell', 'params': {'faces': [[0, 0, 30]], 'thickness': 2}}


def fil(r, **kw):
    return {'command': 'solid.fillet', 'params': {'edges': [[40, 30, 15]], 'radius': r, **kw}}


BASE = [{'command': 'sketch.create', 'params': {'plane': 'XY'}}, {'command': 'solid.extrude', 'params': {'distance': 30}}]


def transcript(steps):
    """steps: [(tool, arguments, reply_body, isError)] -> proxy-shaped rows."""
    rows, i = [], 0
    for tool, args, body, err in steps:
        i += 1
        rows.append({'dir': 'client->server', 'msg': {'jsonrpc': '2.0', 'id': i, 'method': 'tools/call',
                                                      'params': {'name': tool, 'arguments': args}}})
        rows.append({'dir': 'server->client', 'msg': {'jsonrpc': '2.0', 'id': i, 'result': {
            'content': [{'type': 'text', 'text': json.dumps(body)}], 'isError': err}}})
    return rows


REFUSED = {'ok': False, 'failed': {'index': 2, 'command': 'solid.fillet', 'error': 'fillet: … the largest radius that fits is 6.82 mm'}}


def test_shell_first_refused_then_reordered():
    rows = transcript([('batch', {'commands': BASE + [SHELL, fil(10)]}, REFUSED, True),
                       ('batch', {'commands': BASE + [fil(10), SHELL]}, {'ok': True}, False)])
    s = score.analyse(rows)
    assert s['first_attempt_order'] == 'SF'
    assert s['final_order'] == 'FS'
    assert s['refusals'] == 1 and '6.82' in s['refusal_errors'][0]
    assert s['recovery'] == 'reorder'


def test_shell_first_refused_then_offered_radius():
    rows = transcript([('batch', {'commands': BASE + [SHELL, fil(10)]}, REFUSED, True),
                       ('batch', {'commands': BASE + [SHELL, fil(6.82)]}, {'ok': True}, False)])
    s = score.analyse(rows)
    assert s['final_order'] == 'SF' and s['recovery'] == 'smaller radius'
    assert s['final_fillet_radius'] == 6.82


def test_execute_calls_count_too_and_fit_is_seen():
    rows = transcript([('execute', {'command': 'solid.shell', 'params': SHELL['params']}, {'ok': True}, False),
                       ('execute', fil(10), {'error': 'x'}, True),
                       ('execute', fil(10, fit='reduce'), {'ok': True}, False)])
    s = score.analyse(rows)
    assert s['first_attempt_order'] == 'SF' and s['recovery'] == 'fit'


def test_neither_route():
    rows = transcript([('batch', {'commands': [{'command': 'sketch.fillet', 'params': {'radius': 10}}]}, {'ok': True}, False)])
    s = score.analyse(rows)
    assert s['final_order'] == 'neither'


def test_budget_total(tmp_path):
    p = tmp_path / 'BUDGET.log'
    p.write_text('plain-1\t0.21\tlogged\t0.2100\nnamed-1\t1.50\tkilled-floor\t1.7100\n')
    assert score.budget_total(str(p)) == 1.71
