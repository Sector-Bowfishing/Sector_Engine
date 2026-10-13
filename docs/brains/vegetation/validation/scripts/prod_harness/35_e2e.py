"""End-to-end: IMPORTED dws.build_clarity (pass acceptance walk, fallback rule, grass-under-cloud borrow, bed-to-bank strip, fill) on the cached Snohomish
scenes, with ONLY dws.passes (STAC search) stubbed. Frame = production daily.py frame (CLARITY_CELL = 36 m).  usage: 35_e2e.py [lead_days]"""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, datetime as dt, io, contextlib, tempfile, os, warnings
warnings.filterwarnings("ignore")
from PIL import Image
import prod_import as P, loaders as L
dws = P.dws
lead = int(sys.argv[1]) if len(sys.argv) > 1 else 0
H = L.ROOT/"adoption/prod_harness"
res = {}
for nm, geom in L.lakes("snoco").items():
    st, sc = L.stack_scenes("snoco", nm)
    sc = [s for s in sc if s]
    for s in sc: P._STUB[s["id"]] = dict(s["tile"])
    utm = sc[0]["crs"].to_string(); dws.UTM = utm
    z = np.load(H/f"out/cells36_snoco_{nm}.npz", allow_pickle=True)
    survey = dt.date.fromisoformat(str(z["survey"])); until = dt.datetime.combine(survey + dt.timedelta(days=lead), dt.time())
    def passes(search_url, collection, bbox, until_, max_cloud):
        since = until_ - dt.timedelta(days=dws.LOOKBACK_DAYS)
        cand = [s for s in sc if since.date() <= dt.date.fromisoformat(s["date"]) <= until_.date()]
        by = {}
        for s in cand: by.setdefault((s["date"], "sentinel-2a"), []).append({"id": s["id"], "properties": {"eo:cloud_cover": 0, "datetime": s["date"] + "T18:00:00Z"}})
        return [(k, by[k]) for k in sorted(by, key=lambda k: k[0], reverse=True)]
    dws.passes = passes
    fr = dws.Frame(geom, cell=dws.CLARITY_CELL); masks = dws.lake_masks(geom, fr)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "c"); buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                dws.build_clarity(fr, masks, list(geom.bounds), until, out)
            meta = json.load(open(out + ".json"))
            measured = np.array(Image.open(out + ".measured.png"))
            grass_png = measured == 3
            r = dict(pass_date=meta["pass"]["date"], openWaterReadPct=meta["openWaterReadPct"], grassPct=meta["grassPct"], grassToBankPct=meta["fill"]["grassToBankPct"],
                     grassUnderCloudPct=meta["fill"]["grassUnderCloudPct"])
            lake = masks["lake"]; cl = masks["clarity"]
            tfl = np.nan_to_num(z["truth_floating_leaf"]); tsub = np.nan_to_num(z["truth_submerged_assemblage"]) if "truth_submerged_assemblage" in z.files else 0
            tarr = np.nan_to_num(z["truth_arrowhead"]) if "truth_arrowhead" in z.files else 0
            anyv = np.maximum(np.maximum(tfl, tsub), tarr); pos = tfl >= 0.5; neg = anyv < 0.05
            for pop, m in (("whole_lake", lake), ("clarity_40m", cl)):
                tp = int((grass_png & pos & m).sum()); fp = int((grass_png & neg & m).sum()); fn = int((~grass_png & pos & m).sum())
                P_ = tp / max(1, tp + fp); R_ = tp / max(1, tp + fn)
                r[pop] = dict(tp=tp, fp=fp, fn=fn, npos=int((pos & m).sum()), P=round(P_, 3), R=round(R_, 3), F1=round(2 * P_ * R_ / max(1e-9, P_ + R_), 3))
            r["log_tail"] = buf.getvalue().strip().splitlines()[-12:]
        except SystemExit as e:
            r = dict(error=str(e), log_tail=buf.getvalue().strip().splitlines()[-6:])
    res[nm] = r; print(nm, {k: v for k, v in r.items() if k != "log_tail"}, flush=True)
json.dump(res, open(H/f"out/e2e_build_clarity_lead{lead}.json", "w"), indent=1)
