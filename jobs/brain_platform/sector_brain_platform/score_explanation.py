"""Brain Score Explanation V1 (docs/brains/scoring/SCORE_EXPLANATION_V1.md; schema contracts/schemas/brain-score-explanation.schema.json).

A derived, read-only companion of ONE published score block: why the score is what it is, what would raise it, and the
arithmetic distance to the 7.0 planning target. The platform scorer builds it from the SAME block it publishes and writes it
INSIDE that block (/scores/{brainId}/explanation) in the same RTDB update, so a reader can never pair a new score with an old
explanation. It is never an input to any score, never changes `value`, and is excluded from score content comparisons.

Honesty rules (the same as the rubrics'):
  - contributions are reported only when the published breakdown REPRODUCES the published `uncapped` under the platform's
    linear rule (uncapped = sum(value x weight) / 100); otherwise they are left out and the formula is UNVERIFIED;
  - UNKNOWN stays UNKNOWN (it contributes 0 under the rubric and says so); a missing breakdown yields no components;
  - an improvement's impact is "up to" rubric headroom, never a promise; caps are reported, never summed away;
  - the path to 7.0 is arithmetic over the rubric only; it is never "validated" (research outcomes are not known in advance).
Pure functions. The improvement registry is read lazily (no import-time I/O). Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

CONTRACT = "brain-score-explanation-v1"
TARGET = 7.0
LINEAR = "LINEAR_WEIGHTED_CAPPED"
REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "score_improvements_v1.json")
NON_CONTENT = ("scoreUpdatedAt", "updatedAt", "explanation")
PRIORITY_RULE = ("HIGH: a cap that holds the displayed score now, or >= 1.0 point of rubric headroom; MEDIUM: a cap below the "
                 "7.0 target that is not binding yet, or >= 0.4 point of headroom; LOW: less headroom; UNRANKED: impact not "
                 "computable from the published evaluation")
_PRIVATE = re.compile(r"gs://[^\s)\]]+|/Users/[^\s)\]]+|~/[^\s)\]]+")
_REGISTRY: dict | None = None


def registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        with open(REGISTRY_FILE) as fh:
            _REGISTRY = json.load(fh)
    return _REGISTRY


def public(text):
    """Display-safe text: private bucket URIs and local paths are replaced, never published through the explanation."""
    if not isinstance(text, str):
        return text
    return _PRIVATE.sub("[private record]", text).strip()


def score_content(block: dict | None) -> dict:
    return {k: v for k, v in (block or {}).items() if k not in NON_CONTENT and v not in (None, {}, [])}


def evaluation_id(block: dict | None) -> str:
    """Stable id of one evaluation: the hash of the block's substance (timestamps and the explanation excluded)."""
    raw = json.dumps(score_content(block), sort_keys=True, separators=(",", ":"), default=str)
    return "eval-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _r(x, n=2):
    return None if x is None else round(float(x), n)


def components(block: dict, labels: dict | None = None) -> tuple[list[dict], str]:
    """-> (components, formula). Contributions only when the breakdown reproduces `uncapped` (+/- rounding).
    `labels`: the rubric's own dimension labels (copied into the improvement registry from docs/brains/scoring/*-score-v1.json)."""
    labels = labels or {}
    bd = block.get("scoreBreakdown") or {}
    if not bd:
        return [], "UNKNOWN"
    weights = [v.get("weight") for v in bd.values()]
    formula = "UNVERIFIED"
    if all(_num(w) for w in weights) and abs(sum(weights) - 100) < 1e-6 and _num(block.get("uncapped")):
        earned = sum(v["value"] * v["weight"] for v in bd.values() if v.get("status") == "SCORED" and _num(v.get("value")))
        if abs(earned / 100.0 - block["uncapped"]) <= 0.051:
            formula = LINEAR
    out = []
    for cid, v in bd.items():
        scored = v.get("status") == "SCORED" and _num(v.get("value"))
        c = {"id": cid, "label": v.get("label") or labels.get(cid) or cid, "status": v.get("status") or "UNKNOWN", "evidence": public(v.get("evidence"))}
        if scored:
            c["value"] = v["value"]
        if _num(v.get("weight")):
            c["weight"] = v["weight"]
        if formula == LINEAR:
            possible = v["weight"] / 10.0
            earned = v["value"] * v["weight"] / 100.0 if scored else 0.0     # rubric: UNKNOWN contributes 0
            c.update(earned=_r(earned), possible=_r(possible), headroom=_r(possible - earned))
        out.append({k: x for k, x in c.items() if x is not None})
    out.sort(key=lambda c: (-(c.get("weight") or 0), c["id"]))
    return out, formula


def caps(block: dict) -> list[dict]:
    uncapped = block.get("uncapped")
    out = []
    for b in block.get("scoreBlockers") or []:
        if not _num(b.get("cap")):
            continue
        out.append({"gate": b.get("gate") or "unnamed", "cap": b["cap"], "why": public(b.get("why")),
                    "belowUncapped": bool(_num(uncapped) and b["cap"] < uncapped - 1e-9), "belowTarget": b["cap"] < TARGET})
    out.sort(key=lambda c: c["cap"])
    for i, c in enumerate(out):                                   # only the LOWEST cap below the uncapped score holds the value
        c["binding"] = i == 0 and c["belowUncapped"]
    return out


def _entry(brain_id: str, key: str) -> dict | None:
    return (((registry().get("brains") or {}).get(brain_id) or {}).get("entries") or {}).get(key)


def _cap_key(gate: str, cap) -> str:
    return f"gate:{gate}@{cap:g}"


def improvements(brain_id: str, block: dict, comps: list[dict], formula: str, gaps: dict | None = None) -> list[dict]:
    """Every deficiency of this evaluation, as a concrete improvement (registry wording where it exists), ranked by evidence."""
    gaps = gaps or {}
    by_dim = {c["id"]: c for c in comps}
    value, uncapped = block.get("value"), block.get("uncapped")
    cap_list = caps(block)
    items: dict[str, dict] = {}
    attached: dict[str, list[dict]] = {}

    def base(key, title, limitation, entry):
        e = entry or {}
        it = {"id": f"{brain_id}/{key}", "key": key, "title": e.get("title") or title, "limitation": public(limitation),
              "action": e.get("action"), "type": e.get("type"), "nature": e.get("nature"), "status": "OPEN", "blockers": []}
        if e.get("blocker"):
            it["blockers"].append({"kind": e["blocker"]["kind"], "detail": e["blocker"]["detail"], "source": "registry"})
        if e.get("researchGaps"):
            it["researchGaps"] = [{"id": g, **({"status": gaps[g]["status"]} if g in gaps and gaps[g].get("status") else {}),
                                   **({"title": public(gaps[g]["title"])} if g in gaps and gaps[g].get("title") else {})} for g in e["researchGaps"]]
        if e.get("related"):
            it["related"] = [f"{brain_id}/{r}" for r in e["related"]]
        if e.get("blocks"):
            it["status"] = "BLOCKED"
        return it

    # 1. dimensions with headroom (or unknown)
    for c in comps:
        key = f"dimension:{c['id']}"
        unknown = c["status"] != "SCORED"
        if not unknown and c.get("value", 10) >= 10:
            continue
        e = _entry(brain_id, key)
        it = base(key, f"Raise {c['label']}", ("UNKNOWN: " if unknown else "") + (c.get("evidence") or ""), e)
        it["dimension"] = c["id"]
        if formula == LINEAR and c.get("headroom") is not None:
            it["impact"] = ({"kind": "UP_TO_UNCAPPED_IF_MEASURED", "points": c["headroom"],
                             "basis": "the dimension is UNKNOWN (contributes 0); measured at full credit it would add up to this much to the uncapped score; caps still apply"}
                            if unknown else
                            {"kind": "UP_TO_UNCAPPED", "points": c["headroom"],
                             "basis": "rubric headroom: this dimension at full credit adds up to this much to the uncapped score; caps still apply"})
        items[key] = it

    # 2. caps (always their own improvement: they decide the displayed score and the path to 7.0)
    for i, cp in enumerate(cap_list):
        key = _cap_key(cp["gate"], cp["cap"])
        e = _entry(brain_id, key) or _entry(brain_id, f"gate:{cp['gate']}")
        it = base(key, f"Lift the {cp['gate']} cap ({cp['cap']:g})", cp["why"], e)
        it["gate"], it["cap"] = cp["gate"], cp["cap"]
        nxt = min([c["cap"] for c in cap_list[i + 1:]] + [10.0])
        if _num(uncapped) and _num(value):
            gain_now = max(0.0, min(uncapped, nxt) - value) if cp["binding"] else 0.0
            it["impact"] = {"kind": "LIFTS_CAP", "points": _r(gain_now, 1), "cap": cp["cap"],
                            "basis": ("binding now: lifting it raises the displayed score toward the uncapped score (next cap "
                                      f"{nxt:g})") if gain_now > 0 else
                                     ("not binding now; must be lifted before the displayed score can pass " f"{cp['cap']:g}")}
        items[key] = it

    # 3. blockers without a cap: attach to the dimension they explain, or stand alone
    for b in block.get("scoreBlockers") or []:
        if _num(b.get("cap")):
            continue
        gate, dimension = b.get("gate"), b.get("dimension")
        why = public(b.get("why"))
        if dimension and f"dimension:{dimension}" in items:
            attached.setdefault(f"dimension:{dimension}", []).append({"kind": "RUBRIC", "detail": why, "source": "evaluation"})
            continue
        e = _entry(brain_id, f"gate:{gate}") if gate else None
        targets = [t for t in (e or {}).get("blockerOf", []) if t in items]
        if targets:
            for t in targets:
                attached.setdefault(t, []).append({"kind": ((e or {}).get("blocker") or {}).get("kind", "RUBRIC"), "detail": why,
                                                   "source": "evaluation", "gate": gate})
                if (e or {}).get("blocks"):
                    items[t]["status"] = "BLOCKED"
            continue
        key = f"gate:{gate}" if gate else f"dimension:{dimension}"
        it = base(key, f"Clear {gate or dimension}", why, e)
        if gate:
            it["gate"] = gate
        items[key] = it
    for k, extra in attached.items():
        items[k]["blockers"].extend(extra)

    # 4. rank by evidence only
    for it in items.values():
        it["priority"] = _priority(it)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNRANKED": 3}
    ranked = sorted(items.values(), key=lambda x: (order[x["priority"]], -((x.get("impact") or {}).get("points") or 0),
                                                   0 if x.get("cap") is not None else 1, x["key"]))
    for n, it in enumerate(ranked, 1):
        it["rank"] = n if it["priority"] != "UNRANKED" else None
    return [{k: v for k, v in it.items() if v not in (None, [], {})} for it in ranked]


def _priority(it: dict) -> str:
    imp = it.get("impact")
    if not imp:
        return "UNRANKED"
    pts = imp.get("points") or 0
    if imp["kind"] == "LIFTS_CAP":
        if pts > 0:
            return "HIGH"
        return "MEDIUM" if (it.get("cap") or 10) < TARGET else "LOW"
    return "HIGH" if pts >= 1.0 else "MEDIUM" if pts >= 0.4 else "LOW" if pts > 0 else "UNRANKED"


def scope_of(block: dict) -> str:
    applies = block.get("appliesTo") or {}
    return "CANDIDATE" if str(applies.get("status") or "").upper() == "CANDIDATE" else "PUBLISHED"


def target(block: dict, comps: list[dict], formula: str) -> dict:
    value, uncapped = block.get("value"), block.get("uncapped")
    scope = scope_of(block)
    out = {"value": TARGET, "scale": block.get("scale") or 10, "scope": scope}
    if not _num(value):
        return {**out, "pathway": {"status": "NOT_EVALUABLE", "validated": False, "why": "no published score value"}}
    out.update(current=value, gap=_r(max(0.0, TARGET - value), 1), reached=value >= TARGET)
    if scope == "CANDIDATE":
        return {**out, "pathway": {"status": "NOT_EVALUABLE", "validated": False,
                                   "why": "the published value scores an undeployed CANDIDATE; the production model carries no score, so "
                                          "there is no production score to move toward the target"}}
    if value >= TARGET:
        return {**out, "pathway": {"status": "REACHED", "validated": True, "why": f"published score {value:g} is at or above {TARGET:g}"}}
    blocking = [c for c in caps(block) if c["belowTarget"]]
    pw = {"validated": False, "capsToLift": [{"gate": c["gate"], "cap": c["cap"], "why": c["why"]} for c in blocking]}
    if formula != LINEAR or not _num(uncapped):
        pw.update(status="NOT_EVALUABLE",
                  why="the published evaluation has no breakdown that reproduces its score, so no rubric arithmetic toward 7.0 is possible")
        return {**out, "pathway": {k: v for k, v in pw.items() if v not in ([],)}}
    need = max(0.0, TARGET - uncapped)
    scored = sorted([c for c in comps if c["status"] == "SCORED" and (c.get("headroom") or 0) > 0], key=lambda c: -c["headroom"])
    unknown = [c for c in comps if c["status"] != "SCORED" and (c.get("headroom") or 0) > 0]
    avail, unk = sum(c["headroom"] for c in scored), sum(c["headroom"] for c in unknown)
    picked, acc = [], 0.0
    for c in scored:
        if acc >= need - 1e-9:
            break
        picked.append(c["id"]); acc += c["headroom"]
    pw.update(requiredUncappedGain=_r(need), availableHeadroom=_r(avail), unknownHeadroom=_r(unk),
              largestHeadroomDimensions=picked if acc >= need - 1e-9 else [c["id"] for c in scored])
    if avail + 1e-9 >= need:
        pw.update(status="ARITHMETIC_PATH_EXISTS",
                  why=(f"rubric arithmetic only: uncapped {uncapped:g} needs +{need:.2f}; the scored dimensions have {avail:.2f} of headroom"
                       + (f"; {len(blocking)} cap(s) below {TARGET:g} must also be lifted" if blocking else "")
                       + ". Target pathway not yet fully validated: it assumes the listed work succeeds and is published"))
    else:
        pw.update(status="NO_ARITHMETIC_PATH",
                  why=f"uncapped {uncapped:g} needs +{need:.2f} but the scored dimensions have only {avail:.2f} of headroom"
                      + (f" (+{unk:.2f} more if UNKNOWN dimensions became measurable)" if unk else ""))
    return {**out, "pathway": {k: v for k, v in pw.items() if v not in ([],)}}


def change(block: dict, previous: dict | None, items: list[dict]) -> dict:
    prev = previous or {}
    if not score_content(prev):
        return {"direction": "FIRST", "why": "first explained evaluation for this Brain"}
    out = {"previousEvaluationId": (prev.get("explanation") or {}).get("evaluationId") or evaluation_id(prev),
           "previousScoreUpdatedAt": prev.get("scoreUpdatedAt"), "previousValue": prev.get("value"), "previousUncapped": prev.get("uncapped")}
    v, pv = block.get("value"), prev.get("value")
    if _num(v) and _num(pv):
        d = round(v - pv, 1)
        out.update(delta=d, direction="UP" if d > 0 else "DOWN" if d < 0 else "UNCHANGED")
    else:
        out["direction"] = "UNKNOWN"
    moved = []
    pb, nb = prev.get("scoreBreakdown") or {}, block.get("scoreBreakdown") or {}
    for k in sorted(set(pb) | set(nb)):
        a, b = (pb.get(k) or {}).get("value"), (nb.get(k) or {}).get("value")
        if a != b:
            moved.append({"id": k, **({"from": a} if a is not None else {}), **({"to": b} if b is not None else {})})
    if moved:
        out["movedDimensions"] = moved
    old_active = {i["id"]: i for i in ((prev.get("explanation") or {}).get("improvements") or [])}
    now_ids = {i["id"] for i in items}
    resolved = [{"id": i, "title": old_active[i].get("title")} for i in old_active if i not in now_ids]
    if resolved:
        out["resolved"] = resolved
    new = [i for i in now_ids if old_active and i not in old_active]
    if new:
        out["newImprovementIds"] = sorted(new)
    if out.get("direction") == "UNCHANGED":
        bind = [c for c in caps(block) if c["binding"]]
        if bind:
            out["why"] = f"displayed value held at the {bind[0]['gate']} cap {bind[0]['cap']:g}" + (
                f"; uncapped {prev.get('uncapped')} -> {block.get('uncapped')}" if prev.get("uncapped") != block.get("uncapped") else "")
        elif moved:
            out["why"] = "dimensions moved but the rounded score did not"
        else:
            out["why"] = "no dimension moved; the evaluation changed only in evidence wording, blockers or metadata"
    elif out.get("direction") in ("UP", "DOWN"):
        out["why"] = ("dimensions moved: " + ", ".join(m["id"] for m in moved)) if moved else "the published score block changed (no breakdown to compare)"
    return out


def explain(brain_id: str, block: dict, previous: dict | None = None, *, gaps: dict | None = None, knowledge: dict | None = None) -> dict:
    """The explanation for ONE score block. `previous` = the block it replaces (for the change record); `gaps` = {gapId: gap}
    from the Brain's research gap register; `knowledge` = lightweight release identifiers from the Brain registry."""
    reg = (registry().get("brains") or {}).get(brain_id) or {}
    comps, formula = components(block, reg.get("labels"))
    items = improvements(brain_id, block, comps, formula, gaps)
    rubric = {"scoreVersion": block.get("scoreVersion"), "formula": formula}
    ref = block.get("scoreRubric")
    if isinstance(ref, str) and ref:
        if _PRIVATE.search(ref):
            rubric.update(ref=public(ref), refVisibility="PARTLY_PRIVATE")
        else:
            rubric["ref"] = ref
    if reg.get("rubricSource"):
        rubric["improvementSource"] = reg["rubricSource"]
    out = {
        "contract": CONTRACT,
        "evaluationId": evaluation_id(block),
        "forScore": {k: block.get(k) for k in ("value", "uncapped", "scale", "basis", "scoreVersion", "scoreUpdatedAt") if block.get(k) is not None},
        "scope": scope_of(block),
        "rubric": rubric,
        "knowledge": {k: v for k, v in (knowledge or {}).items() if v not in (None, "")} or None,
        "completenessPct": block.get("completenessPct"),
        "components": comps,
        "caps": caps(block),
        "improvements": items,
        "priorityRule": PRIORITY_RULE,
        "registryVersion": registry().get("registryVersion"),
        "target": target(block, comps, formula),
        "change": change(block, previous, items),
    }
    if block.get("note"):
        out["note"] = public(block["note"])
    if block.get("appliesTo"):
        out["appliesTo"] = {k: v for k, v in block["appliesTo"].items() if isinstance(v, (str, int, float))}
    if block.get("nextScoreOpportunity"):
        out["engineNextOpportunity"] = public(block["nextScoreOpportunity"])
    return {k: v for k, v in out.items() if v not in (None, [], {})}


def is_current(block: dict | None) -> bool:
    """True when the block carries an explanation of THIS evaluation under this contract (the reader-side binding rule)."""
    ex = (block or {}).get("explanation") or {}
    return ex.get("contract") == CONTRACT and ex.get("evaluationId") == evaluation_id(block)
