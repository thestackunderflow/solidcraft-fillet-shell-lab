"""The box measurer (NumPy only): volume, bounding box and the corner wall of an exported STL.

The corner wall is measured on a slice at z (default 15 mm, mid-height): the slice gives the outer and the inner loop;
at each corner a least-squares circle (Kasa, as in solidcraft-resize-lab/tests/measure_plate.py) is fitted to the
outer loop's arc vertices. A tessellator puts vertices on the true arc, so the fit recovers the true radius and centre
whatever the chord count; the nearest-polyline distance (which reads low between vertices) is reported beside it,
with the arc's largest sagitta.
"""
import math
import struct

import numpy as np


# ---- STL ----------------------------------------------------------------------------------------------------------
def read_stl(path):
    """Triangles as an (n, 3, 3) array; binary or ASCII STL."""
    data = open(path, 'rb').read()
    if data[:5] == b'solid' and b'facet' in data[:400]:
        v = [list(map(float, l.split()[1:4])) for l in data.decode('ascii', 'replace').splitlines()
             if l.strip().startswith('vertex')]
        return np.array(v).reshape(-1, 3, 3)
    n = struct.unpack('<I', data[80:84])[0]
    a = np.frombuffer(data, dtype=np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')]), count=n, offset=84)
    return a['v'].reshape(-1, 3, 3).astype(float)


def volume(tris):
    return float(np.einsum('ij,ij->i', tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6.0)


def bbox(tris):
    p = tris.reshape(-1, 3)
    return p.min(0).tolist(), p.max(0).tolist()


# ---- hand geometry (ACCURACY G1, G3) --------------------------------------------------------------------------------
def shelled_volume(w, d, h, r, t):
    """Fillet then shell: outer rounded r, inner pocket offset by t (radius r - t, sharp when r <= t), open top."""
    ri = max(r - t, 0.0)
    outer = (w * d - (4 - math.pi) * r * r) * h
    inner = ((w - 2 * t) * (d - 2 * t) - (4 - math.pi) * ri * ri) * (h - t)
    return outer - inner


def sf_breach_radius(t):
    """The radius at which an outer round reaches a sharp inner corner: t*sqrt2/(sqrt2-1) (6.83 for t = 2)."""
    return t * math.sqrt(2) / (math.sqrt(2) - 1)


def sf_volume(w, d, h, r, t):
    """Shell then fillet the outer vertical edges: outer rounded r, inner pocket sharp. Valid only below the breach."""
    if r >= sf_breach_radius(t):
        raise ValueError(f'r = {r} breaks through a {t} mm wall (limit {sf_breach_radius(t):.3f})')
    return (w * d - (4 - math.pi) * r * r) * h - (w - 2 * t) * (d - 2 * t) * (h - t)


# ---- slicing ------------------------------------------------------------------------------------------------------
def slice_loops(tris, z):
    """Closed loops (lists of 2-D points) where the plane Z = z cuts the mesh."""
    z = z + 1e-7  # never exactly on a vertex
    segs = []
    for tri in tris:
        d = tri[:, 2] - z
        pts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            da, db = d[i], d[(i + 1) % 3]
            if (da < 0) != (db < 0):
                s = da / (da - db)
                pts.append(a[:2] + s * (b[:2] - a[:2]))
        if len(pts) == 2:
            segs.append(pts)
    key = lambda p: (round(float(p[0]), 5), round(float(p[1]), 5))  # noqa: E731
    adj = {}
    for a, b in segs:
        ka, kb = key(a), key(b)
        if ka == kb:
            continue
        adj.setdefault(ka, []).append(kb)
        adj.setdefault(kb, []).append(ka)
    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        if len(loop) >= 3:
            loops.append(_drop_collinear(np.array(loop, dtype=float)))
    return loops


def _drop_collinear(loop, tol=1e-4):
    """Remove slice points that lie on the straight segment between their neighbours. A triangle's diagonal across a
    flat facet crosses the plane mid-chord: that point is on the chord, not on the arc, and would bias a circle fit."""
    while len(loop) > 3:
        prev, nxt = np.roll(loop, 1, axis=0), np.roll(loop, -1, axis=0)
        cross = np.abs((loop[:, 0] - prev[:, 0]) * (nxt[:, 1] - prev[:, 1]) - (loop[:, 1] - prev[:, 1]) * (nxt[:, 0] - prev[:, 0]))
        span = np.hypot(*(nxt - prev).T)
        bad = cross / np.maximum(span, 1e-30) < tol
        if not bad.any():
            break
        i = int(np.argmax(bad))
        loop = np.delete(loop, i, axis=0)
    return loop


def _area(loop):
    x, y = loop[:, 0], loop[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _inside(pt, loop):
    x, y = pt
    xs, ys = loop[:, 0], loop[:, 1]
    xs2, ys2 = np.roll(xs, -1), np.roll(ys, -1)
    cross = ((ys > y) != (ys2 > y)) & (x < (xs2 - xs) * (y - ys) / np.where(ys2 == ys, 1e-30, ys2 - ys) + xs)
    return bool(np.count_nonzero(cross) % 2)


def fit_circle(pts):
    """Least-squares circle (Kasa): (cx, cy, r)."""
    x, y = pts[:, 0], pts[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    cx, cy, c = np.linalg.lstsq(A, x * x + y * y, rcond=None)[0]
    return float(cx), float(cy), float(math.sqrt(c + cx * cx + cy * cy))


def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip(np.einsum('ij,ij->i', p - a, ab) / np.maximum(np.einsum('ij,ij->i', ab, ab), 1e-30), 0, 1)
    return np.hypot(*(a + t[:, None] * ab - p).T)


def _arc_points(loop, sx, sy, lo, hi, tol=1e-4):
    """Vertices of the loop in the (sx, sy) quadrant that are on neither straight side (so on the corner arc)."""
    xmax, ymax = (hi[0], hi[1]) if sx > 0 else (-lo[0], hi[1])
    xmax = hi[0] if sx > 0 else -lo[0]
    ymax = hi[1] if sy > 0 else -lo[1]
    q = loop[(np.sign(loop[:, 0]) == sx) & (np.sign(loop[:, 1]) == sy)]
    m = (xmax - np.abs(q[:, 0]) > tol) & (ymax - np.abs(q[:, 1]) > tol)
    return q[m], xmax, ymax


def corner_wall(tris, z=15.0):
    """The thinnest wall at the four vertical corners, from a slice at z. Returns a dict:
    status OK | BREACHED, wall_mm (the minimum of the corners and the straight walls), corners[...]."""
    loops = slice_loops(tris, z)
    loops = [l for l in loops if abs(_area(l)) > 1.0]
    nested = None
    if len(loops) == 2:
        a, b = sorted(loops, key=lambda l: -abs(_area(l)))
        if _inside(b[0], a):
            nested = (a, b)
    if nested is None:
        return {'status': 'BREACHED', 'wall_mm': 0.0, 'loops': len(loops), 'z': z, 'corners': []}
    outer, inner = nested
    # corners are found by quadrant around the box's own centre (a part need not be centred on the origin)
    mid = (outer.min(0) + outer.max(0)) / 2
    outer, inner = outer - mid, inner - mid
    olo, ohi = outer.min(0), outer.max(0)
    ilo, ihi = inner.min(0), inner.max(0)
    straight = float(min(ohi[0] - ihi[0], ilo[0] - olo[0], ohi[1] - ihi[1], ilo[1] - olo[1]))
    corners = []
    for sx, sy in [(1, 1), (-1, 1), (-1, -1), (1, -1)]:
        arc, _, _ = _arc_points(outer, sx, sy, olo, ohi)
        if len(arc) < 3:
            corners.append({'corner': [sx, sy], 'outer': 'sharp'})
            continue
        cx, cy, r = fit_circle(arc)
        iarc, ixm, iym = _arc_points(inner, sx, sy, ilo, ihi)
        if len(iarc) >= 3:
            icx, icy, ir = fit_circle(iarc)
            wall = r - ir - math.hypot(cx - icx, cy - icy)
            inner_kind, r_in = 'round', ir
        else:
            corner = np.array([sx * ixm, sy * iym])
            wall = r - math.hypot(cx - corner[0], cy - corner[1])
            inner_kind, r_in = 'sharp', 0.0
        # raw: the nearest distance from the inner loop's corner region to the outer polyline
        q_in = inner[(np.sign(inner[:, 0]) == sx) & (np.sign(inner[:, 1]) == sy)]
        a, b = outer, np.roll(outer, -1, axis=0)
        raw = min(float(_seg_dist(np.repeat(p[None], len(a), 0), a, b).min()) for p in q_in)
        # largest sagitta of the outer arc's chords
        ordered = arc[np.argsort(np.arctan2(arc[:, 1] - cy, arc[:, 0] - cx))]
        chords = np.hypot(*np.diff(ordered, axis=0).T) if len(ordered) > 1 else np.array([0.0])
        sag = float(max(r - math.sqrt(max(r * r - (c / 2) ** 2, 0)) for c in chords))
        corners.append({'corner': [sx, sy], 'r_fit': round(r, 4), 'centre': [round(cx, 4), round(cy, 4)],
                        'inner': inner_kind, 'r_in_fit': round(r_in, 4), 'arc_vertices': int(len(arc)),
                        'wall_mm': round(min(wall, straight), 4), 'raw_polyline_mm': round(raw, 4),
                        'sagitta_mm': round(sag, 4)})
    walls = [c['wall_mm'] for c in corners if 'wall_mm' in c] or [straight]
    return {'status': 'OK', 'wall_mm': round(min(walls + [straight]), 4), 'straight_wall_mm': round(straight, 4),
            'z': z, 'corners': corners}


def measure_stl(path, z=15.0):
    t = read_stl(path)
    lo, hi = bbox(t)
    return {'triangles': int(len(t)), 'bbox_min': lo, 'bbox_max': hi,
            'size': [round(hi[i] - lo[i], 4) for i in range(3)], 'volume_mm3': round(volume(t), 3),
            'corner_wall': corner_wall(t, z)}
