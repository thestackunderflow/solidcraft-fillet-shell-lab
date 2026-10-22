"""Score every agent run in out/runs/<arm>-<n>/ (PLAN v2 5.2): cost, turns, tool calls, failed calls with their error
text, the order of the fillet / shell steps (first attempt and what was finally built), the recovery after a refusal
(reorder / smaller radius / fit / rebuild / other / gave up), and the exported STL against the spec (bbox ±0.1 mm,
volume within 0.5% of the hand count for R = 10, corner wall >= 1.9 mm). Writes out/runs/SCORES.json.
A run whose transcript holds a proxy HANG row is scored "infra fail" (rows after it are void)."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tests'))

R_HERO = 10
SPEC = {'size': [80, 60, 30], 'wall_min': 1.9}


def _body(reply):
    res = (reply or {}).get('result') or {}
    text = '\n'.join(c.get('text', '') for c in res.get('content', []) if c.get('type') == 'text')
    try:
        return res.get('isError', False), json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return res.get('isError', False), text


def _cmds(tool, args):
    if tool == 'batch':
        return [c for c in args.get('commands', []) if isinstance(c, dict)]
    if tool == 'execute':
        return [{'command': args.get('command'), 'params': args.get('params') or {}}]
    return []


def analyse(rows):
    """rows: proxy transcript rows -> the order / recovery / refusal analysis."""
    hang = next((i for i, r in enumerate(rows) if r.get('dir') == 'proxy' and isinstance(r.get('msg'), dict)
                 and 'HANG' in r['msg']), None)
    if hang is not None:
        rows = rows[:hang]
    calls = [r['msg'] for r in rows if r.get('dir') == 'client->server' and isinstance(r.get('msg'), dict)
             and r['msg'].get('method') == 'tools/call']
    replies = {json.dumps(r['msg'].get('id')): r['msg'] for r in rows if r.get('dir') == 'server->client'
               and isinstance(r.get('msg'), dict) and 'id' in r['msg']}
    attempts, persisted, failed, refusals = [], [], [], []
    tools = []
    for ci, c in enumerate(calls):
        tool, args = c['params']['name'], c['params'].get('arguments') or {}
        tools.append(tool)
        is_err, body = _body(replies.get(json.dumps(c.get('id'))))
        if tool == 'new_design' and not is_err:
            persisted = []
            attempts.append({'call': ci, 'new_design': True})
            continue
        if tool == 'undo' and not is_err and persisted:
            persisted.pop()
        cmds = _cmds(tool, args)
        for k, cmd in enumerate(cmds):
            if cmd.get('command') in ('solid.fillet', 'solid.shell'):
                attempts.append({'call': ci, 'pos': k, 'command': cmd['command'], 'params': cmd.get('params') or {}})
        ok = (not is_err) and not (isinstance(body, dict) and body.get('ok') is False)
        if ok:
            persisted += cmds
        else:
            err = body.get('failed', {}).get('error') if isinstance(body, dict) and isinstance(body.get('failed'), dict) else str(body)[:400]
            fcmd = body.get('failed', {}).get('command') if isinstance(body, dict) and isinstance(body.get('failed'), dict) else (cmds[0]['command'] if len(cmds) == 1 else None)
            failed.append({'call': ci, 'tool': tool, 'command': fcmd, 'error': err})
            if isinstance(body, dict) and body.get('rolled_back') is False and isinstance(body.get('failed'), dict):
                persisted += cmds[:body['failed'].get('index', 0)]
            if fcmd == 'solid.fillet':
                refusals.append({'call': ci, 'error': err,
                                 'radius': next((x['params'].get('radius') for x in cmds if x.get('command') == 'solid.fillet'), None)})

    def order(seq):
        names = [s.get('command') for s in seq if s.get('command') in ('solid.fillet', 'solid.shell')]
        if 'solid.fillet' in names and 'solid.shell' in names:
            return 'FS' if names.index('solid.fillet') < names.index('solid.shell') else 'SF'
        if names:
            return 'fillet only' if names[0] == 'solid.fillet' else 'shell only'
        return 'neither'

    recovery = None
    if refusals:
        first = refusals[0]
        later = [a for a in attempts if a['call'] > first['call']]
        nxt = next((a for a in later if a.get('command') == 'solid.fillet'), None)
        rebuilt = any(a.get('new_design') for a in later if nxt is None or a['call'] <= nxt['call'])
        if nxt is None:
            recovery = 'gave up'
        elif 'fit' in nxt['params']:
            recovery = 'fit'
        else:
            same_call = [a for a in later if a['call'] == nxt['call'] and a.get('command')]
            shells_before = [a for a in later if a.get('command') == 'solid.shell' and a['call'] <= nxt['call']]
            if any(a['command'] == 'solid.shell' and a['pos'] > nxt['pos'] for a in same_call) or (
                    rebuilt and not shells_before):
                recovery = 'reorder'
            elif isinstance(nxt['params'].get('radius'), (int, float)) and isinstance(first['radius'], (int, float)) \
                    and nxt['params']['radius'] < first['radius']:
                recovery = 'smaller radius'
            elif rebuilt:
                recovery = 'rebuild'
            else:
                recovery = 'other'
    fil = [s for s in persisted if s.get('command') == 'solid.fillet']
    return {
        'tool_calls': len(calls), 'tools': tools, 'failed_calls': failed, 'refusals': len(refusals),
        'refusal_errors': [r['error'] for r in refusals],
        'first_attempt_order': order([a for a in attempts if a.get('command')]),
        'final_order': order(persisted), 'recovery': recovery,
        'final_fillet_radius': (fil[-1].get('params') or {}).get('radius') if fil else None,
        'final_fillet_fit': (fil[-1].get('params') or {}).get('fit') if fil else None,
        'hang': hang is not None,
    }


def budget_total(path):
    if not os.path.exists(path):
        return 0.0
    total = 0.0
    for line in open(path, encoding='utf-8'):
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 2 and not line.startswith('#'):
            total += float(parts[1])
    return round(total, 4)


def main():
    from measure_box import measure_stl, shelled_volume
    root = os.path.join(HERE, '..', 'out', 'runs')
    out_rows = []
    for d in sorted(glob.glob(os.path.join(root, '*-*'))):
        if not os.path.isdir(d) or not os.path.exists(os.path.join(d, 'run-meta.json')):
            continue
        meta = json.load(open(os.path.join(d, 'run-meta.json')))
        co = os.path.join(d, 'claude-output.json')
        out = json.load(open(co)) if os.path.exists(co) and os.path.getsize(co) else {}
        tp = os.path.join(d, 'transcript.jsonl')
        rows = [json.loads(l) for l in open(tp, encoding='utf-8')] if os.path.exists(tp) else []
        a = analyse(rows)
        stl = os.path.join(d, 'box.stl')
        exp_v = shelled_volume(80, 60, 30, R_HERO, 2)
        part = None
        if os.path.exists(stl):
            m = measure_stl(stl)
            size_ok = all(abs(m['size'][i] - SPEC['size'][i]) <= 0.1 for i in range(3))
            vol_pct = 100 * (m['volume_mm3'] / exp_v - 1)
            part = {'size': m['size'], 'volume_mm3': m['volume_mm3'], 'expected_volume_mm3': round(exp_v, 2),
                    'volume_vs_expected_pct': round(vol_pct, 4), 'wall_status': m['corner_wall']['status'],
                    'wall_mm': m['corner_wall']['wall_mm'],
                    'corner_r_fit': [c.get('r_fit') for c in m['corner_wall']['corners']],
                    'size_ok': size_ok, 'volume_ok': abs(vol_pct) <= 0.5,
                    'wall_ok': m['corner_wall']['wall_mm'] >= SPEC['wall_min']}
            part['pass'] = part['size_ok'] and part['volume_ok'] and part['wall_ok']
        out_rows.append({'run': os.path.basename(d), 'arm': meta['arm'], 'exit': meta['exit'], 'wall_s': meta['wall_s'],
                         'model': meta['model'], 'claude_version': meta['claude_version'],
                         'cost_usd': out.get('total_cost_usd'), 'cost_kind': 'logged' if out else 'killed (>= 1.50 counted)',
                         'turns': out.get('num_turns'), **a, 'part': part,
                         'scored': 'infra fail' if a['hang'] else ('pass' if part and part['pass'] else 'fail'),
                         'final_text': (out.get('result') or '')[:2000]})
    res = {'runs': out_rows, 'budget_log_total_usd': budget_total(os.path.join(root, 'BUDGET.log'))}
    json.dump(res, open(os.path.join(root, 'SCORES.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for r in out_rows:
        print(r['run'], r['cost_usd'], r['tool_calls'], 'calls', len(r['failed_calls']), 'failed', 'first', r['first_attempt_order'],
              'final', r['final_order'], 'recovery', r['recovery'], 'R', r['final_fillet_radius'],
              'wall', (r['part'] or {}).get('wall_mm'), r['scored'])
    print('budget total', res['budget_log_total_usd'])


if __name__ == '__main__':
    main()
