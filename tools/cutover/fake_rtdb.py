"""A GET-only stand-in for the Brain RTDB REST API, served on 127.0.0.1 from a capture (cutover gate G6 rehearsal; Lake step B4).

Every request is logged. Any method other than GET is refused (405) and recorded, so a rehearsal proves the job made no write. The base path is
/sector-brain, because the Swift store only accepts a database URL that names the Brain database: use http://127.0.0.1:PORT/sector-brain.
"""
from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = "/sector-brain"


class Tree:
    def __init__(self, capture: dict):
        self.captured = sorted(p.strip("/") for p in capture)
        self.root: dict = {}
        for p, v in capture.items():
            node, parts = self.root, [x for x in p.strip("/").split("/") if x]
            for x in parts[:-1]:
                node = node.setdefault(x, {})
            if parts:
                node[parts[-1]] = v
            elif isinstance(v, dict):
                self.root.update(v)

    def covered(self, path: str) -> bool:
        """True when the path is at or below a captured path (so a null there is the real value, not a gap in the capture)."""
        p = path.strip("/")
        return any(p == c or p.startswith(c + "/") for c in self.captured)

    def get(self, path: str):
        node = self.root
        for x in [x for x in path.strip("/").split("/") if x]:
            if not isinstance(node, dict) or x not in node:
                return None
            node = node[x]
        return node


class FakeRTDB:
    def __init__(self, capture: dict):
        self.tree, self.reads, self.uncovered, self.refused = Tree(capture), [], set(), []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _path(self):
                u = urllib.parse.urlparse(self.path)
                p = urllib.parse.unquote(u.path)
                if not p.startswith(BASE + "/") or not p.endswith(".json"):
                    return None, {}
                return p[len(BASE) + 1:-5], urllib.parse.parse_qs(u.query)

            def do_GET(self):
                p, q = self._path()
                if p is None:
                    self.send_response(404); self.end_headers(); return
                fake.reads.append(p)
                if not fake.tree.covered(p):
                    fake.uncovered.add(p)
                v = fake.tree.get(p)
                if q.get("shallow") == ["true"] and isinstance(v, dict):
                    v = {k: True for k in v}
                body = json.dumps(v).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body)

            def _refuse(self):
                fake.refused.append((self.command, self.path))
                self.send_response(405); self.end_headers()

            do_PUT = do_PATCH = do_POST = do_DELETE = _refuse

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}{BASE}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
