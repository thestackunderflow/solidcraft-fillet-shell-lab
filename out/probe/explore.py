"""Spike (no AI): what does this SolidCraft version offer? tools/list, initialize, list_commands for the commands
the probe uses. Saved to out/probe/<ver>/interface/. Run in the lab image: python3 out/probe/explore.py <ver>"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tests'))
from mcp_client import McpClient, SERVER_CMD  # noqa: E402

ver = sys.argv[1]
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), ver, 'interface')
os.makedirs(d, exist_ok=True)
c = McpClient(SERVER_CMD)
init = c.start()
json.dump(init, open(os.path.join(d, 'initialize.json'), 'w'), indent=1)
tl = c.request('tools/list', {})
json.dump(tl, open(os.path.join(d, 'tools_list.json'), 'w'), indent=1)
print('tools:', [t['name'] for t in tl['tools']])
for f in ['fillet', 'shell', 'boss', 'lip', 'parameters', 'rectangle']:
    r = c.call_tool('list_commands', {'filter': f})
    json.dump(r, open(os.path.join(d, f'list_commands_{f}.json'), 'w'), indent=1)
    print('==', f, c.text(r)[:3000])
for t in tl['tools']:
    if t['name'] in ('measure', 'body_topology', 'batch', 'inspect_design', 'export', 'screenshot'):
        print('##', t['name'], t.get('description', '')[:1500])
        print('   schema:', json.dumps(t.get('inputSchema', {}))[:1500])
c.close()
