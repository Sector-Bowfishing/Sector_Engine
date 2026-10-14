#!/usr/bin/env python3
"""Ingest Michael's coordinate review (the CSV exported by coordinate_review.html) and write a machine-readable decisions file.

Validates the export against the pack manifest (pack_manifest.json in the pack directory):
  * the pack id matches; every manifest lake has exactly one row; no unknown or duplicate lake ids;
  * every row has a decision (ACCEPT_PROPOSED, KEEP_CURRENT or NEEDS_INFO) - a blank / PENDING decision is refused;
  * nothing was tampered with: current and proposed coordinates, the computer recommendation and the row digest must equal the manifest;
  * ACCEPT_PROPOSED needs a proposed coordinate in the manifest (a lake with no safe proposal can only be KEEP_CURRENT or NEEDS_INFO).
Dry run by default; --write writes ONE file, <out-dir>/coordinate_review_decisions.json.

This tool NEVER changes a directory coordinate, a registry object, a binding, a lifecycle status or any REVIEWED marker. The decisions
file says `applied: false`; applying accepted coordinates is a separate, reviewed change made by the lead (protocol doc section 6).
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PACK = "/Users/mcather/Desktop/Sector Handoffs/Sector Engine/Lake Brain Coordinate Review"
DEFAULT_OUT = os.path.normpath(os.path.join(HERE, "..", "data"))
OUT_NAME = "coordinate_review_decisions.json"
SCHEMA = "lake-brain-coordinate-review-decisions/v1"
DECISIONS = {"ACCEPT_PROPOSED", "KEEP_CURRENT", "NEEDS_INFO"}
REQUIRED = {"pack_id", "lake_id", "decision", "current_lat", "current_lon", "proposed_lat", "proposed_lon", "computer_recommendation", "row_digest"}
COORD_TOL = 1e-6
BINDING_REREVIEW_CODES = {"AT_RISK", "AMBIGUOUS", "UNVERIFIED"}


class IngestError(Exception):
    pass


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_manifest(pack_dir):
    p = os.path.join(pack_dir, "pack_manifest.json")
    if not os.path.exists(p):
        raise IngestError(f"pack manifest missing: {p}")
    m = json.load(open(p))
    if not str(m.get("schema", "")).startswith("lake-brain-coordinate-review-pack/"):
        raise IngestError("pack_manifest.json is not a coordinate review pack manifest")
    return m


def _num(s):
    s = (s or "").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        raise ValueError(s)


def _same(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= COORD_TOL


def validate(rows, manifest):
    """-> (decisions by lake id, errors list)."""
    errors = []
    if not rows:
        return {}, ["the review CSV has no data rows"]
    missing_cols = REQUIRED - set(rows[0].keys())
    if missing_cols:
        return {}, [f"missing column(s) {sorted(missing_cols)}"]
    pack_lakes = {l["lakeId"]: l for l in manifest["lakes"]}
    out, seen = {}, set()
    for i, r in enumerate(rows, start=2):
        lid = (r.get("lake_id") or "").strip()
        if (r.get("pack_id") or "").strip() != manifest["packId"]:
            errors.append(f"line {i}: pack_id '{r.get('pack_id')}' does not match this pack ('{manifest['packId']}')")
        if lid not in pack_lakes:
            errors.append(f"line {i}: lake id '{lid}' is not part of this pack")
            continue
        if lid in seen:
            errors.append(f"line {i}: duplicate lake id '{lid}'")
            continue
        seen.add(lid)
        m = pack_lakes[lid]
        d = (r.get("decision") or "").strip().upper()
        if d not in DECISIONS:
            errors.append(f"line {i}: {lid}: missing or invalid decision '{r.get('decision')}' (must be one of {sorted(DECISIONS)}; 'PENDING' or blank means not decided)")
            continue
        try:
            cur = (_num(r["current_lat"]), _num(r["current_lon"]))
            prop = (_num(r["proposed_lat"]), _num(r["proposed_lon"]))
        except ValueError as e:
            errors.append(f"line {i}: {lid}: coordinate '{e}' is not a number")
            continue
        if not (_same(cur[0], m["currentLat"]) and _same(cur[1], m["currentLon"])):
            errors.append(f"line {i}: {lid}: current coordinate {cur} differs from the pack ({m['currentLat']}, {m['currentLon']}); the export was altered")
        if not (_same(prop[0], m["proposedLat"]) and _same(prop[1], m["proposedLon"])):
            errors.append(f"line {i}: {lid}: proposed coordinate {prop} differs from the pack ({m['proposedLat']}, {m['proposedLon']}); the export was altered")
        if (r.get("computer_recommendation") or "").strip() != m["recommendation"]:
            errors.append(f"line {i}: {lid}: computer_recommendation '{r.get('computer_recommendation')}' differs from the pack ('{m['recommendation']}')")
        if (r.get("row_digest") or "").strip() != m["digest"]:
            errors.append(f"line {i}: {lid}: row_digest differs from the pack")
        if d == "ACCEPT_PROPOSED" and m["proposedLat"] is None:
            errors.append(f"line {i}: {lid}: ACCEPT_PROPOSED but the pack has no proposed coordinate for this lake")
        out[lid] = dict(decision=d, notes=(r.get("notes") or "").strip(), reviewer=(r.get("reviewer") or "").strip(), decidedAt=(r.get("decided_at_utc") or "").strip())
    for lid in pack_lakes:
        if lid not in seen:
            errors.append(f"{lid}: no decision row in the export (every lake in the pack needs a decision)")
    return out, errors


def build_result(manifest, decisions, review_csv, now):
    rows, cnt = [], {k: 0 for k in sorted(DECISIONS)}
    agree = dict(passAccepted=0, passKept=0, passNeedsInfo=0, flagAccepted=0, flagKept=0, flagNeedsInfo=0)
    for l in manifest["lakes"]:
        d = decisions[l["lakeId"]]
        cnt[d["decision"]] += 1
        acc = d["decision"] == "ACCEPT_PROPOSED"
        key = ("pass" if l["recommendation"] == "PASS" else "flag") + {"ACCEPT_PROPOSED": "Accepted", "KEEP_CURRENT": "Kept", "NEEDS_INFO": "NeedsInfo"}[d["decision"]]
        agree[key] += 1
        rerev = bool(l.get("bindingChanges")) or any(c in BINDING_REREVIEW_CODES for c in l.get("bindingCodes", []))
        rows.append(dict(
            lakeId=l["lakeId"], name=l["name"], state=l["state"], decision=d["decision"], computerRecommendation=l["recommendation"],
            geometryClass=l["geometryClass"], currentLat=l["currentLat"], currentLon=l["currentLon"],
            acceptedLat=l["proposedLat"] if acc else None, acceptedLon=l["proposedLon"] if acc else None,
            overridesFlag=(acc and l["recommendation"] == "FLAG"), bindingsAffected=l.get("bindingsAffected", []),
            bindingNeedsRereview=rerev, bindingTargetChanges=bool(l.get("bindingChanges")), notes=d["notes"], reviewer=d["reviewer"], decidedAt=d["decidedAt"]))
    pass_rows = agree["passAccepted"] + agree["passKept"] + agree["passNeedsInfo"]
    flag_rows = agree["flagAccepted"] + agree["flagKept"] + agree["flagNeedsInfo"]
    return dict(
        schema=SCHEMA, packId=manifest["packId"], generatedAtUtc=now, reviewCsvSha256=sha256_file(review_csv),
        reviewers=sorted({d["reviewer"] for d in decisions.values() if d["reviewer"]}),
        applied=False,
        note="Recorded decisions only. This file does not change any directory coordinate, registry object or binding; no binding is marked REVIEWED by it.",
        counts=dict(lakes=len(rows), acceptProposed=cnt["ACCEPT_PROPOSED"], keepCurrent=cnt["KEEP_CURRENT"], needsInfo=cnt["NEEDS_INFO"]),
        recommendationVsDecision=dict(agree, passRows=pass_rows, flagRows=flag_rows,
                                      passAcceptRate=(None if not pass_rows else round(agree["passAccepted"] / pass_rows, 3)),
                                      flagAcceptRate=(None if not flag_rows else round(agree["flagAccepted"] / flag_rows, 3))),
        acceptedCoordinates=[{"lakeId": r["lakeId"], "lat": r["acceptedLat"], "lon": r["acceptedLon"]} for r in rows if r["decision"] == "ACCEPT_PROPOSED"],
        bindingRereviewLakes=sorted(r["lakeId"] for r in rows if r["bindingNeedsRereview"]),
        decisions=rows)


def run(args):
    manifest = load_manifest(args.pack_dir)
    rows = read_csv(args.review_csv)
    decisions, errors = validate(rows, manifest)
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        print(f"REFUSED: {len(errors)} problem(s); nothing written", file=sys.stderr)
        return 2, None
    now = args.now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = build_result(manifest, decisions, args.review_csv, now)
    c = result["counts"]
    print(f"pack {manifest['packId']}: {c['lakes']} lakes decided - accept proposed {c['acceptProposed']}, keep current {c['keepCurrent']}, needs info {c['needsInfo']}")
    rv = result["recommendationVsDecision"]
    print(f"computer PASS rows accepted: {rv['passAccepted']} of {rv['passRows']}; computer FLAG rows accepted: {rv['flagAccepted']} of {rv['flagRows']}")
    print(f"gauge bindings needing a second look: {len(result['bindingRereviewLakes'])} lakes")
    if args.write:
        os.makedirs(args.out_dir, exist_ok=True)
        p = os.path.join(args.out_dir, OUT_NAME)
        json.dump(result, open(p, "w"), indent=1)
        print("wrote", p, "(applied: false - no coordinate or binding changed)")
    else:
        print(f"(dry run: nothing written; add --write to write {OUT_NAME})")
    return 0, result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-csv", required=True, help="CSV exported by coordinate_review.html")
    ap.add_argument("--pack-dir", default=DEFAULT_PACK, help="the coordinate review pack directory (pack_manifest.json)")
    ap.add_argument("--out-dir", default=DEFAULT_OUT, help="where --write puts coordinate_review_decisions.json")
    ap.add_argument("--write", action="store_true", help="write the decisions file (default: dry run)")
    ap.add_argument("--now", help="timestamp to record (tests)")
    args = ap.parse_args(argv)
    try:
        code, _ = run(args)
    except IngestError as e:
        print("ERROR:", e, file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
