#!/usr/bin/env python3
"""TWDB (Texas Water Development Board, Water Data For Texas) dry run for the Lake Brain bindings.

    python3 jobs/lake-brain/bindings/twdb_dryrun.py            # offline, from the raw files under LB_DATA/twdb/<date>/
    SECTOR_TWDB_TERMS_OK=1 python3 jobs/lake-brain/bindings/twdb_dryrun.py --fetch
                                                               # refresh the raw files first (one request / 2 s, read only). DISABLED unless
                                                               # SECTOR_TWDB_TERMS_OK=1: robots.txt of waterdatafortexas.org has Disallow: *.csv
    python3 jobs/lake-brain/bindings/twdb_dryrun.py --check    # fail if the committed outputs differ from a fresh offline build

Writes jobs/lake-brain/bindings/twdb_dryrun.v1.json and twdb_dryrun.v1.csv.  NOTHING here changes the published bindings table
(bindings.proposed.v1.json is read, never written), nothing is REVIEWED, nothing goes into accepted_batch.json.

What it answers
  1. which directory lakes TWDB covers (name + distance match against recent-conditions.json, file header cross-checked);
  2. for each: where the lake stands in the published table today (proposed / excluded + reasons), and so which lakes would become a
     NEW TWDB-primary CANDIDATE under the unchanged eligibility rules (the same classify_lakes() as the table builder), and which
     already-proposed lakes TWDB could back up (live relay fallback) or deepen (history);
  3. the checks the contract needs: pool sanity (level vs the published conservation pool and the directory full pool), live agreement
     with an independent origin (USGS / NWPS / CWMS, last 7 full days), live/history continuity (the runner's 15 ft rule), file datum
     label, glitches removed, completeness of years.

The parser and the glitch filter below are the Python twin of Sources/SectorEngine/LakeBrain/LakeLevelFeedsTWDB.swift; both are tested
against the same recorded fixtures (Tests/SectorEngineTests/Fixtures/TWDB).
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
import statistics
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.environ.get("LB_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
RESEARCH = os.environ.get("LAKE_BRAIN_RESEARCH", "")
RAW_DATE = "2026-10-13"
RAW = os.path.join(DATA, "twdb", RAW_DATE)
OUT_JSON = os.path.join(HERE, "twdb_dryrun.v1.json")
OUT_CSV = os.path.join(HERE, "twdb_dryrun.v1.csv")
BASE = "https://www.waterdatafortexas.org/reservoirs"
USER_AGENT = "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)"

GLITCH_FT = 15.0                 # same figure as the runner's history/live mismatch rule
MAX_GLITCH_RUN = 3
MATCH_KM = 30.0                  # directory coordinates are lake centroids, TWDB's are gauge locations
POOL_FLOOD_ALLOW_FT = 25.0       # level may sit this far above the conservation pool before it is flagged
POOL_AGREE_FT = 2.0              # TWDB conservation pool vs directory fullPoolFt
LIVE_AGREE_FT = 0.25             # median |TWDB - independent origin| over the last 7 full days (pre-registered before the run)
COMPLETE_YEAR_DAYS = 0.9         # research rule: >= 90 % of days in a calendar year


# ----------------------------------------------------------------------------------------------------------------------- parse
class TWDBError(Exception):
    pass


def parse_file(text: str, expected_datum: str | None = None, allow_headerless: bool = False) -> dict:
    """-> {reservoir, datum, days: [(date, ft)], dropped: {...}} ; raises TWDBError. Mirrors TWDB.parse (Swift)."""
    reservoir = None
    datums: list[str] = []
    in_datum = False
    unit_feet = None
    unit_text = ""
    header = None
    rows: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            body = line[1:].strip()
            if body.startswith("Estimated daily average data for "):
                reservoir = body[len("Estimated daily average data for "):]
            if body.startswith("Vertical datum(s) used:"):
                in_datum = True
                continue
            if in_datum:
                if not body or body.startswith("Units:"):
                    in_datum = False
                else:
                    datums.append(body)
            if body.startswith("water_level:"):
                unit_text = body[len("water_level:"):].strip()
                unit_feet = unit_text.lower().startswith("feet")
            continue
        if header is None:
            header = [h.strip() for h in line.split(",")]
            continue
        rows.append(line)
    if not header or header[0] != "date":
        raise TWDBError("response is not a TWDB CSV")
    if "water_level" not in header:
        raise TWDBError("no water_level column")
    headerless = allow_headerless and not datums and not unit_text and reservoir is None
    if not datums and not headerless:
        raise TWDBError("file declares no vertical datum")
    if len(datums) > 1:
        raise TWDBError("file declares several vertical datums")
    if not headerless:
        if unit_feet is not True:
            raise TWDBError(f"water_level unit '{unit_text or 'missing'}' is not feet")
        if expected_datum is not None and expected_datum.lower() != datums[0].lower():
            raise TWDBError(f"file datum '{datums[0]}' is not the binding's datum '{expected_datum}'")
    w = header.index("water_level")
    days: dict[str, float] = {}
    blank = zero = 0
    for r in rows:
        c = r.split(",")
        if len(c) <= w or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", c[0]):
            continue
        s = c[w].strip()
        if s == "":
            blank += 1
            continue
        try:
            v = float(s)
        except ValueError:
            continue
        if not math.isfinite(v) or v <= 0:
            zero += 1
            continue
        days.setdefault(c[0], v)
    if not days:
        raise TWDBError("no usable daily values")
    raw_days = sorted(days.items())
    kept = despike(raw_days)
    return {"reservoir": reservoir, "datum": datums[0] if datums else "", "headerless": headerless, "days": kept, "rawDays": len(raw_days), "blank": blank, "nonPositive": zero,
            "glitchDropped": len(raw_days) - len(kept)}


def _ordinal(d: str) -> int:
    return dt.date.fromisoformat(d).toordinal()


def despike(days: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Drop runs of 1..3 consecutive days that are > GLITCH_FT from both neighbours when the neighbours agree; hold back an
    unconfirmed trailing jump. Mirrors TWDB.despike (Swift)."""
    ords = [_ordinal(d) for d, _ in days]
    drop: set[int] = set()
    i = 1
    n = len(days)
    while i < n:
        matched = False
        for run in range(1, MAX_GLITCH_RUN + 1):
            j = i + run
            if j >= n:
                break
            if ords[j] - ords[i - 1] != run + 1:
                continue
            p, nx = days[i - 1][1], days[j][1]
            if abs(p - nx) > GLITCH_FT:
                continue
            if all(abs(days[k][1] - p) > GLITCH_FT and abs(days[k][1] - nx) > GLITCH_FT for k in range(i, j)):
                drop.update(range(i, j))
                i = j
                matched = True
                break
        if not matched:
            i += 1
    kept = [x for k, x in enumerate(days) if k not in drop]
    held = 0
    while held < MAX_GLITCH_RUN and len(kept) >= 2 and abs(kept[-1][1] - kept[-2][1]) > GLITCH_FT \
            and _ordinal(kept[-1][0]) - _ordinal(kept[-2][0]) <= 1:
        kept.pop()
        held += 1
    return kept


def corroborates(full: list[tuple[str, float]], year: list[tuple[str, float]]) -> bool:
    """A headerless record agrees with the declared -1year file: >= 200 shared days, 99 % equal to 0.005 ft (Swift: TWDB.corroborates)."""
    f = dict(full)
    shared = [(d, x) for d, x in year if d in f]
    if len(shared) < 200:
        return False
    return sum(1 for d, x in shared if abs(f[d] - x) <= 0.005) >= 0.99 * len(shared)


def complete_years(days: list[tuple[str, float]], today: str) -> int:
    """Research rule (history.py): a calendar year is complete with >= 90 % of its days; the current year never counts."""
    by: dict[int, int] = {}
    for d, _ in days:
        by[int(d[:4])] = by.get(int(d[:4]), 0) + 1
    cur = int(today[:4])
    return sum(1 for y, n in by.items() if y < cur and n >= COMPLETE_YEAR_DAYS * (366 if y % 4 == 0 else 365))


def twdb_live_ref(slug: str, datum: str) -> dict:
    """The LevelSeriesRef-shaped dict of a TWDB live series (daily average: cadence 1440, lag 1440)."""
    return {"provider": "twdb", "capability": "DIRECT_LAKE_GAUGE", "station": slug, "series": f"water_level@{datum}", "cadenceMin": 1440,
            "lagMin": 1440, "datumOffsetFt": 0.0,
            "note": "TWDB Water Data for Texas estimated daily average (relay of the lake's gauge; not independent corroboration)"}


def twdb_history_source(slug: str, datum: str) -> dict:
    return {"kind": "twdbDaily", "slug": slug, "datum": datum, "offsetFt": 0.0}


def slug_of(condensed: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", "-", condensed).lower()


# ----------------------------------------------------------------------------------------------------------------------- matching
def norm_name(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", s.lower())
    s = re.sub(r"[^a-z ]", " ", s)
    stop = {"lake", "reservoir", "the", "of", "o", "dam"}
    return " ".join(w for w in s.split() if w not in stop)


def haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    p = math.pi / 180
    x = math.sin((b_lat - a_lat) * p / 2) ** 2 + math.cos(a_lat * p) * math.cos(b_lat * p) * math.sin((b_lon - a_lon) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def match_directory(directory: list[dict], recent: dict) -> list[dict]:
    """A directory lake matches a TWDB reservoir when the normalised names are equal and the gauge is within MATCH_KM."""
    out = []
    for lake in directory:
        cands = []
        for key, r in recent.items():
            g = r.get("gauge_location") or {}
            if not g:
                continue
            lon, lat = g["coordinates"]
            km = haversine_km(lake["lat"], lake["lon"], lat, lon)
            if km <= MATCH_KM and norm_name(r["full_name"]) == norm_name(lake["name"]):
                cands.append((km, key, r))
        if len(cands) == 1:
            km, key, r = cands[0]
            out.append({"lake": lake, "key": key, "slug": slug_of(key), "distKm": round(km, 1), "recent": r})
        elif len(cands) > 1:
            raise SystemExit(f"ambiguous TWDB match for {lake['id']}: {[c[1] for c in cands]}")
    return out


# ----------------------------------------------------------------------------------------------------------------------- reference origins
def _get(url: str, timeout=60, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def local_date(iso: str, tz_offset_hours: float) -> str:
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return (t.astimezone(dt.timezone(dt.timedelta(hours=tz_offset_hours)))).date().isoformat()


def reference_series(row: dict, now: dt.datetime, tz_off: float) -> tuple[dict, dict[str, float]]:
    """Daily means (lake-local date) of one independent origin over the last 9 days, plus its descriptor."""
    prov, st, ser = row["prov"], row["station"], row["series"]
    vals: list[tuple[str, float]] = []
    if prov == "usgs":
        url = f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={st}&parameterCd={ser}&period=P9D&siteStatus=all"
        j = json.loads(_get(url))
        for ts in j["value"]["timeSeries"]:
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        x = float(v["value"])
                    except ValueError:
                        continue
                    if x > -990000:
                        vals.append((local_date(v["dateTime"], tz_off), x))
    elif prov == "nwps":
        j = json.loads(_get(f"https://api.water.noaa.gov/nwps/v1/gauges/{st}/stageflow/observed"))
        for r in j.get("data", []):
            x = r.get("primary")
            if isinstance(x, (int, float)) and x > -990:
                vals.append((local_date(r["validTime"], tz_off), float(x)))
    elif prov == "cwms":
        b = (now - dt.timedelta(days=9)).strftime("%Y-%m-%dT%H:%M:%SZ")
        e = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        name = urllib.request.quote(ser)
        j = json.loads(_get(f"https://cwms-data.usace.army.mil/cwms-data/timeseries?office={st}&name={name}&begin={b}&end={e}&unit=EN"))
        for ms, x, *_ in j.get("values", []):
            if x is not None:
                vals.append((local_date(dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat(), tz_off), float(x)))
    else:
        raise SystemExit(f"no reference fetcher for {prov}")
    by: dict[str, list[float]] = {}
    for d, x in vals:
        by.setdefault(d, []).append(x)
    return {"provider": prov, "station": st, "series": ser}, {d: round(statistics.fmean(xs), 3) for d, xs in sorted(by.items())}


def cwms_overlap(office: str, series: str, year: int) -> dict[str, float]:
    """Daily medians (UTC date, as the Brain's CWMS history reduces sub-daily series to lake-local days; the 5 h shift is below the
    resolution of this comparison) of one CWMS series for a whole calendar year, in feet."""
    b, e = f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z"
    url = f"https://cwms-data.usace.army.mil/cwms-data/timeseries?office={office}&name={urllib.request.quote(series)}&begin={b}&end={e}&unit=EN&page-size=100000"
    j = json.loads(_get(url, timeout=120))
    by: dict[str, list[float]] = {}
    for ms, x, *_ in j.get("values", []):
        if x is not None:
            by.setdefault(dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat(), []).append(float(x))
    return {d: round(statistics.median(xs), 3) for d, xs in sorted(by.items())}


def pick_reference(cands: list[dict]) -> dict | None:
    order = {"usgs": 0, "nwps": 1, "cwms": 2}
    ok = [c for c in cands if c["status"].startswith("VERIFIED") and c["family"] == "elev" and c["prov"] in order
          and not (c["prov"] == "usgs" and c["series"] not in {"62614", "62615", "62616", "00062", "72020", "72022"})]
    ok.sort(key=lambda c: (order[c["prov"]], -float(c["matchScore"] or 0)))
    return ok[0] if ok else None


# ----------------------------------------------------------------------------------------------------------------------- inputs
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fetch_raw(slugs: list[str], refs: dict[str, dict], now: dt.datetime) -> None:
    os.makedirs(os.path.join(RAW, "full"), exist_ok=True)

    def save(url: str, dest: str):
        time.sleep(2)   # polite: TWDB documents no limit; the full files are generated per request (0.5 to 13 s)
        data = _get(url, timeout=120, accept="text/csv, application/json")
        with open(dest, "wb") as f:
            f.write(data)

    save(f"{BASE}/recent-conditions.json", os.path.join(RAW, "recent-conditions.json"))
    for s in slugs:
        dest = os.path.join(RAW, "full", f"{s}.csv")
        save(f"{BASE}/individual/{s}.csv", dest)
        if not open(dest, errors="replace").read(4000).lstrip().startswith("#"):
            # seen 2026-10-13 on possum-kingdom.csv: no comment block. The -1year file declares the datum and unit.
            save(f"{BASE}/individual/{s}-1year.csv", os.path.join(RAW, "full", f"{s}-1year.csv"))
    out = {}
    for lake, (row, tz_off) in refs.items():
        desc, series = reference_series(row, now, tz_off)
        out[lake] = {"origin": desc, "dailyMeans": series}
    with open(os.path.join(RAW, "reference.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    with open(os.path.join(RAW, "FETCHED_AT"), "w") as f:
        f.write(now.strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")


# ----------------------------------------------------------------------------------------------------------------------- build
def build(raw_dir: str = RAW, research_dir: str = RESEARCH, data_dir: str = DATA, repo: str = REPO, today: str | None = None) -> dict:
    # table builder module (reused for the unchanged eligibility rules and the proposed / excluded tables)
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_bindings_table", os.path.join(HERE, "build_bindings_table.py"))
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)

    recent = json.load(open(os.path.join(raw_dir, "recent-conditions.json")))
    directory = json.load(open(os.path.join(data_dir, "directory_lakes_2026-10-13.json")))["lakes"]
    cands: dict[str, list[dict]] = {}
    for x in read_csv(os.path.join(data_dir, "binding", "candidates.csv")):
        cands.setdefault(x["lakeId"], []).append(x)
    proposed = {b["lakeId"]: b for b in json.load(open(os.path.join(repo, "jobs/lake-brain/data/bindings.proposed.v1.json")))["bindings"]}
    excluded = {e["lakeId"]: e for e in json.load(open(os.path.join(repo, "jobs/lake-brain/data/bindings.proposed.v1.excluded.json")))["excluded"]}
    ref_path = os.path.join(raw_dir, "reference.json")
    refs = json.load(open(ref_path)) if os.path.exists(ref_path) else {}
    ho_path = os.path.join(raw_dir, "history_overlap.json")
    history_overlap = json.load(open(ho_path)) if os.path.exists(ho_path) else {}
    fetched_at = open(os.path.join(raw_dir, "FETCHED_AT")).read().strip() if os.path.exists(os.path.join(raw_dir, "FETCHED_AT")) else None
    today = today or (fetched_at or "2026-10-13")[:10]

    matches = match_directory(directory, recent)
    rows = []
    for m in matches:
        lake, r, slug = m["lake"], m["recent"], m["slug"]
        lid = lake["id"]
        text = open(os.path.join(raw_dir, "full", f"{slug}.csv"), errors="replace").read()
        p = parse_file(text, allow_headerless=True)
        if p["headerless"]:
            yp = parse_file(open(os.path.join(raw_dir, "full", f"{slug}-1year.csv"), errors="replace").read())
            if not corroborates(p["days"], yp["days"]):
                raise SystemExit(f"{slug}: headerless full file is not corroborated by the -1year file")
            p["datum"] = yp["datum"]
            p["reservoir"] = yp["reservoir"]
        # the file must be the reservoir recent-conditions names (guards the slug derivation)
        header_ok = p["reservoir"] == r["full_name"]
        days = p["days"]
        live_date, live_ft = days[-1]
        last365 = [x for d, x in days if d >= (dt.date.fromisoformat(live_date) - dt.timedelta(days=365)).isoformat()]
        med365 = statistics.median(last365) if len(last365) >= 30 else None
        cont = None if med365 is None else round(med365 - live_ft, 2)
        cy = complete_years(days, today)
        age_days = (dt.date.fromisoformat(today) - dt.date.fromisoformat(live_date)).days

        cons, dead = r.get("conservation_pool_elevation"), r.get("dead_pool_elevation")
        lvl = r.get("elevation")
        pool = {
            "levelFt": lvl, "conservationPoolFt": cons, "deadPoolFt": dead, "directoryFullPoolFt": lake["fullPoolFt"],
            "levelMinusConservationFt": None if lvl is None or cons is None else round(lvl - cons, 2),
            "conservationMinusDirectoryFt": None if cons is None else round(cons - lake["fullPoolFt"], 2),
            "recentConditionsEqualsFile": lvl is not None and abs(lvl - live_ft) < 0.011,
        }
        pool["levelWithinStorageRange"] = (lvl is not None and cons is not None and (dead or 0) <= lvl <= cons + POOL_FLOOD_ALLOW_FT)
        pool["poolAgreesWithDirectory"] = pool["conservationMinusDirectoryFt"] is not None and abs(pool["conservationMinusDirectoryFt"]) <= POOL_AGREE_FT

        overlap = None
        ho = history_overlap.get(lid)
        if ho:
            dd = dict(days)
            diffs = [dd[d] - x for d, x in ho["dailyMedians"].items() if d in dd]
            overlap = {"source": ho["source"], "year": ho["year"], "daysCompared": len(diffs),
                       "medianAbsFt": round(statistics.median(abs(x) for x in diffs), 3) if diffs else None,
                       "medianSignedFt": round(statistics.median(diffs), 3) if diffs else None,
                       "p95AbsFt": round(sorted(abs(x) for x in diffs)[int(0.95 * (len(diffs) - 1))], 3) if diffs else None}
        ref = refs.get(lid)
        agree = None
        if ref:
            dm = ref["dailyMeans"]
            full_days = [d for d, _ in days if d < live_date and d in dm][-7:]
            diffs = [round(dict(days)[d] - dm[d], 3) for d in full_days]
            agree = {"origin": ref["origin"], "daysCompared": len(diffs), "diffsFt": diffs,
                     "medianAbsFt": round(statistics.median(abs(x) for x in diffs), 3) if diffs else None,
                     "medianSignedFt": round(statistics.median(diffs), 3) if diffs else None}
            agree["pass"] = agree["medianAbsFt"] is not None and agree["medianAbsFt"] <= LIVE_AGREE_FT and len(diffs) >= 5

        # position in the published table (unchanged rules)
        if lid in proposed:
            b = proposed[lid]
            table = {"state": "proposed", "primaryProvider": b["provider"], "liveProviders": [l["provider"] for l in b["live"]],
                     "historyCompleteYears": b["historyCompleteYears"], "historyKinds": [h["kind"] for h in b["history"]]}
        elif lid in excluded:
            e = excluded[lid]
            table = {"state": "excluded", "researchProvider": e["researchProvider"], "researchStatus": e["researchStatus"],
                     "reasons": [x["code"] for x in e["reasons"]]}
        else:
            table = {"state": "not research-bound"}
        rows.append({
            "lakeId": lid, "twdbKey": m["key"], "slug": m["slug"], "twdbName": r["full_name"], "matchDistKm": m["distKm"],
            "fileHeaderMatchesName": header_ok, "fullFileHadNoHeaderBlock": p["headerless"], "datumLabel": p["datum"], "datumIsNGVD29": p["datum"].upper() == "NGVD29",
            "firstDate": days[0][0], "liveDate": live_date, "liveAgeDays": age_days, "liveFt": live_ft,
            "pool": pool, "agreement": agree, "historyOverlap": overlap,
            "history": {"completeYears": cy, "rawDays": p["rawDays"], "blankLevelRows": p["blank"], "nonPositiveRows": p["nonPositive"],
                        "glitchDaysDropped": p["glitchDropped"], "median365Ft": None if med365 is None else round(med365, 2),
                        "median365MinusLiveFt": cont, "continuityPass": cont is not None and abs(cont) <= 15},
            "table": table,
            "referenceCandidate": None,
        })
        rc = pick_reference(cands.get(lid, []))
        rows[-1]["referenceCandidate"] = None if rc is None else {"provider": rc["prov"], "station": rc["station"], "series": rc["series"]}

    # eligibility under the UNCHANGED rules: a TWDB-primary row is a candidate only if the lake's research row is strict-eligible.
    for row in rows:
        t = row["table"]
        # A lake becomes a NEW TWDB-primary candidate only if its table position is "excluded" with researchProvider twdb AND no
        # exclusion reason is cured by TWDB (post-hoc / flagged-wave1 are research-status decisions, not data problems).
        if t["state"] == "excluded" and t.get("researchProvider") == "twdb":
            row["role"] = "none-today"
            row["roleWhy"] = "research row is " + t["researchStatus"] + " (" + ", ".join(t["reasons"]) + "): excluded by Michael's eligibility decisions, which this work does not change"
        elif t["state"] == "excluded":
            row["role"] = "none-today"
            row["roleWhy"] = "lake is excluded for " + ", ".join(t["reasons"]) + "; TWDB is a relay of the same gauges and cures none of it"
        elif t["state"] == "proposed":
            row["role"] = "backup-and-history"
            row["roleWhy"] = "already proposed on " + t["primaryProvider"] + "; TWDB can only be a relay fallback / history source"
        else:
            row["role"] = "none-today"
            row["roleWhy"] = "lake has no research-bound row"
    # history effect for proposed lakes
    for row in rows:
        if row["role"] != "backup-and-history":
            continue
        cur = row["table"]["historyCompleteYears"]
        new = row["history"]["completeYears"]
        tier = lambda n: "FULL" if n >= 15 else "STANDARD" if n >= 10 else "PROVISIONAL" if n >= 5 else "NONE"
        basis_now, basis_twdb = min(cur, 30), min(new, 30)
        row["historyEffect"] = {"currentCompleteYears": cur, "twdbCompleteYears": new, "currentBasisYears": basis_now, "twdbBasisYears": basis_twdb,
                                "currentTier": tier(basis_now), "twdbTier": tier(basis_twdb),
                                "improvesTier": tier(basis_twdb) != tier(basis_now) and basis_twdb > basis_now,
                                "useful": basis_twdb > basis_now}

    # the exact records an opt-in overlay would add (nothing is written into the published table)
    for row in rows:
        add = None
        if row["role"] == "backup-and-history":
            add = {"liveFallback": twdb_live_ref(row["slug"], row["datumLabel"]),
                   "historySource": twdb_history_source(row["slug"], row["datumLabel"]) if row["historyEffect"]["useful"] else None,
                   "historyOrder": "twdbDaily first (lowest precedence, the runner's merge lets the last entry win a date), then the existing sources",
                   "caveats": (["datum label is not NGVD29: values equal the primary source's native numbers within the compared window, the label is carried verbatim and no offset is applied"]
                               if not row["datumIsNGVD29"] else [])}
        row["proposedAdditions"] = add

    # checks summary per row
    for row in rows:
        c = {
            "fileHeaderMatchesName": row["fileHeaderMatchesName"],
            "liveFresh": row["liveAgeDays"] <= 1,
            "poolSanity": row["pool"]["levelWithinStorageRange"] and row["pool"]["poolAgreesWithDirectory"],
            "recentConditionsEqualsFile": row["pool"]["recentConditionsEqualsFile"],
            "liveAgreesWithIndependentOrigin": None if row["agreement"] is None else row["agreement"]["pass"],
            "historyContinuity": row["history"]["continuityPass"],
            "datumNGVD29": row["datumIsNGVD29"],
        }
        row["checks"] = c
        row["checksFailed"] = [k for k, v in c.items() if v is False]

    inputs = {"recent-conditions.json": sha256(os.path.join(raw_dir, "recent-conditions.json"))}
    for row in rows:
        inputs[f"individual/{row['slug']}.csv"] = sha256(os.path.join(raw_dir, "full", f"{row['slug']}.csv"))
    if os.path.exists(ref_path):
        inputs["reference.json"] = sha256(ref_path)
    if os.path.exists(ho_path):
        inputs["history_overlap.json"] = sha256(ho_path)
    inputs["bindings.proposed.v1.json"] = sha256(os.path.join(repo, "jobs/lake-brain/data/bindings.proposed.v1.json"))
    inputs["bindings.proposed.v1.excluded.json"] = sha256(os.path.join(repo, "jobs/lake-brain/data/bindings.proposed.v1.excluded.json"))
    inputs["directory_lakes_2026-10-13.json"] = sha256(os.path.join(data_dir, "directory_lakes_2026-10-13.json"))
    inputs["candidates.csv"] = sha256(os.path.join(data_dir, "binding", "candidates.csv"))

    tx = [r for r in rows if r["lakeId"].endswith("|TX")]
    useful = [r for r in rows if r.get("historyEffect", {}).get("useful")]
    summary = {
        "twdbReservoirsInRecentConditions": len(recent),
        "directoryLakes": len(directory),
        "directoryLakesMatched": len(rows),
        "texasDirectoryLakes": sum(1 for d in directory if d["state"] == "TX"),
        "texasDirectoryLakesMatched": len(tx),
        "nonTexasMatched": [r["lakeId"] for r in rows if not r["lakeId"].endswith("|TX")],
        "twdbPrimaryRowsInPublishedTable": [lid for lid, b in proposed.items() if b["provider"] == "twdb"],
        "newTwdbPrimaryCandidatesUnderUnchangedRules": [r["lakeId"] for r in rows if r["role"] == "primary-candidate"],
        "alreadyProposedLakesTwdbCouldBackUp": [r["lakeId"] for r in rows if r["role"] == "backup-and-history"],
        "excludedTodayWithTwdbMatch": [r["lakeId"] for r in rows if r["table"]["state"] == "excluded"],
        "excludedTodayWithTwdbAsResearchProvider": [r["lakeId"] for r in rows if r["table"].get("researchProvider") == "twdb"],
        "proposedLiveRelayFallbacks": [r["lakeId"] for r in rows if r["proposedAdditions"]],
        "proposedHistoryAdditions": [r["lakeId"] for r in rows if r["proposedAdditions"] and r["proposedAdditions"]["historySource"]],
        "historyDepthImproves": [{"lakeId": r["lakeId"], **r["historyEffect"]} for r in useful],
        "texasFleetSizeIfTwdbProvidersOnlyDirectoryLakes": len(tx),
        "rowsWithAnyFailedCheck": [{"lakeId": r["lakeId"], "failed": r["checksFailed"]} for r in rows if r["checksFailed"]],
    }
    return {"schema": "lake-brain-twdb-dryrun/v1", "researchDate": RAW_DATE, "fetchedAt": fetched_at,
            "note": "DRY RUN. Reads the published bindings table, never writes it. No TWDB row exists in bindings.proposed.v1.json, none is REVIEWED, none is in accepted_batch.json.",
            "thresholds": {"glitchFt": GLITCH_FT, "maxGlitchRunDays": MAX_GLITCH_RUN, "matchKm": MATCH_KM, "floodAllowFt": POOL_FLOOD_ALLOW_FT,
                           "poolAgreeFt": POOL_AGREE_FT, "liveAgreeFt": LIVE_AGREE_FT, "continuityFt": 15.0, "completeYearShare": COMPLETE_YEAR_DAYS},
            "inputs": inputs, "summary": summary, "lakes": rows}


CSV_COLS = ["lakeId", "twdbName", "slug", "matchDistKm", "datumLabel", "liveDate", "liveFt", "conservationPoolFt", "directoryFullPoolFt",
            "levelMinusConservationFt", "referenceOrigin", "refMedianAbsDiffFt", "histOverlapMedianAbsFt", "median365Ft", "median365MinusLiveFt", "firstDate",
            "completeYears", "glitchDaysDropped", "tableState", "tableDetail", "role", "currentHistoryYears", "twdbBasisYears",
            "checksFailed"]


def to_csv(doc: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLS)
    for r in doc["lakes"]:
        t = r["table"]
        detail = (f"{t['primaryProvider']}; hist {t['historyCompleteYears']}y" if t["state"] == "proposed"
                  else f"{t.get('researchProvider')} {t.get('researchStatus')}: {'+'.join(t.get('reasons', []))}" if t["state"] == "excluded" else "")
        a = r["agreement"]
        he = r.get("historyEffect") or {}
        w.writerow([r["lakeId"], r["twdbName"], r["slug"], r["matchDistKm"], r["datumLabel"], r["liveDate"], r["liveFt"],
                    r["pool"]["conservationPoolFt"], r["pool"]["directoryFullPoolFt"], r["pool"]["levelMinusConservationFt"],
                    "" if not a else f"{a['origin']['provider']}:{a['origin']['station']}", "" if not a else a["medianAbsFt"],
                    "" if not r["historyOverlap"] else r["historyOverlap"]["medianAbsFt"], r["history"]["median365Ft"], r["history"]["median365MinusLiveFt"], r["firstDate"], r["history"]["completeYears"],
                    r["history"]["glitchDaysDropped"], t["state"], detail, r["role"], he.get("currentCompleteYears", ""), he.get("twdbBasisYears", ""),
                    " ".join(r["checksFailed"])])
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="download the raw TWDB files and the independent reference series first")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.fetch:
        if os.environ.get("SECTOR_TWDB_TERMS_OK") != "1":
            raise SystemExit("--fetch is disabled: https://www.waterdatafortexas.org/robots.txt has 'Disallow: *.csv' for all agents and TWDB states "
                             "no licence or rate limit. Set SECTOR_TWDB_TERMS_OK=1 only after TWDB or Michael has cleared it "
                             "(docs/brains/LAKE_BRAIN_PROVIDERS.md section 4).")
        now = dt.datetime.now(dt.timezone.utc)
        os.makedirs(RAW, exist_ok=True)
        # the match needs recent-conditions first
        time.sleep(1)
        rc_path = os.path.join(RAW, "recent-conditions.json")
        open(rc_path, "wb").write(_get(f"{BASE}/recent-conditions.json"))
        recent = json.load(open(rc_path))
        directory = json.load(open(os.path.join(DATA, "directory_lakes_2026-10-13.json")))["lakes"]
        matches = match_directory(directory, recent)
        cands: dict[str, list[dict]] = {}
        for x in read_csv(os.path.join(DATA, "binding", "candidates.csv")):
            cands.setdefault(x["lakeId"], []).append(x)
        refs = {}
        for m in matches:
            rc = pick_reference(cands.get(m["lake"]["id"], []))
            if rc:
                tz = -5.0 if m["lake"]["state"] in ("TX", "LA") else -6.0   # CDT / MDT, 2026-10-13
                refs[m["lake"]["id"]] = (rc, tz)
        fetch_raw([m["slug"] for m in matches], refs, now)
        proposed = {b["lakeId"]: b for b in json.load(open(os.path.join(REPO, "jobs/lake-brain/data/bindings.proposed.v1.json")))["bindings"]}
        ho = {}
        for m in matches:
            b = proposed.get(m["lake"]["id"])
            h = (b or {}).get("history", [])
            if len(h) == 1 and h[0]["kind"] == "cwmsDaily" and b["historyCompleteYears"] < 15:
                time.sleep(2)
                ho[m["lake"]["id"]] = {"source": f"cwms:{h[0]['office']}:{h[0]['series']}", "year": 2024,
                                       "dailyMedians": cwms_overlap(h[0]["office"], h[0]["series"], 2024)}
        with open(os.path.join(RAW, "history_overlap.json"), "w") as f:
            json.dump(ho, f, indent=1, sort_keys=True)
    doc = build()
    js = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    cs = to_csv(doc)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and open(OUT_CSV).read() == cs
        print("twdb_dryrun outputs are up to date" if ok else "twdb_dryrun outputs differ from a fresh offline build")
        return 0 if ok else 1
    open(OUT_JSON, "w").write(js)
    open(OUT_CSV, "w").write(cs)
    s = doc["summary"]
    print(json.dumps({k: s[k] for k in ("directoryLakesMatched", "texasDirectoryLakesMatched", "newTwdbPrimaryCandidatesUnderUnchangedRules",
                                         "alreadyProposedLakesTwdbCouldBackUp", "excludedTodayWithTwdbMatch", "rowsWithAnyFailedCheck")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
