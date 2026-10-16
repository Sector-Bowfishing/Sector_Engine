#!/usr/bin/env python3
"""Stale-score guard: a generated Brain score block baked into the orchestrator lineage must never be OLDER than the one the Brain's own scorer last produced.

The failure this prevents (Wind, 2026-10-13): the Wind scorer legitimately moved 3.1 -> 3.3 and committed the generated block on its branch, but the deployed
orchestrator image still contained the old frozen-scores.json, so the hourly `score_brains.py --write --if-changed` kept restoring 3.1.

  python3 check_score_artifacts.py [--sources docs/brains/scoring/score-artifact-sources.json] [--frozen docs/brains/scoring/frozen-scores.json]

Deterministic and local: it reads this tree's frozen-scores.json and `git show <ref>:<path>` of each listed source ref (already-fetched refs; no network).
Exit 1 when any source holds a NEWER block whose content differs; 0 otherwise (a missing ref is a WARNING, not a pass: it prints what could not be checked)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CONTENT_KEYS = ("value", "scoreVersion", "uncapped", "basis")


def compare(local: dict | None, candidate: dict | None) -> tuple[str, str]:
    """-> (verdict, reason); verdict in OK | STALE | AHEAD | MISSING."""
    if candidate is None:
        return "MISSING", "no candidate block"
    if local is None:
        return "STALE", "the lineage has no block for this Brain but the Brain's branch does"
    lt, ct = local.get("scoreUpdatedAt") or "", candidate.get("scoreUpdatedAt") or ""
    diff = [k for k in CONTENT_KEYS if local.get(k) != candidate.get(k)]
    if ct > lt and diff:
        return "STALE", f"candidate generated {ct} is newer than the baked {lt or '(none)'} and differs in {diff}: baked {[local.get(k) for k in diff]} vs candidate {[candidate.get(k) for k in diff]}"
    if ct > lt:
        return "OK", f"candidate is newer ({ct}) but identical in value/version/uncapped/basis"
    if ct < lt and diff:
        return "AHEAD", f"the baked block ({lt}) is NEWER than the Brain branch's ({ct}) and differs in {diff}: confirm the Brain branch was not regenerated elsewhere"
    return "OK", "identical or equally recent"


def git_show(ref: str, path: str, cwd: str) -> dict | None:
    r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def run(sources_path: str, frozen_path: str, cwd: str) -> int:
    srcs = json.load(open(sources_path))["sources"]
    frozen = json.load(open(frozen_path))
    bad = 0
    for s in srcs:
        cand_doc = git_show(s["ref"], s["path"], cwd)
        cand = None if cand_doc is None else cand_doc.get(s["key"])
        verdict, why = compare(frozen.get(s["key"]), cand)
        if cand_doc is None:
            verdict, why = "MISSING", f"cannot read {s['ref']}:{s['path']} (fetch the ref first); NOT CHECKED"
        print(f"{s['brain']:10s} {verdict:8s} {why}")
        bad += verdict == "STALE"
    if bad:
        print(f"\n{bad} stale generated score artifact(s): regenerate on the Brain's branch (see its 'generator'), carry ONLY the generated block into this lineage "
              f"(git show <ref>:<path>), re-run the tests, then deploy. Override only with a recorded decision: ALLOW_STALE_SCORES=1.", file=sys.stderr)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=os.path.join(ROOT, "docs", "brains", "scoring", "score-artifact-sources.json"))
    ap.add_argument("--frozen", default=os.path.join(ROOT, "docs", "brains", "scoring", "frozen-scores.json"))
    a = ap.parse_args()
    return run(a.sources, a.frozen, ROOT)


if __name__ == "__main__":
    sys.exit(main())
