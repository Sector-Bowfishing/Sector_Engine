#!/usr/bin/env python3
"""Migration-safe score baseline (Repository Foundation V1, Phase 1B).

Records, and later verifies, the per-Brain score artifacts that are ACTUALLY PRESENT in this tree
(docs/brains/scoring/frozen-scores.json) plus the SHA-256 of every rubric definition, so an accidental
score change caused by a repo move is detected. It never computes, changes or reinterprets a score and
does not touch the provisional Engine aggregate (CERT-6 stays deferred).

  python3 verification/integration/score_baseline.py --check     # default; exit 1 on drift
  python3 verification/integration/score_baseline.py --update    # re-record (intentional score change only)

Prints paths, brain ids and values only.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCORING_DIR = os.path.join("docs", "brains", "scoring")
FROZEN = os.path.join(SCORING_DIR, "frozen-scores.json")
BASELINE = os.path.join("verification", "fixtures", "scores", "score_baseline.json")
BLOCK_KEYS = ("value", "scale", "basis", "scoreVersion", "scoreUpdatedAt")
COMPUTED_FROM_LIVE_RTDB = ["lake-brain", "biological-state", "sector-intelligence", "engine (provisional aggregate, CERT-6 deferred)"]


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def canonical_hash(obj):
    return sha256_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())


def snapshot(root=ROOT):
    with open(os.path.join(root, FROZEN), "rb") as fh:
        raw = fh.read()
    frozen = json.loads(raw)
    scores = {}
    for brain_id, block in sorted(frozen.items()):
        if not isinstance(block, dict):
            continue
        entry = {k: block.get(k) for k in BLOCK_KEYS}
        entry["scoreType"] = "ENGINE_READINESS_SCORE"   # concept label assigned by this baseline; the artifact does not carry it
        entry["sourceArtifact"] = FROZEN.replace(os.sep, "/")
        entry["blockSha256"] = canonical_hash(block)
        scores[brain_id] = entry
    rubrics = {}
    for name in sorted(os.listdir(os.path.join(root, SCORING_DIR))):
        if name.endswith(".json") and name != "frozen-scores.json" and name != "score-artifact-sources.json":
            with open(os.path.join(root, SCORING_DIR, name), "rb") as fh:
                rubrics[f"{SCORING_DIR.replace(os.sep, '/')}/{name}"] = sha256_bytes(fh.read())
    return {
        "schemaVersion": "1.0.0",
        "purpose": "Detect accidental score changes caused by repository moves. Not a score, not a certification; never edited to 'fix' a score.",
        "frozenScoresFileSha256": sha256_bytes(raw),
        "scores": scores,
        "rubricSha256": rubrics,
        "notBaselinableOffline": COMPUTED_FROM_LIVE_RTDB,
        "caveats": [
            "Values are recorded verbatim from the artifact; nothing here is a readiness claim or a recomputation.",
            "water-clarity value reflects a research certification of an undeployed candidate (see the artifact's appliesTo/scoreBlockers); it is not reinterpreted.",
            "Research candidate scores elsewhere are out of scope and are not official readiness.",
        ],
    }


def diff(expected, actual):
    msgs = []
    for brain in sorted(set(expected["scores"]) | set(actual["scores"])):
        e, a = expected["scores"].get(brain), actual["scores"].get(brain)
        if e is None:
            msgs.append(f"score block added for {brain!r}")
        elif a is None:
            msgs.append(f"score block removed for {brain!r}")
        elif e != a:
            changed = [k for k in e if e[k] != a.get(k)]
            msgs.append(f"{brain!r} changed in {changed}: " + ", ".join(f"{k}: {e[k]!r} -> {a.get(k)!r}" for k in changed if k != "blockSha256"))
    for path in sorted(set(expected["rubricSha256"]) | set(actual["rubricSha256"])):
        if expected["rubricSha256"].get(path) != actual["rubricSha256"].get(path):
            msgs.append(f"rubric changed/added/removed: {path}")
    return msgs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    actual = snapshot(args.root)
    path = os.path.join(args.root, BASELINE)
    if args.update:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(actual, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"score baseline written: {sorted(actual['scores'])} -> {BASELINE}")
        return 0
    with open(path, encoding="utf-8") as fh:
        expected = json.load(fh)
    msgs = diff(expected, actual)
    for m in msgs:
        print("SCORE BASELINE DRIFT:", m)
    if msgs:
        print("If the change is intentional (an approved score update), re-record with --update in the same commit and say why.")
        return 1
    print("score baseline OK:", ", ".join(f"{b}={v['value']}/{v['scale']}" for b, v in sorted(actual["scores"].items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
