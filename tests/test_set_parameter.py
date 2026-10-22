"""One no-AI `set_parameter` call for the wall (PLAN 5.3 JSON 2 source, used only if no agent run sent one).
Transcript: out/set_parameter/transcript.jsonl."""
import json
import os

import cells

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'set_parameter')


def test_set_parameter_wall():
    os.makedirs(OUT, exist_ok=True)
    lab = cells.Lab('set-parameter', log_path=os.path.join(OUT, 'transcript.jsonl'))
    lab.call('new_design', {'name': 'wall'})
    r = lab.call_json('set_parameter', {'name': 'wall', 'value': 2})
    lab.close()
    assert r['isError'] is False
    with open(os.path.join(OUT, 'transcript.jsonl'), encoding='utf-8') as f:
        rows = [json.loads(l) for l in f]
    req = next(x for x in rows if x['dir'] == 'client->server' and x['msg'].get('method') == 'tools/call'
               and x['msg']['params']['name'] == 'set_parameter')
    assert req['msg']['params'] == {'name': 'set_parameter', 'arguments': {'name': 'wall', 'value': 2}}
    assert req['msg']['jsonrpc'] == '2.0' and isinstance(req['msg']['id'], int)
