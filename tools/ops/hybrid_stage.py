#!/usr/bin/env python3
"""Staged hybrid moves for the next Brains (Roadmap Sector_Ops #23 section 2; Sector_Ops #51). Owner tool; changes nothing live.

Each Brain that is to move the way Water Clarity did (hybrid O3 (b): Pulse runs the Brain while it holds the runner lease; the cloud Orchestrator grants,
reconciles and starts the central Publisher) has ONE staged fragment in tools/ops/hybrid-stage/<brainId>.json (`sector-hybrid-stage-v1`). No runtime
reads that folder. A fragment becomes live only when `apply --write` merges it into the three reviewed policies in an owner-approved PR, and that PR
is deployed:

  jobs/brain_platform/sector_brain_platform/runner-policy.json      primary[brain] = pulse, approvals[brain] = the approvalRef
  jobs/brain_platform/sector_brain_platform/watchdog-policy.json    brains[brain] = {holder, lakes, approvalRef}
  jobs/brain-orchestrator/publication-cutover.json                  brains[brain] = {state CENTRAL, approvalRef[, orderReviewRef]}

  python3 tools/ops/hybrid_stage.py show                            # every staged Brain, by readiness, with its blockers
  python3 tools/ops/hybrid_stage.py check                           # each fragment applied in memory passes the real policy loaders
  python3 tools/ops/hybrid_stage.py apply --brain lake-brain --approval-ref REF [--blockers-cleared] [--write]

`apply` without --write prints the diff only. It refuses an empty approvalRef, a Brain already in any of the three policies, and, unless
--blockers-cleared, a fragment that still lists blockers. It never deploys, grants IAM or enables the execution control: those stay owner steps.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
STAGE_DIR = os.path.join(ROOT, "tools", "ops", "hybrid-stage")
PLATFORM = os.path.join(ROOT, "jobs", "brain_platform")
RUNNER_POLICY = os.path.join(PLATFORM, "sector_brain_platform", "runner-policy.json")
WATCHDOG_POLICY = os.path.join(PLATFORM, "sector_brain_platform", "watchdog-policy.json")
CUTOVER = os.path.join(ROOT, "jobs", "brain-orchestrator", "publication-cutover.json")
SCHEMA = "sector-hybrid-stage-v1"
HOLDERS = ("pulse",)

if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)


class StageError(ValueError):
    pass


def load_fragment(path: str) -> dict:
    f = json.load(open(path, encoding="utf-8"))
    if f.get("schema") != SCHEMA:
        raise StageError(f"{os.path.basename(path)}: schema must be {SCHEMA}")
    brain = f.get("brainId")
    if not brain or os.path.basename(path) != f"{brain}.json":
        raise StageError(f"{os.path.basename(path)}: brainId must match the file name")
    if (f.get("runnerPolicy") or {}).get("primary") not in HOLDERS:
        raise StageError(f"{brain}: runnerPolicy.primary must be one of {HOLDERS}")
    wd = f.get("watchdog") or {}
    if wd.get("holder") != f["runnerPolicy"]["primary"]:
        raise StageError(f"{brain}: watchdog.holder must be the runner-policy primary")
    if not wd.get("lakes") or not all(isinstance(x, str) and x for x in wd["lakes"]):
        raise StageError(f"{brain}: watchdog.lakes must name the lakes the Brain may publish")
    if (f.get("cutover") or {}).get("state") != "CENTRAL":
        raise StageError(f"{brain}: cutover.state must be CENTRAL")
    if f.get("leaseObject") != f"exports/runners/leases/{brain}.json" or f.get("artifactPrefix") != f"artifacts/{brain}/":
        raise StageError(f"{brain}: leaseObject/artifactPrefix must be the Brain's own")
    if not isinstance(f.get("blockers"), list):
        raise StageError(f"{brain}: blockers must be a list (empty when cleared)")
    return f


def fragments(stage_dir: str = STAGE_DIR) -> dict[str, dict]:
    out = {}
    for name in sorted(os.listdir(stage_dir)):
        if name.endswith(".json"):
            f = load_fragment(os.path.join(stage_dir, name))
            out[f["brainId"]] = f
    return out


def _read(path):
    return json.load(open(path, encoding="utf-8"))


def merged(frag: dict, approval_ref: str, runner: dict, watchdog: dict, cutover: dict) -> tuple[dict, dict, dict]:
    """The three policies with `frag` merged in (copies; the inputs are not changed)."""
    if not (approval_ref or "").strip():
        raise StageError("an approvalRef is required (the owner's approval of this move)")
    brain = frag["brainId"]
    r, w, c = copy.deepcopy(runner), copy.deepcopy(watchdog), copy.deepcopy(cutover)
    if brain in (r.get("primary") or {}) or brain in (w.get("brains") or {}) or brain in (c.get("brains") or {}):
        raise StageError(f"{brain} is already in a live policy: nothing to apply")
    r.setdefault("primary", {})[brain] = frag["runnerPolicy"]["primary"]
    r.setdefault("approvals", {})[brain] = approval_ref
    w.setdefault("brains", {})[brain] = {"holder": frag["watchdog"]["holder"], "lakes": list(frag["watchdog"]["lakes"]), "approvalRef": approval_ref}
    entry = {"state": "CENTRAL", "approvalRef": approval_ref}
    if frag["cutover"].get("orderReviewRef"):
        entry["orderReviewRef"] = frag["cutover"]["orderReviewRef"]
    c.setdefault("brains", {})[brain] = entry
    return r, w, c


def verify(runner: dict, watchdog: dict, cutover: dict, brain: str) -> list[str]:
    """Problems found by the REAL loaders for the merged policies (empty = they load and the Brain is CENTRAL with Pulse as its primary)."""
    import tempfile
    from sector_brain_platform import cycle_watchdog as WD
    from sector_brain_platform import publication_stage as PS
    from sector_brain_platform import runner_lease as RL
    probs = []
    with tempfile.TemporaryDirectory() as td:
        paths = {}
        for name, doc in (("runner", runner), ("watchdog", watchdog), ("cutover", cutover)):
            paths[name] = os.path.join(td, f"{name}.json")
            json.dump(doc, open(paths[name], "w"))
        try:
            pol = RL.load_policy(paths["runner"])
            if RL.primary(pol, brain) != "pulse":
                probs.append(f"runner-policy: primary for {brain} is {RL.primary(pol, brain)}")
        except Exception as e:                                       # noqa: BLE001
            probs.append(f"runner-policy does not load: {e}")
        try:
            WD.load_policy(paths["watchdog"])
        except Exception as e:                                       # noqa: BLE001
            probs.append(f"watchdog-policy does not load: {e}")
        cut, problems = PS.load_cutover(paths["cutover"])
        for p in problems:
            if p.get("brainId") == brain:
                probs.append(f"cutover: {p['kind']}: {p.get('why', '')}".rstrip(": "))
        if (cut.get(brain) or {}).get("state") != "CENTRAL" and not any(p.get("brainId") == brain for p in problems):
            probs.append(f"cutover: {brain} is not CENTRAL")
    return probs


def _render(doc) -> str:
    return json.dumps(doc, indent=2) + "\n"


def _diff(path, after) -> str:
    rel = os.path.relpath(path, ROOT)
    a = open(path, encoding="utf-8").read().splitlines(keepends=True)            # the file as it is, so the diff is exactly what --write changes
    b = _render(after).splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, f"a/{rel}", f"b/{rel}"))


def _write(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(_render(doc))
    os.replace(tmp, path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sub.add_parser("check")
    p = sub.add_parser("apply")
    p.add_argument("--brain", required=True)
    p.add_argument("--approval-ref", required=True)
    p.add_argument("--blockers-cleared", action="store_true", help="the owner confirms every listed blocker is done")
    p.add_argument("--write", action="store_true", help="write the three policy files (for the owner-approved PR); default: print the diff")
    a = ap.parse_args(argv)
    try:
        frags = fragments()
    except (StageError, OSError, ValueError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    runner, watchdog, cutover = _read(RUNNER_POLICY), _read(WATCHDOG_POLICY), _read(CUTOVER)

    if a.cmd == "show":
        for f in sorted(frags.values(), key=lambda f: f.get("readiness", 99)):
            live = f["brainId"] in (runner.get("primary") or {})
            print(f"{f.get('readiness')}. {f['brainId']}  (Pulse job {f['pulseJob']}; {'LIVE' if live else 'staged'}; {len(f['blockers'])} blockers)")
            for b in f["blockers"]:
                print(f"     - {b}")
        return 0

    if a.cmd == "check":
        bad = 0
        for brain, f in frags.items():
            try:
                probs = verify(*merged(f, "check-only", runner, watchdog, cutover), brain)
            except StageError as e:
                probs = [str(e)]
            order = [x for x in probs if x.startswith("cutover: CUTOVER_ORDER")]
            other = [x for x in probs if x not in order]
            # PL-10: a CENTRAL entry ahead of the recorded order is DROPPED by the Orchestrator until an order review is recorded. That is a known,
            # owner-decided blocker (it is in the fragment's blockers), not a broken fragment.
            print(f"{brain}: {'OK' if not probs else '; '.join(other) if other else 'OK, but needs an order review (orderReviewRef) first: ' + order[0]}")
            bad += bool(other)
        return 1 if bad else 0

    f = frags.get(a.brain)
    if f is None:
        print(f"REFUSED: no staged fragment for {a.brain} (staged: {sorted(frags)})", file=sys.stderr)
        return 2
    if f["blockers"] and not a.blockers_cleared:
        print(f"REFUSED: {a.brain} still lists {len(f['blockers'])} blockers (pass --blockers-cleared once the owner confirms each is done):", file=sys.stderr)
        for b in f["blockers"]:
            print(f"  - {b}", file=sys.stderr)
        return 2
    try:
        r, w, c = merged(f, a.approval_ref, runner, watchdog, cutover)
    except StageError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    probs = verify(r, w, c, a.brain)
    if probs:
        print("REFUSED: the merged policies would not make the move live:", file=sys.stderr)
        for pr in probs:
            print(f"  - {pr}", file=sys.stderr)
        return 2
    for path, after in ((RUNNER_POLICY, r), (WATCHDOG_POLICY, w), (CUTOVER, c)):
        sys.stdout.write(_diff(path, after))
        if a.write:
            _write(path, after)
    print(f"\n{'WROTE' if a.write else 'DIFF ONLY (add --write)'}: {a.brain}. Still owner steps: the PR review, the Orchestrator and Publisher deploys, "
          f"the IAM, and the execution control enabling {a.brain}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
