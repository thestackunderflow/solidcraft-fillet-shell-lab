"""A minimal MCP client over stdio (from solidcraft-resize-lab; + a 120 s client-side timeout that raises Hang): JSON-RPC 2.0, one message per line. No SDK.

The client starts the server as a child process and talks to it over the child's stdin/stdout,
exactly as Claude Code or Claude Desktop do. stderr is kept for the record.
"""

import base64
import copy
import json
import os
import select
import subprocess
import threading

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SERVER_CMD = ["solidcraft-cli", "mcp", "--allow-path", "/lab/out"]
PROTOCOL = "2025-06-18"
TIMEOUT_S = 120  # every SolidCraft call: a 120 s client-side timeout (no server-side timeout exists)


class McpError(Exception):
    pass


class Hang(McpError):
    """No reply within the client-side timeout: logged as HANG; the caller kills the server."""


class McpClient:
    def __init__(self, cmd, timeout_s=TIMEOUT_S):
        self.cmd = cmd
        self.timeout_s = timeout_s
        self.proc = None
        self.next_id = 0
        self.init_result = None
        self._stderr = []

    # -- process ---------------------------------------------------------------------------
    def start(self):
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self.init_result = self.request("initialize", {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "solidcraft-mcp-lab", "version": "1"},
        })
        self.notify("notifications/initialized")
        return self.init_result

    def _drain_stderr(self):
        for line in self.proc.stderr:
            self._stderr.append(line.rstrip("\n"))

    def stderr_text(self):
        return list(self._stderr)

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def kill(self):
        """After a HANG: the server process is killed (the probe runs it inside a throwaway container)."""
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=10)

    # -- JSON-RPC --------------------------------------------------------------------------
    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def request(self, method, params):
        self.next_id += 1
        rid = self.next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        while True:
            ready, _, _ = select.select([self.proc.stdout], [], [], self.timeout_s)
            if not ready:
                raise Hang(f"HANG: no reply to {method} within {self.timeout_s}s")
            line = self.proc.stdout.readline()
            if not line:
                raise McpError(f"server closed stdout (exit {self.proc.poll()}); stderr: {self._stderr[-5:]}")
            msg = json.loads(line)
            if msg.get("id") != rid:  # a notification or a server request: not ours
                continue
            if "error" in msg:
                raise McpError(json.dumps(msg["error"]))
            return msg["result"]

    # -- tools -----------------------------------------------------------------------------
    def call_tool(self, name, arguments):
        """The raw tool result: {content: [...], isError?: bool}."""
        return self.request("tools/call", {"name": name, "arguments": arguments})

    @staticmethod
    def text(result):
        return "\n".join(c["text"] for c in result.get("content", []) if c.get("type") == "text")

    @staticmethod
    def text_json(result):
        t = McpClient.text(result)
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            return t

    def tool_json(self, name, arguments):
        """Call a tool that must succeed and return its JSON text."""
        r = self.call_tool(name, arguments)
        if r.get("isError"):
            raise McpError(f"{name} failed: {self.text(r)}")
        return self.text_json(r)


# -- saved outputs ----------------------------------------------------------------------------
def _strip_images(obj):
    """Image blocks are saved as PNG files; the JSON keeps their size, not the base64."""
    obj = copy.deepcopy(obj)

    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "image" and isinstance(o.get("data"), str):
                o["data"] = f"<{len(base64.b64decode(o['data']))} bytes of {o.get('mimeType')}, saved as a .png in tests/out>"
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return obj


def _parse_text_blocks(obj):
    """For readability, a text block holding JSON is also saved parsed (`text_parsed`)."""
    if isinstance(obj, dict) and isinstance(obj.get("content"), list):
        for c in obj["content"]:
            if c.get("type") == "text":
                try:
                    c["text_parsed"] = json.loads(c["text"])
                except (json.JSONDecodeError, TypeError):
                    pass
    return obj


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(_parse_text_blocks(_strip_images(obj)), f, indent=1, ensure_ascii=False)
        f.write("\n")


def save_png(mcp, name, args):
    """Take a screenshot over MCP, save the PNG and the reply; return the reply's info JSON."""
    r = mcp.call_tool("screenshot", args)
    if r.get("isError"):
        raise McpError(f"screenshot failed: {mcp.text(r)}")
    img = next(c for c in r["content"] if c.get("type") == "image")
    assert img["mimeType"] == "image/png"
    png = base64.b64decode(img["data"])
    with open(os.path.join(OUT, name + ".png"), "wb") as f:
        f.write(png)
    save(name + "_reply", {"arguments": args, **r})
    info = mcp.text_json(r)
    return info if isinstance(info, dict) else {"text": info}
