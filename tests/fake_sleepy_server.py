"""A fake MCP server for PT4: answers initialize, then never answers anything else."""
import json
import sys
import time

for line in sys.stdin:
    msg = json.loads(line)
    if msg.get('method') == 'initialize':
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {
            'protocolVersion': '2025-06-18', 'capabilities': {}, 'serverInfo': {'name': 'sleepy', 'version': '0'}}}) + '\n')
        sys.stdout.flush()
    elif 'id' in msg:
        time.sleep(3600)
