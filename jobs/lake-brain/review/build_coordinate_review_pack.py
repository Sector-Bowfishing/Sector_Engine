#!/usr/bin/env python3
"""Build the Lake Brain COORDINATE / IDENTITY review pack for the held coordinate-flag lakes.

Population: every lake whose directory pin is flagged identity_risk / off_water by the geometry audit
(<data>/geometry/lake_geometry_flags.csv, point_flag column) plus any lake the live Lake Registry flags off-water / identity-risk.
For each lake the pack shows the pin, the canonical polygon (live public registry), point-in-polygon, other nearby waters, operator / NID
evidence, a proposed corrected coordinate (always a point verified INSIDE the canonical water), what a correction would do to the
candidate binding, and a PASS / FLAG recommendation (rules: coord_evidence.py docstring and
docs/brains/LAKE_BRAIN_COORDINATE_REVIEW_PROTOCOL.md). Identity ambiguity is always FLAG; nothing here decides identity.

Outputs (to --out; the pack stays out of Git):
    coordinate_review.html          the single-file review form (double-click)
    coordinate_review_pack.csv      the same rows as a spreadsheet (every evidence column)
    pack_manifest.json              ids, proposed coordinates, row digests, input fingerprints (used by ingest_coordinate_review.py)
    START HERE - README.md          plain-language instructions for the reviewer

Read-only: the registry bucket and the NHD service are only read (cached under --cache-dir; pass --fetch to allow requests, otherwise
only the cache is used). Nothing is written to any database, bucket, directory or binding.
"""
import argparse
import concurrent.futures
import csv
import datetime as dt
import glob
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coord_evidence as E  # noqa: E402
import coord_fetch as F  # noqa: E402
import coord_geo as G  # noqa: E402
import held_lakes  # noqa: E402

DEFAULT_DATA = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain"
DEFAULT_OUT = "/Users/mcather/Desktop/Sector Handoffs/Sector Engine/Lake Brain Coordinate Review"
HELD_FLAGS = ("identity_risk", "off_water")
REGISTRY_FLAGS = ("off-water", "identity-risk")
SCHEMA = "lake-brain-coordinate-review-pack/v1"
DECISIONS = ("ACCEPT_PROPOSED", "KEEP_CURRENT", "NEEDS_INFO")
MAX_NID_NEAR_M = 4000.0


# ------------------------------------------------------------------------------------------------------------ inputs
def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def population(research_rows, registry_lakes):
    """-> {lake_id: source tag}. research flag first; registry-only flags added with their own tag."""
    pop = {}
    for r in research_rows:
        if (r.get("point_flag") or "").strip() in HELD_FLAGS and r["id"] in registry_lakes:
            pop[r["id"]] = "research:" + r["point_flag"].strip()
    for lid, l in registry_lakes.items():
        if lid not in pop and l.get("pointFlag") in REGISTRY_FLAGS:
            pop[lid] = "registry:" + l["pointFlag"]
    return pop


def load_station_coords(data_dir):
    """(lakeId, provider, station) -> (lat, lon) from the research candidate files (binding wave 1 csv, wave 2 jsonl)."""
    out = {}
    p = os.path.join(data_dir, "binding", "candidates_all.csv")
    if os.path.exists(p):
        for r in read_csv(p):
            try:
                out[(r["lakeId"], r["prov"], r["station"])] = (float(r["lat"]), float(r["lon"]))
            except (ValueError, KeyError):
                pass
    for fn in sorted(glob.glob(os.path.join(data_dir, "binding2", "cand", "*.jsonl"))):
        for line in open(fn):
            try:
                c = json.loads(line)
                if c.get("lat") is not None and c.get("lon") is not None:
                    out.setdefault((c["lakeId"], c.get("prov"), str(c.get("station"))), (float(c["lat"]), float(c["lon"])))
            except (ValueError, KeyError):
                continue
    return out


def load_bindings(data_dir, held_ids):
    """lake_id -> [binding dict]. Source: binding2/verified_v2_full.csv (the complete wave-1 + wave-2 candidate table, 621 rows, NONE = no candidate)."""
    p = os.path.join(data_dir, "binding2", "verified_v2_full.csv")
    if not os.path.exists(p):
        return {}
    coords = load_station_coords(data_dir)
    out = {}
    for r in read_csv(p):
        st = (r.get("bindingStatus") or "").strip()
        if st in ("", "NONE"):
            continue
        key = (r["lakeId"], r.get("provider"), r.get("station"))
        c = coords.get(key) or next((v for k, v in coords.items() if k[0] == r["lakeId"] and k[2] == r.get("station")), None)
        try:
            dist = float(r["distM"]) if r.get("distM") else None
        except ValueError:
            dist = None
        out.setdefault(r["lakeId"], []).append(dict(
            provider=r.get("provider"), station=r.get("station"), stationName=r.get("stationName"), status=st, capability=r.get("capability"),
            distM=dist, lat=None if c is None else c[0], lon=None if c is None else c[1], held=(r["lakeId"] in held_ids)))
    return out


def load_nid(data_dir):
    p = os.path.join(data_dir, "context", "nid", "nid_v1_subset.json")
    if not os.path.exists(p):
        return {}, []
    recs = json.load(open(p))
    by_id = {}
    pts = []
    for r in recs:
        if r.get("LATITUDE") is None or r.get("LONGITUDE") is None:
            continue
        d = dict(id=r["NIDID"], name=r.get("NAME"), lat=float(r["LATITUDE"]), lon=float(r["LONGITUDE"]), surfaceKm2=None)
        by_id[r["NIDID"]] = d
        pts.append(d)
    return by_id, pts


def nid_near(pts, lat, lon, lake_name, radius_m=MAX_NID_NEAR_M):
    out = []
    dlat = radius_m / 111000.0 * 1.2
    dlon = dlat / max(0.2, math.cos(math.radians(lat)))
    for d in pts:
        if abs(d["lat"] - lat) > dlat or abs(d["lon"] - lon) > dlon:
            continue
        m = G.haversine_m(lat, lon, d["lat"], d["lon"])
        if m <= radius_m:
            out.append(dict(id=d["id"], name=d["name"], lat=d["lat"], lon=d["lon"], nameMatch=round(G.name_match(lake_name, d["name"]), 2)))
    out.sort(key=lambda n: (-n["nameMatch"], G.haversine_m(lat, lon, n["lat"], n["lon"])))
    return out[:3]


# ------------------------------------------------------------------------------------------------------------ rows
def map_links(lat, lon):
    return dict(osm=f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=14/{lat}/{lon}",
                sat=f"https://www.google.com/maps/@{lat},{lon},15z/data=!3m1!1e3")


def row_digest(lake_id, cur, prop, rec, binding_codes):
    s = "|".join([lake_id, f"{cur['lat']:.5f},{cur['lon']:.5f}", "none" if not prop else f"{prop['lat']:.5f},{prop['lon']:.5f}", rec, ",".join(binding_codes)])
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def registry_neighbours(lid, registry, geoms, radius_m=6000.0):
    """Other Sector directory lakes (not the same water) whose polygon is within radius_m of this lake's pin, shaped like an alternative.
    `geoms` is a callable lakeId -> GeoJSON geometry (cached registry objects)."""
    lake = registry[lid]
    lat, lon = lake["location"]["lat"], lake["location"]["lon"]
    members = set(lake.get("memberIds") or [lid]) | {lid}
    dlat = radius_m / 111000.0 * 1.3
    dlon = dlat / max(0.2, math.cos(math.radians(lat)))
    out = []
    for oid, o in registry.items():
        if oid in members or not o.get("bbox"):
            continue
        w, s, e, n = o["bbox"]
        if not (w - dlon <= lon <= e + dlon and s - dlat <= lat <= n + dlat):
            continue
        polys = G.polygons_of(geoms(oid))
        if not polys:
            continue
        d = G.distance_to_polygons_m(lat, lon, polys)
        if d is None or d > radius_m:
            continue
        out.append(dict(id=oid, name=o.get("name"), gnisId=None, areaKm2=o.get("areaKm2"), distanceM=round(d), nameMatch=round(G.name_match(lake.get("name"), o.get("name")), 2),
                        pinInside=(d == 0.0), center=(o["centroid"][1], o["centroid"][0]) if o.get("centroid") else None, source="Sector registry lake"))
    return out


def build_rows(pop, registry, geoms, research, directory, nhd_of, bindings, nid_by_id, nid_pts, reg_geoms=None):
    rows = []
    for lid in sorted(pop, key=lambda i: (registry[i].get("state") or "", registry[i].get("name") or "", i)):
        lake = registry[lid]
        cur = (lake["location"]["lat"], lake["location"]["lon"])
        link = nid_by_id.get(((lake.get("externalIds") or {}).get("nidId") or ""))
        ctx = dict(lake=lake, geom=geoms.get(lid), research=research.get(lid), directory=directory.get(lid), nhd=nhd_of.get(lid),
                   nid=dict(linked=link, near=nid_near(nid_pts, cur[0], cur[1], lake.get("name"))), bindings=bindings.get(lid, []),
                   registryAlts=registry_neighbours(lid, registry, reg_geoms or (lambda i: geoms.get(i))))
        ev = E.build_evidence(ctx)
        rec, why, _ = E.recommend(ev)
        ev["recommendation"], ev["why"] = rec, why
        ev["sourceFlag"] = pop[lid]
        ev["digest"] = row_digest(lid, ev["current"], ev["proposed"], rec, [b["code"] for b in ev["bindings"]])
        rows.append(ev)
    for i, r in enumerate(rows):
        r["seq"] = i + 1
    return rows


def pack_id_for(rows, snapshot):
    h = hashlib.sha256((snapshot + "|" + ",".join(f"{r['lakeId']}:{r['digest']}" for r in rows)).encode()).hexdigest()[:10]
    return f"LBC-{snapshot}-{h}"


def binding_summary(r):
    if not r["bindings"]:
        return "no candidate binding"
    return "; ".join(f"{b['provider']} {b['station']} [{b['status']}{', HELD' if b['held'] else ''}]: {b['code']}" for b in r["bindings"])


def evidence_text(r):
    parts = []
    if r["nameSources"]:
        parts.append("names: " + "; ".join(f"{n['source']} '{n['name']}' ({n['match']:.2f})" for n in r["nameSources"][:4]))
    if r["areaRatios"]:
        parts.append("area ratios: " + ", ".join(f"{a['source']} {a['ratio']}" for a in r["areaRatios"]))
    if r["nidDam"]:
        d = r["nidDam"]
        parts.append(f"NID dam {d['id']} '{d['name']}' is {d['toWaterM'] if d['toWaterM'] is not None else 'n/a'} m from the water and {d['toPinM']} m from the pin")
    if r["osmSignal"]:
        parts.append("OSM corroborates the polygon")
    return " | ".join(parts) or "no independent evidence found"


CSV_FIELDS = ["seq", "lake_id", "lake_name", "state", "source_flag", "registry_flag", "geometry_class", "current_lat", "current_lon", "in_polygon",
              "distance_to_water_m", "allowed_m", "geometry_confidence", "canonical_area_km2", "canonical_name", "nhd_ids", "gnis_id",
              "nearest_other_water", "nearest_other_water_m", "nearest_other_water_source", "competing_water", "operator", "usace_name", "nid_id",
              "evidence", "positive_signals", "concerns", "proposed_lat", "proposed_lon", "proposed_basis", "proposed_move_m", "also_nearest_water_point",
              "binding_held", "binding_implication", "recommendation", "why", "row_digest"]


def csv_row(r):
    alt = r["alternatives"][0] if r["alternatives"] else None
    prop = r["proposed"]
    return {
        "seq": r["seq"], "lake_id": r["lakeId"], "lake_name": r["name"], "state": r["state"], "source_flag": r["sourceFlag"], "registry_flag": r["registryFlag"] or "",
        "geometry_class": r["geometryClass"], "current_lat": r["current"]["lat"], "current_lon": r["current"]["lon"],
        "in_polygon": {True: "yes", False: "no", None: "no geometry"}[r["inPolygon"]], "distance_to_water_m": "" if r["distanceM"] is None else r["distanceM"],
        "allowed_m": r["allowedM"], "geometry_confidence": r["geometryLevel"] or "", "canonical_area_km2": "" if r["areaKm2"] is None else r["areaKm2"],
        "canonical_name": r["canonicalName"] or "", "nhd_ids": ";".join(map(str, r["nhdIds"])), "gnis_id": r["gnisId"] or "",
        "nearest_other_water": "" if not alt else f"{alt['name'] or 'unnamed'} ({alt['id']}, {alt['areaKm2']} km2)", "nearest_other_water_m": "" if not alt else alt["distanceM"],
        "nearest_other_water_source": "" if not alt else alt["source"] if r["scanAvailable"] else "",
        "competing_water": "" if not r["competitor"] else f"{r['competitor'].get('name') or 'unnamed'} ({r['competitor']['why']})",
        "operator": r["operator"] or "", "usace_name": r["usaceName"] or "", "nid_id": "" if not r["nidDam"] else r["nidDam"]["id"],
        "evidence": evidence_text(r), "positive_signals": ",".join(r.get("positiveSignals", [])), "concerns": " | ".join(r.get("contradictions", [])),
        "proposed_lat": "" if not prop else prop["lat"], "proposed_lon": "" if not prop else prop["lon"], "proposed_basis": "" if not prop else prop["basis"],
        "proposed_move_m": "" if not prop else prop["moveM"],
        "also_nearest_water_point": "" if not r["alsoNearest"] else f"{r['alsoNearest']['lat']},{r['alsoNearest']['lon']} ({r['alsoNearest']['moveM']} m)",
        "binding_held": "yes" if any(b["held"] for b in r["bindings"]) else ("no" if r["bindings"] else "no binding"), "binding_implication": binding_summary(r),
        "recommendation": r["recommendation"], "why": r["why"], "row_digest": r["digest"]}


def html_row(r):
    """Compact JSON for the form (everything the card shows)."""
    prop = r["proposed"]
    cur = r["current"]
    d = dict(
        seq=r["seq"], id=r["lakeId"], name=r["name"], state=r["state"], rec=r["recommendation"], why=r["why"], digest=r["digest"], cls=r["geometryClass"],
        sourceFlag=r["sourceFlag"], registryFlag=r["registryFlag"], cur=dict(lat=cur["lat"], lon=cur["lon"], links=map_links(cur["lat"], cur["lon"])),
        prop=None if not prop else dict(lat=prop["lat"], lon=prop["lon"], basis=prop["basis"], moveM=prop["moveM"], links=map_links(prop["lat"], prop["lon"])),
        alsoNearest=r["alsoNearest"], labelPoint=(None if not r["labelPoint"] else dict(r["labelPoint"], links=map_links(r["labelPoint"]["lat"], r["labelPoint"]["lon"]))), inPolygon=r["inPolygon"], distanceM=r["distanceM"], allowedM=r["allowedM"], toleranceM=r["toleranceM"],
        geom=dict(level=r["geometryLevel"], reasons=r["geometryReasons"], areaKm2=r["areaKm2"], nhdIds=r["nhdIds"], name=r["canonicalName"], gnisId=r["gnisId"], members=r["memberIds"]),
        alts=[dict(a, links=(map_links(a["center"][0], a["center"][1]) if a.get("center") else None)) for a in r["alternatives"]], scanAvailable=r["scanAvailable"],
        competitor=r["competitor"], names=r["nameSources"], areaRatios=r["areaRatios"], dam=r["nidDam"], nidNear=r["nidNearPin"], operator=r["operator"],
        usace=r["usaceName"], osm=r["osmSignal"], pos=r.get("positiveSignals", []), concerns=r.get("contradictions", []), bindings=r["bindings"])
    return d


def manifest_row(r):
    prop = r["proposed"]
    return dict(lakeId=r["lakeId"], name=r["name"], state=r["state"], currentLat=r["current"]["lat"], currentLon=r["current"]["lon"],
                proposedLat=None if not prop else prop["lat"], proposedLon=None if not prop else prop["lon"], recommendation=r["recommendation"],
                geometryClass=r["geometryClass"], bindingCodes=[b["code"] for b in r["bindings"]],
                bindingsAffected=[f"{b['provider']}:{b['station']}" for b in r["bindings"]], bindingChanges=any(b.get("changes") for b in r["bindings"]),
                digest=r["digest"])


def json_for_html(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_html(template_path, pack_id, rows, meta):
    tpl = open(template_path, encoding="utf-8").read()
    payload = dict(packId=pack_id, rows=[html_row(r) for r in rows], meta=meta)
    return tpl.replace("__TITLE__", "Lake Brain coordinate review").replace("__DATA_JSON__", json_for_html(payload))


def write_readme(path, pack_id, rows, meta):
    n = len(rows)
    n_pass = sum(1 for r in rows if r["recommendation"] == "PASS")
    n_flag = n - n_pass
    cls = {}
    for r in rows:
        cls[r["geometryClass"]] = cls.get(r["geometryClass"], 0) + 1
    held = sum(1 for r in rows if any(b["held"] for b in r["bindings"]))
    nb = sum(1 for r in rows if r["bindings"])
    chg = sum(1 for r in rows if any(b.get("changes") for b in r["bindings"]))
    risk = sum(1 for r in rows if any(b["code"] == "AT_RISK" for b in r["bindings"]))
    T = f"""# START HERE - Lake Brain coordinate review

**What this is.** Some lakes in our directory have a map pin that does not sit on the lake (it may be on the dam, on the shore, or in the wrong place). Before the app is allowed to trust the water-level gauge matched to those lakes, a person has to say whether the pin should be moved. The computer has already worked out where each pin should go; you only say yes or no.

**The one question on every card:** *should this lake's pin move to the point the computer proposes, stay where it is, or does someone need to look into it more?*

## What to do
1. Double-click `coordinate_review.html` (opens in Safari or Chrome; nothing is uploaded anywhere).
2. There are **{n} cards**. Each shows the lake, where the pin is now, the lake's real outline from the national water map, the point the computer proposes (always on the water), other lakes nearby, what the gauge matched to this lake looks like, and a computer recommendation (**PASS** or **FLAG**).
3. For each card press one button:
   - **Accept proposed** - the proposed point is the right place for this lake's pin.
   - **Keep current** - leave the pin where it is (the pin is fine, or the lake outline is the thing that is wrong).
   - **Needs more info** - you cannot tell; write a note. These come back to us, nothing is changed.
4. Use the "Open on map" links on a card to look at the pin and the proposed point on a real map (satellite view is the second link). On most cards a quick look is enough.
5. At the end press **Download my review (CSV)** and send that file back (drop it in the chat with Claude, or put it in this folder).

**How long:** plan on about **{max(20, round(n_flag * 2 + 20))} minutes to {max(40, round(n_flag * 2 + 60))} minutes**: roughly 2 minutes for each of the {n_flag} FLAG cards (open the map links, read the one-line reason), plus 20 to 60 minutes to skim the {n_pass} PASS cards (about 10 seconds each when nothing looks odd). Short on time? Settle the FLAG cards first (use the "Show: Computer says FLAG" filter), skim a handful of PASS cards, then use "Mark every untouched PASS card as Accept proposed" - it only fills in cards you have not decided yet, and you can change any of them afterwards. Your answers are saved in your browser as you go; close the page and come back with the same browser and the same file.

## What the computer's PASS and FLAG mean
- **PASS** ({n_pass} cards): the lake's name, size, dam or gauge position all agree that the outline is this lake, no other lake with the same name is near the pin, and the proposed point is on that water. For a pin that is only a short way off the water this is a simple fix; for a pin several kilometres away it is the computer saying "the pin is the mistake, not the lake". Looks safe to accept.
- **FLAG** ({n_flag} cards): look at this one closely. Typical reasons: the pin is kilometres from the outline (could be the wrong lake or the wrong outline), another lake with the same name is nearby, the outline has no second source, or the gauge sits far from this lake's water. A FLAG does not mean the pin is wrong; a PASS does not mean you can skip it.
- The recommendations come from a fixed set of written rules, checked against public maps and the dam inventory. They have **not** been checked against any human answers yet - your answers are the first. Treat PASS as "probably fine", not as "verified".
- Where the identity of the lake is unclear the computer never decides: it shows the alternatives and flags the card.

## What happens next
Your CSV is checked by `jobs/lake-brain/review/ingest_coordinate_review.py` against this pack (every lake id, every proposed coordinate, every decision must match; anything missing or changed is refused). It writes a decisions file and nothing else. **No directory coordinate and no gauge binding is changed by your review or by the checking tool.** The lead then uses your accepted points to prepare a separate, reviewed update of the directory pins, and every gauge binding marked "re-review" on a card is looked at again before it can be accepted.

## What is in this folder
| File | What it is |
|---|---|
| `coordinate_review.html` | The review form (double-click) |
| `coordinate_review_pack.csv` | The same {n} lakes as a spreadsheet, with every evidence column |
| `pack_manifest.json` | Ids, proposed points and fingerprints so the returned CSV can be verified |

## The numbers
- Lakes in this pack: **{n}** ({meta['researchFlagged']} flagged by the geometry audit as identity-risk / off-water; {meta['registryOnly']} more that the live registry flags). Pack id `{pack_id}`.
- Pin classes: {', '.join(f'{k}: {v}' for k, v in sorted(cls.items()))}.
- Computer recommendations: **{n_pass} PASS, {n_flag} FLAG**.
- Lakes with a candidate gauge binding: {nb} ({held} of them are the lakes held back in the binding review). Bindings that sit far from the lake's water (re-review): {risk}. Bindings whose target the correction would change: {chg}.
- Registry used: `lakes.v1.json` generated {meta['registryGeneratedAt']} (sha256 `{meta['registrySha256'][:16]}`).

## Important limits
- Nothing here changes the app, the directory or any gauge binding. Nothing is marked REVIEWED.
- The lake outlines are from the national water map (USGS NHD); they can be out of date or cover only part of a big reservoir.
- Moving a pin by a short distance within the same lake is low risk; moving it kilometres is a different claim (the pin or the lake was wrong) and always deserves your eyes.
"""
    open(path, "w", encoding="utf-8").write(T)


# ------------------------------------------------------------------------------------------------------------ main
def write_pack(out, rows, meta, pack_id, summary):
    """Write the four pack files into `out` (created if needed). Returns the manifest dict."""
    os.makedirs(out, exist_ok=True)
    html_path = os.path.join(out, "coordinate_review.html")
    open(html_path, "w", encoding="utf-8").write(render_html(os.path.join(HERE, "coordinate_review_template.html"), pack_id, rows, meta))
    csv_path = os.path.join(out, "coordinate_review_pack.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(csv_row(r))
    n_pass = sum(1 for r in rows if r["recommendation"] == "PASS")
    manifest = dict(schema=SCHEMA, packId=pack_id, snapshotDate=meta["snapshot"], builtAtUtc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    decisions=list(DECISIONS), counts=dict(lakes=len(rows), pass_=n_pass, flag=len(rows) - n_pass, byClass=summary["byClass"]),
                    inputs=dict(registryGeneratedAt=meta["registryGeneratedAt"], registrySha256=meta["registrySha256"], files=meta.get("inputFiles", {})),
                    files=dict(html=sha256_file(html_path), csv=sha256_file(csv_path)),
                    note="Decisions never change a directory coordinate or a binding; see docs/brains/LAKE_BRAIN_COORDINATE_REVIEW_PROTOCOL.md",
                    lakes=[manifest_row(r) for r in rows])
    json.dump(manifest, open(os.path.join(out, "pack_manifest.json"), "w"), indent=1)
    write_readme(os.path.join(out, "START HERE - README.md"), pack_id, rows, meta)
    return manifest


def load_inputs(data_dir, cache_dir, fetch, progress=True):
    idx = F.fetch_index(cache_dir, fetch)
    registry = {l["lakeId"]: l for l in idx["lakes"]}
    research = {}
    p = os.path.join(data_dir, "geometry", "lake_geometry_flags.csv")
    rrows = read_csv(p) if os.path.exists(p) else []
    for r in rrows:
        research[r["id"]] = r
    directory = {}
    dp = os.path.join(data_dir, "directory_lakes_2026-10-13.json")
    if os.path.exists(dp):
        directory = {l["id"]: l for l in json.load(open(dp))["lakes"]}
    return idx, registry, rrows, research, directory


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=DEFAULT_DATA, help="Sector_Research_Data/lake-brain (bulk research data outside Git)")
    ap.add_argument("--cache-dir", help="cache for registry / NHD responses (default <data-dir>/coords-review)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="pack output directory (created; nothing else in its parent is touched)")
    ap.add_argument("--fetch", action="store_true", help="allow read-only requests to the public registry bucket and the NHD service (cached)")
    ap.add_argument("--neighbours", help="HydroLAKES neighbour file from prep_hydrolakes_neighbours.py (default <cache-dir>/hydrolakes_neighbours.json)")
    ap.add_argument("--with-nhd", action="store_true", help="also scan the USGS NHD service (slow and shared; cached; needs --fetch for uncached lakes)")
    ap.add_argument("--snapshot", default="2026-10-13", help="snapshot label recorded in the pack id")
    ap.add_argument("--limit", type=int, help="only the first N lakes (tests / smoke runs)")
    ap.add_argument("--dry-run", action="store_true", help="compute and print the counts, write nothing")
    args = ap.parse_args(argv)
    cache = args.cache_dir or os.path.join(args.data_dir, "coords-review")
    args.neighbours = args.neighbours or os.path.join(cache, "hydrolakes_neighbours.json")

    idx, registry, rrows, research, directory = load_inputs(args.data_dir, cache, args.fetch)
    pop = population(rrows, registry)
    if args.limit:
        pop = dict(sorted(pop.items())[:args.limit])
    held_ids = set(json.load(open(held_lakes.SNAPSHOT_FILE)).get("coordinateFlagged", []))
    bindings = load_bindings(args.data_dir, held_ids)
    nid_by_id, nid_pts = load_nid(args.data_dir)
    geoms, nhd_of, n_missing = {}, {}, 0
    ids = sorted(pop)

    def geom_one(lid):
        return lid, F.fetch_geometry(cache, registry[lid], args.fetch)

    # static public registry objects: 4 at a time. Everything is cached, so a re-run makes no request.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4 if args.fetch else 1) as ex:
        for lid, g in ex.map(geom_one, ids):
            geoms[lid] = g
            if g is None and (registry[lid].get("geometry") or {}).get("analysisUrl"):
                n_missing += 1
    # scan of other waters near each pin: HydroLAKES (offline prep) and, only with --with-nhd, the USGS NHD service (slow, one request at a time)
    hl = json.load(open(args.neighbours)) if os.path.exists(args.neighbours) else {}
    for i, lid in enumerate(ids):
        scan = None
        if lid in hl:
            scan = [dict(w, source="HydroLAKES v10 (lakes of 10 ha and up)", gnisId=None) for w in hl[lid]]
        if args.with_nhd:
            loc = registry[lid]["location"]
            nh = F.nhd_nearby(cache, loc["lat"], loc["lon"], registry[lid].get("name"), fetch=args.fetch, name_match=G.name_match)
            if nh is not None:
                scan = (scan or []) + nh
            if args.fetch and (i + 1) % 10 == 0:
                print(f"nhd scanned {i + 1}/{len(ids)}", file=sys.stderr, flush=True)
        nhd_of[lid] = scan

    def reg_geom(oid):          # polygons of neighbouring directory lakes (static public registry objects, cached)
        if oid in geoms:
            return geoms[oid]
        geoms[oid] = F.fetch_geometry(cache, registry[oid], args.fetch)
        return geoms[oid]

    rows = build_rows(pop, registry, geoms, research, directory, nhd_of, bindings, nid_by_id, nid_pts, reg_geom)
    snapshot = args.snapshot
    pack_id = pack_id_for(rows, snapshot)
    n_pass = sum(1 for r in rows if r["recommendation"] == "PASS")
    summary = dict(lakes=len(rows), pass_=n_pass, flag=len(rows) - n_pass,
                   byClass={k: sum(1 for r in rows if r["geometryClass"] == k) for k in sorted({r["geometryClass"] for r in rows})},
                   researchFlagged=sum(1 for v in pop.values() if v.startswith("research")), registryOnly=sum(1 for v in pop.values() if v.startswith("registry")),
                   scanMissing=sum(1 for r in rows if not r["scanAvailable"]), geometryFetchMissing=n_missing)
    print(json.dumps(summary, indent=1))
    if args.dry_run:
        return 0
    meta = dict(snapshot=snapshot, registryGeneratedAt=idx.get("generatedAt"), registrySha256=sha256_file(os.path.join(cache, "lakes.v1.json")),
                researchFlagged=summary["researchFlagged"], registryOnly=summary["registryOnly"], decisions=list(DECISIONS),
                inputFiles={name: (sha256_file(path) if os.path.exists(path) else None) for name, path in (
                    ("geometry/lake_geometry_flags.csv", os.path.join(args.data_dir, "geometry", "lake_geometry_flags.csv")),
                    ("binding2/verified_v2_full.csv", os.path.join(args.data_dir, "binding2", "verified_v2_full.csv")),
                    ("binding/candidates_all.csv", os.path.join(args.data_dir, "binding", "candidates_all.csv")),
                    ("context/nid/nid_v1_subset.json", os.path.join(args.data_dir, "context", "nid", "nid_v1_subset.json")),
                    ("coords-review/hydrolakes_neighbours.json", args.neighbours),
                    ("directory_lakes_2026-10-13.json", os.path.join(args.data_dir, "directory_lakes_2026-10-13.json")))})
    write_pack(args.out, rows, meta, pack_id, summary)
    print("wrote pack", pack_id, "to", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
