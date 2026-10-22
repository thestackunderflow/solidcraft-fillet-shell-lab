"""PT4: a SolidCraft call that never answers is cut at the client-side timeout and marked HANG (SolidCraft has no
server-side timeout: the lighthouse lab's extrude-cut hung the server)."""
import os
import sys
import time

import pytest

from mcp_client import Hang, McpClient

FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fake_sleepy_server.py')


def test_pt4_timeout_marks_hang():
    c = McpClient([sys.executable, FAKE], timeout_s=2)
    c.start()                                  # initialize is answered
    t0 = time.time()
    with pytest.raises(Hang) as e:
        c.call_tool('batch', {'commands': []})  # tools/call never is
    assert 1.5 <= time.time() - t0 < 10
    assert 'HANG' in str(e.value)
    c.kill()
    assert c.proc.poll() is not None


def test_pt4_default_timeout_is_120_s():
    assert McpClient(['true']).timeout_s == 120
