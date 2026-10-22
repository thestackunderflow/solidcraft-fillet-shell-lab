"""Summarise every probe cell (out/probe/<ver>/*/summary.json) into out/probe/SUMMARY.md and SUMMARY.json."""
import glob
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'probe')
rows = []
for f in sorted(glob.glob(os.path.join(ROOT, '*', '*', 'summary.json'))):
    s = json.load(open(f, encoding='utf-8'))
    ver = os.path.basename(os.path.dirname(os.path.dirname(f)))
    cell = os.path.basename(os.path.dirname(f))
    b2 = s.get('batch2') or {}
    failed = b2.get('failed') if isinstance(b2.get('failed'), dict) else {}
    stl = s.get('stl') or {}
    sw = s.get('sc_wall') or {}
    rows.append({
        'version': ver, 'cell': cell, 'R': s.get('R'), 'ok': b2.get('ok'), 'isError': b2.get('isError'),
        'failed_command': failed.get('command'), 'error': failed.get('error'), 'rolled_back': b2.get('rolled_back'),
        'undone': b2.get('undone'), 'warning': b2.get('warning'), 'radius_applied': b2.get('radius_applied'),
        'timeline_after': [t['name'] for t in (s.get('timeline_after') or []) if isinstance(t, dict)],
        'feature_errors': [t.get('error') for t in (s.get('timeline_after') or []) if isinstance(t, dict) and t.get('error')],
        'feature_warnings': [t.get('warning') for t in (s.get('timeline_after') or []) if isinstance(t, dict) and t.get('warning')],
        'timeline_unchanged': s.get('timeline_unchanged'),
        'sc_volume': s.get('sc_volume_mm3'), 'stl_volume': stl.get('volume_mm3'), 'expected_volume': s.get('expected_volume'),
        'sc_vs_expected_pct': s.get('sc_vs_expected_pct'), 'stl_vs_expected_pct': s.get('stl_vs_expected_pct'),
        'stl_wall': stl.get('wall_mm'), 'stl_wall_status': stl.get('wall_status'), 'r_fit': (stl.get('corner_r_fit') or [None])[0],
        'sc_min': sw.get('min_mm'), 'sc_radius_minus_axis': sw.get('radius_minus_axis_mm'), 'expected_wall': s.get('expected_wall'),
        'stage1_md5': s.get('stage1_md5'), 'final_md5': s.get('final_md5'), 'HANG': s.get('HANG'), 'exception': s.get('exception'),
        'wall_s': s.get('wall_s'), 'offered_from_error': s.get('offered_from_error'),
        'p4': {k: s.get(k) for k in ('box', 'bosses', 'volume_after_bosses', 'lip', 'volume_after_lip')} if s.get('cell') == 'P4' else None,
    })
json.dump(rows, open(os.path.join(ROOT, 'SUMMARY.json'), 'w', encoding='utf-8', newline='\n'), indent=1, ensure_ascii=False)


def f(x, n=4):
    return '' if x is None else (f'{x:.{n}f}' if isinstance(x, float) else str(x))


lines = ['| ver | cell | R | ok | failed | stl wall | sc min | sc r-axis | expected wall | sc vol | expected vol | sc vs exp % | stl vs exp % | warning | hang/exc |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
for r in rows:
    if r['p4']:
        lines.append(f"| {r['version']} | {r['cell']} | | | P4: {json.dumps(r['p4'], ensure_ascii=False)} | | | | | | | | | | {r['HANG'] or r['exception'] or ''} |")
        continue
    lines.append(f"| {r['version']} | {r['cell']} | {f(r['R'])} | {r['ok']} | {r['failed_command'] or ''} | {f(r['stl_wall'])} {'' if r['stl_wall_status'] in (None, 'OK') else r['stl_wall_status']} | "
                 f"{f(r['sc_min'])} | {f(r['sc_radius_minus_axis'])} | {f(r['expected_wall'])} | {f(r['sc_volume'], 2)} | {f(r['expected_volume'], 2)} | "
                 f"{f(r['sc_vs_expected_pct'])} | {f(r['stl_vs_expected_pct'])} | {r['warning'] or ''}{'; '.join(r['feature_warnings'])} | {r['HANG'] or r['exception'] or ''} |")
errors = sorted({(r['version'], r['error']) for r in rows if r['error']})
lines += ['', 'Refusal texts (failed.error, verbatim):', '']
lines += [f'- {v}: `{e}`' for v, e in errors]
open(os.path.join(ROOT, 'SUMMARY.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
