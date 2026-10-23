#!/usr/bin/env python3
"""Gap ledger and progress model of the research coordinator (owner directive 2026-10-23: Sector Brains are BOWFISHING INTELLIGENCE systems;
a run that downloads evidence and completes its stages but improves nothing is NOT a successful improvement campaign). Stdlib only.

Execution success, acquisition, data quality, literature leads, scientific support, a candidate change and an independently validated
improvement are different things (TIERS, lowest to highest). Only INDEPENDENTLY_VALIDATED, with a measured improvement on the Brain's own
capability metric, is progress; everything below it is evidence. The ledger (<folder>/research/gap-ledger.json in the research home) is
persistent across campaigns:
  gaps     id -> status (OPEN, INVESTIGATING, PARTIAL, BLOCKED_EXTERNAL, BLOCKED_APPROVAL, EXHAUSTED, RESOLVED_PENDING_APPROVAL), best tier,
           findings that touched it, blockers with the exact next evidence source
  avenues  stable key -> what was tried (never repeated: identical queries / parameters are not run twice), outcome, new evidence
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

TIERS = ("ACQUIRED", "QUALITY_CHECKED", "EVIDENCE_LEAD", "SCIENTIFIC_SUPPORT", "CANDIDATE_CHANGE", "INDEPENDENTLY_VALIDATED")
RANK = {t: i for i, t in enumerate(TIERS)}
ACTIONABLE = ("OPEN", "INVESTIGATING", "PARTIAL")
TERMINAL = ("BLOCKED_EXTERNAL", "BLOCKED_APPROVAL", "EXHAUSTED", "RESOLVED_PENDING_APPROVAL")
OUTCOMES = ("IMPROVED", "STALLED", "BLOCKED", "BUDGET_REACHED")
CHANGE_FIELDS = ("scientificChange", "previous", "proposed", "evidenceSummary", "validationMethod", "validationResults", "practicalEffect",
                 "scoreImpact", "limitations")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rank(tier: str | None) -> int:
    return RANK.get(tier or "", -1)


def avenue_key(avenue: dict, targets=None) -> str:
    """Stable identity of a research avenue: same avenue + same parameters (+ same targets) = same key = never run twice."""
    body = json.dumps({k: avenue.get(k) for k in ("id", "run", "kind", "experiment", "iter", "params")}, sort_keys=True, default=str)
    if targets:
        body += "|" + ",".join(sorted(map(str, targets)))
    return avenue["id"] + ":" + hashlib.sha256(body.encode()).hexdigest()[:12]


class Ledger:
    def __init__(self, path: str, brain: str):
        self.path, self.brain = path, brain
        if os.path.exists(path):
            self.doc = json.load(open(path, encoding="utf-8"))
        else:
            self.doc = {"schema": "sector-gap-ledger-v1", "brainId": brain, "gaps": {}, "avenues": {}, "evidence": []}

    # ---- gaps
    def sync(self, gaps: list[dict]) -> None:
        """Known gaps (Engine GAPS.json / generated / discovered weaknesses) enter the ledger as OPEN; existing statuses are kept."""
        for g in gaps:
            cur = self.doc["gaps"].setdefault(g["id"], {"status": "OPEN", "bestTier": None, "findings": [], "blockers": [], "title": g.get("title"), "firstSeen": now_iso()})
            cur["title"] = g.get("title") or cur.get("title")

    def status(self, gid: str) -> str:
        return (self.doc["gaps"].get(gid) or {}).get("status", "OPEN")

    def actionable(self) -> list[str]:
        return [g for g, v in self.doc["gaps"].items() if v["status"] in ACTIONABLE]

    def block(self, gid: str, kind: str, reason: str, next_source: str, campaign: str) -> None:
        g = self.doc["gaps"].setdefault(gid, {"status": "OPEN", "bestTier": None, "findings": [], "blockers": [], "title": gid, "firstSeen": now_iso()})
        if not any(b["reason"] == reason for b in g["blockers"]):
            g["blockers"].append({"kind": kind, "reason": reason, "nextEvidenceSource": next_source, "campaign": campaign, "at": now_iso()})
        if g["status"] not in ("RESOLVED_PENDING_APPROVAL",):
            g["status"] = "BLOCKED_APPROVAL" if kind == "approval" else "BLOCKED_EXTERNAL"

    def touch(self, gids: list[str], tier: str, finding_id: str, resolves: bool, improved: bool) -> None:
        """A validated finding touched these gaps at `tier`. Only an independently validated, measured improvement that explicitly
        `resolves` a gap moves it to RESOLVED_PENDING_APPROVAL (candidate only: authoritative scores change through approval)."""
        for gid in gids:
            g = self.doc["gaps"].get(gid)
            if g is None:
                continue
            if rank(tier) > rank(g["bestTier"]):
                g["bestTier"] = tier
            if finding_id not in g["findings"]:
                g["findings"].append(finding_id)
            if g["status"] == "RESOLVED_PENDING_APPROVAL" or g["status"].startswith("BLOCKED"):
                continue                                       # a blocker stays until its external/approval condition is met
            if resolves and improved and tier == "INDEPENDENTLY_VALIDATED":
                g["status"] = "RESOLVED_PENDING_APPROVAL"
            elif rank(tier) >= rank("SCIENTIFIC_SUPPORT"):
                g["status"] = "PARTIAL"
            elif g["status"] == "OPEN":
                g["status"] = "INVESTIGATING"

    def exhaust(self, gid: str, reason: str) -> None:
        g = self.doc["gaps"].get(gid)
        if g and g["status"] in ACTIONABLE:
            g["status"], g["exhaustedReason"] = "EXHAUSTED", reason

    # ---- avenues
    def tried(self, key: str, campaign: str | None = None) -> bool:
        """Within one campaign an avenue (same parameters) never runs twice. A later campaign may re-run it: sources change, and the stall
        rule stops the repetition if nothing new arrives."""
        a = self.doc["avenues"].get(key)
        return a is not None and (campaign is None or a["campaign"] == campaign)

    def reopen_exhausted(self) -> None:
        for g in self.doc["gaps"].values():
            if g["status"] == "EXHAUSTED":
                g["status"] = "INVESTIGATING"

    def seen_findings(self, ids: list[str]) -> int:
        """Validated finding ids never validated before in this Brain's ledger (analysis-only avenues make progress through findings, not downloads)."""
        known = set(self.doc.setdefault("findingsSeen", []))
        new = [i for i in ids if i not in known]
        self.doc["findingsSeen"] = sorted(known | set(ids))
        return len(new)

    def record(self, key: str, avenue: dict, campaign: str, outcome: str, best_tier: str | None, new_evidence: int, note: str = "", new_findings: int = 0, result_hash: str = "") -> None:
        prev = self.doc["avenues"].get(key)
        changed = (prev is None and result_hash != "") or (prev is not None and prev.get("resultHash") != result_hash)   # a different result is new information
        self.doc["avenues"][key] = {"id": avenue["id"], "run": avenue.get("run"), "gaps": avenue.get("gaps") or [], "campaign": campaign, "at": now_iso(),
                                    "outcome": outcome, "bestTier": best_tier, "newEvidence": new_evidence, "newFindings": new_findings, "changed": changed, "resultHash": result_hash, "note": note[:300]}

    def seen_evidence(self, shas: list[str]) -> int:
        """Number of evidence hashes never recorded before (unchanged re-downloads count as zero progress)."""
        known = set(self.doc["evidence"])
        new = [s for s in shas if s not in known]
        self.doc["evidence"] = sorted(known | set(shas))
        return len(new)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        json.dump(self.doc, open(tmp, "w", encoding="utf-8"), indent=1, sort_keys=True)
        os.replace(tmp, self.path)


def next_avenue(avenues: list[dict], ledger: Ledger, last_weak: list, improved_ladders: set, campaign: str | None = None) -> tuple[dict, list | None] | None:
    """The next untried avenue for a still-actionable gap, in configured priority order; None when nothing actionable and affordable remains."""
    open_gaps = set(ledger.actionable())
    for av in avenues:
        targets = last_weak if av.get("when") == "weak" else None
        if av.get("when") == "weak" and not last_weak:
            continue
        if ledger.tried(avenue_key(av, targets), campaign):
            continue
        if av.get("gaps") and not (set(av["gaps"]) & open_gaps):
            continue                                           # every gap it serves is resolved, blocked or exhausted
        if any(not any(k.startswith(r + ":") and (campaign is None or v["campaign"] == campaign) for k, v in ledger.doc["avenues"].items()) for r in av.get("requires") or []):
            continue
        if av.get("ladder") and av["ladder"] in improved_ladders:
            continue                                           # a rung of this hypothesis ladder already produced a measured improvement
        return av, targets
    return None
