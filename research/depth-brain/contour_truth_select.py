#!/usr/bin/env python3
"""Depth Brain / contour truth, step 4: quality flags, one best source per lake, anchors, lake type -> data/contour_truth_lakes.csv + data/contour_truth_summary.json.

Quality tier (data-quality flag):
  A  whole lake (convex-hull coverage >= 0.85) and (ladder gaps <= 3 ft, or 5-ft ladder on a lake with contours to >= 25 ft)   [TWDB tables count as A]
  B  whole lake with 10-ft ladder on a lake >= 40 ft deep, OR coverage 0.65-0.85 with an A-grade ladder
  C  anything else (partial lake, >10 ft steps, band-only, datum uncertain) – reported but excluded from validation
valid_gt10: the >10 ft share is only meaningful if contours reach >= 15 ft or an independent max-depth anchor says the lake is that shallow."""
import json
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain/data"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
FEAT = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv")
LICENCE = {  # redistribution notes
    "FL": "FL FWC metadata: do not redistribute – internal research use only", "TWDB": "TWDB: not for navigation/fishing; public domain data, check before shipping raw contours",
    "MN": "MN DNR: public (Minnesota Geospatial Commons), attribution", "MI": "MI DNR/IFR: public, partial digitized", "default": "state agency open data; no raw contour redistribution implied; review before shipping to app users"}


def ladder_class(g):
    if not np.isfinite(g): return "none"
    return "fine" if g <= 3.01 else "std5" if g <= 5.01 else "coarse10" if g <= 10.01 else "gappy"


def main():
    p = pd.read_csv(RAW / "depth-brain/contour/truth_pairs.csv")
    p = p[p.cov_raster.notna() & (p.n_lines > 0)].copy()
    p["method"] = "contour_interp"
    tw = pd.read_csv(D / "contour_twdb_truth.csv"); tw["method"] = "area_capacity_table"
    p = pd.concat([p, tw], ignore_index=True)
    sa = pd.read_csv(D / "contour_survey_area.csv")[["lakeId", "src", "ratio", "ratio_max_group"]]
    p = p.merge(sa, on=["lakeId", "src"], how="left")
    # reliable ratio only in [0.3, 3]; take the ratio closest to 1 of (sum, largest group) – conservative towards the lake being fine
    r1, r2 = p.ratio, p.ratio_max_group.fillna(p.ratio)
    pick = np.where((r1 - 1).abs() <= (r2 - 1).abs(), r1, r2)
    p["area_ratio_poly_to_survey"] = np.where((pick >= 0.3) & (pick <= 3), pick, np.nan)
    p["ladder"] = p.max_gap_to10_ft.map(ladder_class)
    p["hull_class"] = pd.cut(p.cov_hull, [-1, 0.65, 0.85, 2], labels=["partial", "most", "full"]).astype(str)
    # --- independent max-depth anchors (agency / supplied observed / EPA NLA index-site depth = lower bound)
    a = pd.read_csv(D / "contour_anchors_verified.csv")
    best_anchor = {}
    for lid, sub in a.groupby("lakeId"):
        nn = sub[sub.anchor_src != "EPA_NLA2007_DEPTHMAX"]
        r = (nn if len(nn) else sub).sort_values("depth_ft", ascending=False).iloc[0]
        nla = sub[sub.anchor_src == "EPA_NLA2007_DEPTHMAX"].depth_ft
        best_anchor[lid] = dict(anchor_max_ft=r.depth_ft, anchor_src=r.anchor_src, anchor_nla_ft=float(nla.iloc[0]) if len(nla) else np.nan)
    A = pd.DataFrame.from_dict(best_anchor, orient="index"); A.index.name = "lakeId"
    p = p.merge(A.reset_index(), on="lakeId", how="left")
    gt = pd.read_csv(D / "globathy_truth_comparison.csv")[["id", "max_depth_m"]].rename(columns={"id": "lakeId"})
    gt["supplied_max_ft"] = gt.max_depth_m * 3.28084
    p = p.merge(gt[["lakeId", "supplied_max_ft"]], on="lakeId", how="left")
    ref = p[["anchor_max_ft", "supplied_max_ft"]].max(axis=1)           # reference max depth (agency / supplied / NLA when it is the only anchor)
    p["ref_max_ft"] = ref
    p["max_ratio_ref"] = p.max_contour_ft / ref
    ref_conflict = (ref > 1.25 * p.max_contour_ft + 3)
    p["max_depth_check"] = np.where(ref_conflict, "contours_end_above_reference_max", np.where(ref.notna(), "consistent", "no_anchor"))
    top_closed_plausible = (p.max_contour_ft >= 15) | ((ref.notna()) & ~ref_conflict) | (p.src == "FL")
    p["valid_gt10"] = ((p.max_contour_ft >= 15) | ((ref.notna()) & ~ref_conflict) | (p.src == "FL")).astype(int)
    p.loc[p.src == "WI", "valid_gt10"] = 0
    notes, tier = [], []
    for r, tcp in zip(p.itertuples(), top_closed_plausible):
        n = []
        if r.method == "area_capacity_table": t = "A"
        else:
            ok5 = r.ladder == "fine" or (r.ladder == "std5" and r.max_contour_ft >= 25)         # 5-ft ladder only trusted on lakes >= 25 ft deep (method check: MAE 0.03 vs 0.16-0.22 on shallower lakes)
            if r.hull_class == "full" and ok5: t = "A"
            elif (r.hull_class == "full" and r.ladder == "coarse10" and r.max_contour_ft >= 40) or (r.hull_class == "most" and ok5): t = "B"
            else: t = "C"
            if t == "C" and r.hull_class != "partial" and r.ladder in ("std5", "coarse10"): n.append("contour_ladder_too_coarse_for_lake_depth")
            if r.hull_class == "partial": n.append("partial_coverage")
            if r.ladder == "gappy": n.append("contour_gap>10ft_in_0-10ft_zone")
            if r.src == "UT": t = "C"; n.append("datum_uncertain(elevation->depth vs compromise level)")
            ar = r.area_ratio_poly_to_survey
            if np.isfinite(ar):
                if not (0.7 <= ar <= 1.43): t = "C"; n.append(f"polygon_area_mismatch({ar:.2f})")
                elif not (0.8 <= ar <= 1.25) and t == "A": t = "B"; n.append(f"polygon_area_off({ar:.2f})")
            if not tcp: t = "C"; n.append("top_unverified(max contour<15ft and no consistent max-depth anchor)")
            elif r.max_depth_check == "contours_end_above_reference_max": n.append("deep_part_missing_vs_reference(mean/max depth invalid; shares to 10ft ok if rings closed)")
            if r.src == "FL" and not np.isfinite(r.ref_max_ft): n.append("FL authority exception (full-lake hydroacoustic) for top check")
            if r.src == "WI": t = "C"; n.append("agency DRAFT file; contours only to 10 ft")
        tier.append(t); notes.append(";".join(n))
    p["tier"] = tier; p["flags"] = notes
    # best source per lake
    order = {"A": 0, "B": 1, "C": 2}
    p["_o"] = p.tier.map(order)
    p = p.sort_values(["lakeId", "_o", "cov_hull"], ascending=[True, True, False])
    p["alt_sources"] = p.groupby("lakeId").src.transform(lambda s: ",".join(s))
    best = p.groupby("lakeId", as_index=False).head(1).copy()
    # duplicate fleet entries (same contour set)
    best["dup_key"] = best.src + "|" + best.shr_0_3.round(5).astype(str) + "|" + best.max_contour_ft.round(2).astype(str)
    best["is_duplicate"] = best.duplicated("dup_key", keep="first").astype(int)
    feat = pd.read_csv(FEAT)[["id", "name", "state1", "regime", "lake_class", "hyd", "area_km2", "perim_km", "hasDam", "lat", "lon", "frac_within_100m", "frac_narrow_300m", "sdi_ext", "solidity", "mean_depth_m", "storage_mcm", "glob_dmax_m", "glob_shallow_frac_1p2m"]]
    best = best.merge(feat.rename(columns={"id": "lakeId", "name": "lakeName", "mean_depth_m": "hl_mean_depth_m"}), on="lakeId", how="left")
    best["shr_lt6"] = best.shr_0_3 + best.shr_3_6
    best["licence_note"] = best.src.map(lambda s: LICENCE.get(s, LICENCE["default"]))
    cols = ["lakeId", "lakeName", "state1", "src", "method", "tier", "flags", "ladder", "hull_class", "regime", "lake_class", "hyd", "hasDam", "area_km2", "poly_area_km2", "cov_hull", "cov_raster", "cell_m",
            "shr_0_3", "shr_3_6", "shr_6_10", "shr_gt10", "shr_lt6", "valid_gt10", "mean_depth_ft", "max_contour_ft", "p95_depth_ft", "interval_ft", "first_level_ft", "n_levels", "n_lines",
            "shore_to_3ft_med_m", "shore_to_3ft_p25_m", "shore_to_3ft_p75_m", "shore_to_6ft_med_m", "shore_to_6ft_p25_m", "shore_to_6ft_p75_m", "shore_to_6ft_p90_m", "steep_share_6ft_30m", "shore_6ft_gt100m_share",
            "flat100_n", "flat100_ha", "flat100_max_ha", "flat100_share_of_surveyed", "flat200_n", "flat200_ha", "flat200_max_ha", "flat200_share_of_surveyed",
            "ref_max_ft", "area_ratio_poly_to_survey", "anchor_max_ft", "anchor_src", "anchor_nla_ft", "supplied_max_ft", "max_ratio_ref", "max_depth_check", "alt_sources", "is_duplicate", "licence_note",
            "frac_within_100m", "frac_narrow_300m", "sdi_ext", "solidity", "hl_mean_depth_m", "storage_mcm", "glob_dmax_m", "glob_shallow_frac_1p2m", "lat", "lon"]
    best = best[[c for c in cols if c in best.columns]].sort_values("lakeId")
    best.to_csv(D / "contour_truth_lakes.csv", index=False, float_format="%.4f")
    # all (lake, source) pairs for cross-source agreement
    p.drop(columns=["_o"]).to_csv(RAW / "depth-brain/contour/truth_pairs_flagged.csv", index=False)
    u = best[best.is_duplicate == 0]
    mm = pd.read_csv(D / "contour_matches_verified.csv", dtype={"grp": str})
    vv = mm[mm.matchConfidence == "verified_spatial"]
    msum = dict(pairs_by_confidence=mm.matchConfidence.value_counts().to_dict(), verified_distinct_fleet_lakes=int(vv.lakeId.nunique()), verified_lakes_by_source=vv.groupby("src").lakeId.nunique().to_dict(),
                verified_polygonless_point_matches=int(vv.matchBasis.fillna("").str.startswith("point").sum()),
                rejected_by_kind={"name_collision_or_no_geometric_support(scout candidates)": int(mm[mm.matchBasis.fillna("").str.startswith("scout") & (mm.matchConfidence == "rejected")].shape[0]),
                                  "embedded_or_neighbouring_water_body_inside_polygon(name disagrees)": int(mm.reason.fillna("").str.contains("neighbouring/embedded").sum()),
                                  "weak_overlap": int(mm.reason.fillna("").str.contains("weak geometric overlap").sum())},
                name_only_unverified_by_source=mm[mm.matchConfidence == "name_only_unverified"].src.value_counts().to_dict(),
                note="matching tested every contour group against every fleet polygon (not only scout name candidates); 599 polygons, 621 fleet lakes")
    S = dict(matching=msum, n_lake_rows=int(len(best)), n_unique_lakes_excl_fleet_duplicates=int(len(u)), n_pairs=int(len(p)),
             tier_counts=u.tier.value_counts().to_dict(), by_source_all_tiers=u.src.value_counts().to_dict(),
             by_source_tierA=u[u.tier == "A"].src.value_counts().to_dict(), by_source_tierAB=u[u.tier.isin(["A", "B"])].src.value_counts().to_dict(),
             by_regime_tierAB=u[u.tier.isin(["A", "B"])].regime.value_counts().to_dict(), by_lake_class_tierAB=u[u.tier.isin(["A", "B"])].lake_class.value_counts().to_dict(),
             by_lake_class_tierA=u[u.tier == "A"].lake_class.value_counts().to_dict(),
             by_state_tierAB=u[u.tier.isin(["A", "B"])].state1.value_counts().to_dict(),
             flags=u["flags"].fillna("").replace("", "none").value_counts().to_dict(), max_depth_check=u.max_depth_check.value_counts().to_dict(),
             method=u.method.value_counts().to_dict(),
             shares_tierA_quantiles={c: u[u.tier == "A"][c].quantile([.1, .25, .5, .75, .9]).round(4).tolist() for c in ["shr_0_3", "shr_3_6", "shr_6_10", "shr_gt10", "shr_lt6"]},
             licences=LICENCE)
    json.dump(S, open(D / "contour_truth_summary.json", "w"), indent=1)
    print(json.dumps({k: S[k] for k in ["n_lake_rows", "n_unique_lakes_excl_fleet_duplicates", "tier_counts", "by_source_tierA", "by_source_tierAB", "by_regime_tierAB", "by_lake_class_tierAB", "max_depth_check"]}, indent=1))


if __name__ == "__main__":
    main()
