"""Recompute fleet exposure readiness for all 621 lakes from the CURRENT geometry assets.
Inputs: directory (621), Lake Brain geometry flags CSV, per-lake polygon-fetch summary, audited fetch tables (headers only).
  python research/fleet_readiness.py OUT_DIR"""
import csv, glob, gzip, hashlib, json, os, sys, collections
HOME = os.path.expanduser("~"); R = HOME + "/Desktop/Development/Sector_Research_Data/"
DIR = R + "lake-brain/directory_lakes_2026-10-13.json"; FLAGS = R + "lake-brain/geometry/lake_geometry_flags.csv"
POLY = R + "lake-brain/geometry/engine_polygons_599.geojson.gz"; FETCH = R + "wind-brain/out/fleet_fetch.json"
TABLES = HOME + "/Library/Caches/sector-wind/national-fetch/tables/*.gz"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]
d = json.load(open(DIR))["lakes"]; flags = {r["id"]: r for r in csv.DictReader(open(FLAGS))}
fetch = {r["id"]: r for r in json.load(open(FETCH))}
polys = {f["properties"]["id"] for f in json.load(gzip.open(POLY))["features"]}
audited = {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"}
for p in glob.glob(TABLES):
    x = json.load(gzip.open(p))["directory"]; audited.add(f"{x['name']}|{x['state']}")
rows = []
for l in sorted(d, key=lambda x: x["id"]):
    i = l["id"]; f = flags.get(i, {}); conf = f.get("confidence") or "MISSING"; fe = fetch.get(i)
    has_poly = i in polys; fetch_ok = bool(fe and fe.get("ok")); dom = {"AK": "AK", "HI": "HI"}.get(l["state"], "CONUS")
    blockers = []
    if dom != "CONUS": blockers.append(f"NBM {dom} domain not tested/sampled")
    if f.get("point_flag") == "identity_risk": blockers.append("lake identity risk (directory point far from polygon)")
    if i in audited: base = "AUDITED"
    elif not has_poly: base = "NO_GEOMETRY"
    elif conf == "LOW": base = "LOW_GEOMETRY"
    elif not fetch_ok or (fe["res"] > 40) or fe["nBanks"] < 20: base = "POINT_ONLY"
    elif conf == "HIGH": base = "ESTIMATED_HIGH_GEOMETRY"
    elif conf == "MEDIUM": base = "ESTIMATED_MEDIUM_GEOMETRY"
    else: base = "POINT_ONLY"
    cat = "BLOCKED" if (blockers and base in ("AUDITED", "ESTIMATED_HIGH_GEOMETRY", "ESTIMATED_MEDIUM_GEOMETRY")) else base
    why_point = "" if base != "POINT_ONLY" else ("polygon fetch failed" if not fetch_ok else f"raster {fe['res']:.0f} m / banks {fe['nBanks']}")
    elig = {"AUDITED": "Field-validation candidate; customer exposure labels only after bank-pair validation (modeled, audited geometry)",
            "ESTIMATED_HIGH_GEOMETRY": "Tonight wind block only; exposure labels internal until matched + field validation passes",
            "ESTIMATED_MEDIUM_GEOMETRY": "Tonight wind block only; exposure labels internal; lower priority than HIGH",
            "LOW_GEOMETRY": "Tonight wind block only; no bank labels (geometry confidence LOW)",
            "POINT_ONLY": "Tonight wind block only; no bank labels (" + why_point + ")",
            "NO_GEOMETRY": "Tonight wind block only; no bank labels (no polygon)",
            "BLOCKED": "No Wind customer output until " + "; ".join(blockers)}[cat]
    vt = {"AUDITED": "A: audited geometry, SHA-256 verified, QA'd; exposure MODELED, no field truth",
          "ESTIMATED_HIGH_GEOMETRY": "E: polygon estimate; matched bank-level checks vs audited PASS, lake-dominant-direction FAIL; no field truth",
          "ESTIMATED_MEDIUM_GEOMETRY": "E: as HIGH, medium polygon confidence; no field truth"}.get(cat, "none")
    rows.append({"lakeId": i, "lake": l["name"], "state": l["state"], "category": cat, "baseCategory": base, "geometrySource": f.get("source") or "none",
                 "geometryConfidence": conf, "pointFlag": f.get("point_flag") or "", "fetchAvailable": "audited" if i in audited else ("estimated" if (fetch_ok and base != "POINT_ONLY") else "no"),
                 "bankClassification": "yes (modeled)" if cat in ("AUDITED", "ESTIMATED_HIGH_GEOMETRY", "ESTIMATED_MEDIUM_GEOMETRY") else ("modeled but blocked" if cat == "BLOCKED" else "no"),
                 "forecastDomain": dom, "validationTier": vt, "customerEligibility": elig, "blockers": "; ".join(blockers), "polygonRasterM": None if not fe or not fe.get("ok") else round(fe["res"], 1),
                 "maxP90FetchM": None if not fe or not fe.get("ok") else int(max(fe["p90FetchByDir"]))})
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
with open(out + "/fleet_exposure_readiness.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
cnt = collections.Counter(r["category"] for r in rows); base = collections.Counter(r["baseCategory"] for r in rows)
summ = {"assets": {"directory": sha(DIR), "flagsCsv": sha(FLAGS), "enginePolygons": sha(POLY), "fleetFetch": sha(FETCH)}, "lakes": len(rows), "categories": dict(cnt), "beforeBlockedOverlay": dict(base),
        "blocked": [(r["lakeId"], r["baseCategory"], r["blockers"]) for r in rows if r["category"] == "BLOCKED"],
        "confidenceAll621": dict(collections.Counter(r["geometryConfidence"] for r in rows)), "offWaterDirectoryPoints": sum(r["pointFlag"] == "off_water" for r in rows)}
json.dump(summ, open(out + "/fleet_exposure_readiness_summary.json", "w"), indent=1); print(json.dumps(summ, indent=1))
