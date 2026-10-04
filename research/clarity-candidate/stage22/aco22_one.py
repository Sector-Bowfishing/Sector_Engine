"""Stage 22: one crop through the FROZEN ACOLITE K4 path, instrumented.
  python aco22_one.py INPUT LAT LON OUTDIR POINTS_JSON OVERRIDES_JSON
INPUT is a SAFE (local, or lazy: lazy.json maps empty band placeholders to /vsis3/ objects) or an ACOLITE L1R NetCDF.
Overrides keys besides ACOLITE settings: "_toa_sub" {band: additive TOA offset to remove from rhot before atmospheric
correction}; "_keep_l1r" path (the crop's L1R is copied there). Output-only ACOLITE switches glint_write_rhog_ref/all are
on. Instrumentation (no change to the computation): acolite_l2r is loaded with three recording lines inserted - the
per-tile DSF band order (b1/b2 = the two lowest-AOT bands) and per-band AOT for each aerosol model, the per-tile model
choice, the selected model and its mean AOT. Disk diagnostics: rhot (L1R), rhos (L2R), aot_550, rhog_ref and per-band
rhog medians over the M0 disk pixels; L2R ac_model / ac_aot_550_mean. The L2W sampling is stage13 sample_variants, unchanged."""
import json, sys, os, shutil, glob
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage12/tools"); sys.path.insert(0, f"{S}/stage13/tools"); sys.path.insert(0, f"{S}/stage11/tools/acolite")
import run_acolite  # ACOLITE source path
import acolite as ac
from osgeo import gdal
inp, lat, lon, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
pts, ov = json.loads(sys.argv[5]), json.loads(sys.argv[6])
SUB = ov.pop("_toa_sub", None); KEEP = ov.pop("_keep_l1r", None)
ov.update({"glint_write_rhog_ref": True, "glint_write_rhog_all": True})
WAVE = {"B01": 443, "B02": 490, "B03": 560, "B04": 665, "B05": 705, "B06": 740, "B07": 783, "B08": 833, "B8A": 865, "B11": 1612, "B12": 2190}
# ---- lazy SAFE: open the /vsis3/ object behind each empty placeholder
if os.path.isdir(inp) and os.path.exists(os.path.join(inp, "lazy.json")):
    MAP = {os.path.normpath(os.path.join(inp, k)): v for k, v in json.load(open(os.path.join(inp, "lazy.json")))["map"].items()}
    _open = gdal.Open
    def _lazy_open(path, *a):
        p = os.path.normpath(os.fspath(path)); return _open(MAP.get(p, path), *a)
    gdal.Open = _lazy_open
# ---- instrumented acolite_l2r (recording lines only)
import importlib; M2 = importlib.import_module("acolite.acolite.acolite_l2r")   # the module (the package re-exports a function of the same name)
src = open(M2.__file__).read(); D = {}
reps = [("                ## remove sorted indices\n                tmp = None\n",
         "                ## remove sorted indices\n                tmp = None\n"
         "                _ACO22.setdefault('dsf', {})[lut] = {'band_list': [str(x) for x in aot_stack[lut]['band_list']], 'b1': np.asarray(aot_stack[lut]['b1']).tolist(), 'b2': np.asarray(aot_stack[lut]['b2']).tolist(), 'aot': np.nan_to_num(np.asarray(aot_stack[lut]['aot'], dtype=float), nan=-1).tolist(), 'all': np.nan_to_num(np.asarray(aot_stack[lut]['all'], dtype=float), nan=-1).tolist()}\n"),
        ("            ## set selected model\n            aot_lut[:] = li_sel\n", "            _ACO22['tile_model'] = np.asarray(aot_lut).tolist()\n            ## set selected model\n            aot_lut[:] = li_sel\n"),
        ("            print('Selected {}, mean aot = {:.2f}'.format(aot_sel_lut, np.nanmean(aot_sel)))\n",
         "            print('Selected {}, mean aot = {:.2f}'.format(aot_sel_lut, np.nanmean(aot_sel)))\n            _ACO22['selected_model'] = str(aot_sel_lut); _ACO22['mean_aot'] = float(np.nanmean(aot_sel))\n")]
for a, b in reps:
    assert src.count(a) == 1, a[:60]
    src = src.replace(a, b)
M2.__dict__["_ACO22"] = D; exec(compile(src, M2.__file__, "exec"), M2.__dict__)
ac.acolite.acolite_l2r = M2.acolite_l2r
# ---- optional additive TOA offsets
def _sub_l1r(f):
    from netCDF4 import Dataset
    with Dataset(f, "a") as nc:
        rh = [n for n in nc.variables if n.startswith("rhot_")]
        for b, v in SUB.items():
            names = [n for n in rh if abs(float(n.split("_")[1]) - WAVE[b]) <= 15]
            assert len(names) == 1, (b, names, rh)
            nc[names[0]][:] = nc[names[0]][:] - v
src_inp = inp
if SUB and inp.endswith(".nc"):
    os.makedirs(out, exist_ok=True); src_inp = os.path.join(out, os.path.basename(inp)); shutil.copy(inp, src_inp); _sub_l1r(src_inp)   # keeps ACOLITE's *_L1R.nc name
elif SUB:
    _orig = ac.sentinel2.l1_convert
    def _wrapped(*a, **k):
        files, setu = _orig(*a, **k)
        for f in files: _sub_l1r(f)
        return files, setu
    ac.sentinel2.l1_convert = _wrapped
import aco12_one as A, sample_variants as SV, sample as SM
from netCDF4 import Dataset
limit = [lat - 0.08, lon - 0.10, lat + 0.08, lon + 0.10]
l2w, att = A.run(src_inp, limit, out, ov)
if not l2w and any("ogr.Open not implemented" in (a.get("error") or "") for a in att):
    l2w, att2 = A.run(src_inp, limit, out, {**ov, "geometry_type": "grids"}); att += att2


def bandmap(nc, prefix):
    out_ = {}
    for v in nc.variables:
        if v.startswith(prefix):
            try: w = float(v[len(prefix):])
            except ValueError: continue
            b = min(WAVE, key=lambda k: abs(WAVE[k] - w))
            if abs(WAVE[b] - w) <= 15: out_[b] = v
    return out_


def levels(l2w_path, plat, plon):
    with Dataset(l2w_path) as nc:
        la, lo = np.array(nc["lat"][:]), np.array(nc["lon"][:])
        m = np.hypot((la - plat) * 111320.0, (lo - plon) * 111320.0 * np.cos(np.radians(plat))) <= 60
        bm = SM._band_map(nc); fl = np.array(nc["l2_flags"][:]).astype("int64")
        fin = np.all([np.isfinite(np.array(nc[bm[b]][:], dtype="float64")) for b in ("B02", "B03", "B04", "B05")], axis=0)
        ok = m & ((fl & SV.DEFAULT) == 0) & fin
        g = {k: float(nc.getncattr(k)) for k in ("sza", "vza", "raa") if k in nc.ncattrs()}
    r = {"n": int(ok.sum()), **g}
    if ok.sum() < 5: return r
    d = os.path.dirname(l2w_path)
    for kind, pre in (("L1R", "rhot_"), ("L2R", "rhos_")):
        if kind == "L1R": f = [src_inp] if src_inp.endswith(".nc") else glob.glob(os.path.join(d, "*_L1R.nc"))
        if kind == "L1R" and not f: f = glob.glob(os.path.join(d, "*_L1R.nc"))
        else: f = [x for x in glob.glob(os.path.join(d, "*L2R*.nc"))]
        if not f: continue
        with Dataset(f[0]) as nc:
            r[pre[:-1]] = {b: float(np.nanmedian(np.array(nc[v][:], dtype="float64")[ok])) for b, v in bandmap(nc, pre).items()}
            if kind == "L2R":
                r["ac_model"] = str(nc.getncattr("ac_model")) if "ac_model" in nc.ncattrs() else None
                r["ac_aot_550_mean"] = float(nc.getncattr("ac_aot_550_mean")) if "ac_aot_550_mean" in nc.ncattrs() else None
                for v in ("aot_550", "rhog_ref"):
                    if v in nc.variables: r[v] = float(np.nanmedian(np.array(nc[v][:], dtype="float64")[ok]))
                r["rhog"] = {b: float(np.nanmedian(np.array(nc[v][:], dtype="float64")[ok])) for b, v in bandmap(nc, "rhog_").items() if v != "rhog_ref"}
    return r


res = {"attempts": [{k: v for k, v in a.items() if k != "l1r"} for a in att], "points": {}, "diag": {}, "toa_sub": SUB}
if l2w:
    for plat, plon, key in pts:
        try: res["points"][key] = SV.sample(l2w, plat, plon); res["diag"][key] = levels(l2w, plat, plon)
        except Exception as e: res["points"][key] = {"error": str(e)[:150]}
    res["files"] = sorted(os.listdir(os.path.dirname(l2w))); res["l2w_path"] = l2w
    if KEEP:
        l1r = glob.glob(os.path.join(out, "*_L1R.nc"))
        if l1r and not inp.endswith(".nc"): os.makedirs(KEEP, exist_ok=True); dst = os.path.join(KEEP, os.path.basename(l1r[0])); shutil.copy(l1r[0], dst); res["kept_l1r"] = dst
else:
    res["error"] = "no L2W"
dsf = D.get("dsf") or {}; sel = D.get("selected_model")
summ = {"selected_model": sel, "mean_aot": D.get("mean_aot"), "tile_model": D.get("tile_model")}
for lut, v in dsf.items():
    bl = v["band_list"]; b1 = np.array(v["b1"]).ravel(); b2 = np.array(v["b2"]).ravel()
    names = lambda arr: [("B" + bl[i].upper().zfill(2) if bl[i].isdigit() else "B" + bl[i].upper()) if 0 <= i < len(bl) else None for i in arr]
    summ[lut] = {"band_list": bl, "b1": names(b1), "b2": names(b2), "aot_tiles": np.array(v["aot"]).ravel().tolist(),
                 "band_aot_tiles": {("B" + bl[k].upper().zfill(2) if bl[k].isdigit() else "B" + bl[k].upper()): np.array(v["all"])[:, :, k].ravel().tolist() for k in range(len(bl))}}
res["dsf"] = summ
shutil.rmtree(out, ignore_errors=True)
print("@@JSON@@" + json.dumps(res, default=str))
