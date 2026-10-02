"""Stage 13: run ACOLITE (overrides) on one crop keeping the output, sample points with the mask variants, delete.
  python aco13_one.py INPUT LAT LON OUTDIR POINTS_JSON OVERRIDES_JSON"""
import json, sys, os, shutil
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage12/tools"); sys.path.insert(0, f"{S}/stage13/tools")
import aco12_one as A, sample_variants as SV
inp, lat, lon, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
pts, ov = json.loads(sys.argv[5]), json.loads(sys.argv[6])
limit = [lat - 0.08, lon - 0.10, lat + 0.08, lon + 0.10]
l2w, att = A.run(inp, limit, out, ov)
if not l2w and any("ogr.Open not implemented" in (a.get("error") or "") for a in att):
    l2w, att2 = A.run(inp, limit, out, {**ov, "geometry_type": "grids"}); att += att2
res = {"attempts": [{k: v for k, v in a.items() if k != "l1r"} for a in att], "points": {}}
if l2w:
    for plat, plon, key in pts:
        try: res["points"][key] = SV.sample(l2w, plat, plon)
        except Exception as e: res["points"][key] = {"error": str(e)[:150]}
else:
    res["error"] = "no L2W"
shutil.rmtree(out, ignore_errors=True)
print("@@JSON@@" + json.dumps(res, default=str))
