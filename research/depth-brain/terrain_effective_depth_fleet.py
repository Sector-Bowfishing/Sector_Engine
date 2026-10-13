#!/usr/bin/env python3
"""Depth Brain / effective depth (Question B), fleet level.
 (1) which of the 621 directory lakes could receive a bathymetry-independent 'effective depth shift = level - fullPoolFt' (and how many with a usable range);
 (2) sigma propagation: sigma_depth^2 = sigma_ref^2 + sigma_level^2 + sigma_datum^2, with numbers MEASURED from fleet data where possible;
 (3) predicted acres exposed / flooded per foot of pool change (3DEP shoreline proxy, fleet run) with the validated error band.
Inputs: lake_features.csv, full_pool.csv, verified bindings v1+v2, operating_range_by_lake.csv, datum_shift_ngvd29_navd88.csv, history_extension.csv, <RAW>/dem_fleet/*.npz.
Outputs: docs/research/depth-brain/data/fleet_delta_depth_eligibility.json, acres_per_ft_by_lake.csv, sigma_propagation.json.  venv python."""
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from terrain_features import slope_deg

REPO = Path(__file__).resolve().parents[2]
LB = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data")
FP = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/data/full_pool.csv")
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
D = REPO / "docs/research/depth-brain/data"
FT = 3.28084


def safe(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def main():
    feats = pd.read_csv(LB / "lake_features.csv").set_index("id")
    fp = pd.read_csv(FP).drop_duplicates("id").set_index("id")
    v1 = pd.read_csv(LB / "verified_bindings.csv"); v2 = pd.read_csv(LB / "verified_bindings_v2.csv")
    vb = pd.concat([v2, v1[~v1.lake_id.isin(v2.lake_id)]]); vb = vb[vb.binding_status.str.startswith("VERIFIED")].drop_duplicates("lake_id").set_index("lake_id")
    op = pd.read_csv(D / "operating_range_by_lake.csv").set_index("lake")
    out = {}
    L = feats.join(fp[["fullPoolFt", "basis", "conf", "winterPoolFt"]], how="left")
    L["bound"] = L.index.isin(vb.index)
    L["pool_ref_ok"] = (L.basis == "fullPool") & L.conf.isin(["high", "med"]) & L.fullPoolFt.notna()
    L["delta_possible"] = L.bound & L.pool_ref_ok                     # same rule as Lake Brain differenceFromNormalPoolFt (fullPool basis + conf med/high) AND a bound live level
    out["n_lakes"] = int(len(L)); out["n_bound"] = int(L.bound.sum()); out["n_pool_ref_ok"] = int(L.pool_ref_ok.sum()); out["n_delta_possible"] = int(L.delta_possible.sum())
    out["by_operator_delta_possible"] = L[L.delta_possible].operator_family.value_counts().to_dict()
    out["by_regime_delta_possible"] = L[L.delta_possible].regime.value_counts().to_dict()
    # lakes with a pool reference but no bound live level
    out["pool_ref_ok_but_unbound"] = int((L.pool_ref_ok & ~L.bound).sum())
    # operating range classes among delta-possible lakes that have history
    X = L[L.delta_possible].join(op[["days", "full_years", "p05_p95_range_ft", "annual_swing_p99_p01_ft", "draw_p50", "draw_p95", "frac_below_2", "frac_below_5", "datum_flag", "regime_note", "median_minus_fullpool"]], how="left", rsuffix="_op")
    X["has_hist"] = X.p05_p95_range_ft.notna()
    out["delta_possible_with_history_stats"] = int(X.has_hist.sum())
    H = X[X.has_hist & X.datum_flag.isna()].copy()
    out["history_stats_after_datum_QC"] = int(len(H)); out["history_dropped_datum_or_unit"] = int(X.has_hist.sum() - len(H))
    def cls(r):
        return "large(>=4ft)" if r >= 4 else ("moderate(1.5-4ft)" if r >= 1.5 else "small(<1.5ft)")
    H["range_class"] = H.p05_p95_range_ft.map(cls)
    out["range_class_counts"] = H.range_class.value_counts().to_dict()
    out["regime_notes_among_history_lakes"] = H.regime_note.fillna("none").value_counts().to_dict()
    out["range_p05_p95_quantiles"] = {q: round(float(H.p05_p95_range_ft.quantile(q)), 2) for q in (.1, .25, .5, .75, .9)}
    out["annual_swing_quantiles"] = {q: round(float(H.annual_swing_p99_p01_ft.quantile(q)), 2) for q in (.1, .25, .5, .75, .9)}
    out["share_days_drawn_down_gt2ft_median_lake"] = round(float(H.frac_below_2.median()), 3); out["share_days_drawn_down_gt5ft_median_lake"] = round(float(H.frac_below_5.median()), 3)
    out["n_lakes_median_drawdown_gt2ft"] = int((H.draw_p50 > 2).sum()); out["n_lakes_p95_drawdown_gt5ft"] = int((H.draw_p95 > 5).sum()); out["n_lakes_p95_drawdown_gt10ft"] = int((H.draw_p95 > 10).sum())
    by_op = H.groupby("operator_family").agg(n=("p05_p95_range_ft", "size"), median_range=("p05_p95_range_ft", "median"), median_p95_drawdown=("draw_p95", "median")).round(2)
    out["by_operator_with_history"] = by_op.to_dict("index")
    # designed seasonal drawdown (fullPool - winterPool) from the full_pool table
    sw = fp[fp.winterPoolFt.notna() & (fp.basis == "fullPool")].copy(); sw["designed_drawdown_ft"] = sw.fullPoolFt - sw.winterPoolFt
    sw = sw[(sw.designed_drawdown_ft > 0.3) & (sw.designed_drawdown_ft < 200)]
    out["designed_winter_drawdown_n"] = int(len(sw)); out["designed_winter_drawdown_quantiles"] = {q: round(float(sw.designed_drawdown_ft.quantile(q)), 1) for q in (.1, .25, .5, .75, .9)}
    tva = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Norris Lake|TN", "Douglas Lake|TN", "Kentucky Lake|TN", "Kentucky Lake|KY"]
    out["designed_drawdown_examples"] = {l: round(float(sw.loc[l, "designed_drawdown_ft"]), 1) for l in tva if l in sw.index}
    # ----- sigma_level measured: HADS vs binding agreement from the plan thread, resolution
    he = pd.read_csv(LB / "history_extension.csv")
    mae = he.liveMaeFt.dropna()
    out["sigma_level_evidence"] = dict(live_vs_binding_mae_ft_n=int(len(mae)), median=round(float(mae.median()), 3), p90=round(float(mae.quantile(.9)), 3), max=round(float(mae.max()), 3))
    # ----- sigma_pool: how well does fullPoolFt agree with the lake's own upper level? (p95 of 2016-2025 daily level - fullPool), robust spread by confidence
    O = op.dropna(subset=["fullPoolFt"]).copy(); O["p95_minus_fp"] = O.p95 - O.fullPoolFt
    O = O[O.datum_flag.isna()]; O = O[O.regime_note.isna()]       # exclude flood-pool-excursion and rarely-full lakes: they are not a test of the pool figure
    rob = lambda s: float(1.4826 * np.median(np.abs(s - np.median(s)))) if len(s) > 4 else np.nan
    out["sigma_pool_evidence"] = {c: dict(n=int(len(g)), median_p95_minus_fullpool=round(float(g.p95_minus_fp.median()), 2), robust_sd_ft=round(rob(g.p95_minus_fp), 2), iqr_ft=[round(float(g.p95_minus_fp.quantile(.25)), 2), round(float(g.p95_minus_fp.quantile(.75)), 2)])
                                 for c, g in O.groupby("fp_conf")}
    # ----- sigma_datum measured
    ds = pd.read_csv(D / "datum_shift_ngvd29_navd88.csv").dropna(subset=["shift_ft_ngvd29_to_navd88"])
    a = ds.shift_ft_ngvd29_to_navd88.abs()
    out["datum_shift_ngvd29_to_navd88"] = dict(n=int(len(ds)), abs_median=round(float(a.median()), 2), abs_p75=round(float(a.quantile(.75)), 2), abs_p90=round(float(a.quantile(.9)), 2), abs_max=round(float(a.max()), 2),
                                               share_gt_0_5ft=round(float((a > .5).mean()), 3), share_gt_1ft=round(float((a > 1).mean()), 3), rms=round(float(np.sqrt((a ** 2).mean())), 2),
                                               by_operator={k: dict(n=int(len(g)), abs_median=round(float(g.shift_ft_ngvd29_to_navd88.abs().median()), 2), abs_max=round(float(g.shift_ft_ngvd29_to_navd88.abs().max()), 2)) for k, g in ds.groupby("operator_family")})
    # ----- acres per ft from the fleet DEM run
    rows = []
    for lid in L.index:
        fpn = RAW / "dem_fleet" / (safe(lid) + ".npz")
        if not fpn.exists(): continue
        d = np.load(fpn)
        z = d["z"]; ok = np.isfinite(z).all(axis=1) & (z > -100).all(axis=1)
        if ok.sum() < 40: continue
        s = slope_deg(z[ok], 10, 60, {10: 0, 60: 1})
        run = float(np.median(np.clip(1 / np.tan(np.radians(np.clip(s, .2, 89))), 0, 500)))
        a_km2 = L.loc[lid, "area_km2"]; p_km = L.loc[lid, "perim_km"]
        if not np.isfinite(a_km2) or not np.isfinite(p_km) or a_km2 <= 0: continue
        rel = p_km * 1000 * FT * run / (a_km2 * 1e6 * 10.7639)
        ref_km2 = L.loc[lid, "area_ref_km2"] if np.isfinite(L.loc[lid, "area_ref_km2"]) and L.loc[lid, "area_ref_km2"] > 0 else a_km2      # full-pool reference area (NID / HydroLAKES); the Sector polygon is often a lower-stage extent
        rows.append(dict(id=lid, area_ac=ref_km2 * 247.105, poly_area_ac=a_km2 * 247.105, slope_med_deg=float(np.median(s)), frac_lt2=float((s < 2).mean()), run_ft_per_ft=run, rel_per_ft_pred=rel, acres_per_ft_pred=rel * ref_km2 * 247.105, n_pts=int(ok.sum()),
                         fullPoolFt=L.loc[lid, "fullPoolFt"], delta_possible=bool(L.loc[lid, "delta_possible"])))
    A = pd.DataFrame(rows)
    if len(A):
        A["rel_per_ft_pred_capped"] = A.rel_per_ft_pred.clip(upper=0.15)
        A["acres_per_ft_pred_capped"] = A.rel_per_ft_pred_capped * A.area_ac
        A.round(4).to_csv(D / "acres_per_ft_by_lake.csv", index=False)
        q = lambda S, col: {str(k): round(float(S[col].quantile(k)), 4 if "rel" in col else 0) for k in (.1, .25, .5, .75, .9)}
        for nm, S in (("acres_per_ft_all_with_dem", A), ("acres_per_ft_delta_possible", A[A.delta_possible])):
            out[nm] = dict(n=int(len(S)), rel_per_ft_quantiles=q(S, "rel_per_ft_pred_capped"), acres_per_ft_quantiles=q(S, "acres_per_ft_pred_capped"),
                           share_rel_per_ft_gt_0_03=round(float((S.rel_per_ft_pred_capped > .03).mean()), 3), share_capped=round(float((S.rel_per_ft_pred > .15).mean()), 3))
        out["acres_per_ft_delta_possible"]["n_of_339"] = int(A.delta_possible.sum())
        out["acres_per_ft_pilots"] = {l: dict(rel_per_ft=round(float(A.set_index("id").loc[l, "rel_per_ft_pred_capped"]), 4), acres_per_ft=round(float(A.set_index("id").loc[l, "acres_per_ft_pred_capped"]), 0)) for l in ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC", "Lake Fork Reservoir|TX", "Lake Texoma|TX", "Kentucky Lake|TN", "Norris Lake|TN"] if l in set(A.id)}
    # ----- sigma propagation scenarios (ft).  MEASURED: contour interval (terrain_contour_interval_error), Landsat MAE (sat_hypso_validation), datum RMS (NCAT fleet), live-vs-binding MAE.
    #       ASSUMED (flagged): survey-grade sigma_ref 0.3 ft, operator pool figure 0.25 ft (high) / 1 ft (med) / 3 ft (low), gauge 0.1 ft, NCAT residual 0.23 ft (VERTCON3 sigma 0.069 m).
    ci = json.load(open(D / "contour_interval_error.json"))["summary"] if (D / "contour_interval_error.json").exists() else {}
    sat = json.load(open(D / "sat_hypso_validation.json")) if (D / "sat_hypso_validation.json").exists() else []
    rmse = lambda *a: float(np.sqrt(sum(x ** 2 for x in a)))
    sat_mae = float(np.mean([r["mae_ft"] for r in sat])) if sat else 1.0
    sc = [
        ("delta only (level - fullPool), same datum, pool high-conf", dict(ref=0.0, level=0.1, pool=0.25, datum=0.0)),
        ("delta only, pool sigma at the measured upper bound (robust SD of p95 level minus fullPool, 149 high-conf lakes)", dict(ref=0.0, level=0.1, pool=out["sigma_pool_evidence"]["high"]["robust_sd_ft"], datum=0.0)),
        ("delta only, pool med-conf", dict(ref=0.0, level=0.1, pool=1.0, datum=0.0)),
        ("delta only, pool low-conf / natural-lake reference", dict(ref=0.0, level=0.1, pool=3.0, datum=0.0)),
        ("absolute depth, survey-grade contours (1-ft, TWDB-type), datum reconciled, pool high", dict(ref=0.3, level=0.1, pool=0.25, datum=0.0)),
        ("absolute depth, 2-ft contours (measured interpolation error)", dict(ref=ci.get("k2", {}).get("rmse_ft", 0.28), level=0.1, pool=0.25, datum=0.23)),
        ("absolute depth, 5-ft contours (state lake map; measured)", dict(ref=ci.get("k5", {}).get("rmse_ft", 1.3), level=0.1, pool=0.25, datum=0.23)),
        ("absolute depth, 10-ft contours (measured)", dict(ref=ci.get("k10", {}).get("rmse_ft", 2.8), level=0.1, pool=0.25, datum=0.23)),
        ("absolute depth, survey contours but datum NOT reconciled (fleet NGVD29/NAVD88 RMS)", dict(ref=0.3, level=0.1, pool=0.25, datum=out["datum_shift_ngvd29_to_navd88"]["rms"])),
        ("absolute depth, survey contours, Western (USBR-type) lake with unreconciled datum", dict(ref=0.3, level=0.1, pool=0.25, datum=out["datum_shift_ngvd29_to_navd88"]["by_operator"]["USBR"]["abs_median"])),
        ("Landsat drawdown-derived depth (measured MAE across 5 TX lakes)", dict(ref=sat_mae, level=0.1, pool=0.25, datum=0.0)),
        ("absolute depth, modeled bathymetry (GLOBathy-type, Dmax-driven)", dict(ref=3.0, level=0.1, pool=0.25, datum=0.0)),
    ]
    out["sigma_propagation_ft"] = [dict(scenario=n, **{k: round(v, 2) for k, v in c.items()}, sigma_depth=round(rmse(*c.values()), 2),
                                        claim_flat_4ft_now_2ft_resolvable=bool(rmse(*c.values()) <= 0.7)) for n, c in sc]
    (D / "sigma_propagation.json").write_text(json.dumps(out["sigma_propagation_ft"], indent=1))
    (D / "fleet_delta_depth_eligibility.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
