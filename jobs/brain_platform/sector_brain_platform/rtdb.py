"""Brain RTDB REST client (contract section 8): retries, schema gate, app-db refusal, dry-run store."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from .keys import check_update
from .ownership import assert_owned

SCHEMA_VERSION = 1
BRAIN_RTDB_URL = "https://sector-brain.firebaseio.com"
APP_DATABASES = ("sector-9393c-default-rtdb", "sector-dev-1f4d0")   # customer data: never written here
ATTEMPTS = 4
BACKOFF_BASE_S = 1.5
CONNECT_TIMEOUT_S, READ_TIMEOUT_S = 10.0, 30.0
MAX_LAKES_PER_PATCH = 50


def should_retry(status: int | None) -> bool:
    """Transport errors, 5xx and 429 only."""
    return status is None or status >= 500 or status == 429


def backoff_seconds(attempt: int) -> float:
    return BACKOFF_BASE_S * (2 ** attempt)


def accepted_url(url: str) -> bool:
    return "sector-brain" in url and not any(db in url for db in APP_DATABASES)


class BrainRtdbError(RuntimeError):
    pass


class TokenProvider:
    """OAuth2 token: Cloud Run metadata server, else gcloud; BRAIN_ACCESS_TOKEN for tests. Refreshed < 120 s to expiry."""
    SCOPES = ("https://www.googleapis.com/auth/firebase.database,https://www.googleapis.com/auth/userinfo.email,"
              "https://www.googleapis.com/auth/cloud-platform")

    def __init__(self, mode: str | None = None):
        self.mode = mode or os.environ.get("BRAIN_TOKEN_MODE") or ("metadata" if os.environ.get("CLOUD_RUN_JOB") else "gcloud")
        self._tok, self._exp = None, 0.0

    def token(self) -> str:
        if self._tok and time.time() < self._exp - 120:
            return self._tok
        if os.environ.get("BRAIN_ACCESS_TOKEN"):
            self._tok, self._exp = os.environ["BRAIN_ACCESS_TOKEN"], time.time() + 3000
        elif self.mode == "metadata":
            url = ("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token?scopes="
                   + urllib.parse.quote(self.SCOPES, safe=","))
            req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
            with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT_S) as r:
                d = json.load(r)
            self._tok, self._exp = d["access_token"], time.time() + float(d.get("expires_in", 3000))
        else:
            out = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, timeout=60)
            if out.returncode != 0:
                raise RuntimeError("gcloud auth print-access-token failed: " + out.stderr.strip()[:200])
            self._tok, self._exp = out.stdout.strip(), time.time() + 3000
        return self._tok


class BrainRtdb:
    """GET / multi-path PATCH with the contract's retry policy. `transport(method, url, body) -> (status, text)` is injectable."""

    def __init__(self, url: str = BRAIN_RTDB_URL, tokens: TokenProvider | None = None, transport=None,
                 brain_id: str | None = None, sleep=time.sleep, attempts: int = ATTEMPTS,
                 backoff_base_s: float = BACKOFF_BASE_S, retries: int | None = None, backoff_s: float | None = None,
                 timeout_s: float | None = None, recorder=None):
        """`attempts`/`backoff_base_s` default to the contract's policy. `retries`/`backoff_s`/`timeout_s` are the
        pre-contract names (retries = attempts - 1) kept so existing brain tests can run without the backoff."""
        if retries is not None:
            attempts = retries + 1
        if backoff_s is not None:
            backoff_base_s = backoff_s
        self.attempts, self.backoff_base_s = attempts, backoff_base_s
        self.timeout_s = READ_TIMEOUT_S if timeout_s is None else timeout_s
        if not accepted_url(url):
            raise ValueError(f"refusing to write Brain data to {url}: not the dedicated sector-brain database")
        self.url = url.rstrip("/")
        self.tokens = tokens or TokenProvider()
        self.transport = transport or self._urllib
        self.brain_id = brain_id            # when set, every update is ownership-checked
        self.recorder = recorder            # consumption.ConsumptionRecorder: when set, every successful GET is recorded as ACTUAL consumption
        self._sleep = sleep
        self.writes = 0
        self.bytes_written = 0

    def _urllib(self, method: str, url: str, body: bytes | None):
        req = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace")

    def _request(self, method: str, path: str, payload=None, query: dict | None = None):
        q = {"access_token": self.tokens.token(), **(query or {})}
        url = f"{self.url}/{path.strip('/')}.json?" + urllib.parse.urlencode(q)
        body = None if payload is None else json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        last = None
        for attempt in range(self.attempts):
            try:
                status, text = self.transport(method, url, body)
            except Exception as e:                       # network-level failure
                status, text = None, str(e)
            if status is not None and 200 <= status < 300:
                if body:
                    self.writes += 1
                    self.bytes_written += len(body)
                return json.loads(text) if text else None
            last = f"{method} /{path.strip('/')} -> {status}: {str(text)[:200]}"
            if not should_retry(status):
                break
            if attempt < self.attempts - 1:
                self._sleep(self.backoff_base_s * (2 ** attempt))
        raise BrainRtdbError(last)

    def get(self, path: str, shallow: bool = False):
        value = self._request("GET", path, query={"shallow": "true"} if shallow else None)
        if self.recorder is not None:
            self.recorder.observe(path, value, shallow)
        return value

    def consumed(self) -> list[dict] | None:
        """The execution's ACTUAL consumption so far (consumption-lineage-v1), or None when nothing is being recorded."""
        return self.recorder.entries() if self.recorder is not None else None

    def update(self, updates: dict):
        """One atomic multi-location update ({"a/b": v, ...}); None deletes. Keys and ownership are checked first."""
        if not updates:
            return None
        clean = {k.lstrip("/"): v for k, v in updates.items()}
        check_update(clean)
        if self.brain_id:
            assert_owned(clean, self.brain_id)
        return self._request("PATCH", "", clean, query={"print": "silent"})

    def delete(self, path: str):
        return self.update({path: None})


class DryRunStore:
    """Same interface as BrainRtdb, applied to an in-memory tree. Used by tests and `--dry-run`."""

    def __init__(self, tree: dict | None = None, brain_id: str | None = None, recorder=None):
        self.tree = tree if tree is not None else {}
        self.patches: list[dict] = []
        self.brain_id = brain_id
        self.recorder = recorder
        self.writes = 0
        self.bytes_written = 0

    def get(self, path: str, shallow: bool = False):
        node = self.tree
        for p in [p for p in path.split("/") if p]:
            if not isinstance(node, dict) or p not in node:
                node = None
                break
            node = node[p]
        value = {k: True for k in node} if (shallow and isinstance(node, dict)) else node
        if self.recorder is not None:
            self.recorder.observe(path, value, shallow)
        return value

    def consumed(self) -> list[dict] | None:
        return self.recorder.entries() if self.recorder is not None else None

    def update(self, updates: dict):
        if not updates:
            return None
        clean = {k.lstrip("/"): v for k, v in updates.items()}
        body = json.dumps(clean, allow_nan=False)          # the live writer's serialization guard
        check_update(clean)
        if self.brain_id:
            assert_owned(clean, self.brain_id)
        self.patches.append(clean)
        self.writes += 1
        self.bytes_written += len(body)
        for path, val in clean.items():
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
        return None

    def delete(self, path: str):
        return self.update({path: None})

    def dump(self, out_path: str) -> None:
        with open(out_path, "w") as f:
            json.dump(self.tree, f, indent=1, sort_keys=True)


def check_schema(store) -> int | None:
    """Abort before any write if /schemaVersion is present and not the one this platform speaks."""
    v = store.get("schemaVersion")
    if v is not None and v != SCHEMA_VERSION:
        raise BrainRtdbError(f"Brain RTDB schemaVersion is {v}; this platform writes schema {SCHEMA_VERSION}")
    return v
