"""Synthetic meshes for the measurer tests (NumPy only): open-top boxes whose outline is a rounded rectangle.

A box = an outer prism (z 0..h, outward normals) plus a reversed inner pocket prism (z t..h). Their signed volumes add up
to the box's volume, and a slice between t and h gives the outer loop and the inner loop. Arc vertices lie exactly on the
true circle, as a CAD tessellator's do, so a circle fit recovers the radius.
"""
import math

import numpy as np


def rounded_rect(w, d, r, chords):
    """Counter-clockwise outline of a w x d rectangle centred on the origin, corners rounded to r (r = 0: sharp)."""
    pts = []
    hx, hy = w / 2, d / 2
    centres = [(hx - r, hy - r, 0), (-hx + r, hy - r, 90), (-hx + r, -hy + r, 180), (hx - r, -hy + r, 270)]
    for cx, cy, a0 in centres:
        if r <= 0:
            pts.append((cx, cy))
            continue
        for k in range(chords + 1):
            a = math.radians(a0 + 90.0 * k / chords)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts, dtype=float)


def sharp_rect(w, d):
    return rounded_rect(w, d, 0, 1)


def prism(poly, z0, z1, outward=True):
    """Closed triangle mesh of a convex polygon extruded from z0 to z1."""
    n = len(poly)
    c = poly.mean(axis=0)
    tris = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        a0, b0, a1, b1 = [*a, z0], [*b, z0], [*a, z1], [*b, z1]
        tris += [[a0, b0, b1], [a0, b1, a1]]          # side (CCW outline: outward)
        tris.append([[*c, z1], a1, b1])               # top
        tris.append([[*c, z0], b0, a0])               # bottom
    t = np.array(tris, dtype=float)
    return t if outward else t[:, ::-1, :]


def box(w=80, d=60, h=30, t=2, r_out=6, r_in=None, chords=16, chords_in=None):
    """Open-top box: outer rounded r_out; inner pocket rounded r_in (None = r_out - t, uniform wall; 0 = sharp)."""
    if r_in is None:
        r_in = max(r_out - t, 0)
    outer = rounded_rect(w, d, r_out, chords)
    inner = rounded_rect(w - 2 * t, d - 2 * t, r_in, chords_in or chords)
    return np.concatenate([prism(outer, 0, h), prism(inner, t, h, outward=False)])


def fs_box(r, chords=16, **kw):
    """Fillet then shell: the inner corner follows the round (radius r - t, or sharp when r <= t)."""
    return box(r_out=r, r_in=None, chords=chords, **kw)


def sf_box(r, chords=16, **kw):
    """Shell then fillet the outer vertical edges: the inner corners stay sharp."""
    return box(r_out=r, r_in=0, chords=chords, **kw)


def breached_walls(w=80, d=60, h=30, t=2, gap=3.0):
    """Four separate wall slabs with open corners: what a corner round that went through the wall would leave."""
    hx, hy = w / 2, d / 2
    slabs = [
        np.array([[-hx + gap, hy - t], [hx - gap, hy - t], [hx - gap, hy], [-hx + gap, hy]]),
        np.array([[-hx + gap, -hy], [hx - gap, -hy], [hx - gap, -hy + t], [-hx + gap, -hy + t]]),
        np.array([[hx - t, -hy + gap], [hx, -hy + gap], [hx, hy - gap], [hx - t, hy - gap]]),
        np.array([[-hx, -hy + gap], [-hx + t, -hy + gap], [-hx + t, hy - gap], [-hx, hy - gap]]),
    ]
    return np.concatenate([prism(s, 0, h) for s in slabs])


def write_stl(path, tris):
    """Binary STL."""
    import struct
    with open(path, 'wb') as f:
        f.write(b'synthetic'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for tri in tris:
            f.write(struct.pack('<3f', 0, 0, 0))
            f.write(struct.pack('<9f', *tri.reshape(-1)))
            f.write(b'\0\0')
