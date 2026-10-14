#!/usr/bin/env python3
"""Read-only live-vs-history probe for the 14 history/live mismatch lakes (acceptance criteria: mismatch14_criteria.py).

    python3 jobs/lake-brain/bindings/mismatch14_probe.py [--lake "Detroit Lake|OR" ...] [--offline]

Fetches the LIVE series (and, for cross-checks, the history candidates) from the provider APIs, reduces every series to one value per UTC
calendar day (the day key the research history uses), and evaluates the pre-registered criteria O1-O4 / S1. Raw API bodies are cached outside
Git (LB_DATA/mismatch14/cache) so a re-run is offline and reproducible. Politeness: one request at a time, >= 1.5 s apart (IEM/HADS: 15 s),
a descriptive User-Agent (override the contact with SECTOR_CONTACT; none by default).

The probe never writes bindings. mismatch14_dispositions.json is hand-curated from its output (see build_dispositions in the generator).
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mismatch14_criteria as C  # noqa: E402

DATA = os.environ.get("LB_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
CACHE = os.path.join(DATA, "mismatch14", "cache")
UA = "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)" + (
    f"; contact {os.environ['SECTOR_CONTACT']}" if os.environ.get("SECTOR_CONTACT") else "")
RUN_DATE = dt.date.fromisoformat(C.RUN_DATE)


# --------------------------------------------------------------------------------------------------------------------------- pure
def percentile(xs: list[float], q: float) -> float:
    """Linear-interpolation percentile (numpy default), q in [0, 100]."""
    if not xs:
        raise ValueError("empty")
    s = sorted(xs)
    k = (len(s) - 1) * q / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def daily_median(points: list[tuple[int, float]]) -> dict[dt.date, float]:
    """[(epoch_ms_utc, value)] -> {UTC date: median}. Non-finite and None values are dropped."""
    by: dict[dt.date, list[float]] = {}
    for ms, v in points:
        if v is None or not math.isfinite(v):
            continue
        d = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()
        by.setdefault(d, []).append(v)
    return {d: statistics.median(vs) for d, vs in by.items()}


def window_for(hist: dict[dt.date, float], run_date: dt.date = RUN_DATE, days: int = C.WINDOW_DAYS) -> tuple[dt.date, dt.date] | None:
    """The WINDOW_DAYS days that end at the history's last day (capped at the run date)."""
    if not hist:
        return None
    end = min(max(hist), run_date)
    return end - dt.timedelta(days=days - 1), end


def evaluate_overlap(live: dict[dt.date, float], hist: dict[dt.date, float], window: tuple[dt.date, dt.date] | None) -> dict:
    """O1-O3 on the matched days inside the window. Returns the statistics and the per-criterion booleans."""
    if window is None:
        return {"matchedDays": 0, "O1": False, "O2": False, "O3": False, "reason": "no history"}
    lo, hi = window
    diffs = [live[d] - hist[d] for d in sorted(set(live) & set(hist)) if lo <= d <= hi]
    out: dict = {"window": [lo.isoformat(), hi.isoformat()], "matchedDays": len(diffs)}
    if not diffs:
        out.update(O1=False, O2=False, O3=False, reason="no matched days")
        return out
    ab = [abs(x) for x in diffs]
    out.update(medianAbsFt=round(statistics.median(ab), 3), p95AbsFt=round(percentile(ab, 95), 3), maxAbsFt=round(max(ab), 3),
               medianSignedFt=round(statistics.median(diffs), 3))
    out["O1"] = len(diffs) >= C.MIN_MATCHED_DAYS
    out["O2"] = out["medianAbsFt"] <= C.MEDIAN_ABS_FT
    out["O3"] = out["p95AbsFt"] <= C.P95_ABS_FT
    return out


def evaluate_short(live: dict[dt.date, float], record: dict[dt.date, float]) -> dict:
    """S1(a): a short live feed against the record-holding read of the same series, every day both exist."""
    diffs = [abs(live[d] - record[d]) for d in sorted(set(live) & set(record))]
    out = {"matchedDays": len(diffs)}
    if not diffs:
        out["S1a"] = False
        return out
    out.update(medianAbsFt=round(statistics.median(diffs), 3), maxAbsFt=round(max(diffs), 3))
    out["S1a"] = len(diffs) >= C.SHORT_MIN_DAYS and out["medianAbsFt"] <= C.SHORT_MEDIAN_FT and out["maxAbsFt"] <= C.SHORT_MAX_FT
    return out


def evaluate_recency(hist: dict[dt.date, float], run_date: dt.date = RUN_DATE) -> dict:
    if not hist:
        return {"O4": False, "historyLast": None, "staleDays": None}
    last = max(hist)
    stale = (run_date - last).days
    return {"O4": stale <= C.HISTORY_MAX_STALE_DAYS, "historyLast": last.isoformat(), "staleDays": stale}


def plausibility(live: dict[dt.date, float], window: tuple[dt.date, dt.date] | None, lo_ft: float | None, hi_ft: float | None) -> dict:
    """P2: the live values in the window lie inside [lo - tol, hi + tol] of the operator's documented range."""
    if window is None or lo_ft is None or hi_ft is None:
        return {"P2": None, "reason": "operator range not documented"}
    vals = [v for d, v in live.items() if window[0] <= d <= window[1]]
    if not vals:
        return {"P2": False, "reason": "no live values in window"}
    ok = min(vals) >= lo_ft - C.POOL_TOL_FT and max(vals) <= hi_ft + C.POOL_TOL_FT
    return {"P2": ok, "liveMinFt": round(min(vals), 2), "liveMaxFt": round(max(vals), 2), "operatorRangeFt": [lo_ft, hi_ft]}


def value_range(series: dict[dt.date, float], window: tuple[dt.date, dt.date] | None) -> dict:
    vals = [v for d, v in series.items() if window and window[0] <= d <= window[1]]
    return {"n": len(vals), "min": round(min(vals), 2), "max": round(max(vals), 2)} if vals else {"n": 0}


def qa_reproduction(live: dict[dt.date, float]) -> dict:
    """The hold-out QA statistic computed on the LIVE series alone: median since 2025-01-01 vs median of its last 30 days. If this 'mismatch' appears
    inside one and the same series it is seasonality / drawdown, not a series or datum error."""
    since = [v for d, v in live.items() if d >= dt.date(2025, 1, 1)]
    last = sorted(live)[-30:]
    if not since or not last:
        return {}
    a, b = statistics.median(since), statistics.median(live[d] for d in last)
    return {"liveMedianSince2025": round(a, 2), "liveMedianLast30d": round(b, 2), "diffFt": round(b - a, 1)}


def read_daily_file(path: str) -> dict[dt.date, float]:
    """date,value[,..] csv(.gz) -> {date: ft}; the research convention drops v <= 1.0 (RISE placeholders)."""
    out: dict[dt.date, float] = {}
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as fh:
        for line in fh:
            parts = line.strip().split(",")
            if len(parts) < 2 or not parts[1]:
                continue
            try:
                d, v = dt.date.fromisoformat(parts[0][:10]), float(parts[1])
            except ValueError:
                continue
            if v > 1.0:
                out[d] = v
    return out


# --------------------------------------------------------------------------------------------------------------------------- http
class Http:
    def __init__(self, offline: bool = False, gap: float = 1.5):
        self.offline, self.gap, self._last = offline, gap, 0.0
        os.makedirs(CACHE, exist_ok=True)

    def get(self, url: str, accept: str = "application/json", gap: float | None = None, timeout: int = 120) -> bytes | None:
        key = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest()[:40] + ".bin")
        if os.path.exists(key):
            return open(key, "rb").read()
        if self.offline:
            return None
        wait = (gap if gap is not None else self.gap) - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            self._last = time.time()
            if e.code in (404, 400):
                body = f"HTTPERROR {e.code}".encode()
            else:
                print(f"  HTTP {e.code} {url[:120]}", file=sys.stderr)
                return None
        except Exception as e:  # noqa: BLE001 - network failures are reported, never fatal
            print(f"  fetch failed {type(e).__name__}: {url[:120]}", file=sys.stderr)
            return None
        self._last = time.time()
        with open(key, "wb") as f:
            f.write(body)
        return body


# --------------------------------------------------------------------------------------------------------------------------- fetchers
def fetch_rise(h: Http, item: str, after: str) -> dict[dt.date, float] | None:
    out: dict[dt.date, float] = {}
    page = 1
    while page < 80:
        q = f"https://data.usbr.gov/rise/api/result?itemId={item}&dateTime%5Bafter%5D={after}&itemsPerPage=2000&page={page}"
        body = h.get(q, accept="application/vnd.api+json", timeout=90)
        if body is None or body.startswith(b"HTTPERROR"):
            return None if page == 1 else out
        obj = json.loads(body)
        for it in obj.get("data", []):
            a = it.get("attributes", {})
            v, t = a.get("result"), a.get("dateTime")
            if v is None or t is None or not isinstance(v, (int, float)) or v <= 0:
                continue
            ra = a.get("resultAttributes") or {}
            if isinstance(ra, dict) and ra.get("resultType") not in (None, "observed"):
                continue
            out[dt.date.fromisoformat(t[:10])] = float(v)
        if not (obj.get("links") or {}).get("next"):
            break
        page += 1
    return out


def fetch_cwms(h: Http, office: str, name: str, begin: dt.date, end: dt.date) -> dict[dt.date, float] | None:
    pts: list[tuple[int, float]] = []
    page = None
    for _ in range(60):
        q = {"office": office, "name": name, "unit": "EN", "begin": f"{begin}T00:00:00Z", "end": f"{end}T23:59:59Z", "page-size": "5000"}
        if page:
            q["page"] = page
        body = h.get("https://cwms-data.usace.army.mil/cwms-data/timeseries?" + urllib.parse.urlencode(q), accept="application/json;version=2")
        if body is None or body.startswith(b"HTTPERROR"):
            return None if not pts else daily_median(pts)
        obj = json.loads(body)
        k = 3.28084 if str(obj.get("units", "ft")).lower() == "m" else 1.0
        pts += [(r[0], r[1] * k) for r in obj.get("values", []) if len(r) >= 2 and r[1] is not None]
        page = obj.get("next-page")
        if not page:
            break
    return daily_median(pts)


def fetch_usgs_iv(h: Http, site: str, param: str, begin: dt.date, end: dt.date) -> dict[dt.date, float] | None:
    pts: list[tuple[int, float]] = []
    y0 = begin
    while y0 <= end:
        y1 = min(end, dt.date(y0.year, 12, 31))
        url = (f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={param}&startDT={y0}&endDT={y1}&siteStatus=all")
        body = h.get(url)
        if body is None:
            return None
        if not body.startswith(b"HTTPERROR"):
            for s in json.loads(body).get("value", {}).get("timeSeries", []):
                for blk in s.get("values", []):
                    for v in blk.get("value", []):
                        try:
                            t = dt.datetime.fromisoformat(v["dateTime"]).astimezone(dt.timezone.utc)
                            x = float(v["value"])
                        except (KeyError, ValueError):
                            continue
                        if x > -990000:
                            pts.append((int(t.timestamp() * 1000), x))
        y0 = y1 + dt.timedelta(days=1)
    return daily_median(pts)


def fetch_usgs_dv(h: Http, site: str, param: str, begin: dt.date, end: dt.date) -> dict[dt.date, float] | None:
    url = f"https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}&parameterCd={param}&startDT={begin}&endDT={end}&siteStatus=all"
    body = h.get(url)
    if body is None:
        return None
    out: dict[dt.date, float] = {}
    if body.startswith(b"HTTPERROR"):
        return out
    best: dict[str, dict[dt.date, float]] = {}
    for s in json.loads(body).get("value", {}).get("timeSeries", []):
        stat = (((s.get("variable") or {}).get("options") or {}).get("option") or [{}])[0].get("optionCode", "?")
        for blk in s.get("values", []):
            for v in blk.get("value", []):
                try:
                    x = float(v["value"])
                except (KeyError, ValueError):
                    continue
                if x > -990000:
                    best.setdefault(stat, {})[dt.date.fromisoformat(v["dateTime"][:10])] = x
    for stat in ["00003", "32400", "30800", "00001", "00002"] + sorted(best):
        for d, x in best.get(stat, {}).items():
            out.setdefault(d, x)
    return out


def fetch_nwps(h: Http, lid: str) -> dict[dt.date, float] | None:
    body = h.get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow/observed", timeout=60)
    if body is None or body.startswith(b"HTTPERROR"):
        return None
    obj = json.loads(body)
    pts = []
    for r in obj.get("data", []):
        v, t = r.get("primary"), r.get("validTime")
        if v is None or t is None or v <= -990:
            continue
        pts.append((int(dt.datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp() * 1000), float(v)))
    return daily_median(pts)


def fetch_hads(h: Http, lid: str, pe_prefix: str, begin: dt.date, end: dt.date) -> dict[dt.date, float] | None:
    """IEM HADS archive, 3-year chunks, 15 s apart (the research and Swift convention). First non-empty PE?IR* column per row."""
    out: dict[dt.date, float] = {}
    pts: list[tuple[int, float]] = []
    y = end.year
    while y >= begin.year:
        lo = max(begin.year, y - 2)
        sts = f"{lo}-01-01T00:00Z"
        ets = f"{y + 1}-01-01T00:00Z" if y < end.year else f"{end}T23:59Z"
        url = f"https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations={lid}&sts={sts}&ets={ets}&what=txt&delim=comma"
        body = h.get(url, accept="text/plain", gap=15, timeout=300)
        if body is None:
            return None
        lines = body.decode("utf-8", "replace").splitlines()
        if lines:
            cols = lines[0].split(",")
            if "utc_valid" in cols:
                ti = cols.index("utc_valid")
                vi = [i for i, c in enumerate(cols) if c.startswith(pe_prefix)]
                for ln in lines[1:]:
                    c = ln.split(",")
                    try:
                        t = dt.datetime.strptime(c[ti], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
                    except (ValueError, IndexError):
                        continue
                    for i in vi:
                        if i < len(c):
                            try:
                                x = float(c[i])
                            except ValueError:
                                continue
                            if x > -990:
                                pts.append((int(t.timestamp() * 1000), x))
                                break
        y = lo - 1
    out = daily_median(pts)
    return out


# --------------------------------------------------------------------------------------------------------------------------- spec
def norm(x: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9.\-]+", "_", x)


def hist_file_for(src: dict) -> str | None:
    """Cached history file of a generator history component (read-only research cache)."""
    k = src["kind"]
    if k == "riseDaily":
        return os.path.join(DATA, "binding", "history", f"rise_{src['item']}.csv.gz")
    if k == "cwmsDaily":
        return os.path.join(DATA, "binding", "history", f"cwms_{src['office']}_{norm(src['series'].replace('~', '_'))}.csv.gz")
    if k == "usgsDaily" and src["stat"] == "iv":
        return os.path.join(DATA, "binding2", "history", f"usgsiv_{src['site']}_{src['param']}.csv.gz")
    if k == "usgsDaily":
        return os.path.join(DATA, "binding", "history", f"usgs_{src['site']}_{src['param']}.csv.gz")
    if k == "hadsDaily":
        return os.path.join(DATA, "binding2", "history", f"hads_{src['lid']}_{src['pe']}IRG.csv.gz")
    return None


def a2w_tie(h: Http, district: str, code: str, tsid: str, cda_office: str) -> dict:
    """One-point tie of an Access2Water series (latest value only) to the CWMS CDA read of the SAME tsid at the same timestamp."""
    body = h.get(f"https://water.usace.army.mil/cda/reporting/providers/{district.lower()}/locations", timeout=90)
    if not body or body.startswith(b"HTTPERROR"):
        return {"error": "A2W listing unavailable"}
    loc = next((x for x in json.loads(body) if x.get("code") == code), None)
    ts = next((t for t in (loc or {}).get("timeseries", []) if t.get("tsid") == tsid), None)
    if not ts:
        return {"error": f"{tsid} not listed at {district}:{code}"}
    t = dt.datetime.fromisoformat(ts["latest_time"].replace("Z", "+00:00"))
    q = {"office": cda_office, "name": tsid, "unit": "EN", "begin": (t - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "end": (t + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    b2 = h.get("https://cwms-data.usace.army.mil/cwms-data/timeseries?" + urllib.parse.urlencode(q), accept="application/json;version=2")
    if not b2 or b2.startswith(b"HTTPERROR"):
        return {"a2wTime": ts["latest_time"], "a2wValueFt": ts["latest_value"], "error": "CDA read unavailable"}
    vals = {r[0]: r[1] for r in json.loads(b2).get("values", []) if r[1] is not None}
    ms = int(t.timestamp() * 1000)
    near = min(vals, key=lambda k: abs(k - ms)) if vals else None
    return {"a2wTime": ts["latest_time"], "a2wValueFt": ts["latest_value"], "cdaOffsetMin": None if near is None else round((near - ms) / 60000),
            "cdaValueFt": None if near is None else round(vals[near], 3),
            "diffFt": None if near is None else round(ts["latest_value"] - vals[near], 3), "matchedPoints": 1 if near is not None else 0}


def fetch_series(h: Http, spec: dict, begin: dt.date, end: dt.date) -> dict[dt.date, float] | None:
    k = spec["kind"]
    if k == "rise":
        return fetch_rise(h, spec["item"], begin.isoformat())
    if k == "cwms":
        return fetch_cwms(h, spec["office"], spec["name"], begin, end)
    if k == "usgsiv":
        return fetch_usgs_iv(h, spec["site"], spec["param"], begin, end)
    if k == "usgsdv":
        return fetch_usgs_dv(h, spec["site"], spec["param"], begin, end)
    if k == "nwps":
        return fetch_nwps(h, spec["lid"])
    if k == "hads":
        return fetch_hads(h, spec["lid"], spec["pe"], begin, end)
    raise ValueError(k)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=os.path.join(HERE, "mismatch14_specs.json"), help="per-lake probe plan (live / history candidates)")
    ap.add_argument("--lake", action="append")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out", default=os.path.join(DATA, "mismatch14", "probe_results.json"))
    args = ap.parse_args(argv)
    specs = json.load(open(args.specs))
    h = Http(offline=args.offline)
    results = {}
    for lake, sp in specs["lakes"].items():
        if args.lake and lake not in args.lake:
            continue
        res = {"lake": lake, "tests": []}
        for t in sp["tests"]:
            live_spec, hist_spec = t["live"], t["history"]
            hf = None
            hist: dict[dt.date, float] | None
            if hist_spec.get("file"):
                hf = os.path.join(DATA, hist_spec["file"])
                hist = read_daily_file(hf) if os.path.exists(hf) else None
            else:
                hist = fetch_series(h, hist_spec, RUN_DATE - dt.timedelta(days=C.WINDOW_DAYS * 2), RUN_DATE)
            if not hist:
                res["tests"].append({"id": t["id"], "error": "history unavailable"})
                continue
            win = window_for(hist)
            live = fetch_series(h, live_spec, win[0], win[1])
            rec = {"id": t["id"], "label": t.get("label"), "live": live_spec, "history": hist_spec,
                   "historyDays": len(hist), "historyFirst": min(hist).isoformat(), **evaluate_recency(hist)}
            if live is None:
                rec["error"] = "live unavailable"
            else:
                rec["liveDays"] = len(live)
                rec["liveRange"] = [min(live).isoformat(), max(live).isoformat()] if live else None
                rec["overlap"] = evaluate_overlap(live, hist, win)
                rec["qaReproduction"] = qa_reproduction(live)
                rec["liveWindowRange"] = value_range(live, win)
                rec["historyWindowRange"] = value_range(hist, win)
                rec["lastDays"] = {d.isoformat(): round(live[d], 2) for d in sorted(live)[-3:]}
            if t.get("short"):
                sl = fetch_series(h, t["short"]["live"], RUN_DATE - dt.timedelta(days=40), RUN_DATE)
                sr = fetch_series(h, t["short"]["record"], RUN_DATE - dt.timedelta(days=40), RUN_DATE)
                rec["s1a"] = evaluate_short(sl or {}, sr or {}) if sl is not None and sr is not None else {"S1a": False, "error": "short feed or record unavailable"}
            if t.get("a2w"):
                a = t["a2w"]
                rec["a2wTie"] = a2w_tie(h, a["district"], a["code"], a["tsid"], a["cdaOffice"])
            res["tests"].append(rec)
            ov = rec.get("overlap", {})
            print(f"{lake:28} {t['id']:22} n={ov.get('matchedDays')} med={ov.get('medianAbsFt')} p95={ov.get('p95AbsFt')} "
                  f"max={ov.get('maxAbsFt')} signed={ov.get('medianSignedFt')} hist_last={rec.get('historyLast')}")
        results[lake] = res
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"criteriaVersion": C.CRITERIA_VERSION, "runDate": C.RUN_DATE, "results": results}, open(args.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
