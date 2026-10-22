"""PT1 + PT2: the box measurer on synthetic meshes (NumPy only, no SolidCraft)."""
import math
import os
import tempfile

import pytest

import synth
from measure_box import corner_wall, read_stl, sf_volume, shelled_volume, volume

SQ2 = math.sqrt(2)


def g2(r, t=2.0):
    """Hand geometry (ACCURACY G2): the corner wall of shell-then-fillet with a sharp inner corner."""
    return r - (r - t) * SQ2


# ---- PT1: the analytic volumes match closed synthetic meshes -------------------------------------------------------
@pytest.mark.parametrize('r', [1, 2, 6, 10, 25])
def test_pt1_shelled_volume_matches_fs_mesh(r):
    mesh = synth.fs_box(r, chords=64)
    assert volume(mesh) == pytest.approx(shelled_volume(80, 60, 30, r, 2), rel=1e-4)


@pytest.mark.parametrize('r', [2, 4, 5, 6, 6.5])
def test_pt1_sf_volume_matches_sf_mesh(r):
    mesh = synth.sf_box(r, chords=64)
    assert volume(mesh) == pytest.approx(sf_volume(80, 60, 30, r, 2), rel=1e-4)


def test_pt1_known_values():
    # ACCURACY G1 / G3 (re-derived by the accuracy reviewer)
    assert shelled_volume(80, 60, 30, 6, 2) == pytest.approx(24289.49, abs=0.01)
    assert shelled_volume(80, 60, 30, 10, 2) == pytest.approx(23795.04, abs=0.01)
    assert sf_volume(80, 60, 30, 6, 2) == pytest.approx(23904.92, abs=0.01)
    assert sf_volume(80, 60, 30, 5, 2) == pytest.approx(24188.19, abs=0.01)


def test_pt1_sf_volume_refuses_a_breached_radius():
    with pytest.raises(ValueError):
        sf_volume(80, 60, 30, 7, 2)


# ---- PT2: the corner wall, by circle fit, at coarse and fine tessellation ------------------------------------------
@pytest.mark.parametrize('chords', [4, 8, 16])
@pytest.mark.parametrize('kind,r,expected', [
    ('fs', 6, 2.000), ('fs', 10, 2.000),
    ('sf', 3, g2(3)), ('sf', 5, g2(5)), ('sf', 6, g2(6)), ('sf', 2, 2.000),
])
def test_pt2_corner_wall(kind, r, expected, chords):
    mesh = (synth.fs_box if kind == 'fs' else synth.sf_box)(r, chords=chords)
    m = corner_wall(mesh, z=15.0)
    assert m['status'] == 'OK'
    assert m['wall_mm'] == pytest.approx(expected, abs=0.005)
    assert len(m['corners']) == 4
    for c in m['corners']:
        assert c['wall_mm'] == pytest.approx(expected, abs=0.005)
        assert c['r_fit'] == pytest.approx(r, abs=0.005)
        # the raw polyline distance is reported, never above the true wall by more than the sagitta
        assert c['raw_polyline_mm'] <= expected + c['sagitta_mm'] + 1e-6


def test_pt2_expected_numbers():
    assert g2(6) == pytest.approx(0.343, abs=0.001)
    assert g2(5) == pytest.approx(0.757, abs=0.001)
    assert g2(3) == pytest.approx(1.586, abs=0.001)


def test_pt2_breached_wall_fails_loudly():
    m = corner_wall(synth.breached_walls(), z=15.0)
    assert m['status'] == 'BREACHED'
    assert m['wall_mm'] == 0.0


def test_pt2_reads_a_binary_stl_round_trip():
    mesh = synth.sf_box(6, chords=8)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'b.stl')
        synth.write_stl(p, mesh)
        back = read_stl(p)
    assert corner_wall(back, z=15.0)['wall_mm'] == pytest.approx(g2(6), abs=0.005)


@pytest.mark.parametrize('kind,r,expected', [('fs', 10, 2.000), ('sf', 6, g2(6))])
def test_pt2_off_centre_box(kind, r, expected):
    """A box with one corner at the origin (how the agent runs drew it), not centred on it."""
    mesh = (synth.fs_box if kind == 'fs' else synth.sf_box)(r, chords=8) + [40.0, 30.0, 0.0]
    m = corner_wall(mesh, z=15.0)
    assert m['wall_mm'] == pytest.approx(expected, abs=0.005)
    assert [c['r_fit'] for c in m['corners']] == pytest.approx([r] * 4, abs=0.005)
