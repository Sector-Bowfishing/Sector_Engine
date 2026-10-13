"""Append every file new in the 05 note work (not already in MANIFEST.jsonl) with bytes + sha256. Run last."""
import json, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; MAN = ROOT.parent/"MANIFEST.jsonl"
seen = {json.loads(l)["path"] for l in open(MAN) if l.strip()}
URL = {"carver": "https://services.arcgis.com/wMZT8kNwa6tOxhKg/arcgis/rest/services/{ReitzLakeBiovolume,BrickyardVegetationBiovolume}/FeatureServer/0 (Carver County MN, ArcGIS Online)",
       "secchi": "https://www.waterqualitydata.us/data/{Station,Result}/search (Water Quality Portal; FL LAKEWATCH, FDEP, WMDs)",
       "pac": "https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/41/query (LTM_lakes_PAC_PVI)"}
def classify(p):
    s = str(p.relative_to(ROOT))
    if s.startswith("data/carver"): return "ground_truth", URL["carver"], "keep", "sonar biovolume points (BioBase), survey date not stated in metadata"
    if s.startswith("data/secchi"): return "water_clarity_proxy", URL["secchi"], "keep", "Secchi depth records / stations from WQP"
    if s == "data/fwc_ltm_lakes_PAC_PVI.json": return "ground_truth", URL["pac"], "keep", "FWC LTM sonar-derived percent area covered (PAC) and percent volume infested (PVI) per lake-year, 126 lakes 2015-2023"
    if s == "data/pac_lakeyears.json": return "derived_selection", "derived", "keep", "lake-years selected for lake-level S2 test (PAC/PVI + LTM survey dates)"
    if s.startswith("out/s2cache_pac"): return "s2_window_cache", "https://earth-search.aws.element84.com/v1 (sentinel-2-c1-l2a, fallback sentinel-2-l2a)", "regenerable", "lean uint16 DN window (B02,B03,B04,B08,B8A,B11,SCL) around lake; offset recorded per file"
    if s.startswith("out/cell_") or s.startswith("out/stack_carver"): return "derived_stack", "derived", "regenerable", "cell-level / pixel stacks (note 05)"
    if s.startswith("out/pac/"): return "derived_summary", "derived", "keep", "per lake-year Sector cell/pixel summaries"
    if s.startswith("scripts/"): return "script", "local", "keep", "note-05 script"
    if s.startswith("out/figures"): return "figure", "derived", "keep", "note-05 figure"
    return "derived_metrics", "derived", "keep", "note-05 metrics/table/log"
rows = []
import os, time
t0 = time.time() - 6*3600
for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or str(p) in seen or ".venv" in p.parts or p.name.startswith(".") or "_discarded" in str(p): continue
    if p.stat().st_mtime < t0: continue
    k, u, ret, n = classify(p)
    rows.append(dict(kind=k, path=str(p), bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), source_url=u, retention=ret, note=n))
with open(MAN, "a") as fh:
    for r in rows: fh.write(json.dumps(r) + "\n")
print(len(rows), "rows appended;", round(sum(r["bytes"] for r in rows)/1e6, 1), "MB")
