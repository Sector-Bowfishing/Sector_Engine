import json, hashlib, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; MAN = ROOT.parent / "MANIFEST.jsonl"
src = {
 "fwc_ltm_point_intercepts.json": ("ground_truth", "https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/33/query", "FWC Long-Term Monitoring plant point intercepts, all 96,055 records (species lists, date, lat/lon; vegetated sites only)"),
 "fwc_ltm_lakes.geojson": ("ground_truth_geometry", "https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/35/query", "FWC LTM lake polygons (139)"),
}
rows = []
def add(kind, p, url, note, ret="keep"):
    p = Path(p); h = hashlib.sha256(p.read_bytes()).hexdigest()
    rows.append(dict(kind=kind, path=str(p), bytes=p.stat().st_size, sha256=h, source_url=url, retention=ret, note=note))
for f in sorted((ROOT/"data").glob("*")):
    if f.name in src: k, u, n = src[f.name]; add(k, f, u, n)
    elif f.name.startswith("snoco_layer"):
        i = f.stem.replace("snoco_layer", "")
        add("ground_truth", f, f"https://gis.snoco.org/host/rest/services/Hosted/Lake_Aquatic_Plant_Surveys_Service/FeatureServer/{i}/query", f"Snohomish County Surface Water Mgmt lake aquatic plant survey layer {i}")
for f in sorted((ROOT/"out"/"s2cache").glob("*.npz")):
    add("s2_window_cache", f, "https://earth-search.aws.element84.com/v1 (sentinel-2-c1-l2a, fallback sentinel-2-l2a)", "Sentinel-2 L2A window around lake, 10 bands + SCL at 10 m; derived from range reads of public COGs", ret="regenerable")
for f in sorted((ROOT/"out").glob("stack_*.npz")):
    add("derived_stack", f, "derived", "per-lake index stack + label rasters (03_extract.py)", ret="regenerable")
with open(MAN, "a") as fh:
    for r in rows: fh.write(json.dumps(r) + "\n")
print(len(rows), "rows appended;", sum(r["bytes"] for r in rows)/1e6, "MB")
