#!/usr/bin/env python3
"""Synthetic controls for the coordinate review rules (coord_evidence.py). There are no human labels yet, so this is the only measurement of how the
rules behave. It does NOT validate the pack against the truth; it measures two things on registry lakes whose pin is already fine (pointFlag ok):

  A  wrong-lake control: move lake L's pin onto the real directory pin of a DIFFERENT, nearby lake M (outlines 2 to 15 km apart). The right answer is
     never PASS (the pin belongs to M). Reports how many are wrongly PASS.
  B  dam-offset control: move L's pin onto its own NID dam when that dam is at least 400 m from the outline (the typical way a directory pin ends
     up off the water). The right answer is a proposal on L's own water. Reports the PASS rate, how many proposals land on L's outline, and the
     distance from the proposal to L's original (good) pin.

Reads the cache built by build_coordinate_review_pack.py (no network unless --fetch). Prints one JSON summary.
    python3 validate_coordinate_rules.py [--data-dir DIR] [--fetch] [--max 120]
"""
import argparse
import copy
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_coordinate_review_pack as B  # noqa: E402
import coord_evidence as E  # noqa: E402
import coord_fetch as F  # noqa: E402
import coord_geo as G  # noqa: E402
import held_lakes  # noqa: E402


def evaluate(lid, registry, geoms, research, directory, hl, bindings, nid_by, nid_pts, reg_geom, pin=None):
    lake = copy.deepcopy(registry[lid])
    if pin:
        lake["location"]["lat"], lake["location"]["lon"] = pin
    reg = dict(registry)
    reg[lid] = lake
    scan = [dict(w, source="HydroLAKES v10 (lakes of 10 ha and up)", gnisId=None) for w in hl.get(lid, [])]
    rows = B.build_rows({lid: "control"}, reg, geoms, research, directory, {lid: scan}, bindings, nid_by, nid_pts, reg_geom)
    return rows[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=B.DEFAULT_DATA)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--max", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20261013)
    ap.add_argument("--pairs", choices=("median", "all"), default="median",
                    help="control A: one transplant per lake (the median-distance neighbour) or every neighbour 3 to 20 km away (a broader, partly held-out set)")
    args = ap.parse_args(argv)
    cache = os.path.join(args.data_dir, "coords-review")
    idx, registry, rrows, research, directory = B.load_inputs(args.data_dir, cache, args.fetch)
    pop = B.population(rrows, registry)
    held = set(json.load(open(held_lakes.SNAPSHOT_FILE)).get("coordinateFlagged", []))
    bindings = B.load_bindings(args.data_dir, held)
    nid_by, nid_pts = B.load_nid(args.data_dir)
    hl = json.load(open(os.path.join(cache, "hydrolakes_neighbours.json")))
    geoms = {}

    def reg_geom(oid):
        if oid not in geoms:
            geoms[oid] = F.fetch_geometry(cache, registry[oid], args.fetch)
        return geoms[oid]

    ok = [l for l, v in registry.items() if l not in pop and v.get("pointFlag") == "ok" and v.get("bbox") and (v.get("geometryConfidence") or {}).get("level") == "HIGH"]
    rnd = random.Random(args.seed)
    rnd.shuffle(ok)
    # A: wrong-lake pins
    a_res = []
    for lid in ok:
        if len(a_res) >= args.max:
            break
        polys = G.polygons_of(reg_geom(lid))
        if not polys:
            continue
        members = set(registry[lid].get("memberIds") or [lid])
        cands = []
        for mid, m in registry.items():
            if mid in members or m.get("pointFlag") != "ok" or not m.get("bbox"):
                continue
            mp = m["location"]
            d = G.haversine_m(registry[lid]["location"]["lat"], registry[lid]["location"]["lon"], mp["lat"], mp["lon"])
            if 3000 <= d <= 20000:
                cands.append((d, mid))
        if not cands:
            continue
        cands.sort()
        chosen = [cands[len(cands) // 2][1]] if args.pairs == "median" else [m for _, m in cands]
        for mid in chosen:
            pin = (registry[mid]["location"]["lat"], registry[mid]["location"]["lon"])
            d_poly = G.distance_to_polygons_m(pin[0], pin[1], polys)
            if d_poly is None or d_poly < 1500:         # the transplanted pin must be clearly off L's water
                continue
            r = evaluate(lid, registry, geoms, research, directory, hl, bindings, nid_by, nid_pts, reg_geom, pin)
            a_res.append(dict(lakeId=lid, wrongPinOf=mid, distanceM=round(d_poly), rec=r["recommendation"], cls=r["geometryClass"], why=r["why"]))
    # B: dam offsets
    b_res = []
    for lid in ok:
        if len(b_res) >= args.max:
            break
        link = nid_by.get((registry[lid].get("externalIds") or {}).get("nidId") or "")
        polys = G.polygons_of(reg_geom(lid))
        if not link or not polys:
            continue
        d = G.distance_to_polygons_m(link["lat"], link["lon"], polys)
        if d is None or d < 400 or d > 5000:
            continue
        r = evaluate(lid, registry, geoms, research, directory, hl, bindings, nid_by, nid_pts, reg_geom, (round(link["lat"], 4), round(link["lon"], 4)))
        orig = registry[lid]["location"]
        prop = r["proposed"]
        on = bool(prop) and G.point_in_polygons(prop["lat"], prop["lon"], polys)
        b_res.append(dict(lakeId=lid, damToWaterM=round(d), rec=r["recommendation"], cls=r["geometryClass"], proposalOnWater=on,
                          proposalToOriginalPinM=None if not prop else round(G.haversine_m(prop["lat"], prop["lon"], orig["lat"], orig["lon"])),
                          originalPinToWaterM=round(G.distance_to_polygons_m(orig["lat"], orig["lon"], polys))))
    def rate(rs, f):
        return None if not rs else round(sum(1 for x in rs if f(x)) / len(rs), 3)
    near = [x["proposalToOriginalPinM"] for x in b_res if x["proposalToOriginalPinM"] is not None]
    near.sort()
    out = dict(
        A_wrong_lake=dict(n=len(a_res), wronglyPass=sum(1 for x in a_res if x["rec"] == "PASS"), flag=sum(1 for x in a_res if x["rec"] == "FLAG"),
                          wrongPassIds=[x["lakeId"] for x in a_res if x["rec"] == "PASS"][:10]),
        B_dam_offset=dict(n=len(b_res), passRate=rate(b_res, lambda x: x["rec"] == "PASS"), proposalOnWaterRate=rate(b_res, lambda x: x["proposalOnWater"]),
                          proposalToOriginalPinMedianM=(near[len(near) // 2] if near else None), proposalToOriginalPinP90M=(near[int(len(near) * 0.9)] if near else None),
                          classes={c: sum(1 for x in b_res if x["cls"] == c) for c in sorted({x["cls"] for x in b_res})}))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
