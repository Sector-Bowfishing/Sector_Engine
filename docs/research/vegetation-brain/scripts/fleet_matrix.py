#!/usr/bin/env python3
"""Vegetation Brain research: fleet coverage matrix for the 621-lake directory.
Inputs are read-only research data outside Git. Output: data/fleet_matrix.csv.
No clarity measurement exists fleet-wide, so submerged feasibility is a CONDITIONAL
tier, never a detection claim."""
import csv, gzip, json, math, re, collections, os, sys
D = os.environ.get("SECTOR_RESEARCH_DATA", os.path.expanduser("~/Desktop/Development/Sector_Research_Data")).rstrip("/") + "/"
V = D + "vegetation-brain/sources/"
dire = json.load(open(D + "lake-brain/directory_lakes_2026-10-13.json"))["lakes"]
glob = {r["id"]: r for r in csv.DictReader(open(V + "globathy_fleet_match_from_depth_research.csv"))}
polys = {f["properties"]["id"]: f["geometry"] for f in json.load(gzip.open(D + "lake-brain/geometry/engine_polygons_599.geojson.gz"))["features"]}

def rings(g):
    if g["type"] == "GeometryCollection":
        for sub in g["geometries"]:
            yield from rings(sub)
        return
    if g["type"] not in ("Polygon", "MultiPolygon"):
        return
    polys_ = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    for p in polys_:
        yield p
def pip(x, y, ring):
    c = False; n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][:2]; x2, y2 = ring[(i + 1) % n][:2]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def inside(x, y, g):
    for p in rings(g):
        if pip(x, y, p[0]) and not any(pip(x, y, h) for h in p[1:]): return True
    return False
def bbox(g):
    xs = [c[0] for p in rings(g) for c in p[0]]; ys = [c[1] for p in rings(g) for c in p[0]]
    return min(xs), min(ys), max(xs), max(ys)
polys = {k: g for k, g in polys.items() if any(True for _ in rings(g))}
BB = {k: bbox(g) for k, g in polys.items()}

# NLA 2017 sites inside each polygon (+ phab veg cover)
nla_site = {}
for r in csv.DictReader(open(V + "nla_2017_phab/nla_2017_site_information-data.csv")):
    try: nla_site[r["SITE_ID"]] = (float(r["LON_DD83"]), float(r["LAT_DD83"]), r["PSTL_CODE"])
    except: pass
nla_cnt = collections.Counter(); nla_sub = collections.defaultdict(list)
phab = collections.defaultdict(list)
for r in csv.DictReader(open(V + "nla_2017_phab/nla_2017_phab-data.csv")):
    phab[r["SITE_ID"]].append(r)
for sid, (x, y, st) in nla_site.items():
    for k, g in polys.items():
        b = BB[k]
        if b[0] <= x <= b[2] and b[1] <= y <= b[3] and inside(x, y, g):
            nla_cnt[k] += 1
            for r in phab.get(sid, []):
                try: nla_sub[k].append(int(float(r["AM_SUBMERGENT"])))
                except: pass
            break

# FWC LTM lake names
norm = lambda s: re.sub(r"[^a-z]", "", s.lower().replace("lake", "").replace("reservoir", ""))
fwc = collections.Counter()
for r in csv.DictReader(open(V + "fwc_ltm_point_intercepts/fwc_ltm_point_intercepts.csv")):
    fwc[norm(r["Lake"])] += 1

def area_km2(g):
    a = 0.0
    for p in rings(g):
        for i, ring in enumerate(p):
            lat0 = sum(c[1] for c in ring) / len(ring); k = math.cos(math.radians(lat0))
            s = 0.0
            for j in range(len(ring)):
                x1, y1 = ring[j][:2]; x2, y2 = ring[(j + 1) % len(ring)][:2]
                s += x1 * y2 - x2 * y1
            v = abs(s) / 2 * 111.32 * 111.32 * k
            a += v if i == 0 else -v
    return a

REG = {"FL": "GULF", "LA": "GULF", "GA": "SOUTHEAST", "SC": "SOUTHEAST", "NC": "SOUTHEAST", "AL": "SOUTHEAST", "MS": "SOUTHEAST", "VA": "SOUTHEAST",
       "TN": "MIDSOUTH", "KY": "MIDSOUTH", "AR": "MIDSOUTH", "WV": "MIDSOUTH", "OH": "MIDWEST", "IN": "MIDWEST", "IL": "MIDWEST", "IA": "MIDWEST", "MO": "MIDWEST",
       "MN": "UPPER_MIDWEST_GL", "WI": "UPPER_MIDWEST_GL", "MI": "UPPER_MIDWEST_GL",
       "NY": "NORTHEAST", "PA": "NORTHEAST", "NJ": "NORTHEAST", "CT": "NORTHEAST", "MA": "NORTHEAST", "RI": "NORTHEAST", "VT": "NORTHEAST", "NH": "NORTHEAST", "ME": "NORTHEAST", "MD": "NORTHEAST", "DE": "NORTHEAST",
       "KS": "PLAINS", "NE": "PLAINS", "SD": "PLAINS", "ND": "PLAINS", "OK": "PLAINS",
       "MT": "MOUNTAIN_WEST", "WY": "MOUNTAIN_WEST", "CO": "MOUNTAIN_WEST", "ID": "MOUNTAIN_WEST", "UT": "MOUNTAIN_WEST",
       "WA": "PACIFIC_NW", "OR": "PACIFIC_NW", "CA": "CALIFORNIA", "AZ": "SOUTHWEST", "NM": "SOUTHWEST", "NV": "SOUTHWEST", "AK": "ALASKA", "HI": "HAWAII"}
def region(st, lon):
    if st == "TX": return "SOUTHEAST" if lon > -97.5 else "PLAINS"
    return REG[st]
TVA = re.compile(r"guntersville|wheeler|nickajack|chickamauga|pickwick|watts bar|fort loudoun|kentucky lake|norris|douglas|cherokee|melton|tellico|fontana|boone|south holston|watauga|wilson|normandy", re.I)
UMR = re.compile(r"pepin|pool \d|keokuk|la grange|mississippi|illinois river|peoria|saylorville", re.I)
ICE = {"GULF": 0, "SOUTHEAST": 0, "SOUTHWEST": 1, "MIDSOUTH": 1, "HAWAII": 0, "CALIFORNIA": 1, "PLAINS": 3, "MIDWEST": 3, "NORTHEAST": 4, "PACIFIC_NW": 2, "MOUNTAIN_WEST": 5, "UPPER_MIDWEST_GL": 5, "ALASKA": 7}

rows = []
for L in dire:
    k = L["id"]; st = L["state"]; g = polys.get(k)
    a = area_km2(g) if g else None
    gl = glob.get(k, {})
    sh18 = float(gl["glob_shallow_frac_1p8m"]) if gl.get("glob_shallow_frac_1p8m") else None
    rg = region(st, L["lon"])
    nm = norm(L["name"])
    fw = fwc.get(nm, 0) if st == "FL" else 0
    gt = []
    if nla_cnt[k]: gt.append(f"NLA2017x{nla_cnt[k]}")
    if fw: gt.append(f"FWC_LTM_pts{fw}")
    if st == "MN": gt.append("UMN_MN_plants(unverified-match)")
    if st == "WI": gt.append("WI_DNR_PI(request)")
    if st in ("IA", "IL", "MO", "MN", "WI") and UMR.search(L["name"]): gt.append("USGS_UMR(possible)")
    if TVA.search(L["name"]) and st in ("TN", "AL", "KY", "MS", "NC", "GA", "VA"): gt.append("TVA(request)")
    if st == "TX": gt.append("TPWD_acreage(report)")
    if st == "FL" and not fw: gt.append("FWC_inventory(report)")
    nw = "NWI" if st not in ("AK", "HI") else "NWI(partial)"
    gt.append(nw)
    # tiers
    if a is None: ef = "UNKNOWN_no_polygon"
    elif a >= 5: ef = "HIGH"
    elif a >= 0.5: ef = "MEDIUM_mixed_pixels"
    else: ef = "LOW_lt0.5km2"
    if a is None: sub = "UNKNOWN"
    elif a < 0.5: sub = "S0_not_feasible_size"
    elif sh18 is not None and sh18 < 0.03: sub = "S1_little_shallow_area_modeled"
    elif sh18 is not None and sh18 >= 0.10: sub = "S2_shallow_candidate_CLARITY_UNKNOWN"
    else: sub = "S1b_limited_shallow_area_modeled"
    ice = ICE[rg]
    strong = [x for x in gt if x.startswith(("NLA", "FWC_LTM"))]
    val = "VALIDATABLE_NOW" if strong else ("VALIDATABLE_WITH_REQUEST_OR_BROWSER_DOWNLOAD" if any(x.startswith(("UMN", "WI_", "TVA", "USGS", "TPWD")) for x in gt) else "NWI_PRIOR_ONLY")
    rows.append(dict(id=k, name=L["name"], state=st, region=rg, lat=L["lat"], lon=L["lon"], poly_area_km2=None if a is None else round(a, 2),
        regime=gl.get("regime", ""), lake_class=gl.get("lake_class", ""), has_dam=L.get("hasDam"), full_pool_ft=L.get("fullPoolFt"),
        modeled_shallow_frac_le1p8m=sh18, ice_months_est=ice, emergent_floating_feasibility=ef, submerged_feasibility_tier=sub,
        ground_truth=";".join(gt), nla_submergent_mean_cover_code=("%.2f" % (sum(nla_sub[k]) / len(nla_sub[k])) if nla_sub[k] else ""), validation_class=val))
out = "data/fleet_matrix.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
c = collections.Counter
print(len(rows)); 
for col in ("region", "emergent_floating_feasibility", "submerged_feasibility_tier", "validation_class"):
    print(col, dict(c(r[col] for r in rows)))
print("with NLA:", sum(1 for r in rows if "NLA2017" in r["ground_truth"]), "with FWC pts:", sum(1 for r in rows if "FWC_LTM" in r["ground_truth"]))
print("regime", dict(c(r["regime"] for r in rows)))
