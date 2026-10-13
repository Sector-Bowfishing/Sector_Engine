#!/usr/bin/env python3
"""Write ledger/globathy.jsonl (source records) + data/globathy_truth_raw.json (merged agent-collected truth records)."""
import glob, json, os, collections
D = "/Users/mcather/Desktop/Development/"; DATA = D + "Sector_Research_Data/depth-brain/globathy/"; W = D + "Sector_Engine-depth-research/docs/research/depth-brain/"
T = []
for f in sorted(glob.glob(DATA + "truth/truth_*.json")): T += json.load(open(f))
ovr = json.load(open(DATA + "truth_overrides.json"))
json.dump(T, open(W + "data/globathy_truth_raw.json", "w"), indent=0)
L = []; n = 0
def add(**k):
    global n; n += 1; L.append({"kind": "source", "id": f"S-globathy-{n:03d}", **k})
add(title="GLOBathy, the Global Lakes Bathymetry Dataset (Khazaei et al. 2022, Scientific Data)", url="https://doi.org/10.1038/s41597-022-01132-9", accessed="2026-10-13", decision="evaluated", reason="Subject of evaluation. Dmax modeled from surrounding-terrain slope + area/perimeter; for 1,468 lakes worldwide (59 fleet lakes) an observed/literature Dmax is supplied. Bathymetry = radial extrapolation from shore, so no real morphology.")
add(title="GLOBathy Bathymetry Rasters (figshare 13404635)", url="https://doi.org/10.6084/m9.figshare.13404635.v1", accessed="2026-10-13", decision="used", reason="Single 16.7 GB zip (1,427,688 per-lake GeoTIFFs, 1 arc-sec). Not downloaded whole: central directory + 554 fleet-lake members (257 MB) fetched with HTTP range requests; ids 1056588/112353/112213/747 needed retry. Raster max equals Dmax_use; raster is generated from the same A(h) law, so adds no information beyond Dmax and b.")
add(title="GLOBathy basic parameters + head-Area-Volume relationships (figshare 13402070 / 13402124)", url="https://doi.org/10.6084/m9.figshare.13402124.v1", accessed="2026-10-13", decision="used", reason="Dmax_use_m, A(h)=a*h^b coefficients, V; cached from Lake Brain work.")
add(title="HydroLAKES v1.0 points/polygons (join to Sector lakes via lake-brain external_join.json)", url="https://www.hydrosheds.org/products/hydrolakes", accessed="2026-10-13", decision="used", reason="Id link between Sector lakes and GLOBathy; match QA by area ratio, polygon IoU, hl_n, shared id.")
add(title="Lake Brain CWMS stage-storage fits (hypso_truth.json)", url="local:Sector_Research_Data/lake-brain/context/hypso_truth.json", accessed="2026-10-13", decision="used", reason="Truth for fractional area change per ft near pool (34 USACE lakes matched to a GLOBathy row); USACE-measured, not modeled.")
seen = collections.defaultdict(list)
for r in T: seen[r.get("source_url") or "none"].append(r)
for u, rs in sorted(seen.items()):
    if u == "none": continue
    confs = sorted(set(r.get("confidence") or "?" for r in rs)); lakes = [r["id"] for r in rs]
    excl = [r["id"] for r in rs if r["id"] in ovr and ovr[r["id"]].get("confidence") == "excluded"]
    nodepth = all(r.get("max_depth_m") is None for r in rs)
    dec = "excluded" if (len(excl) == len(rs)) else ("recorded_no_max_depth" if nodepth else "used_as_truth")
    reason = f"lakes={lakes}; confidence={confs}; " + "; ".join((r.get("evidence_quote") or "")[:140] for r in rs[:2])
    add(title=(rs[0].get("source_title") or u)[:200], url=u, accessed="2026-10-13", decision=dec, reason=reason[:600])
os.makedirs(W + "ledger", exist_ok=True)
with open(W + "ledger/globathy.jsonl", "w") as f:
    for r in L: f.write(json.dumps(r) + "\n")
print(len(L), "ledger lines;", os.path.getsize(W + "data/globathy_truth_raw.json") // 1000, "KB raw truth")
