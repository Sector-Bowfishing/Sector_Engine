"""api.weather.gov access for the Weather Brain (the only network code in the runtime). NWS terms: U.S. Government data, public domain,
no key; every request sends a self-identifying User-Agent and `Accept: application/geo+json` (the package's NWS_PROVIDER.md).

Request budget per lake: the /points lookup and its station list are static and cached (PointCache, refreshed after 30 days); each run
fetches one gridpoint per distinct grid cell and one observation window per distinct station (stations shared by several lakes are
fetched once). Requests are paced; 429/5xx/transport errors are retried with backoff; a 404 from /points means outside NWS coverage.

The point cache is a durable file OUTSIDE the repository (NWS asks clients to cache /points): `--point-cache FILE` or
$SECTOR_WEATHER_POINT_CACHE (a runner's data folder, e.g. Pulse's {data}). Entries are keyed by lake id AND the lake coordinate rounded to the
4 decimals the /points request uses, so a moved lake point is a miss. An entry is used for POINT_CACHE_DAYS; a cached gridpoint or station URL
that answers 404 or a redirect (301/308) is revalidated (publish.run). An unreadable or foreign file is ignored and rewritten, never fatal.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import contract as C

BASE = "https://api.weather.gov"
DEFAULT_USER_AGENT = "Sector-WeatherBrain/0.1 (io.sector.co; read-only public data)"
POINT_CACHE_DAYS = 30
POINT_CACHE_ENV = "SECTOR_WEATHER_POINT_CACHE"
POINT_CACHE_SCHEMA = "sector-weather-point-cache-v2"


class OutOfCoverage(Exception):
    pass


class FetchError(Exception):
    pass


class Moved(FetchError):
    """A request that NWS answered with a redirect (301/308, or a followed redirect to another path). `doc` is the redirected body when it
    was read, so a caller that did not take the URL from the cache can still use it; a cached URL is revalidated instead."""

    def __init__(self, url: str, location: str | None, doc: dict | None = None):
        super().__init__(f"moved: {url} -> {location}")
        self.url, self.location, self.doc = url, location, doc


def _path(url: str | None) -> str:
    return (url or "").split("?", 1)[0].rstrip("/")


class NwsHttp:
    def __init__(self, user_agent: str | None = None, timeout: float = 10.0, pace_s: float = 0.25, attempts: int = 4, opener=None):
        self.ua = user_agent or os.environ.get("SECTOR_WEATHER_USER_AGENT") or DEFAULT_USER_AGENT
        self.timeout, self.pace, self.attempts = timeout, pace_s, attempts
        self._open = opener or urllib.request.urlopen
        self._last = 0.0
        self.requests = 0

    def get(self, url: str, detect_moved: bool = False) -> dict:
        """GET a NWS URL. With detect_moved, a redirect raises Moved (carrying the body when the opener followed it)."""
        if not url.startswith(BASE + "/"):
            raise FetchError(f"refusing a non-NWS URL: {url[:80]}")
        err = None
        for n in range(self.attempts):
            wait = self._last + self.pace - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept": "application/geo+json"})
            try:
                with self._open(req, timeout=self.timeout) as r:
                    doc = json.loads(r.read())
                    final = r.geturl() if hasattr(r, "geturl") else url
                if detect_moved and _path(final) != _path(url):
                    raise Moved(url, final, doc)
                return doc
            except urllib.error.HTTPError as e:
                if e.code in (301, 308) and detect_moved:
                    raise Moved(url, (e.headers or {}).get("Location") if e.headers else None) from None
                if e.code == 404:
                    raise OutOfCoverage(url) from None
                if e.code != 429 and e.code < 500:
                    raise FetchError(f"HTTP {e.code} {url}") from None
                err = f"HTTP {e.code}"
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                err = repr(e)
            time.sleep(1.5 * 2 ** n)
        raise FetchError(f"{err} after {self.attempts} attempts: {url}")


class LiveSource:
    """The four NWS reads the runtime needs, behind the same interface the tests' FixtureSource implements."""

    def __init__(self, http: NwsHttp | None = None):
        self.http = http or NwsHttp()

    def point(self, lat: float, lon: float) -> dict:
        return self.http.get(f"{BASE}/points/{lat:.4f},{lon:.4f}")

    def stations(self, url: str) -> dict:
        return self.http.get(url)

    def observations(self, station: str, now: datetime) -> dict:
        start = (now - timedelta(hours=C.OBS_LOOKBACK_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.http.get(f"{BASE}/stations/{urllib.parse.quote(station)}/observations?start={start}&limit=200", detect_moved=True)

    def grid(self, url: str) -> dict:
        return self.http.get(url, detect_moved=True)


def point_key(lake: dict) -> str:
    """Lake id + the coordinate as the /points request sends it (4 decimals): a lake whose point moves gets a new entry."""
    return f"{lake['id']}@{float(lake['lat']):.4f},{float(lake['lon']):.4f}"


def default_point_cache_path(given: str | None) -> str | None:
    """--point-cache when given, else $SECTOR_WEATHER_POINT_CACHE, else None (no cache: every run resolves /points)."""
    return given or os.environ.get(POINT_CACHE_ENV) or None


class PointCache:
    """point_key -> {gridpoint, forecastGridData, stations[], cachedAt} (or {outOfCoverage: true, cachedAt}). A JSON file
    {schema, entries}; static NWS metadata only (no observation, no forecast value, no credential).

    get() is a hit only for an entry younger than ttl_days (and not stamped more than a day in the future); a malformed entry is a miss.
    A file that cannot be read, is not JSON or has another schema (including the v1 lakeId-keyed file) starts empty and is rewritten on save().
    save() is atomic (temp file + rename) and creates the parent folder; a failed save is reported on stderr and never fails the run."""

    def __init__(self, path: str | None, ttl_days: int = POINT_CACHE_DAYS):
        self.path, self.ttl_days, self.entries = path, ttl_days, {}
        self.load_error: str | None = None
        self.stats = {"hits": 0, "misses": 0, "expired": 0, "revalidated": 0}
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
                if isinstance(doc, dict) and doc.get("schema") == POINT_CACHE_SCHEMA and isinstance(doc.get("entries"), dict):
                    self.entries = {k: v for k, v in doc["entries"].items() if isinstance(k, str) and isinstance(v, dict)}
                else:
                    self.load_error = "unrecognised point-cache file (ignored; rewritten on save)"
            except (OSError, ValueError) as e:
                self.load_error = f"unreadable point-cache file (ignored; rewritten on save): {type(e).__name__}"

    @property
    def data(self) -> dict:                                     # the entries, for callers that only read
        return self.entries

    def get(self, lake: dict, now: datetime) -> dict | None:
        e = self.entries.get(point_key(lake))
        if not e:
            self.stats["misses"] += 1
            return None
        try:
            at = datetime.fromisoformat(str(e["cachedAt"]).replace("Z", "+00:00"))
            age = now - at
        except (KeyError, ValueError, TypeError):
            self.stats["misses"] += 1
            return None
        if age >= timedelta(days=self.ttl_days) or age < -timedelta(days=1):
            self.stats["expired"] += 1
            return None
        if not e.get("outOfCoverage") and not (e.get("forecastGridData") and isinstance(e.get("stations"), list)):
            self.stats["misses"] += 1
            return None
        self.stats["hits"] += 1
        return e

    def put(self, lake: dict, entry: dict) -> None:
        self.entries[point_key(lake)] = entry

    def invalidate(self, lake: dict) -> None:
        if self.entries.pop(point_key(lake), None) is not None:
            self.stats["revalidated"] += 1

    def save(self) -> None:
        if not self.path:
            return
        tmp = f"{self.path}.{os.getpid()}.tmp"
        try:
            parent = os.path.dirname(os.path.abspath(self.path))
            os.makedirs(parent, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"schema": POINT_CACHE_SCHEMA, "entries": self.entries}, fh, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except OSError as e:
            print(f"warning: point cache not saved ({type(e).__name__}); the next run resolves /points again", file=sys.stderr)
            try:
                os.remove(tmp)
            except OSError:
                pass
