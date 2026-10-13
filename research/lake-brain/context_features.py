#!/usr/bin/env python3
"""Lake Brain context features for all 621 directory lakes (Tracks 5-7).  Reproducible build of
  docs/research/lake-brain/data/lake_features.csv           one row per lake, small columns only
  docs/research/lake-brain/data/lake_features_summary.json  counts, class scheme, pilot detail, coverage
Inputs (all under <DATA>/context, rebuildable, never committed):
  geom_features.json   (context_geom.py)      polygon morphometry
  external_join.json   (context_join.py)      HydroLAKES + NID spatial/name join   (needs hydrolakes/, nid/ from context_fetch_nid.py)
  erom.json            (context_erom.py)      NHDPlus HR mean-annual flow + drainage area at the dam
  chain.json           (context_chain.py)     NLDI up/downstream directory lakes   (optional)
  globathy/            GLOBathy_hAV_relationships.nc (optional)
  pilot proxies: shore_dem.json, gsw_features.json, nwi_features.json (optional, pilots only)
Run:  <DATA>/context/venv/bin/python research/lake-brain/context_features.py
"""
import json, math, re, sys, collections
from pathlib import Path
import numpy as np, pandas as pd

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
CTX = DATA / "context"
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/research/lake-brain/data"
CFS = 0.0283168      # m3/s per cfs
AF = 1233.48 / 1e6   # Mm3 per acre-ft
PILOTS = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]
GREAT = {"Lake Michigan", "Lake Erie", "Lake Huron", "Lake Superior", "Lake Ontario", "Green Bay", "Lake of the Woods", "Great Salt Lake"}
REGION = {**{s: "NE" for s in "CT ME MA NH RI VT NY NJ PA DE MD DC".split()}, **{s: "SE" for s in "VA WV NC SC GA FL AL MS TN KY LA AR".split()},
          **{s: "MW" for s in "OH IN IL MI WI MN IA MO".split()}, **{s: "GP" for s in "ND SD NE KS OK TX".split()},
          **{s: "W" for s in "MT WY CO NM AZ UT NV ID CA OR WA".split()}, **{s: "AKHI" for s in "AK HI".split()}}


def fam(o):
    o = str(o)
    if o == "TVA": return "TVA"
    if "USACE" in o: return "USACE"
    if re.search(r"USBR|Reclamation|Northern Water", o): return "USBR"
    if re.search(r"natural|^none|^—$", o, re.I): return "NONE"
    return "OTHER"


def num(df, cols):
    for c in cols: df[c] = pd.to_numeric(df[c], errors="coerce")


def load():
    dd = pd.DataFrame(json.load(open(DATA / "directory_lakes_2026-10-13.json"))["lakes"]).set_index("id")
    g = pd.DataFrame(json.load(open(CTX / "geom_features.json"))).T
    j = pd.DataFrame(json.load(open(CTX / "external_join.json"))).T
    e = pd.DataFrame(json.load(open(CTX / "erom.json"))).T if (CTX / "erom.json").exists() else pd.DataFrame()
    df = dd.join(g, rsuffix="_g").join(j)
    if len(e): df = df.join(e[["totdasqkm", "qama", "qema", "streamorde"]].rename(columns={"totdasqkm": "erom_da_km2", "qama": "erom_qama_cfs", "qema": "erom_qema_cfs", "streamorde": "erom_order"}))
    num(df, ["area_km2", "perim_km", "sdi", "sdi_ext", "n_parts", "n_islands", "solidity", "elong", "bbox_len_km", "frac_within_50m", "frac_within_100m", "frac_within_250m",
             "frac_narrow_300m", "frac_narrow_800m", "n_narrow_arms", "narrow_arm_len_km", "hl_type", "hl_area_km2", "hl_depth_avg_m", "hl_vol_mcm", "hl_res_time_d", "hl_dis_avg_m3s",
             "hl_wshd_km2", "hl_elev_m", "nid_storage_af", "nid_normal_storage_af", "nid_surface_ac", "nid_drainage_sqmi", "nid_height_ft", "nid_year", "nid_locks",
             "erom_da_km2", "erom_qama_cfs", "erom_qema_cfs", "fullPoolFt", "lat", "lon"] if False else [c for c in df.columns if c in
             ("area_km2", "perim_km", "sdi", "sdi_ext", "n_parts", "n_islands", "solidity", "elong", "bbox_len_km", "frac_within_50m", "frac_within_100m", "frac_within_250m",
              "frac_narrow_300m", "frac_narrow_800m", "n_narrow_arms", "narrow_arm_len_km", "hl_type", "hl_area_km2", "hl_depth_avg_m", "hl_vol_mcm", "hl_res_time_d",
              "hl_dis_avg_m3s", "hl_wshd_km2", "hl_elev_m", "nid_storage_af", "nid_normal_storage_af", "nid_surface_ac", "nid_drainage_sqmi", "nid_height_ft", "nid_year",
              "nid_locks", "erom_da_km2", "erom_qama_cfs", "erom_qema_cfs", "fullPoolFt", "lat", "lon", "hl_id")])
    return df


def derive(df):
    df["operator_family"] = df.operatorName.map(fam)
    df["region"] = [REGION.get(str(s[0]) if isinstance(s, list) and s else df.state.get(i), "OTH") for i, s in zip(df.index, df.states)]
    df["state1"] = df.state
    df["cwms"] = df.cwmsOffice.notna()
    # --- reference area = max(polygon, HydroLAKES, NID surface area if within 2x of max(polygon, HydroLAKES)).  Polygon area is the *currently mapped water* (low-pool
    #     western reservoirs map at 10-40 % of NID surface area); HydroLAKES is an older mask; NID surface area is wrong for ~6 % of lakes (it often describes a small
    #     outlet structure on a natural lake, or includes flood pool).  The max of the credible estimates is the best normal-pool area.
    est = pd.DataFrame({"poly": df.area_km2, "hl": df.hl_area_km2})
    est = est.where(est > 0)
    base = est.max(axis=1)
    nid_a = (df.nid_surface_ac * 0.00404686).where(df.nid_surface_ac > 0)
    nid_ok = nid_a.where((nid_a <= 2 * base) | base.isna())
    df["area_ref_km2"] = pd.concat([base, nid_ok], axis=1).max(axis=1)
    df["area_src_n"] = est.notna().sum(axis=1) + nid_ok.notna()
    df["poly_to_nid_area"] = df.area_km2 / (df.nid_surface_ac * 0.00404686).where(df.nid_surface_ac > 0)
    # --- storage (Mm3): HydroLAKES capacity (GRanD for reservoirs); NID as fallback.  inflow: EROM gage-adjusted, else runoff-EROM, else HydroLAKES
    stor = df.hl_vol_mcm.where(df.hl_vol_mcm > 0)
    nid_s = (df.nid_storage_af.where(df.nid_storage_af > 0)) * AF
    df["storage_mcm"] = stor.fillna(nid_s)
    df["storage_src"] = np.where(stor.notna(), "HL", np.where(nid_s.notna(), "NID", ""))
    hl_q = df.hl_dis_avg_m3s.where(df.hl_dis_avg_m3s > 0)
    q_e = df.erom_qema_cfs.where(df.erom_qema_cfs > 1) * CFS if "erom_qema_cfs" in df else pd.Series(np.nan, index=df.index)
    q_a = df.erom_qama_cfs.where(df.erom_qama_cfs > 1) * CFS if "erom_qama_cfs" in df else pd.Series(np.nan, index=df.index)
    # EROM sanity: runoff yield >= 0.01 cfs/km2 (~9 mm/yr); the HR flowline at some western/plains dams carries ~0 cfs (diverted / endorheic / artificial path)
    da = df.erom_da_km2 if "erom_da_km2" in df else pd.Series(np.nan, index=df.index)
    q_e = q_e.where(~(df.erom_qema_cfs / da < 0.01)) if "erom_qema_cfs" in df else q_e
    q_a = q_a.where(~(df.erom_qama_cfs / da < 0.01)) if "erom_qama_cfs" in df else q_a
    ok_e = q_e.notna() & (hl_q.isna() | ((q_e / hl_q).between(0.3, 3)))
    ok_a = q_a.notna() & (hl_q.isna() | ((q_a / hl_q).between(0.3, 3)))
    q = np.where(ok_e, q_e, np.where(ok_a, q_a, hl_q))
    df["inflow_m3s"] = q
    df["inflow_src"] = np.where(ok_e, "EROM_qema", np.where(ok_a, "EROM_qama", np.where(hl_q.notna(), "HL", "")))
    df["res_time_d"] = df.storage_mcm * 1e6 / (df.inflow_m3s * 86400)
    df.loc[~np.isfinite(df.res_time_d), "res_time_d"] = np.nan
    bad = df.inflow_src.str.startswith("EROM") & (df.res_time_d > 10000)       # implausible: >27 years for a surface-fed lake -> EROM flow unusable here
    df.loc[bad, "res_time_d"] = np.nan; df.loc[bad, "inflow_m3s"] = np.nan; df.loc[bad, "inflow_src"] = "rejected"
    df["res_time_d"] = df.res_time_d.fillna(df.hl_res_time_d.where(df.hl_res_time_d > 0))
    df["dor"] = df.res_time_d / 365.0          # degree of regulation: storage / mean annual inflow volume
    df["mean_depth_m"] = df.storage_mcm * 1e6 / (df.area_ref_km2 * 1e6)
    df.loc[df.mean_depth_m > 150, "mean_depth_m"] = np.nan
    df["drainage_km2"] = df.erom_da_km2.where(df.erom_da_km2 > 0).fillna(df.hl_wshd_km2.where(df.hl_wshd_km2 > 0)).fillna(df.nid_drainage_sqmi.where(df.nid_drainage_sqmi > 0) * 2.58999)
    df["da_to_area"] = df.drainage_km2 / df.area_ref_km2
    # --- GLOBathy (modeled): A(h) = a h^b with h = height above the deepest point; fraction of surface area shallower than d metres = 1-(1-d/Dmax)^b
    nc = CTX / "globathy/GLOBathy_hAV_relationships.nc"
    df["glob_dmax_m"] = np.nan; df["glob_shallow_frac_1p2m"] = np.nan
    if nc.exists():
        import xarray as xr
        ds = xr.open_dataset(nc); ids = ds["lake_id"].values; pos = {int(v): i for i, v in enumerate(ids)}
        fhA = ds["f_hA"].values; att = ds["lake_attributes"].values
        for k, hid in df.hl_id.items():
            if pd.notna(hid) and int(hid) in pos:
                i = pos[int(hid)]; dmax, b = float(att[i][0]), float(fhA[i][1])
                if dmax > 0 and b > 0: df.loc[k, "glob_dmax_m"] = dmax; df.loc[k, "glob_shallow_frac_1p2m"] = 1 - max(0.0, 1 - 1.2 / dmax) ** b
    df["hydropower"] = df.nid_purposes.fillna("").str.contains("Hydroelectric")
    # --- regime
    dam_signal = df.hasDam | (df.nid_match == "name") | df.hl_type.isin([2, 3])
    is_res = df.hasDam & (df.poolBasis != "naturalSurface")
    big = df.index.map(lambda i: i.split("|")[0] in GREAT) | (df.area_ref_km2 > 1500)
    # reservoir = directory says dam AND pool basis is a built full pool; regulated_natural = dam signal (NID name match / HydroLAKES reservoir flag / directory dam)
    # on a lake whose pool basis is the natural surface, or a directory 'no dam' lake with a dam signal; natural = no dam signal
    df["regime"] = np.where(big, "MEGA", np.where(is_res, "reservoir", np.where(dam_signal, "regulated_natural", "natural")))
    # --- hydraulic class (residence time); 'unk' when no storage/inflow
    rt = df.res_time_d
    df["hyd"] = np.select([rt < 30, rt < 180, rt >= 180], ["RoR", "FLOW", "STOR"], default="unk")
    df["dendritic"] = (df.sdi_ext >= 8)
    df["size"] = pd.cut(df.area_ref_km2, [0, 2, 20, 100, 1e9], labels=["xs", "s", "m", "l"]).astype(str)
    df["depth_class"] = pd.cut(df.mean_depth_m, [0, 4, 10, 1e9], labels=["shallow", "mid", "deep"]).astype(str)
    cls = []
    for i, r in df.iterrows():
        if r.regime == "MEGA": cls.append("X_mega"); continue
        if pd.isna(r.area_ref_km2): cls.append("Z_nodata"); continue
        small = r.area_ref_km2 < 2
        if r.regime == "reservoir":
            if small: cls.append("R5_small_impoundment")
            elif r.hyd == "RoR": cls.append("R1_run_of_river_pool")
            elif r.hyd == "FLOW": cls.append("R2_flow_through_reservoir")
            elif r.hyd == "STOR" or r.hyd == "unk": cls.append("R3_dendritic_storage" if r.dendritic else "R4_open_basin_storage")
        elif r.regime == "regulated_natural":
            cls.append("N3_small_pond_or_outlet_dam" if small else "N2_regulated_natural_lake")
        else:
            cls.append("N3_small_pond_or_outlet_dam" if small else ("N1b_natural_shallow" if (pd.notna(r.mean_depth_m) and r.mean_depth_m < 6) else "N1a_natural_deep_or_unknown"))
    df["lake_class"] = cls
    return df


CSV_COLS = ["name", "state1", "region", "lat", "lon", "operator_family", "hasDam", "poolBasis", "apiLevel", "usgsGage", "cwms", "regime", "lake_class", "hyd", "size", "depth_class", "dendritic",
            "area_km2", "area_ref_km2", "poly_to_nid_area", "perim_km", "sdi_ext", "n_islands", "solidity", "frac_within_100m", "frac_narrow_300m", "n_narrow_arms",
            "storage_mcm", "storage_src", "inflow_m3s", "inflow_src", "res_time_d", "mean_depth_m", "drainage_km2", "da_to_area", "hl_type", "hl_match", "nid_match", "nid_year",
            "nid_height_ft", "glob_dmax_m", "glob_shallow_frac_1p2m", "hydropower", "hl_elev_m", "n_up_lakes", "n_down_lakes", "nearest_down", "chain_id"]


def chain(df):
    """River-network relations from chain.json (NLDI downstream-main navigation, 250 km, from each matched dam).  Direction is taken from DM only
    (UM also returns the adjacent downstream pool whose headwater touches the dam).  n_down_lakes = directory lakes downstream within 250 km;
    n_up_lakes = directory lakes whose DM list contains this lake; nearest_down = closest (straight-line) downstream lake; chain_id groups lakes linked by
    DM edges with the first lake alphabetically (coarse river-system id)."""
    p = CTX / "chain.json"
    df["n_up_lakes"] = np.nan; df["n_down_lakes"] = np.nan; df["nearest_down"] = ""; df["chain_id"] = ""
    if not p.exists(): return df, {}
    c = json.load(open(p))
    ups = collections.defaultdict(set)
    for k, v in c.items():
        for d in (v.get("DM") or []): ups[d[0]].add(k)
    for k, v in c.items():
        if "error" in v or v.get("DM") is None: continue
        df.loc[k, "n_down_lakes"] = len(v["DM"]); df.loc[k, "n_up_lakes"] = len(ups.get(k, ()))
        if v["DM"]: df.loc[k, "nearest_down"] = v["DM"][0][0]
    par = {k: k for k in df.index}
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for a_, v in c.items():
        for d in (v.get("DM") or []):
            if d[0] in par and a_ in par: par[f(a_)] = f(d[0])
    groups = collections.defaultdict(list)
    for k in df.index: groups[f(k)].append(k)
    cid = {m: "chain-" + sorted(mem)[0].split("|")[0].replace(" ", "")[:14] for mem in groups.values() if len(mem) > 1 for m in mem}
    df["chain_id"] = [cid.get(k, "") for k in df.index]
    return df, {k: v["DM"] for k, v in c.items() if v.get("DM")}


def main():
    df = derive(load())
    df, dm = chain(df)
    OUT.mkdir(parents=True, exist_ok=True)
    out = df[[c for c in CSV_COLS if c in df.columns]].copy()
    for c in out.columns:
        if out[c].dtype == float: out[c] = out[c].round(3)
    out.reset_index(names="id").to_csv(OUT / "lake_features.csv", index=False)
    # --- summary
    S = {"n_lakes": int(len(df)), "built": "context_features.py", "class_counts": df.lake_class.value_counts().to_dict(), "regime_counts": df.regime.value_counts().to_dict(),
         "hyd_counts_reservoirs": df[df.regime == "reservoir"].hyd.value_counts().to_dict(),
         "coverage": {"polygon": int(df.area_km2.notna().sum()), "hydrolakes_match": int(df.hl_match.notna().sum()), "hydrolakes_name": int((df.hl_match == "name").sum()),
                      "nid_match": int(df.nid_match.notna().sum()), "nid_name": int((df.nid_match == "name").sum()), "erom": int(df.erom_da_km2.notna().sum()) if "erom_da_km2" in df else 0,
                      "res_time": int(df.res_time_d.notna().sum()), "mean_depth": int(df.mean_depth_m.notna().sum()), "inflow": int(df.inflow_m3s.notna().sum())},
         "operator_family": df.operator_family.value_counts().to_dict(), "region": df.region.value_counts().to_dict(),
         "class_by_region": pd.crosstab(df.lake_class, df.region).to_dict("index"), "class_by_operator": pd.crosstab(df.lake_class, df.operator_family).to_dict("index"),
         "class_examples": {k: list(v.index[:6]) for k, v in df.groupby("lake_class")}}
    pil = {}
    for k in PILOTS:
        r = df.loc[k]
        pil[k] = {c: (None if (isinstance(r[c], float) and not np.isfinite(r[c])) else (r[c].item() if hasattr(r[c], "item") else r[c])) for c in out.columns if c in r.index}
    S["pilots"] = pil
    for fn, key in (("shore_dem.json", "shore_dem"), ("gsw_features.json", "gsw"), ("nwi_features.json", "nwi"), ("tribs.json", "tribs")):
        p = CTX / fn
        if p.exists():
            d = json.load(open(p)); S[key] = {k: v for k, v in d.items() if k in PILOTS} if key != "gsw" else {k: v for k, v in d.items() if k in PILOTS}
    S["chain_downstream_within_250km"] = {k: v[:4] for k, v in dm.items() if k in PILOTS}
    (OUT / "lake_features_summary.json").write_text(json.dumps(S, indent=1, default=str))
    print(json.dumps({k: S[k] for k in ("class_counts", "regime_counts", "hyd_counts_reservoirs", "coverage")}, indent=1))


if __name__ == "__main__":
    main()
