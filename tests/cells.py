"""Probe cells as a library for the lab tests (the same two-batch cell as probe/probe.py), with a logged client: every
JSON-RPC message the client sends is written as sent (`{"t", "seq", "dir", "msg"}`, the proxy's line shape), and every
reply with image data replaced by its size and SHA-256."""
import base64
import datetime
import hashlib
import json
import math
import os
import re
import tempfile

from mcp_client import McpClient, SERVER_CMD
from measure_box import measure_stl, sf_breach_radius, sf_volume, shelled_volume

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
EXPORT_DIR = '/lab/out'   # the server's --allow-path


def fillet(r):
    return {'command': 'solid.fillet', 'params': {'edges': EDGES, 'radius': r}}


def shell():
    return {'command': 'solid.shell', 'params': {'faces': TOP, 'thickness': T}}


def offered_radius(err):
    m = re.search(r'largest radius that fits is ([0-9]+(?:\.[0-9]+)?) mm', err or '')
    return float(m.group(1)) if m else None


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')


class LoggedClient(McpClient):
    def __init__(self, cmd, log):
        super().__init__(cmd)
        self.log = log
        self.seq = 0

    def _w(self, d, msg):
        self.seq += 1
        self.log.write(json.dumps({'t': _now(), 'seq': self.seq, 'dir': d, 'msg': msg}, ensure_ascii=False) + '\n')
        self.log.flush()

    def _send(self, msg):
        self._w('client->server', msg)
        super()._send(msg)

    def request(self, method, params):
        res = super().request(method, params)
        r = json.loads(json.dumps(res))
        for b in r.get('content', []) if isinstance(r, dict) else []:
            if b.get('type') == 'image' and isinstance(b.get('data'), str):
                raw = base64.b64decode(b['data'])
                b['data'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self._w('server->client', {'jsonrpc': '2.0', 'id': self.next_id, 'result': r})
        return res


def text_json(r):
    t = '\n'.join(b['text'] for b in r.get('content', []) if b.get('type') == 'text')
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return t


class Lab:
    def __init__(self, name, log_path=None):
        self.name = name
        self.log = open(log_path or os.devnull, 'w', encoding='utf-8')
        self.c = LoggedClient(SERVER_CMD, self.log)
        self.c.start()

    def close(self):
        self.c.close()
        self.log.close()

    def server_version(self):
        return (self.c.init_result.get('serverInfo') or {}).get('version')

    def call(self, name, args):
        return self.c.call_tool(name, args)

    def call_json(self, name, args):
        r = self.call(name, args)
        return {'isError': r.get('isError', False), 'body': text_json(r)}

    def _md5_png(self):
        r = self.call('screenshot', CAMERA)
        img = next((b for b in r.get('content', []) if b.get('type') == 'image'), None)
        return hashlib.md5(base64.b64decode(img['data'])).hexdigest() if img else None

    def _timeline(self):
        insp = text_json(self.call('inspect_design', {}))
        return [{k: f.get(k) for k in ('name', 'type', 'error', 'warning')} for f in insp.get('timeline', [])]

    def cell(self, order, r):
        """Two batches (PLAN v2 D7): sketch -> extrude -> first step; then the second step alone."""
        res = {'order': order, 'R': r}
        self.call('new_design', {'name': f'{order}-{r}'})
        first, second = (fillet(r), shell()) if order == 'FS' else (shell(), fillet(r))
        self.call_json('batch', {'commands': BASE + [first]})
        res['stage1_md5'] = self._md5_png()
        res['timeline_before'] = self._timeline()
        b2 = self.call_json('batch', {'commands': [second]})
        body = b2['body'] if isinstance(b2['body'], dict) else {}
        res['batch2'] = {'isError': b2['isError'], **{k: body.get(k) for k in ('ok', 'completed', 'failed', 'rolled_back', 'undone')}}
        results = body.get('results') or []
        res['batch2']['warning'] = results[-1].get('warning') if results and isinstance(results[-1], dict) else None
        res['timeline_after'] = self._timeline()
        m = text_json(self.call('measure', {}))
        res['sc_volume_mm3'] = m['total']['volume_mm3']
        res['final_md5'] = self._md5_png()
        if body.get('ok'):
            path = f'{EXPORT_DIR}/{self.name}-{order}-{r}.stl'
            self.call('export', {'path': path})
            ms = measure_stl(path)
            res['stl'] = {'volume_mm3': ms['volume_mm3'], 'wall_mm': ms['corner_wall']['wall_mm'], 'size': ms['size']}
            res['sc_wall'] = self._sc_wall(m['bodies'][0]['name'], r, order)
        return res

    def _sc_wall(self, body, r, order):
        topo = text_json(self.call('body_topology', {'body': body}))
        cyl = [f for f in topo['faces'] if f.get('cylinder') and f['centroid'][0] > 0 and f['centroid'][1] > 0]
        outer = next(f for f in cyl if abs(f['cylinder']['radius'] - r) < 0.01)
        a = {'type': 'face', 'body': body, 'index': outer['index'], 'point': outer['point']}
        if order == 'FS' and r > T:
            inner = next(f for f in cyl if abs(f['cylinder']['radius'] - (r - T)) < 0.01)
            b = {'type': 'face', 'body': body, 'index': inner['index'], 'point': inner['point']}
        else:
            e = next(e for e in topo['edges'] if abs(e['mid'][0] - (W / 2 - T)) < 0.05
                     and abs(e['mid'][1] - (D / 2 - T)) < 0.05 and e['length'] > 10)
            b = {'type': 'edge', 'body': body, 'index': e['index'], 'point': e['mid']}
        m = text_json(self.call('measure', {'items': [a, b]}))
        items = m['items']
        r_in = items[1].get('radius', 0.0) if items[1].get('round') else 0.0
        return {'min_mm': m['min'], 'radius_minus_axis_mm': items[0]['radius'] - r_in - m['center_distance']}
