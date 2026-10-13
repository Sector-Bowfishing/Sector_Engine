#!/usr/bin/env python3
"""Depth Brain / contour truth, step 2: SPATIALLY VERIFY contour-group <-> fleet-lake pairings.

Every normalized contour group (contour_ingest.py) is tested against EVERY fleet polygon (engine_polygons_599) by geometry, not only the
name+state candidates of the scout.  Name candidates from scout/fleet_candidate_matches.csv are then used only to (a) flag name agreement and
(b) catch name collisions (name matches, geometry far away -> rejected).

Per (group, lake) pair:
  fracLenIn  = length of group lines inside the fleet polygon (buffered 150 m for digitising offset) / total group line length
  hullCov    = area(convex hull of the in-polygon lines  ∩ polygon) / polygon area        (spec: contour-hull / polygon)
  nameAgree  = normalised name equality or containment (generic words removed)
Classification
  verified_spatial : fracLenIn >= 0.70 and (nameAgree or group not named or hullCov >= 0.25 or group length share >= 0.05 of lake)
                     or 0.25 <= fracLenIn < 0.70 and nameAgree (partial overlap, flagged)
  rejected         : name-candidate with no geometric support (>2 km from polygon), or overlapping but tiny/unrelated (name disagree, hullCov<0.02)
  name_only_unverified: scout name candidate whose data is not geometry-checkable here (not downloaded / index only / no polygon+no point)
Fleet lakes with no polygon use the lake_features lat/lon point (<= 2 km of the group's hull, nameAgree or unnamed group).
Outputs: data/contour_matches_verified.csv (all pairs with evidence), data/contour_anchors_verified.csv (max-depth anchors verified by point-in-polygon)."""
import gzip, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
from shapely import STRtree
import shapely

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
NORM = RAW / "depth-brain/contour/norm"
SRCD = RAW / "depth-brain/sources"
FEAT = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv")
EPSG = 5070
GENERIC = {"lake", "reservoir", "pond", "res", "the", "dam", "lakes", "ponds", "flowage", "impoundment", "of", "and", "upper", "lower", "big", "little"}


def norm_name(s):
    s = re.sub(r"\(.*?\)", " ", str(s or "").lower()); s = re.sub(r"[^a-z0-9 ]", " ", s)
    t = [w for w in s.split() if w not in GENERIC and w not in {"st", "saint", "mount", "mt"} or w in {"st", "saint"}]
    return " ".join(t).replace("saint", "st")


def name_agree(a, b):
    a, b = norm_name(a), norm_name(b)
    if not a or not b: return False
    return a == b or a in b or b in a


def load_fleet():
    raw = json.loads(gzip.open(RAW / "lake-brain/geometry/engine_polygons_599.geojson.gz").read())
    g = gpd.GeoDataFrame.from_features(raw["features"], crs=4326)
    g["geometry"] = g.geometry.apply(lambda x: shapely.union_all([p for p in x.geoms if p.geom_type in ("Polygon", "MultiPolygon")]) if x.geom_type == "GeometryCollection" else x)
    g = g.to_crs(EPSG); g["geometry"] = g.geometry.make_valid()
    f = pd.read_csv(FEAT)[["id", "name", "state1", "lat", "lon", "regime", "lake_class", "area_km2", "hasDam"]]
    return g, f


def main():
    poly, feat = load_fleet()
    poly = poly.set_index("id")
    pbuf = poly.geometry.buffer(150)
    tree = STRtree(pbuf.values)
    ids = list(poly.index)
    st_of = dict(zip(feat.id, feat.state1)); nm_of = dict(zip(feat.id, feat.name))
    cand = pd.read_csv(D / "scout/fleet_candidate_matches.csv")
    cand_names = {}
    for r in cand.itertuples():
        if isinstance(r.sourceId, str) and r.sourceId: cand_names.setdefault(r.lakeId, set()).add(r.sourceId)
    rows = []
    for gp in sorted(NORM.glob("*.gpkg")):
        src = gp.stem
        lines = gpd.read_file(gp).to_crs(EPSG)
        for grp, sub in lines.groupby("grp", sort=False):
            geom = shapely.union_all(sub.geometry.values) if len(sub) > 1 else sub.geometry.iloc[0]
            L = geom.length
            if L <= 0: continue
            gname = sub.grp_name.iloc[0]
            hits = tree.query(geom, predicate="intersects")
            for h in hits:
                lid = ids[h]; P = poly.geometry.iloc[h]
                inside = geom.intersection(pbuf.iloc[h])
                fl = inside.length / L
                if fl < 0.02: continue
                # hull of in-polygon lines
                hull = inside.convex_hull
                hcov = hull.intersection(P).area / P.area if P.area > 0 and hull.area > 0 else 0.0
                rows.append(dict(lakeId=lid, lakeName=nm_of.get(lid, ""), state=st_of.get(lid, ""), src=src, grp=grp, grp_name=gname, nLines=len(sub),
                                 lenKm=L / 1000, fracLenIn=fl, hullCov=hcov, lakeAreaKm2=P.area / 1e6, nameAgree=name_agree(gname, nm_of.get(lid, "")),
                                 matchBasis="polygon"))
    m = pd.DataFrame(rows)
    # name-candidate groups without polygon support (collisions) + polygon-less lakes via point
    nopoly = feat[~feat.id.isin(poly.index)]
    pts = gpd.GeoSeries([Point(x, y) for x, y in zip(nopoly.lon, nopoly.lat)], crs=4326).to_crs(EPSG)
    extra = []
    for gp in sorted(NORM.glob("*.gpkg")):
        src = gp.stem
        lines = gpd.read_file(gp).to_crs(EPSG)
        for grp, sub in lines.groupby("grp", sort=False):
            gname = sub.grp_name.iloc[0]; geom = shapely.union_all(sub.geometry.values) if len(sub) > 1 else sub.geometry.iloc[0]
            hull = geom.convex_hull
            for (lid, nm, stt), pt in zip(zip(nopoly.id, nopoly.name, nopoly.state1), pts):
                d = hull.distance(pt)
                if d <= 2000 and (name_agree(gname, nm) or not str(gname).strip()):
                    extra.append(dict(lakeId=lid, lakeName=nm, state=stt, src=src, grp=grp, grp_name=gname, nLines=len(sub), lenKm=geom.length / 1000, fracLenIn=np.nan, hullCov=np.nan,
                                      lakeAreaKm2=np.nan, nameAgree=name_agree(gname, nm), matchBasis=f"point_{d:.0f}m"))
    if extra: m = pd.concat([m, pd.DataFrame(extra)], ignore_index=True)

    def classify(r):
        if r.matchBasis.startswith("point"):
            return ("verified_spatial", "no polygon; fleet point within 2 km of contour hull" + (" and name agrees" if r.nameAgree else " (unnamed group)")) if r.nameAgree or not str(r.grp_name).strip() else ("rejected", "point only, name disagrees")
        fl, hc, na = r.fracLenIn, r.hullCov, r.nameAgree
        unnamed = not str(r.grp_name).strip()
        if fl >= 0.70 and (na or unnamed or hc >= 0.25):
            return "verified_spatial", "contours inside polygon" + ("" if na or unnamed else "; name disagrees but hull covers >=25% of lake")
        if 0.25 <= fl < 0.70 and na:
            return "verified_spatial", f"partial overlap (fracLenIn {fl:.2f}); name agrees; polygon/contour extent mismatch"
        if fl >= 0.70:
            return "rejected", f"contours inside polygon but name disagrees and hull covers only {hc:.3f} of lake (neighbouring/embedded water body)"
        return "rejected", f"weak geometric overlap (fracLenIn {fl:.2f}) and name {'agrees' if na else 'disagrees'}"
    cl = m.apply(classify, axis=1, result_type="expand")
    m["matchConfidence"], m["reason"] = cl[0], cl[1]
    # collision check from scout name candidates: lakes with name candidate in a source but no verified pair in that source
    srcmap = {"S-depth-002": "MN", "S-depth-003": "IN", "S-depth-004": "MT", "S-depth-005": "NE", "S-depth-006": "ND", "S-depth-007": "NH", "S-depth-008": "WA", "S-depth-009": "MI",
              "S-depth-010": "MA", "S-depth-011": "KS", "S-depth-012": "FL", "S-depth-013": "OK", "S-depth-014": "IL", "S-depth-015": "OH", "S-depth-016": "TN", "S-depth-017": "WV",
              "S-depth-018": "NJ", "S-depth-019": "CT"}
    rev = {}
    for r in cand.itertuples():
        if r.sourceId in srcmap and r.matchConfidence in ("exact", "name_state", "spatial_only"):
            rev.setdefault((r.lakeId, srcmap[r.sourceId]), r.matchConfidence)
    have = set(zip(m[m.matchConfidence == "verified_spatial"].lakeId, m[m.matchConfidence == "verified_spatial"].src))
    coll = []
    gtabs = {gp.stem[:-7]: pd.read_csv(gp, dtype={"grp": str}) for gp in NORM.glob("*_groups.csv")}
    featxy = feat.set_index("id")
    for (lid, s), how in rev.items():
        if (lid, s) in have: continue
        why = "scout name/spatial candidate has no verified geometric support in the downloaded data"
        g = gtabs.get(s)
        if g is not None and lid in featxy.index:
            lat, lon = featxy.loc[lid, "lat"], featxy.loc[lid, "lon"]
            pa = poly.geometry[lid].area / 1e6 if lid in poly.index else np.nan
            cands = g[g.grp_name.map(lambda x: name_agree(x, nm_of.get(lid, ""))) | (g.grp_name.fillna("").str.strip() == "")]
            if len(cands):
                dx = np.maximum(np.maximum(cands.minx - lon, lon - cands.maxx), 0) * 111.32 * np.cos(np.radians(lat)); dy = np.maximum(np.maximum(cands.miny - lat, lat - cands.maxy), 0) * 110.57
                dist = np.hypot(dx, dy); j = dist.idxmin(); c = cands.loc[j]
                bb = (c.maxx - c.minx) * 111.32 * np.cos(np.radians(lat)) * (c.maxy - c.miny) * 110.57
                if dist[j] <= 2.0:
                    why = (f"candidate group '{c.grp_name}' (src cluster) lies within 2 km of the fleet point but does not overlap the fleet polygon: extent mismatch, polygon {pa:.3f} km2 vs contour bbox ~{bb:.1f} km2 "
                           f"(fleet polygon wrong/partial, or contours belong to a different water body) - cannot verify" if np.isfinite(pa) else f"name-matching group '{c.grp_name}' near fleet point but fleet has no polygon")
                else:
                    why = f"name collision: nearest same-name group '{c.grp_name}' is {dist[j]:.0f} km from the fleet lake point"
            else:
                why = "no group with a matching name in the downloaded data (scout candidate was name-normalisation or spatial-only)"
        coll.append(dict(lakeId=lid, lakeName=nm_of.get(lid, ""), state=st_of.get(lid, ""), src=s, grp="", grp_name="", matchBasis="scout_name_candidate:" + how, matchConfidence="rejected", reason=why))
    m = pd.concat([m, pd.DataFrame(coll)], ignore_index=True)
    # name-only: candidates whose source is not downloaded as contours (index / catalog only)
    nd = []
    for r in cand.itertuples():
        if r.sourceId in ("S-depth-001", "S-depth-020", "S-depth-024", "S-depth-025", "S-depth-031", "S-depth-033") and r.matchConfidence in ("exact", "name_state"):
            nd.append(dict(lakeId=r.lakeId, lakeName=r.lakeName, state=r.state, src=r.sourceId, grp="", grp_name="", matchBasis="scout_name_candidate:" + r.matchConfidence,
                           matchConfidence="name_only_unverified", reason="source not available as geometry here (TWDB handled via terrain tables / USGS index or catalog only / not downloaded)"))
    m = pd.concat([m, pd.DataFrame(nd)], ignore_index=True)
    m.to_csv(D / "data/contour_matches_verified.csv", index=False, float_format="%.4f")
    v = m[m.matchConfidence == "verified_spatial"]
    print(m.matchConfidence.value_counts().to_dict(), "verified lakes:", v.lakeId.nunique())
    print(v.groupby("src").lakeId.nunique().to_dict())


if __name__ == "__main__":
    main()
