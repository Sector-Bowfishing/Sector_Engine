"""wind-candidate-read: the master-only read path for the Wind Candidate inspector.

GET /latest/<lake> with `Authorization: Bearer <Firebase ID token>`. The token is verified against
the Firebase project and the uid must be in MASTER_UIDS; then the private bucket's
latest/<lake>.json.gz is returned as-is (gzip). The bucket itself stays private: only this
service's read-only account can read it. Nothing here touches production."""
import json, os, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import google.auth.transport.requests
from google.cloud import storage
from google.oauth2 import id_token

PROJECT = os.environ.get("FIREBASE_PROJECT", "sector-9393c")
BUCKET = os.environ["BUCKET"]
PREFIX = os.environ.get("PREFIX", "wind/v1")
MASTERS = {u.strip() for u in os.environ.get("MASTER_UIDS", "").split(",") if u.strip()}
LAKES = {"guntersville", "wheeler", "wilson", "pickwick"}
_req = google.auth.transport.requests.Request()
_bucket = storage.Client().bucket(BUCKET)


def master_uid(header: str | None) -> str | None:
    if not header or not header.startswith("Bearer "):
        return None
    try:
        claims = id_token.verify_firebase_token(header[7:], _req, audience=PROJECT)
    except Exception:
        return None
    uid = claims.get("user_id") or claims.get("sub")
    return uid if uid in MASTERS else None


class H(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, b'{"ok":true}')
        m = re.fullmatch(r"/latest/([a-z]+)", self.path)
        if not m or m.group(1) not in LAKES:
            return self._send(404, b'{"error":"not found"}')
        if not master_uid(self.headers.get("Authorization")):
            return self._send(403, b'{"error":"master accounts only"}')
        blob = _bucket.blob(f"{PREFIX}/latest/{m.group(1)}.json.gz")
        if not blob.exists():
            return self._send(404, b'{"error":"no bundle yet"}')
        return self._send(200, blob.download_as_bytes(raw_download=True), "application/gzip")

    def log_message(self, fmt, *args):  # one line per request, no tokens
        print(json.dumps({"path": self.path, "status": args[1] if len(args) > 1 else None}))


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
