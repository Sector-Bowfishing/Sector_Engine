"""Build one lake's Weather state document (sector-brain-weather-state-v1, contracts/weather-state-v1.schema.json). Pure."""
from __future__ import annotations

from datetime import datetime

from . import contract as C
from .freshness import decide
from .reading import Reading, describe_code, forecast_rows, qpf
from .signal import evaluate


def _v(x: dict | None, nd: int | None = 1) -> dict | None:
    if not x:
        return None
    val = x["value"] if nd is None else C.r(x["value"], nd)
    return {"value": val, "at": C.iso(x["at"]), "origin": x["origin"], "station": x.get("station")}


def _trend(t: dict | None) -> dict | None:
    if not t:
        return None
    return {"trend": t["trend"], "changeInHg": round(t["change"] * C.HPA_TO_INHG, 3), "changeHPa": round(t["change"], 2), "from": C.iso(t["from"])}


def build_state(lake: dict, rd: Reading, point_info: dict, now: datetime) -> dict:
    sig = evaluate(rd)
    p = rd.pressure
    temp, rh = rd.values.get("airTemperatureF"), rd.values.get("humidityPct")
    # kind: "observation" when ANY tile rests on a fresh station observation, "forecast" when only forecast-grid values exist, "unavailable" when
    # nothing does. `origins` says, tile by tile, where each value came from, so a mixed state is described honestly (review of #234).
    tiles = {"pressure": p, "airTemperatureF": temp, "humidityPct": rh, "dewPointF": rd.values.get("dewPointF"),
             "cloudCoverPct": rd.values.get("cloudCoverPct"), "weatherCode": rd.values.get("weatherCode")}
    origins = {t: (v or {}).get("origin") for t, v in tiles.items()}
    observed_at = [v["at"] for v in tiles.values() if v and v.get("origin") == "observation"]
    kind = "observation" if observed_at else ("forecast" if any(tiles.values()) else "unavailable")
    obs_at = max(observed_at, default=None)
    fresh = decide(sig["level"], obs_at, now)
    cover, code = rd.values.get("cloudCoverPct"), rd.values.get("weatherCode")
    q6, q12 = qpf(rd.grid, now, 6), qpf(rd.grid, now, 12)
    missing = [t for t, ok in (("pressure", p), ("airTemperatureF", temp), ("humidityPct", rh), ("sky", cover or code)) if not ok]
    return {
        "schema": C.STATE_SCHEMA, "schemaVersion": C.SCHEMA_VERSION, "brainId": C.BRAIN_ID, "brainVersion": C.BRAIN_VERSION,
        "thresholdsVersion": C.THRESHOLDS_VERSION, "lakeId": lake["id"], "lakeKey": C.lake_key(lake["id"]), "kind": kind,
        "generatedAt": C.iso(now),
        "location": {"lat": lake["lat"], "lon": lake["lon"], "gridpoint": point_info.get("gridpoint"), "stations": point_info.get("stations") or []},
        "sky": {"cloudCoverPct": _v(cover, 0), "word": C.cloud_word(cover and cover["value"]), "weatherCode": _v(code, None),
                "description": describe_code(code and code["value"]), "nwsText": rd.values.get("nwsText"),
                "rain": {"lastHourIn": _v(rd.values.get("precipLastHourIn"), 2), "forecastNext6hIn": q6, "forecastNext12hIn": q12,
                                  "forecastIssuedAt": C.iso(rd.grid.update_time) if rd.grid else None}},
        "pressure": None if not p else {
            "inHg": round(p["inHg"], 2), "hPa": round(p["hPa"], 1), "at": C.iso(p["at"]), "station": p["station"], "origin": p["origin"], "kind": p["kind"],
            "seaLevelOffsetHPa": C.r(p["seaLevelOffsetHPa"], 2), "trend3h": _trend(p["trend3h"]), "trend12h": _trend(p["trend12h"]),
            "forecast": None, "forecastNote": "The NWS forecast grid has no pressure layer; no pressure forecast is published."},
        "airTemperatureF": _v(temp), "humidityPct": _v(rh, 0), "dewPointF": _v(rd.values.get("dewPointF")),
        "forecast": {"source": "NWS forecast grid (NBM-based NDFD)", "issuedAt": C.iso(rd.grid.update_time) if rd.grid else None,
                     "hourly": forecast_rows(rd.grid, now)},
        "origins": origins, "mixedOrigin": len({o for o in origins.values() if o}) > 1,
        "weatherChange": sig,
        "freshness": {**fresh, "generatedAt": C.iso(now)},
        "missing": missing,
        "provenance": {"provider": C.PROVIDER, "sourceIds": list(C.SOURCE_IDS), "rules": "NWS_WEATHER_ADAPTER_V1 (Engine adapter, ported)",
                       "estimates": "none: a value no station or forecast reported is null"},
    }


def readiness(state: dict | None, blocked: bool = False) -> str:
    if blocked:
        return "BLOCKED"
    if state is None:
        return "DISCOVERED"
    if state["kind"] == "observation" and not state["freshness"]["stale"] and not state["missing"]:
        return "CALIBRATION"
    return "DEGRADED"
