"""api.weather.gov access for the Weather Brain (the only network code in the runtime). NWS terms: U.S. Government data, public domain,
no key; every request sends a self-identifying User-Agent and `Accept: application/geo+json` (the package's NWS_PROVIDER.md).

Request budget per lake: the /points lookup and its station list are static and cached (PointCache, refreshed after 30 days); each run
fetches one gridpoint per distinct grid cell and one observation window per distinct station (stations shared by several lakes are
fetched once). Requests are paced; 429/5xx/transport errors are retried with backoff; a 404 from /points means outside NWS coverage.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import contract as C

BASE = "https://api.weather.gov"
DEFAULT_USER_AGENT = "Sector-WeatherBrain/0.1 (io.sector.co; read-only public data)"
POINT_CACHE_DAYS = 30


class OutOfCoverage(Exception):
    pass


class FetchError(Exception):
    pass


class NwsHttp:
    def __init__(self, user_agent: str | None = None, timeout: float = 10.0, pace_s: float = 0.25, attempts: int = 4, opener=None):
        self.ua = user_agent or os.environ.get("SECTOR_WEATHER_USER_AGENT") or DEFAULT_USER_AGENT
        self.timeout, self.pace, self.attempts = timeout, pace_s, attempts
        self._open = opener or urllib.request.urlopen
        self._last = 0.0
        self.requests = 0

    def get(self, url: str) -> dict:
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
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
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
        return self.http.get(f"{BASE}/stations/{urllib.parse.quote(station)}/observations?start={start}&limit=200")

    def grid(self, url: str) -> dict:
        return self.http.get(url)


class PointCache:
    """lakeId -> {gridpoint, forecastGridData, stations[], cachedAt} (or {outOfCoverage: true}). A JSON file; static metadata only."""

    def __init__(self, path: str | None):
        self.path, self.data = path, {}
        if path and os.path.exists(path):
            try:
                self.data = json.load(open(path))
            except (OSError, ValueError):
                self.data = {}

    def get(self, lake_id: str, now: datetime) -> dict | None:
        e = self.data.get(lake_id)
        if not e:
            return None
        try:
            at = datetime.fromisoformat(e["cachedAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            return None
        return e if (now - at).days < POINT_CACHE_DAYS else None

    def put(self, lake_id: str, entry: dict) -> None:
        self.data[lake_id] = entry

    def save(self) -> None:
        if self.path:
            tmp = self.path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(self.data, fh, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
