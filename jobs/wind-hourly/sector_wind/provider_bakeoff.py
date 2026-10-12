"""Prospective live provider bake-off (Stage 3D.1 §C, rebuilt for Stage 3D.2 §21–25). Research only: never read by the
Candidate, never written to the authoritative archive (the Candidate bucket is only READ, for the NBM/RTMA/METAR control).

  python -m sector_wind.provider_bakeoff collect     # one pass (run hourly)
  python -m sector_wind.provider_bakeoff status      # health per provider; skill only outside sealed windows
  python -m sector_wind.provider_bakeoff parity      # Open-Meteo NBM vs direct NOAA NBM on identical point/valid (not skill)
  python -m sector_wind.provider_bakeoff loop        # local interim scheduler: collect at :20 every hour

Providers (Stage 3D.2 §4 list only; Michael + ChatGPT reopen anything else):
  noaa_nbm            direct NOAA NBM v5.0 — the CONTROL (Candidate archive cut-outs, bilinear; issue = NBM init)
  open_meteo_nbm      Open-Meteo models=ncep_nbm_conus (transport check)
  open_meteo_best     Open-Meteo Best Match = what production uses (reference only)
  visual_crossing     Timeline API blended forecast (+ per-model datasets kept separate)      credential-gated
  meteomatics_us1k    source=mm-us1k, native and calibrated=true kept as separate products     credential-gated
  rtma                RTMA-RU analysis at the points (sourceType = analysis)
  madis               MADIS public surface obs near the four lakes (sourceType = observation, own file)
Storage:  ~/Library/Caches/sector-wind/wind-validation/provider-bakeoff/
  raw/<family>/<YYYYMMDD>/<HH>/<product>__<point>.json   immutable payload + sha256 + request (credentials stripped)
  normalized/<YYYYMMDD>.jsonl                             ProviderWindSample rows (missing = null, never 0)
  observations/<YYYYMMDD>.jsonl                           MADIS observation rows
Sealed windows: H2 2026-10-07..2026-12-31 (NBM-probability test) — status never computes skill on valid times inside it."""
from __future__ import annotations

import argparse, base64, glob, gzip, hashlib, json, math, os, re, subprocess, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

ROOT = os.environ.get("SECTOR_WIND_BAKEOFF", os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/provider-bakeoff"))
BUCKET = "gs://sector-wind-candidate/wind/v1"          # Candidate archive: READ ONLY
DECODER = "provider_bakeoff 2.0.0"
UA = "SectorWind research bake-off (contact: mgcather07@gmail.com)"
LEADS = (1, 3, 6, 12, 18, 24)
SEALED = [(datetime(2026, 10, 7, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc), "H2")]
POINTS = {   # the 8 frozen stations + 4 lake points; identical for every provider (pre-registered, no cherry-picking)
    "8A1": (34.3996, -86.2682), "4A6": (34.6887, -86.0059), "DCU": (34.6525, -86.9453), "HSV": (34.6439, -86.7861),
    "9A4": (34.6594, -87.3488), "MSL": (34.7438, -87.5996), "SNH": (35.1703, -88.2167), "15M": (34.7723, -88.1659),
    "lake:guntersville": (34.42, -86.23), "lake:wheeler": (34.66, -87.05), "lake:wilson": (34.80, -87.52), "lake:pickwick": (34.95, -88.15)}
POINT_LAKE = {"8A1": "guntersville", "4A6": "guntersville", "DCU": "wheeler", "HSV": "wheeler", "9A4": "wheeler", "MSL": "wilson",
              "SNH": "pickwick", "15M": "pickwick", "lake:guntersville": "guntersville", "lake:wheeler": "wheeler",
              "lake:wilson": "wilson", "lake:pickwick": "pickwick"}


def iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pt(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def sealed(vt):
    return next((n for a, b, n in SEALED if a <= vt < b), None)


def _get(url, timeout=60, auth=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if auth:
        h["Authorization"] = "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read()


def _strip(url):
    return re.sub(r"(key|password|access_token)=[^&]+", r"\1=REDACTED", url)


def _store_raw(now, family, product, point, url, body):
    d = os.path.join(ROOT, "raw", family, f"{now:%Y%m%d}", f"{now:%H}"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{product}__{point.replace(':', '_')}.json")
    if os.path.exists(p):
        return p
    rec = {"family": family, "product": product, "point": point, "request": _strip(url), "retrievedAt": iso(now),
           "sha256": hashlib.sha256(body).hexdigest(), "payload": body.decode("utf-8", "replace")}
    open(p, "w").write(json.dumps(rec)); os.chmod(p, 0o444)
    return p


def sample(provider, product, source_type, point, issue, retrieved, valid, speed, dirn, gust, meta=None, u=None, v=None,
           probabilities=None, percentiles=None, spread=None):
    """ProviderWindSample (Stage 3D.2 §22). Missing stays None (never 0, never manufactured)."""
    if u is None and v is None and speed is not None and dirn is not None:
        u, v = -speed * math.sin(math.radians(dirn)), -speed * math.cos(math.radians(dirn))
    la, lo = POINTS[point]
    return {"provider": provider, "product": product, "sourceType": source_type, "locationId": point, "lat": la, "lon": lo,
            "issueTime": iso(issue) if issue else None, "retrievedAt": iso(retrieved), "validTime": iso(valid),
            "leadHours": round((valid - issue).total_seconds() / 3600, 2) if issue else None,
            "leadFromRetrievalHours": round((valid - retrieved).total_seconds() / 3600, 2),
            "speedMS": speed, "directionFromDeg": dirn, "u": u, "v": v, "gustMS": gust,
            "probabilities": probabilities, "percentiles": percentiles, "spread": spread,
            "rawSourceMetadata": meta or {}, "decoderVersion": DECODER}


def err(provider, point, e, now):
    return {"provider": provider, "locationId": point, "error": repr(e)[:200], "retrievedAt": iso(now)}


def _valid_hours(now):
    base = now.replace(minute=0, second=0, microsecond=0)
    return [base + timedelta(hours=L) for L in LEADS]


# ── control: direct NOAA NBM + RTMA from the Candidate archive (read only) ─────────────────────

_GRIDS = {}


def _gcat(key):
    r = subprocess.run(["gcloud", "storage", "cat", f"{BUCKET}/{key}"], capture_output=True, timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-200:])
    return r.stdout


def _gjson(key):
    b = _gcat(key)
    return json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b), b


def _weights(product, lake, gridkey):
    from sector_wind.interp import CutoutIndex
    k = (product, lake)
    if k not in _GRIDS:
        g, _ = _gjson(gridkey); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
        _GRIDS[k] = {p: ci.weights(*POINTS[p]) for p, lk in POINT_LAKE.items() if lk == lake}
    return _GRIDS[k]


def noaa_nbm(now):
    """Newest complete NBM cycle per lake in the Candidate archive (the same decoded cut-outs the Candidate reads)."""
    from sector_wind.interp import blend, blend_wind
    out = []
    for lake in sorted(set(POINT_LAKE.values())):
        try:
            obj = raw = None
            for back in range(1, 7):
                t = (now - timedelta(hours=back)).replace(minute=0, second=0, microsecond=0)
                try:
                    obj, raw = _gjson(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz"); break
                except RuntimeError:
                    continue
            if obj is None:
                raise RuntimeError("no NBM cycle in the last 6 h")
            _store_raw(now, "noaa", "nbm", f"lake:{lake}", f"{BUCKET}/nbm/{lake}/{t:%Y%m%d%H}.json.gz", gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
            init = pt(obj["initTime"]); steps = {s["validTime"]: s for s in obj["steps"]}
            W = _weights("nbm", lake, obj["grid"])
            for p, wt in W.items():
                for vt in _valid_hours(now):
                    s = steps.get(iso(vt))
                    if not s:
                        out.append(sample("noaa_nbm", obj.get('modelVersion') or 'NBM', "forecast", p, init, now, vt, None, None, None, {"init": obj["initTime"], "status": obj.get("status")}))
                        continue
                    sp, dr = blend_wind(s["speedMS"], s["dirFromDeg"], wt)
                    pc = {k: blend(s[k], wt) for k in ("speedP10", "speedP50", "speedP90", "gustP90") if k in s} or None
                    out.append(sample("noaa_nbm", obj.get('modelVersion') or 'NBM', "forecast", p, init, now, vt, sp, dr, blend(s["gustMS"], wt),
                                      {"init": obj["initTime"], "status": obj.get("status"), "interp": wt.method}, percentiles=pc))
        except Exception as e:
            out.append(err("noaa_nbm", f"lake:{lake}", e, now))
    return out


def rtma(now):
    """Newest RTMA-RU analysis at or before the top of the hour, per lake (analysis, never 'observed')."""
    from sector_wind.interp import blend, blend_wind
    out = []
    base = now.replace(minute=0, second=0, microsecond=0)
    for lake in sorted(set(POINT_LAKE.values())):
        try:
            obj = raw = None
            for back in range(0, 8):
                t = base - timedelta(minutes=15 * back)
                try:
                    obj, raw = _gjson(f"rtma/{lake}/{t:%Y%m%d}/{t:%H%M}.json.gz"); break
                except RuntimeError:
                    continue
            if obj is None:
                raise RuntimeError("no RTMA-RU analysis in the last 2 h")
            _store_raw(now, "noaa", "rtma", f"lake:{lake}", f"{BUCKET}/rtma/{lake}/{t:%Y%m%d}/{t:%H%M}.json.gz", gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
            at = pt(obj["analysisTime"])
            for p, wt in _weights("rtma", lake, obj["grid"]).items():
                sp, dr = blend_wind(obj["speedMS"], obj["dirFromDeg"], wt)
                out.append(sample("rtma", "RTMA-RU 2.5 km", "analysis", p, at, now, at, sp, dr, blend(obj["gustMS"], wt), {"analysisTime": obj["analysisTime"]}))
        except Exception as e:
            out.append(err("rtma", f"lake:{lake}", e, now))
    return out


# ── Open-Meteo (transport check + production reference) ─────────────────────────────────────

def open_meteo(now):
    out = []
    lat = ",".join(f"{v[0]:.4f}" for v in POINTS.values()); lon = ",".join(f"{v[1]:.4f}" for v in POINTS.values())
    for prov, model in (("open_meteo_nbm", "ncep_nbm_conus"), ("open_meteo_best", "best_match")):
        q = {"latitude": lat, "longitude": lon, "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m", "wind_speed_unit": "ms",
             "timezone": "GMT", "forecast_days": 2}
        if model != "best_match":
            q["models"] = model
        url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)
        try:
            body = _get(url); _store_raw(now, "open-meteo", model, "all", url, body)
            js = json.loads(body); js = js if isinstance(js, list) else [js]
            for p, j in zip(POINTS, js):
                h = j["hourly"]; idx = {datetime.fromisoformat(t).replace(tzinfo=timezone.utc): i for i, t in enumerate(h["time"])}
                for vt in _valid_hours(now):
                    i = idx.get(vt); g = lambda k: None if i is None or h.get(k) is None else h[k][i]
                    out.append(sample(prov, f"Open-Meteo {model}", "forecast", p, None, now, vt, g("wind_speed_10m"), g("wind_direction_10m"),
                                      g("wind_gusts_10m"), {"model": model, "gridLat": j.get("latitude"), "gridLon": j.get("longitude"),
                                                            "issueTime": "not exposed by API"}))
        except Exception as e:
            out.append(err(prov, "all", e, now))
    return out


# ── Visual Crossing (credential-gated; stops at the credential boundary) ────────────────────

VC_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}/{d1}/{d2}"
VC_DATASETS = ["ndfd", "hrrr", "gfs", "ecmwf"]     # per-model output (forecastDataset), never mixed with the blend


def visual_crossing_request(lat, lon, d1, d2, key, basis_date=None, dataset=None):
    """Timeline API, unitGroup=base (m/s). basis_date -> forecastBasisDate (historical issued forecast; needs that licence).
    dataset -> forecastDataset (raw single-model output). Returns the URL (caller fetches/archives)."""
    q = {"unitGroup": "base", "include": "hours", "key": key, "contentType": "json",
         "elements": "datetime,datetimeEpoch,windspeed,winddir,windgust,source,stations"}
    if basis_date:
        q["forecastBasisDate"] = basis_date
    if dataset:
        q["forecastDataset"] = dataset
    return VC_URL.format(lat=f"{lat:.4f}", lon=f"{lon:.4f}", d1=d1, d2=d2) + "?" + urllib.parse.urlencode(q)


def visual_crossing_normalize(js, point, retrieved, product, issue=None):
    out = []
    for day in js.get("days", []):
        for h in day.get("hours", []):
            vt = datetime.fromtimestamp(h["datetimeEpoch"], timezone.utc)
            out.append(sample("visual_crossing", product, "forecast", point, issue, retrieved, vt, h.get("windspeed"), h.get("winddir"),
                              h.get("windgust"), {"source": h.get("source"), "stations": h.get("stations"), "tz": js.get("timezone"),
                                                  "issueTime": "forecastBasisDate (day only)" if issue else "not exposed"}))
    return out


def visual_crossing(now):
    key = os.environ.get("VISUAL_CROSSING_KEY")
    if not key:
        return [{"provider": "visual_crossing", "locationId": "all", "credential": "missing VISUAL_CROSSING_KEY", "retrievedAt": iso(now)}]
    out = []; d1, d2 = f"{now:%Y-%m-%d}", f"{now + timedelta(days=2):%Y-%m-%d}"
    for p, (la, lo) in POINTS.items():
        for ds in [None] + (VC_DATASETS if now.hour % 6 == 0 else []):     # per-model datasets 4x/day to bound record cost
            url = visual_crossing_request(la, lo, d1, d2, key, dataset=ds); product = f"VC blend" if ds is None else f"VC dataset {ds}"
            try:
                body = _get(url); _store_raw(now, "visual-crossing", ds or "blend", p, url, body)
                rows = {r["validTime"]: r for r in visual_crossing_normalize(json.loads(body), p, now, product)}
                out += [rows[iso(vt)] for vt in _valid_hours(now) if iso(vt) in rows]
            except Exception as e:
                out.append(err("visual_crossing", p, e, now))
    return out


# ── Meteomatics US1k (credential-gated; native vs calibrated kept separate) ─────────────────

MM_PARAMS = "wind_speed_10m:ms,wind_dir_10m:d,wind_gusts_10m_1h:ms,wind_speed_u_10m:ms,wind_speed_v_10m:ms"


def meteomatics_request(t1, t2, points, calibrated=False, source="mm-us1k"):
    loc = "+".join(f"{la:.4f},{lo:.4f}" for la, lo in points)
    return (f"https://api.meteomatics.com/{iso(t1)}--{iso(t2)}:PT1H/{MM_PARAMS}/{loc}/json?source={source}"
            f"&calibrated={'true' if calibrated else 'false'}")


def meteomatics_init(auth, valid, source="mm-us1k"):
    """Model run actually used (meta request). Verify on the first credentialed call; None if unavailable."""
    try:
        js = json.loads(_get(f"https://api.meteomatics.com/get_init_date?model={source}&valid_date={iso(valid)}&parameters=wind_speed_10m:ms", auth=auth))
        return js
    except Exception as e:
        return {"error": repr(e)[:120]}


def meteomatics_normalize(js, retrieved, product, init_meta):
    cols = {}
    for d in js.get("data", []):
        for ci, c in enumerate(d["coordinates"]):
            for x in c["dates"]:
                cols.setdefault((ci, x["date"]), {})[d["parameter"]] = x["value"]
    names = list(POINTS); out = []
    issue = None
    try:
        issue = datetime.fromisoformat(str(init_meta.get("data", [{}])[0].get("coordinates", [{}])[0].get("dates", [{}])[0].get("value")).replace("Z", "+00:00"))
    except Exception:
        issue = None
    for (ci, ds), v in cols.items():
        vt = datetime.fromisoformat(ds.replace("Z", "+00:00"))
        nz = lambda k: None if v.get(k) in (None, -666, -999) else v.get(k)
        out.append(sample("meteomatics_us1k", product, "forecast", names[ci], issue, retrieved, vt, nz("wind_speed_10m:ms"), nz("wind_dir_10m:d"),
                          nz("wind_gusts_10m_1h:ms"), {"initMeta": init_meta, "gustDefinition": "max 1 h gust"}, u=nz("wind_speed_u_10m:ms"), v=nz("wind_speed_v_10m:ms")))
    return out


def meteomatics(now):
    user, pw = os.environ.get("METEOMATICS_USER"), os.environ.get("METEOMATICS_PASSWORD")
    if not (user and pw):
        return [{"provider": "meteomatics_us1k", "locationId": "all", "credential": "missing METEOMATICS_USER/METEOMATICS_PASSWORD", "retrievedAt": iso(now)}]
    out = []; vh = _valid_hours(now); init = meteomatics_init((user, pw), vh[0])
    for cal in (False, True):
        product = "US1k calibrated (observation-assisted 0–6 h)" if cal else "US1k native"
        url = meteomatics_request(vh[0], vh[-1], list(POINTS.values()), calibrated=cal)
        try:
            body = _get(url, auth=(user, pw)); _store_raw(now, "meteomatics", "us1k_calibrated" if cal else "us1k_native", "all", url, body)
            rows = {(r["locationId"], r["validTime"]): r for r in meteomatics_normalize(json.loads(body), now, product, init)}
            out += [rows[(p, iso(vt))] for p in POINTS for vt in vh if (p, iso(vt)) in rows]
        except Exception as e:
            out.append(err("meteomatics_us1k", "all", e, now))
    return out


# ── MADIS observations (public CGI, QC flags kept) ──────────────────────────────────────────

MADIS_CGI = ("https://madis-data.ncep.noaa.gov/madisPublic1/cgi-bin/madisXmlPublicDir?rdr=&time=0&minbck=-59&minfwd=0&recwin=4&dfltrsel=2"
             "&state={st}&stanam=&stasel=0&pvdrsel=0&varsel=2&qctype=0&qcsel=1&xml=1&csvmiss=0&nvars=DD&nvars=FF&nvars=FFGUST")
NOMINAL_HEIGHT_M = {"PRIMARY": 10.0, "RAWS": 6.1, "CRN": 1.5}
_INV = None


def _inventory():
    global _INV
    if _INV is None:
        p = os.path.join(ROOT, "observations", "madis", "inventory.json")
        _INV = {r["station"].removeprefix("K") if len(r["station"]) == 4 and r["station"][0] == "K" else r["station"]: r
                for r in json.load(open(p))["stations"]} if os.path.exists(p) else {}
    return _INV


def madis(now):
    inv = _inventory(); recs = {}; out = []
    for st in ("AL", "TN", "MS"):
        url = MADIS_CGI.format(st=st)
        try:
            body = _get(url, timeout=120); _store_raw(now, "madis", f"surface_{st}", "all", url, body)
            for m in re.finditer(r"<record ([^>]*)/>", body.decode("latin-1")):
                a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
                sid = a["shef_id"]; key = sid.removeprefix("K") if len(sid) == 4 and sid[0] == "K" else sid
                iv = inv.get(key)
                if not iv or iv["class"] == "REJECT":
                    continue
                r = recs.setdefault((sid, a["ObTime"]), {"station": sid, "network": iv["network"], "class": iv["class"], "lat": float(a["lat"]),
                                                         "lon": float(a["lon"]), "elevationM": float(a["elev"]), "obsTime": a["ObTime"] + ":00Z",
                                                         "retrievedAt": iso(now), "madisProvider": a.get("provider"),
                                                         "sensorHeightM": NOMINAL_HEIGHT_M.get(iv["class"] if iv["class"] == "PRIMARY" else iv["network"].split("/")[-1]),
                                                         "sensorHeightBasis": "network nominal (not station metadata)" if iv["class"] == "PRIMARY" or iv["network"].split("/")[-1] in NOMINAL_HEIGHT_M else None,
                                                         "speedMS": None, "directionFromDeg": None, "gustMS": None, "qc": {}})
                v = float(a["data_value"]); var = a["var"].split("-")[-1]
                field = {"FF": "speedMS", "DD": "directionFromDeg", "FFGUST": "gustMS"}.get(var)
                if field:
                    r[field] = None if v <= -9999 else v
                    r["qc"][field] = {"QCD": a.get("QCD"), "QCA": a.get("QCA"), "QCR": a.get("QCR")}
        except Exception as e:
            out.append(err("madis", st, e, now))
    for r in recs.values():   # QC: descriptor X/Q/B -> value withheld (kept in raw), never silently used
        for f, q in r["qc"].items():
            r[f + "QcPass"] = q.get("QCD") in ("C", "S", "V", "G")
    d = os.path.join(ROOT, "observations"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{now:%Y%m%d}.jsonl"), "a") as f:
        for r in recs.values():
            f.write(json.dumps(r) + "\n")
    return out + [{"provider": "madis", "locationId": "all", "observations": len(recs), "retrievedAt": iso(now)}]


ADAPTERS = {"noaa_nbm": noaa_nbm, "rtma": rtma, "open_meteo": open_meteo, "visual_crossing": visual_crossing,
            "meteomatics_us1k": meteomatics, "madis": madis}


def collect(now=None):
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    rows = []
    for name, fn in ADAPTERS.items():
        try:
            rows += fn(now)
        except Exception as e:
            rows.append(err(name, "all", e, now))
    d = os.path.join(ROOT, "normalized"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{now:%Y%m%d}.jsonl"), "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    errs = [r for r in rows if "error" in r]; n = sum("speedMS" in r for r in rows)
    print(f"{iso(now)} collected {n} samples, {len(errs)} errors", flush=True)
    for e in errs[:5]:
        print("  ERROR", e["provider"], e["locationId"], e["error"], flush=True)
    return rows


# ── status / parity ─────────────────────────────────────────────────────────────────────────

def _rows():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "normalized", "*.jsonl"))):
        for l in open(p):
            if l.strip():
                r = json.loads(l)
                if "point" in r and "locationId" not in r:   # Stage 3D.1 v1 rows
                    r["locationId"] = r["point"]; r["directionFromDeg"] = r.get("dirFromDeg")
                    r["provider"] = {"openmeteo_ncep_nbm_conus": "open_meteo_nbm", "openmeteo_best_match": "open_meteo_best"}.get(r["provider"], r["provider"] + " (3D.1 retired)")
                out.append(r)
    return out


def status():
    rows = _rows(); by = {}
    for r in rows:
        by.setdefault(r["provider"], []).append(r)
    print(f"PROVIDER BAKE-OFF  ({ROOT})")
    print(f"{'provider':<34}{'days':>5}{'samples':>9}{'miss%':>7}{'errors':>7}  {'latest':<21} skill")
    for src, rs in sorted(by.items()):
        ok = [r for r in rs if "speedMS" in r]; errs = sum("error" in r for r in rs); cred = [r for r in rs if "credential" in r]
        miss = sum(r["speedMS"] is None for r in ok) / max(len(ok), 1)
        days = len({r["retrievedAt"][:10] for r in rs}); latest = max(r["retrievedAt"] for r in rs)
        sealed_n = sum(1 for r in ok if sealed(pt(r["validTime"])))
        note = f"CREDENTIAL BOUNDARY: {cred[-1]['credential']}" if cred and not ok else \
               (f"SEALED ({sealed_n} rows in H2; scored after 2027-01-01)" if sealed_n == len(ok) and ok else f"{len(ok) - sealed_n} scorable rows")
        print(f"{src:<34}{days:>5}{len(ok):>9}{100 * miss:>6.1f}%{errs:>7}  {latest:<21} {note}")
    obs = sorted(glob.glob(os.path.join(ROOT, "observations", "*.jsonl")))
    if obs:
        n = sum(1 for p in obs for _ in open(p)); print(f"{'madis observations':<34}{len(obs):>5}{n:>9}")


def parity():
    """Open-Meteo NBM vs direct NOAA NBM at the same point/valid from the same collection pass. Not a skill score."""
    rows = _rows(); nbm = {}; om = []
    for r in rows:
        if r.get("speedMS") is None:
            continue
        if r["provider"] == "noaa_nbm":
            nbm[(r["retrievedAt"], r["locationId"], r["validTime"])] = r
        elif r["provider"] == "open_meteo_nbm":
            om.append(r)
    d = [(o, nbm[k]) for o in om if (k := (o["retrievedAt"], o["locationId"], o["validTime"])) in nbm]
    if not d:
        print("no matched rows yet"); return
    sd = np.array([a["speedMS"] - b["speedMS"] for a, b in d])
    print(f"matched {len(d)}  speed meanDiff {sd.mean():+.3f}  MAD {np.abs(sd).mean():.3f}  within0.2 {(np.abs(sd) <= 0.2).mean():.3f}")


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
        try:   # RRFS/REFS prospective archive (research only); a no-op until NOAA publishes operational cycles
            from sector_wind import rrfs
            for s in rrfs.collect():
                if s["status"] != "not published":
                    print("  RRFS", s, flush=True)
        except Exception as e:
            print("rrfs failed", repr(e), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["collect", "status", "parity", "loop"]); a = ap.parse_args()
    {"collect": collect, "status": status, "parity": parity, "loop": loop}[a.cmd]()
