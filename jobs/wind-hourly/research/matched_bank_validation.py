"""Matched per-bank validation of ESTIMATED vs AUDITED exposure (docs/brains/wind/WIND_VALIDATION_PHASE_PREREG.md section M).

Every estimate is evaluated AT THE AUDITED BANK STANDOFF COORDINATES (same points, same 16 wind directions, same 9-ray +-12 deg
effective fetch, same frozen CEM at 12 mph), so differences come only from the geometry/method, not from where banks were sampled.
  M1  same NHD polygon the audited table was built from (7 lakes)       -> method match
  M2  Lake Brain engine polygon (all audited lakes with one)            -> source match (the real ESTIMATED-tier test)
  M2C M2 with the shipped conservative PROTECTED policy (exposure.label_bank_estimated, fetch x 1.5)

Run 1 (vocabulary v1: lee-facing banks PROTECTED unless chop >= 4) is kept in matched_bank_run1.json. Run 2 (this file as shipped:
PROTECTED needs chop <= 2) is a POST-HOC SAFETY FIX on the same data and is NOT an independent confirmation.

  python research/matched_bank_validation.py OUT.json [--max-banks 1000]"""
import base64, glob, gzip, json, math, os, struct, sys
import numpy as np
from scipy import ndimage
from scipy.stats import spearmanr
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shapely.geometry import shape
from sector_wind import bowfishing as BF
from sector_wind.brain import estimate as ES
from sector_wind.brain import exposure as EX

MPH12 = 12 * 0.44704
OFFS = tuple(range(-12, 13, 3))                      # 9 rays at 3 deg across +-12
DIRS = [22.5 * i for i in range(16)]
HOME = os.path.expanduser("~")
CACHE = HOME + "/Library/Caches/sector-wind/"
ENGINE = HOME + "/Desktop/Development/Sector_Research_Data/lake-brain/geometry/engine_polygons_599.geojson.gz"
ASSETS = HOME + "/Desktop/Development/iOS/sector-wind/Sector/Assets.xcassets/FishIntel/Wind/*/*.windfetch.json.gz"
NHD_SAME = {"Guntersville|AL": CACHE + "fetch-build/nhd/guntersville.geojson", "Wheeler|AL": CACHE + "fetch-build/nhd/wheeler.geojson",
            "Wilson|AL": CACHE + "fetch-build/nhd/wilson.geojson", "Pickwick Lake|TN": CACHE + "fetch-build/nhd/pickwick.geojson",
            "Aleknagik|AK": CACHE + "fetch-build/nhd-national/aleknagik-ak.geom.json",
            "Coventry Lake (Wangumbaug)|CT": CACHE + "fetch-build/nhd-national/coventry-lake-wangumbaug-ct.geom.json",
            "Salton Sea|CA": CACHE + "fetch-build/nhd-national/salton-sea-ca.geom.json"}
DEV = {"guntersville": "Guntersville|AL", "wheeler": "Wheeler|AL", "wilson": "Wilson|AL", "pickwick": "Pickwick Lake|TN"}


def audited_tables():
    out = {}
    for f in glob.glob(CACHE + "national-fetch/tables/*.gz") + glob.glob(ASSETS):
        d = json.load(gzip.open(f))
        lid = (d["directory"]["name"] + "|" + d["directory"]["state"]) if d.get("directory") else DEV.get(d.get("lake"))
        if lid is None:
            continue
        raw = base64.b64decode(d["tableBase64"]); n = len(raw) // 2
        out[lid] = {"banks": d["banks"], "table": np.array(struct.unpack(f"<{n}H", raw), dtype=float).reshape(len(d["banks"]), 120) * 10.0}
    return out


def load_poly(path_or_feature):
    if isinstance(path_or_feature, str):
        j = json.load(open(path_or_feature)); g = j["features"][0]["geometry"] if j.get("type") == "FeatureCollection" else j
        geom = shape(g)
    else:
        geom = shape(path_or_feature["geometry"])
    return ES.clean_geometry(geom)


def chop12(f):
    return BF.chop_class(BF.cem(MPH12, f, 6 * 3600))


def evaluate(lake_id, A, geom, max_banks):
    mask, res, ref = ES.rasterize(geom)
    lon0, lat1, kx, ky = ref
    banks, table = A["banks"], A["table"]
    ok_idx = [i for i, b in enumerate(banks) if not b.get("belowResolution") and b.get("standoff") and b.get("anchor")]
    stride = max(1, len(ok_idx) // max_banks); sel = ok_idx[::stride]
    px = np.array([(banks[i]["standoff"][1] - lon0) * kx / res + 1 for i in sel]); py = np.array([(lat1 - banks[i]["standoff"][0]) * ky / res + 1 for i in sel])
    H, W = mask.shape
    # place on water: standoff cell, else nearest water cell within 2 cells, else UNKNOWN (never PROTECTED)
    water = np.zeros(len(sel), bool); sx, sy = px.copy(), py.copy()
    for k in range(len(sel)):
        x, y = int(round(px[k])), int(round(py[k]))
        best = None
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H and mask[yy, xx]:
                    d = dx * dx + dy * dy
                    if best is None or d < best[0]:
                        best = (d, xx, yy)
        if best:
            water[k] = True; sx[k], sy[k] = best[1], best[2]
    sm = ndimage.gaussian_filter(mask.astype(float), sigma=3.0); gy, gx = np.gradient(sm)
    face_est = np.full(len(sel), np.nan)
    for k in range(len(sel)):
        if water[k]:
            e, n = gx[int(sy[k]), int(sx[k])], -gy[int(sy[k]), int(sx[k])]
            if math.hypot(e, n) > 1e-6:
                face_est[k] = (math.degrees(math.atan2(e, n)) + 360) % 360
    face_aud = np.array([EX.facing_deg(banks[i]) if EX.facing_deg(banks[i]) is not None else np.nan for i in sel])
    wi = np.nonzero(water)[0]
    eff_est = np.full((len(sel), 16), np.nan)
    for j, b in enumerate(DIRS):
        if len(wi):
            eff_est[wi, j] = np.mean([ES.ray_distances(mask, res, sx[wi], sy[wi], (b + o) % 360) for o in OFFS], axis=0)
    eff_aud = np.array([[BF.nine_ray(table[i], b) for b in DIRS] for i in sel])
    # label cells
    L = {"aud": [], "est": [], "estC": [], "estFace": [], "estFaceC": []}
    hi_aud, hi_est, exposed_aud, exp_label_est, exp_label_estC = [], [], [], [], []
    spear, unk = [], 0
    ang = EX.angdiff
    for j, b in enumerate(DIRS):
        for k in range(len(sel)):
            fa = face_aud[k]
            ca = chop12(eff_aud[k, j])
            la = EX.label_bank(b, 12, None if np.isnan(fa) else fa, ca)["label"]
            if np.isnan(eff_est[k, j]) or np.isnan(fa):
                unk += 1; continue
            ce = chop12(eff_est[k, j]); cc = chop12(eff_est[k, j] * 1.5)
            le = EX.label_bank(b, 12, fa, ce)["label"]
            lf = EX.label_bank(b, 12, None if np.isnan(face_est[k]) else face_est[k], ce)["label"]
            lfc = EX.label_bank_estimated(b, 12, None if np.isnan(face_est[k]) else face_est[k], ce, cc)["label"]   # the pipeline an ESTIMATED lake would really publish
            lc = EX.label_bank_estimated(b, 12, fa, ce, cc)["label"]       # shipped ESTIMATED policy (M2-C)
            L["aud"].append(la); L["est"].append(le); L["estC"].append(lc); L["estFace"].append(lf); L["estFaceC"].append(lfc)
            hi_aud.append(ca >= 4); hi_est.append(ce >= 4); exposed_aud.append(ca >= 3)
    A_, E_, C_, F_, G_ = (np.array(L[k]) for k in ("aud", "est", "estC", "estFace", "estFaceC"))
    ex = np.array(exposed_aud); ha = np.array(hi_aud); he = np.array(hi_est)
    kn = (A_ != "UNKNOWN")
    out = {"lake": lake_id, "banksAudited": len(banks), "banksSampled": len(sel), "rasterM": round(res, 1), "standoffNotWater": int((~water).sum()),
           "cellsCompared": int(kn.sum()), "cellsUnknownEstimate": int(unk),
           "labelAgreement": float((A_[kn] == E_[kn]).mean()) if kn.any() else None, "labelAgreementConservative": float((A_[kn] == C_[kn]).mean()) if kn.any() else None,
           "labelAgreementEstFacing": float((A_[kn] == F_[kn]).mean()) if kn.any() else None,
           "labelAgreementShippedPipeline(est facing + conservative)": float((A_[kn] == G_[kn]).mean()) if kn.any() else None,
           "falseProtectedShippedPipeline(audited chop>=3)": float(((G_ == "PROTECTED") & ex).sum() / ex.sum()) if ex.sum() else None,
           "falseProtectedShippedPipeline_vsAuditedDirectCross": float(((G_ == "PROTECTED") & np.isin(A_, ["DIRECT", "CROSS"])).sum() / max(np.isin(A_, ["DIRECT", "CROSS"]).sum(), 1)),
           "confusionShippedPipeline": [[int(((A_ == a) & (G_ == e)).sum()) for e in ["DIRECT", "CROSS", "PROTECTED"]] for a in ["DIRECT", "CROSS", "PROTECTED"]],
           "highFetchPrecision": float((ha & he).sum() / he.sum()) if he.sum() else None, "highFetchRecall": float((ha & he).sum() / ha.sum()) if ha.sum() else None,
           "highFetchAuditedCells": int(ha.sum()),
           "falseProtected(audited chop>=3)": float(((E_ == "PROTECTED") & ex).sum() / ex.sum()) if ex.sum() else None,
           "falseProtectedConservative": float(((C_ == "PROTECTED") & ex).sum() / ex.sum()) if ex.sum() else None,
           "falseProtected_vsAuditedDirectCross": float(((E_ == "PROTECTED") & np.isin(A_, ["DIRECT", "CROSS"])).sum() / max(np.isin(A_, ["DIRECT", "CROSS"]).sum(), 1)),
           "falseProtectedConservative_vsAuditedDirectCross": float(((C_ == "PROTECTED") & np.isin(A_, ["DIRECT", "CROSS"])).sum() / max(np.isin(A_, ["DIRECT", "CROSS"]).sum(), 1)),
           "exposedCells": int(ex.sum()),
           "conservativeSharePROTECTED": {"audited": float((A_ == "PROTECTED").mean()), "est": float((E_ == "PROTECTED").mean()), "estC": float((C_ == "PROTECTED").mean())}}
    labs = ["DIRECT", "CROSS", "PROTECTED"]
    out["confusion_rows_audited_cols_estimated"] = [[int(((A_ == a) & (E_ == e)).sum()) for e in labs] for a in labs]
    out["confusion_rows_audited_cols_estimatedConservative"] = [[int(((A_ == a) & (C_ == e)).sum()) for e in labs] for a in labs]
    ok = ~np.isnan(eff_est).any(axis=1)
    sp = []
    for j in range(16):
        a, e = eff_aud[ok, j], eff_est[ok, j]
        if len(a) > 20 and a.std() > 0 and e.std() > 0:
            sp.append(spearmanr(a, e)[0])
    out["spearmanMedian"] = float(np.median(sp)) if sp else None
    da = np.argmax(np.nanmedian(eff_aud[ok], axis=0)) if ok.any() else None; de = np.argmax(np.nanmedian(eff_est[ok], axis=0)) if ok.any() else None
    out["dominantDirAudited"] = None if da is None else DIRS[int(da)]; out["dominantDirEstimated"] = None if de is None else DIRS[int(de)]
    out["dominantWithin22_5"] = None if da is None else bool(ang(DIRS[int(da)], DIRS[int(de)]) <= 22.5)
    both = ~np.isnan(face_est) & ~np.isnan(face_aud)
    fe = np.array([ang(a, b) for a, b in zip(face_aud[both], face_est[both])])
    out["facingErrMedianDeg"] = float(np.median(fe)) if len(fe) else None; out["facingWithin45"] = float((fe <= 45).mean()) if len(fe) else None
    lr = np.log((np.nanmedian(eff_est[ok]) + 1) / (np.nanmedian(eff_aud[ok]) + 1)) if ok.any() else None
    out["logRatioMedianFetch"] = None if lr is None else float(lr)
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return float(np.median(xs)) if xs else None


def summarize(rs, tag):
    w = lambda k: [r[k] for r in rs]
    cells = sum(r["cellsCompared"] for r in rs)
    ex = sum(r["exposedCells"] for r in rs)
    pool = lambda num, den: sum(r[num] * r[den] for r in rs if r[num] is not None) / max(sum(r[den] for r in rs if r[num] is not None), 1)
    s = {"set": tag, "lakes": len(rs), "cells": cells, "unknownEstimateCells": sum(r["cellsUnknownEstimate"] for r in rs),
         "labelAgreement_median": med(w("labelAgreement")), "labelAgreement_pooled": pool("labelAgreement", "cellsCompared"),
         "labelAgreementConservative_median": med(w("labelAgreementConservative")), "labelAgreementEstFacing_median": med(w("labelAgreementEstFacing")),
         "highFetchPrecision_median": med(w("highFetchPrecision")), "highFetchRecall_median": med(w("highFetchRecall")),
         "spearman_median": med(w("spearmanMedian")),
         "dominantWithin22_5_share": float(np.mean([r["dominantWithin22_5"] for r in rs if r["dominantWithin22_5"] is not None])) if rs else None,
         "facingErrMedianDeg": med(w("facingErrMedianDeg")), "facingWithin45_median": med(w("facingWithin45")),
         "falseProtected_pooled": pool("falseProtected(audited chop>=3)", "exposedCells"), "falseProtectedConservative_pooled": pool("falseProtectedConservative", "exposedCells"),
         "falseProtected_median": med(w("falseProtected(audited chop>=3)")), "falseProtectedConservative_median": med(w("falseProtectedConservative")),
         "falseProtected_vsDirectCross_pooled": pool("falseProtected_vsAuditedDirectCross", "cellsCompared"),
         "falseProtectedConservative_vsDirectCross_pooled": pool("falseProtectedConservative_vsAuditedDirectCross", "cellsCompared"),
         "labelAgreementShippedPipeline_median": med(w("labelAgreementShippedPipeline(est facing + conservative)")),
         "falseProtectedShippedPipeline_pooled": pool("falseProtectedShippedPipeline(audited chop>=3)", "exposedCells"),
         "falseProtectedShippedPipeline_vsDirectCross_pooled": pool("falseProtectedShippedPipeline_vsAuditedDirectCross", "cellsCompared"),
         "exposedCells": ex, "logRatioMedianFetch_median": med(w("logRatioMedianFetch"))}
    for key in ("confusion_rows_audited_cols_estimated", "confusion_rows_audited_cols_estimatedConservative"):
        M = np.sum([r[key] for r in rs], axis=0)
        s[key] = M.tolist()
        s[key.replace("confusion", "perClass")] = {lab: {"recall": float(M[i, i] / max(M[i].sum(), 1)), "precision": float(M[i, i] / max(M[:, i].sum(), 1)), "auditedCells": int(M[i].sum())} for i, lab in enumerate(["DIRECT", "CROSS", "PROTECTED"])}
    return s


if __name__ == "__main__":
    out = sys.argv[1]; maxb = int(sys.argv[sys.argv.index("--max-banks") + 1]) if "--max-banks" in sys.argv else 1000
    T = audited_tables()
    eng = {f["properties"]["id"]: f for f in json.load(gzip.open(ENGINE))["features"]}
    m1, m2, per = [], [], {}
    for lid, A in sorted(T.items()):
        for tag, src in (("M1", NHD_SAME.get(lid)), ("M2", eng.get(lid))):
            if src is None:
                continue
            try:
                geom = load_poly(src)
                r = evaluate(lid, A, geom, maxb)
            except Exception as e:
                print("ERR", tag, lid, repr(e)[:120], flush=True); continue
            (m1 if tag == "M1" else m2).append(r); per[f"{tag}|{lid}"] = r
            print(tag, lid, r["cellsCompared"], round(r["labelAgreement"] or 0, 3), "fP", r["falseProtected(audited chop>=3)"], "fPc", r["falseProtectedConservative"], flush=True)
    res = {"M1": summarize(m1, "M1 same NHD polygon"), "M2": summarize(m2, "M2 engine polygon"), "perLake": per}
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ("M1", "M2")}, indent=1, default=float))
