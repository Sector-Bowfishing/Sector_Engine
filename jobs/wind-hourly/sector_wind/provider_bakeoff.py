"""Prospective live provider bake-off (Stage 3D.1 §C; pre-registered sha 2f935d06…). Research only: never read by
the Candidate, never written to the authoritative archive.

  python -m sector_wind.provider_bakeoff collect            # one collection pass (run hourly)
  python -m sector_wind.provider_bakeoff status             # per-source health + skill vs METAR (and live NBM)
  python -m sector_wind.provider_bakeoff loop               # local interim scheduler: collect at :20 every hour

Storage (isolated):  ~/Library/Caches/sector-wind/wind-validation/provider-bakeoff/
  raw/<YYYYMMDD>/<HH>/<source>__<point>.json   immutable payload + sha256 + request
  normalized/<YYYYMMDD>.jsonl                   ProviderWindSample rows (missing = null, never 0)
Sources need no credentials. A paid source is added only after Michael approves a key."""
from __future__ import annotations

import argparse, glob, gzip, hashlib, json, math, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

ROOT = os.environ.get("SECTOR_WIND_BAKEOFF", os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/provider-bakeoff"))
MIRROR = os.path.expanduser("~/Library/Caches/sector-wind/live-mirror")
DECODER = "provider_bakeoff 1.0.0"
UA = "SectorWind research bake-off (contact: mgcather07@gmail.com)"
LEADS = (1, 3, 6, 12, 18, 24)
POINTS = {   # the 8 frozen stations + 4 lake centres; identical for every source (pre-registered)
    "8A1": (34.3996, -86.2682), "4A6": (34.6887, -86.0059), "DCU": (34.6525, -86.9453), "HSV": (34.6439, -86.7861),
    "9A4": (34.6594, -87.3488), "MSL": (34.7438, -87.5996), "SNH": (35.1703, -88.2167), "15M": (34.7723, -88.1659),
    "lake:guntersville": (34.42, -86.23), "lake:wheeler": (34.66, -87.05), "lake:wilson": (34.80, -87.52), "lake:pickwick": (34.95, -88.15)}
# Open-Meteo explicit models (ids verified in the Stage 3D.1 Open-Meteo audit). best_match is collected because
# production uses it; it is a delivery/selection product, not an independent model.
OPEN_METEO_MODELS = ["best_match", "ncep_nbm_conus", "ncep_hrrr_conus", "gfs_seamless", "ecmwf_ifs025", "icon_seamless", "gem_seamless"]


def iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _store_raw(now, source, point, url, body):
    d = os.path.join(ROOT, "raw", f"{now:%Y%m%d}", f"{now:%H}"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{source}__{point.replace(':', '_')}.json")
    if os.path.exists(p):
        return p
    rec = {"source": source, "point": point, "request": url, "retrievedAt": iso(now), "sha256": hashlib.sha256(body).hexdigest(),
           "payload": body.decode("utf-8", "replace")}
    open(p, "w").write(json.dumps(rec)); os.chmod(p, 0o444)
    return p


def sample(source, product, point, issue, retrieved, valid, speed, dirn, gust, meta=None):
    """ProviderWindSample. kind = forecast. Missing stays None (never 0)."""
    lead = (valid - issue).total_seconds() / 3600 if issue else None
    u = v = None
    if speed is not None and dirn is not None:
        u, v = -speed * math.sin(math.radians(dirn)), -speed * math.cos(math.radians(dirn))
    la, lo = POINTS[point]
    return {"provider": source, "product": product, "kind": "forecast", "point": point, "latitude": la, "longitude": lo,
            "issueTime": iso(issue) if issue else None, "retrievedAt": iso(retrieved), "validTime": iso(valid),
            "leadHours": round(lead, 2) if lead is not None else None,
            "leadFromRetrievalHours": round((valid - retrieved).total_seconds() / 3600, 2),
            "speedMS": speed, "dirFromDeg": dirn, "u": u, "v": v, "gustMS": gust,
            "speedPercentiles": None, "gustPercentiles": None, "speedExceedanceProbabilities": None,
            "gustExceedanceProbabilities": None, "sourceMetadata": meta or {}, "decoderVersion": DECODER}


# ── adapters ─────────────────────────────────────────────────────────────────────────────────

_GRID = {}


def nws(now):
    """NWS NDFD gridpoint forecast (forecaster-edited, NBM-initialised). km/h intervals -> hourly m/s; issue = updateTime."""
    out = []
    for pt, (la, lo) in POINTS.items():
        try:
            if pt not in _GRID:
                _GRID[pt] = json.loads(_get(f"https://api.weather.gov/points/{la:.4f},{lo:.4f}"))["properties"]["forecastGridData"]
            url = _GRID[pt]; body = _get(url); _store_raw(now, "nws_ndfd", pt, url, body)
            p = json.loads(body)["properties"]; issue = datetime.fromisoformat(p["updateTime"])
            def expand(key):
                vals = {}
                for e in p.get(key, {}).get("values", []):
                    st, dur = e["validTime"].split("/"); t0 = datetime.fromisoformat(st)
                    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?", dur); hrs = int(m.group(1) or 0) * 24 + int(m.group(2) or 0)
                    for k in range(max(hrs, 1)):
                        vals[t0 + timedelta(hours=k)] = e["value"]
                return vals
            sp, dr, gu = expand("windSpeed"), expand("windDirection"), expand("windGust")
            kmh = lambda x: None if x is None else x / 3.6
            for L in LEADS:
                vt = (now + timedelta(hours=L)).replace(minute=0, second=0, microsecond=0)
                out.append(sample("nws_ndfd", "NDFD gridpoint (api.weather.gov)", pt, issue, now, vt, kmh(sp.get(vt)), dr.get(vt), kmh(gu.get(vt)),
                                  {"gridpoint": url}))
        except Exception as e:
            out.append({"provider": "nws_ndfd", "point": pt, "error": repr(e)[:200], "retrievedAt": iso(now)})
    return out


def open_meteo(now):
    """Open-Meteo free API, explicit models. No issue time is exposed (lead counted from retrieval)."""
    out = []
    lat = ",".join(f"{v[0]:.4f}" for v in POINTS.values()); lon = ",".join(f"{v[1]:.4f}" for v in POINTS.values())
    for m in OPEN_METEO_MODELS:
        q = {"latitude": lat, "longitude": lon, "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m", "wind_speed_unit": "ms",
             "timezone": "GMT", "forecast_days": 2}
        if m != "best_match":
            q["models"] = m
        url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)
        try:
            body = _get(url); _store_raw(now, f"openmeteo_{m}", "all", url, body)
            js = json.loads(body); js = js if isinstance(js, list) else [js]
            for pt, j in zip(POINTS, js):
                h = j["hourly"]; idx = {datetime.fromisoformat(t).replace(tzinfo=timezone.utc): i for i, t in enumerate(h["time"])}
                for L in LEADS:
                    vt = (now + timedelta(hours=L)).replace(minute=0, second=0, microsecond=0); i = idx.get(vt)
                    g = lambda k: None if i is None or h.get(k) is None else h[k][i]
                    out.append(sample(f"openmeteo_{m}", f"Open-Meteo {m}", pt, None, now, vt, g("wind_speed_10m"), g("wind_direction_10m"),
                                      g("wind_gusts_10m"), {"model": m, "gridLat": j.get("latitude"), "gridLon": j.get("longitude")}))
        except Exception as e:
            out.append({"provider": f"openmeteo_{m}", "point": "all", "error": repr(e)[:200], "retrievedAt": iso(now)})
    return out


ADAPTERS = {"nws_ndfd": nws, "openmeteo": open_meteo}


def collect(now=None):
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    rows = []
    for name, fn in ADAPTERS.items():
        rows += fn(now)
    d = os.path.join(ROOT, "normalized"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{now:%Y%m%d}.jsonl"), "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    errs = [r for r in rows if "error" in r]
    print(f"{iso(now)} collected {len(rows) - len(errs)} samples, {len(errs)} errors", flush=True)
    for e in errs[:5]:
        print("  ERROR", e["provider"], e["point"], e["error"], flush=True)
    return rows


# ── status / scoring ─────────────────────────────────────────────────────────────────────────

def _obs():
    out = {}
    for p in glob.glob(os.path.join(MIRROR, "metar", "*.json.gz")):
        for o in json.load(gzip.open(p)).get("observations", []):
            t = datetime.strptime(o["validTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            h = (t + timedelta(minutes=30)).replace(minute=0, second=0)
            if abs((t - h).total_seconds()) <= 600:
                k = (o["station"], h)
                if k not in out or abs((t - h).total_seconds()) < out[k][0]:
                    out[k] = (abs((t - h).total_seconds()), o)
    return {k: v[1] for k, v in out.items()}


def status():
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, "normalized", "*.jsonl"))):
        rows += [json.loads(l) for l in open(p) if l.strip()]
    obs = _obs()
    by = {}
    for r in rows:
        by.setdefault(r["provider"], []).append(r)
    print(f"PROVIDER BAKE-OFF  ({ROOT})")
    print(f"{'source':<26}{'days':>5}{'rows':>7}{'miss%':>7}{'errors':>7}  {'latest':<21}{'n':>6}{'MAE':>7}{'bias':>7}{'dir22':>7}{'>=15mph obs/hit':>17}{'gust20 obs/hit':>16}")
    for src, rs in sorted(by.items()):
        ok = [r for r in rs if "error" not in r]; errs = len(rs) - len(ok)
        miss = sum(r["speedMS"] is None for r in ok) / max(len(ok), 1)
        days = len({r["retrievedAt"][:10] for r in rs}); latest = max(r["retrievedAt"] for r in rs)
        pairs = []
        for r in ok:
            if r["point"].startswith("lake:") or r["speedMS"] is None:
                continue
            o = obs.get((r["point"], datetime.strptime(r["validTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)))
            if o and o["speedMS"] is not None:
                pairs.append((r, o))
        e = np.array([r["speedMS"] - o["speedMS"] for r, o in pairs])
        de = [abs(((r["dirFromDeg"] - o["dirFromDeg"] + 180) % 360) - 180) for r, o in pairs
              if r["dirFromDeg"] is not None and o["dirFromDeg"] is not None and r["speedMS"] >= 2.6 and o["speedMS"] >= 2.6]
        e15 = (sum(o["speedMS"] >= 6.7056 for _, o in pairs), sum(o["speedMS"] >= 6.7056 and r["speedMS"] >= 6.7056 for r, o in pairs))
        g20 = (sum((o["gustMS"] or 0) >= 10.2889 for _, o in pairs), sum((o["gustMS"] or 0) >= 10.2889 and (r["gustMS"] or 0) >= 10.2889 for r, o in pairs))
        f = lambda x: f"{x:7.2f}" if x is not None else "      -"
        print(f"{src:<26}{days:>5}{len(ok):>7}{100 * miss:>6.1f}%{errs:>7}  {latest:<21}{len(pairs):>6}{f(float(np.abs(e).mean()) if len(e) else None)}"
              f"{f(float(e.mean()) if len(e) else None)}{f(float(np.mean(np.array(de) <= 22.5)) if de else None)}{str(e15):>17}{str(g20):>16}")
    if not by:
        print("  no collections yet")


def loop():
    while True:
        now = datetime.now(timezone.utc)
        nxt = now.replace(minute=20, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(hours=1)
        time.sleep((nxt - now).total_seconds())
        try:
            collect()
        except Exception as e:
            print("collect failed", repr(e), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["collect", "status", "loop"]); a = ap.parse_args()
    {"collect": collect, "status": status, "loop": loop}[a.cmd]()
