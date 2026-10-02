"""Stage 12: run ACOLITE once on one crop with setting overrides, sample the points, print JSON (acolite venv).
  python aco12_one.py INPUT LAT LON OUTDIR POINTS_JSON OVERRIDES_JSON [--keep]
INPUT is a SAFE or an ACOLITE L1R NetCDF. The output directory is deleted afterwards unless --keep."""
import json, os, sys, time, shutil
S11 = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage11"
sys.path.insert(0, f"{S11}/tools/acolite")
import run_acolite as RA, sample as SM
import acolite as ac


def run(inp, limit, out, overrides):
    os.makedirs(out, exist_ok=True)
    attempts, l2w = [], None
    for estimate in ("tiled", "fixed"):
        st = dict(RA.BASE_SETTINGS); st.update(overrides)
        st.update({"inputfile": inp, "output": out, "limit": limit, "region_name": os.path.basename(out), "dsf_aot_estimate": estimate})
        t0, err, processed = time.time(), None, {}
        try:
            ret = ac.acolite.acolite_run(settings=st)
            processed = ret[0] if isinstance(ret, tuple) else ret
            processed = processed if isinstance(processed, dict) else {}
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        l2w = RA._l2w_from(processed)
        attempts.append({"estimate": estimate, "s": round(time.time() - t0, 1), "error": err, "l2w": l2w, "l1r": [f for k in processed for f in processed[k].get("l1r", [])]})
        if l2w: break
    return l2w, attempts


if __name__ == "__main__":
    inp, lat, lon, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    pts, ov = json.loads(sys.argv[5]), json.loads(sys.argv[6])
    keep = "--keep" in sys.argv
    limit = [lat - 0.08, lon - 0.10, lat + 0.08, lon + 0.10]
    l2w, attempts = run(inp, limit, out, ov)
    if not l2w and any("ogr.Open not implemented" in (a.get("error") or "") for a in attempts):
        # addendum D: older L1C baselines keep detector footprints as GML, which the GDAL stand-in cannot read;
        # fall back to ACOLITE's angle-grid geometry for this crop only
        l2w, att2 = run(inp, limit, out, {**ov, "geometry_type": "grids"})
        attempts += [{**a, "geometry_type": "grids"} for a in att2]
    res = {"attempts": [{k: v for k, v in a.items() if k != "l1r"} for a in attempts], "points": {}, "l1r": attempts[-1]["l1r"] if attempts else []}
    if l2w:
        for plat, plon, key in pts:
            try:
                res["points"][key] = SM.sample(l2w, plat, plon, radius_m=60)
            except Exception as e:
                res["points"][key] = {"error": str(e)[:120]}
    else:
        res["error"] = (attempts[-1]["error"] if attempts else "no attempt") or "no L2W"
    if not keep:
        shutil.rmtree(out, ignore_errors=True)
    print("@@JSON@@" + json.dumps(res, default=str))
