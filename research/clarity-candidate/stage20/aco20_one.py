"""Stage 20: one crop through the FROZEN ACOLITE path (stage13/tools/aco13_one.py: aco12_one.run with the given overrides,
the grids fallback, sample_variants.sample on the L2W - unchanged), plus a diagnostic read of the SAME disk pixels in the
L1R (rhot, top of atmosphere) and L2R (rhos, surface) products before they are deleted, so a satellite difference can be
located: radiometry, atmospheric correction, or water-reflectance processing.
  python aco20_one.py INPUT LAT LON OUTDIR POINTS_JSON OVERRIDES_JSON"""
import json, sys, os, shutil, glob
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage12/tools"); sys.path.insert(0, f"{S}/stage13/tools"); sys.path.insert(0, f"{S}/stage11/tools/acolite")
import aco12_one as A, sample_variants as SV, sample as SM
from netCDF4 import Dataset
inp, lat, lon, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
pts, ov = json.loads(sys.argv[5]), json.loads(sys.argv[6])
limit = [lat - 0.08, lon - 0.10, lat + 0.08, lon + 0.10]
l2w, att = A.run(inp, limit, out, ov)
if not l2w and any("ogr.Open not implemented" in (a.get("error") or "") for a in att):
    l2w, att2 = A.run(inp, limit, out, {**ov, "geometry_type": "grids"}); att += att2


def levels(l2w_path, plat, plon):
    """Medians of rhot (L1R) and rhos (L2R) over the M0 disk pixels of the L2W (default mask, finite B02-B05), and geometry."""
    with Dataset(l2w_path) as nc:
        la, lo = np.array(nc["lat"][:]), np.array(nc["lon"][:])
        m = np.hypot((la - plat) * 111320.0, (lo - plon) * 111320.0 * np.cos(np.radians(plat))) <= 60
        bm = SM._band_map(nc); fl = np.array(nc["l2_flags"][:]).astype("int64")
        fin = np.all([np.isfinite(np.array(nc[bm[b]][:], dtype="float64")) for b in ("B02", "B03", "B04", "B05")], axis=0)
        ok = m & ((fl & SV.DEFAULT) == 0) & fin
        g = {k: float(nc.getncattr(k)) for k in ("sza", "vza", "raa") if k in nc.ncattrs()}
    if ok.sum() < 5: return {"n": int(ok.sum()), **g}
    r = {"n": int(ok.sum()), **g}
    d = os.path.dirname(l2w_path)
    for kind, pre in (("L1R", "rhot_"), ("L2R", "rhos_")):
        f = glob.glob(os.path.join(d, f"*_{kind}.nc"))
        if not f: continue
        with Dataset(f[0]) as nc:
            bm = SM._band_map(nc, prefix=pre)
            r[pre[:-1]] = {b: float(np.nanmedian(np.array(nc[v][:], dtype="float64")[ok])) for b, v in bm.items()}
    return r


res = {"attempts": [{k: v for k, v in a.items() if k != "l1r"} for a in att], "points": {}, "diag": {}}
if l2w:
    for plat, plon, key in pts:
        try:
            res["points"][key] = SV.sample(l2w, plat, plon)
            res["diag"][key] = levels(l2w, plat, plon)
        except Exception as e:
            res["points"][key] = {"error": str(e)[:150]}
else:
    res["error"] = "no L2W"
shutil.rmtree(out, ignore_errors=True)
print("@@JSON@@" + json.dumps(res, default=str))
