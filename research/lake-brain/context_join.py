#!/usr/bin/env python3
"""Spatial/name join of the 621 directory lakes to HydroLAKES v1.0 (points = pour points) and NID (Esri mirror).
Inputs : directory snapshot, engine polygons, <DATA>/context/hydrolakes/pts/**/HydroLAKES_points_v10.shp,
         <DATA>/context/nid/nid_v1_subset.json (research/lake-brain/context_fetch_nid.py)
Output : <DATA>/context/external_join.json  (rebuildable; merged by context_features.py)
Match rule (documented in LAKE_BRAIN_CONTEXT_RESEARCH.md): candidates within 5 km of the lake polygon (point lakes: 5 km of
the directory lat/lon); prefer a candidate whose normalised name equals the lake's normalised name; otherwise the largest
candidate whose area is within 0.25-4x the polygon area (HydroLAKES) / whose surface area is within 0.2-5x (NID)."""
import glob, gzip, json, re, unicodedata
from pathlib import Path
import geopandas as gpd, numpy as np, pandas as pd
from shapely.geometry import shape, Point

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
CRS = 5070
R_M = 5000


def core(n):
    n = unicodedata.normalize("NFKD", n if isinstance(n, str) else "").lower()
    n = re.sub(r"\(.*?\)", "", n)
    n = re.sub(r"\b(lake|reservoir|pond|ponds|res|the|of|lago|dam|lock|and|no|\d+)\b", " ", n)
    return " ".join(re.findall(r"[a-z]+", n))


def same_name(a, b):
    """normalised names equal, or one token set contains the other (e.g. 'truman' in 'harry s truman', 'lanier' in 'sidney lanier')"""
    ta, tb = set(core(a).split()), set(core(b).split())
    return bool(ta) and bool(tb) and (ta <= tb or tb <= ta)


def load():
    dirl = {l["id"]: l for l in json.load(open(DATA / "directory_lakes_2026-10-13.json"))["lakes"]}
    pg = json.load(gzip.open(DATA / "geometry/engine_polygons_599.geojson.gz"))
    pm = {f["properties"]["id"]: shape(f["geometry"]) for f in pg["features"]}
    rows = []
    for k, l in dirl.items():
        g = pm.get(k) or Point(l["lon"], l["lat"])
        rows.append(dict(id=k, name=l["name"], has_poly=k in pm, geometry=g))
    L = gpd.GeoDataFrame(rows, crs=4326).to_crs(CRS)
    L["area_km2"] = np.where(L.has_poly, L.geometry.area / 1e6, np.nan)
    L["geom_buf"] = L.geometry.simplify(40).buffer(R_M, quad_segs=2)
    return L


def join_hl(L):
    f = glob.glob(str(DATA / "context/hydrolakes/pts/**/HydroLAKES_points_v10.shp"), recursive=True)[0]
    hl = gpd.read_file(f).cx[-180:-50, 15:75]
    H = hl.to_crs(CRS).reset_index(drop=True)
    B = gpd.GeoDataFrame(L[["id"]], geometry=L.geom_buf, crs=CRS)
    j = gpd.sjoin(B, H, how="inner", predicate="intersects")
    nm = L.set_index("id")
    cands = {}
    claimed = {}   # HydroLAKES id -> directory lakes whose normalised name equals the HydroLAKES name (within 5 km)
    for lid, grp in j.groupby("id"):
        row = nm.loc[lid]; c = core(row["name"]); a = row["area_km2"]
        grp = grp.copy(); grp["nm"] = grp.Lake_name.fillna("").map(lambda x: same_name(row["name"], x))
        grp["ratio"] = grp.Lake_area / a if not np.isnan(a) else np.nan
        cands[lid] = grp
        for _, r in grp[grp.nm].iterrows(): claimed.setdefault(int(r.Hylak_id), set()).add(lid)
    out = {}
    for lid, grp in cands.items():
        a = nm.loc[lid, "area_km2"]
        d = grp[grp.nm]; how = "name"
        if len(d) and not np.isnan(a): d = d[(d.ratio > 0.2) & (d.ratio < 5)]
        if len(d) == 0:
            how = "geo"
            g2 = grp[[not (claimed.get(int(h), set()) - {lid}) for h in grp.Hylak_id]]   # not claimed by another lake
            if np.isnan(a): d = g2[g2.nm]   # point-only lake: only name matches are trusted
            else:
                d = g2[(g2.ratio > 0.4) & (g2.ratio < 2.5)]
                if len(d): d = d.assign(lr=np.abs(np.log(d.ratio))).sort_values("lr")
        if len(d) == 0: continue
        r = d.iloc[0] if how == "geo" else d.sort_values("Lake_area", ascending=False).iloc[0]
        out[lid] = dict(hl_match=how, hl_ratio=float(r.Lake_area / a) if not np.isnan(a) else None, hl_id=int(r.Hylak_id), hl_name=r.Lake_name, hl_type=int(r.Lake_type), hl_area_km2=float(r.Lake_area),
                        hl_depth_avg_m=float(r.Depth_avg), hl_vol_mcm=float(r.Vol_total), hl_res_time_d=float(r.Res_time), hl_dis_avg_m3s=float(r.Dis_avg),
                        hl_wshd_km2=float(r.Wshd_area), hl_elev_m=float(r.Elevation), hl_grand_id=int(r.Grand_id), hl_shore_dev=float(r.Shore_dev))
    # one HydroLAKES lake -> one directory lake, unless the rows are the same lake listed twice (identical normalised name, e.g. a two-state lake)
    byid = {}
    for k, v in out.items(): byid.setdefault(v["hl_id"], []).append(k)
    for hid, ks in byid.items():
        if len(ks) < 2: continue
        def key(k):
            v = out[k]; lr = abs(np.log(v["hl_ratio"])) if v["hl_ratio"] else 9
            return (0 if v["hl_match"] == "name" else 1, lr)
        best = min(ks, key=key)
        for k in ks:
            if k != best and core(nm.loc[k, "name"]) != core(nm.loc[best, "name"]): del out[k]
    return out


def join_nid(L):
    n = pd.DataFrame(json.load(open(DATA / "context/nid/nid_v1_subset.json")))
    n = n[(n.LATITUDE.notna()) & (n.LATITUDE != 0)]
    N = gpd.GeoDataFrame(n, geometry=gpd.points_from_xy(n.LONGITUDE, n.LATITUDE), crs=4326).to_crs(CRS).reset_index(drop=True)
    B = gpd.GeoDataFrame(L[["id"]], geometry=L.geom_buf, crs=CRS)
    j = gpd.sjoin(B, N, how="inner", predicate="intersects")
    nm = L.set_index("id")
    cands = {}; claimed = {}
    for lid, grp in j.groupby("id"):
        row = nm.loc[lid]; c = core(row["name"])
        grp = grp.copy()
        grp["nm"] = [(c != "" and (c in core(x if isinstance(x, str) else "") or c in core(y if isinstance(y, str) else ""))) for x, y in zip(grp.NAME, grp.OTHER_NAMES)]
        grp["dike"] = grp.NAME.fillna("").str.contains(r"dike|saddle|auxiliary|aux\.|spillway|dyke", case=False)
        cands[lid] = grp
        for _, r in grp[grp.nm].iterrows(): claimed.setdefault(r.NIDID, set()).add(lid)
    out = {}
    for lid, grp in cands.items():
        a = nm.loc[lid, "area_km2"]
        d = grp[grp.nm]; how = "name"
        if len(d) == 0:
            how = "geo"
            g2 = grp[[not (claimed.get(i, set()) - {lid}) for i in grp.NIDID]]
            if np.isnan(a): d = g2[g2.NID_STORAGE.fillna(0) > 5000]
            else:
                r = (g2.SURFACE_AREA.fillna(0) * 0.00404686) / a  # acres -> km2
                d = g2[(r > 0.2) & (r < 5)]
        if len(d) == 0: continue
        d = d.assign(hasda=(d.DRAINAGE_AREA.fillna(0) > 0)).sort_values(["dike", "hasda", "NID_STORAGE"], ascending=[True, False, False])
        r = d.iloc[0]
        out[lid] = dict(nid_match=how, nid_id=r.NIDID, nid_name=r.NAME, nid_river=r.RIVER_OR_STREAM, nid_storage_af=_f(r.NID_STORAGE),
                        nid_normal_storage_af=_f(r.NORMAL_STORAGE), nid_surface_ac=_f(r.SURFACE_AREA), nid_drainage_sqmi=_f(r.DRAINAGE_AREA),
                        nid_height_ft=_f(r.NID_HEIGHT), nid_year=_f(r.YEAR_COMPLETED), nid_purposes=r.PURPOSES, nid_primary=r.PRIMARY_PURPOSE,
                        nid_locks=_f(r.NUMBER_OF_LOCKS), nid_owner_type=r.PRIMARY_OWNER_TYPE, nid_max_discharge_cfs=_f(r.MAX_DISCHARGE),
                        nid_lat=_f(r.LATITUDE), nid_lon=_f(r.LONGITUDE))
    return out


def _f(x):
    try:
        return None if pd.isna(x) else float(x)
    except Exception:
        return None


if __name__ == "__main__":
    L = load()
    hl = join_hl(L); nid = join_nid(L)
    res = {k: {**hl.get(k, {}), **nid.get(k, {})} for k in L.id}
    (DATA / "context/external_join.json").write_text(json.dumps(res))
    import collections
    print("HL", collections.Counter(v.get("hl_match", "none") for v in res.values()))
    print("NID", collections.Counter(v.get("nid_match", "none") for v in res.values()))
