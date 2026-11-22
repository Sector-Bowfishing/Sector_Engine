"""Read-only HTTP for the Generation Brain's source readers: bounded, classified retries and an access gate.

Every request goes through `Fetcher.get`, which
  * refuses a provider whose source-access status (knowledge/source_access.json) is not ALLOWED, before any request is made;
  * reads one URL at most once per run (a shared page such as SWPA's daily schedule serves every project from one GET);
  * retries only transient failures (timeout, connection error, HTTP 408/429/500/502/503/504) at most `max_attempts` times with a
    jittered exponential backoff, honours Retry-After up to 30 s, and never retries a permanent status (the Lake Brain CWMS policy);
  * never writes anything (GET only).
The transport is injected: tests use a fixture transport and never reach the network."""
from __future__ import annotations

import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

USER_AGENT = "Sector-GenerationBrain/0.1 (io.sector.co; read-only public data)"
TRANSIENT = frozenset({408, 429, 500, 502, 503, 504})


class TransportError(Exception):
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind


@dataclass
class Response:
    status: int
    body: bytes
    retry_after: float | None = None


Transport = Callable[[str, dict, float], Response]


def live_transport(url: str, headers: dict, timeout: float) -> Response:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, r.read(64 * 1024 * 1024))
    except urllib.error.HTTPError as e:
        ra = e.headers.get("Retry-After") if e.headers else None
        try:
            ra_s = float(ra) if ra else None
        except ValueError:
            ra_s = None
        return Response(e.code, e.read() if hasattr(e, "read") else b"", ra_s)
    except TimeoutError as e:
        raise TransportError("timeout", str(e)) from None
    except (urllib.error.URLError, OSError) as e:
        raise TransportError("connection", str(e)[:160]) from None


@dataclass
class FetchResult:
    ok: bool
    body: bytes = b""
    error: str | None = None
    attempts: int = 0


@dataclass
class Fetcher:
    access: dict                                   # source_access.json "providers"
    transport: Transport = live_transport
    sleep: Callable[[float], None] = time.sleep
    jitter: Callable[[], float] = random.random
    max_attempts: int = 3
    timeout_s: float = 30.0
    log: Callable[[str], None] = lambda line: None
    requests: list = field(default_factory=list)   # (provider, url, outcome) for the run record
    _memo: dict = field(default_factory=dict)

    def allowed(self, provider: str) -> tuple[bool, str]:
        p = self.access.get(provider)
        if not p:
            return False, f"{provider}: not in the source-access list"
        if p.get("status") != "ALLOWED":
            return False, f"{provider}: source access {p.get('status')} ({p.get('agency')}); not read"
        return True, ""

    def get(self, provider: str, url: str, accept: str = "application/json") -> FetchResult:
        ok, why = self.allowed(provider)
        if not ok:
            self.requests.append((provider, url, "REFUSED_ACCESS"))
            return FetchResult(False, error=why)
        if url in self._memo:
            return self._memo[url]
        last = "unreachable"
        res = None
        for attempt in range(1, self.max_attempts + 1):
            retry_after = None
            try:
                r = self.transport(url, {"Accept": accept}, self.timeout_s)
            except TransportError as e:
                last = str(e)
            else:
                if 200 <= r.status < 300:
                    res = FetchResult(True, r.body, None, attempt)
                    break
                if r.status not in TRANSIENT:
                    res = FetchResult(False, error=f"HTTP {r.status} (permanent; not retried)", attempts=attempt)
                    break
                last, retry_after = f"HTTP {r.status}", r.retry_after
                if retry_after is not None and retry_after > 30:
                    res = FetchResult(False, error=f"HTTP {r.status} with Retry-After {int(retry_after)} s (over the 30 s cap)", attempts=attempt)
                    break
            if attempt == self.max_attempts:
                break
            wait = min(10.0, 2.0 * 2 ** (attempt - 1)) * (0.5 + 0.5 * min(max(self.jitter(), 0.0), 1.0))
            wait = max(wait, retry_after or 0.0)
            self.log(f"{provider}: attempt {attempt}/{self.max_attempts} {last}; retrying in {wait:.1f} s")
            self.sleep(wait)
        if res is None:
            res = FetchResult(False, error=f"{last} after {self.max_attempts} attempts", attempts=self.max_attempts)
        self.requests.append((provider, url, "OK" if res.ok else res.error))
        self._memo[url] = res
        return res
