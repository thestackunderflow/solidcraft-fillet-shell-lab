"""The logging proxy's per-call watchdog (PLAN v2 5.2, change 2): a request with no reply for --watchdog seconds gets a
HANG row in the transcript, the server is killed, and the proxy exits (so the run ends instead of waiting forever)."""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROXY = os.path.join(HERE, '..', 'proxy', 'mcp_log_proxy.py')
FAKE = os.path.join(HERE, 'fake_sleepy_server.py')


def test_watchdog_writes_hang_and_exits():
    with tempfile.TemporaryDirectory() as d:
        log = os.path.join(d, 't.jsonl')
        p = subprocess.Popen([sys.executable, PROXY, '--log', log, '--watchdog', '2', '--', sys.executable, FAKE],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n')
        p.stdin.flush()
        assert json.loads(p.stdout.readline())['id'] == 1          # answered: no HANG for it
        p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                  'params': {'name': 'batch', 'arguments': {}}}) + '\n')
        p.stdin.flush()
        t0 = time.time()
        rc = p.wait(timeout=30)
        assert time.time() - t0 < 15
        rows = [json.loads(l) for l in open(log, encoding='utf-8')]
        hang = [r for r in rows if r['dir'] == 'proxy' and isinstance(r['msg'], dict) and 'HANG' in r['msg']]
        assert len(hang) == 1
        assert hang[0]['msg']['HANG']['id'] == 2 and hang[0]['msg']['HANG']['method'] == 'tools/call'
        assert hang[0]['msg']['HANG']['tool'] == 'batch'
        assert rc != 0


def test_no_watchdog_row_when_replies_come():
    with tempfile.TemporaryDirectory() as d:
        log = os.path.join(d, 't.jsonl')
        p = subprocess.Popen([sys.executable, PROXY, '--log', log, '--watchdog', '2', '--', sys.executable, FAKE],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n')
        p.stdin.flush()
        p.stdout.readline()
        time.sleep(3)
        p.stdin.close()
        p.wait(timeout=10)
        rows = [json.loads(l) for l in open(log, encoding='utf-8')]
        assert not [r for r in rows if isinstance(r['msg'], dict) and 'HANG' in r['msg']]
