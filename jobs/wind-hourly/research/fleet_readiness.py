"""Recompute fleet exposure readiness for all 621 lakes from the CURRENT geometry asset: the published Lake Registry v1 index (+ per-lake analysis polygons
fetched by research/registry_fleet.py), the audited fetch tables, and the audited-vs-registry cross-check.
  python research/fleet_readiness.py REGISTRY_INDEX.json REGISTRY_FLEET_FETCH.json AUDITED_CHECK.json OUT_DIR"""
import csv, glob, gzip, hashlib, json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind.brain import fleet as FL
HOME = os.path.expanduser("~")
TABLES = HOME + "/Library/Caches/sector-wind/national-fetch/tables/*.gz"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]
idx_path, fetch_path, check_path, out = sys.argv[1:5]
reg = json.load(open(idx_path)); fetch = {r["id"]: r for r in json.load(open(fetch_path))}; checks = {r["lakeId"]: r for r in json.load(open(check_path))}
audited = {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"}
for p in glob.glob(TABLES):
    x = json.load(gzip.open(p))["directory"]; audited.add(f"{x['name']}|{x['state']}")
rows = []
for l in sorted(reg["lakes"], key=lambda x: x["lakeId"]):
    i = l["lakeId"]; fl = FL.registry_flags(l); conf = fl["confidence"]; fe = fetch.get(i); g = l.get("geometry")
    dom = FL.forecast_domain(l["state"])
    blockers = FL.blockers(l["state"], fl["point_flag"])
    if i in audited:
        blockers += FL.audited_check_blockers(checks.get(i))
    fetch_ok = bool(fe and fe.get("ok"))
    if i in audited: base = "AUDITED"
    elif g is None: base = "NO_GEOMETRY"
    elif conf == "LOW": base = "LOW_GEOMETRY"
    elif not fetch_ok or fe["res"] > FL.MAX_RASTER_M or fe["nBanks"] < FL.MIN_BANKS: base = "POINT_ONLY"
    elif conf == "HIGH": base = "ESTIMATED_HIGH_GEOMETRY"
    elif conf == "MEDIUM": base = "ESTIMATED_MEDIUM_GEOMETRY"
    else: base = "POINT_ONLY"
    cat = "BLOCKED" if (blockers and base in ("AUDITED", "ESTIMATED_HIGH_GEOMETRY", "ESTIMATED_MEDIUM_GEOMETRY")) else base
    why_point = "" if base != "POINT_ONLY" else ("polygon fetch failed" if not fetch_ok else f"raster {fe['res']:.0f} m / banks {fe['nBanks']}")
    elig = {"AUDITED": "Field-validation candidate; customer exposure labels only after bank-pair validation (modeled, audited geometry)",
            "ESTIMATED_HIGH_GEOMETRY": "Tonight wind block only; exposure labels internal until independent validation passes",
            "ESTIMATED_MEDIUM_GEOMETRY": "Tonight wind block only; exposure labels internal; lower priority than HIGH",
            "LOW_GEOMETRY": "Tonight wind block only; no bank labels (registry confidence LOW)",
            "POINT_ONLY": "Tonight wind block only; no bank labels (" + why_point + ")",
            "NO_GEOMETRY": "Tonight wind block only; no bank labels (no registry geometry: " + str(l.get("geometryMissingStatus")) + ")",
            "BLOCKED": "No Wind customer output until " + "; ".join(blockers)}[cat]
    vt = {"AUDITED": "A", "ESTIMATED_HIGH_GEOMETRY": "E", "ESTIMATED_MEDIUM_GEOMETRY": "E"}.get(cat, "none")
    rows.append({"lakeId": i, "lake": l["name"], "state": l["state"], "category": cat, "baseCategory": base,
                 "geometrySource": (g or {}).get("source") or "none", "geometryKind": (g or {}).get("extentKind") or "none", "registryPickMethod": (g or {}).get("pickMethod") or "",
                 "geometryConfidence": conf, "pointFlag": fl["point_flag"], "memberIds": ";".join(l.get("memberIds") or [i]),
                 "fetchAvailable": "audited" if i in audited else ("estimated" if (fetch_ok and base != "POINT_ONLY") else "no"),
                 "bankClassification": "yes (modeled)" if cat in ("AUDITED", "ESTIMATED_HIGH_GEOMETRY", "ESTIMATED_MEDIUM_GEOMETRY") else ("modeled but blocked" if cat == "BLOCKED" else "no"),
                 "forecastDomain": dom, "validationTier": vt, "customerEligibility": elig, "blockers": "; ".join(blockers),
                 "polygonRasterM": None if not fetch_ok else round(fe["res"], 1), "maxP90FetchM": None if not fetch_ok else int(max(fe["p90FetchByDir"]))})
os.makedirs(out, exist_ok=True)
with open(out + "/fleet_exposure_readiness.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
cnt = collections.Counter(r["category"] for r in rows); base = collections.Counter(r["baseCategory"] for r in rows)
summ = {"assets": {"registryIndex": sha(idx_path), "registryGeneratedAt": reg["generatedAt"], "registryFleetFetch": sha(fetch_path), "auditedCheck": sha(check_path)}, "lakes": len(rows),
        "categories": dict(cnt), "beforeBlockedOverlay": dict(base), "blocked": [(r["lakeId"], r["baseCategory"], r["blockers"]) for r in rows if r["category"] == "BLOCKED"],
        "confidenceAll621": dict(collections.Counter(r["geometryConfidence"] for r in rows)), "pointFlags": dict(collections.Counter(r["pointFlag"] for r in rows)),
        "labelEligible": sum(1 for r in rows if r["category"] in ("AUDITED", "ESTIMATED_HIGH_GEOMETRY", "ESTIMATED_MEDIUM_GEOMETRY"))}
json.dump(summ, open(out + "/fleet_exposure_readiness_summary.json", "w"), indent=1); print(json.dumps({k: summ[k] for k in ("assets", "categories", "beforeBlockedOverlay", "labelEligible", "confidenceAll621")}, indent=1))
