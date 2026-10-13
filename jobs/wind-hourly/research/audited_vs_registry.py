"""Cross-check every AUDITED fetch table against the published Lake Registry v1: same water body? (area of the NHD feature the table was built from vs the
registry shoreline union; name match; registry pointFlag/confidence). Identity is Lake Brain's; this only reports.
  python research/audited_vs_registry.py INDEX.json OUT.json"""
import glob, gzip, json, os, sys
HOME = os.path.expanduser("~")
idx = {l["lakeId"]: l for l in json.load(open(sys.argv[1]))["lakes"]}
rows = []
DEV = {"guntersville": "Guntersville|AL", "wheeler": "Wheeler|AL", "wilson": "Wilson|AL", "pickwick": "Pickwick Lake|TN"}
for p in sorted(glob.glob(HOME + "/Library/Caches/sector-wind/national-fetch/tables/*.gz")):
    d = json.load(gzip.open(p)); lid = f"{d['directory']['name']}|{d['directory']['state']}"; g = d["geometry"]; r = idx.get(lid)
    if not r:
        rows.append({"lakeId": lid, "registry": "absent"}); continue
    ra = r.get("areaKm2"); ta = g.get("nhdAreaKm2")
    ratio = None if not ra or not ta else round(ra / ta, 3)
    seeds = set((r.get("geometry") or {}).get("seedIds") or []) | set((r.get("geometry") or {}).get("sourceIds") or [])
    flag = []
    if r.get("geometry") is None: flag.append("registry geometry null")
    elif ratio is not None and not (0.8 <= ratio <= 1.25): flag.append(f"area ratio {ratio} outside 0.8-1.25")
    if g.get("nameMatchesDirectory") is False: flag.append("audited table GNIS name != directory name")
    if r.get("pointFlag") == "identity-risk": flag.append("registry pointFlag identity-risk")
    if r["geometryConfidence"]["level"] in ("LOW", "MISSING"): flag.append(f"registry confidence {r['geometryConfidence']['level']}")
    rows.append({"lakeId": lid, "tableGnis": g.get("gnis"), "tableNhdAreaKm2": ta, "registryAreaKm2": ra, "areaRatio": ratio, "registryConfidence": r["geometryConfidence"]["level"],
                 "registryPointFlag": r.get("pointFlag"), "registryMemberIds": r.get("memberIds"), "flags": flag})
for k, lid in DEV.items():
    r = idx.get(lid); rows.append({"lakeId": lid, "dev": True, "registryAreaKm2": r and r.get("areaKm2"), "registryConfidence": r and r["geometryConfidence"]["level"], "registryPointFlag": r and r.get("pointFlag")})
json.dump(rows, open(sys.argv[2], "w"), indent=1)
bad = [x for x in rows if x.get("flags")]
print(len(rows), "audited lakes;", len(bad), "flagged")
for x in bad: print(x["lakeId"], x.get("areaRatio"), x["flags"])
