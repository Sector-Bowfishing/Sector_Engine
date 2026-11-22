"""Shared test helpers: a fixture-backed NWS source (the LiveSource interface) and hand-built observation builders."""
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(HERE, "fixtures", "recorded")
HAND = os.path.join(HERE, "fixtures", "hand_built")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RECORDED_NOW = datetime(2026, 11, 6, 20, 51, tzinfo=timezone.utc)      # the recording time of the Engine fixtures

LAKES = {
    "Guntersville|AL": {"id": "Guntersville|AL", "lat": 34.42, "lon": -86.26, "prefix": "guntersville"},
    "Champlain|VT": {"id": "Champlain|VT", "lat": 44.47, "lon": -73.3, "prefix": "champlain"},
}


def load(path):
    with open(path) as fh:
        return json.load(fh)


class FixtureSource:
    """Serves the recorded files; a station with no recorded file raises like a failed fetch would not: it returns no observations."""

    def __init__(self, root=REC, overrides=None):
        self.root, self.overrides, self.calls = root, overrides or {}, []

    def _prefix(self, lat, lon):
        return next(l["prefix"] for l in LAKES.values() if abs(l["lat"] - lat) < 1e-6 and abs(l["lon"] - lon) < 1e-6)

    def point(self, lat, lon):
        self.calls.append(("point", lat, lon))
        p = self._prefix(lat, lon)
        doc = load(os.path.join(self.root, f"{p}-points.json"))
        self._last = p
        return doc

    def stations(self, url):
        self.calls.append(("stations", url))
        p = "guntersville" if "HUN" in url else "champlain"
        return load(os.path.join(self.root, f"{p}-stations.json"))

    def observations(self, station, now):
        self.calls.append(("observations", station))
        if station in self.overrides:
            return self.overrides[station]
        for p in ("guntersville", "champlain"):
            f = os.path.join(self.root, f"{p}-obs-{station}.json")
            if os.path.exists(f):
                return load(f)
        return {"type": "FeatureCollection", "features": []}

    def grid(self, url):
        self.calls.append(("grid", url))
        if url in self.overrides:
            return self.overrides[url]
        p = "guntersville" if "HUN" in url else "champlain"
        return load(os.path.join(self.root, f"{p}-grid.json"))


def obs_feature(station, at, *, temp_c=None, dew_c=None, rh=None, alt_pa=None, slp_pa=None, wind_kmh=None, wind_dir=None,
                text=None, icon=None, precip_mm=None):
    """One observation in the api.weather.gov shape (HAND-BUILT; units as NWS sends them)."""
    q = lambda v, u: {"unitCode": f"wmoUnit:{u}", "value": v, "qualityControl": "V" if v is not None else "Z"}
    return {"properties": {
        "station": f"https://api.weather.gov/stations/{station}", "timestamp": at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "textDescription": text or "", "icon": icon, "temperature": q(temp_c, "degC"), "dewpoint": q(dew_c, "degC"),
        "relativeHumidity": q(rh, "percent"), "windSpeed": q(wind_kmh, "km_h-1"), "windDirection": q(wind_dir, "degree_(angle)"),
        "barometricPressure": q(alt_pa, "Pa"), "seaLevelPressure": q(slp_pa, "Pa"), "precipitationLastHour": q(precip_mm, "mm"),
        "cloudLayers": []}}


def collection(features):
    return {"type": "FeatureCollection", "features": sorted(features, key=lambda f: f["properties"]["timestamp"], reverse=True)}


def hourly(now, hours, fn, station="KTST", minute=53):
    """Hourly observations ending at the last :53 before `now`, oldest first in fn's index (i = 0 is `hours` before the newest)."""
    newest = now.replace(minute=minute, second=0, microsecond=0)
    if newest > now:
        newest -= timedelta(hours=1)
    return [obs_feature(station, newest - timedelta(hours=hours - i), **fn(i)) for i in range(hours + 1)]
