"""Shared helpers for the `plan` thread (history extension + operator plan evidence). Read-only, polite."""
import csv, gzip, json, os, time, urllib.request, urllib.parse, datetime as dt, collections

DATA = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain")
PLAN = f"{DATA}/plan"
REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine")
DOCS_DATA = f"{REPO}/docs/research/lake-brain/data"
UA = "SectorResearch/1.0 (lake-brain plan research; mgcather07@gmail.com)"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def get(url, accept="application/json", timeout=120, retries=3, ua=UA, sleep=0.0, raw=False):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
            if sleep: time.sleep(sleep)
            return b if raw else b.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 404): raise
            time.sleep(2 * (i + 1))
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last

def verified():
    return list(csv.DictReader(open(f"{DATA}/binding/verified.csv")))

def bound(rows=None, flagged=True):
    rows = rows or verified()
    ok = {"VERIFIED", "VERIFIED_CORROBORATED"} | ({"VERIFIED_FLAG"} if flagged else set())
    return [r for r in rows if r["bindingStatus"] in ok]

def write_daily(path, series):
    """series: dict date(str)->value. gz csv date,value"""
    with gzip.open(path, "wt") as f:
        f.write("date,value\n")
        for d in sorted(series): f.write(f"{d},{series[d]}\n")

def read_daily(path):
    out = {}
    with gzip.open(path, "rt") as f:
        next(f)
        for ln in f:
            d, v = ln.strip().split(",")[:2]
            if v != "": out[d] = float(v)
    return out

def complete_years(series, min_days=329, exclude_current=True):
    by = collections.Counter(d[:4] for d in series)
    cur = dt.date.today().year
    ys = sorted(int(y) for y, n in by.items() if n >= min_days and (not exclude_current or int(y) < cur))
    return ys
