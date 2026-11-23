#!/usr/bin/env python3
"""Lake Brain operator-truth validation v2 (`lake-operator-truth-v2`): the READ-ONLY runner of the pre-registered protocol.

Protocol: PREREGISTRATION_v2.md beside this file. Sections 3-8 are implemented literally; thresholds are protocol constants, not options.
Integrity chain (checked before anything else; any mismatch = REFUSED, exit 2):
  PREREGISTRATION_v2.sha256  holds the sha256 of PREREGISTRATION_v2.md;
  PREREGISTRATION_v2.md      pins (between its `pins` markers) the sha256 of sample_v2.json, build_sample_v2.py and THIS runner;
  sample_v2.json             must still be build_sample_v2.py's output on the current bindings.
The run window is pre-registered too (refused outside it).

Read-only: public HTTPS GET to providers the Lake Brain already reads (CWMS Data API, USGS WaterServices, NWS NWPS, USBR RISE). It writes ONLY
into --out-dir (result JSON, per-lake CSV, summary text) and records its own sha256 and the commit it ran from. It never writes a database, bucket,
binding, Pulse config or the live build, and it does NOT publish /validation/lake-brain: it prints the value that WOULD be proposed (section 8).

usage:
  run_operator_truth_v2.py --out-dir DIR --commit SHA [--include-report-only] [--processes N]
  run_operator_truth_v2.py --verify-only        (integrity checks only; no network)
exit: 0 = ran (whatever the verdict); 2 = refused (integrity, run window, bad input)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_sample_v2 as BS  # noqa: E402

PROTOCOL = "lake-operator-truth-v2"
PREREG_PATH = os.path.join(HERE, "PREREGISTRATION_v2.md")
LOCK_PATH = os.path.join(HERE, "PREREGISTRATION_v2.sha256")
SAMPLE_PATH = os.path.join(HERE, "sample_v2.json")
RULE_PATH = os.path.join(HERE, "build_sample_v2.py")
RUNNER_PATH = os.path.abspath(__file__)
PINNED = {"sample_v2.json": SAMPLE_PATH, "build_sample_v2.py": RULE_PATH, "run_operator_truth_v2.py": RUNNER_PATH}

# ---- pre-registered constants (sections 5-7) ----------------------------------------------------------------------------------------------------
NIGHTS = [dt.date(2026, 11, 3) + dt.timedelta(days=i) for i in range(21)]     # 00:00 lake-local on each date
FETCH_BEFORE = dt.timedelta(days=6)
FETCH_AFTER = dt.timedelta(days=1)
RUN_START = dt.datetime(2026, 11, 24, 0, 0, tzinfo=dt.timezone.utc)
RUN_END = dt.datetime(2026, 11, 30, 23, 59, tzinfo=dt.timezone.utc)
SUBDAILY_TOL = dt.timedelta(minutes=90)
DAILY_TOL = dt.timedelta(hours=13)
AGREE_FT = 0.50
LAKE_MIN_N, LAKE_MIN_SHARE, LAKE_MAX_MEDAE = 14, 0.90, 0.25
V1_MIN_SCORED, V1_MIN_STRATA, V1_STRATUM_N = 45, 3, 5
V2_MIN_PASS = 0.90
V3_MIN_NIGHT_SHARE = 0.95
V4_MIN_STRATUM_PASS = 0.75

UA = "SectorLakeOperatorTruth/2.0 (read-only validation)"
CWMS = "https://cwms-data.usace.army.mil/cwms-data/timeseries"
USGS = "https://waterservices.usgs.gov/nwis"
NWPS = "https://api.water.noaa.gov/nwps/v1/gauges"
RISE = "https://data.usbr.gov/rise/api/result"
USGS_STAT_ORDER = ["00003", "32400", "30800", "00001", "00002"]


class FetchError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ integrity
def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_pins(prereg_text: str) -> dict:
    m = re.search(r"<!-- pins:begin -->(.*?)<!-- pins:end -->", prereg_text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        p = line.replace("`", "").split()
        if len(p) == 2 and re.fullmatch(r"[0-9a-f]{64}", p[1]):
            out[p[0]] = p[1]
    return out


def verify_preregistration(prereg=PREREG_PATH, lock=LOCK_PATH, pinned=None) -> list[str]:
    """Problems that make the run invalid; empty when the protocol and every pinned file are exactly as pre-registered."""
    pinned = PINNED if pinned is None else pinned
    problems = []
    for label, path in [("protocol", prereg), ("protocol lock", lock)] + list(pinned.items()):
        if not os.path.exists(path):
            problems.append(f"{label} missing: {os.path.basename(path)}")
    if problems:
        return problems
    with open(lock, encoding="utf-8") as fh:
        parts = fh.read().split()
    want = parts[0] if parts else ""
    if sha256_file(prereg) != want:
        return ["protocol differs from the sha256 in its lock file"]
    with open(prereg, encoding="utf-8") as fh:
        pins = read_pins(fh.read())
    for name, path in pinned.items():
        if name not in pins:
            problems.append(f"{name} is not pinned in the protocol")
        elif sha256_file(path) != pins[name]:
            problems.append(f"{name} differs from its pre-registered sha256")
    return problems


def in_run_window(now: dt.datetime) -> bool:
    return RUN_START <= now <= RUN_END


def head_commit(arg: str | None) -> str:
    if arg:
        return arg
    try:
        return subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# ------------------------------------------------------------------------------------------------ transport (GET only)
def http_get(url: str, accept: str = "application/json", timeout: int = 60) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - fixed public HTTPS hosts, GET only
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def _iso(s: str) -> dt.datetime:
    s = s.strip().replace("Z", "+00:00")
    t = dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _z(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _merge(obs):
    seen = {}
    for t, v in obs:
        seen[t] = v                                        # the later reading of one timestamp wins, as LakeLevelSeries.merge
    return sorted(seen.items())


# ------------------------------------------------------------------------------------------------ provider readers (mirror the Lake Brain's)
def read_cwms(get, office: str, name: str, begin: dt.datetime, end: dt.datetime):
    out, page = [], None
    for _ in range(20):
        q = {"office": office, "name": name, "unit": "EN", "begin": _z(begin), "end": _z(end), "page-size": "5000"}
        if page:
            q["page"] = page
        st, body = get(f"{CWMS}?{urllib.parse.urlencode(q)}", "application/json;version=2")
        if st != 200:
            raise FetchError(f"CWMS {office} {name}: HTTP {st}")
        raw = json.loads(body)
        k = 1 / 0.3048 if str(raw.get("units", "ft")).lower() == "m" else 1.0
        for row in raw.get("values") or []:
            if len(row) >= 2 and isinstance(row[0], (int, float)) and isinstance(row[1], (int, float)):
                out.append((dt.datetime.fromtimestamp(row[0] / 1000, dt.timezone.utc), row[1] * k))
        page = raw.get("next-page")
        if not page:
            break
    return _merge(out)


def read_usgs_iv(get, site: str, param: str, begin: dt.datetime, end: dt.datetime):
    st, body = get(f"{USGS}/iv/?format=json&sites={site}&parameterCd={param}&startDT={_z(begin)}&endDT={_z(end)}&siteStatus=all",
                   "application/json")
    if st == 404:
        return []
    if st != 200:
        raise FetchError(f"USGS iv {site} {param}: HTTP {st}")
    out = []
    for s in (json.loads(body).get("value") or {}).get("timeSeries") or []:
        for blk in s.get("values") or []:
            for v in blk.get("value") or []:
                try:
                    x = float(v.get("value"))
                except (TypeError, ValueError):
                    continue
                if x > -990000:
                    out.append((_iso(v["dateTime"]), x))
    return _merge(out)


def read_usgs_dv(get, site: str, param: str, stat: str, begin: dt.datetime, end: dt.datetime, tz: ZoneInfo):
    """Daily values, statistic precedence as the Lake Brain (mean, end-of-day, ...); each at 12:00 lake-local of its date (pre-registration section 6)."""
    url = f"{USGS}/dv/?format=json&sites={site}&parameterCd={param}&startDT={begin.date()}&endDT={end.date()}&siteStatus=all"
    if stat != "dv":
        url += f"&statCd={stat}"
    st, body = get(url, "application/json")
    if st == 404:
        return []
    if st != 200:
        raise FetchError(f"USGS dv {site} {param}: HTTP {st}")
    by_stat: dict = {}
    for s in (json.loads(body).get("value") or {}).get("timeSeries") or []:
        var = s.get("variable") or {}
        nodata = var.get("noDataValue", -999999)
        opts = ((var.get("options") or {}).get("option") or [{}])
        code = opts[0].get("optionCode", "?") if opts else "?"
        for blk in s.get("values") or []:
            for v in blk.get("value") or []:
                try:
                    x = float(v.get("value"))
                except (TypeError, ValueError):
                    continue
                if x != nodata and x > -990000:
                    by_stat.setdefault(code, {})[v["dateTime"][:10]] = x
    merged: dict = {}
    for code in USGS_STAT_ORDER + sorted(k for k in by_stat if k not in USGS_STAT_ORDER):
        for d, x in (by_stat.get(code) or {}).items():
            merged.setdefault(d, x)
    return sorted((dt.datetime.combine(dt.date.fromisoformat(d), dt.time(12, 0), tz), x) for d, x in merged.items())


def read_nwps(get, lid: str, expected_pe: str | None):
    st, body = get(f"{NWPS}/{lid}/stageflow/observed", "application/json")
    if st != 200:
        raise FetchError(f"NWPS {lid}: HTTP {st}")
    obj = json.loads(body)
    if expected_pe and isinstance(obj.get("pedts"), str) and not obj["pedts"].startswith(expected_pe):
        raise FetchError(f"NWPS {lid}: gauge reports {obj['pedts']}, binding expects {expected_pe}")
    if str(obj.get("primaryUnits", "ft")).lower() != "ft":
        raise FetchError(f"NWPS {lid}: unit {obj.get('primaryUnits')} is not feet")
    out = []
    for r in obj.get("data") or []:
        v = r.get("primary")
        if isinstance(v, (int, float)) and v > -990 and r.get("validTime"):
            out.append((_iso(r["validTime"]), float(v)))
    return _merge(out)


def read_rise(get, item: str, begin: dt.datetime):
    out, page = [], 1
    while page <= 10:
        st, body = get(f"{RISE}?itemId={item}&dateTime%5Bafter%5D={begin.date()}&itemsPerPage=2000&page={page}", "application/vnd.api+json")
        if st != 200:
            raise FetchError(f"RISE {item}: HTTP {st}")
        obj = json.loads(body)
        for it in obj.get("data") or []:
            a = it.get("attributes") or {}
            v = a.get("result")
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                continue                                   # RISE writes 0.0 for a missing daily value
            kind = (a.get("resultAttributes") or {}).get("resultType")
            if kind is not None and kind != "observed":
                continue
            out.append((_iso(a["dateTime"]), float(v)))
        if not ((obj.get("links") or {}).get("next")):
            break
        page += 1
    return _merge(out)


def readings(get, ref: dict, begin: dt.datetime, end: dt.datetime, tz: ZoneInfo):
    """(time, ft) readings of one series in [begin, end], with its recorded offset ADDED (LakeHistoryOffsets sign convention)."""
    k = ref["kind"]
    if k in ("cwms", "a2w", "cwmsDaily"):
        office, name = ref["key"]                                          # a2w: same office + tsid from the CWMS Data API (assumption A1)
        obs = read_cwms(get, office, name, begin, end)
    elif k == "usgs":
        obs = read_usgs_iv(get, ref["station"], ref["series"], begin, end)
    elif k == "usgsDaily":
        obs = (read_usgs_iv(get, ref["site"], ref["param"], begin, end) if ref.get("stat") == "iv"
               else read_usgs_dv(get, ref["site"], ref["param"], ref.get("stat", "dv"), begin, end, tz))
    elif k == "nwps":
        obs = read_nwps(get, ref["station"], (ref.get("series") or "")[:2] or None)
    elif k in ("rise", "riseDaily"):
        obs = read_rise(get, ref.get("station") or ref.get("item"), begin)
    else:
        # tva / tvaOperatingGuide / hadsDaily: no lake of the frozen set uses them (TVA-primary lakes are excluded)
        raise FetchError(f"series kind {k} is not read by protocol v2")
    off = float(ref.get("offsetFt") or 0.0)
    return [(t, v + off) for t, v in obs if begin <= t <= end]

# ------------------------------------------------------------------------------------------------ the protocol
def r2(x: float) -> float:
    return math.copysign(math.floor(abs(x) * 100 + 0.5) / 100, x)


def night_instant(d: dt.date, tz: ZoneInfo) -> dt.datetime:
    return dt.datetime.combine(d, dt.time(0, 0), tz)


def brain_value(primary_obs, at: dt.datetime, lag_min: int, cadence_min: int):
    """(t_B, B) the Brain would select at `at`: the latest reading at or before it within lagMin + 3 x cadenceMin (offset already added)."""
    limit = dt.timedelta(minutes=lag_min + 3 * cadence_min)
    best = None
    for t, v in primary_obs:
        if t <= at and at - t <= limit and (best is None or t > best[0]):
            best = (t, v)
    return None if best is None else (best[0], r2(best[1]))


def is_fresh(t_b: dt.datetime, at: dt.datetime, lag_min: int, cadence_min: int) -> bool:
    """The Brain's own staleness limit (age <= cadenceMin + lagMin, LakeLevelClassifier freshness): a staler value is published as stale."""
    return at - t_b <= dt.timedelta(minutes=lag_min + cadence_min)


def match_truth(truth_obs, t_b: dt.datetime, cadence: str):
    """The truth reading nearest to t_B (earlier on a tie), within 90 min (sub-daily) or 13 h (daily)."""
    tol = DAILY_TOL if cadence == "DAILY" else SUBDAILY_TOL
    best = None
    for t, v in truth_obs:
        d = abs(t - t_b)
        if d <= tol and (best is None or d < best[0] or (d == best[0] and t < best[1])):
            best = (d, t, v)
    return None if best is None else (best[1], r2(best[2]))


def lake_class(n: int, share, medae) -> str:
    if n < LAKE_MIN_N:
        return "INSUFFICIENT"
    return "PASS" if share >= LAKE_MIN_SHARE and medae <= LAKE_MAX_MEDAE else "FAIL"


def evaluate_lake(entry: dict, get) -> dict:
    tz = ZoneInfo(entry["timeZone"])
    instants = [night_instant(d, tz) for d in NIGHTS]
    begin, end = instants[0] - FETCH_BEFORE, instants[-1] + FETCH_AFTER
    p, tr = entry["primary"], entry["truth"]
    lag, cad = int(p.get("lagMin") or 0), int(p.get("cadenceMin") or 0)
    res = {"lakeId": entry["lakeId"], "stratum": entry["primaryProvider"], "independent": bool(entry.get("independentTruth")),
           "truthClass": tr["independence"], "truthKind": tr["kind"], "truthCadence": tr["cadence"], "truthBoundRole": tr["boundRole"],
           "truthOffsetFt": tr["offsetFt"], "valueDatum": entry.get("valueDatum"), "truthDatum": tr.get("datum"),
           "valueSeries": f"{p['kind']}:{':'.join(map(str, p['key']))}", "truthSeries": f"{tr['kind']}:{':'.join(map(str, tr['key']))}",
           "nights": [], "errors": []}
    res["fetchedAt"] = _z(dt.datetime.now(dt.timezone.utc))
    try:
        pobs = readings(get, p, begin, end, tz)
    except Exception as e:                                                    # noqa: BLE001 - recorded, never a pass
        pobs = []
        res["errors"].append(f"value series: {type(e).__name__}: {e}")
    try:
        tobs = readings(get, tr, begin, end, tz)
    except Exception as e:                                                    # noqa: BLE001
        tobs = []
        res["errors"].append(f"truth series: {type(e).__name__}: {e}")
    res["valueReadings"], res["truthReadings"] = len(pobs), len(tobs)
    errs, ages = [], []
    counts = {"NO_BRAIN_VALUE": 0, "STALE_BRAIN_VALUE": 0, "NO_TRUTH_MATCH": 0}
    for d, m in zip(NIGHTS, instants):
        b = brain_value(pobs, m, lag, cad)
        if b is None:
            counts["NO_BRAIN_VALUE"] += 1
            res["nights"].append({"night": d.isoformat(), "status": "NO_BRAIN_VALUE"})
            continue
        age = round((m - b[0]).total_seconds() / 60)
        if not is_fresh(b[0], m, lag, cad):
            counts["STALE_BRAIN_VALUE"] += 1
            res["nights"].append({"night": d.isoformat(), "status": "STALE_BRAIN_VALUE", "tB": _z(b[0]), "B": b[1], "ageMin": age})
            continue
        t = match_truth(tobs, b[0], tr["cadence"])
        if t is None:
            counts["NO_TRUTH_MATCH"] += 1
            res["nights"].append({"night": d.isoformat(), "status": "NO_TRUTH_MATCH", "tB": _z(b[0]), "B": b[1], "ageMin": age})
            continue
        e = r2(b[1] - t[1])
        errs.append(e)
        ages.append(age)
        res["nights"].append({"night": d.isoformat(), "status": "MATCHED", "tB": _z(b[0]), "B": b[1], "ageMin": age, "tT": _z(t[0]),
                              "T": t[1], "e": e, "dtMin": round((t[0] - b[0]).total_seconds() / 60)})
    n = len(errs)
    abs_e = [abs(x) for x in errs]
    res.update({"n": n, "noBrainValue": counts["NO_BRAIN_VALUE"], "staleBrainValue": counts["STALE_BRAIN_VALUE"],
                "noTruthMatch": counts["NO_TRUTH_MATCH"],
                "medAE": r2(statistics.median(abs_e)) if n else None,
                "shareWithin": round(sum(1 for x in abs_e if x <= AGREE_FT + 1e-9) / n, 4) if n else None,
                "within": sum(1 for x in abs_e if x <= AGREE_FT + 1e-9),
                "meanE": r2(statistics.fmean(errs)) if n else None, "maxAE": r2(max(abs_e)) if n else None,
                "medianAgeMin": statistics.median(ages) if ages else None, "maxAgeMin": max(ages) if ages else None})
    res["result"] = lake_class(n, res["shareWithin"], res["medAE"])
    if res["result"] == "INSUFFICIENT":
        res["insufficientReason"] = "fetch error" if res["errors"] else max(counts, key=lambda k: counts[k])
    return res


def summarize(lakes: list[dict]) -> dict:
    scored = [x for x in lakes if x["result"] in ("PASS", "FAIL")]
    passed = [x for x in scored if x["result"] == "PASS"]
    nights = sum(x["n"] for x in scored)
    within = sum(x["within"] for x in scored)

    def group(key):
        out = {}
        for x in lakes:
            g = out.setdefault(str(x[key]), {"lakes": 0, "scored": 0, "pass": 0, "fail": 0, "insufficient": 0, "nights": 0, "within": 0})
            g["lakes"] += 1
            g[{"PASS": "pass", "FAIL": "fail", "INSUFFICIENT": "insufficient"}[x["result"]]] += 1
            if x["result"] in ("PASS", "FAIL"):
                g["scored"] += 1
                g["nights"] += x["n"]
                g["within"] += x["within"]
        for g in out.values():
            g["passShare"] = round(g["pass"] / g["scored"], 4) if g["scored"] else None
            g["nightShare"] = round(g["within"] / g["nights"], 4) if g["nights"] else None
        return dict(sorted(out.items()))
    return {"lakes": len(lakes), "scored": len(scored), "pass": len(passed), "fail": len(scored) - len(passed),
            "insufficient": len(lakes) - len(scored), "passShare": round(len(passed) / len(scored), 4) if scored else None,
            "lakeNights": nights, "lakeNightsWithin": within, "nightShare": round(within / nights, 4) if nights else None,
            "byStratum": group("stratum"), "byTruthClass": group("truthClass"), "byTruthCadence": group("truthCadence")}


def criteria(summary: dict) -> dict:
    big = {s: g for s, g in summary["byStratum"].items() if g["scored"] >= V1_STRATUM_N}
    low = sorted(s for s, g in big.items() if g["passShare"] < V4_MIN_STRATUM_PASS)
    return {"V1": {"pass": summary["scored"] >= V1_MIN_SCORED and len(big) >= V1_MIN_STRATA, "scored": summary["scored"],
                   "need": V1_MIN_SCORED, "strataWith5Scored": sorted(big), "needStrata": V1_MIN_STRATA},
            "V2": {"pass": summary["passShare"] is not None and summary["passShare"] >= V2_MIN_PASS, "passShare": summary["passShare"],
                   "need": V2_MIN_PASS},
            "V3": {"pass": summary["nightShare"] is not None and summary["nightShare"] >= V3_MIN_NIGHT_SHARE, "nightShare": summary["nightShare"],
                   "need": V3_MIN_NIGHT_SHARE},
            "V4": {"pass": not low, "strataBelow": low, "need": V4_MIN_STRATUM_PASS}}


def verdict(all_summary: dict, independent_summary: dict) -> dict:
    """Section 7: V1-V4 must hold for the whole verdict set AND, on its own, for the independent (CROSS_AGENCY) subset."""
    ca, ci = criteria(all_summary), criteria(independent_summary)
    if not (ca["V1"]["pass"] and ci["V1"]["pass"]):
        overall = "INCONCLUSIVE"
    elif all(c["pass"] for c in list(ca.values()) + list(ci.values())):
        overall = "PASS"
    else:
        overall = "FAIL"
    return {"verdict": overall, "criteria": ca, "independentCriteria": ci}


def validation_node_proposal(result: dict, model_version: str = "lake-level-rules-v2") -> dict | None:
    """The /validation/lake-brain value section 8 would PROPOSE, in exactly LakeBrainRunner.ValidationSummary's shape; None = no change.
    Never written by this runner."""
    if result["verdict"]["verdict"] != "PASS":
        return None
    s = result["summary"]
    return {
        "brainId": "lake-brain",
        "modelVersion": model_version,
        "validationVersion": f"{PROTOCOL} (prereg {result['preregSha256'][:12]}, runner {result['runnerSha256'][:12]}, run {result['runAt'][:10]})",
        "status": "PARTIAL",
        "lastRunAt": result["runAt"],
        "holdoutType": ("pre-registered operator-truth comparison: 21 past nights (2026-11-03..23, 00:00 lake-local), every verdict-eligible "
                        f"accepted lake ({s['lakes']}); truth = an operator or other-agency history series, never the Brain's value series, a "
                        "fallback live series, a same-sensor series or a fitted offset"),
        "sampleCount": s["lakeNights"],
        "lakeCount": s["scored"],
        "notes": [
            "Scope: accuracy of the Brain's fresh current observed level (LB-04) only. Bands, trend labels, zones, flood state and outlooks are not validated by this.",
            f"{s['pass']} of {s['scored']} scored lakes PASS; {s['lakeNightsWithin']} of {s['lakeNights']} lake-nights within 0.5 ft; "
            f"{s['insufficient']} lakes had too few matched nights.",
            "Protocol lake-operator-truth-v2 (Sector_Engine jobs/lake-brain/validation/operator_truth); result committed with the owner approval.",
        ],
    }


def run(sample: dict, get, include_report_only: bool, processes: int, now: dt.datetime, prereg_sha: str, runner_sha: str, commit: str) -> dict:
    def go(entries):
        with cf.ThreadPoolExecutor(max_workers=max(1, processes)) as ex:
            return sorted(ex.map(lambda e: evaluate_lake(e, get), entries), key=lambda x: x["lakeId"])
    lakes = go(sample["verdictSet"])
    summary = summarize(lakes)
    ind = summarize([x for x in lakes if x["independent"]])
    out = {"protocol": PROTOCOL, "preregSha256": prereg_sha, "runnerSha256": runner_sha, "commit": commit,
           "sampleSha256": sha256_file(SAMPLE_PATH) if os.path.exists(SAMPLE_PATH) else None,
           "python": platform.python_version(), "runAt": _z(now),
           "window": {"nights": [d.isoformat() for d in NIGHTS], "instant": "00:00 lake-local", "scope": "fresh Brain value (age <= cadence + lag)"},
           "lakes": lakes, "summary": summary, "independentSummary": ind, "verdict": verdict(summary, ind)}
    if include_report_only:
        ro = go(sample["reportOnlySample"])
        out["reportOnly"] = {"lakes": ro, "summary": summarize(ro), "note": "never part of the verdict (section 3.5)"}
    out["proposedValidationNode"] = validation_node_proposal(out)
    out["published"] = False
    return out


def write_outputs(result: dict, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    stamp = result["runAt"][:10]
    paths = []
    jp = os.path.join(out_dir, f"operator_truth_v2_{stamp}.json")
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
        fh.write("\n")
    paths.append(jp)
    cp = os.path.join(out_dir, f"operator_truth_v2_{stamp}_lakes.csv")
    cols = ["set", "lakeId", "stratum", "independent", "result", "n", "within", "shareWithin", "medAE", "meanE", "maxAE", "medianAgeMin",
            "maxAgeMin", "noBrainValue", "staleBrainValue", "noTruthMatch", "truthClass", "truthKind", "truthCadence", "truthOffsetFt",
            "valueDatum", "truthDatum", "valueSeries", "truthSeries", "insufficientReason", "errors"]
    with open(cp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for label, lakes in (("verdict", result["lakes"]), ("reportOnly", (result.get("reportOnly") or {}).get("lakes") or [])):
            for x in lakes:
                w.writerow({**x, "set": label, "errors": " | ".join(x["errors"])})
    paths.append(cp)
    sp = os.path.join(out_dir, f"operator_truth_v2_{stamp}_summary.txt")
    with open(sp, "w", encoding="utf-8") as fh:
        fh.write(summary_text(result))
    paths.append(sp)
    return paths


def _crit_lines(label: str, c: dict) -> list[str]:
    def pf(x):
        return "PASS" if x else "FAIL"
    return [f"{label} V1 enough evidence {pf(c['V1']['pass'])} ({c['V1']['scored']} scored, need {V1_MIN_SCORED}; strata with >= 5: "
            f"{', '.join(c['V1']['strataWith5Scored']) or 'none'})",
            f"{label} V2 lakes PASS share {c['V2']['passShare']} (need >= {V2_MIN_PASS}) {pf(c['V2']['pass'])}",
            f"{label} V3 lake-nights within 0.5 ft {c['V3']['nightShare']} (need >= {V3_MIN_NIGHT_SHARE}) {pf(c['V3']['pass'])}",
            f"{label} V4 strata >= {V4_MIN_STRATUM_PASS} PASS {pf(c['V4']['pass'])}" + (f" ({', '.join(c['V4']['strataBelow'])})" if c['V4']['strataBelow'] else "")]


def summary_text(result: dict) -> str:
    s, v = result["summary"], result["verdict"]
    lines = [f"Lake operator-truth validation v2 (prereg sha256 {result['preregSha256'][:12]}, runner {result['runnerSha256'][:12]}, "
             f"commit {str(result['commit'])[:9]}): {v['verdict']}",
             f"Scored {s['scored']} of {s['lakes']} verdict lakes: {s['pass']} PASS, {s['fail']} FAIL, {s['insufficient']} INSUFFICIENT."]
    lines += _crit_lines("All:", v["criteria"]) + _crit_lines("Independent (cross-agency):", v["independentCriteria"])
    lines.append("By truth class: " + "; ".join(f"{k} {g['pass']}/{g['scored']}" for k, g in s["byTruthClass"].items()))
    for x in result["lakes"]:
        lines.append(f"  {x['lakeId']}: {x['result']} n={x['n']} medAE={x['medAE']} within={x['within']}/{x['n']} meanE={x['meanE']} "
                     f"maxAE={x['maxAE']} medianAge={x['medianAgeMin']} min stale={x['staleBrainValue']} ({x['truthClass']}, {x['truthSeries']})"
                     + (f" [{x.get('insufficientReason')}]" if x["result"] == "INSUFFICIENT" else ""))
    if result.get("reportOnly"):
        r = result["reportOnly"]["summary"]
        lines.append(f"Report-only (not in the verdict): {r['pass']} PASS, {r['fail']} FAIL, {r['insufficient']} INSUFFICIENT of {r['lakes']}.")
    lines.append("Proposed /validation/lake-brain: " + ("status PARTIAL (NOT published; owner decision)" if result.get("proposedValidationNode")
                                                       else "no change (stays NOT_VALIDATED)"))
    return "\n".join(lines) + "\n"


def refuse(msg: str) -> int:
    print("REFUSED:\n  " + msg.replace("\n", "\n  "))
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir")
    ap.add_argument("--commit", help="the commit the files were taken from (recorded; read from git when omitted)")
    ap.add_argument("--include-report-only", action="store_true")
    ap.add_argument("--processes", type=int, default=4)
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args(argv)
    problems = verify_preregistration()
    if problems:
        return refuse("\n".join(problems))
    try:
        with open(SAMPLE_PATH, encoding="utf-8") as fh:
            text = fh.read()
        sample = json.loads(text)
        rebuilt = BS.dumps(BS.build(BS.load_generated(), BS.load_accepted(), BS.load_reviewed()))
    except (OSError, ValueError, KeyError) as e:
        return refuse(f"cannot read the frozen set or its inputs: {type(e).__name__}: {e}")
    if text != rebuilt:
        return refuse("the frozen set is not the rule's output on the current bindings (bindings changed since registration)")
    if a.verify_only:
        print("pre-registration verified (protocol lock, pinned set, rule, runner)")
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    if not in_run_window(now):
        return refuse(f"{_z(now)} is outside the pre-registered run window {_z(RUN_START)} .. {_z(RUN_END)}")
    if not a.out_dir:
        return refuse("--out-dir is required")
    result = run(sample, http_get, a.include_report_only, a.processes, now, sha256_file(PREREG_PATH), sha256_file(RUNNER_PATH),
                 head_commit(a.commit))
    for p in write_outputs(result, a.out_dir):
        print("wrote", p)
    print(summary_text(result), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
