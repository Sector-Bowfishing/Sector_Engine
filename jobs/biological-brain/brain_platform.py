"""Brain Platform plumbing (Sector Engine side). Copied verbatim from the Water Clarity Brain
(brain/water-clarity d206e01c, jobs/water-clarity-brain/brain_platform.py) so both brains speak the same
platform; lift into a shared module when the Brain platform is unified.

Implements the Sector Ops Brain Platform contract
(Sector_Ops docs/SECTOR_BRAIN_RTDB_SCHEMA.md, docs/BRAIN_INTEGRATION_REQUIREMENTS.md):

  * canonical lake key  = re.sub(r"[^A-Za-z0-9]+", "_", lakeId), the slug the
    lake-surface job already uses for gs://sector-lake-surface/lakes/<slug>/;
    collisions fail the write (contract section 3).
  * the dedicated Brain RTDB (instance sector-brain in project sector-9393c),
    written over the RTDB REST API with a server credential. Writes are
    multi-location PATCHes, so every request is atomic and touches only the
    leaf paths it names (other brains' nodes are never replaced).

Nothing here knows anything about clarity. It is deliberately stdlib-only so
the other brains can lift it into a shared module later.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

SCHEMA_VERSION = 1
BRAIN_RTDB_URL = "https://sector-brain.firebaseio.com"
APP_DATABASES = ("sector-9393c-default-rtdb", "sector-dev-1f4d0")   # customer data: never written here

_SLUG = re.compile(r"[^A-Za-z0-9]+")


def lake_key(lake_id: str) -> str:
    """Brain RTDB key for a canonical lake ID (Engine slug)."""
    return _SLUG.sub("_", lake_id)


def lake_keys(lake_ids) -> dict[str, str]:
    """lakeId -> key for a whole directory; raises on a slug collision."""
    out, seen = {}, {}
    for lid in lake_ids:
        k = lake_key(lid)
        if k in seen and seen[k] != lid:
            raise ValueError(f"lake key collision: {seen[k]!r} and {lid!r} both map to {k!r}")
        seen[k] = lid
        out[lid] = k
    return out


def iso(t: dt.datetime | None) -> str | None:
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def age_hours(at: str | None, now: dt.datetime) -> float | None:
    t = parse_time(at)
    return None if t is None else round((now - t).total_seconds() / 3600, 2)


def event_id(at: dt.datetime, tag: str, n: int) -> str:
    """Time-sortable activity key (contract: eventId sorts by time)."""
    return f"{int(at.timestamp() * 1000):013d}-{tag}-{n:03d}"


# ---------------------------------------------------------------- credentials
class TokenProvider:
    """OAuth2 access token for the Brain RTDB and Google APIs.

    On Cloud Run the metadata server issues it for the job's service account;
    on a developer machine the already-authenticated gcloud CLI does. A static
    token (BRAIN_ACCESS_TOKEN) is accepted for tests. No key files.
    """
    SCOPES = "https://www.googleapis.com/auth/firebase.database,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform"

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
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.load(r)
            self._tok, self._exp = d["access_token"], time.time() + float(d.get("expires_in", 3000))
        else:
            out = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, timeout=60)
            if out.returncode != 0:
                raise RuntimeError("gcloud auth print-access-token failed: " + out.stderr.strip()[:200])
            self._tok, self._exp = out.stdout.strip(), time.time() + 3000
        return self._tok


# ---------------------------------------------------------------- RTDB client
class BrainRtdbError(RuntimeError):
    pass


class BrainRtdb:
    """Minimal Brain RTDB REST client: GET, multi-path PATCH, retries.

    `transport(method, url, body) -> (status, text)` is injectable so tests can
    run without a network. Every failure is raised as BrainRtdbError; callers
    decide what a failure means (the Clarity publisher never lets one reach
    production Clarity).
    """

    def __init__(self, url: str = BRAIN_RTDB_URL, tokens: TokenProvider | None = None,
                 transport=None, retries: int = 3, backoff_s: float = 1.5, timeout_s: float = 30):
        if any(db in url for db in APP_DATABASES):
            raise ValueError(f"refusing to write Brain data to an app database: {url}")
        self.url = url.rstrip("/")
        self.tokens = tokens or TokenProvider()
        self.transport = transport or self._urllib
        self.retries, self.backoff_s, self.timeout_s = retries, backoff_s, timeout_s
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
        for attempt in range(self.retries + 1):
            try:
                status, text = self.transport(method, url, body)
            except Exception as e:          # network-level failure
                status, text = None, str(e)
            if status is not None and 200 <= status < 300:
                if body:
                    self.writes += 1
                    self.bytes_written += len(body)
                return json.loads(text) if text else None
            last = f"{method} /{path.strip('/')} -> {status}: {text[:200]}"
            if status is not None and 400 <= status < 500 and status != 429:
                break                       # a rejected request will not succeed on retry
            if attempt < self.retries:
                time.sleep(self.backoff_s * (2 ** attempt))
        raise BrainRtdbError(last)

    def get(self, path: str, shallow: bool = False):
        return self._request("GET", path, query={"shallow": "true"} if shallow else None)

    def update(self, updates: dict):
        """One atomic multi-location update ({"/a/b": v, ...}); None deletes."""
        if not updates:
            return None
        return self._request("PATCH", "", {k.lstrip("/"): v for k, v in updates.items()})


def check_schema(rtdb: BrainRtdb) -> int | None:
    """Platform schema version, or None when the platform has not written one.

    A version this brain does not speak aborts the run before any write
    (contract section 10: breaking changes bump /schemaVersion).
    """
    v = rtdb.get("schemaVersion")
    if v is not None and v != SCHEMA_VERSION:
        raise BrainRtdbError(f"Brain RTDB schemaVersion is {v}; this brain writes schema {SCHEMA_VERSION}")
    return v
