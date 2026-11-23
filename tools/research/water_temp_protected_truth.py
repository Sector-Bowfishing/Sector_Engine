#!/usr/bin/env python3
"""Water Temp Level-4 protected truth: read-only runner for protocol PT-L4-2026-11-23 (gap WATER-VAL-001).

The protocol (brains/water-temperature/research/protected-truth/PT-L4-2026-11-23.protocol.json) was pre-registered and
hashed before any truth value was fetched. This runner only reads public sources and writes local files in --out. It never
writes Firebase, never changes a score, binding or schedule, and never opens a truth value unless step A showed sufficiency
and an owner request for step B is given.

Step A (metadata only, no result values):
    verify          check the protocol's sha256 against the committed sidecar
    fetch-metadata  WQP Station + Activity metadata per lake box (identifiers, coordinates, dates, depths)
    fetch-forcing   Open-Meteo archive daily forcing at each lake point (model input, not truth)
    stations        draft station classification from metadata (a reviewer may reclassify UNCLASSIFIED rows)
    census          count qualifying casts per lake from activity metadata; INSUFFICIENT_TRUTH stops here
Step B (opens truth values; refused unless census is sufficient and --owner-request is given):
    fetch-results   WQP Result rows (Temperature, water) per lake box
    compare         pair each counted cast with production M0 and apply the pre-registered pass mark
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROTOCOL = os.path.join(REPO, "brains", "water-temperature", "research", "protected-truth", "PT-L4-2026-11-23.protocol.json")
LABELS = ["INTERNAL_EXPERIMENTAL", "NOT_FOR_CUSTOMERS"]
ALLOWED_HOSTS = {"www.waterqualitydata.us", "archive-api.open-meteo.com"}
WQP = "https://www.waterqualitydata.us/data/{kind}/search"
OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
CHARACTERISTIC = "Temperature, water"
SITE_TYPE = "Lake, Reservoir, Impoundment"

EMBAYMENT_WORDS = ("creek", "branch", "embayment", " bay", "slough", "spring", " run", "cove", "hollow")
TAILWATER_WORDS = ("tailwater", "below dam", "blw dam", " tw ", "release", "outflow", "tailrace", "spillway", "powerhouse", "below ")
MAIN_WORDS = ("tennessee river", "tenn river", "tennessee r", "forebay", "main channel", "mainstem", "main stem", "near dam", "above dam")
TRM_RE = re.compile(r"\b(?:TRM|TENN(?:ESSEE)?\s*R(?:IVER)?\s*(?:MI(?:LE)?)?|RIVER\s*MILE|RM)\s*\.?\s*(\d{2,3}(?:\.\d+)?)", re.I)


# ----------------------------------------------------------------------------------------------------------------- protocol
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_protocol(path: str = PROTOCOL) -> tuple[dict, str]:
    """Load the protocol and refuse it unless its sha256 equals the committed sidecar (pre-registration is immutable)."""
    digest = sha256_file(path)
    side = path + ".sha256"
    if not os.path.exists(side):
        raise SystemExit(f"REFUSED: no committed hash sidecar {os.path.basename(side)}")
    expected = open(side, encoding="utf-8").read().split()[0]
    if digest != expected:
        raise SystemExit(f"REFUSED: protocol sha256 {digest} != pre-registered {expected}")
    return json.load(open(path, encoding="utf-8")), digest


def per_lake_min(p: dict) -> int:
    return int(p["governingRule"]["knownFromRepository"]["perLakeMinimum"])


def total_min(p: dict) -> int:
    return int(p["governingRule"]["knownFromRepository"]["totalMinimum"])


# ----------------------------------------------------------------------------------------------------------------- fetching
def _get(url: str, params: dict, dest: str, prov: list) -> str:
    host = urllib.parse.urlparse(url).hostname
    if host not in ALLOWED_HOSTS:
        raise SystemExit(f"REFUSED: host {host} is not allowlisted")
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "sector-research-readonly/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        body = r.read()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(body)
    prov.append({"url": full, "path": os.path.basename(dest), "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                 "retrievedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    return dest


def lake_slug(lake_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id).strip("_")


def wqp_params(lake: dict, start: str) -> dict:
    b = lake["bbox"]
    s = dt.date.fromisoformat(start)
    return {"bBox": ",".join(str(x) for x in b), "siteType": SITE_TYPE, "characteristicName": CHARACTERISTIC,
            "startDateLo": s.strftime("%m-%d-%Y"), "mimeType": "csv", "zip": "no"}


def write_provenance(out: str, name: str, prov: list) -> None:
    with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
        json.dump({"labels": LABELS, "items": prov}, fh, indent=1)


def cmd_fetch_metadata(p: dict, out: str) -> dict:
    prov = []
    start = p["independence"]["window"]["from"]
    for lake in p["lakes"]:
        for kind in ("Station", "Activity"):
            _get(WQP.format(kind=kind), wqp_params(lake, start), os.path.join(out, f"{lake_slug(lake['lakeId'])}.{kind.lower()}.csv"), prov)
    write_provenance(out, "metadata.provenance.json", prov)
    return {"files": len(prov)}


def cmd_fetch_forcing(p: dict, out: str, start: str, end: str) -> dict:
    prov = []
    fstart = (dt.date.fromisoformat(start) - dt.timedelta(days=46)).isoformat()
    for lake in p["lakes"]:
        lat, lon = lake["point"]
        _get(OPEN_METEO, {"latitude": lat, "longitude": lon, "start_date": fstart, "end_date": end, "timezone": "auto",
                          "daily": "temperature_2m_mean,shortwave_radiation_sum,wind_speed_10m_mean,relative_humidity_2m_mean"},
             os.path.join(out, f"{lake_slug(lake['lakeId'])}.forcing.json"), prov)
    write_provenance(out, "forcing.provenance.json", prov)
    return {"files": len(prov)}


# ----------------------------------------------------------------------------------------------------------------- stations
def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def in_bbox(lat: float, lon: float, b: list) -> bool:
    return b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def river_mile(name: str):
    m = TRM_RE.search(name or "")
    return float(m.group(1)) if m else None


def classify_station(p: dict, name: str, lat, lon) -> tuple[str, str | None, str]:
    """(class, lakeId or None, reason) from station metadata only (protocol stationRule)."""
    if lat is None or lon is None:
        return "UNCLASSIFIED", None, "no coordinates"
    boxes = [l for l in p["lakes"] if in_bbox(lat, lon, l["bbox"])]
    if not boxes:
        return "OUTSIDE", None, "outside every lake box"
    n = f" {(name or '').lower()} "
    if len(boxes) > 1 and any(w in n for w in TAILWATER_WORDS):
        return "TAILWATER", None, "tailwater keyword in name (station inside two lake boxes)"
    trm = river_mile(name)
    lake = None
    if trm is not None:
        for l in p["lakes"]:
            r = l["tennesseeRiverMile"]
            if r["dam"] <= trm <= r["upstreamDam"]:
                lake = l
        if lake is None:
            return "TAILWATER", None, f"river mile {trm} is below a dam of the four lakes or outside them"
    elif len(boxes) > 1:
        return "AMBIGUOUS", None, "inside two lake boxes with no river mile"
    else:
        lake = boxes[0]
    lid = lake["lakeId"]
    if any(w in n for w in TAILWATER_WORDS):
        return "TAILWATER", lid, "tailwater keyword in name"
    if trm is not None:
        if trm > lake["tennesseeRiverMile"]["upstreamDam"] - 2.0:
            return "TAILWATER", lid, f"river mile {trm} within 2.0 mi below the upstream dam"
        if any(w in n for w in EMBAYMENT_WORDS):
            return "EMBAYMENT", lid, "embayment keyword in name"
        return "MAIN_BODY", lid, f"Tennessee River mile {trm}"
    if any(w in n for w in EMBAYMENT_WORDS):
        return "EMBAYMENT", lid, "embayment keyword in name"
    other_river = re.search(r"\b([a-z]+) river\b", n)
    if other_river and other_river.group(1) not in ("tennessee", "tenn"):
        return "EMBAYMENT", lid, f"names the {other_river.group(1).title()} River"
    if any(w in n for w in MAIN_WORDS):
        return "MAIN_BODY", lid, "main-stem or forebay keyword in name"
    return "UNCLASSIFIED", lid, "no main-stem, embayment or tailwater evidence in metadata"


def read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        return list(csv.DictReader(fh))


STATION_FIELDS = ["MonitoringLocationIdentifier", "OrganizationIdentifier", "MonitoringLocationName", "LatitudeMeasure",
                  "LongitudeMeasure", "lakeId", "class", "reason", "reviewNote"]


def cmd_stations(p: dict, metadata: str, out_csv: str) -> dict:
    seen, rows = set(), []
    for lake in p["lakes"]:
        path = os.path.join(metadata, f"{lake_slug(lake['lakeId'])}.station.csv")
        if not os.path.exists(path):
            continue
        for r in read_csv(path):
            sid = r.get("MonitoringLocationIdentifier")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            lat, lon = _f(r.get("LatitudeMeasure")), _f(r.get("LongitudeMeasure"))
            cls, lid, why = classify_station(p, r.get("MonitoringLocationName", ""), lat, lon)
            rows.append({"MonitoringLocationIdentifier": sid, "OrganizationIdentifier": r.get("OrganizationIdentifier", ""),
                         "MonitoringLocationName": r.get("MonitoringLocationName", ""), "LatitudeMeasure": lat, "LongitudeMeasure": lon,
                         "lakeId": lid or "", "class": cls, "reason": why, "reviewNote": ""})
    rows.sort(key=lambda r: (r["lakeId"], r["class"], r["MonitoringLocationIdentifier"]))
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=STATION_FIELDS)
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {"stations": len(rows), "byClass": counts}


def load_stations(path: str) -> dict:
    """Reviewed station file -> {id: row}. A changed class must carry a review note."""
    out = {}
    for r in read_csv(path):
        out[r["MonitoringLocationIdentifier"]] = r
    return out


# ----------------------------------------------------------------------------------------------------------------- casts
def depth_m(value, unit):
    v = _f(value)
    if v is None:
        return None
    u = (unit or "").strip().lower()
    if u in ("ft", "feet", "foot"):
        return v * 0.3048
    if u in ("m", "meters", "meter", "metres", ""):
        return v
    if u in ("cm",):
        return v / 100.0
    return None


def to_c(value, unit):
    v = _f(value)
    if v is None:
        return None
    u = (unit or "").lower().replace(" ", "")
    if u in ("degf", "deg.f", "f"):
        return (v - 32.0) / 1.8
    if u in ("degc", "deg.c", "c"):
        return v
    return None


def _date_in_window(d: str, start: str, cutoff: str) -> bool:
    return bool(d) and start <= d <= cutoff


def _dedupe(casts: dict, stations: dict) -> dict:
    """Same lake and date, station coordinates within 0.002 deg: one cast, keep the one with more readings."""
    by = {}
    for key, c in casts.items():
        by.setdefault((c["lakeId"], c["date"]), []).append((key, c))
    keep = {}
    for group in by.values():
        group.sort(key=lambda kc: (-kc[1]["readings"], kc[0]))
        chosen = []
        for key, c in group:
            s = stations[c["station"]]
            lat, lon = _f(s["LatitudeMeasure"]), _f(s["LongitudeMeasure"])
            dup = False
            for _, k in chosen:
                t = stations[k["station"]]
                if abs(lat - _f(t["LatitudeMeasure"])) <= 0.002 and abs(lon - _f(t["LongitudeMeasure"])) <= 0.002:
                    dup = True
                    break
            if not dup:
                chosen.append((key, c))
        keep.update(dict(chosen))
    return keep


def census_from_activities(p: dict, activities: list[dict], stations: dict, cutoff: str) -> dict:
    start = p["independence"]["window"]["from"]
    casts, depth_unknown, excluded = {}, {}, {"notMainBody": 0, "outsideWindow": 0, "tooDeep": 0}
    for a in activities:
        sid, d = a.get("MonitoringLocationIdentifier"), a.get("ActivityStartDate", "")
        s = stations.get(sid)
        if not s or s.get("class") != "MAIN_BODY" or not s.get("lakeId"):
            excluded["notMainBody"] += 1
            continue
        if not _date_in_window(d, start, cutoff):
            excluded["outsideWindow"] += 1
            continue
        key = (s["lakeId"], sid, d)
        dep = depth_m(a.get("ActivityDepthHeightMeasure/MeasureValue"), a.get("ActivityDepthHeightMeasure/MeasureUnitCode"))
        if dep is None:
            depth_unknown[key] = True
            continue
        c = casts.setdefault(key, {"lakeId": s["lakeId"], "station": sid, "date": d, "readings": 0, "shallowest": dep})
        c["readings"] += 1
        c["shallowest"] = min(c["shallowest"], dep)
    qualifying = {k: c for k, c in casts.items() if c["shallowest"] <= 1.5}
    excluded["tooDeep"] = len(casts) - len(qualifying)
    qualifying = _dedupe(qualifying, stations)
    lakes = {}
    for l in p["lakes"]:
        lid = l["lakeId"]
        n = sum(1 for c in qualifying.values() if c["lakeId"] == lid)
        pot = sum(1 for k in depth_unknown if k[0] == lid and k not in casts)
        lakes[lid] = {"qualifyingCasts": n, "depthOnlyOnResults": pot, "needed": per_lake_min(p), "sufficient": n >= per_lake_min(p)}
    total = sum(v["qualifyingCasts"] for v in lakes.values())
    ok = all(v["sufficient"] for v in lakes.values()) and total >= total_min(p)
    return {"lakes": lakes, "total": total, "totalNeeded": total_min(p), "excluded": excluded,
            "outcome": "SUFFICIENT_FOR_STEP_B" if ok else "INSUFFICIENT_TRUTH",
            "castKeys": sorted("|".join(k) for k in qualifying)}


def cmd_census(p: dict, digest: str, metadata: str, stations_path: str, cutoff: str, out: str) -> dict:
    stations = load_stations(stations_path)
    acts = []
    for lake in p["lakes"]:
        path = os.path.join(metadata, f"{lake_slug(lake['lakeId'])}.activity.csv")
        if os.path.exists(path):
            acts += read_csv(path)
    res = census_from_activities(p, acts, stations, cutoff)
    rec = {"labels": LABELS, "protocolId": p["protocolId"], "protocolSha256": digest, "step": "A_census",
           "valuesOpened": False, "cutoff": cutoff, "stationFileSha256": sha256_file(stations_path),
           "authoritativeScoresUnchanged": True, **res}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec


# ----------------------------------------------------------------------------------------------------------------- step B
def require_step_b(census: dict, digest: str, stations_path: str, owner_request: str | None) -> None:
    if not owner_request or not owner_request.startswith("Owner request (Michael, "):
        raise SystemExit("REFUSED: step B opens protected truth values and needs --owner-request 'Owner request (Michael, ...)'")
    if census.get("protocolSha256") != digest:
        raise SystemExit("REFUSED: the census was made under a different protocol hash")
    if census.get("outcome") != "SUFFICIENT_FOR_STEP_B":
        raise SystemExit("REFUSED: census outcome is not SUFFICIENT_FOR_STEP_B; protected values stay closed")
    if sha256_file(stations_path) != census.get("stationFileSha256"):
        raise SystemExit("REFUSED: the station file changed after the census")


def cmd_fetch_results(p: dict, digest: str, census: dict, stations_path: str, owner_request: str, out: str) -> dict:
    require_step_b(census, digest, stations_path, owner_request)
    prov = []
    for lake in p["lakes"]:
        _get(WQP.format(kind="Result"), wqp_params(lake, p["independence"]["window"]["from"]),
             os.path.join(out, f"{lake_slug(lake['lakeId'])}.result.csv"), prov)
    write_provenance(out, "results.provenance.json", prov)
    return {"files": len(prov)}


def surface_values(results: list[dict], counted: set) -> dict:
    """{castKey: surface deg C} for counted casts (protocol truthUnit.surfaceValue and unitsAndQc)."""
    readings = {}
    for r in results:
        if (r.get("CharacteristicName") or "").strip() != CHARACTERISTIC:
            continue
        if (r.get("ResultStatusIdentifier") or "").strip().lower() == "rejected":
            continue
        sid, d = r.get("MonitoringLocationIdentifier"), r.get("ActivityStartDate", "")
        match = [k for k in counted if k[1] == sid and k[2] == d]
        if not match:
            continue
        t = to_c(r.get("ResultMeasureValue"), r.get("ResultMeasure/MeasureUnitCode"))
        if t is None or not (-0.5 <= t <= 40.0):
            continue
        dep = depth_m(r.get("ResultDepthHeightMeasure/MeasureValue"), r.get("ResultDepthHeightMeasure/MeasureUnitCode"))
        if dep is None:
            dep = depth_m(r.get("ActivityDepthHeightMeasure/MeasureValue"), r.get("ActivityDepthHeightMeasure/MeasureUnitCode"))
        if dep is None:
            continue
        readings.setdefault(match[0], []).append((dep, t))
    out = {}
    for k, rs in readings.items():
        top = [t for dpt, t in rs if dpt <= 1.0]
        if top:
            out[k] = sum(top) / len(top)
            continue
        shallow = sorted((dpt, t) for dpt, t in rs if dpt <= 1.5)
        if shallow:
            out[k] = shallow[0][1]
    return out


def _season(date: str) -> str:
    m = int(date[5:7])
    return {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA"}.get(m, "SON")


def lake_metrics(pairs: list[tuple[str, float, float]]) -> dict:
    errs = [m - t for _, m, t in pairs]
    n = len(errs)
    if not n:
        return {"n": 0}
    mse = sum(e * e for e in errs) / n
    out = {"n": n, "rmseC": round(math.sqrt(mse), 4), "mseC2": mse, "biasC": round(sum(errs) / n, 4),
           "maeC": round(sum(abs(e) for e in errs) / n, 4), "shareAbsErrorOver2.78C": round(sum(abs(e) > 2.78 for e in errs) / n, 4)}
    seasons = {}
    for d, m, t in pairs:
        seasons.setdefault(_season(d), []).append(m - t)
    out["seasonRmseC"] = {s: round(math.sqrt(sum(e * e for e in v) / len(v)), 4) for s, v in sorted(seasons.items()) if len(v) >= 5}
    return out


def verdict(p: dict, per_lake: dict) -> dict:
    pm = p["passMark"]
    paired_ok = all(v["n"] >= per_lake_min(p) for v in per_lake.values()) and sum(v["n"] for v in per_lake.values()) >= total_min(p)
    if not paired_ok:
        return {"outcome": "INSUFFICIENT_PAIRED", "pooledEqualLakeRmseC": None}
    pooled = math.sqrt(sum(v["mseC2"] for v in per_lake.values()) / len(per_lake))
    lake_ok = {k: v["rmseC"] <= pm["perLakeRmseC"]["value"] for k, v in per_lake.items()}
    ok = pooled <= pm["pooledEqualLakeRmseC"]["value"] and all(lake_ok.values())
    return {"outcome": "PASS" if ok else "FAIL", "pooledEqualLakeRmseC": round(pooled, 4), "perLakePass": lake_ok}


def m0_functions():
    sys.path.insert(0, HERE)
    import discovery  # noqa: E402  (the single canonical research re-implementation of production M0)
    import inspect
    src = inspect.getsource(discovery.m0_daily) + inspect.getsource(discovery.m0_for_date)
    return discovery.m0_daily, discovery.m0_for_date, hashlib.sha256(src.encode()).hexdigest()


def compare(p: dict, census: dict, results: list[dict], forcing: dict) -> dict:
    m0_daily, m0_for_date, m0_sha = m0_functions()
    counted = {_split_key(k) for k in census["castKeys"]}
    truth = surface_values(results, counted)
    per_lake, unpaired = {}, {}
    for l in p["lakes"]:
        lid = l["lakeId"]
        forc = m0_daily(forcing[lid]["daily"]) if lid in forcing else {}
        pairs = []
        for k, t in sorted(truth.items()):
            if k[0] != lid:
                continue
            m = m0_for_date(forc, k[2])
            if m is None:
                unpaired[lid] = unpaired.get(lid, 0) + 1
                continue
            pairs.append((k[2], m, t))
        per_lake[lid] = lake_metrics(pairs)
        per_lake[lid]["unpaired"] = unpaired.get(lid, 0)
        per_lake[lid]["noSurfaceValue"] = sum(1 for k in counted if k[0] == lid and k not in truth)
    v = verdict(p, per_lake)
    for x in per_lake.values():
        x.pop("mseC2", None)
    return {"labels": LABELS, "protocolId": p["protocolId"], "step": "B_compare", "valuesOpened": True,
            "model": p["model"]["id"], "m0ImplementationSha256": m0_sha, "perLake": per_lake, **v,
            "passMark": p["passMark"], "authoritativeScoresUnchanged": True,
            "scoreImpact": "none: the frozen water-temp block changes only by an owner decision in a separate change"}


def _split_key(k: str) -> tuple[str, str, str]:
    """castKeys are 'lakeId|station|date'; a lakeId itself contains one '|'."""
    parts = k.split("|")
    return "|".join(parts[:-2]), parts[-2], parts[-1]


def cmd_compare(p: dict, digest: str, census_path: str, stations_path: str, results_dir: str, forcing_dir: str,
                owner_request: str, out: str) -> dict:
    census = json.load(open(census_path, encoding="utf-8"))
    require_step_b(census, digest, stations_path, owner_request)
    results, forcing = [], {}
    for l in p["lakes"]:
        rp = os.path.join(results_dir, f"{lake_slug(l['lakeId'])}.result.csv")
        if os.path.exists(rp):
            results += read_csv(rp)
        fp = os.path.join(forcing_dir, f"{lake_slug(l['lakeId'])}.forcing.json")
        if os.path.exists(fp):
            forcing[l["lakeId"]] = json.load(open(fp, encoding="utf-8"))
    rec = compare(p, census, results, forcing)
    rec.update({"protocolSha256": digest, "censusSha256": sha256_file(census_path), "stationFileSha256": census["stationFileSha256"],
                "ownerRequest": owner_request})
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec


# ----------------------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", default=PROTOCOL)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    s = sub.add_parser("fetch-metadata"); s.add_argument("--out", required=True)
    s = sub.add_parser("fetch-forcing"); s.add_argument("--out", required=True); s.add_argument("--start", required=True); s.add_argument("--end", required=True)
    s = sub.add_parser("stations"); s.add_argument("--metadata", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("census"); s.add_argument("--metadata", required=True); s.add_argument("--stations", required=True)
    s.add_argument("--cutoff", default=(dt.date.today() - dt.timedelta(days=1)).isoformat()); s.add_argument("--out", required=True)
    s = sub.add_parser("fetch-results"); s.add_argument("--census", required=True); s.add_argument("--stations", required=True)
    s.add_argument("--owner-request"); s.add_argument("--out", required=True)
    s = sub.add_parser("compare"); s.add_argument("--census", required=True); s.add_argument("--stations", required=True)
    s.add_argument("--results", required=True); s.add_argument("--forcing", required=True); s.add_argument("--owner-request"); s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    p, digest = load_protocol(a.protocol)
    if a.cmd == "verify":
        res = {"protocolId": p["protocolId"], "sha256": digest, "status": "OK"}
    elif a.cmd == "fetch-metadata":
        res = cmd_fetch_metadata(p, a.out)
    elif a.cmd == "fetch-forcing":
        res = cmd_fetch_forcing(p, a.out, a.start, a.end)
    elif a.cmd == "stations":
        res = cmd_stations(p, a.metadata, a.out)
    elif a.cmd == "census":
        res = cmd_census(p, digest, a.metadata, a.stations, a.cutoff, a.out)
        res = {k: res[k] for k in ("outcome", "lakes", "total", "excluded", "stationFileSha256")}
    elif a.cmd == "fetch-results":
        res = cmd_fetch_results(p, digest, json.load(open(a.census, encoding="utf-8")), a.stations, a.owner_request, a.out)
    else:
        res = cmd_compare(p, digest, a.census, a.stations, a.results, a.forcing, a.owner_request, a.out)
        res = {k: res[k] for k in ("outcome", "pooledEqualLakeRmseC", "perLake")}
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
