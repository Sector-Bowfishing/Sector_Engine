#!/usr/bin/env python3
"""Track 8 (species presence) evidence probe. Read-only against public APIs; nothing is written to any RTDB/bucket.

Subcommands (outputs go to the data dir, never into Git; the committed summary is produced by `summary`):
  audit     aggregate structure of the private presence release (counts only; rows are never written to disk)
  nas       download USGS NAS occurrence records for the target species, match to lake polygons
  gbif      GBIF occurrence probes per lake bbox -> point-in-polygon match
  wbd       lake -> HUC8 via USGS WBD ArcGIS service
  coverage  combine nas/gbif/wbd outputs into per-lake evidence tiers (aggregates)
  validate  in-memory comparison of private presence vs independent observed records -> aggregate metrics only
  summary   write docs/research/lake-brain/data/presence_sources_summary.json
Usage: presence_evidence_probe.py <cmd> [--data DIR]
"""
import argparse, collections, gzip, json, math, os, subprocess, sys, time
import requests
from shapely.geometry import shape, Point, box
from shapely.strtree import STRtree

DATA = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain"
OUT = DATA + "/species"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UA = {"User-Agent": "SectorEngine-LakeBrain-research/1.0 (mgcather07@gmail.com; polite, low-rate)"}
# Sector species id -> (scientific name, NAS speciesID(s), GBIF scientific name)
SPECIES = {
    "common_carp": ("Cyprinus carpio", [4]),
    "grass_carp": ("Ctenopharyngodon idella", [514, 2947, 2948]),
    "bighead_carp": ("Hypophthalmichthys nobilis", [551]),
    "silver_carp": ("Hypophthalmichthys molitrix", [549]),
    "black_carp": ("Mylopharyngodon piceus", [573, 2949, 2950]),
    "smallmouth_buffalo": ("Ictiobus bubalus", [361]),
    "bigmouth_buffalo": ("Ictiobus cyprinellus", [362]),
    "black_buffalo": ("Ictiobus niger", [363]),
    "alligator_gar": ("Atractosteus spatula", [755]),
    "longnose_gar": ("Lepisosteus osseus", []),     # NAS has no speciesID (no non-native record)
    "shortnose_gar": ("Lepisosteus platostomus", [757]),
    "spotted_gar": ("Lepisosteus oculatus", [756]),
    # outside the 12 assessed species; bowfishing relevant (Biological Brain knows them, presence does not assess them)
    "bowfin": ("Amia calva", [305]),
    "freshwater_drum": ("Aplodinotus grunniens", [946]),
}
ASSESSED12 = [k for k in SPECIES if k not in ("bowfin", "freshwater_drum")]

def get(url, params=None, tries=4, timeout=90):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (i + 1)); continue
            return r
        except requests.RequestException:
            time.sleep(2 * (i + 1))
    return None

def lakes():
    return json.load(open(DATA + "/directory_lakes_2026-10-13.json"))["lakes"]

def polygons():
    g = json.load(gzip.open(DATA + "/geometry/engine_polygons_599.geojson.gz"))
    return {f["properties"]["id"]: shape(f["geometry"]) for f in g["features"]}

def km_to_deg(km, lat):
    return km / 111.0, km / (111.0 * max(0.2, math.cos(math.radians(lat))))

def lake_geoms(buffer_m=0):
    """lake id -> shapely geometry (polygon buffered by buffer_m, else point-buffer of ~ 1 km fallback)"""
    polys = polygons(); out = {}; kinds = {}
    for l in lakes():
        g = polys.get(l["id"])
        if g is not None:
            kinds[l["id"]] = "polygon"
        else:
            dlat, dlon = km_to_deg(1.0, l["lat"]); g = Point(l["lon"], l["lat"]).buffer(max(dlat, dlon)); kinds[l["id"]] = "point1km"
        if buffer_m and kinds[l["id"]] == "polygon":
            dlat, _ = km_to_deg(buffer_m / 1000.0, l["lat"]); g = g.buffer(dlat)
        out[l["id"]] = g
    return out, kinds

# ----------------------------------------------------------------------------- audit
def presence_rows_in_memory():
    ptr = json.loads(subprocess.check_output(["gcloud", "storage", "cat", "gs://sector-lake-brain/presence/latest.json"]))
    raw = subprocess.check_output(["gcloud", "storage", "cat", "gs://sector-lake-brain/" + ptr["path"]])
    return ptr, json.loads(raw)

def cmd_audit(a):
    ptr, d = presence_rows_in_memory(); rows = d["rows"]; C = collections.Counter
    obs = {"established", "reported", "stocked"}
    out = {"release": ptr["researchVersion"], "rows": len(rows), "lakes": len({r["lakeId"] for r in rows}),
           "assessedSpecies": d["assessedSpecies"], "sourceArtifacts": [s.split(" sha256")[0] for s in d["sourceArtifacts"]],
           "byState": C(r["presenceState"] for r in rows), "byConfidence": C(r["confidence"] for r in rows),
           "byTier": C(str(r["sourceTier"]) for r in rows), "byNative": C(r["nativeStatus"] for r in rows),
           "stateByTier": {f"{t}|{s}": n for (t, s), n in C((str(r["sourceTier"]), r["presenceState"]) for r in rows).items()},
           "speciesByState": {}, "lakesWithObsGrade": 0, "lakesAllUnknown": 0, "lakesWithAnyNonUnknown": 0}
    per = collections.defaultdict(list)
    for r in rows:
        per[r["lakeId"]].append(r)
        out["speciesByState"].setdefault(r["speciesId"], C())[r["presenceState"]] += 1
    out["lakesWithObsGrade"] = sum(1 for v in per.values() if any(r["presenceState"] in obs for r in v))
    out["lakesAllUnknown"] = sum(1 for v in per.values() if all(r["presenceState"] == "unknown" for r in v))
    out["lakesWithAnyNonUnknown"] = len(per) - out["lakesAllUnknown"]
    out["lakesWithEstablished"] = sum(1 for v in per.values() if any(r["presenceState"] == "established" for r in v))
    out["lakesWithOnlyRange"] = sum(1 for v in per.values() if not any(r["presenceState"] in obs | {"historical", "failed/eradicated"} for r in v)
                                    and any(r["presenceState"] == "inRangeUnconfirmed" for r in v))
    yrs = [int(r["latestRecord"]) for r in rows if str(r.get("latestRecord") or "").isdigit()]
    out["latestRecordYear"] = {"n": len(yrs), "min": min(yrs), "median": sorted(yrs)[len(yrs) // 2], "max": max(yrs),
                               "ge2015": sum(y >= 2015 for y in yrs), "lt1990": sum(y < 1990 for y in yrs)}
    out["rowsWithLatestRecord"] = len(yrs)
    out["nonUnknownRows"] = sum(1 for r in rows if r["presenceState"] != "unknown")
    out["nonUnknownMissingLatestRecord"] = sum(1 for r in rows if r["presenceState"] not in ("unknown", "inRangeUnconfirmed") and not r.get("latestRecord"))
    gaps = C()
    for r in rows:
        if r["presenceState"] == "unknown": continue
        for g in str(r.get("dataGaps") or "").split(";"):
            g = g.strip()
            if g: gaps[g] += 1
    out["dataGapPhrases"] = dict(gaps.most_common(12))
    pil = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]
    out["pilot"] = {p: dict(C(r["presenceState"] for r in per.get(p, []) if r["presenceState"] != "unknown")) for p in pil}
    json.dump(out, open(OUT + "/audit_presence_aggregates.json", "w"), indent=1, default=dict)
    print(json.dumps(out, indent=1, default=dict)[:6000])

# ----------------------------------------------------------------------------- NAS
def cmd_nas(a):
    gz = OUT + "/nas/nas_occurrences_target_species.json.gz"
    if os.path.exists(gz) and not getattr(a, "refresh", False):
        slim = json.load(gzip.open(gz, "rt"))                      # reuse the download; --refresh re-pulls from the API
        print("NAS: reusing", gz)
    else:
        allrec = {}
        for sp, (sci, ids) in SPECIES.items():
            recs = []
            for sid in ids:
                off = 0
                while True:
                    r = get("https://nas.er.usgs.gov/api/v2/occurrence/search", {"species_ID": sid, "limit": 5000, "offset": off}, timeout=180)
                    if r is None or r.status_code != 200:
                        print("NAS fail", sp, sid, getattr(r, "status_code", None)); break
                    j = r.json(); recs += j["results"]; off += j["count"]
                    if str(j["endOfRecords"]).lower() == "true" or j["count"] == 0: break
                    time.sleep(1.0)
                time.sleep(1.0)
            allrec[sp] = recs; print("NAS", sp, len(recs), flush=True)
        keep = ["key", "state", "county", "locality", "decimalLatitude", "decimalLongitude", "huc8", "year", "status", "recordType", "latLongAccuracy", "freshMarineIntro"]
        slim = {sp: [{k: r.get(k) for k in keep} for r in rs] for sp, rs in allrec.items()}
        with gzip.open(gz, "wt") as f:
            json.dump(slim, f)
    # match to lakes (polygon buffered 500 m / point 1 km)
    geoms, kinds = lake_geoms(buffer_m=500)
    ids = list(geoms); tree = STRtree([geoms[i] for i in ids])
    match = collections.defaultdict(lambda: collections.defaultdict(list))
    for sp, rs in slim.items():
        for r in rs:
            lat, lon = r["decimalLatitude"], r["decimalLongitude"]
            if lat is None or lon is None: continue
            for ix in tree.query(Point(lon, lat), predicate="intersects"):
                match[ids[ix]][sp].append({"year": r["year"], "status": r["status"], "recordType": r["recordType"], "acc": r["latLongAccuracy"]})
    json.dump(match, open(OUT + "/nas/nas_lake_matches.json", "w"))
    print("lakes with >=1 NAS record in/at polygon:", len(match))

# ----------------------------------------------------------------------------- GBIF
GBIF_KEYS = {"common_carp": 4286975, "grass_carp": 2362030, "bighead_carp": 2362486, "silver_carp": 2362473, "black_carp": 2362110,
             "smallmouth_buffalo": 2359075, "bigmouth_buffalo": 2359081, "black_buffalo": 2359079, "alligator_gar": 2346754,
             "longnose_gar": 2346701, "shortnose_gar": 2346740, "spotted_gar": 2346692, "bowfin": 5207891, "freshwater_drum": 2400265}
GBIF_REV = {v: k for k, v in GBIF_KEYS.items()}

def cmd_gbif(a):
    """One bbox query per lake (bbox of polygon buffered ~500 m), all 14 taxa, paged; slim records saved; PIP done in `coverage`."""
    path = OUT + "/gbif/gbif_lake_bbox_records.jsonl.gz"
    done = set()
    if os.path.exists(OUT + "/gbif/progress.json"):
        done = set(json.load(open(OUT + "/gbif/progress.json")))
    geoms, kinds = lake_geoms(buffer_m=500)
    mode = "at" if done else "wt"
    with gzip.open(path, mode) as f:
        for n, (lid, g) in enumerate(geoms.items()):
            if lid in done: continue
            x0, y0, x1, y1 = g.bounds
            total = 0; off = 0; nrec = 0
            while True:
                params = [("taxonKey", k) for k in GBIF_KEYS.values()] + [("hasCoordinate", "true"), ("hasGeospatialIssue", "false"),
                          ("decimalLatitude", f"{y0:.5f},{y1:.5f}"), ("decimalLongitude", f"{x0:.5f},{x1:.5f}"), ("limit", 300), ("offset", off)]
                r = get("https://api.gbif.org/v1/occurrence/search", params, timeout=120)
                if r is None or r.status_code != 200:
                    print("GBIF fail", lid, getattr(r, "status_code", None), flush=True); break
                j = r.json(); total = j["count"]
                for o in j["results"]:
                    f.write(json.dumps({"lake": lid, "sp": GBIF_REV.get(o.get("speciesKey")), "lat": o.get("decimalLatitude"), "lon": o.get("decimalLongitude"),
                        "date": o.get("eventDate"), "year": o.get("year"), "basis": o.get("basisOfRecord"), "ds": o.get("datasetKey"),
                        "inst": o.get("institutionCode"), "unc": o.get("coordinateUncertaintyInMeters"), "occ": o.get("occurrenceStatus"),
                        "est": o.get("establishmentMeans"), "id": o.get("key")}) + "\n")
                    nrec += 1
                off += 300
                if j.get("endOfRecords") or off >= min(total, 6000): break
                time.sleep(0.25)
            done.add(lid)
            if n % 25 == 0:
                json.dump(sorted(done), open(OUT + "/gbif/progress.json", "w")); f.flush(); print("GBIF", n, lid, total, nrec, flush=True)
            time.sleep(0.25)
    json.dump(sorted(done), open(OUT + "/gbif/progress.json", "w"))
    print("GBIF done", len(done))

# ----------------------------------------------------------------------------- WBD
def cmd_wbd(a):
    """lake -> HUC8 (USGS WBD ArcGIS REST; representative point of polygon, else directory lat/lon)."""
    polys = polygons(); res = {}
    for n, l in enumerate(lakes()):
        g = polys.get(l["id"]); pt = g.representative_point() if g is not None else Point(l["lon"], l["lat"])
        r = get("https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4/query",
                {"geometry": f"{pt.x},{pt.y}", "geometryType": "esriGeometryPoint", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                 "outFields": "huc8,name", "returnGeometry": "false", "f": "json"})
        try:
            f = r.json()["features"]; res[l["id"]] = {"huc8": f[0]["attributes"]["huc8"], "name": f[0]["attributes"]["name"]} if f else None
        except Exception:
            res[l["id"]] = None
        time.sleep(0.15)
    json.dump(res, open(OUT + "/wbd/lake_huc8.json", "w"))
    print("WBD resolved", sum(1 for v in res.values() if v), "of", len(res))

# ----------------------------------------------------------------------------- WQP (EPA/USGS Water Quality Portal biological data)
def cmd_wqp(a):
    """Lake/reservoir sites with fish-taxon biological results (NLA, state programs) -> stations matched to lake polygons."""
    import csv, io
    geoms, kinds = lake_geoms(buffer_m=500); ids = list(geoms); tree = STRtree([geoms[i] for i in ids])
    out = {}; sites_total = {}
    for sp, (sci, _) in SPECIES.items():
        p = {"siteType": "Lake, Reservoir, Impoundment", "subjectTaxonomicName": sci, "mimeType": "csv", "zip": "no", "dataProfile": "resultPhysChem"}
        h = requests.head("https://www.waterqualitydata.us/data/Result/search", params={**p, "dataProfile": "biological"}, headers=UA, timeout=120)
        sites_total[sp] = int(h.headers.get("Total-Site-Count", 0)); time.sleep(1)
        r = get("https://www.waterqualitydata.us/data/Station/search", {"siteType": "Lake, Reservoir, Impoundment", "subjectTaxonomicName": sci, "mimeType": "csv", "zip": "no"}, timeout=300)
        hit = set(); n = 0
        if r is not None and r.status_code == 200:
            for row in csv.DictReader(io.StringIO(r.text)):
                try: lat = float(row["LatitudeMeasure"]); lon = float(row["LongitudeMeasure"])
                except Exception: continue
                n += 1
                for ix in tree.query(Point(lon, lat), predicate="intersects"): hit.add(ids[ix])
        out[sp] = {"wqpLakeSites": sites_total[sp], "stationsParsed": n, "lakesMatched": sorted(hit)}
        print("WQP", sp, sites_total[sp], n, len(hit), flush=True); time.sleep(1.5)
    json.dump(out, open(OUT + "/other/wqp_lake_matches.json", "w"))

# ----------------------------------------------------------------------------- MidFish (USGS data release, 7 Upper Midwest states)
MIDFISH_SPECIES = {"common_carp": ["common_carp", "mirror_carp"], "grass_carp": ["grass_carp"], "bighead_carp": ["bighead_carp"],
    "silver_carp": ["silver_carp"], "bigmouth_buffalo": ["bigmouth_buffalo"], "black_buffalo": ["black_buffalo"], "smallmouth_buffalo": ["smallmouth_buffalo"],
    "longnose_gar": ["longnose_gar"], "shortnose_gar": ["shortnose_gar"], "spotted_gar": ["spotted_gar"], "bowfin": ["bowfin", "bowfin_dogfish"],
    "freshwater_drum": ["freshwater_drum"], "alligator_gar": ["alligator_gar"], "black_carp": ["black_carp"]}

def cmd_midfish(a):
    import pandas as pd, glob
    base = OUT + "/other/midfish/hive"
    rev = {v: k for k, vs in MIDFISH_SPECIES.items() for v in vs}
    frames = []
    for f in glob.glob(base + "/state=*/*.parquet"):
        df = pd.read_parquet(f, columns=["state", "lake_name", "lake_id", "latitude_lake_centroid", "longitude_lake_centroid", "year", "species_1"])
        df = df[df["species_1"].isin(rev)]
        df["sp"] = df["species_1"].map(rev)
        frames.append(df.groupby(["state", "lake_id", "lake_name", "latitude_lake_centroid", "longitude_lake_centroid", "sp"]).agg(n=("year", "size"), y0=("year", "min"), y1=("year", "max")).reset_index())
        print("MidFish", f.split("/")[-1], len(frames[-1]), flush=True)
    allr = pd.concat(frames)
    allr.to_csv(OUT + "/other/midfish_target_species_by_lake.csv", index=False)
    # also the set of ALL surveyed lakes (for 'surveyed but species not caught' evidence) -- need lake list regardless of species
    lk = []
    for f in glob.glob(base + "/state=*/*.parquet"):
        d = pd.read_parquet(f, columns=["state", "lake_id", "lake_name", "latitude_lake_centroid", "longitude_lake_centroid", "year"])
        lk.append(d.groupby(["state", "lake_id", "lake_name", "latitude_lake_centroid", "longitude_lake_centroid"]).agg(y0=("year", "min"), y1=("year", "max")).reset_index())
    lk = pd.concat(lk); lk.to_csv(OUT + "/other/midfish_surveyed_lakes.csv", index=False)
    geoms, kinds = lake_geoms(buffer_m=1500)
    ids = list(geoms); tree = STRtree([geoms[i] for i in ids])
    sp_by = collections.defaultdict(dict)
    for r in allr.itertuples():
        sp_by[(r.state, r.lake_id)][r.sp] = {"n": int(r.n), "y1": 0 if pd.isna(r.y1) else int(r.y1)}
    out = {}
    for r in lk.itertuples():
        if pd.isna(r.latitude_lake_centroid): continue
        for ix in tree.query(Point(r.longitude_lake_centroid, r.latitude_lake_centroid), predicate="intersects"):
            e = out.setdefault(ids[ix], {"surveyedLakeMatches": [], "species": {}})
            e["surveyedLakeMatches"].append({"name": r.lake_name, "y0": None if pd.isna(r.y0) else int(r.y0), "y1": None if pd.isna(r.y1) else int(r.y1)})
            for sp, v in sp_by.get((r.state, r.lake_id), {}).items():
                c = e["species"].setdefault(sp, {"n": 0, "y1": 0}); c["n"] += v["n"]; c["y1"] = max(c["y1"], v["y1"])
    json.dump(out, open(OUT + "/other/midfish_lake_matches.json", "w"))
    print("MidFish: directory lakes matched to a surveyed lake:", len(out))

# ----------------------------------------------------------------------------- coverage (independent observed evidence per lake x species)
# GBIF datasetKey -> evidence family (so NAS/MARIS republished through GBIF are not double counted as independent)
GBIF_DS = {"d6cc311c-c5ab-4f23-9a20-10514f9eb9c4": "NAS", "e0ae862b-d456-4cb2-900b-c4928b75a1f8": "MARIS", "50c9509d-22c7-4a22-a47d-8c48425ef4a7": "INAT",
           "f46c93f2-123d-4dc3-a06e-b2faecfda2ce": "TPWD_SABINE", "29b43457-5ebc-465c-b275-21a03cb9f148": "TPWD_SABINE",
           "ba5b0f3a-73dd-459f-a7f1-9abc327aed00": "MUSEUM", "71e6db8e-f762-11e1-a439-00145eb45e9a": "MUSEUM", "59825263-9f89-43a9-8f22-c22a6a53b8fc": "MUSEUM"}
NAS_POS = {"established", "stocked", "collected", "unknown", ""}      # 'failed'/'extirpated' kept apart
def lake_evidence():
    """lake -> species -> {source: {n, last}} from independent PUBLIC sources (point-in-polygon, polygon +500 m; MidFish 1.5 km centroid)."""
    ev = collections.defaultdict(lambda: collections.defaultdict(dict))
    nas = json.load(open(OUT + "/nas/nas_lake_matches.json"))
    for lid, d in nas.items():
        for sp, rs in d.items():
            pos = [r for r in rs if (r["status"] or "") in NAS_POS and r.get("acc") != "Centroid"]
            neg = [r for r in rs if (r["status"] or "") in ("failed", "extirpated")]
            if pos: ev[lid][sp]["NAS"] = {"n": len(pos), "last": max([r["year"] or 0 for r in pos])}
            if neg: ev[lid][sp]["NAS_failed"] = {"n": len(neg), "last": max([r["year"] or 0 for r in neg])}
    geoms, kinds = lake_geoms(buffer_m=500)
    with gzip.open(OUT + "/gbif/gbif_lake_bbox_records.jsonl.gz", "rt") as f:
        for line in f:
            r = json.loads(line)
            if not r["sp"] or r["lat"] is None or r["occ"] == "ABSENT": continue
            g = geoms[r["lake"]]
            if not g.intersects(Point(r["lon"], r["lat"])): continue
            unc = r["unc"]
            if unc is not None and unc > 1000: continue
            key = GBIF_DS.get(r["ds"]) or ("MUSEUM" if r["basis"] == "PRESERVED_SPECIMEN" else "GBIF_OTHER")
            c = ev[r["lake"]][r["sp"]].setdefault(key, {"n": 0, "last": 0}); c["n"] += 1; c["last"] = max(c["last"], r["year"] or 0)
    wq = json.load(open(OUT + "/other/wqp_lake_matches.json"))
    for sp, d in wq.items():
        for lid in d["lakesMatched"]: ev[lid][sp]["WQP"] = {"n": 1, "last": None}
    mf = json.load(open(OUT + "/other/midfish_lake_matches.json"))
    for lid, d in mf.items():
        for sp, v in d["species"].items(): ev[lid][sp]["MIDFISH"] = {"n": v["n"], "last": v["y1"] or None}
    return ev, kinds

def hu8_priors():
    """lake -> set(species) with a NAS record anywhere in the lake's HUC8, or in USGS coarse-range HUC8 table."""
    import csv
    huc = {k: (v or {}).get("huc8") for k, v in json.load(open(OUT + "/wbd/lake_huc8.json")).items()}
    nas = json.load(gzip.open(OUT + "/nas/nas_occurrences_target_species.json.gz", "rt"))
    by_huc = collections.defaultdict(set)
    for sp, rs in nas.items():
        for r in rs:
            if r["huc8"] and (r["status"] or "") in NAS_POS: by_huc[r["huc8"]].add(sp)
    coarse = collections.defaultdict(set)
    name2sp = {v[0]: k for k, v in SPECIES.items()}
    for r in csv.DictReader(open(OUT + "/other/coarse_range/agap_coarse_fish_ranges_v2_0.csv")):
        sp = name2sp.get(r["scientific_name"])
        if sp: coarse[str(r["huc8"]).zfill(8)].add(sp)
    return huc, by_huc, coarse

def cmd_coverage(a):
    ev, kinds = lake_evidence(); huc, by_huc, coarse = hu8_priors()
    allids = [l["id"] for l in lakes()]; n = len(allids)
    res = {"lakes": n, "polygonLakes": sum(1 for k in kinds.values() if k == "polygon")}
    def has(lid, sp, pred=lambda src, v: True): return any(pred(s, v) for s, v in ev[lid].get(sp, {}).items() if s != "NAS_failed")
    for label, sps in (("12species", ASSESSED12), ("bowfinDrum", ["bowfin", "freshwater_drum"]), ("all14", list(SPECIES)),
                       ("carp5", ["common_carp", "grass_carp", "bighead_carp", "silver_carp", "black_carp"]), ("buffalo3", ["smallmouth_buffalo", "bigmouth_buffalo", "black_buffalo"]),
                       ("gar4", ["alligator_gar", "longnose_gar", "shortnose_gar", "spotted_gar"])):
        e1 = sum(1 for l in allids if any(has(l, s) for s in sps))
        e1recent = sum(1 for l in allids if any(has(l, s, lambda src, v: (v.get("last") or 0) >= 2010) for s in sps))
        e2 = sum(1 for l in allids if not any(has(l, s) for s in sps) and any(s in by_huc.get(huc.get(l), set()) | coarse.get(huc.get(l), set()) for s in sps))
        res[f"lakesWithInWaterbodyRecord_{label}"] = e1
        res[f"lakesWithInWaterbodyRecord2010plus_{label}"] = e1recent
        res[f"lakesHucOnly_{label}"] = e2
        res[f"lakesNoEvidence_{label}"] = n - e1 - e2
    res["bySpecies"] = {}
    for sp in SPECIES:
        e1 = sum(1 for l in allids if has(l, sp))
        e2 = sum(1 for l in allids if not has(l, sp) and sp in by_huc.get(huc.get(l), set()) | coarse.get(huc.get(l), set()))
        srcs = collections.Counter(s for l in allids for s in ev[l].get(sp, {}))
        res["bySpecies"][sp] = {"inWaterbody": e1, "hucOnly": e2, "sources": dict(srcs)}
    srcs = collections.Counter(); first = collections.Counter()
    for l in allids:
        seen = set()
        for sp in SPECIES:
            for s in ev[l].get(sp, {}):
                if s != "NAS_failed": seen.add(s)
        for s in seen: srcs[s] += 1
    res["lakesPerSource_anyTargetSpecies"] = dict(srcs)
    # source-combination: lakes by number of distinct independent sources (12 species + bowfin/drum)
    k = collections.Counter(min(3, len({s.split("_")[0] for sp in SPECIES for s in ev[l].get(sp, {}) if s != "NAS_failed"})) for l in allids)
    res["lakesByDistinctSourceFamilies_0_1_2_3plus"] = {str(x): k.get(x, 0) for x in range(4)}
    json.dump(res, open(OUT + "/coverage_summary.json", "w"), indent=1)
    json.dump({l: {sp: v for sp, v in d.items()} for l, d in ev.items()}, open(OUT + "/lake_species_evidence.json", "w"))
    print(json.dumps(res, indent=1))

# ----------------------------------------------------------------------------- validate (aggregate-only comparison with the private presence release)
PILOTS = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]
OBS = {"established", "reported", "stocked"}

def cmd_validate(a):
    """Private presence is read into memory only; nothing per-row is written. Output: counts/rates by species, tier, state; pilot lakes as per-lake counts."""
    _, d = presence_rows_in_memory()
    priv = {(r["lakeId"], r["speciesId"]): r for r in d["rows"]}
    ev = json.load(open(OUT + "/lake_species_evidence.json"))
    def indep(lid, sp):
        e = {k: v for k, v in ev.get(lid, {}).get(sp, {}).items() if k != "NAS_failed"}
        if not e: return None
        yrs = [v["last"] for v in e.values() if v.get("last")]
        return {"sources": sorted(e), "last": max(yrs) if yrs else None}
    C = collections.Counter
    tot = {"pairs12": 0, "indepPos": 0}
    st_given_indep = C(); indep_given_st = collections.defaultdict(C); by_sp = collections.defaultdict(lambda: C())
    hist_recent = C(); stale = C(); tier_corr = collections.defaultdict(C); unknown_upgrade = C()
    for (lid, sp), r in priv.items():
        i = indep(lid, sp); stt = r["presenceState"]; tot["pairs12"] += 1
        indep_given_st[stt]["total"] += 1
        if i:
            tot["indepPos"] += 1; st_given_indep[stt] += 1; indep_given_st[stt]["indep"] += 1; by_sp[sp][stt] += 1
            if stt == "unknown": unknown_upgrade[sp] += 1
            if stt == "historical" and i["last"] and i["last"] >= 2015: hist_recent["historical_but_independent_record_2015plus"] += 1
            if stt == "historical": hist_recent["historical_total_with_indep"] += 1
            try:
                if stt in OBS | {"historical"} and i["last"] and r.get("latestRecord") and i["last"] > int(r["latestRecord"]): stale["indep_newer_than_private_latestRecord"] += 1
            except ValueError: pass
        if stt in OBS: tier_corr[str(r["sourceTier"])]["n"] += 1; tier_corr[str(r["sourceTier"])]["corroborated"] += 1 if i else 0
    out = {"release": d["researchVersion"], "totals": tot, "privateStateGivenIndependentRecord": dict(st_given_indep),
           "independentRecordGivenPrivateState": {k: dict(v) for k, v in indep_given_st.items()},
           "unknownButIndependentRecordBySpecies": dict(unknown_upgrade),
           "historicalFlags": dict(hist_recent), "staleness": dict(stale), "observedStatesCorroboratedByTier": {k: dict(v) for k, v in tier_corr.items()}}
    # per-species recall/corroboration
    rec = {}
    for sp in ASSESSED12:
        pos = by_sp[sp]; n = sum(pos.values())
        if not n: continue
        covered = sum(v for k, v in pos.items() if k in OBS | {"historical", "failed/eradicated"})
        rec[sp] = {"independentPositivePairs": n, "privateHadEvidenceState": covered, "privateInRangeOnly": pos.get("inRangeUnconfirmed", 0),
                   "privateUnknown": pos.get("unknown", 0), "recallOfIndependent": round(covered / n, 3)}
        po = [(l, s2) for (l, s2), r in priv.items() if s2 == sp and r["presenceState"] in OBS]
        rec[sp]["privateObservedPairs"] = len(po); rec[sp]["corroboratedByIndependent"] = sum(1 for l, s2 in po if indep(l, s2))
    out["perSpecies"] = rec
    huc, by_huc, coarse = hu8_priors()
    xt = collections.defaultdict(C); recent = C()
    for (lid, sp), r in priv.items():
        i = indep(lid, sp)
        if i: tier = "E3_inWaterbodyRecord" + ("_2015plus" if (i["last"] or 0) >= 2015 else "_older_or_undated")
        elif sp in by_huc.get(huc.get(lid), set()) | coarse.get(huc.get(lid), set()): tier = "E4_hucOccurrence"
        else: tier = "none"
        xt[r["presenceState"]][tier] += 1
        if i and (i["last"] or 0) >= 2015: recent[sp] += 1
    out["currentStateByProposedPublicTier"] = {k: dict(v) for k, v in xt.items()}
    out["pairsWithIndependentRecord2015plusBySpecies"] = dict(recent)
    out["pilot"] = {}
    for pl in PILOTS:
        c = C()
        for sp in ASSESSED12:
            r = priv.get((pl, sp)); i = indep(pl, sp)
            if i: c["speciesWithIndependentRecord"] += 1; c["indep_priv_" + r["presenceState"]] += 1
            if r["presenceState"] in OBS and not i: c["privateObservedNoIndependent"] += 1
        out["pilot"][pl] = dict(c)
    # bowfin / drum: not assessed by private presence at all
    out["notAssessedButIndependentRecord"] = {sp: sum(1 for l in ev if sp in ev[l] and any(k != "NAS_failed" for k in ev[l][sp])) for sp in ("bowfin", "freshwater_drum")}
    json.dump(out, open(OUT + "/validation_aggregates.json", "w"), indent=1)
    print(json.dumps(out, indent=1))

# ----------------------------------------------------------------------------- state-agency probes (MN LakeFinder, IN Data Hub)
BOW = {"common carp": "common_carp", "grass carp": "grass_carp", "bighead carp": "bighead_carp", "silver carp": "silver_carp", "black carp": "black_carp",
       "smallmouth buffalo": "smallmouth_buffalo", "bigmouth buffalo": "bigmouth_buffalo", "black buffalo": "black_buffalo", "alligator gar": "alligator_gar",
       "longnose gar": "longnose_gar", "shortnose gar": "shortnose_gar", "spotted gar": "spotted_gar", "bowfin": "bowfin", "bowfin (dogfish)": "bowfin",
       "freshwater drum": "freshwater_drum", "emerald bowfin": "bowfin"}

def cmd_states(a):
    res = {"MN": {"lakesInDirectory": 0, "lakesResolved": 0, "lakesWithSpeciesList": 0, "speciesLakes": {}}, "IN": {}}
    mn = [l for l in lakes() if l["state"] == "MN"]; res["MN"]["lakesInDirectory"] = len(mn)
    def norm(x): return "".join(c for c in x.lower().replace(" lake", "").replace("lake ", "") if c.isalnum())
    for l in mn:
        r = get("https://services.dnr.state.mn.us/api/lakefinder/by_point/v1/", {"lat": l["lat"], "lon": l["lon"]})
        time.sleep(1.0)
        try: cand = r.json()["results"] or []
        except Exception: continue
        pick = [c for c in cand if norm(c["name"]) and (norm(c["name"]) in norm(l["name"]) or norm(l["name"]) in norm(c["name"]))]
        if not pick: continue
        pick = max(pick, key=lambda c: c["morphology"].get("area") or 0)
        res["MN"]["lakesResolved"] += 1
        sp = [x.strip() for x in (pick.get("fishSpecies") or [""])[0].split(",") if x.strip()]
        if sp: res["MN"]["lakesWithSpeciesList"] += 1
        for x in sp:
            if x in BOW: res["MN"]["speciesLakes"].setdefault(BOW[x], []).append(l["id"])
        if sp: res["MN"].setdefault("_listLakes", []).append(l["id"])
    res["MN"]["speciesLakeCounts"] = {k: len(v) for k, v in res["MN"]["speciesLakes"].items()}
    # agency species list (gold for presence in that lake) vs private presence for common carp -- aggregate counts only
    _, d = presence_rows_in_memory(); priv = {(r["lakeId"], r["speciesId"]): r["presenceState"] for r in d["rows"]}
    cmp_ = collections.Counter()
    for lid in res["MN"].pop("_listLakes", []):
        agency = lid in res["MN"]["speciesLakes"].get("common_carp", [])
        cmp_[f"agency_{'present' if agency else 'not_listed'}|private_{priv[(lid, 'common_carp')]}"] += 1
    res["MN"]["commonCarpAgencyVsPrivate"] = dict(cmp_); del res["MN"]["speciesLakes"]
    # Indiana Data Hub (CKAN): Fish_Surveys + Batch_Fish_Records (downloaded by the state sub-survey into other/states/IN)
    import csv
    base = OUT + "/other/states/IN/"
    if os.path.exists(base + "fish_surveys_full.csv"):
        surv = {r["Id"]: r for r in csv.DictReader(open(base + "fish_surveys_full.csv"))}
        inl = [l for l in lakes() if l["state"] == "IN"]
        wbs = collections.defaultdict(set)
        for r in csv.DictReader(open(base + "batch_fish_records_full.csv")):
            sv = surv.get(r["FishSurveyId"])
            if sv: wbs[norm(sv["WaterbodyName"])].add(BOW.get((r["SpeciesName"] or "").lower().strip(), None))
        matched = {l["id"]: wbs[k] - {None} for l in inl for k in [norm(l["name"])] if k in wbs}
        res["IN"] = {"lakesInDirectory": len(inl), "lakesWithBatchSpeciesRows": len(matched), "lakesWithBowfishTarget": sum(1 for v in matched.values() if v),
                     "surveysTotal": len(surv), "waterbodiesWithSurveys": len({s["WaterbodyId"] for s in surv.values()})}
    json.dump(res, open(OUT + "/state_probe_results.json", "w"), indent=1); print(json.dumps(res, indent=1))

# ----------------------------------------------------------------------------- summary (the only artifact committed to Git)
BOWSTATES = "TX OK AR AL TN KY MO IL IN IA WI MN MS LA GA SC NC".split()
STATE_VERDICTS = {  # live-tested 2026-10-13 (see LAKE_BRAIN_SPECIES_PRESENCE_RESEARCH.md section 5)
    "MN": ("ACCEPTED", "LakeFinder by_id/by_point JSON per-lake fishSpecies (undocumented public API); DOW list via env_lakes_surveyed_by_mndnr (4,383 polygons)"),
    "IN": ("ACCEPTED", "Indiana Data Hub CKAN CSVs: Fish_Surveys + Batch_Fish_Records (373 waterbodies, 48 with species rows) + Fish_Records (aged fish only); license blank"),
    "TX": ("LEAD", "stocking HTML per waterbody (grass/bighead/common carp tracked); alligator gar harvest FeatureServer by waterbody; survey PDFs"),
    "IL": ("LEAD", "iFish Illinois lake pages (469, sitemap, robots allows) narrative HTML; no data feed"),
    "WI": ("LEAD", "no species layer; MARIS (via GBIF) is the only bulk lake fish source; gamefish-only lake pages"),
    "OK": ("LEAD", "ODWC lake record-fish layer (sparse); survey PDFs"),
    "KY": ("LEAD", "annual survey PDFs only; lake layer has no species"),
    "MO": ("LEAD", "HTML fishing-prospects narratives; polygons only"),
    "IA": ("DEAD_END", "Power BI dashboard only"), "MS": ("DEAD_END", "geometry only"), "LA": ("DEAD_END", "gamefish narrative only"),
    "GA": ("DEAD_END", "geometry/gamefish only"), "SC": ("DEAD_END", "geometry only"), "NC": ("DEAD_END", "geometry only"),
    "AR": ("DEAD_END", "geometry only"), "AL": ("DEAD_END", "ArcGIS host dead; PDFs"), "TN": ("DEAD_END", "stocking PDFs moved/404"),
}

def cmd_summary(a):
    cov = json.load(open(OUT + "/coverage_summary.json")); val = json.load(open(OUT + "/validation_aggregates.json"))
    aud = json.load(open(OUT + "/audit_presence_aggregates.json")); st = json.load(open(OUT + "/state_probe_results.json"))
    ev = json.load(open(OUT + "/lake_species_evidence.json")); L = lakes()
    per_state = {}
    for l in L:
        k = l["state"]; e = per_state.setdefault(k, {"lakes": 0, "inWaterbody12": 0})
        e["lakes"] += 1
        if any(sp in ev.get(l["id"], {}) and any(x != "NAS_failed" for x in ev[l["id"]][sp]) for sp in ASSESSED12): e["inWaterbody12"] += 1
    bow = {k: per_state[k] for k in BOWSTATES if k in per_state}
    nb = sum(v["lakes"] for v in bow.values()); ib = sum(v["inWaterbody12"] for v in bow.values())
    nas = json.load(gzip.open(OUT + "/nas/nas_occurrences_target_species.json.gz", "rt"))
    out = {"generated": time.strftime("%Y-%m-%d"), "thread": "species", "disclaimer": "aggregates and method only; no presence rows",
           "privatePresenceRelease": {k: aud[k] for k in ("release", "rows", "lakes", "byState", "byConfidence", "byTier", "byNative", "lakesWithObsGrade", "lakesAllUnknown",
                                      "lakesWithAnyNonUnknown", "lakesWithEstablished", "lakesWithOnlyRange", "latestRecordYear", "dataGapPhrases", "speciesByState", "pilot")},
           "apiTests": {"NAS_recordsDownloaded": {k: len(v) for k, v in nas.items()},
                        "GBIF_US_hasCoordinate_counts": {"common_carp": 109058, "grass_carp": 7151, "bighead_carp": 3197, "silver_carp": 11296, "black_carp": 302,
                            "smallmouth_buffalo": 14479, "bigmouth_buffalo": 3789, "black_buffalo": 714, "alligator_gar": 46706, "longnose_gar": 19022,
                            "shortnose_gar": 1887, "spotted_gar": 83710, "bowfin": 12430, "freshwater_drum": 16643},
                        "GBIF_records_in_lake_bbox_after_filters_note": "26,120 bbox records over 621 lakes (cap 6,000/lake not hit); datasets: iNaturalist RG, USGS NAS, MARIS fish, FoTX, UMMZ and other museums",
                        "WQP_lakeSites": {k: v for k, v in {"common_carp": 824, "smallmouth_buffalo": 99, "bigmouth_buffalo": 30, "freshwater_drum": 75, "bowfin": 30, "spotted_gar": 5, "longnose_gar": 4, "grass_carp": 5, "silver_carp": 2}.items()},
                        "USGS_coarse_range_HUC8": "257 species; covers buffalo x3, grass/bighead/silver carp only (no common/black carp, gars, bowfin, drum)",
                        "MidFish": "7 states (IA IL IN MI MN SD WI); full species only IA IN MN SD WI; IL and MI hold 8 gamefish only; 74 directory lakes coordinate-matched to a surveyed lake"},
           "coverage": cov, "validation": val, "stateProbes": st,
           "perStateInWaterbodyRecord12": per_state,
           "bowfishingStates17": {"lakes": nb, "withInWaterbodyRecord12": ib, "share": round(ib / nb, 3)},
           "stateVerdicts": {k: {"verdict": v[0], "note": v[1]} for k, v in STATE_VERDICTS.items()}}
    dst = os.path.join(REPO, "docs/research/lake-brain/data/presence_sources_summary.json")
    json.dump(out, open(dst, "w"), indent=1, default=dict); print("wrote", dst, os.path.getsize(dst), "bytes")
    print("17-state share:", nb, ib)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--data"); ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.data: OUT = a.data
    globals()["cmd_" + a.cmd](a)
