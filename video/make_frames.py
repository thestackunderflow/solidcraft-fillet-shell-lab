"""Render-ready stills, all drawn by SolidCraft 0.17.0 itself (`solidcraft-cli snapshot`), no AI, no repainting.

    docker run --rm -v <lab>:/work -w /work solidcraft-fillet-shell-lab:0.17.0 python3 video/make_frames.py

- frame0-both-boxes.png: ONE render holding both boxes (so the camera is the same by construction). Left: the hollow box
  before the rounding step (shell only), with the four vertical edges the refused fillet named shown as thin red rods
  (separate bodies, our highlight: disclose "edges highlighted"). Right: round first, then shell (R10), built.
- section-*.png: top views cut at z = 15 (`--section z=15`): the corner wall the video talks about.
- iso-*.png: single-box iso renders.
Every script that was rendered is kept next to its PNG (video/frames/*.script.json), so each image can be re-made.
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'frames')
EDGE_RED = '#e0262b'


def box(cx, name):
    return [
        {'command': 'sketch.create', 'params': {'plane': 'XY'}},
        {'command': 'sketch.rectangle.center', 'params': {'center': [cx, 0], 'corner': [cx + 40, 30]}},
        {'command': 'sketch.finish', 'params': {}},
        {'command': 'solid.extrude', 'params': {'distance': 30, 'operation': 'new', 'body_name': name}},
    ]


def edges(cx):
    return [[cx + 40, 30, 15], [cx - 40, 30, 15], [cx - 40, -30, 15], [cx + 40, -30, 15]]


def shell(cx, name):
    return {'command': 'solid.shell', 'params': {'faces': [[cx, 0, 30]], 'thickness': 2, 'body': name}}


def fillet(cx, r, name):
    return {'command': 'solid.fillet', 'params': {'edges': edges(cx), 'radius': r, 'body': name}}


def snapshot(name, commands, *opts):
    os.makedirs(OUT, exist_ok=True)
    script = os.path.join(OUT, name + '.script.json')
    with open(script, 'w', encoding='utf-8') as f:
        json.dump({'commands': commands}, f, indent=1)
    png = os.path.join(OUT, name + '.png')
    p = subprocess.run(['solidcraft-cli', 'snapshot', script, '--out', png, *opts], capture_output=True, text=True, timeout=120)
    print(name, p.returncode, (p.stdout + p.stderr).strip()[:300])
    if p.returncode != 0:
        raise SystemExit(f'{name} failed')
    return png


def main():
    # frame 0: both boxes, one camera
    left, right = -60, 60
    rods = [{'command': 'solid.cylinder', 'params': {'radius': 0.9, 'height': 30, 'base': [x, y, 0], 'operation': 'new',
                                                      'body_name': f'Edge{i + 1}'}}
            for i, (x, y, _) in enumerate(edges(left))]
    cmds = box(left, 'ShellFirst') + [shell(left, 'ShellFirst')] + box(right, 'RoundFirst') + \
        [fillet(right, 10, 'RoundFirst'), shell(right, 'RoundFirst')] + rods
    body_opts = [x for i in range(4) for x in ('--body', f'Edge{i + 1}:color={EDGE_RED}')]
    snapshot('frame0-both-boxes', cmds, '--view', 'iso', '--width', '1920', '--height', '1080', '--no-grid', '--no-axes', *body_opts)
    snapshot('frame0-both-boxes-plain', box(left, 'ShellFirst') + [shell(left, 'ShellFirst')] + box(right, 'RoundFirst') +
             [fillet(right, 10, 'RoundFirst'), shell(right, 'RoundFirst')],
             '--view', 'iso', '--width', '1920', '--height', '1080', '--no-grid', '--no-axes')
    # single boxes, iso
    snapshot('iso-shell-only', box(0, 'Box') + [shell(0, 'Box')], '--view', 'iso', '--width', '1600', '--height', '1000', '--no-grid', '--no-axes')
    snapshot('iso-FS-10', box(0, 'Box') + [fillet(0, 10, 'Box'), shell(0, 'Box')], '--view', 'iso', '--width', '1600', '--height', '1000', '--no-grid', '--no-axes')
    snapshot('iso-SF-6', box(0, 'Box') + [shell(0, 'Box'), fillet(0, 6, 'Box')], '--view', 'iso', '--width', '1600', '--height', '1000', '--no-grid', '--no-axes')
    # sections at z = 15, from the top
    for name, cmds in [('section-shell-only', box(0, 'Box') + [shell(0, 'Box')]),
                       ('section-FS-10', box(0, 'Box') + [fillet(0, 10, 'Box'), shell(0, 'Box')]),
                       ('section-FS-6', box(0, 'Box') + [fillet(0, 6, 'Box'), shell(0, 'Box')]),
                       ('section-SF-6', box(0, 'Box') + [shell(0, 'Box'), fillet(0, 6, 'Box')]),
                       ('section-SF-6.82', box(0, 'Box') + [shell(0, 'Box'), fillet(0, 6.82, 'Box')])]:
        snapshot(name, cmds, '--view', 'top', '--section', 'z=15', '--width', '1600', '--height', '1000', '--no-grid', '--no-axes')
        # the (+x, +y) corner, close up, looking straight down (camera: target, yaw, pitch, distance in mm and radians)
        cam = json.dumps({'target': [36.5, 26.5, 15], 'yaw': 0.0, 'pitch': 1.5707, 'distance': 28})
        snapshot(name + '-corner', cmds, '--camera', cam, '--section', 'z=15', '--width', '1200', '--height', '1200', '--no-grid', '--no-axes')


if __name__ == '__main__':
    main()
