"""Stage 14 cert, step 1 (value-blind): every site id and coordinate that appears in any Current Clarity development
file (Stages 1-13), plus the Stage 12/13 blind-sample sites. Reads only id/lat/lon columns. Writes dev_footprint.json."""
import csv, json, glob, os, re
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
DEV_CSV = (["q9/national_sample.csv", "q9/targeted_sample.csv", "q9/targeted_capped.csv", "q9/national_matchups.csv", "q9/national_matchups_clean.csv",
            "q9/targeted_matchups.csv", "q9/all_matchups.csv", "q9/test_in.csv", "q9/test_out.csv",
            "stage6/station_days.csv", "stage6/readouts.csv", "stage6/readouts_old.csv", "stage6/landsat_readouts.csv",
            "stage8/fresh_draw.csv", "stage8/val_in.csv", "stage8/val_out.csv", "stage8/fresh_readouts.csv",
            "stage11/temporal/neighbors_days.csv", "stage11/corpus/g_days.csv", "stage11/corpus/g_readouts.csv", "stage11/corpus/e_draw.csv", "stage11/corpus/e_readouts.csv",
            "stage10/dryrun/dry_obs.csv", "stage9/screens/sector-field-clarity-reports.csv"] +
           sorted(glob.glob(f"{S}/stage6/wqp_*.csv")) + sorted(glob.glob(f"{S}/stage7/*.csv")) + sorted(glob.glob(f"{S}/stage8/wqp_*.csv")) + [f"{S}/stage11/corpus/wqp_e_chl.csv"])
BLIND = ["stage12/cert/blind_sample.csv", "stage13/cert/blind_sample13.csv"]
ids, xy, files = set(), set(), []
def scan(p, tag):
    p = p if p.startswith("/") else f"{S}/{p}"
    if not os.path.exists(p): return
    n = 0
    with open(p, newline="", encoding="utf-8", errors="ignore") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames or []
        idc = [c for c in cols if c in ("site", "site_id", "MonitoringLocationIdentifier")]
        la = next((c for c in cols if c in ("lat", "LatitudeMeasure")), None); lo = next((c for c in cols if c in ("lon", "LongitudeMeasure")), None)
        for r in rd:
            for c in idc:
                if r.get(c): ids.add(r[c])
            if la and lo:
                try: xy.add((round(float(r[la]), 5), round(float(r[lo]), 5), tag))
                except (TypeError, ValueError): pass
            n += 1
    files.append({"file": os.path.relpath(p, S), "rows": n, "id_cols": idc, "xy": bool(la and lo), "tag": tag})
for p in DEV_CSV: scan(p, "dev")
for p in BLIND: scan(p, "blind")
for l in open(f"{S}/stage7/national_sites.txt"):
    if l.strip(): ids.add(l.strip())
files.append({"file": "stage7/national_sites.txt", "tag": "dev"})
for x in json.load(open(f"{S}/stage11/corpus/corpus.json")):
    ids.add(x["site"]); xy.add((round(x["lat"], 5), round(x["lon"], 5), "dev"))
files.append({"file": "stage11/corpus/corpus.json", "tag": "dev"})
for j in json.load(open(f"{S}/stage11/ac/jobs_aeronet.json")): xy.add((round(j["lat"], 5), round(j["lon"], 5), "dev"))
files.append({"file": "stage11/ac/jobs_aeronet.json", "tag": "dev"})
out = {"site_ids": sorted(ids), "coords": sorted([list(t) for t in xy]), "files": files,
       "guntersville_box": [34.27, -86.42, 35.06, -85.60]}
json.dump(out, open(f"{S}/stage14/cert/dev_footprint.json", "w"))
print(len(ids), "site ids;", sum(1 for t in xy if t[2] == "dev"), "dev coords;", sum(1 for t in xy if t[2] == "blind"), "blind-sample coords;", len(files), "files")
