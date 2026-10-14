#!/usr/bin/env python3
"""Ingest Michael's export of the consolidated (individually reviewed) binding packet. DRY RUN BY DEFAULT; --write is required to write anything.

    python3 ingest_batch_review.py --export lake_brain_consolidated_review_<date>.csv --manifest "<packet>/pack_manifest.json" [--write]

What it checks (every problem is listed; any problem stops the ingest, nothing is written):
  * the export belongs to this packet (pack_id), every manifest row appears exactly once, no unknown or duplicate (section, lake id);
  * every decision is ACCEPT / REJECT / NEEDS REVIEW (blank or PENDING = not decided). Section A rows must all be decided unless --allow-partial
    (only the ACCEPT rows can ever count, so a partial export is harmless); Section B rows may be left undecided;
  * the locked columns (section, lake name, state, provider, provider identifier, computer recommendation, row digest) equal the manifest: an
    edited or foreign export is refused;
  * every Section A id is in the bindings table, is not one of the 5 REVIEWED pilots and is not held.

Individual acceptance, no extrapolation:
  * Section A: the accepted set is ONLY the rows decided ACCEPT. REJECT and NEEDS REVIEW rows are recorded and excluded. Lakes not in the packet are
    never accepted by this ingest.
  * Section B: a row counts only if Michael ACCEPTs it AND it is in the bindings table (and not a pilot / held). A Section B ACCEPT of a lake that is
    not in the table (the recovered mismatch-14 lakes, wave-1 flagged lakes, held lakes) is recorded as 'accepted for later table inclusion' and
    is NEVER written to accepted_batch.json.

Files written with --write (into --data-dir, default jobs/lake-brain/data):
  review_batches/consolidated_result.json      this packet's result (decisions, accepted/rejected/needs-review ids, sha256 of the export and manifest)
  accepted_batch.json                          CUMULATIVE: the sorted, duplicate-free union of every individually accepted lake over all
                                               review_batches/*_result.json (plus the sample component, below). Never loses an id (a revoked ACCEPT
                                               needs --allow-revoke and is recorded)
  binding_review_result.json                   reviewKind 'individual-cumulative': components, sha256 of accepted_batch.json (acceptedBatchSha256) and of every
                                               component file; this is the form history/preseed_fleet.py validates (validate_batch)

UNION WITH A SAMPLE-BASED RESULT (ingest_review_result.py): pass --sample-dir <folder with its accepted_batch.json and binding_review_result.json>. It is
copied to review_batches/sample_accepted_batch.json and sample_review_result.json and joins the union under ONE rule: an individual decision always
wins over extrapolation. cumulative = individual ACCEPTs  UNION  (sample accepted batch  MINUS  every lake Michael individually rejected or marked
NEEDS REVIEW). A lake that Michael individually ACCEPTs but the sample REJECTED (or the reverse conflict) is an error to resolve by hand.
The sample result must itself be a legitimately formed ACCEPT_BATCH (verdict ACCEPT_BATCH, ruleMet true, <= maxErrors rejects, nothing undecided).
"""
import argparse
import csv
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import consolidated_common as CC  # noqa: E402
import held_lakes  # noqa: E402

SAMPLE_BATCH = "sample_accepted_batch.json"
SAMPLE_RESULT = "sample_review_result.json"


class IngestError(Exception):
    pass


def norm_decision(s):
    s = " ".join((s or "").replace("_", " ").replace("-", " ").upper().split())
    return "" if s == "PENDING" else s


def read_export(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        rows = list(rd)
        cols = rd.fieldnames or []
    missing = [c for c in CC.EXPORT_COLUMNS if c not in cols]
    if missing:
        raise IngestError(f"the export lacks column(s) {missing}: it is not a file the review form produces")
    return rows


def load_json(path, what):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise IngestError(f"{what} unreadable: {path}: {e}")


def analyse(export_rows, manifest, table_ids, pilots, held, allow_partial=False):
    """Pure validation + classification. Returns (problems, info)."""
    problems = []
    mrows = {(r["section"], r["id"]): r for r in manifest["rows"]}
    seen = {}
    for i, r in enumerate(export_rows, 2):
        k = (r["section"].strip(), r["lake_id"])
        if r["pack_id"] != manifest["packId"]:
            problems.append(f"line {i}: pack_id {r['pack_id']!r} is not this packet ({manifest['packId']})")
        if k not in mrows:
            problems.append(f"line {i}: unknown row {k[0]}/{k[1]!r} (not in the packet manifest)")
            continue
        if k in seen:
            problems.append(f"line {i}: duplicate row {k[0]}/{k[1]!r}")
            continue
        seen[k] = r
    for k in mrows:
        if k not in seen:
            problems.append(f"missing row {k[0]}/{k[1]!r} (in the manifest, not in the export)")
    dec = {}
    for k, r in seen.items():
        m = mrows[k]
        d = norm_decision(r["decision"])
        if d not in CC.DECISIONS and d != "":
            problems.append(f"{k[0]}/{k[1]}: decision {r['decision']!r} is not one of {list(CC.DECISIONS)}")
            d = ""
        if d == "" and k[0] == CC.SECTION_A and not allow_partial:
            problems.append(f"{k[0]}/{k[1]}: not decided (every Section A row must be decided; use --allow-partial to ingest a partial export)")
        dec[k] = d
        locked = {"section": m["section"], "lake_name": m["name"], "state": m["state"], "provider": m["provider"], "provider_identifier": m["identifier"],
                  "computer_recommendation": m["recommendation"], "row_digest": m["digest"]}
        for col, want in locked.items():
            if (r[col] if col != "section" else r[col].strip()) != want:
                problems.append(f"{k[0]}/{k[1]}: locked field {col} was changed (export {r[col]!r} != packet {want!r})")
    for (sec, lid), m in mrows.items():
        if sec == CC.SECTION_A:
            if lid not in table_ids:
                problems.append(f"A/{lid}: not in the bindings table")
            if lid in pilots:
                problems.append(f"A/{lid}: is one of the REVIEWED pilots (a packet never contains a pilot)")
            if lid in held:
                problems.append(f"A/{lid}: is held back (hold list)")
    by = {s: {d: [] for d in (*CC.DECISIONS, "")} for s in (CC.SECTION_A, CC.SECTION_B)}
    for (sec, lid), d in dec.items():
        by[sec][d].append(lid)
    for s in by:
        for d in by[s]:
            by[s][d].sort()
    a_acc = by["A"]["ACCEPT"]
    b_acc = by["B"]["ACCEPT"]
    b_countable = [l for l in b_acc if l in table_ids and l not in pilots and l not in held]
    b_later = [l for l in b_acc if l not in b_countable]
    info = dict(
        sectionA=dict(size=sum(1 for k in mrows if k[0] == "A"), accepted=len(a_acc), rejected=len(by["A"]["REJECT"]), needsReview=len(by["A"]["NEEDS REVIEW"]),
                      notDecided=len(by["A"][""]), acceptedIds=a_acc, rejectedIds=by["A"]["REJECT"], needsReviewIds=by["A"]["NEEDS REVIEW"], notDecidedIds=by["A"][""]),
        sectionB=dict(size=sum(1 for k in mrows if k[0] == "B"), accepted=len(b_acc), rejected=len(by["B"]["REJECT"]), needsReview=len(by["B"]["NEEDS REVIEW"]),
                      notDecided=len(by["B"][""]), acceptedIds=b_acc, acceptedCountableIds=b_countable, acceptedForLaterTableInclusionIds=b_later,
                      rejectedIds=by["B"]["REJECT"], needsReviewIds=by["B"]["NEEDS REVIEW"], notDecidedIds=by["B"][""]),
        acceptedIds=sorted(set(a_acc) | set(b_countable)),
        decisions=[dict(section=k[0], id=k[1], decision=(d or "NOT DECIDED"), notes=seen[k]["notes"], decidedAtUtc=seen[k]["decided_at_utc"]) for k, d in sorted(dec.items())],
        reviewer=next((r["reviewer"] for r in export_rows if r.get("reviewer")), ""), exportedAtUtc=(export_rows[0]["exported_at_utc"] if export_rows else ""),
    )
    return problems, info


def load_individual_results(batches_dir, exclude_pack=None):
    out = []
    if os.path.isdir(batches_dir):
        for fn in sorted(os.listdir(batches_dir)):
            if fn.endswith("_result.json") and not fn.startswith("sample_"):
                p = os.path.join(batches_dir, fn)
                d = load_json(p, "batch result")
                if d.get("schema") != CC.SCHEMA_RESULT:
                    raise IngestError(f"{p}: not a {CC.SCHEMA_RESULT} file")
                if exclude_pack and d.get("packId") == exclude_pack:
                    continue
                out.append((fn, p, d))
    return out


def sample_component(sample_dir=None, batches_dir=None):
    """Read the sample pair from --sample-dir, or the copies already in review_batches/. Returns (batch_ids, result, batch_path, result_path) or None."""
    if sample_dir:
        bp, rp = os.path.join(sample_dir, "accepted_batch.json"), os.path.join(sample_dir, "binding_review_result.json")
    else:
        bp, rp = os.path.join(batches_dir, SAMPLE_BATCH), os.path.join(batches_dir, SAMPLE_RESULT)
        if not (os.path.isfile(bp) and os.path.isfile(rp)):
            return None
    for p in (bp, rp):
        if not os.path.isfile(p):
            raise IngestError(f"sample result file not found: {p}")
    ids, res = load_json(bp, "sample accepted batch"), load_json(rp, "sample review result")
    bad = []
    if res.get("reviewKind"):
        bad.append("the sample result is itself a cumulative individual result")
    if res.get("verdict") != "ACCEPT_BATCH" or res.get("ruleMet") is not True:
        bad.append(f"sample verdict {res.get('verdict')!r} / ruleMet {res.get('ruleMet')!r} is not an accepted sample batch")
    if res.get("unsure") != 0 or res.get("pending") != 0:
        bad.append("the sample has undecided rows")
    mx = (res.get("acceptRule") or {}).get("maxErrors")
    if not isinstance(mx, int) or not isinstance(res.get("rejected"), int) or res["rejected"] > mx:
        bad.append("the sample has more rejects than its rule allows")
    if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids) or ids != sorted(ids) or len(set(ids)) != len(ids):
        bad.append("the sample accepted batch is not a sorted, duplicate-free list of ids")
    if bad:
        raise IngestError("sample result refused: " + "; ".join(bad))
    return ids, res, bp, rp


def cumulative(results, sample, nonaccept_ids):
    """The union rule. results: [(fn, path, doc)] of individual results; sample: sample_component() or None; nonaccept_ids: every lake any individual result
    rejected / set to NEEDS REVIEW. Returns (sorted ids, report)."""
    indiv = set()
    for _, _, d in results:
        indiv |= set(d["acceptedIds"])
    clash = sorted(indiv & set(nonaccept_ids))
    rep = dict(individualAccepted=len(indiv), conflicts=clash)
    out = set(indiv)
    if sample:
        sids, sres, _, _ = sample
        sample_rejected = set(sres.get("rejectedIds") or [])
        rep["sampleRejectedAndIndividuallyAccepted"] = sorted(indiv & sample_rejected)
        excluded = sorted(set(sids) & set(nonaccept_ids))
        rep["sampleExcludedByIndividualDecision"] = excluded
        out |= set(sids) - set(nonaccept_ids)
    return sorted(out), rep


def nonaccepted_all(results, this_info=None):
    ids = set()
    for _, _, d in results:
        ids |= set(d.get("rejectedIds", [])) | set(d.get("needsReviewIds", []))
    if this_info:
        for s in ("sectionA", "sectionB"):
            ids |= set(this_info[s]["rejectedIds"]) | set(this_info[s]["needsReviewIds"])
    return ids


def result_doc(manifest, manifest_path, export_path, info, held):
    a, b = info["sectionA"], info["sectionB"]
    return dict(
        schema=CC.SCHEMA_RESULT, criteriaVersion=CC.CRITERIA_VERSION, reviewKind="individual", packId=manifest["packId"], selectionRule=manifest.get("selectionRule"),
        packManifestSha256=CC.sha256_file(manifest_path), reviewCsvSha256=CC.sha256_file(export_path), reviewer=info["reviewer"], exportedAtUtc=info["exportedAtUtc"],
        note="Individual acceptance: acceptedIds are only lakes Michael decided ACCEPT (Section A, or Section B and in the bindings table). Nothing is extrapolated.",
        sectionA=dict(size=a["size"], accepted=a["accepted"], rejected=a["rejected"], needsReview=a["needsReview"], notDecided=a["notDecided"]),
        sectionB=dict(size=b["size"], accepted=b["accepted"], rejected=b["rejected"], needsReview=b["needsReview"], notDecided=b["notDecided"],
                      acceptedCountableIds=b["acceptedCountableIds"], acceptedForLaterTableInclusionIds=b["acceptedForLaterTableInclusionIds"]),
        acceptedIds=info["acceptedIds"], rejectedIds=sorted(set(a["rejectedIds"]) | set(b["rejectedIds"])), needsReviewIds=sorted(set(a["needsReviewIds"]) | set(b["needsReviewIds"])),
        sectionBRejectedIds=b["rejectedIds"], sectionBNeedsReviewIds=b["needsReviewIds"], notDecidedIds=a["notDecidedIds"] + b["notDecidedIds"],
        heldBackLakes=sorted(held), decisions=info["decisions"],
    )


def build_cumulative_result(data_dir, batches_dir, ids, batch_path, sample, rep, results, held, revoked):
    comps = []
    for fn, p, d in results:
        comps.append(dict(kind="individual", resultFile=f"review_batches/{fn}", resultSha256=CC.sha256_file(p), packId=d["packId"], packManifestSha256=d["packManifestSha256"],
                          reviewCsvSha256=d["reviewCsvSha256"], acceptedIds=d["acceptedIds"], rejectedIds=d["rejectedIds"], needsReviewIds=d["needsReviewIds"]))
    if sample:
        sids, sres, bp, rp = sample
        comps.append(dict(kind="sample", resultFile=f"review_batches/{SAMPLE_RESULT}", resultSha256=CC.sha256_file(rp), batchFile=f"review_batches/{SAMPLE_BATCH}",
                          batchSha256=CC.sha256_file(bp), packId=sres.get("packId"), ids=sids, rejectedIds=sres.get("rejectedIds") or [],
                          excludedByIndividualDecision=rep.get("sampleExcludedByIndividualDecision", [])))
    rejected = sorted(set().union(*[set(d["rejectedIds"]) for _, _, d in results]) if results else set())
    return dict(
        schema="lake-brain-binding-review-result/v2", reviewKind=CC.REVIEW_KIND, criteriaVersion=CC.CRITERIA_VERSION, verdict="ACCEPTED_INDIVIDUALLY",
        rule="cumulative accepted batch = individually accepted lakes UNION (sample accepted batch MINUS lakes individually rejected / marked NEEDS REVIEW); never extrapolated",
        acceptedBatchFile="accepted_batch.json", acceptedBatchCount=len(ids), acceptedBatchSha256=CC.sha256_file(batch_path),
        components=comps, rejectedIds=rejected, heldBackLakes=sorted(held), revokedAcceptIds=sorted(revoked),
        pilotCount=CC.PILOT_COUNT, profiledLakes=CC.PILOT_COUNT + len(ids), coverageThreshold=CC.COVERAGE_THRESHOLD,
    )


def run(args, out=print):
    manifest = load_json(args.manifest, "packet manifest")
    if manifest.get("schema") != CC.SCHEMA_PACK or not str(manifest.get("packId", "")).startswith(CC.PACK_PREFIX):
        raise IngestError("the manifest is not a consolidated packet manifest")
    if list(manifest.get("decisions", [])) != list(CC.DECISIONS):
        raise IngestError("the manifest's decision vocabulary differs from consolidated_common.DECISIONS")
    tdoc = load_json(args.bindings, "bindings table")
    table_ids = {b["lakeId"] for b in tdoc["bindings"]}
    pilots = set(manifest["pilots"]) | {p["lakeId"] for p in tdoc.get("pilotReproduction", [])}
    held = held_lakes.load_snapshot() | set(manifest.get("held", []))
    rows = read_export(args.export)
    problems, info = analyse(rows, manifest, table_ids, pilots, held, allow_partial=args.allow_partial)
    batches_dir = os.path.join(args.data_dir, "review_batches")
    if not re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", args.label) or args.label.startswith("sample"):
        raise IngestError("--label must be lowercase letters/digits/underscores and not start with 'sample'")
    result_fn = f"{args.label}_result.json"
    other = os.path.join(batches_dir, result_fn)
    if os.path.isfile(other) and load_json(other, "existing result").get("packId") != manifest["packId"]:
        raise IngestError(f"{result_fn} already holds the result of a DIFFERENT packet; use another --label so no earlier result is overwritten")
    out(f"packet {manifest['packId']}: {len(rows)} rows in the export")
    if manifest.get("inputs", {}).get("bindingsTableSha256") not in (None, CC.sha256_file(args.bindings)):
        out("WARNING: the bindings table has changed since this packet was built (ids are still checked against the current table)")
    if problems:
        out("REFUSED: the export is not valid for this packet:")
        for p in problems:
            out("  - " + p)
        return 2, info
    a, b = info["sectionA"], info["sectionB"]
    out(f"Section A: {a['accepted']} accepted, {a['rejected']} rejected, {a['needsReview']} needs review, {a['notDecided']} not decided (of {a['size']})")
    out(f"Section B: {b['accepted']} accepted ({len(b['acceptedCountableIds'])} in the bindings table and countable; {len(b['acceptedForLaterTableInclusionIds'])} recorded as "
        f"'accepted for later table inclusion' only), {b['rejected']} rejected, {b['needsReview']} needs review, {b['notDecided']} not decided (of {b['size']})")
    prior = load_individual_results(batches_dir, exclude_pack=manifest["packId"])
    sample = sample_component(args.sample_dir, batches_dir)
    this = (result_fn, None, dict(acceptedIds=info["acceptedIds"], rejectedIds=sorted(set(a["rejectedIds"]) | set(b["rejectedIds"])),
                                                   needsReviewIds=sorted(set(a["needsReviewIds"]) | set(b["needsReviewIds"]))))
    ids, rep = cumulative(prior + [this], sample, nonaccepted_all(prior, info))
    if rep["conflicts"]:
        out("REFUSED: lake(s) accepted in one result and rejected / set to NEEDS REVIEW in another: " + ", ".join(rep["conflicts"]))
        return 2, info
    if rep.get("sampleRejectedAndIndividuallyAccepted"):
        out("REFUSED: lake(s) individually accepted but REJECTED in the sample result (resolve by hand): " + ", ".join(rep["sampleRejectedAndIndividuallyAccepted"]))
        return 2, info
    bpath = os.path.join(args.data_dir, "accepted_batch.json")
    revoked = []
    if os.path.isfile(bpath):
        old = set(load_json(bpath, "existing accepted_batch.json"))
        revoked = sorted(old - set(ids))
        if revoked and not args.allow_revoke:
            out(f"REFUSED: this would remove {len(revoked)} id(s) from the cumulative accepted_batch.json ({revoked[:5]}); the file never loses an id unless --allow-revoke is given")
            return 2, info
    n = len(ids)
    out(f"accepted lakes (cumulative, individually accepted{' + sample' if sample else ''}): {n}" + (f"; sample excluded by an individual decision: {len(rep.get('sampleExcludedByIndividualDecision', []))}" if sample else ""))
    out(f"profiled lakes would be {CC.PILOT_COUNT} + {n} = {CC.PILOT_COUNT + n} (threshold {CC.COVERAGE_THRESHOLD})" + ("  -> threshold reached" if CC.PILOT_COUNT + n >= CC.COVERAGE_THRESHOLD else f"  -> {CC.COVERAGE_THRESHOLD - CC.PILOT_COUNT - n} more needed"))
    if a["acceptedIds"]:
        out("Section A accepted: " + "; ".join(a["acceptedIds"]))
    if not args.write:
        out("DRY RUN: nothing written. Add --write to write the result files.")
        return 0, info
    os.makedirs(batches_dir, exist_ok=True)
    rdoc = result_doc(manifest, args.manifest, args.export, info, held)
    rpath = os.path.join(batches_dir, result_fn)
    with open(rpath, "w") as f:
        json.dump(rdoc, f, indent=1)
    if args.sample_dir and sample:
        shutil.copyfile(sample[2], os.path.join(batches_dir, SAMPLE_BATCH))
        shutil.copyfile(sample[3], os.path.join(batches_dir, SAMPLE_RESULT))
        sample = sample_component(None, batches_dir)
    results = load_individual_results(batches_dir)
    ids2, rep2 = cumulative(results, sample, nonaccepted_all(results))
    assert ids2 == ids, (ids2, ids)
    with open(bpath, "w") as f:
        json.dump(ids2, f, indent=1)
    cdoc = build_cumulative_result(args.data_dir, batches_dir, ids2, bpath, sample, rep2, results, held, revoked)
    cpath = os.path.join(args.data_dir, "binding_review_result.json")
    with open(cpath, "w") as f:
        json.dump(cdoc, f, indent=1)
    out(f"wrote {rpath}")
    out(f"wrote {bpath}")
    out(f"wrote {cpath}")
    return 0, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", required=True, help="the CSV the review form downloaded")
    ap.add_argument("--manifest", required=True, help="pack_manifest.json of the consolidated packet")
    ap.add_argument("--bindings", default=CC.BINDINGS)
    ap.add_argument("--data-dir", default=CC.DATA_DIR, help="where accepted_batch.json, binding_review_result.json and review_batches/ live")
    ap.add_argument("--label", default="consolidated", help="name of this packet's result file: review_batches/<label>_result.json (use another label for another packet)")
    ap.add_argument("--sample-dir", default=None, help="folder with a sample-based accepted_batch.json + binding_review_result.json to union in")
    ap.add_argument("--allow-partial", action="store_true", help="ingest an export whose Section A is not fully decided (only ACCEPT rows count)")
    ap.add_argument("--allow-revoke", action="store_true", help="allow a re-export that drops a previously accepted id from the cumulative batch (recorded)")
    ap.add_argument("--write", action="store_true", help="write the result files (default: dry run)")
    args = ap.parse_args(argv)
    try:
        code, _ = run(args)
    except IngestError as e:
        print("REFUSED:", e)
        code = 2
    return code


if __name__ == "__main__":
    sys.exit(main())
