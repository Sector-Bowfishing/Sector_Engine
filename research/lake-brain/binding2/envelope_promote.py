"""Rule v1.1-R7h (history envelope): a FLAGGED lake (R7 drawdown/weak class) is promoted to core when the bound series' own daily history (>= 5 complete years)
reaches the directory full pool: the 99th percentile of daily values over complete years within [-8,+8] ft of fullPoolFt (strong identity already required by the flag),
because a series from a different pool or a local-datum stage cannot reach the lake's full-pool elevation. This is NOT a second origin; it is reported separately
('promoted by envelope') and never mixed into the v1 counts. Output: binding2/envelope.json"""
import csv, gzip, json, os, re, statistics
from common2 import *
from providers import _safe, HIST
B2_ = os.path.join(DATA, 'binding2')

def hist_file(label):
    p = label.split(":")
    if p[0] == "usgs":
        return f"{BIND}/history/usgs_{p[1]}_{p[2]}.csv.gz"
    if p[0] == "cwms":
        return f"{BIND}/history/cwms_{p[1]}_{_safe(':'.join(p[2:]))}.csv.gz"
    if p[0] == "rise":
        return f"{BIND}/history/rise_{p[1]}.csv.gz"
    if p[0] == "b2":
        return f"{B2_}/history/{label[3:]}"
    if p[0] == "hads":
        return f"{B2_}/history/hads_{p[1]}_{p[2]}.csv.gz"
    if p[0] == "usgsiv":
        return f"{B2_}/history/usgsiv_{p[1]}_{p[2]}.csv.gz"
    if p[0] == "coops":
        return f"{B2_}/history/coops_{p[1]}_daily_mean.csv.gz"
    if p[0] == "twdb":
        return f"{BIND}/history/twdb_{_safe(p[1])}.csv.gz"
    return None

def load(path):
    if not path or not os.path.exists(path):
        return None
    return {r[0]: float(r[1]) for r in csv.reader(gzip.open(path, "rt")) if r}

def envelope(daily, fp):
    by = {}
    for k, v in daily.items():
        by.setdefault(k[:4], []).append(v)
    yrs = [y for y, v in by.items() if len(v) >= 329 and int(y) < 2026]
    vals = [v for y in yrs for v in by[y]]
    if len(yrs) < 5:
        return None
    vals.sort()
    q = lambda p: vals[int(p * (len(vals) - 1))]
    return dict(years=len(yrs), p50=round(q(.5), 2), p95=round(q(.95), 2), p99=round(q(.99), 2), mx=round(vals[-1], 2), d99=round(q(.99) - fp, 2), dmax=round(vals[-1] - fp, 2))

if __name__ == "__main__":
    ver = [r for r in csv.DictReader(open(f"{BIND}/verified.csv")) if r["bindingStatus"] == "VERIFIED_FLAG"]
    out = {}
    for r in ver:
        fp = float(r["fullPoolFt"]) if r["fullPoolFt"] else None
        d = load(hist_file(r["histSeries"]))
        e = envelope(d, fp) if d and fp else None
        promote = bool(e and -8 <= e["d99"] <= 8)
        out[r["lakeId"]] = dict(provider=r["provider"], histSeries=r["histSeries"], fullPool=fp, med=r["medFt"], env=e, promote=promote, basis=r["poolBasis"])
        print(f"{r['lakeId'][:30]:30} {r['provider']:5} fp={fp} med={r['medFt']} env={e} -> {'PROMOTE' if promote else '-'}")
    json.dump(out, open(f"{B2}/envelope.json", "w"), indent=1)
    print("flagged with >=5y history:", sum(1 for v in out.values() if v["env"]), "promote:", sum(1 for v in out.values() if v["promote"]))
