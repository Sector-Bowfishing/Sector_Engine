#!/usr/bin/env python3
"""Onboard a new Brain into the research system with minimal manual work (owner directive 2026-10-25: a ninth Brain must not cost weeks of infrastructure).

  python3 tools/research/onboard.py add-brain --id <brainId> --dir <brains/ dir> --folder <research folder> --domain "<bowfishing domain in words>"
         [--home <research home>] [--consumes a,b] [--provides x,y]

It creates, from existing structures only (no new framework):
  brains/<dir>/research/GAPS.json     required by Cortex BR-22 (one placeholder gap that points at the charter questions)
  brains/<dir>/research/CHARTER.json  bowfishing charter skeleton: purpose, decisions, predictions, needs/provides, fit-for-purpose targets, priority questions
  tools/research/discovery.json       the Brain's entry: folder, weaknesses, default avenues (literature, dataset search, owner-actions), score metadata NOT_RUN
  <home>/<folder>/...                 the Cortex research layout folders and manifest.json (when --home is given)
Then `campaign.py init/run` already covers the Brain: it reconstructs/reads gaps, writes agent research tasks for gaps no avenue covers, searches registered
sources, tests tiers, packages EVIDENCE_ONLY or candidate knowledge and reports an honest outcome. `integration.contract_gaps` generates the integration check for the
declared dependencies. Everything the script cannot know is marked UNFILLED so a charter that was never completed is visible, not silently accepted.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.abspath(os.path.join(HERE, "..", ".."))
SUBDIRS = ("datasets", "sources", "research", "analysis", "candidates", "closeouts", "validation")
UNFILLED = "UNFILLED"


def _w(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path + ".tmp", "w", encoding="utf-8"), indent=1)
    os.replace(path + ".tmp", path)


def add_brain(engine: str, bid: str, dirname: str, folder: str, domain: str, home: str | None = None, consumes: list | None = None, provides: list | None = None,
              discovery_path: str | None = None) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]+", bid) or not re.fullmatch(r"[a-z][a-z0-9-]+", dirname) or not re.fullmatch(r"[a-z][a-z0-9-]+", folder):
        raise ValueError("id, dir and folder must be lowercase words with hyphens")
    bdir = os.path.join(engine, "brains", dirname)
    if not os.path.exists(os.path.join(bdir, "brain.json")):
        raise ValueError(f"{bdir}/brain.json must exist first: register the Brain with the existing template (brains/_template) before onboarding its research")
    made = []
    prefix = re.sub(r"[^A-Z]", "", bid.upper())
    gp = os.path.join(bdir, "research", "GAPS.json")
    if not os.path.exists(gp):
        _w(gp, {"schemaVersion": 1, "brainId": bid, "gaps": [{"id": f"{prefix}-NEW-001", "type": "validation", "title": f"First scientific gaps of {bid} are not yet defined: answer the charter's priority questions",
                                                              "whyItMatters": domain, "status": "OPEN"}]})
        made.append(os.path.relpath(gp, engine))
    cp = os.path.join(bdir, "research", "CHARTER.json")
    if not os.path.exists(cp):
        _w(cp, {"schema": "sector-bowfishing-charter-v1", "status": "SKELETON_UNFILLED", "note": "Fill every UNFILLED field. Priors about bowfishing are hypotheses until validated.",
                "brainId": bid, "role": UNFILLED, "bowfishingPurpose": domain or UNFILLED, "decisionsInformed": [UNFILLED],
                "predicts": [{"id": UNFILLED, "desc": UNFILLED, "status": "EXPERIMENTAL"}], "mustNotPredict": [UNFILLED],
                "needsFrom": [{"brain": b, "output": UNFILLED, "why": UNFILLED, "requiredFor": UNFILLED} for b in consumes or []],
                "providesTo": [{"brain": b, "output": UNFILLED, "why": UNFILLED} for b in provides or []],
                "fitForPurpose": [{"metric": UNFILLED, "target": None, "direction": "lower", "rationale": UNFILLED}], "priorityQuestions": [f"What do bowfishers need from {bid} that no Brain provides today?"],
                "abstainWhen": [UNFILLED]})
        made.append(os.path.relpath(cp, engine))
    dp = discovery_path or os.path.join(HERE, "discovery.json")
    d = json.load(open(dp, encoding="utf-8"))
    if bid not in d["brains"]:
        terms = [t for t in re.split(r"[^a-z]+", domain.lower()) if len(t) >= 5][:3] or [bid]
        d["brains"][bid] = {"folder": folder, "dir": dirname, "purpose": domain, "weaknesses": [],
                            "scoreMeta": {"rubricId": "none (new Brain: define its capability dimensions in tools/research/bowfishing_capability.py)", "scale": None, "class": "NONE", "source": "NOT_RUN",
                                          "movable": "no rubric exists yet"},
                            "avenues": [{"id": f"{bid}-literature", "run": "connector", "kind": "literature", "iter": 1, "gaps": [f"{prefix}-NEW-001"]},
                                        {"id": f"{bid}-datasets", "run": "experiment", "experiment": "dataset-search", "gaps": [f"{prefix}-NEW-001"], "acquiring": True,
                                         "params": {"queries": [" ".join(terms), f"{terms[0]} reservoir fish habitat data"], "relevance": terms + ["reservoir", "lake", "fish", "dataset"], "minTerms": 2, "perSource": 8, "minLeads": 1}}],
                            "kind": "literature", "domainTerms": terms, "gapsPerIteration": 3, "queryTerms": [6, 3], "rows": 20, "fromYear": 2010, "minLeads": 3}
        _w(dp, d)
        made.append("tools/research/discovery.json (entry)")
    if home:
        root = os.path.join(home, folder)
        for sd in SUBDIRS:
            os.makedirs(os.path.join(root, sd), exist_ok=True)
        mp = os.path.join(root, "manifest.json")
        if not os.path.exists(mp):
            _w(mp, {"brainId": bid, "folder": folder, "owner": bid, "manifestVersion": 1, "items": []})
        made.append(f"{folder}/ (research layout + manifest.json)")
    return {"created": made, "todo": ["complete every UNFILLED field in CHARTER.json (purpose, predictions, needs/provides, fit-for-purpose targets with rationale)",
                                       "replace the placeholder gap in GAPS.json with the Brain's real scientific gaps (or let the first campaign propose them)",
                                       "declare consumed inputs in brain.json `consumes` so the contract check passes",
                                       "add capability extractors for the Brain in tools/research/bowfishing_capability.py once it produces measurable evidence",
                                       f"run: python3 tools/research/campaign.py init --campaign <id> --brains {bid} && ... run"]}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("add-brain",))
    ap.add_argument("--id", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--home")
    ap.add_argument("--consumes", default="")
    ap.add_argument("--provides", default="")
    a = ap.parse_args(argv)
    r = add_brain(ENGINE, a.id, a.dir, a.folder, a.domain, a.home, [x for x in a.consumes.split(",") if x], [x for x in a.provides.split(",") if x])
    print(json.dumps(r, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
