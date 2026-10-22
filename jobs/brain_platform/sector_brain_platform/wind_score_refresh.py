"""Safe refresh of Wind's CERTIFICATION score block (`wind-certification-rubric-v1`) in docs/brains/scoring/frozen-scores.json.

Why: the published Wind 3.3 is a frozen snapshot (2026-10-13T21:13Z); the platform scorer publishes that block verbatim and nothing
re-evaluates it as live reliability days accrue. The rubric implementation stays where it is (Wind's research scoreboard, run by the
block generator on the Wind adoption lineage); THIS module is the platform's admission gate for a candidate block it produced:

  new eligible evidence -> candidate block (canonical scorer) -> admit() here -> versioned frozen block + append-only history
  -> score_brains.py publishes /scores/wind as before -> Sector Ops renders it. Ops never computes. (The Wind job still writes a legacy, non-canonical copy of its
validation scores into /brains/wind/scores and /validation/wind; /scores/wind is the canonical value. Retiring that copy is an open decision.)

Automatic acceptance is deliberately narrow: only the live-reliability dimension (8) may move. Any other movement (skill evidence,
field dimensions, coverage, provenance, caps, rubric/version, weights) is HELD for certification review, because before 2027-01-01
new skill evidence could only come from the sealed H2 window or from a changed rubric, and field evidence needs its own audit.
History is append-only; an earlier block is never edited.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re

from .timeutil import iso

RUBRIC = "wind-certification-rubric-v1"
AUTO_DIMENSIONS = ("Freshness/reliability",)
MAX_METADATA_AGE_H = 36.0
H2_UNSEALS = dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc)
_HYPO = re.compile(r"hypothetical|simulat|what-if|scenario", re.I)


def _p(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _dims(block):
    return {k.replace("-", "/") if k == "Freshness-reliability" else k: v for k, v in (block.get("scoreBreakdown") or {}).items()}


def reproduce(block: dict) -> list[str]:
    """The block's own arithmetic: Σ points = rawPoints; uncapped = raw/10; value = round(min(uncapped, caps), 1)."""
    p = []
    d = _dims(block)
    pts = round(sum(v.get("points", 0) for v in d.values()), 2)
    if abs(pts - (block.get("rawPoints") or -1)) > 0.02:
        p.append(f"points {pts} != rawPoints {block.get('rawPoints')}")
    if abs((block.get("rawPoints") or 0) / 10 - (block.get("uncapped") or -1)) > 0.0051:      # uncapped is raw/10 to 2 dp
        p.append(f"uncapped {block.get('uncapped')} != rawPoints/10")
    caps = [b["cap"] for b in block.get("scoreBlockers") or [] if "cap" in b]
    if round(min([block.get("uncapped") or 0] + caps), 1) != block.get("value"):
        p.append(f"value {block.get('value')} != round(min(uncapped, caps {caps}), 1)")
    for k, v in d.items():
        if abs(v.get("weight", 0) * v.get("value", 0) / 10 - v.get("points", 0)) > 0.02:
            p.append(f"{k}: weight x value != points")
    return p


def admit(current: dict, candidate: dict, now: dt.datetime) -> dict:
    """ACCEPT / HOLD / NO_CHANGE with every reason. Pure."""
    hold = []
    if candidate.get("scoreVersion") != RUBRIC or current.get("scoreVersion") != RUBRIC:
        hold.append(f"rubric must stay {RUBRIC} (candidate {candidate.get('scoreVersion')}); a rubric change is a separate approval")
    if candidate.get("basis") != "COMPUTED":
        hold.append(f"basis {candidate.get('basis')!r}: only a COMPUTED block from the canonical scorer is admissible")
    if _HYPO.search(json.dumps({k: candidate.get(k) for k in ("scoreRubric", "note", "basis", "evidence")})):
        hold.append("candidate is marked hypothetical/simulated")
    hold += [f"arithmetic: {x}" for x in reproduce(candidate)]
    cd, od = _dims(candidate), _dims(current)
    if set(cd) != set(od):
        hold.append(f"dimension set changed: {sorted(set(cd) ^ set(od))}")
    for k in set(cd) & set(od):
        if cd[k].get("weight") != od[k].get("weight"):
            hold.append(f"{k}: weight {od[k].get('weight')} -> {cd[k].get('weight')} (rubric change)")
    moved = sorted(k for k in set(cd) & set(od) if abs(cd[k].get("points", 0) - od[k].get("points", 0)) > 1e-9)
    review = [k for k in moved if k not in AUTO_DIMENSIONS]
    if review:
        hold.append(f"dimensions {review} moved: certification review required (only {list(AUTO_DIMENSIONS)} refresh automatically)")
    ev, oev = candidate.get("evidence") or {}, current.get("evidence") or {}
    for key in ("metadataThrough", "validArchiveDays", "evidenceFileSha", "scorerCode"):
        if ev.get(key) in (None, ""):
            hold.append(f"evidence.{key} missing")
    if ev.get("evidenceFileSha") and oev.get("evidenceFileSha") and ev["evidenceFileSha"] != oev["evidenceFileSha"]:
        hold.append("skill evidence file changed: review required" + (" (H2 sealed until 2027-01-01)" if now < H2_UNSEALS else ""))
    t_new, t_old = _p(ev.get("metadataThrough")), _p(oev.get("metadataThrough"))
    if t_new and (now - t_new).total_seconds() / 3600 > MAX_METADATA_AGE_H:
        hold.append(f"evidence stale: metadataThrough {ev.get('metadataThrough')} is older than {MAX_METADATA_AGE_H:g} h")
    if t_new and t_new > now:
        hold.append("evidence from the future")
    if t_new and t_old and t_new <= t_old:
        hold.append(f"evidence not newer than the published block ({ev.get('metadataThrough')} <= {oev.get('metadataThrough')})")
    if isinstance(ev.get("validArchiveDays"), int) and isinstance(oev.get("validArchiveDays"), int) and ev["validArchiveDays"] < oev["validArchiveDays"]:
        hold.append(f"valid archive days fell {oev['validArchiveDays']} -> {ev['validArchiveDays']}: ledger inconsistency, review required")
    same = {k: v for k, v in candidate.items() if k not in ("scoreUpdatedAt", "evidence")} == {k: v for k, v in current.items() if k not in ("scoreUpdatedAt", "evidence")}
    decision = "HOLD" if hold else ("NO_CHANGE" if same else "ACCEPT")
    return {"decision": decision, "reasons": hold or (["content unchanged"] if same else [f"dimension(s) {moved or 'none'} refreshed from newer live evidence"]),
            "moved": moved, "old": {"value": current.get("value"), "uncapped": current.get("uncapped"), "scoreUpdatedAt": current.get("scoreUpdatedAt")},
            "new": {"value": candidate.get("value"), "uncapped": candidate.get("uncapped"), "scoreUpdatedAt": candidate.get("scoreUpdatedAt")},
            "evaluatedAt": iso(now)}


def splice_wind(frozen_text: str, block: dict) -> str:
    """Replace ONLY the top-level "wind" object; every other entry stays byte-identical (same rule as the block generator)."""
    i = frozen_text.index('"wind": {'); j = frozen_text.index("{", i)
    depth, k, instr, esc = 0, j, False, False
    while True:
        ch = frozen_text[k]
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
        elif ch == '"':
            instr = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    out = frozen_text[:j] + json.dumps(block, indent=2, ensure_ascii=False).replace("\n", "\n  ") + frozen_text[k + 1:]
    a, b = json.loads(frozen_text), json.loads(out)
    assert {x: y for x, y in a.items() if x != "wind"} == {x: y for x, y in b.items() if x != "wind"} and b["wind"] == block
    return out


def history_line(result: dict, current: dict, candidate: dict) -> dict:
    """Append-only record. evaluationId links to the block it replaces."""
    h = lambda b: hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()[:16]
    return {"evaluationId": h(candidate), "previousEvaluationId": h(current), "scoreVersion": RUBRIC, **result,
            "evidence": candidate.get("evidence"), "previousEvidence": current.get("evidence")}


def refresh(frozen_path: str, history_path: str, candidate: dict, now: dt.datetime, write: bool = False) -> dict:
    """Admit a candidate; on ACCEPT (and only with write=True) splice it in and append the history line. HOLD/NO_CHANGE write
    a history line too when write=True (the decision itself is evidence), but never touch frozen-scores.json."""
    txt = open(frozen_path).read()
    current = json.loads(txt)["wind"]
    res = admit(current, candidate, now)
    line = history_line(res, current, candidate)
    if write:
        if res["decision"] == "ACCEPT":
            open(frozen_path, "w").write(splice_wind(txt, candidate))
        with open(history_path, "a") as f:
            f.write(json.dumps(line, sort_keys=True) + "\n")
    return line
