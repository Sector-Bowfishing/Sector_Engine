#!/usr/bin/env python3
"""Add newly recovered lakes to the LIVE Lake Registry index without touching any other lake.

`build_geometry.py --only "<id>,<id>"` builds a partial registry (just those entries + their geometry objects). Publishing that
partial index would replace the 621-lake index with 2 lakes, so this tool merges instead:

  live index (downloaded, read-only)  +  partial build (the recovered lakes)  ->  new full index + manifest, staged in --out

A second list (`--refresh-null`) updates the status text of lakes that stay null: a lake whose live entry says `pending`
(retrieval failed at build time) and whose fresh retrieval succeeded but found no NHD water body gets the builder's accurate
`no-nhd` reason. Geometry stays null; nothing is published for it.

Safety rules (each is a hard failure, nothing is written):
  * a target must be `geometry: null` in the live index (this ADDS geometry; it never replaces a published shoreline)
    and must have geometry in the partial build, with both variants' files present and sha256-correct;
  * every non-target entry of the new index is byte-for-byte the live entry (compared as parsed JSON, including memberIds);
  * every geometry object path of the live index is still referenced with the same sha256;
  * the merged index passes lake_geometry.validate_entry for all entries; count and lake set are unchanged.
The staged `lakes/` tree contains ONLY the new objects, so `gcloud storage cp --no-clobber` cannot overwrite anything.

  python merge_registry.py --live live/lakes.v1.json --live-manifest live/manifest.v1.json --partial <build_out> \
      --targets "Buckeye Lake|OH,Wilson Lake / Kaelepulu Pond|HI" --out <stage_dir> [--built-at ISO]
"""
import argparse
import copy
import datetime as dt
import gzip
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lake_geometry as lg  # noqa: E402

BASE_URL = "https://storage.googleapis.com/sector-lake-registry"


class MergeError(Exception):
    pass


def load_index(path):
    raw = open(path, "rb").read()
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    return json.loads(raw)


def link_members_unchanged(index):
    """memberIds of the merged index must equal the entries' own memberIds (the targets' NHD ids must not join an existing group)."""
    owner = {}
    for e in index:
        for nid in ((e["geometry"] or {}).get("seedIds") or []):
            owner.setdefault(nid, set()).add(e["lakeId"])
    shared = {n: sorted(v) for n, v in owner.items() if len(v) > 1}
    return shared


def merge(live, partial, targets, partial_dir, built_at, refresh_null=()):
    """Return (merged_index_dict, report). Raises MergeError on any violated rule."""
    refresh_null = list(refresh_null)
    lakes = {e["lakeId"]: e for e in live["lakes"]}
    new = {e["lakeId"]: e for e in partial["lakes"]}
    report = {"targets": [], "unchanged": 0}
    for t in targets:
        if t not in lakes:
            raise MergeError(f"{t}: not in the live index")
        if lakes[t]["geometry"] is not None:
            raise MergeError(f"{t}: live entry already has geometry; this tool only ADDS geometry to null lakes")
        if t not in new or new[t]["geometry"] is None:
            raise MergeError(f"{t}: partial build has no geometry for it")
        g = new[t]["geometry"]
        for v in ("display", "analysis"):
            rel = f"lakes/{new[t]['lakeKey']}/geometry.{lg.GEOMETRY_VERSION}.{v}.geojson.gz"
            p = os.path.join(partial_dir, rel)
            if not os.path.exists(p):
                raise MergeError(f"{t}: missing {rel}")
            if lg.sha256(open(p, "rb").read()) != g["sha256"][v]:
                raise MergeError(f"{t}: sha256 of {rel} does not match the index entry")
    for t in refresh_null:
        if t not in lakes or lakes[t]["geometry"] is not None or lakes[t].get("geometryMissingStatus") != "pending":
            raise MergeError(f"{t}: --refresh-null needs a live entry that is null and `pending`")
        if t not in new or new[t]["geometry"] is not None or new[t].get("geometryMissingStatus") == "pending":
            raise MergeError(f"{t}: the fresh retrieval must be a null entry with a final (non-pending) status")
        if t in targets:
            raise MergeError(f"{t}: cannot be both a target and a refresh-null lake")
    merged = copy.deepcopy(live)
    out = []
    report["refreshedNull"] = []
    for e in live["lakes"]:
        if e["lakeId"] in refresh_null:
            out.append(copy.deepcopy(new[e["lakeId"]]))
            report["refreshedNull"].append(e["lakeId"])
        elif e["lakeId"] in targets:
            ne = copy.deepcopy(new[e["lakeId"]])
            ne["memberIds"] = [e["lakeId"]]
            out.append(ne)
            report["targets"].append(e["lakeId"])
        else:
            out.append(e)
            report["unchanged"] += 1
    merged["lakes"] = out
    merged["generatedAt"] = built_at
    merged["count"] = len(out)
    # ---- invariants
    if len(out) != len(live["lakes"]) or [e["lakeId"] for e in out] != [e["lakeId"] for e in live["lakes"]]:
        raise MergeError("lake set or order changed")
    for a, b in zip(live["lakes"], out):
        if a["lakeId"] not in targets and a["lakeId"] not in refresh_null and a != b:
            raise MergeError(f"{a['lakeId']}: a non-target entry changed")
        ga, gb = a.get("geometry"), b.get("geometry")
        if ga is not None and (gb is None or gb["sha256"] != ga["sha256"] or gb["displayUrl"] != ga["displayUrl"]):
            raise MergeError(f"{a['lakeId']}: published geometry would change")
    shared = link_members_unchanged(out)
    for t in targets:
        if any(t in v for v in shared.values()):
            raise MergeError(f"{t}: shares an NHD feature with another lake ({shared}); needs a memberIds review, not an automatic merge")
    problems = [p for e in out for p in lg.validate_entry(e, BASE_URL)]
    if problems:
        raise MergeError("schema problems: " + "; ".join(problems[:5]))
    return merged, report


def stage(args):
    live = load_index(args.live)
    partial = load_index(os.path.join(args.partial, "registry", "lakes.v1.json"))
    targets = [t for t in args.targets.split(",") if t]
    built_at = args.built_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    refresh = [t for t in (args.refresh_null or "").split(",") if t]
    merged, report = merge(live, partial, targets, args.partial, built_at, refresh)
    os.makedirs(os.path.join(args.out, "registry"), exist_ok=True)
    shutil.rmtree(os.path.join(args.out, "lakes"), ignore_errors=True)
    rb = json.dumps(merged, separators=(",", ":"), sort_keys=False, allow_nan=False).encode()
    open(os.path.join(args.out, "registry", "lakes.v1.json"), "wb").write(rb)
    # only the NEW objects are staged (so a no-clobber upload cannot touch anything else)
    lakes = {e["lakeId"]: e for e in merged["lakes"]}
    staged = []
    for t in targets:
        for v in ("display", "analysis"):
            rel = f"lakes/{lakes[t]['lakeKey']}/geometry.{lg.GEOMETRY_VERSION}.{v}.geojson.gz"
            dst = os.path.join(args.out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(args.partial, rel), dst)
            staged.append(rel)
    # manifest: the live one with updated counts and an amendment record (the build inputs of the original build are unchanged)
    man = json.load(open(args.live_manifest)) if args.live_manifest else {}
    from collections import Counter
    lv = Counter(e["geometryConfidence"]["level"] for e in merged["lakes"])
    withg = [e for e in merged["lakes"] if e["geometry"]]
    man.setdefault("counts", {}).update({"lakes": len(merged["lakes"]), "withGeometry": len(withg), "geometryNull": len(merged["lakes"]) - len(withg),
                                         "confidenceAfter": dict(lv),
                                         "pointFlag": dict(Counter(e["pointFlag"] or "none" for e in merged["lakes"])),
                                         "nullByStatus": dict(Counter(e["geometryMissingStatus"] for e in merged["lakes"] if not e["geometry"]))})
    man["objectCount"] = man.get("objectCount", 0) + len(staged)
    man.setdefault("amendments", []).append({"at": built_at, "kind": "add-geometry-to-null-lakes", "lakes": targets, "statusRefreshedLakes": refresh, "objects": staged,
                                              "note": "index-only replacement + new no-clobber objects; no published object changed"})
    man.setdefault("files", {})["registry/lakes.v1.json"] = {"bytes": len(rb), "gzipBytes": len(lg.gzip_bytes(rb)), "sha256": lg.sha256(rb)}
    json.dump(man, open(os.path.join(args.out, "registry", "manifest.v1.json"), "w"), indent=1)
    report.update({"staged": staged, "counts": man["counts"], "indexSha256": lg.sha256(rb)})
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", required=True)
    ap.add_argument("--live-manifest", default="")
    ap.add_argument("--partial", required=True, help="output dir of build_geometry.py --only ...")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--refresh-null", default="", help="ids that stay null but whose `pending` status is replaced by the fresh no-nhd result")
    ap.add_argument("--out", required=True)
    ap.add_argument("--built-at", default="")
    try:
        print(json.dumps(stage(ap.parse_args()), indent=1))
    except MergeError as e:
        raise SystemExit(f"MERGE REFUSED: {e}")


if __name__ == "__main__":
    main()
