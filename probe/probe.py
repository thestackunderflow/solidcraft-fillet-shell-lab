"""THE PROBE (no AI, $0): fillet-then-shell vs shell-then-fillet on SolidCraft, over MCP (JSON-RPC over stdio, no SDK).

    docker run --rm -v <lab>:/work -v <lab>/out/probe/<ver>:/lab/out -w /work solidcraft-fillet-shell-lab:<ver> \
        python3 probe/probe.py <ver> deciding|all [reps]

PLAN v2 section 4. Each cell: a fresh new_design and TWO batches: (1) sketch -> extrude -> the first of fillet / shell,
rendered as stage1.png; (2) the second step alone. Every SolidCraft call has a 120 s client-side timeout; a HANG kills
the server and marks the cell. Every request and reply goes to <cell>/calls.jsonl (images saved as PNGs).
The wall is measured two ways: the STL slice + circle fit (tests/measure_box.py) and SolidCraft's own `measure` min
distance between the fillet's face and the inner corner (edge or round face).
"""
import base64
import datetime
import hashlib
import json
import math
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tests'))
from mcp_client import Hang, McpClient, SERVER_CMD  # noqa: E402
from measure_box import measure_stl, sf_breach_radius, sf_volume, shelled_volume  # noqa: E402

VER = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else 'deciding'
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
OUT = '/lab/out'          # = out/probe/<ver> on the host; the server may write here (--allow-path)
W, D, H, T = 80, 60, 30, 2
EDGES = [[40, 30, 15], [-40, 30, 15], [-40, -30, 15], [40, -30, 15]]
TOP = [[0, 0, 30]]
BASE = [
    {'command': 'sketch.create', 'params': {'plane': 'XY'}},
    {'command': 'sketch.rectangle.center', 'params': {'center': [0, 0], 'corner': [40, 30]}},
    {'command': 'sketch.finish', 'params': {}},
    {'command': 'solid.extrude', 'params': {'distance': H}},
]
CAMERA = {'view': 'iso', 'width': 960, 'height': 600}


def fillet(r, **extra):
    return {'command': 'solid.fillet', 'params': {'edges': EDGES, 'radius': r, **extra}}


def shell():
    return {'command': 'solid.shell', 'params': {'faces': TOP, 'thickness': T}}


class Session:
    def __init__(self):
        self.c = None
        self.log = None
        self.seq = 0

    def ensure(self):
        if self.c is None or self.c.proc.poll() is not None:
            self.c = McpClient(SERVER_CMD)
            self.c.start()
        return self.c

    def call(self, name, args):
        c = self.ensure()
        self._w('client->server', {'method': 'tools/call', 'params': {'name': name, 'arguments': args}})
        try:
            r = c.call_tool(name, args)
        except Hang as e:
            self._w('client', {'HANG': str(e)})
            c.kill()
            self.c = None
            raise
        self._w('server->client', self._strip(r))
        return r

    def _strip(self, r):
        r = json.loads(json.dumps(r))
        for b in r.get('content', []):
            if b.get('type') == 'image':
                raw = base64.b64decode(b['data'])
                b['data'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        return r

    def _w(self, d, msg):
        self.seq += 1
        if self.log:
            self.log.write(json.dumps({'t': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds'),
                                       'seq': self.seq, 'dir': d, 'msg': msg}, ensure_ascii=False) + '\n')
            self.log.flush()


S = Session()


def text_json(r):
    t = '\n'.join(b['text'] for b in r.get('content', []) if b.get('type') == 'text')
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return t


def save(d, name, obj):
    with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write('\n')


def png(d, name, r):
    img = next((b for b in r.get('content', []) if b.get('type') == 'image'), None)
    if not img:
        return None
    raw = base64.b64decode(img['data'])
    with open(os.path.join(d, name), 'wb') as f:
        f.write(raw)
    return hashlib.md5(raw).hexdigest()


def timeline(insp):
    if not isinstance(insp, dict):
        return insp
    return [{k: f.get(k) for k in ('name', 'type', 'error', 'warning', 'suppressed', 'rolled_back')}
            for f in insp.get('timeline', [])]


def body_name(m):
    try:
        return m['bodies'][0]['name']
    except (KeyError, IndexError, TypeError):
        return None


def sc_wall(d, body, r, order):
    """SolidCraft's own corner-wall measurement at the (+x, +y) corner: `measure` min distance between the outer
    round (cylindrical face, radius ~ r) and the inner corner (SF: the inner vertical edge at (38, 28);
    FS: the inner round face, radius ~ r - t)."""
    topo = text_json(S.call('body_topology', {'body': body}))
    save(d, 'body_topology.json', topo)
    if not isinstance(topo, dict):
        return {'error': 'no topology', 'raw': str(topo)[:300]}
    faces = topo.get('faces', [])
    cyl = [f for f in faces if f.get('cylinder')]

    def near(f, x, y):
        p = f.get('centroid') or f.get('point')
        return p and p[0] * x > 0 and p[1] * y > 0
    outer = [f for f in cyl if near(f, 1, 1) and abs(f['cylinder']['radius'] - r) < 0.5]
    res = {'cylinder_radii': sorted({round(f['cylinder']['radius'], 4) for f in cyl})}
    if not outer:
        res['error'] = 'no outer round face found'
        return res
    of = outer[0]
    a = {'type': 'face', 'body': body, 'index': of['index'], 'point': of['point']}
    if order == 'FS' and r > T:
        inner = [f for f in cyl if near(f, 1, 1) and abs(f['cylinder']['radius'] - (r - T)) < 0.5]
        if not inner:
            res['error'] = 'no inner round face found'
            return res
        b = {'type': 'face', 'body': body, 'index': inner[0]['index'], 'point': inner[0]['point']}
    else:
        edges = topo.get('edges', [])
        cand = [e for e in edges if e.get('mid') and abs(e['mid'][0] - (W / 2 - T)) < 0.05
                and abs(e['mid'][1] - (D / 2 - T)) < 0.05 and e.get('length', 0) > 10]
        if not cand:
            res['error'] = 'no inner corner edge found'
            return res
        b = {'type': 'edge', 'body': body, 'index': cand[0]['index'], 'point': cand[0]['mid']}
    m = text_json(S.call('measure', {'items': [a, b]}))
    save(d, 'sc_measure_wall.json', {'items': [a, b], 'reply': m})
    res.update({'outer_face_radius': of['cylinder']['radius'], 'items': [a, b], 'reply': m})
    if isinstance(m, dict):
        # `min`: SolidCraft's two-item min distance. Also from its own numbers: the round's radius minus the distance
        # from its axis to the inner corner edge (SF), or minus the inner round's radius and the axis offset (FS).
        res['min_mm'] = m.get('min')
        items = m.get('items') or []
        r_out = items[0].get('radius') if items else None
        cd = m.get('center_distance')
        if r_out is not None and cd is not None:
            r_in = items[1].get('radius', 0.0) if len(items) > 1 and items[1].get('round') else 0.0
            res['radius_minus_axis_mm'] = r_out - r_in - cd
            res['sc_radii'] = [r_out, r_in]
            res['center_distance'] = cd
    return res


def run_cell(name, order, r, rep, first_extra=None, second_extra=None, second_override=None):
    d = os.path.join(OUT, f'{name}-{rep}')
    os.makedirs(d, exist_ok=True)
    S.log = open(os.path.join(d, 'calls.jsonl'), 'w', encoding='utf-8')
    S.seq = 0
    res = {'cell': name, 'order': order, 'R': r, 'rep': rep, 'version': VER}
    t0 = time.time()
    try:
        S.call('new_design', {'name': f'{name}-{rep}'})
        if order == 'FS':
            first, second = fillet(r, **(first_extra or {})), shell()
        else:
            first, second = shell(), fillet(r, **(second_extra or {}))
        if second_override:
            second = second_override
        b1 = {'commands': BASE + [first]}
        r1 = S.call('batch', b1)
        save(d, 'batch1_request.json', b1)
        save(d, 'batch1_reply.json', {'isError': r1.get('isError', False), 'body': text_json(r1)})
        res['batch1'] = {'isError': r1.get('isError', False), 'ok': (text_json(r1) or {}).get('ok') if isinstance(text_json(r1), dict) else None}
        res['stage1_md5'] = png(d, 'stage1.png', S.call('screenshot', CAMERA))
        before = text_json(S.call('inspect_design', {}))
        save(d, 'inspect_before.json', before)
        b2 = {'commands': [second]}
        r2 = S.call('batch', b2)
        body2 = text_json(r2)
        save(d, 'batch2_request.json', b2)
        save(d, 'batch2_reply.json', {'isError': r2.get('isError', False), 'body': body2})
        res['batch2'] = {'isError': r2.get('isError', False)}
        if isinstance(body2, dict):
            res['batch2'].update({k: body2.get(k) for k in ('ok', 'completed', 'failed', 'rolled_back', 'undone')})
            if body2.get('results'):
                last = body2['results'][-1] if isinstance(body2['results'], list) else body2['results']
                if isinstance(last, dict):
                    res['batch2']['result_keys'] = sorted(last)
                    for k in ('radius_applied', 'radii_applied', 'warning', 'warnings'):
                        if k in last:
                            res['batch2'][k] = last[k]
        else:
            res['batch2']['text'] = str(body2)[:800]
        after = text_json(S.call('inspect_design', {}))
        save(d, 'inspect_after.json', after)
        res['timeline_before'] = timeline(before)
        res['timeline_after'] = timeline(after)
        res['timeline_unchanged'] = timeline(before) == timeline(after)
        m = text_json(S.call('measure', {}))
        save(d, 'measure.json', m)
        if isinstance(m, dict):
            res['sc_volume_mm3'] = (m.get('total') or {}).get('volume_mm3')
        res['final_md5'] = png(d, 'final.png', S.call('screenshot', CAMERA))
        ex = S.call('export', {'path': f'/lab/out/{name}-{rep}/box.stl'})
        res['export'] = {'isError': ex.get('isError', False)}
        stl = os.path.join(d, 'box.stl')
        if os.path.exists(stl):
            ms = measure_stl(stl)
            save(d, 'stl_measure.json', ms)
            res['stl'] = {'size': ms['size'], 'volume_mm3': ms['volume_mm3'], 'wall_status': ms['corner_wall']['status'],
                          'wall_mm': ms['corner_wall']['wall_mm'],
                          'corner_r_fit': [c.get('r_fit') for c in ms['corner_wall']['corners']],
                          'raw_polyline_mm': [c.get('raw_polyline_mm') for c in ms['corner_wall']['corners']],
                          'sagitta_mm': [c.get('sagitta_mm') for c in ms['corner_wall']['corners']]}
        ok2 = isinstance(body2, dict) and body2.get('ok') is True
        built = 'FS' if order == 'FS' else 'SF'
        rr = res['batch2'].get('radius_applied') or r
        if ok2:
            res['sc_wall'] = sc_wall(d, body_name(m), rr if isinstance(rr, (int, float)) else r, built)
        # the hand geometry for what was built
        if ok2 and isinstance(rr, (int, float)):
            if built == 'FS':
                res['expected_volume'] = round(shelled_volume(W, D, H, rr, T), 3)
                res['expected_wall'] = 2.0
            elif rr < sf_breach_radius(T):
                res['expected_volume'] = round(sf_volume(W, D, H, rr, T), 3)
                res['expected_wall'] = round(min(rr - (rr - T) * math.sqrt(2), T), 4)
            if res.get('expected_volume') and res.get('stl'):
                res['stl_vs_expected_pct'] = round(100 * (res['stl']['volume_mm3'] / res['expected_volume'] - 1), 4)
            if res.get('expected_volume') and res.get('sc_volume_mm3'):
                res['sc_vs_expected_pct'] = round(100 * (res['sc_volume_mm3'] / res['expected_volume'] - 1), 4)
    except Hang as e:
        res['HANG'] = str(e)
    except Exception as e:  # noqa: BLE001 - recorded, the probe goes on
        res['exception'] = f'{type(e).__name__}: {e}'
    res['wall_s'] = round(time.time() - t0, 2)
    save(d, 'summary.json', res)
    S.log.close()
    S.log = None
    print(json.dumps({k: res.get(k) for k in ('cell', 'rep', 'batch2', 'stl', 'sc_wall', 'expected_wall', 'HANG', 'exception')},
                     default=str)[:900], flush=True)
    return res


def offered_radius(err):
    m = re.search(r'largest radius[^0-9]*([0-9]+(?:\.[0-9]+)?)', err or '')
    return float(m.group(1)) if m else None


def p4(rep):
    """Sub-probe P4 (producer MF7): screw bosses on the shelled floor and a lip on the rounded rim of the FS-10 box."""
    d = os.path.join(OUT, f'P4-{rep}')
    os.makedirs(d, exist_ok=True)
    S.log = open(os.path.join(d, 'calls.jsonl'), 'w', encoding='utf-8')
    res = {'cell': 'P4', 'rep': rep, 'version': VER}
    try:
        S.call('new_design', {'name': 'P4'})
        r0 = S.call('batch', {'commands': BASE + [fillet(10), shell()]})
        res['box'] = text_json(r0).get('ok') if isinstance(text_json(r0), dict) else str(text_json(r0))[:300]
        bosses = {'commands': [{'command': 'plastic.boss', 'params': {'position': [x, y, 2], 'diameter': 7, 'height': 12,
                                                                       'hole_diameter': 2.5}}
                               for x, y in [(-30, -20), (30, -20), (30, 20), (-30, 20)]]}
        rb = S.call('batch', bosses)
        save(d, 'bosses_request.json', bosses)
        save(d, 'bosses_reply.json', {'isError': rb.get('isError', False), 'body': text_json(rb)})
        bb = text_json(rb)
        res['bosses'] = {k: bb.get(k) for k in ('ok', 'completed', 'failed')} if isinstance(bb, dict) else str(bb)[:400]
        m = text_json(S.call('measure', {}))
        res['volume_after_bosses'] = (m.get('total') or {}).get('volume_mm3') if isinstance(m, dict) else None
        png(d, 'bosses.png', S.call('screenshot', CAMERA))
        lip = {'commands': [{'command': 'plastic.lip', 'params': {'face': [39, 0, 30], 'width': 1, 'height': 2}}]}
        rl = S.call('batch', lip)
        save(d, 'lip_request.json', lip)
        save(d, 'lip_reply.json', {'isError': rl.get('isError', False), 'body': text_json(rl)})
        lb = text_json(rl)
        res['lip'] = {k: lb.get(k) for k in ('ok', 'completed', 'failed')} if isinstance(lb, dict) else str(lb)[:400]
        insp = text_json(S.call('inspect_design', {}))
        save(d, 'inspect.json', insp)
        res['timeline'] = timeline(insp)
        m = text_json(S.call('measure', {}))
        res['volume_after_lip'] = (m.get('total') or {}).get('volume_mm3') if isinstance(m, dict) else None
        png(d, 'lip.png', S.call('screenshot', CAMERA))
        S.call('export', {'path': f'/lab/out/P4-{rep}/p4.stl'})
    except Hang as e:
        res['HANG'] = str(e)
    except Exception as e:  # noqa: BLE001
        res['exception'] = f'{type(e).__name__}: {e}'
    save(d, 'summary.json', res)
    S.log.close()
    S.log = None
    print(json.dumps(res, default=str)[:1500], flush=True)
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    results = []
    # determinism of renders: the same state twice
    reps = range(1, REPS + 1)
    for rep in reps:
        results.append(run_cell('FS-10', 'FS', 10, rep))
        results.append(run_cell('FS-6', 'FS', 6, rep))
        results.append(run_cell('SF-6', 'SF', 6, rep))
        sf10 = run_cell('SF-10', 'SF', 10, rep)
        results.append(sf10)
        err = ((sf10.get('batch2') or {}).get('failed') or {}).get('error') if isinstance((sf10.get('batch2') or {}).get('failed'), dict) else None
        off = offered_radius(err)
        if off is not None:
            r = run_cell('SF-offered', 'SF', off, rep)
            r['offered_from_error'] = err
            save(os.path.join(OUT, f'SF-offered-{rep}'), 'summary.json', r)
            results.append(r)
        else:
            results.append({'cell': 'SF-offered', 'rep': rep, 'skipped': 'no radius in the SF-10 error', 'error': err})
    if MODE == 'all':
        for r in [2, 4, 5, 6.5, 7, 25]:
            results.append(run_cell(f'SF-{r}', 'SF', r, 1))
        results.append(run_cell('SF-fit-reduce', 'SF', 10, 1, second_extra={'fit': 'reduce'}))
        results.append(run_cell('SF-fit-taper', 'SF', 10, 1, second_extra={'fit': 'taper'}))
        results.append(run_cell('RIM', 'FS', 6, 1, second_override={'command': 'solid.fillet',
                                                                  'params': {'edges': [[40, 0, 30]], 'radius': 25}}))
        results.append(p4(1))
    save(OUT, f'probe-results-{MODE}.json', results)
    if S.c:
        S.c.close()


if __name__ == '__main__':
    main()
