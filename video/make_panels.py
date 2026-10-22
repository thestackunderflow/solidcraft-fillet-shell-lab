"""Panel text and card specs for the video, written from out/ only (no number is typed by hand).

    python3 video/make_panels.py      (in the lab image, or any Python 3 with no extra packages)

Writes out/evidence/numbers.json (every number the panels use, formatted), out/evidence/refusal.txt (the verbatim
refusal), video/terminal-*.txt (<= 8 rows x 44 cols), video/rule-card.txt, video/toolcalls.json (toolcall panels:
args <= 160 chars of compact JSON, result <= 60), video/json-cards.json (JSON view cards: src#line, view, focusKey).
tests/test_evidence.py re-derives every value from out/.
"""
import json
import os

LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
P = lambda *a: os.path.join(LAB, *a)  # noqa: E731


def jload(*a):
    with open(P(*a), encoding='utf-8') as f:
        return json.load(f)


def write(rel, text):
    os.makedirs(os.path.dirname(P(rel)), exist_ok=True)
    with open(P(rel), 'w', encoding='utf-8', newline='\n') as f:
        f.write(text if text.endswith('\n') else text + '\n')


def line_of(rel, pred):
    with open(P(rel), encoding='utf-8') as f:
        for i, l in enumerate(f, 1):
            row = json.loads(l)
            if pred(row):
                return i, row
    raise LookupError(rel)


def probe(cell):
    return jload('out', 'probe', '0.17.0', cell, 'summary.json')


def main():
    fs10, fs6, sf6, sf10, off = (probe(c) for c in ('FS-10-1', 'FS-6-1', 'SF-6-1', 'SF-10-1', 'SF-offered-1'))
    scores = jload('out', 'runs', 'SCORES.json')
    runs = scores['runs']
    refusal = sf10['batch2']['failed']['error']
    write('out/evidence/refusal.txt', refusal)
    total = sum(r['cost_usd'] for r in runs)
    n = {
        'fs10_sc_volume': f"{fs10['sc_volume_mm3']:.2f}",
        'fs10_expected_volume': f"{fs10['expected_volume']:.2f}",
        'fs10_volume_pct': f"{fs10['sc_vs_expected_pct']:+.4f}",
        'fs_wall': f"{fs6['stl']['wall_mm']:.4f}",
        'sf6_wall_stl': f"{sf6['stl']['wall_mm']:.4f}",
        'sf6_wall_sc': f"{sf6['sc_wall']['radius_minus_axis_mm']:.4f}",
        'sf6_wall_sc_min': f"{sf6['sc_wall']['min_mm']:.4f}",
        'offered_radius': refusal.rsplit(' ', 2)[-2],
        'offered_wall_stl': f"{off['stl']['wall_mm']:.4f}",
        'offered_wall_sc': f"{off['sc_wall']['radius_minus_axis_mm']:.4f}",
        'runs': str(len(runs)),
        'runs_plain': str(sum(r['arm'] == 'plain' for r in runs)),
        'runs_named': str(sum(r['arm'] == 'named' for r in runs)),
        'plain_round_first': str(sum(r['arm'] == 'plain' and r['first_attempt_order'] == 'FS' for r in runs)),
        'named_round_first': str(sum(r['arm'] == 'named' and r['first_attempt_order'] == 'FS' for r in runs)),
        'refusals': str(sum(r['refusals'] for r in runs)),
        'runs_pass': str(sum(r['scored'] == 'pass' for r in runs)),
        'runs_total_usd': f'{total:.2f}',
        'model': runs[0]['model'], 'claude_version': runs[0]['claude_version'].split()[0],
        'run_wall': f"{runs[0]['part']['wall_mm']:.4f}",
    }
    write('out/evidence/numbers.json', json.dumps(n, indent=1))

    # terminals (<= 8 rows x 44 cols)
    write('video/terminal-refusal-clause.txt', refusal.split('; ')[-1])
    write('video/terminal-proof.txt', '\n'.join([
        'SolidCraft 0.17.0 · 80 x 60 x 30, wall 2',
        'corner wall at z = 15     STL     SolidCraft',
        f"round first, R10       {n['fs_wall']:>7}   {n['fs_wall']:>7}",
        f"shell first, R6        {n['sf6_wall_stl']:>7}   {n['sf6_wall_sc']:>7}",
        f"shell first, R{n['offered_radius']:<6}   {n['offered_wall_stl']:>7}   {n['offered_wall_sc']:>7}",
        f"volume R10 {n['fs10_sc_volume']} mm3",
        f"hand count {n['fs10_expected_volume']} ({n['fs10_volume_pct']}%)",
    ]))
    write('video/terminal-runs.txt', '\n'.join([
        f"Claude Code {n['claude_version']} · {n['model']}",
        f"plain prompt: rounded first {n['plain_round_first']} of {n['runs_plain']}",
        f"named order:  rounded first {n['named_round_first']} of {n['runs_named']}",
        f"refused: {n['refusals']} · parts in spec: {n['runs_pass']} of {n['runs']}",
        f"total cost: ${n['runs_total_usd']} at API prices",
    ]))
    write('video/terminal-prompts.txt', '\n'.join([
        'both: an open-top box, 80 x 60 x 30 mm,',
        'walls and floor 2 mm, corners 10 mm',
        'named adds one sentence:',
        '"Round the corners before you hollow it',
        'out."',
    ]))
    write('video/rule-card.txt', '\n'.join(['SolidCraft 0.17', '1. Round first, then shell',
                                            '2. Its offered radius can be too thin', '3. Measure the wall']))

    # toolcall panels (args: compact JSON <= 160; result <= 60)
    compact = lambda o: json.dumps(o, separators=(',', ':'))  # noqa: E731
    la, ra = line_of('out/steps/batch-shell-then-fillet.jsonl', lambda r: r['dir'] == 'server->client'
                     and 'failed' in (r['msg'].get('result', {}).get('content', [{}])[0].get('text', '')))
    lb, rb = line_of('out/steps/batch-fillet-then-shell.jsonl', lambda r: r['dir'] == 'server->client'
                     and '"completed"' in (r['msg'].get('result', {}).get('content', [{}])[0].get('text', '')))
    body_a = json.loads(ra['msg']['result']['content'][0]['text'])
    body_b = json.loads(rb['msg']['result']['content'][0]['text'])
    steps_a = jload('steps', 'shell-then-fillet.json')['commands']
    calls = [
        {'id': 'toolcall-1-refused', 'tool': 'batch', 'src': f'out/steps/batch-shell-then-fillet.jsonl#L{la}',
         'args': compact(steps_a[5]), 'args_note': 'commands[5] of 6 (the failing step)',
         'result': f"ok: {str(body_a['ok']).lower()} · failed.command {body_a['failed']['command']}",
         'also': {'rolled_back': body_a['rolled_back'], 'undone': body_a['undone'], 'failed.index': body_a['failed']['index']}},
        {'id': 'toolcall-3-built', 'tool': 'batch', 'src': f'out/steps/batch-fillet-then-shell.jsonl#L{lb}',
         'args': compact(jload('steps', 'fillet-then-shell.json')['commands'][4]), 'args_note': 'commands[4] of 6',
         'result': f"ok: {str(body_b['ok']).lower()} · completed: {body_b['completed']}"},
        {'id': 'toolcall-4-measure', 'tool': 'measure', 'src': 'out/probe/0.17.0/FS-10-1/measure.json',
         'args': '{}', 'result': f"volume_mm3: {n['fs10_sc_volume']}"},
        {'id': 'toolcall-gob-sf6', 'tool': 'batch', 'src': 'out/probe/0.17.0/SF-6-1/batch2_reply.json',
         'args': compact(jload('out', 'probe', '0.17.0', 'SF-6-1', 'batch2_request.json')['commands'][0]),
         'result': 'ok: true · warning: null'},
        {'id': 'toolcall-gob-offered', 'tool': 'batch', 'src': 'out/probe/0.17.0/SF-offered-1/batch2_reply.json',
         'args': compact(jload('out', 'probe', '0.17.0', 'SF-offered-1', 'batch2_request.json')['commands'][0]),
         'result': 'ok: true · warning: null'},
    ]
    for c in calls:
        assert len(c['args']) <= 160 and len(c['result']) <= 60, c['id']
    write('video/toolcalls.json', json.dumps(calls, indent=1, ensure_ascii=False))

    # JSON view cards (cols 44; one pinned transcript line each)
    lp, _ = line_of('out/set_parameter/transcript.jsonl', lambda r: r['dir'] == 'client->server'
                    and r['msg'].get('params', {}).get('name') == 'set_parameter')
    lq, _ = line_of('out/steps/batch-shell-then-fillet.jsonl', lambda r: r['dir'] == 'client->server'
                    and r['msg'].get('params', {}).get('name') == 'batch')
    cards = [
        {'id': 'json-2-wall', 'src': f'out/set_parameter/transcript.jsonl#L{lp}', 'source_kind': 'no-AI test',
         'view': {'reformat': 'pretty', 'at': '/msg/params/arguments', 'cols': 44},
         'focusKey': '/msg/params/arguments/value', 'focusValue': 2, 'spoken': 'value, two'},
        {'id': 'json-1a-shell', 'src': f'out/steps/batch-shell-then-fillet.jsonl#L{lq}', 'source_kind': 'no-AI test',
         'view': {'reformat': 'pretty', 'at': '/msg/params/arguments/commands', 'items': [4, 4], 'cols': 44},
         'mark': 'solid.shell'},
        {'id': 'json-1b-fillet', 'src': f'out/steps/batch-shell-then-fillet.jsonl#L{lq}', 'source_kind': 'no-AI test',
         'view': {'reformat': 'pretty', 'at': '/msg/params/arguments/commands/5/params', 'cols': 44},
         'note': 'the whole step (items [5, 5]) is 14 rows at 44 cols: the card shows its params; the path row names step 5',
         'focusKey': '/msg/params/arguments/commands/5/params/radius', 'focusValue': 10, 'spoken': 'radius, ten'},
    ]
    write('video/json-cards.json', json.dumps(cards, indent=1, ensure_ascii=False))
    print(json.dumps(n, indent=1))


if __name__ == '__main__':
    main()
