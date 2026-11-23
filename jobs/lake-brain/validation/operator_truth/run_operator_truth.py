#!/usr/bin/env python3
"""Lake Brain operator-truth validation v1 (`lake-operator-truth-v1`): the READ-ONLY runner of the pre-registered protocol.

Protocol: docs/brains/LAKE_BRAIN_OPERATOR_TRUTH_PREREGISTRATION.md (committed 469a15f before this runner and before any fetch). Sections 3-8 are
implemented literally; thresholds are constants of the protocol, not options. The runner refuses to run when the protocol, the frozen sample or the
sample rule differ from the pre-registered hashes, or outside the pre-registered run window.

Read-only: public HTTPS GET to providers the Lake Brain already reads (CWMS Data API, USGS WaterServices, NWS NWPS, USBR RISE).
It writes ONLY into --out-dir (result JSON, per-lake CSV, summary text). It never writes a database, bucket, binding, Pulse config or the live build,
and it does NOT publish /validation/lake-brain: it prints the value that WOULD be proposed (section 8); publishing is the owner's decision.

usage:
  run_operator_truth.py --out-dir DIR [--include-report-only] [--processes N]
  run_operator_truth.py --verify-only        (hash and rule checks only; no network)
exit: 0 = ran (whatever the verdict); 2 = refused (hash mismatch, outside the run window, bad input)
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
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
import build_sample  # noqa: E402

PROTOCOL = "lake-operator-truth-v1"
PREREG_PATH = os.path.join(ROOT, "docs", "brains", "LAKE_BRAIN_OPERATOR_TRUTH_PREREGISTRATION.md")
SAMPLE_PATH = os.path.join(HERE, "sample_v1.json")
RULE_PATH = os.path.join(HERE, "build_sample.py")
PREREG_COMMIT = "469a15fda5308cd471f95a0b8454ef04223f3045"
PREREG_SHA256 = "7bc8d1df9f2bb319164a42791b5128ce3777953a0b4f6e59e40f1d9fbc5b07c0"
SAMPLE_SHA256 = "b6fe824b9f5aa9d0959014ed757c32110e53339db1e10d5806df22c39038684d"
RULE_SHA256 = "2b0a29d7fd8531233f7866f3035de297e7fffa2771548f09ddd9ca315f27a317"

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

UA = "SectorLakeOperatorTruth/1.0 (read-only validation)"
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


def verify_preregistration(prereg=PREREG_PATH, sample=SAMPLE_PATH, rule=RULE_PATH) -> list[str]:
    """Problems that make the run invalid; empty when the protocol, sample and rule are exactly the pre-registered files."""
    problems = []
    for label, path, want in (("protocol", prereg, PREREG_SHA256), ("sample", sample, SAMPLE_SHA256), ("sample rule", rule, RULE_SHA256)):
        if not os.path.exists(path):
            problems.append(f"{label} missing: {os.path.relpath(path, ROOT)}")
        elif sha256_file(path) != want:
            problems.append(f"{label} differs from the pre-registered sha256 ({os.path.relpath(path, ROOT)})")
    return problems


def in_run_window(now: dt.datetime) -> bool:
    return RUN_START <= now <= RUN_END


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
        seen.setdefault(t, v)
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
    """Daily values, statistic precedence as the Lake Brain (mean, end-of-day, ...); each at 12:00 lake-local of its date (protocol section 6)."""
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
        # tva / tvaOperatingGuide / hadsDaily: no lake of the frozen sample uses them (TVA-primary lakes are excluded, section 3.1)
        raise FetchError(f"series kind {k} is not read by protocol v1")
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
    res = {"lakeId": entry["lakeId"], "stratum": entry["primaryProvider"], "truthClass": tr["independence"], "truthKind": tr["kind"],
           "truthCadence": tr["cadence"], "truthBoundRole": tr["boundRole"], "truthOffsetFt": tr["offsetFt"],
           "valueSeries": f"{p['kind']}:{':'.join(map(str, p['key']))}", "truthSeries": f"{tr['kind']}:{':'.join(map(str, tr['key']))}",
           "nights": [], "errors": []}
    fetched_at = dt.datetime.now(dt.timezone.utc)
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
    res["fetchedAt"] = _z(fetched_at)
    res["valueReadings"], res["truthReadings"] = len(pobs), len(tobs)
    errs = []
    no_b = no_t = 0
    for d, m in zip(NIGHTS, instants):
        b = brain_value(pobs, m, int(p.get("lagMin") or 0), int(p.get("cadenceMin") or 0))
        if b is None:
            no_b += 1
            res["nights"].append({"night": d.isoformat(), "status": "NO_BRAIN_VALUE"})
            continue
        t = match_truth(tobs, b[0], tr["cadence"])
        if t is None:
            no_t += 1
            res["nights"].append({"night": d.isoformat(), "status": "NO_TRUTH_MATCH", "tB": _z(b[0]), "B": b[1]})
            continue
        e = r2(b[1] - t[1])
        errs.append(e)
        res["nights"].append({"night": d.isoformat(), "status": "MATCHED", "tB": _z(b[0]), "B": b[1], "tT": _z(t[0]), "T": t[1], "e": e,
                              "dtMin": round((t[0] - b[0]).total_seconds() / 60)})
    n = len(errs)
    abs_e = [abs(x) for x in errs]
    res.update({"n": n, "noBrainValue": no_b, "noTruthMatch": no_t,
                "medAE": r2(statistics.median(abs_e)) if n else None,
                "shareWithin": round(sum(1 for x in abs_e if x <= AGREE_FT + 1e-9) / n, 4) if n else None,
                "within": sum(1 for x in abs_e if x <= AGREE_FT + 1e-9),
                "meanE": r2(statistics.fmean(errs)) if n else None, "maxAE": r2(max(abs_e)) if n else None})
    res["result"] = lake_class(n, res["shareWithin"], res["medAE"])
    if res["result"] == "INSUFFICIENT":
        res["insufficientReason"] = ("fetch error" if res["errors"] else
                                     "no Brain value" if no_b >= no_t else "no truth match")
    return res


def summarize(lakes: list[dict]) -> dict:
    scored = [x for x in lakes if x["result"] in ("PASS", "FAIL")]
    passed = [x for x in scored if x["result"] == "PASS"]
    nights = sum(x["n"] for x in scored)
    within = sum(x["within"] for x in scored)

    def group(key):
        out = {}
        for x in lakes:
            g = out.setdefault(x[key], {"lakes": 0, "scored": 0, "pass": 0, "fail": 0, "insufficient": 0, "nights": 0, "within": 0})
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


def verdict(summary: dict) -> dict:
    strata = summary["byStratum"]
    big = {s: g for s, g in strata.items() if g["scored"] >= V1_STRATUM_N}
    v1 = summary["scored"] >= V1_MIN_SCORED and len(big) >= V1_MIN_STRATA
    v2 = summary["passShare"] is not None and summary["passShare"] >= V2_MIN_PASS
    v3 = summary["nightShare"] is not None and summary["nightShare"] >= V3_MIN_NIGHT_SHARE
    low = sorted(s for s, g in big.items() if g["passShare"] < V4_MIN_STRATUM_PASS)
    v4 = not low
    overall = "INCONCLUSIVE" if not v1 else ("PASS" if (v2 and v3 and v4) else "FAIL")
    return {"verdict": overall,
            "criteria": {
                "V1": {"pass": v1, "scored": summary["scored"], "need": V1_MIN_SCORED, "strataWith5Scored": sorted(big), "needStrata": V1_MIN_STRATA},
                "V2": {"pass": v2, "passShare": summary["passShare"], "need": V2_MIN_PASS},
                "V3": {"pass": v3, "nightShare": summary["nightShare"], "need": V3_MIN_NIGHT_SHARE},
                "V4": {"pass": v4, "strataBelow": low, "need": V4_MIN_STRATUM_PASS}}}


def validation_node_proposal(result: dict, model_version: str = "lake-level-rules-v2") -> dict | None:
    """The /validation/lake-brain value section 8 would PROPOSE, in exactly LakeBrainRunner.ValidationSummary's shape; None = no change proposed.
    Never written by this runner."""
    if result["verdict"]["verdict"] != "PASS":
        return None
    s = result["summary"]
    return {
        "brainId": "lake-brain",
        "modelVersion": model_version,
        "validationVersion": f"{PROTOCOL} (prereg {PREREG_SHA256[:12]}, sample {SAMPLE_SHA256[:12]}, run {result['runAt'][:10]})",
        "status": "PARTIAL",
        "lastRunAt": result["runAt"],
        "holdoutType": ("pre-registered operator-truth comparison: 21 past nights (2026-11-03..23, 00:00 lake-local), stratified sample of "
                        f"{s['lakes']} accepted lakes; truth = the operator's other published series or another agency's series, never the "
                        "Brain's value series"),
        "sampleCount": s["lakeNights"],
        "lakeCount": s["scored"],
        "notes": [
            "Scope: current observed level (LB-04) only. Bands, trend labels, zones, flood state and outlooks are not validated by this.",
            f"{s['pass']} of {s['scored']} scored lakes PASS; {s['lakeNightsWithin']} of {s['lakeNights']} lake-nights within 0.5 ft; "
            f"{s['insufficient']} lakes had too few matched nights.",
            "Protocol docs/brains/LAKE_BRAIN_OPERATOR_TRUTH_PREREGISTRATION.md; result committed with the owner approval.",
        ],
    }


def run(sample: dict, get, include_report_only: bool, processes: int, now: dt.datetime) -> dict:
    def go(entries):
        with cf.ThreadPoolExecutor(max_workers=max(1, processes)) as ex:
            return sorted(ex.map(lambda e: evaluate_lake(e, get), entries), key=lambda x: x["lakeId"])
    lakes = go(sample["verdictSample"])
    summary = summarize(lakes)
    out = {"protocol": PROTOCOL, "preregCommit": PREREG_COMMIT, "preregSha256": PREREG_SHA256, "sampleSha256": SAMPLE_SHA256,
           "runAt": _z(now), "window": {"nights": [d.isoformat() for d in NIGHTS], "instant": "00:00 lake-local"},
           "lakes": lakes, "summary": summary, "verdict": verdict(summary)}
    if include_report_only:
        ro = go(sample["reportOnlySample"])
        out["reportOnly"] = {"lakes": ro, "summary": summarize(ro), "note": "NWS redistribution truth; never part of the verdict"}
    out["proposedValidationNode"] = validation_node_proposal(out)
    out["published"] = False
    return out


def write_outputs(result: dict, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    stamp = result["runAt"][:10]
    paths = []
    jp = os.path.join(out_dir, f"operator_truth_v1_{stamp}.json")
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
        fh.write("\n")
    paths.append(jp)
    cp = os.path.join(out_dir, f"operator_truth_v1_{stamp}_lakes.csv")
    cols = ["set", "lakeId", "stratum", "result", "n", "within", "shareWithin", "medAE", "meanE", "maxAE", "noBrainValue", "noTruthMatch",
            "truthClass", "truthKind", "truthCadence", "truthOffsetFt", "valueSeries", "truthSeries", "insufficientReason", "errors"]
    with open(cp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for label, lakes in (("verdict", result["lakes"]), ("reportOnly", (result.get("reportOnly") or {}).get("lakes") or [])):
            for x in lakes:
                w.writerow({**x, "set": label, "errors": " | ".join(x["errors"])})
    paths.append(cp)
    sp = os.path.join(out_dir, f"operator_truth_v1_{stamp}_summary.txt")
    with open(sp, "w", encoding="utf-8") as fh:
        fh.write(summary_text(result))
    paths.append(sp)
    return paths


def summary_text(result: dict) -> str:
    s, v = result["summary"], result["verdict"]
    c = v["criteria"]
    lines = [f"Lake operator-truth validation v1 (pre-registered {PREREG_COMMIT[:9]}, sha256 {PREREG_SHA256[:12]}): {v['verdict']}",
             f"Scored {s['scored']} of {s['lakes']} sample lakes: {s['pass']} PASS, {s['fail']} FAIL, {s['insufficient']} INSUFFICIENT.",
             f"V1 enough evidence {'PASS' if c['V1']['pass'] else 'FAIL'} ({c['V1']['scored']} scored, strata with >= 5: {', '.join(c['V1']['strataWith5Scored']) or 'none'})",
             f"V2 lakes PASS share {c['V2']['passShare']} (need >= {V2_MIN_PASS}) {'PASS' if c['V2']['pass'] else 'FAIL'}",
             f"V3 lake-nights within 0.5 ft {c['V3']['nightShare']} (need >= {V3_MIN_NIGHT_SHARE}) {'PASS' if c['V3']['pass'] else 'FAIL'}",
             f"V4 strata >= {V4_MIN_STRATUM_PASS} PASS {'PASS' if c['V4']['pass'] else 'FAIL (' + ', '.join(c['V4']['strataBelow']) + ')'}",
             "By stratum: " + "; ".join(f"{k} {g['pass']}/{g['scored']} (insufficient {g['insufficient']})" for k, g in s["byStratum"].items()),
             "By truth class: " + "; ".join(f"{k} {g['pass']}/{g['scored']}" for k, g in s["byTruthClass"].items())]
    fails = [x for x in result["lakes"] if x["result"] == "FAIL"]
    if fails:
        lines.append("FAIL lakes: " + "; ".join(f"{x['lakeId']} (medAE {x['medAE']} ft, {x['within']}/{x['n']} within 0.5, mean e {x['meanE']}, "
                                                 f"{x['truthClass']} {x['truthSeries']})" for x in fails))
    ins = [x for x in result["lakes"] if x["result"] == "INSUFFICIENT"]
    if ins:
        lines.append("INSUFFICIENT: " + "; ".join(f"{x['lakeId']} ({x.get('insufficientReason')}, n={x['n']})" for x in ins))
    if result.get("reportOnly"):
        r = result["reportOnly"]["summary"]
        lines.append(f"Report-only (NWS truth, not in the verdict): {r['pass']} PASS, {r['fail']} FAIL, {r['insufficient']} INSUFFICIENT of {r['lakes']}.")
    prop = result.get("proposedValidationNode")
    lines.append("Proposed /validation/lake-brain: " + ("status PARTIAL (NOT published; owner decision)" if prop else
                                                       "no change (stays NOT_VALIDATED)"))
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir")
    ap.add_argument("--include-report-only", action="store_true")
    ap.add_argument("--processes", type=int, default=4)
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args(argv)
    problems = verify_preregistration()
    with open(SAMPLE_PATH, encoding="utf-8") as fh:
        sample = json.load(fh)
    rebuilt = build_sample.dumps(build_sample.build(build_sample.load_generated(), build_sample.load_accepted()))
    with open(SAMPLE_PATH, encoding="utf-8") as fh:
        if fh.read() != rebuilt:
            problems.append("the frozen sample is not the sample rule's output on the current bindings (bindings changed since registration)")
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems))
        return 2
    if a.verify_only:
        print("pre-registration verified (protocol, sample, rule)")
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    if not in_run_window(now):
        print(f"REFUSED: {_z(now)} is outside the pre-registered run window {_z(RUN_START)} .. {_z(RUN_END)}")
        return 2
    if not a.out_dir:
        print("REFUSED: --out-dir is required")
        return 2
    result = run(sample, http_get, a.include_report_only, a.processes, now)
    for p in write_outputs(result, a.out_dir):
        print("wrote", p)
    print(summary_text(result), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
