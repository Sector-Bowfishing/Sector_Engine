#!/usr/bin/env python3
"""Build the Lake Registry geometry set (A2): canonical lake shorelines + the Lake Registry index.

DRY-RUN BY DEFAULT. Without --upload this only reads inputs, (re)builds every artifact into --out and prints the upload plan;
the only network traffic is public GET requests to the USGS NHD REST service for lakes whose query is not in the local cache.
With --upload it writes to gs://sector-lake-registry (`gcloud storage`), never overwriting a versioned geometry object.

Per lake (621 directory lakes):
  shoreline = USGS NHD High Resolution waterbody UNION of the lake's connected pieces (the Engine's name-based pick dropped the
              unnamed / same-named neighbours of 67 lakes), repaired, tiny islands (< 100 m2) dropped, then two variants:
              ANALYSIS (Douglas-Peucker 25 m) and DISPLAY (50 m), snapped to a 5-decimal grid, gzip.
  lakes with no usable NHD shape get `geometry: null`, confidence MISSING and a reason. Nothing is invented.

Outputs (under --out):
  lakes/{lakeKey}/geometry.v1.display.geojson.gz     immutable
  lakes/{lakeKey}/geometry.v1.analysis.geojson.gz    immutable
  registry/lakes.v1.json                              the index (621 lakes)
  registry/manifest.v1.json, registry/README.txt

Inputs (research data, outside Git; env LAKE_BRAIN_DATA moves the root):
  directory_lakes_2026-10-13.json   the production directory snapshot (621 ids)
  geometry/lake_geometry_flags.csv  research audit flags per lake (confidence BEFORE the union, NID/USACE/OSM/GSW evidence)
  geometry/cache/*.json             NHD REST responses used by the research audit (reused; live queries only on a miss)
  geometry/engine_polygons_599.geojson.gz   the Engine's shipped polygons (identity evidence + degenerate-polygon detection)
  lake_features.csv                 classification features (research output)
  geometry/gsw_registry_v1.json     optional: JRC GSW inside-share recomputed on the new shorelines (gsw_recheck.py)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import numpy as np
import pyproj
import shapely
from shapely.geometry import Point, shape
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lake_geometry as lg  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.environ.get("LAKE_BRAIN_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
GEO = os.path.join(DATA, "geometry")
DEFAULTS = {
    "directory": os.path.join(DATA, "directory_lakes_2026-10-13.json"),
    "flags": os.path.join(GEO, "lake_geometry_flags.csv"),
    "cache": os.path.join(GEO, "cache"),
    "engine": os.path.join(GEO, "engine_polygons_599.geojson.gz"),
    "features": "/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv",
    "gsw": os.path.join(GEO, "gsw_registry_v1.json"),
    "out": os.path.join(GEO, "registry_out"),
}
BUCKET = "sector-lake-registry"
BASE_URL = f"https://storage.googleapis.com/{BUCKET}"
PROJECT = "sector-9393c"
GEOM_V = lg.GEOMETRY_VERSION
SCHEMA = "sector.lake-registry/v1"
UA = "SectorEngine-LakeRegistry/1.0 (mgcather07@gmail.com)"
NHD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12/query"
NHD_FIELDS = "OBJECTID,PERMANENT_IDENTIFIER,GNIS_NAME,AREASQKM,FTYPE,FCODE,FDATE,RESOLUTION"
LARGE_WATER_KM2 = 1000.0      # no Engine polygon and a seed this big: display-boundary policy is pending (M-geometry-05)
LICENSE = "USGS National Hydrography Dataset (public domain)"


# ------------------------------------------------------------------ inputs


def read_csv(p, key):
    with open(p, newline="") as fh:
        return {r[key]: r for r in csv.DictReader(fh)}


def file_sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def num(r, k):
    try:
        v = r.get(k)
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def coord_decimals(lake):
    def dec(x):
        t = repr(float(x))
        return len(t.split(".")[1]) if "." in t else 0
    return max(dec(lake["lat"]), dec(lake["lon"]))


def point_tolerance_m(lake):
    return max(300.0, 0.71 * 111_000.0 * 10 ** -coord_decimals(lake))


# ------------------------------------------------------------------ NHD REST (cache shared with research/geometry_audit.py)


class Cache:
    def __init__(self, path, live=True):
        self.path, self.live = path, live
        self.hits = self.misses = self.live_ok = self.live_fail = 0
        self.used = set()
        os.makedirs(path, exist_ok=True)

    def get(self, key, fn):
        p = os.path.join(self.path, hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")
        if os.path.exists(p):
            self.hits += 1
            self.used.add(p)
            return json.load(open(p))
        self.misses += 1
        if not self.live:
            raise LookupError("not in cache (offline): " + key[:80])
        v = fn()
        json.dump(v, open(p, "w"))
        self.used.add(p)
        return v


def http_json(url, params, timeout=150, retries=3, post=False):
    """GET (or POST for long parameter lists) a JSON document. The USGS service is slow at times (50 s for a trivial query)."""
    q = url if post else url + "?" + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(params).encode() if post else None
    err = None
    for k in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, data=body, headers={"User-Agent": UA}), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"{url}: {err}")


def nhd_candidates(lake, engine_feat, cache):
    """Candidate NHD HR lake/reservoir polygons around a lake. Same request + cache key as research/geometry_audit.py::ref_query,
    so the research cache is reused. engine_feat=None -> a +-0.08 degree window around the directory point."""
    if engine_feat is not None:
        w, s, e, n = shape(engine_feat["geometry"]).bounds
        eng = engine_feat["properties"].get("areaKm2") or 1.0
        minarea = max(0.02, 0.03 * eng)
    else:
        w, s, e, n = lake["lon"] - 0.08, lake["lat"] - 0.08, lake["lon"] + 0.08, lake["lat"] + 0.08
        minarea = 0.01
    env = f"{w - 0.002},{s - 0.002},{e + 0.002},{n + 0.002}"
    key = f"nhd|{lake['id']}|{env}|{minarea}"

    def attrs():
        return http_json(NHD_URL, {"geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                                   "spatialRel": "esriSpatialRelIntersects",
                                   "where": f"FTYPE IN (390,436) AND AREASQKM>={minarea}", "outFields": NHD_FIELDS,
                                   "returnGeometry": "false", "orderByFields": "AREASQKM DESC", "resultRecordCount": 60,
                                   "f": "json"})

    a = cache.get("A|" + key, attrs)
    if a.get("error"):
        return {"error": str(a["error"]), "cands": []}
    feats = [f["attributes"] for f in a.get("features", [])]
    pick = []
    for f in feats:
        if len(pick) < 10 or lg.name_match(f.get("GNIS_NAME"), lake["name"]) >= 0.99:
            pick.append(f)
    ids = ",".join(str(f["OBJECTID"]) for f in pick[:14])
    cands = []
    if ids:
        def geo():
            return http_json(NHD_URL, {"objectIds": ids, "outFields": NHD_FIELDS, "returnGeometry": "true", "outSR": 4326,
                                       "maxAllowableOffset": 0.00008, "f": "geojson"}, timeout=90)
        gj = cache.get("G|" + key + "|" + ids, geo)
        byid = {f["properties"]["OBJECTID"]: f for f in gj.get("features", [])}
        for f in pick[:14]:
            gf = byid.get(f["OBJECTID"])
            if gf and gf.get("geometry"):
                cands.append({"attrs": f, "geom": gf["geometry"]})
    return {"cands": cands}


# ------------------------------------------------------------------ one lake


def build_rows(lake, cands, engine_m, t):
    pt = Point(*t.transform(lake["lon"], lake["lat"]))
    rows = []
    for c in cands:
        g = lg.repair(shape(c["geom"]))
        if g is None:
            continue
        gm = lg.repair(lg.project(g, t))
        if gm is None or gm.is_empty:
            continue
        a = c["attrs"]
        nm = a.get("GNIS_NAME")
        cover = None
        if engine_m is not None and gm.area > 0:
            cover = gm.intersection(engine_m).area / gm.area
        rows.append({"g": gm, "g_deg": g, "area": gm.area, "contains_pt": bool(gm.contains(pt)), "dist": float(gm.distance(pt)),
                     "name": nm, "nm": lg.name_match(nm, lake["name"]), "cover": cover, "attrs": a})
    return rows


def fuse_pieces(pieces_m, gap_m=12.0):
    """Union of NHD pieces that were generalised separately: closes hairline gaps BETWEEN pieces (never fills bays inside one)."""
    if len(pieces_m) == 1:
        return pieces_m[0]
    u = unary_union(pieces_m)
    closed = u.buffer(gap_m).buffer(-gap_m)
    fill = closed.difference(u)
    add = []
    for comp in lg.parts_of(fill):
        touching = sum(1 for p in pieces_m if p.distance(comp) <= 1.0)
        if touching >= 2:
            add.append(comp)
    return unary_union([u] + add) if add else u


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if ms else None


def held_large_water(lake, cands):
    """No Engine polygon + an NHD water body >= 1,000 km2 whose envelope holds the directory point (Great Lakes, Lake of the
    Woods, Great Salt Lake, Iliamna): the display-boundary policy is pending, so the geometry is null with the NHD ids recorded.
    Decided from the envelope only (these polygons have millions of vertices)."""
    for c in cands:
        a = c["attrs"]
        if (a.get("AREASQKM") or 0) < LARGE_WATER_KM2:
            continue
        w, s, e, n = shape(c["geom"]).bounds
        if w - 0.01 <= lake["lon"] <= e + 0.01 and s - 0.01 <= lake["lat"] <= n + 0.01:
            return {"status": "held-large-water", "seed_area_km2": round(a["AREASQKM"], 1),
                    "nhd_ids": [a.get("PERMANENT_IDENTIFIER")], "pick_method": "envelope",
                    "reason": f"NHD shoreline exists ({a['AREASQKM']:,.0f} km2, {a.get('GNIS_NAME') or 'unnamed'}) but the "
                              "display-boundary policy for very large water is pending (research M-geometry-05); shipped as null, "
                              "not simplified blindly"}
    return None


def plan_lake(lake, flag, engine_feat, cache, notes):
    """Decide which NHD pieces make the lake and return the plan (no serialisation yet)."""
    t, _ = lg.transformers(lake["lon"], lake["lat"])
    usable = False
    engine_m = None
    if engine_feat is not None:
        g = lg.repair(shape(engine_feat["geometry"]))
        usable = g is not None and not lg.is_degenerate(g)
        if usable:
            engine_m = lg.repair(lg.project(g, t))
    plan = {"id": lake["id"], "engine_source": (flag.get("source") or "") if engine_feat is not None else "", "engine_usable": usable}
    try:
        res = nhd_candidates(lake, engine_feat if usable else None, cache)
        if res.get("error"):
            plan.update(status="query-error", reason="NHD service error: " + res["error"][:80])
            return plan
        if engine_feat is None:
            held = held_large_water(lake, res["cands"])
            if held:
                plan.update(held)
                return plan
        rows = build_rows(lake, res["cands"], engine_m, t)
        refs = [num(flag, "nid_surface_km2"), num(flag, "usace_area_km2")]
        seed, method = lg.match_seed(rows, usable, refs)
        if not seed and usable:       # the Engine polygon sits somewhere else (Skilak): look around the directory point instead
            res = nhd_candidates(lake, None, cache)
            rows = build_rows(lake, res["cands"], None, t)
            seed, method = lg.match_seed(rows, False, refs)
            usable = False
    except LookupError:
        plan.update(status="query-missing", reason="NHD search around the directory point is not cached and live queries were disabled (--offline)")
        return plan
    except Exception as e:  # noqa: BLE001
        plan.update(status="query-error", reason="NHD search around the directory point failed (USGS service error: " + str(e)[-60:] + "); re-run to retry")
        return plan
    plan["pick_method"] = method
    if not seed:
        plan.update(status="no-nhd", reason="no NHD lake/reservoir (FTYPE 390/436) polygon matches the lake name near its "
                    "coordinates or is an unnamed water containing them")
        if engine_feat is not None:
            why = ("the Engine polygon is OSM-derived (ODbL) and no NHD shape corroborates it: withheld from the public bucket pending a "
                   "license decision" if plan["engine_source"] == "osm" else
                   "the Engine polygon is degenerate or in the wrong place and no NHD shape replaces it")
            plan["reason"] += "; " + why
            plan["engine_polygon"] = plan["engine_source"] or "present"
        near = sorted(rows, key=lambda r: r["dist"])[:1]
        if near:
            plan["nearest"] = {"name": near[0]["name"], "areaKm2": round(near[0]["area"] / 1e6, 3), "distM": round(near[0]["dist"])}
        return plan
    seed_area = unary_union([r["g"] for r in seed]).area / 1e6
    adj = lg.adjacent_pieces(rows, seed)
    base_km2 = seed_area
    full = unary_union([r["g"] for r in seed + adj])
    full_km2 = full.area / 1e6
    refs = [num(flag, "nid_surface_km2"), num(flag, "usace_area_km2")]
    use_adj, why = (lg.choose_variant(base_km2, full_km2, refs) if adj else (True, "no adjacent pieces"))
    members = seed + (adj if use_adj else [])
    plan.update(status="ok", seed=seed, adj=adj, use_adj=use_adj, adj_why=why, members=members,
                adj_area_km2=round(sum(r["area"] for r in adj) / 1e6, 3), base_km2=base_km2, full_km2=full_km2,
                pieces_m=[r["g"] for r in members], rows=rows)
    return plan


def resolve_shared_adjacent(plans):
    """An unnamed adjacent NHD piece that touches two DIFFERENT lakes (Weiss / Neely Henry on the Coosa) belongs to one: the nearer
    seed keeps it (10 m bins), then the lake whose area gets closer to its pool-area reference, then lakeId. Returns the number
    of (lake, piece) assignments removed."""
    claims = {}
    for lake, flag, plan in plans:
        if plan.get("status") == "ok" and plan["use_adj"]:
            for r in plan["adj"]:
                claims.setdefault(r["attrs"]["PERMANENT_IDENTIFIER"], []).append((lake, flag, plan, r))
    removed = 0
    for pid, cl in claims.items():
        if len(cl) < 2 or len({tuple(sorted(x["attrs"]["PERMANENT_IDENTIFIER"] for x in c[2]["seed"])) for c in cl}) < 2:
            continue

        def key(c):
            lake, flag, plan, r = c
            seed_u = unary_union([x["g"] for x in plan["seed"]])
            d = round(r["g"].distance(seed_u) / 10.0)
            refs = [x for x in (num(flag, "nid_surface_km2"), num(flag, "usace_area_km2")) if x]
            dref = min((abs(math.log((plan["base_km2"] + r["area"] / 1e6) / x)) for x in refs), default=9.0)
            return (d, round(dref, 3), lake["id"])
        winner = min(cl, key=key)
        for c in cl:
            if c is winner:
                continue
            _l, flag, plan, r = c
            plan["adj"] = [x for x in plan["adj"] if x is not r]
            plan["members"] = [x for x in plan["members"] if x is not r]
            plan["adj_area_km2"] = round(sum(x["area"] for x in plan["adj"]) / 1e6, 3)
            plan["adj_why"] += f"; piece {pid} assigned to the nearer lake {winner[0]['id']}"
            if not plan["adj"]:
                plan["use_adj"] = True
            removed += 1
    return removed


def make_geometry(lake, plan):
    """Union -> analysis + display variants. Returns dict or None."""
    t, tinv = lg.transformers(lake["lon"], lake["lat"])
    members = plan["members"]
    fused = fuse_pieces([r["g"] for r in members])
    union_deg = lg.repair(lg.project(fused, tinv))
    if union_deg is None:
        return None
    center = lg.center_of(union_deg)
    ana, ana_a, ana_t = lg.make_variant(union_deg, lg.ANALYSIS_TOL_M, center)
    dis, dis_a, dis_t = lg.make_variant(union_deg, lg.DISPLAY_TOL_M, center)
    if ana is None or dis is None:
        return None
    return {"union_deg": union_deg, "analysis": ana, "display": dis, "analysis_km2": ana_a, "display_km2": dis_a, "center": center,
            "analysis_tol": ana_t, "display_tol": dis_t}


# ------------------------------------------------------------------ registry entry


def date_of(plan):
    top = max(plan["members"], key=lambda r: r["area"])
    ds = sorted(d for d in (iso(r["attrs"].get("FDATE")) for r in plan["members"]) if d)
    return iso(top["attrs"].get("FDATE")), (ds[0], ds[-1]) if ds else None


def features_of(fr):
    if not fr:
        return None
    rt = num(fr, "res_time_d")
    return {"lakeClass": fr.get("lake_class") or None, "regime": fr.get("regime") or None, "region": fr.get("region") or None,
            "size": fr.get("size") or None, "depthClass": fr.get("depth_class") or None,
            "residenceTimeDays": None if rt is None else round(rt, 1), "hasDam": fr.get("hasDam") == "True"}


def pool_extents(lake, flag, area):
    out = []
    u = num(flag, "usace_area_km2")
    if flag.get("usace_matched") == "True" and u:
        out.append({"kind": "floodPool" if flag.get("usace_dry") in ("True", "Yes", "Y", "1", "true") else "maxConservationPool",
                    "source": "usace-rez", "name": flag.get("usace_name") or None, "id": flag.get("usace_nidid") or None,
                    "areaKm2": round(u, 2), "ratioToShoreline": round(area / u, 3) if area else None,
                    "note": "USACE reservoir polygon (maximum conservation pool or a reasonable representation); reference only"})
    n = num(flag, "nid_surface_km2")
    if n:
        out.append({"kind": "normalPool", "source": "nid", "name": flag.get("nid_name") or None, "id": flag.get("nid_id") or None,
                    "areaKm2": round(n, 2), "ratioToShoreline": round(area / n, 3) if area else None,
                    "note": "National Inventory of Dams reported normal-pool surface area (owner-reported, has unit errors); reference only"})
    if lake.get("fullPoolFt") is not None:
        out.append({"kind": "fullPoolElevation", "source": "sector-directory", "elevationFt": lake["fullPoolFt"],
                    "basis": lake.get("poolBasis"), "confidence": lake.get("poolConfidence")})
    return out


def external_ids(plan, flag, osm_ok):
    ids = {}
    if plan and plan.get("members"):
        order = sorted(plan["seed"], key=lambda r: -r["area"]) + sorted([r for r in plan["members"] if r not in plan["seed"]], key=lambda r: -r["area"])
        ids["nhd"] = [r["attrs"].get("PERMANENT_IDENTIFIER") for r in order]
        g = [str(r["attrs"].get("GNIS_ID")) for r in order if r["attrs"].get("GNIS_ID")]
        ids["gnisId"] = g[0] if g else None
    else:
        ids["nhd"] = []
        ids["gnisId"] = None
    ids["nidId"] = (flag.get("nid_id") or flag.get("usace_nidid") or None)
    ids["osm"] = flag.get("osm_best_type") if osm_ok else None
    ids["wikidata"] = flag.get("osm_wikidata") if osm_ok and flag.get("osm_wikidata") else None
    ids["hydrolakes"] = flag.get("hl_top_id") if flag.get("hl_matched") == "True" else None
    ids["grand"] = flag.get("hl_grand_id") if flag.get("hl_matched") == "True" and flag.get("hl_grand_id") not in (None, "", "0") else None
    return ids


def aliases_of(lake, plan, flag):
    seen, out = {lake["name"].lower()}, []
    cands = [r["attrs"].get("GNIS_NAME") for r in (plan.get("members") or [])] if plan else []
    cands += [flag.get("usace_name"), flag.get("hl_top_name")] if flag else []
    for n in cands:
        if n and n.lower() not in seen and lg.name_match(n, lake["name"]) >= 0.5:
            seen.add(n.lower())
            out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for k in ("directory", "flags", "cache", "engine", "features", "gsw", "out"):
        ap.add_argument("--" + k, default=DEFAULTS[k])
    ap.add_argument("--only", default="", help="comma-separated lake ids (debug)")
    ap.add_argument("--offline", action="store_true", help="never query the NHD REST service (cache only)")
    ap.add_argument("--built-at", default="", help="ISO timestamp recorded as geometryUpdatedAt (default: now, UTC)")
    ap.add_argument("--upload", action="store_true", help="write to gs://%s (default: dry run)" % BUCKET)
    ap.add_argument("--enrich", action="store_true", help="fetch GNIS_ID for the selected NHD features (a few hundred small GETs)")
    a = ap.parse_args()

    built_at = a.built_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    directory = json.load(open(a.directory))
    lakes = directory["lakes"]
    flags = read_csv(a.flags, "id")
    feats = read_csv(a.features, "id") if os.path.exists(a.features) else {}
    engine = {f["properties"]["id"]: f for f in json.load(gzip.open(a.engine, "rt"))["features"]}
    gsw_new = json.load(open(a.gsw)) if os.path.exists(a.gsw) else {}
    cache = Cache(a.cache, live=not a.offline)
    if a.only:
        want = set(a.only.split(","))
        lakes = [l for l in lakes if l["id"] in want]

    keys = [lg.lake_key(l["id"]) for l in lakes]
    assert len(set(keys)) == len(keys), "lakeKey collision"
    out = a.out
    if not a.only:
        shutil.rmtree(os.path.join(out, "lakes"), ignore_errors=True)
    os.makedirs(os.path.join(out, "registry"), exist_ok=True)

    plans, stats = [], {}
    t0 = time.time()
    for i, lake in enumerate(sorted(lakes, key=lambda l: l["id"])):
        flag = flags.get(lake["id"], {})
        tl = time.time()
        plan = plan_lake(lake, flag, engine.get(lake["id"]), cache, stats)
        if time.time() - tl > 8:
            print(f"  slow lake {lake['id']}: plan {time.time() - tl:.1f}s", flush=True)
        plans.append((lake, flag, plan))
        if (i + 1) % 100 == 0:
            print(f"  planned {i + 1}/{len(lakes)} ({time.time() - t0:.0f}s) cache hit/miss {cache.hits}/{cache.misses}", flush=True)
    stats["shared_adjacent_reassigned"] = resolve_shared_adjacent(plans)
    entries = []
    for i, (lake, flag, plan) in enumerate(plans):
        tl = time.time()
        geom = make_geometry(lake, plan) if plan.get("status") == "ok" else None
        if time.time() - tl > 15:
            print(f"  slow geometry {lake['id']}: {time.time() - tl:.1f}s", flush=True)
        entries.append((lake, flag, plan, geom))
        plan.pop("rows", None)
        plan.pop("pieces_m", None)

    if a.enrich:
        enrich(entries, cache)

    index, files = [], []
    for lake, flag, plan, geom in entries:
        index.append(registry_entry(lake, flag, plan, geom, feats.get(lake["id"]), gsw_new.get(lake["id"]), built_at, out, files))
    link_members(index)
    problems = [p for e in index for p in lg.validate_entry(e, BASE_URL)]
    if problems:
        raise SystemExit("index schema problems:\n  " + "\n  ".join(problems[:20]))

    build_commit = git(["rev-parse", "HEAD"])
    dirty = bool(git(["status", "--porcelain", "--", "jobs/lake-geometry"]))
    inputs = {k: {"path": getattr(a, k), "sha256": file_sha256(getattr(a, k))} for k in ("directory", "flags", "engine", "features")
              if os.path.exists(getattr(a, k))}
    if os.path.exists(a.gsw):
        inputs["gsw"] = {"path": a.gsw, "sha256": file_sha256(a.gsw)}
    h = hashlib.sha256()
    for p in sorted(cache.used):
        h.update(os.path.basename(p).encode() + file_sha256(p).encode())
    inputs["nhdCache"] = {"path": a.cache, "files": len(cache.used), "sha256": h.hexdigest(),
                          "note": "NHD REST responses (maxAllowableOffset 0.00008 deg ~ 9 m server-side generalisation)"}
    manifest = make_manifest(index, files, inputs, build_commit, dirty, built_at, cache)
    reg = {"schema": SCHEMA, "geometryVersion": GEOM_V, "generatedAt": built_at, "count": len(index), "baseUrl": BASE_URL,
           "license": LICENSE, "lakes": index}
    rb = json.dumps(reg, separators=(",", ":"), sort_keys=False, allow_nan=False).encode()
    open(os.path.join(out, "registry", "lakes.v1.json"), "wb").write(rb)
    manifest["files"]["registry/lakes.v1.json"] = {"bytes": len(rb), "gzipBytes": len(lg.gzip_bytes(rb)), "sha256": lg.sha256(rb)}
    manifest["objectsDigest"] = {"count": len(files), "sha256": hashlib.sha256("\n".join(
        f"{e['geometry']['sha256']['display']} {e['geometry']['sha256']['analysis']}" for e in index if e["geometry"]).encode()).hexdigest(),
        "note": "sha256 over the per-lake display+analysis object hashes in lakeId order; each hash is in registry/lakes.v1.json"}
    json.dump(manifest, open(os.path.join(out, "registry", "manifest.v1.json"), "w"), indent=1, sort_keys=False)
    open(os.path.join(out, "registry", "README.txt"), "w").write(README.format(base=BASE_URL, bucket=BUCKET, built=built_at, count=len(index)))
    summarize(index, manifest)
    if a.upload:
        upload(out)
    else:
        print("\nDRY RUN: nothing uploaded. Files are in", out, "\nTo publish: python build_geometry.py --upload")


def git(args):
    try:
        return subprocess.run(["git", "-C", REPO] + args, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def enrich(entries, cache, batch=100):
    """GNIS_ID for the selected NHD features (the research cache did not request it); batched POSTs. Failures leave gnisId null."""
    oids = sorted({r["attrs"]["OBJECTID"] for _l, _f, plan, _g in entries if plan.get("status") == "ok" for r in plan["members"]})
    got, fail = {}, 0
    for k in range(0, len(oids), batch):
        chunk = oids[k:k + batch]
        ids = ",".join(map(str, chunk))

        def q():
            return http_json(NHD_URL, {"objectIds": ids, "outFields": "OBJECTID,GNIS_ID,REACHCODE", "returnGeometry": "false", "f": "json"},
                             post=True)
        try:
            res = cache.get("ENR|" + ids, q)
            for f in res.get("features", []):
                got[f["attributes"]["OBJECTID"]] = f["attributes"]
        except Exception:  # noqa: BLE001
            fail += 1
    for _l, _f, plan, _g in entries:
        if plan.get("status") == "ok":
            for r in plan["members"]:
                r["attrs"]["GNIS_ID"] = (got.get(r["attrs"]["OBJECTID"]) or {}).get("GNIS_ID")
    print(f"  enrichment: {len(got)}/{len(oids)} features, {fail} failed batches")


def registry_entry(lake, flag, plan, geom, fr, gsw, built_at, out, files):
    key = lg.lake_key(lake["id"])
    tol_m = point_tolerance_m(lake)
    osm_ok = (num(flag, "osm_name_match") or 0) >= 0.5 and (num(flag, "osm_bbox_iou") or 0) >= 0.5
    e = {"lakeId": lake["id"], "lakeKey": key, "name": lake["name"], "aliases": aliases_of(lake, plan, flag),
         "memberIds": [lake["id"]], "state": lake["state"], "states": lake.get("states") or [lake["state"]],
         "location": {"lat": lake["lat"], "lon": lake["lon"], "source": "sector-directory", "pointFlag": None},
         "externalIds": external_ids(plan, flag, osm_ok), "bbox": None, "centroid": None, "labelPoint": None, "areaKm2": None,
         "geometry": None, "poolExtents": [], "geometryVersion": GEOM_V, "geometryUpdatedAt": built_at,
         "geometryConfidence": None, "pointFlag": None, "classification": features_of(fr)}
    before = flag.get("confidence") or "MISSING"
    facts = {"has_geometry": geom is not None, "engine_source": plan.get("engine_source"), "identity_pick": plan.get("pick_method")}
    if geom is None:
        reason = plan.get("reason") or "no usable polygon"
        e["geometryMissingReason"] = reason
        if plan.get("engine_polygon"):
            e["geometryWithheld"] = {"engineSource": plan["engine_polygon"]}
        if plan.get("status") == "held-large-water":
            e["geometryHeld"] = {"nhdIds": plan.get("nhd_ids"), "nhdAreaKm2": plan.get("seed_area_km2")}
        facts["missing_reason"] = reason
        lvl, reasons = lg.derive_confidence(facts)
        e["geometryConfidence"] = {"level": lvl, "score": 0.0, "reasons": reasons, "before": before}
        e["poolExtents"] = pool_extents(lake, flag, None)
        return e
    ana, dis, center = geom["analysis"], geom["display"], geom["center"]
    to_m, to_deg = lg.transformers(*center)
    ana_m = lg.project(ana, to_m)
    area = geom["analysis_km2"]
    cen = lg.project(ana_m.centroid, to_deg)
    lab = lg.project(ana_m.representative_point(), to_deg)
    w, s, e_, n = ana.bounds
    e["bbox"] = [round(w, 5), round(s, 5), round(e_, 5), round(n, 5)]
    e["centroid"] = [round(cen.x, 5), round(cen.y, 5)]
    e["labelPoint"] = [round(lab.x, 5), round(lab.y, 5)]
    e["areaKm2"] = round(area, 3)
    t_lake, _ = lg.transformers(lake["lon"], lake["lat"])
    dist = float(lg.project(ana, t_lake).distance(Point(*t_lake.transform(lake["lon"], lake["lat"]))))
    pf = lg.point_flag(dist, tol_m, area)
    e["pointFlag"] = pf
    e["location"]["pointFlag"] = pf
    e["location"]["distanceToShorelineM"] = round(dist)
    src_date, rng = date_of(plan)
    members = sorted(plan["members"], key=lambda r: -r["area"])
    props = {"lakeId": lake["id"], "lakeKey": key, "geometryVersion": GEOM_V, "extentKind": "shoreline-nhd-hr-union",
             "source": "usgs-nhd-hr", "sourceIds": [r["attrs"].get("PERMANENT_IDENTIFIER") for r in members], "sourceDate": src_date,
             "license": LICENSE}
    seed_ids = [r["attrs"].get("PERMANENT_IDENTIFIER") for r in sorted(plan["seed"], key=lambda r: -r["area"])]
    paths = {}
    ginfo = {}
    for variant, g, tol, ar in (("display", dis, geom["display_tol"], geom["display_km2"]), ("analysis", ana, geom["analysis_tol"], geom["analysis_km2"])):
        raw = lg.feature_bytes(g, dict(props, variant=variant, toleranceM=tol, areaKm2=round(ar, 3)))
        gz = lg.gzip_bytes(raw)
        rel = f"lakes/{key}/geometry.{GEOM_V}.{variant}.geojson.gz"
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(gz)
        files.append(rel)
        paths[variant] = {"url": f"{BASE_URL}/{rel}", "rel": rel, "gz": len(gz), "raw": len(raw), "sha": lg.sha256(gz),
                          "vertices": lg.nverts(g), "holes": lg.n_holes(g), "areaKm2": round(ar, 3), "tol": tol}
    e["geometry"] = {
        "extentKind": "shoreline-nhd-hr-union", "source": "usgs-nhd-hr", "sourceIds": props["sourceIds"], "seedIds": seed_ids,
        "sourceDate": src_date,
        "sourceDateRange": list(rng) if rng else None, "pickMethod": plan["pick_method"], "pieces": len(members),
        "adjacentPieces": {"found": len(plan["adj"]), "included": len(plan["adj"]) if plan["use_adj"] else 0,
                           "areaKm2": plan["adj_area_km2"], "decision": plan["adj_why"]},
        "islands": paths["analysis"]["holes"], "areaKm2": round(area, 3),
        "sourceAreaKm2": round(sum(r["attrs"].get("AREASQKM") or 0 for r in members), 3), "areaDisplayKm2": paths["display"]["areaKm2"],
        "displayToleranceM": lg.DISPLAY_TOL_M, "analysisToleranceM": lg.ANALYSIS_TOL_M,
        "displayToleranceEffectiveM": paths["display"]["tol"], "analysisToleranceEffectiveM": paths["analysis"]["tol"],
        "displayVertices": paths["display"]["vertices"], "analysisVertices": paths["analysis"]["vertices"],
        "displayUrl": paths["display"]["url"], "analysisUrl": paths["analysis"]["url"],
        "bytes": {"displayGzip": paths["display"]["gz"], "displayRaw": paths["display"]["raw"],
                  "analysisGzip": paths["analysis"]["gz"], "analysisRaw": paths["analysis"]["raw"]},
        "sha256": {"display": paths["display"]["sha"], "analysis": paths["analysis"]["sha"]},
        "license": LICENSE}
    e["poolExtents"] = pool_extents(lake, flag, area)
    # ---- confidence, re-derived on the new geometry
    # fragmentation is judged on the matched water (the seed): the adjacent NHD pieces are part of the lake on purpose, and are
    # often separated from it by a dam or narrows, so they do not count as "several substantial parts"
    seed_m = unary_union([r["g"] for r in plan["seed"]])
    parts = lg.parts_of(seed_m)
    tot = sum(p.area for p in parts) or 1.0
    allowed = max(3000.0, 3 * tol_m, 600.0 * math.sqrt(area))
    gsw_v = None
    if gsw and gsw.get("gsw_inside_ge50_pct") is not None:
        gsw_v = gsw["gsw_inside_ge50_pct"]
    elif num(flag, "gsw_inside_ge50_pct") is not None and abs((num(flag, "geom_area_km2") or 0) / max(area, 1e-9) - 1) < 0.02:
        gsw_v = num(flag, "gsw_inside_ge50_pct")      # unchanged shoreline: the research value still applies
    adj_rej = 0.0 if plan["use_adj"] else plan["adj_area_km2"]
    nmatch = max(r["nm"] for r in plan["members"])
    facts.update({"point_flag": pf, "dist_m": dist, "allowed_m": allowed, "area_km2": area, "nid_km2": num(flag, "nid_surface_km2"),
                  "usace_km2": num(flag, "usace_area_km2"), "gsw_ge50_pct": gsw_v, "osm_ok": osm_ok, "name_match": nmatch,
                  "n_substantial_parts": sum(1 for p in parts if p.area / tot >= 0.01), "adjacent_rejected_km2": adj_rej})
    lvl, reasons = lg.derive_confidence(facts)
    corr = 0
    for r in (num(flag, "nid_surface_km2"), num(flag, "usace_area_km2")):
        if r and 0.9 <= area / r <= 1.1:
            corr += 1
    if gsw_v is not None and gsw_v >= 80:
        corr += 1
    if osm_ok and (num(flag, "osm_bbox_iou") or 0) >= 0.8:
        corr += 1
    e["geometryConfidence"] = {"level": lvl, "score": lg.confidence_score(lvl, reasons, corr), "reasons": reasons, "before": before,
                               "evidence": {"nidAreaRatio": None if not num(flag, "nid_surface_km2") else round(area / num(flag, "nid_surface_km2"), 3),
                                            "usaceAreaRatio": None if not num(flag, "usace_area_km2") else round(area / num(flag, "usace_area_km2"), 3),
                                            "gswWaterSharePct": gsw_v, "osmCorroborated": osm_ok}}
    return e


def link_members(index):
    """memberIds: directory ids that are the same water (they share at least one NHD permanent id)."""
    parent = {e["lakeId"]: e["lakeId"] for e in index}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    owner = {}
    for e in index:
        for nid in ((e["geometry"] or {}).get("seedIds") or []):
            if nid in owner:
                parent[find(e["lakeId"])] = find(owner[nid])
            else:
                owner[nid] = e["lakeId"]
    groups = {}
    for e in index:
        groups.setdefault(find(e["lakeId"]), []).append(e["lakeId"])
    for e in index:
        e["memberIds"] = sorted(groups[find(e["lakeId"])])


def make_manifest(index, files, inputs, commit, dirty, built_at, cache):
    from collections import Counter
    levels = Counter(e["geometryConfidence"]["level"] for e in index)
    before = Counter(e["geometryConfidence"]["before"] for e in index)
    disp = [e["geometry"]["bytes"]["displayGzip"] for e in index if e["geometry"]]
    ana = [e["geometry"]["bytes"]["analysisGzip"] for e in index if e["geometry"]]
    return {
        "schema": SCHEMA, "geometryVersion": GEOM_V, "generatedAt": built_at, "bucket": f"gs://{BUCKET}", "baseUrl": BASE_URL,
        "build": {"commit": commit, "dirtyJobDir": dirty, "script": "jobs/lake-geometry/build_geometry.py",
                  "python": platform.python_version(), "shapely": shapely.__version__, "geos": shapely.geos_version_string,
                  "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str, "numpy": np.__version__},
        "parameters": {"displayToleranceM": lg.DISPLAY_TOL_M, "analysisToleranceM": lg.ANALYSIS_TOL_M, "minHoleM2": lg.MIN_HOLE_M2,
                       "minPartM2": lg.MIN_PART_M2, "toleranceSizeFraction": lg.TOL_SIZE_FRACTION, "toleranceMinM": lg.TOL_MIN_M,
                       "coordDecimals": lg.COORD_DECIMALS, "adjacentDistM": lg.ADJ_DIST_M,
                       "adjacentMinShare": lg.ADJ_MIN_SHARE, "coverMin": lg.COVER_MIN, "largeWaterHeldKm2": LARGE_WATER_KM2,
                       "gzip": "level 9, mtime 0", "crs": "EPSG:4326"},
        "counts": {"lakes": len(index), "withGeometry": len(disp), "geometryNull": len(index) - len(disp),
                   "confidenceAfter": dict(levels), "confidenceBefore": dict(before),
                   "pointFlag": dict(Counter(e["pointFlag"] or "none" for e in index)),
                   "memberGroups": sum(1 for e in index if len(e["memberIds"]) > 1)},
        "bytes": {"displayGzipTotal": sum(disp), "analysisGzipTotal": sum(ana), "objectsGzipTotal": sum(disp) + sum(ana),
                  "displayGzipMedian": int(np.median(disp)) if disp else 0, "displayGzipMax": max(disp) if disp else 0},
        "inputs": inputs,
        "confidenceRules": "docs/brains/LAKE_REGISTRY_GEOMETRY_CONTRACT.md section 'Confidence'",
        "nhdCache": {"hits": cache.hits, "misses": cache.misses},
        "files": {}, "objectCount": len(files),
    }


def summarize(index, m):
    c = m["counts"]
    print("\n== build summary")
    print(f"lakes {c['lakes']}  with geometry {c['withGeometry']}  null {c['geometryNull']}")
    print("confidence before:", c["confidenceBefore"])
    print("confidence after: ", c["confidenceAfter"])
    b = m["bytes"]
    print(f"display gz total {b['displayGzipTotal'] / 1e6:.2f} MB (median {b['displayGzipMedian']} B, max {b['displayGzipMax']} B), "
          f"analysis gz total {b['analysisGzipTotal'] / 1e6:.2f} MB")
    print("member groups:", c["memberGroups"], " pointFlag:", c["pointFlag"])


README = """Sector Lake Registry (gs://{bucket})
Built {built}. {count} lakes. Geometry: USGS National Hydrography Dataset High Resolution waterbodies (public domain).

registry/lakes.v1.json              the index: identity, provenance, bbox, area, confidence, URLs. Fetch this first.
registry/manifest.v1.json           build record: counts, input checksums, parameters, per-file sha256
lakes/{{lakeKey}}/geometry.v1.display.geojson.gz    shoreline, 50 m simplification (draw this)
lakes/{{lakeKey}}/geometry.v1.analysis.geojson.gz   shoreline, 25 m simplification (measure with this)

lakeKey = lakeId with every run of non-alphanumerics replaced by one underscore ("Guntersville|AL" -> "Guntersville_AL").
Geometry objects are IMMUTABLE (Cache-Control: public, max-age=31536000, immutable). A new geometry is a NEW path (v2);
the index points at the latest. Never overwrite a versioned object. The index is cached for 5 minutes.
Objects are gzip with Content-Encoding: gzip; fetch() and curl --compressed decode them. geometry == null means no
usable shoreline (see geometryMissingReason); confidence is MISSING. Base URL: {base}
Contract: docs/brains/LAKE_REGISTRY_GEOMETRY_CONTRACT.md in the sector-engine repository.
"""


# ------------------------------------------------------------------ upload


def sh(cmd, check=True):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout.strip():
        print(r.stdout.strip()[-1500:])
    if r.returncode and check:
        print(r.stderr.strip()[-2000:])
        raise SystemExit(f"gcloud failed ({r.returncode}): {' '.join(cmd[:5])}")
    return r


def upload(out):
    """Versioned geometry objects: --no-clobber (a published object is never replaced). Index: short cache, replaceable."""
    dest = f"gs://{BUCKET}"
    common = ["gcloud", "storage", "cp", "--project", PROJECT]
    sh(common + ["--recursive", "--no-clobber", "--content-type=application/geo+json", "--content-encoding=gzip",
                 "--cache-control=public, max-age=31536000, immutable", os.path.join(out, "lakes"), dest + "/"])
    tmp = tempfile.mkdtemp(prefix="registry_up_")
    try:
        src = os.path.join(out, "registry", "lakes.v1.json")
        stage = os.path.join(tmp, "lakes.v1.json")
        open(stage, "wb").write(lg.gzip_bytes(open(src, "rb").read()))
        sh(common + ["--content-type=application/json", "--content-encoding=gzip", "--cache-control=public, max-age=300",
                     stage, dest + "/registry/lakes.v1.json"])
        for f, ct in (("manifest.v1.json", "application/json"), ("README.txt", "text/plain; charset=utf-8")):
            sh(common + [f"--content-type={ct}", "--cache-control=public, max-age=300", os.path.join(out, "registry", f), dest + f"/registry/{f}"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
