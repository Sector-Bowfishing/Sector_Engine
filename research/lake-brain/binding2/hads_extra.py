"""HADS history for NWPS gauges that appeared in wave-2 candidates (Catawba chain local stage, Gaston, Smith Mountain, Thurmond, Youghiogheny, Liberty, McConaughy, Minnetonka, Poinsett).
Runs after hads_history.py (sequential, polite). Output: history/hads_<ID>_<element>.csv.gz and hads_probe_extra.json"""
import csv, glob, gzip, io, json, os, collections
from common2 import *
import sys
WANT = set(sys.argv[1:]) or {"CWAN7", "FOMS1", "WATS1", "KEOS1", "JCSS1", "BRWN7", "OXFN7", "GASN7", "SMIV2", "CHDS1", "YGBP1", "MFEM2", "KNGN1", "MTKM5", "PONS2", "LNZM7", "MLBK1"}
st = {}
for p in glob.glob(f"{B2}/cand/*.jsonl"):
    for l in open(p):
        r = json.loads(l)
        if r["prov"] == "nwps" and r["station"] in WANT:
            st[r["station"]] = (r["series"], r["lakeId"])
probe = {}
for sid, (el, lake) in sorted(st.items()):
    yrs = []
    for y in (2012, 2016, 2019, 2022):
        s, b = http_get(f"https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations={sid}&sts={y}-01-01T00:00Z&ets={y}-01-04T00:00Z&what=txt&delim=comma&tz=UTC", timeout=60, sleep=0.5, retries=2)
        if s == 200 and not b.startswith("Error") and len(b.splitlines()) > 2:
            yrs.append(y)
    probe[sid] = dict(lakeId=lake, element=el, yearsWithData=yrs, firstYear=min(yrs) if yrs else None)
    print(sid, lake, yrs, flush=True)
    if not yrs and not os.environ.get("FORCE"):
        continue
    yrs = yrs or [2012]
    out = f"{B2}/history/hads_{sid}_{el}.csv.gz"
    if os.path.exists(out):
        continue
    daily = collections.defaultdict(list)
    for y in range(max(2008, min(yrs) - 3), 2026):
        s, b = http_get(f"https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations={sid}&sts={y}-01-01T00:00Z&ets={y+1}-01-01T00:00Z&what=txt&delim=comma&tz=UTC", timeout=180, sleep=1.0, retries=2)
        if s != 200 or b.startswith("Error"):
            continue
        rd = csv.DictReader(io.StringIO(b)); rows = list(rd)
        cols = [c for c in (rd.fieldnames or []) if c.startswith(el[:5])] or [c for c in (rd.fieldnames or []) if c[:2] in ("HP", "HG")]
        best = max(cols, key=lambda c: sum(1 for r in rows if r.get(c) not in (None, "", "M")), default=None)
        for r in rows:
            try:
                x = float(r[best])
            except Exception:
                continue
            if x > -900:
                daily[r["utc_valid"][:10]].append(x)
    series = {k: sum(v) / len(v) for k, v in daily.items() if len(v) >= 1}
    with gzip.open(out, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(series):
            w.writerow([k, round(series[k], 3)])
    print("  ", sid, len(series), "days", flush=True)
json.dump(probe, open(f"{B2}/hads_probe_extra.json", "w"), indent=1)
