"""Safe score publication (docs/brains/platform/SCORING_SEMANTICS.md section 6, SCORE_DURABILITY in the platform docs).

The durable canonical score store is ALREADY the Brain RTDB node /scores/{brainId}. A score artifact baked into an image (frozen-scores.json)
is therefore only a PROPOSAL: the publisher accepts it only when it is not older than what is already published. This removes the dependence on
whichever frozen file happens to be in a specialist worktree or deployment image, with no new infrastructure.

Verdicts for one Brain:
  NEW       nothing published yet                         -> write
  SAME      content equal (timestamps ignored)            -> no write
  ADVANCE   candidate is newer and differs                -> write
  STALE     candidate is OLDER than the published block   -> HOLD (keep published)
  CONFLICT  same timestamp, different content             -> HOLD (needs a human)
  UNDATED   candidate has no scoreUpdatedAt, published does -> HOLD (age cannot be proven)
An explicit, recorded override (`allow`) lets a named Brain regress; the override is reported, never silent.

ATTACHED sub-blocks (Wind `measurements`, Fish `capability`) are added by the scorer AFTER the guard, from its own gated evaluation; they are
never part of the proposal. The guard therefore judges the proposal without them (otherwise every re-run of an unchanged certification reads
as CONFLICT against its own published block, seen 2026-10-19 on /scores/wind), and on SAME carries the published ones forward so a run whose
attachment is HELD keeps what is published instead of deleting it. Whether an attachment changed is decided by plan_writes, not here.
"""
from __future__ import annotations

from .timeutil import parse_time

NON_CONTENT = ("scoreUpdatedAt", "updatedAt", "explanation")   # explanation: derived from the block (score_explanation.py), never content
HOLD = ("STALE", "CONFLICT", "UNDATED")
ATTACHED = ("measurements", "capability")   # attached after the guard (score_brains.attach_wind_measurements, fish_capability.attach_capability)


def score_content(score: dict | None) -> dict:
    """A score block without refresh timestamps. RTDB drops empty objects/arrays on write, so None/{}/[] count as absent."""
    return {k: v for k, v in (score or {}).items() if k not in NON_CONTENT and v not in (None, {}, [])}


def proposal_content(score: dict | None) -> dict:
    """What the guard judges: the score content without the sub-blocks the scorer attaches after the guard."""
    return {k: v for k, v in score_content(score).items() if k not in ATTACHED}


def judge(candidate: dict | None, published: dict | None) -> dict:
    if candidate is None:
        return {"verdict": "SAME", "why": "no candidate"}
    if not published:
        return {"verdict": "NEW", "why": "nothing published"}
    if proposal_content(candidate) == proposal_content(published):
        return {"verdict": "SAME", "why": "content unchanged"}
    ct, pt = parse_time(candidate.get("scoreUpdatedAt")), parse_time(published.get("scoreUpdatedAt"))
    if pt is None:
        return {"verdict": "ADVANCE", "why": "published block carries no timestamp"}
    if ct is None:
        return {"verdict": "UNDATED", "why": "candidate has no scoreUpdatedAt; cannot prove it is newer than " + str(published.get("scoreUpdatedAt"))}
    if ct < pt:
        return {"verdict": "STALE", "why": f"candidate {candidate.get('scoreUpdatedAt')} is older than published {published.get('scoreUpdatedAt')}"}
    if ct == pt:
        return {"verdict": "CONFLICT", "why": f"same scoreUpdatedAt {candidate.get('scoreUpdatedAt')} but different content"}
    return {"verdict": "ADVANCE", "why": f"candidate {candidate.get('scoreUpdatedAt')} newer than published {published.get('scoreUpdatedAt')}"}


def apply_guard(candidates: dict[str, dict], published: dict[str, dict] | None, allow=()) -> tuple[dict, list[dict]]:
    """-> (effective scores, held). A held Brain keeps its PUBLISHED block in `effective`, so everything computed from the set (the Engine
    score, the control overview) is consistent with what is canonical, and one Brain's stale artifact can never move another's number."""
    published = published or {}
    effective, held = {}, []
    for bid, cand in candidates.items():
        v = judge(cand, published.get(bid))
        if v["verdict"] in HOLD and bid not in set(allow):
            held.append({"brainId": bid, **v, "publishedValue": (published.get(bid) or {}).get("value"), "candidateValue": (cand or {}).get("value")})
            effective[bid] = published[bid]
        else:
            if v["verdict"] in HOLD:
                held.append({"brainId": bid, **v, "overridden": True, "publishedValue": (published.get(bid) or {}).get("value"),
                             "candidateValue": (cand or {}).get("value")})
            if v["verdict"] == "SAME" and cand is not None:
                carried = {k: published[bid][k] for k in ATTACHED if k not in cand and (published.get(bid) or {}).get(k) not in (None, {}, [])}
                cand = {**cand, **carried} if carried else cand
            effective[bid] = cand
    return effective, held


def regressions(before: dict[str, dict], after: dict[str, dict], intended=()) -> list[str]:
    """Brains whose displayed value or version changed although they were not in `intended`. A publish that touches an unintended Brain is a defect."""
    out = []
    for bid in sorted(set(before) | set(after)):
        if bid in set(intended):
            continue
        b, a = before.get(bid) or {}, after.get(bid) or {}
        if (b.get("value"), b.get("scoreVersion")) != (a.get("value"), a.get("scoreVersion")):
            out.append(f"{bid}: {b.get('value')} -> {a.get('value')}")
    return out
