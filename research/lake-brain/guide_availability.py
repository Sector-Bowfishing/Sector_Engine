#!/usr/bin/env python3
"""Track 3 (baselines thread): how many of the 621 directory lakes could get an operator guide / flood-pool level
from the public USACE CWMS 'levels' API (https://cwms-data.usace.army.mil/cwms-data/levels).
Inputs (all under HIST, fetched by baseline_fetch / shell loops documented in the research doc):
  cwms_levels/lv_<OFFICE>.json   -- /levels?office=O&level-id-mask=*.Elev*.*  (all Elev levels)
  cwms_levels/loc_<OFFICE>.json  -- /catalog/LOCATIONS?office=O               (lat/lon, kind, datum)
Matching is AUTOMATIC (spatial: CWMS location within 5 km of the lake polygon, or <= 25 km with a name match).
It is an upper bound for 'available', NOT a reviewed binding (rubric cannotCount).
Writes docs/research/lake-brain/data/guide_availability.csv and returns a dict for baseline_summary.json.
"""
import glob, gzip, json, math, os, re, collections, csv, sys
from shapely.geometry import shape, Point

HIST = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain")
H = f"{HIST}/history/cwms_levels"
REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine")
OUTCSV = f"{REPO}/docs/research/lake-brain/data/guide_availability.csv"

FLOOD_BOTTOM = re.compile(r"^(Bottom of Flood( Control)?|Top of Conservation.*|Top of Constant Conservation|Top of Normal|Guide Curve|Seasonal Rule Curve.*|Top of Gross Pool|Top of Full)$", re.I)
STRICT_FLOOD_BOTTOM = re.compile(r"^(Bottom of Flood( Control)?|Top of Conservation.*|Top of Constant Conservation)$", re.I)
GUIDE = re.compile(r"^(Guide Curve|Seasonal Rule Curve.*|Top of Conservation.*|Top of Normal|Rule Curve.*)$", re.I)
DROUGHT = re.compile(r"^(Drought Level.*|Bottom of Conservation|Bottom of Normal|Bottom of Navigation Pool|Bottom of Power|Bottom of Operating)$", re.I)
TOPFLOOD = re.compile(r"^(Top of Flood( Control)?|Top of Exclusive Flood Control|Maximum Pool|Top of Dam|Spillway Crest)$", re.I)

def norm(s):
    s = s.lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(lake|reservoir|res|dam|lock|and|the|l&d|pool|of)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)

def km(a, b):  # (lat,lon) pairs, small-distance approx
    return math.hypot((a[0] - b[0]) * 111.0, (a[1] - b[1]) * 111.0 * math.cos(math.radians(a[0])))

def load():
    D = json.load(open(f"{HIST}/directory_lakes_2026-10-13.json"))["lakes"]
    poly = {}
    for f in json.load(gzip.open(f"{HIST}/geometry/engine_polygons_599.geojson.gz"))["features"]:
        poly[f["properties"]["id"]] = shape(f["geometry"])
    levels = collections.defaultdict(lambda: collections.defaultdict(list))  # office -> loc -> [level dicts]
    for f in glob.glob(f"{H}/lv_*.json"):
        o = os.path.basename(f)[3:6]
        try: L = json.load(open(f)).get("levels", [])
        except Exception: continue
        for l in L:
            loc = l["location-level-id"].split(".")[0]
            levels[o][loc].append(l)
    locs = {}
    for f in glob.glob(f"{H}/loc_*.json"):
        o = os.path.basename(f)[4:7]
        for e in json.load(open(f)):
            if "latitude" in e and e.get("latitude") is not None:
                locs[(o, e["name"])] = e
    return D, poly, levels, locs

def classify(lv):
    names = {l["specified-level-id"] for l in lv}
    seasonal = {l["specified-level-id"] for l in lv if "seasonal-values" in l}
    return {
        "flood_bottom": any(STRICT_FLOOD_BOTTOM.match(n) for n in names),
        "flood_bottom_seasonal": any(STRICT_FLOOD_BOTTOM.match(n) for n in seasonal),
        "guide_curve": any(GUIDE.match(n) for n in seasonal),
        "drought_or_bottom": any(DROUGHT.match(n) for n in names),
        "top_of_flood_or_max": any(TOPFLOOD.match(n) for n in names),
        "n_levels": len(names),
        "names": sorted(names),
    }

def match(D, poly, levels, locs):
    res = {}
    for lk in D:
        pt = (lk["lat"], lk["lon"]); P = poly.get(lk["id"]); nk = norm(lk["name"])
        best = None
        offices = [lk["cwmsOffice"]] if lk["cwmsOffice"] else list(levels.keys())
        for o in offices:
            for loc, lv in levels.get(o, {}).items():
                e = locs.get((o, loc))
                if not e: continue
                cp = (e["latitude"], e["longitude"])
                if P is not None:
                    dkm = P.distance(Point(cp[1], cp[0])) * 111.0  # degrees -> km (approx)
                else:
                    dkm = km(pt, cp)
                nm = norm(loc) or "x"
                name_ok = (len(nm) >= 4 and (nm in nk or nk in nm)) or (len(nm) == 4 and nk.startswith(nm[:4]))
                ok = dkm <= 5 or (dkm <= 25 and name_ok) or (lk["cwmsOffice"] and name_ok and dkm <= 60)
                if not ok: continue
                c = classify(lv)
                score = (c["flood_bottom"] * 4 + c["guide_curve"] * 2 + c["drought_or_bottom"]) * 10 - dkm
                if best is None or score > best[0]:
                    best = (score, o, loc, round(dkm, 1), c, e.get("vertical-datum"))
        if best:
            res[lk["id"]] = {"office": best[1], "location": best[2], "dist_km": best[3], "cls": best[4], "datum": best[5]}
    return res

def history_spans(M):
    """For each matched lake: longest Elev.Inst series span (years) in the CWMS catalog (pool elevation, any interval/version)."""
    import datetime as dt
    ts = {}
    for f in glob.glob(f"{H}/ts_*.json"):
        o = os.path.basename(f)[3:6]
        for e in json.load(open(f)):
            loc = e["name"].split(".Elev")[0]
            if not e.get("e") or not e.get("l"): continue
            a = dt.datetime.fromisoformat(e["e"].replace("Z", "+00:00")); b = dt.datetime.fromisoformat(e["l"].replace("Z", "+00:00"))
            ts.setdefault((o, loc), []).append(((b - a).days / 365.25, e["name"], b))
    out = {}
    for lid, m in M.items():
        c = ts.get((m["office"], m["location"]))
        if c:
            best = max(c); out[lid] = {"span_years": round(best[0], 1), "series": best[1], "latest": best[2].date().isoformat()}
    return out

FAMILIES = [  # (family label, regex on operatorName, machine-readable guide source, access, notes)
    ("USACE", r"USACE|NOAA / USACE|Corps", "CWMS levels API (this table's USACE rows); NWD/other districts partly not on the public CWMS host", "api", "see per-office rows"),
    ("TVA", r"^TVA$", "TVA RestApi /operating-guide/{loc}: GuideCurve (15 of 16 lakes), Top/BtmOpZone (9 of 16), TopOfGates; 2 calendar years only", "api", "tested 43 TVA locations 2026-10-13; Cloudflare needs a browser User-Agent and Accept: application/json"),
    ("USBR", r"USBR", "RISE (data.usbr.gov/rise) elevation/storage series; flood-control top-of-conservation appears as CWMS SPK 'Elev-Top Con' for many USBR projects; no RISE rule-curve parameter found", "api", "partial via CWMS SPK; RISE catalog filters did not work in testing"),
    ("Alabama Power", r"Alabama Power", "Guide curve is published as chart/app content (apcshorelines.com, Shorelines app); CWMS SAM carries 'Elev-Guide Curve' for several APC projects (Martin, Harris, HNHenry, Weiss/Logan Martin via SAM)", "portal/partial api", "numeric table not found as a feed"),
    ("Duke Energy", r"Duke", "Lake levels as feet-below/at full pond (100 ft local datum) on web/phone/app; targets in FERC relicensing documents; no API found", "portal/pdf", "LEAD"),
    ("State / local / water-district", r"State|DNREC|DEEP|NH DES|SJRWMD|NJWSA|Baltimore|DPW|WMD|District|Authority|City|County|Water", "No uniform feed; SJRWMD/SFWMD/SAJ regulation schedules appear in CWMS SAJ as 'Elev-Zone' (Kissimmee chain, Okeechobee)", "mixed", "per-operator work"),
    ("Natural / none", r"^none|natural|Natural|^—$", "n/a (no operator guide)", "n/a", "natural-surface lakes get history-only baselines"),
]

def family_rows(D, M):
    rows, used = [], set()
    for label, rx, src, access, note in FAMILIES:
        ids = [lk["id"] for lk in D if re.search(rx, lk["operatorName"] or "") and lk["id"] not in used]
        used.update(ids)
        mm = [M[i] for i in ids if i in M]
        rows.append({"operator_or_office": f"operator family: {label}", "source_api": src, "directory_lakes": len(ids),
                     "matched_any_elev_level": len(mm), "flood_pool_bottom_level": sum(m["cls"]["flood_bottom"] for m in mm),
                     "flood_pool_bottom_seasonal": sum(m["cls"]["flood_bottom_seasonal"] for m in mm),
                     "seasonal_guide_curve": sum(m["cls"]["guide_curve"] for m in mm), "drought_or_bottom_cons": sum(m["cls"]["drought_or_bottom"] for m in mm),
                     "top_of_flood_or_max_pool": sum(m["cls"]["top_of_flood_or_max"] for m in mm), "matched_within_5km": sum(m["dist_km"] <= 5 for m in mm),
                     "machine_readable": access, "status": note,
                     "operator_api_guide_lakes": 16 if label == "TVA" else ""})
    rest = [lk["id"] for lk in D if lk["id"] not in used]
    mm = [M[i] for i in rest if i in M]
    rows.append({"operator_or_office": "operator family: other / unclassified", "source_api": "n/a", "directory_lakes": len(rest), "matched_any_elev_level": len(mm),
                 "flood_pool_bottom_level": sum(m["cls"]["flood_bottom"] for m in mm), "flood_pool_bottom_seasonal": sum(m["cls"]["flood_bottom_seasonal"] for m in mm),
                 "seasonal_guide_curve": sum(m["cls"]["guide_curve"] for m in mm), "drought_or_bottom_cons": sum(m["cls"]["drought_or_bottom"] for m in mm),
                 "top_of_flood_or_max_pool": sum(m["cls"]["top_of_flood_or_max"] for m in mm), "matched_within_5km": sum(m["dist_km"] <= 5 for m in mm),
                 "machine_readable": "n/a", "status": "unreviewed"})
    return rows

def write_csv(rows):
    os.makedirs(os.path.dirname(OUTCSV), exist_ok=True)
    cols = ["operator_or_office", "directory_lakes", "matched_any_elev_level", "flood_pool_bottom_level", "flood_pool_bottom_seasonal", "seasonal_guide_curve",
            "drought_or_bottom_cons", "top_of_flood_or_max_pool", "matched_within_5km", "operator_api_guide_lakes", "machine_readable", "source_api", "status"]
    with open(OUTCSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({c: r.get(c, "") for c in cols})

def main():
    D, poly, levels, locs = load()
    M = match(D, poly, levels, locs)
    byoff = collections.OrderedDict()
    def row(key):
        return byoff.setdefault(key, collections.Counter())
    for lk in D:
        o = lk["cwmsOffice"] or "(none)"
        c = row(o); c["directory_lakes"] += 1
        m = M.get(lk["id"])
        if m:
            cl = m["cls"]; c["matched_any_elev_level"] += 1
            c["flood_bottom_level"] += cl["flood_bottom"]
            c["flood_bottom_seasonal"] += cl["flood_bottom_seasonal"]
            c["guide_curve_seasonal"] += cl["guide_curve"]
            c["drought_or_bottom_conservation"] += cl["drought_or_bottom"]
            c["top_of_flood_or_max"] += cl["top_of_flood_or_max"]
            c["matched_within_5km"] += m["dist_km"] <= 5
    rows = []
    for o, c in sorted(byoff.items(), key=lambda kv: -kv[1]["directory_lakes"]):
        rows.append({"operator_or_office": f"USACE CWMS {o}" if o != "(none)" else "directory lakes with no cwmsOffice",
                     "source_api": "cwms-data/levels" if o != "(none)" else "cwms-data/levels (spatial match across all offices)",
                     "directory_lakes": c["directory_lakes"], "matched_any_elev_level": c["matched_any_elev_level"],
                     "flood_pool_bottom_level": c["flood_bottom_level"], "flood_pool_bottom_seasonal": c["flood_bottom_seasonal"],
                     "seasonal_guide_curve": c["guide_curve_seasonal"], "drought_or_bottom_cons": c["drought_or_bottom_conservation"],
                     "top_of_flood_or_max_pool": c["top_of_flood_or_max"], "matched_within_5km": c["matched_within_5km"],
                     "machine_readable": "yes", "status": "automatic spatial match; unreviewed upper bound"})
    summ = collections.Counter()
    for r in rows:
        for k in ("directory_lakes", "matched_any_elev_level", "flood_pool_bottom_level", "seasonal_guide_curve", "drought_or_bottom_cons", "matched_within_5km"):
            summ[k] += r[k]
    fam = family_rows(D, M)
    hs = history_spans(M)
    sp = [v["span_years"] for v in hs.values()]
    summ["history_span_ge5y"] = sum(1 for x in sp if x >= 5); summ["history_span_ge10y"] = sum(1 for x in sp if x >= 10)
    summ["history_span_ge20y"] = sum(1 for x in sp if x >= 20); summ["history_span_ge30y"] = sum(1 for x in sp if x >= 30); summ["matched_with_any_elev_series"] = len(sp)
    write_csv(rows + fam)
    json.dump({"rows": rows, "families": fam, "matches": M, "history_spans": hs, "totals": summ}, open(f"{HIST}/history/guide_availability_cwms.json", "w"), indent=1, default=str)
    return rows, summ, M, D, fam

if __name__ == "__main__":
    rows, summ, M, D, fam = main()
    for r in fam: print({k: v for k, v in r.items() if k in ("operator_or_office", "directory_lakes", "matched_any_elev_level", "flood_pool_bottom_level", "seasonal_guide_curve")})
    for r in rows: print({k: v for k, v in r.items() if k in ("operator_or_office", "directory_lakes", "matched_any_elev_level", "flood_pool_bottom_level", "seasonal_guide_curve", "drought_or_bottom_cons")})
    print(dict(summ), len(D))
