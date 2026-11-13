"""Water Clarity H1 shadow lane: each lake's own last-5-years seasonal Secchi median, side by side with production.

SHADOW ONLY. Nothing here is served to a customer, written to a database or uploaded. Owner approval: Sector_Ops #51,
2026-11-11 ~23:40Z, decision 1 ("promote the H1 rule to a shadow lane; serving to customers stays a separate approval").
Evidence: now-test CL-NOW-1 (Sector_Ops #51, 2026-11-11), where H1 met the frozen G0-2 bars on 379 unseen Southern lakes.

The rule (frozen in the H1 pre-registration, Sector_Ops #40, 2026-11-01):
  * For year Y and a season (warm = Apr..Oct, cool = Nov..Mar), the median of the lake's own public Secchi lake-days in Y-5..Y-1.
  * Too thin (< 5 lake-days or < 2 distinct years) -> widen one year back at a time, down to Y-10; still thin -> UNKNOWN.
  * No rain, flow or trend term. Bands: V0 < 1.5 ft, V1 1.5-<3, V2 3-<6, V3 >= 6 (G0-2).

Data: Water Quality Portal "Depth, Secchi disk depth" at lake/reservoir sites within --radius-mi of the lake's directory point.
A lake-day is the median of that day's retained values across stations. Censored ("bottom", ">") and Rejected rows are dropped.

usage: h1_shadow.py --lakes "Guntersville|AL,Lake Hartwell|SC" --out DIR [--cache DIR] [--production-dir DIR] [--sites-file JSON] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request

SCHEMA = "clarity-h1-shadow-v1"
RULE = "h1-own-last5y-seasonal-median"
EDGES = (1.5, 3.0, 6.0)
UNIT = {"ft": 1.0, "feet": 1.0, "m": 3.28084, "meters": 3.28084, "cm": 0.0328084, "in": 1 / 12, "mm": 0.00328084}
CENSORED = re.compile(r"bottom|greater|>|not detected|present above", re.I)
WQP = "https://www.waterqualitydata.us/data/Result/search"
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DIRECTORY = os.path.join(REPO, "Sources", "SectorEngine", "Support", "LakeDirectory.swift")


def band(ft: float) -> str:
    return "V" + str(sum(ft >= e for e in EDGES))


def season(month: int) -> str:
    return "warm" if 4 <= month <= 10 else "cool"


def directory(path: str = DIRECTORY) -> dict:
    out = {}
    for line in open(path):
        line = line.strip().rstrip(",")
        if line.startswith('{"name"'):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            out[f"{o['name']}|{o['state']}"] = o
    return out


def parse_rows(text: str) -> list[tuple[str, float]]:
    """(date, feet) for retained rows of a WQP Result CSV."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("CharacteristicName") != "Depth, Secchi disk depth":
            continue
        if "rejected" in (r.get("ResultStatusIdentifier") or "").lower():
            continue
        if CENSORED.search(r.get("ResultDetectionConditionText") or "") or CENSORED.search(r.get("MeasureQualifierCode") or ""):
            continue
        u = UNIT.get((r.get("ResultMeasure/MeasureUnitCode") or "").strip().lower())
        try:
            v = float(r.get("ResultMeasureValue") or "") * u if u else None
        except ValueError:
            v = None
        d = (r.get("ActivityStartDate") or "")[:10]
        if v is None or not (0 < v <= 60) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue
        out.append((d, v))
    return out


def lake_days(rows: list[tuple[str, float]]) -> dict[str, float]:
    by: dict[str, list[float]] = {}
    for d, v in rows:
        by.setdefault(d, []).append(v)
    return {d: statistics.median(v) for d, v in by.items()}


def h1(ld: dict[str, float], year: int, seas: str) -> dict:
    """The frozen H1 rule for one lake, year and season."""
    pts = [(int(d[:4]), v) for d, v in ld.items() if season(int(d[5:7])) == seas]
    for lo in range(year - 5, year - 11, -1):
        w = [(y, v) for y, v in pts if lo <= y <= year - 1]
        if len(w) >= 5 and len({y for y, _ in w}) >= 2:
            m = round(statistics.median(v for _, v in w), 2)
            return {"status": "ANSWER", "medianFt": m, "band": band(m), "lakeDays": len(w), "years": [lo, year - 1]}
    return {"status": "UNKNOWN", "reason": "fewer than 5 lake-days over 2 years in Y-10..Y-1"}


def fetch(lat: float, lon: float, radius_mi: float, start: str, timeout: int = 600, sites: list[str] | None = None) -> str:
    if sites:   # the lake's own stations (a runtime --sites-file built from the lake polygon); radius is the fallback
        q = {"siteid": ";".join(sites), "characteristicName": "Depth, Secchi disk depth", "startDateLo": start, "mimeType": "csv"}
    else:
        q = {"lat": f"{lat:.4f}", "long": f"{lon:.4f}", "within": str(radius_mi), "siteType": "Lake, Reservoir, Impoundment",
             "characteristicName": "Depth, Secchi disk depth", "startDateLo": start, "mimeType": "csv"}
    req = urllib.request.Request(WQP + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "SectorPulse/1.0 (clarity-h1-shadow)"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # network: retry, then surface
            last = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"WQP fetch failed: {last}")


def production_bands(prod_dir: str | None) -> tuple[dict, str | None]:
    """({lakeId: (clarityFt, band, generatedAt)}, artifactId) from the newest WATER-CLARITY artifact under prod_dir (read-only).
    Only artifacts whose lineage.brainId is water-clarity count; gzip files and other Brains' artifacts are skipped."""
    if not prod_dir:
        return {}, None
    best = None
    for f in glob.glob(os.path.join(prod_dir, "**", "artifact.json*"), recursive=True):
        if f.endswith(".gz") or not os.path.isfile(f):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (ValueError, OSError):
            continue
        lin = doc.get("lineage") if isinstance(doc, dict) else None
        if not isinstance(lin, dict) or lin.get("brainId") != "water-clarity":
            continue
        key = (lin.get("generatedAt") or "", os.path.getmtime(f))
        if best is None or key > best[0]:
            best = (key, doc, lin.get("artifactId"))
    if best is None:
        return {}, None
    out = {}

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("clarityFt"), (int, float)) and isinstance(o.get("lakeId"), str):
                out[o["lakeId"]] = (o["clarityFt"], band(o["clarityFt"]), (o.get("provenance") or {}).get("generatedAt"))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(best[1])
    return out, best[2]


def run(lakes: list[str], out: str, cache: str | None, prod_dir: str | None, today: dt.date, radius_mi: float,
        fetcher=fetch, sites: dict | None = None) -> dict:
    d = directory()
    prod, prod_artifact = production_bands(prod_dir)
    year, seas = today.year, season(today.month)
    res = []
    for lid in lakes:
        row = {"lakeId": lid}
        o = d.get(lid)
        if not o:
            row.update({"status": "UNKNOWN", "reason": "not in the Engine lake directory"}); res.append(row); continue
        start = f"01-01-{year - 10}"
        ls = (sites or {}).get(lid)
        sel = "sites-" + hashlib.sha256(";".join(sorted(ls)).encode()).hexdigest()[:12] if ls else f"r{radius_mi:g}mi"
        cp = os.path.join(cache, re.sub(r"[^A-Za-z0-9]+", "_", lid) + f"_{sel}.csv") if cache else None
        text = None
        if cp and os.path.exists(cp) and (time.time() - os.path.getmtime(cp)) < 7 * 86400:
            text = open(cp).read()
        if text is None:
            try:
                text = fetcher(o["lat"], o["lon"], radius_mi, start, sites=ls) if ls else fetcher(o["lat"], o["lon"], radius_mi, start)
            except RuntimeError as e:
                row.update({"status": "UNKNOWN", "reason": str(e)[:200]}); res.append(row); continue
            if cp:
                os.makedirs(cache, exist_ok=True)
                with open(cp + ".part", "w") as fh:
                    fh.write(text)
                os.replace(cp + ".part", cp)
        ld = lake_days(parse_rows(text))
        row.update({"lakeDaysOnRecord": len(ld), "seasonNow": seas, "stationSelection": "sites-file" if (sites or {}).get(lid) else f"within {radius_mi} mi",
                    "h1": {"warm": h1(ld, year, "warm"), "cool": h1(ld, year, "cool")}})
        now = row["h1"][seas]
        row["status"] = now["status"]
        p = prod.get(lid)
        if p:
            row["production"] = {"clarityFt": p[0], "band": p[1], "generatedAt": p[2]}
            if now["status"] == "ANSWER":
                bi = lambda b: int(b[1])
                row["comparison"] = {"sameBand": now["band"] == p[1], "h1MinusProductionBands": bi(now["band"]) - bi(p[1])}
        res.append(row)
    answered = [r for r in res if r.get("status") == "ANSWER"]
    doc = {"schema": SCHEMA, "rule": RULE, "lane": "SHADOW", "customerVisible": False, "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "asOf": today.isoformat(), "season": seas, "radiusMi": radius_mi, "productionArtifact": prod_artifact, "bands": {"V0": "<1.5 ft", "V1": "1.5-<3", "V2": "3-<6", "V3": ">=6"},
           "summary": {"lakes": len(res), "answered": len(answered),
                       "comparedWithProduction": sum(1 for r in res if "comparison" in r),
                       "sameBandAsProduction": sum(1 for r in res if (r.get("comparison") or {}).get("sameBand"))},
           "lakes": res}
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "h1-shadow.json"), "w") as f:
        json.dump(doc, f, indent=1)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lakes", required=True, help="comma-separated lake ids, e.g. 'Guntersville|AL,Lake Hartwell|SC'")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache")
    ap.add_argument("--production-dir", help="read-only: newest water-clarity artifact under this directory is compared")
    ap.add_argument("--radius-mi", type=float, default=5.0)
    ap.add_argument("--sites-file", help="optional JSON {lakeId: [WQP site ids]} for the lake's own stations (runtime input, never committed)")
    ap.add_argument("--today", help="YYYY-MM-DD (tests / replays)")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()
    sites = json.load(open(a.sites_file)) if a.sites_file else None
    doc = run([x.strip() for x in a.lakes.split(",") if x.strip()], a.out, a.cache, a.production_dir, today, a.radius_mi, sites=sites)
    print(json.dumps(doc["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
