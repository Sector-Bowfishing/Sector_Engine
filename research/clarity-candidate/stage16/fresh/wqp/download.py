#!/opt/homebrew/bin/python3.13
"""Download Secchi + turbidity results and stations from the Water Quality Portal.

Re-runnable: a job whose raw/<name>.meta.json says ok=true is skipped.
Every download is verified against the Total-Result-Count / Total-Site-Count
header WQP returns; a mismatch, HTTP error or timeout is retried, then the job
is split by calendar year.

Usage: download.py [--workers N] [--only secchi|turb|comp] [--states AL,TN]
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
LOG = os.path.join(HERE, "download.log")
BASE = "https://www.waterqualitydata.us/data"
SITE_TYPE = "Lake, Reservoir, Impoundment"
START = "01-01-2026"   # Stage 16 fresh pull (the only change)
FIRST_YEAR = 2026
LAST_YEAR = dt.date.today().year

STATES = [
    ("01", "AL"), ("02", "AK"), ("04", "AZ"), ("05", "AR"), ("06", "CA"),
    ("08", "CO"), ("09", "CT"), ("10", "DE"), ("11", "DC"), ("12", "FL"),
    ("13", "GA"), ("15", "HI"), ("16", "ID"), ("17", "IL"), ("18", "IN"),
    ("19", "IA"), ("20", "KS"), ("21", "KY"), ("22", "LA"), ("23", "ME"),
    ("24", "MD"), ("25", "MA"), ("26", "MI"), ("27", "MN"), ("28", "MS"),
    ("29", "MO"), ("30", "MT"), ("31", "NE"), ("32", "NV"), ("33", "NH"),
    ("34", "NJ"), ("35", "NM"), ("36", "NY"), ("37", "NC"), ("38", "ND"),
    ("39", "OH"), ("40", "OK"), ("41", "OR"), ("42", "PA"), ("44", "RI"),
    ("45", "SC"), ("46", "SD"), ("47", "TN"), ("48", "TX"), ("49", "UT"),
    ("50", "VT"), ("51", "VA"), ("53", "WA"), ("54", "WV"), ("55", "WI"),
    ("56", "WY"),
]

SECCHI = "Depth, Secchi disk depth"
TURB = "Turbidity"
# Companion characteristics used only to flag bottom-visible Secchi readings
# (joined on ActivityIdentifier). Small enough to pull nationwide in one go.
COMPANIONS = {
    "comp_secchi_bottom_yn": "Depth, Secchi disk visible at bottom (Y/N) (choice list)",
    "comp_secchi_choice": "Depth, Secchi disk depth (choice list)",
    "comp_secchi_condition": "Secchi Reading Condition (choice list)",
    "comp_lake_clear_bottom": "Lake Clear to Bottom",
    "comp_depth_bottom": "Depth, bottom",
    "comp_water_transparency": "Water transparency, Secchi disc",
}

_log_lock = threading.Lock()


def log(msg):
    line = f"{dt.datetime.now().strftime('%H:%M:%S')} {msg}"
    with _log_lock:
        print(line, flush=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")


def build_url(endpoint, params):
    q = "&".join(f"{k}={urllib.parse.quote(str(v), safe=',()/:')}" for k, v in params.items())
    return f"{BASE}/{endpoint}/search?{q}"


def base_params(characteristic, state=None, lo=START, hi=None, profile=None):
    p = {}
    if state:
        p["statecode"] = f"US:{state}"
    else:
        p["countrycode"] = "US"
    p["siteType"] = SITE_TYPE
    p["characteristicName"] = characteristic
    p["startDateLo"] = lo
    if hi:
        p["startDateHi"] = hi
    p["mimeType"] = "csv"
    p["zip"] = "no"
    if profile:
        p["dataProfile"] = profile
    return p


def fetch(url, dest, timeout=900):
    """Stream url to dest. Returns (headers_dict, bytes, rows)."""
    req = urllib.request.Request(url, headers={"User-Agent": "wqp-secchi-groundtruth/1.0 (research; python-urllib)"})
    tmp = dest + ".part"
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        hdrs = {k: v for k, v in resp.headers.items() if "count" in k.lower() or k.lower() in ("warning", "content-type")}
        n = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                n += len(chunk)
    with open(tmp, newline="", encoding="utf-8", errors="replace") as f:
        rows = sum(1 for _ in csv.reader(f)) - 1
    rows = max(rows, 0)
    os.replace(tmp, dest)
    return hdrs, n, rows, time.time() - t0


def expected_count(endpoint, hdrs):
    key = "Total-Result-Count" if endpoint == "Result" else "Total-Site-Count"
    for k, v in hdrs.items():
        if k.lower() == key.lower():
            try:
                return int(v)
            except ValueError:
                return None
    return None


def run_one(name, endpoint, params, attempts=3):
    """Fetch one URL with retries. Returns meta dict (ok True/False)."""
    dest = os.path.join(RAW, name + ".csv")
    url = build_url(endpoint, params)
    last_err = None
    for a in range(1, attempts + 1):
        try:
            hdrs, nbytes, rows, secs = fetch(url, dest)
            exp = expected_count(endpoint, hdrs)
            # WQP omits the count headers when the answer is zero rows.
            ok = (exp is None and rows == 0) or (exp == rows)
            meta = dict(name=name, endpoint=endpoint, url=url, headers=hdrs, bytes=nbytes,
                        rows=rows, expected=exp, ok=ok, seconds=round(secs, 1), attempt=a,
                        fetched=dt.datetime.now().isoformat(timespec="seconds"))
            if ok:
                return meta
            last_err = f"row mismatch: got {rows}, header says {exp}"
            log(f"  {name}: {last_err} (attempt {a})")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read(300).decode("utf-8", "replace")
            except Exception:
                pass
            last_err = f"HTTP {e.code} {body!r}"
            log(f"  {name}: {last_err} (attempt {a})")
        except Exception as e:  # timeouts, resets, incomplete reads
            last_err = f"{type(e).__name__}: {e}"
            log(f"  {name}: {last_err} (attempt {a})")
        time.sleep(10 * a)
    return dict(name=name, endpoint=endpoint, url=url, ok=False, error=last_err,
                fetched=dt.datetime.now().isoformat(timespec="seconds"))


def meta_path(name):
    return os.path.join(RAW, name + ".meta.json")


def done(name):
    try:
        with open(meta_path(name)) as f:
            return json.load(f).get("ok", False)
    except Exception:
        return False


def write_meta(meta):
    with open(meta_path(meta["name"]), "w") as f:
        json.dump(meta, f, indent=1)


def job(name, endpoint, characteristic, state, profile):
    if done(name):
        log(f"skip {name} (already ok)")
        return name, True
    t0 = time.time()
    prev = {}
    if os.path.exists(meta_path(name)):
        with open(meta_path(name)) as f:
            prev = json.load(f)
    if prev.get("split_by_year"):
        # Already known to need splitting: go straight to the (unfinished) year parts.
        meta = dict(ok=False, error=prev.get("first_error"))
    else:
        meta = run_one(name, endpoint, base_params(characteristic, state, profile=profile))
    if meta["ok"]:
        write_meta(meta)
        log(f"ok   {name}: {meta['rows']} rows, {meta['bytes']/1e6:.1f} MB, {meta['seconds']}s")
        return name, True
    # Fall back to one request per calendar year.
    log(f"split {name} by year after: {meta.get('error')}")
    parts, all_ok = [], True
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        pname = f"{name}_{y}"
        if done(pname):
            with open(meta_path(pname)) as f:
                parts.append(json.load(f))
            continue
        pm = run_one(pname, endpoint, base_params(characteristic, state, lo=f"01-01-{y}", hi=f"12-31-{y}", profile=profile))
        write_meta(pm)
        parts.append(pm)
        all_ok &= pm["ok"]
        log(f"  {'ok  ' if pm['ok'] else 'FAIL'} {pname}: {pm.get('rows')} rows")
    # The un-split file (if any) is stale/partial; remove so it is never read.
    stale = os.path.join(RAW, name + ".csv")
    if os.path.exists(stale):
        os.remove(stale)
    summary = dict(name=name, endpoint=endpoint, ok=all_ok, split_by_year=True,
                   parts=[p["name"] for p in parts], rows=sum(p.get("rows") or 0 for p in parts),
                   failed_parts=[p["name"] for p in parts if not p["ok"]],
                   first_error=meta.get("error"), seconds=round(time.time() - t0, 1),
                   fetched=dt.datetime.now().isoformat(timespec="seconds"))
    write_meta(summary)
    log(f"{'ok  ' if all_ok else 'FAIL'} {name} (split): {summary['rows']} rows")
    return name, all_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--only", choices=["secchi", "turb", "comp"], action="append")
    ap.add_argument("--states")
    args = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    only = set(args.only or ["secchi", "turb", "comp"])
    states = STATES
    if args.states:
        want = set(args.states.upper().split(","))
        states = [s for s in STATES if s[1] in want]

    jobs = []
    if "comp" in only:
        for name, ch in COMPANIONS.items():
            jobs.append((name, "Result", ch, None, "resultPhysChem"))
    for fips, ab in states:
        if "secchi" in only:
            jobs.append((f"secchi_result_{ab}", "Result", SECCHI, fips, "resultPhysChem"))
            jobs.append((f"secchi_station_{ab}", "Station", SECCHI, fips, None))
        if "turb" in only:
            jobs.append((f"turb_result_{ab}", "Result", TURB, fips, "resultPhysChem"))
            jobs.append((f"turb_station_{ab}", "Station", TURB, fips, None))

    log(f"start: {len(jobs)} jobs, {args.workers} workers")
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(job, *j) for j in jobs]
        for fu in as_completed(futs):
            try:
                name, ok = fu.result()
                if not ok:
                    failed.append(name)
            except Exception as e:
                log(f"worker crashed: {e!r}")
                failed.append("?")
    log(f"finished; failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
