"""Brain RTDB writers. Engine writes with a server credential (bypasses rules); Ops only reads.

RtdbWriter: Firebase RTDB REST with an OAuth2 access token. `patch()` is ONE multi-path update at the root, which RTDB
applies atomically, so a reader never sees half a snapshot. Every request has a hard timeout.
DryRunWriter: applies the same updates to an in-memory tree (and can dump it) — used locally and in tests."""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request

SCOPES = ["https://www.googleapis.com/auth/firebase.database", "https://www.googleapis.com/auth/userinfo.email"]
APP_INSTANCES = ("sector-9393c-default-rtdb", "sector-dev-1f4d0")     # the Sector app databases: never written here


class WriteError(RuntimeError):
    pass


def default_token() -> str:
    """Cloud Run: the job's service account via google-auth. Local: the gcloud user (admin) token."""
    try:
        import google.auth
        import google.auth.transport.requests
        creds, _ = google.auth.default(scopes=SCOPES)
        creds.refresh(google.auth.transport.requests.Request())
        if creds.token:
            return creds.token
    except Exception:
        pass
    r = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, timeout=30)
    if r.returncode or not r.stdout.strip():
        raise WriteError("no credential for the Brain RTDB (google-auth default and gcloud both failed)")
    return r.stdout.strip()


class RtdbWriter:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 20.0):
        if any(x in base_url for x in APP_INSTANCES):
            raise WriteError(f"refusing to write a Sector APP database: {base_url}")
        if "sector-brain" not in base_url:
            raise WriteError(f"not the dedicated Brain RTDB: {base_url}")
        self.base = base_url.rstrip("/"); self.timeout = timeout; self._token = token

    def _req(self, method: str, path: str, body=None, query: dict | None = None):
        self._token = self._token or default_token()
        q = {"access_token": self._token, **(query or {})}
        url = f"{self.base}/{path.strip('/')}.json?{urllib.parse.urlencode(q)}" if path.strip("/") else f"{self.base}/.json?{urllib.parse.urlencode(q)}"
        data = None if body is None else json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                txt = r.read().decode()
        except urllib.error.HTTPError as e:
            raise WriteError(f"{method} /{path} -> HTTP {e.code}: {e.read().decode()[:200]}") from None
        return json.loads(txt) if txt else None

    def patch(self, updates: dict) -> None:
        """Atomic multi-path update at the root. Keys are absolute paths without a leading slash."""
        if updates:
            self._req("PATCH", "", updates)

    def get(self, path: str, query: dict | None = None):
        return self._req("GET", path, query=query)

    def delete(self, path: str) -> None:
        self._req("DELETE", path)


class DryRunWriter:
    def __init__(self, tree: dict | None = None):
        self.tree = tree if tree is not None else {}
        self.patches: list[dict] = []

    def patch(self, updates: dict) -> None:
        json.dumps(updates, allow_nan=False)      # same serialisation guard as the live writer (no NaN/Infinity)
        self.patches.append(updates)
        for path, val in updates.items():
            parts = [p for p in path.split("/") if p]
            node = self.tree
            for p in parts[:-1]:
                if not isinstance(node.get(p), dict):
                    node[p] = {}
                node = node[p]
            if val is None:
                node.pop(parts[-1], None)
            else:
                node[parts[-1]] = val

    def get(self, path: str, query: dict | None = None):
        node = self.tree
        for p in [p for p in path.split("/") if p]:
            if not isinstance(node, dict) or p not in node:
                return None
            node = node[p]
        return node

    def delete(self, path: str) -> None:
        self.patch({path: None})

    def dump(self, out_path: str) -> None:
        with open(out_path, "w") as f:
            json.dump(self.tree, f, indent=1, sort_keys=True)
