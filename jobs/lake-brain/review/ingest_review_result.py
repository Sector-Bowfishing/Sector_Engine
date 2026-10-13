#!/usr/bin/env python3
"""Ingest Michael's binding-review result (the CSV exported by binding_review_sample.html) and apply the acceptance rule.

Reads the review CSV, validates every lake id against the review pack, counts reviewed / rejected rows, computes the exact one-sided
95 % binomial upper bound on the error rate and applies the pre-registered rule: accept the batch when there is at most 1 error in the
full sample (n = 60, upper bound <= 7.7 %), every sample row is decided (no Unsure, no pending) and the pack matches.
Stratum rule: any stratum (provider x capability class) that contains a rejected row is flagged for FULL review and none of its rows
enter the proposed accepted batch.

Dry run by default. With --write it writes
    jobs/lake-brain/data/binding_review_result.json   the full result (always)
    jobs/lake-brain/data/accepted_batch.json          JSON list of lake ids eligible to become REVIEWED ([] unless the rule is met)
Every id must also be a lake of jobs/lake-brain/data/bindings.proposed.v1.json (--bindings), otherwise the run is refused.
It never marks anything REVIEWED itself, and the accepted batch never contains held-back coordinate-flagged lakes, the wave-1 flagged
rows or post-hoc rows (only rows of the strict eligible population that are in a stratum without rejects).

The optional --flagged-csv ingests the export of binding_review_flagged57.html (full review of the 57 flagged rows): counts only;
accepted flagged rows are listed in the result but are never part of accepted_batch.json.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from review_stats import upper_bound  # noqa: E402
import held_lakes  # noqa: E402

DEFAULT_PACK = "/Users/mcather/Desktop/Sector Handoffs/Sector Engine/Lake Brain Binding Review"
DEFAULT_OUT = os.path.normpath(os.path.join(HERE, "..", "data"))
DEFAULT_BINDINGS = os.path.join(DEFAULT_OUT, "bindings.proposed.v1.json")
DECISIONS = {"ACCEPT", "REJECT", "UNSURE", "PENDING"}
REQUIRED_COLUMNS = {"pack_id", "lake_id", "decision"}
MAX_ERRORS_DEFAULT = 1
CONFIDENCE = 0.95


class IngestError(Exception):
    pass


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def load_pack(pack_dir):
    paths = dict(
        manifest=os.path.join(pack_dir, "pack_manifest.json"),
        sample=os.path.join(pack_dir, "binding_review_sample.csv"),
        population=os.path.join(pack_dir, "strict_population.csv"),
        held=os.path.join(pack_dir, "held_back_coordinate_flags.csv"),
        flagged=os.path.join(pack_dir, "binding_review_flagged57.csv"),
        held_series=os.path.join(pack_dir, "held_back_series_mismatch.csv"),
    )
    for k, p in paths.items():
        if k != "held_series" and not os.path.exists(p):
            raise IngestError(f"pack file missing: {p}")
    manifest = json.load(open(paths["manifest"]))
    sample = read_csv(paths["sample"])
    population = read_csv(paths["population"])
    held = {r["lake_id"] for r in read_csv(paths["held"])}
    if os.path.exists(paths["held_series"]):          # series/datum-mismatch holds (older packs do not have this file)
        held |= {r["lake_id"] for r in read_csv(paths["held_series"])}
    held |= held_lakes.load_snapshot()                # repository copy of the hold lists: a held lake can never enter the batch
    flagged = {r["lake_id"] for r in read_csv(paths["flagged"])}
    stratum_of = {r["lake_id"]: r["stratum"] for r in population}
    in_sample = {r["lake_id"] for r in population if r["in_sample"] == "yes"}
    sample_ids = {r["lake_id"] for r in sample}
    if sample_ids & held:
        raise IngestError("pack inconsistent: held-back lakes appear in the sample: " + ", ".join(sorted(sample_ids & held)))
    if in_sample != sample_ids:
        raise IngestError("pack inconsistent: strict_population.csv in_sample column differs from binding_review_sample.csv")
    return dict(manifest=manifest, sample_ids=sample_ids, population=population, stratum_of=stratum_of, held=held, flagged=flagged,
                sample_rows=sample)


def load_bindings_ids(path):
    """Lake ids of the generated bindings table (bindings.proposed.v1.json). Only these lakes can ever be accepted."""
    if not os.path.exists(path):
        raise IngestError(f"bindings table missing: {path} (pass --bindings)")
    d = json.load(open(path))
    rows = d["bindings"] if isinstance(d, dict) else d
    return {(b["lakeId"] if isinstance(b, dict) else b) for b in rows}


def validate_rows(rows, pack_id, valid_ids, label):
    """Return (decisions: id -> (decision, notes, reviewer, decided_at), errors list)."""
    errors = []
    if not rows:
        return {}, [f"{label}: the file has no data rows"]
    missing = REQUIRED_COLUMNS - set(rows[0].keys())
    if missing:
        return {}, [f"{label}: missing column(s) {sorted(missing)}"]
    out = {}
    for i, r in enumerate(rows, start=2):
        lid = (r.get("lake_id") or "").strip()
        pid = (r.get("pack_id") or "").strip()
        d = (r.get("decision") or "").strip().upper()
        if pid != pack_id:
            errors.append(f"{label} line {i}: pack_id '{pid}' does not match this pack ('{pack_id}'); the export belongs to a different pack")
        if lid not in valid_ids:
            errors.append(f"{label} line {i}: lake id '{lid}' is not part of this pack")
            continue
        if lid in out:
            errors.append(f"{label} line {i}: duplicate lake id '{lid}'")
            continue
        if d not in DECISIONS:
            errors.append(f"{label} line {i}: decision '{r.get('decision')}' is not one of {sorted(DECISIONS)}")
            continue
        out[lid] = dict(decision=d, notes=(r.get("notes") or "").strip(), reviewer=(r.get("reviewer") or "").strip(), decided_at=(r.get("decided_at_utc") or "").strip())
    return out, sorted(set(errors))


def evaluate(pack, decisions, max_errors=MAX_ERRORS_DEFAULT):
    sample_ids = pack["sample_ids"]
    n_total = len(sample_ids)
    dec = {lid: decisions.get(lid, dict(decision="PENDING"))["decision"] for lid in sample_ids}
    accepted = sorted(l for l, d in dec.items() if d == "ACCEPT")
    rejected = sorted(l for l, d in dec.items() if d == "REJECT")
    unsure = sorted(l for l, d in dec.items() if d == "UNSURE")
    pending = sorted(l for l, d in dec.items() if d == "PENDING")
    reviewed = len(accepted) + len(rejected)
    k = len(rejected)
    ub = upper_bound(reviewed, k, CONFIDENCE)
    complete = reviewed == n_total and not unsure and not pending
    rule_met = complete and k <= max_errors
    strata = {}
    for lid in sample_ids:
        s = pack["stratum_of"][lid]
        e = strata.setdefault(s, dict(stratum=s, eligible=0, sampled=0, accepted=0, rejected=0, unsure=0, pending=0))
        e["sampled"] += 1
        e[{"ACCEPT": "accepted", "REJECT": "rejected", "UNSURE": "unsure", "PENDING": "pending"}[dec[lid]]] += 1
    for lid, s in pack["stratum_of"].items():
        strata.setdefault(s, dict(stratum=s, eligible=0, sampled=0, accepted=0, rejected=0, unsure=0, pending=0))["eligible"] += 1
    full_review = sorted(s for s, e in strata.items() if e["rejected"] > 0)
    for s, e in strata.items():
        e["fullReviewRequired"] = e["rejected"] > 0
    if k > max_errors:
        verdict = "REJECT_BATCH"
        reason = f"{k} rejected rows exceeds the allowed {max_errors}; review the affected strata in full"
    elif not complete:
        verdict = "INCOMPLETE"
        reason = f"{reviewed} of {n_total} reviewed; {len(unsure)} unsure, {len(pending)} not looked at"
    else:
        verdict = "ACCEPT_BATCH"
        reason = f"{k} rejected of {n_total} reviewed (<= {max_errors}); upper bound {100 * ub:.1f}%"
    return dict(n_total=n_total, accepted=accepted, rejected=rejected, unsure=unsure, pending=pending, reviewed=reviewed, k=k, ub=ub,
                complete=complete, rule_met=rule_met, strata=strata, full_review=full_review, verdict=verdict, reason=reason, max_errors=max_errors)


def proposed_batch(pack, ev):
    """Lake ids eligible to become REVIEWED. Empty unless the rule is met. Excludes held-back lakes (coordinate flags, series mismatches, provider terms), the flagged-57, rejected rows and every
    row of a stratum that contains a reject."""
    if not ev["rule_met"]:
        return []
    bad_strata = set(ev["full_review"])
    out = []
    for lid, s in pack["stratum_of"].items():
        if s in bad_strata or lid in pack["held"] or lid in pack["flagged"] or lid in ev["rejected"]:
            continue
        out.append(lid)
    return sorted(out)


def summarize_flagged(rows_by_id, flagged_ids):
    c = {"ACCEPT": [], "REJECT": [], "UNSURE": [], "PENDING": []}
    for lid in sorted(flagged_ids):
        c[rows_by_id.get(lid, dict(decision="PENDING"))["decision"]].append(lid)
    return dict(total=len(flagged_ids), accepted=len(c["ACCEPT"]), rejected=len(c["REJECT"]), unsure=len(c["UNSURE"]), pending=len(c["PENDING"]),
                acceptedIds=c["ACCEPT"], rejectedIds=c["REJECT"], unsureIds=c["UNSURE"], pendingIds=c["PENDING"],
                complete=(len(c["UNSURE"]) + len(c["PENDING"]) == 0),
                note="Full review of the wave-1 flagged rows. Accepted flagged rows are NOT part of accepted_batch.json (they are outside the sampled strict population); adopting them is a separate decision.")


def build_result(pack, ev, batch, review_csv, decisions, flagged_summary, now):
    m = pack["manifest"]
    reviewers = sorted({d["reviewer"] for d in decisions.values() if d["reviewer"]})
    return dict(
        criteriaVersion=m.get("criteria", "binding-review-v1"),
        generatedAtUtc=now,
        packId=m.get("samplePackId"), seed=m.get("seed"), snapshotDate=m.get("snapshotDate"),
        reviewCsvSha256=sha256_file(review_csv), reviewers=reviewers,
        sampleSize=ev["n_total"], reviewed=ev["reviewed"], accepted=len(ev["accepted"]), rejected=len(ev["rejected"]), unsure=len(ev["unsure"]), pending=len(ev["pending"]),
        errorRateUpperBound95=ev["ub"], errorRateUpperBound95Percent=(None if ev["ub"] is None else round(100 * ev["ub"], 2)),
        acceptRule=dict(maxErrors=ev["max_errors"], sampleSize=ev["n_total"], confidence=CONFIDENCE, text=f"Accept the batch when there are at most {ev['max_errors']} error(s) in the full sample of {ev['n_total']}, with every row decided."),
        ruleMet=ev["rule_met"], verdict=ev["verdict"], reason=ev["reason"], rejectedIds=ev["rejected"], unsureIds=ev["unsure"], pendingIds=ev["pending"],
        strata=[ev["strata"][s] for s in sorted(ev["strata"])], fullReviewStrata=ev["full_review"],
        acceptedBatchCount=len(batch), acceptedBatchFile="accepted_batch.json",
        heldBackLakes=sorted(pack["held"]), flagged57=flagged_summary,
        notes=["This script does not mark any binding REVIEWED; accepted_batch.json is a proposal for the adoption work.",
               "Binding review is not complete until the flagged-57 review is also done and the held-back lakes (coordinate flags, series/datum mismatches) are resolved."],
    )


def run(args):
    pack = load_pack(args.pack_dir)
    pack_id = pack["manifest"]["samplePackId"]
    rows = read_csv(args.review_csv)
    decisions, errors = validate_rows(rows, pack_id, pack["sample_ids"], "review csv")
    flagged_summary = None
    if args.flagged_csv:
        frows = read_csv(args.flagged_csv)
        fdec, ferr = validate_rows(frows, pack["manifest"]["flaggedPackId"], pack["flagged"], "flagged csv")
        errors += ferr
        flagged_summary = summarize_flagged(fdec, pack["flagged"])
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        return 2, None
    max_errors = int((pack["manifest"].get("acceptRule") or {}).get("maxErrors", MAX_ERRORS_DEFAULT))
    ev = evaluate(pack, decisions, max_errors)
    batch = proposed_batch(pack, ev)
    allowed = load_bindings_ids(args.bindings)
    not_allowed = sorted(set(batch) - allowed)
    if not_allowed:
        print(f"ERROR: refusing: {len(not_allowed)} proposed accepted id(s) are not in {args.bindings}: " + ", ".join(not_allowed[:10]) + (" ..." if len(not_allowed) > 10 else ""), file=sys.stderr)
        return 2, None
    assert not (set(batch) & (pack["held"] | pack["flagged"])), "held/flagged ids must never be in the batch"
    now = args.now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = build_result(pack, ev, batch, args.review_csv, decisions, flagged_summary, now)
    ub = result["errorRateUpperBound95Percent"]
    print(f"pack {pack_id}: {ev['reviewed']} of {ev['n_total']} reviewed, {ev['k']} rejected, {len(ev['unsure'])} unsure, {len(ev['pending'])} pending")
    print(f"exact one-sided 95% upper bound on the error rate: {'n/a' if ub is None else f'{ub:.1f}%'}")
    print(f"verdict: {ev['verdict']} - {ev['reason']}")
    if ev["full_review"]:
        print("strata needing FULL review:", "; ".join(ev["full_review"]))
    print(f"proposed accepted batch: {len(batch)} lake ids")
    if flagged_summary:
        print(f"flagged-57: {flagged_summary['accepted']} accepted, {flagged_summary['rejected']} rejected, {flagged_summary['unsure']} unsure, {flagged_summary['pending']} pending")
    if args.write:
        os.makedirs(args.out_dir, exist_ok=True)
        rp, bp = os.path.join(args.out_dir, "binding_review_result.json"), os.path.join(args.out_dir, "accepted_batch.json")
        json.dump(result, open(rp, "w"), indent=1)
        json.dump(batch, open(bp, "w"), indent=1)
        print("wrote", rp)
        print("wrote", bp)
    else:
        print("(dry run: nothing written; add --write to write binding_review_result.json and accepted_batch.json)")
    return 0, result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-csv", required=True, help="CSV exported by binding_review_sample.html")
    ap.add_argument("--flagged-csv", help="CSV exported by binding_review_flagged57.html (optional)")
    ap.add_argument("--pack-dir", default=DEFAULT_PACK, help="the review pack directory (pack_manifest.json, strict_population.csv, ...)")
    ap.add_argument("--out-dir", default=DEFAULT_OUT, help="where --write puts binding_review_result.json and accepted_batch.json")
    ap.add_argument("--bindings", default=DEFAULT_BINDINGS, help="generated bindings table; an accepted id must be one of its lakes")
    ap.add_argument("--write", action="store_true", help="write the result and the proposed batch (default: dry run)")
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
