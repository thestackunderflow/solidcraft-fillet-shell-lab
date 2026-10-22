"""The deciding probe cells, re-run live on the pinned SolidCraft 0.17.0 (no AI) and checked against the committed probe
record (out/probe/0.17.0/). The video quotes out/, never memory. PLAN v2 section 4; PROBE-RESULT.md."""
import json
import os

import pytest

import cells
from measure_box import shelled_volume, sf_volume

PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'probe', '0.17.0')
REFUSAL = ('fillet: the rounds would leave openings in the surface (they overlap where a wall or a face is narrower '
           'than both); the largest radius that fits is 6.82 mm')


def recorded(cell):
    with open(os.path.join(PROBE, cell, 'summary.json'), encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope='module')
def lab():
    s = cells.Lab('probe-cells')
    yield s
    s.close()


def test_version_is_pinned(lab):
    assert lab.server_version() == '0.17.0'


def test_fs10_builds_with_a_2_mm_wall(lab):
    r = lab.cell('FS', 10)
    assert r['batch2']['ok'] is True
    assert [f['name'] for f in r['timeline_after']] == ['Sketch1', 'Extrude1', 'Fillet1', 'Shell1']
    assert all(f['error'] is None and f['warning'] is None for f in r['timeline_after'])
    assert r['sc_volume_mm3'] == pytest.approx(shelled_volume(80, 60, 30, 10, 2), rel=1e-5)
    assert r['stl']['wall_mm'] == pytest.approx(2.0, abs=0.001)
    assert r['sc_wall']['radius_minus_axis_mm'] == pytest.approx(2.0, abs=0.001)


def test_sf10_is_refused_and_rolled_back(lab):
    r = lab.cell('SF', 10)
    b = r['batch2']
    assert b['isError'] is True and b['ok'] is False
    assert b['failed'] == {'command': 'solid.fillet', 'error': REFUSAL, 'index': 0}
    assert b['rolled_back'] is True
    assert r['timeline_before'] == r['timeline_after']
    assert [f['name'] for f in r['timeline_after']] == ['Sketch1', 'Extrude1', 'Shell1']
    assert r['stage1_md5'] == r['final_md5']        # the refusal left the stage-1 part exactly as it was


def test_sf6_builds_a_third_of_a_millimetre_corner_with_no_warning(lab):
    r = lab.cell('SF', 6)
    assert r['batch2']['ok'] is True and r['batch2']['warning'] is None
    assert all(f['error'] is None and f['warning'] is None for f in r['timeline_after'])
    assert r['stl']['wall_mm'] == pytest.approx(0.3431, abs=0.0005)
    assert r['sc_wall']['radius_minus_axis_mm'] == pytest.approx(0.3431, abs=0.0005)
    assert abs(r['stl']['wall_mm'] - r['sc_wall']['min_mm']) < 0.05     # two methods agree
    assert r['sc_volume_mm3'] == pytest.approx(sf_volume(80, 60, 30, 6, 2), rel=1e-4)


def test_the_offered_radius_leaves_almost_no_corner(lab):
    off = cells.offered_radius(REFUSAL)
    assert off == 6.82
    r = lab.cell('SF', off)
    assert r['batch2']['ok'] is True and r['batch2']['warning'] is None
    assert r['stl']['wall_mm'] < 0.01
    assert r['sc_wall']['radius_minus_axis_mm'] == pytest.approx(r['stl']['wall_mm'], abs=0.001)


@pytest.mark.parametrize('cell,order,radius', [('FS-10-1', 'FS', 10), ('SF-10-1', 'SF', 10), ('SF-6-1', 'SF', 6),
                                               ('SF-offered-1', 'SF', 6.82)])
def test_live_equals_the_committed_probe_record(lab, cell, order, radius):
    live, rec = lab.cell(order, radius), recorded(cell)
    assert live['batch2'].get('ok') == rec['batch2'].get('ok')
    assert (live['batch2'].get('failed') or None) == (rec['batch2'].get('failed') or None)
    assert live['sc_volume_mm3'] == pytest.approx(rec['sc_volume_mm3'], abs=0.01)
    assert live['final_md5'] == rec['final_md5']
