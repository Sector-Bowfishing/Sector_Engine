"""Plain-English reviewer package for bowfishers: one line per usable rule, no jargon, no rule ids in the headline, three decisions.

  fish -> condition -> Sector conclusion -> what it means on the water -> sources + evidence strength + regional confidence -> ACCEPT / REJECT / NEEDS_MORE_EVIDENCE
Rule CONTENT is private research output: the generated package belongs in the private store, never in git. The answer sheet is compatible with `review.py apply`.
Pure functions; reads nothing.
"""
from __future__ import annotations

import movement_outlook as mo
import target_set as ts

MONTH = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CONCLUSION = {"FAVORABLE": "Strong increase in shallow / active likelihood", "WORKABLE": "Fish still workable", "LIMITING": "Fewer shootable fish", "BLOCKING": "Fish effectively unavailable"}
MEANING = {
    ("risingStage", "FAVORABLE"): "Check newly flooded margins, creek mouths and backwaters.", ("risingStage", "LIMITING"): "No rise in level: expect fewer fish in the shallows.",
    ("fallingStage", "LIMITING"): "The margins are emptying; move to channels, backwaters and holes.", ("warmRise", "FAVORABLE"): "Warm water plus a rising lake pushes fish onto flooded edges.",
    ("coldRise", "LIMITING"): "A rise in cold water does little; do not expect a push into the shallows.", ("daypart", "FAVORABLE"): "Work the shallows after dark.",
    ("daypart", "WORKABLE"): "Night trips are worth it in this condition.", ("clarityBand", "WORKABLE"): "Muddy water does not keep them away.", ("clarityBand", "LIMITING"): "Dirty water makes them hard to see or find.",
    ("waterTempBand", "LIMITING"): "Cold water: slow fish, few in the shallows.", ("waterTempBand", "BLOCKING"): "Too cold: expect almost none.", ("waterTempBand", "WORKABLE"): "Workable water temperature.", ("daypart", "LIMITING"): "Night is a poor time for this fish in this condition.", ("daypart", "BLOCKING"): "Do not expect fish at this time.",
    ("waterTempBand", "FAVORABLE"): "Water in the sweet spot: fish move shallow.", ("stageTrend", "LIMITING"): "Fast-falling water strands or pulls fish out of the shallows.",
}
HAB_MEANING = {"FAVOR": "Look in ", "AVOID": "Skip "}


def months_phrase(months) -> str:
    if not months:
        return "any time of year"
    ms = sorted(months)
    runs, cur = [], [ms[0]]
    for m in ms[1:]:
        (cur.append(m) if m == cur[-1] + 1 else (runs.append(cur), cur := [m]))
    runs.append(cur)
    if len(runs) > 1 and runs[0][0] == 1 and runs[-1][-1] == 12:
        runs = [runs[-1] + runs[0]] + runs[1:-1]
    return ", ".join(f"{MONTH[r[0]]}-{MONTH[r[-1]]}" if len(r) > 1 else MONTH[r[0]] for r in runs)


def _temp_phrase(states) -> str:
    return " or ".join(mo.TEMP_PHRASE[s] for s in states if s in mo.TEMP_PHRASE)


def condition(rule: dict) -> str:
    when = months_phrase((rule.get("applicability") or {}).get("months"))
    k = rule["kind"]
    if k == "PHENOLOGY":
        t = rule["phenology"]["tempC"]
        return f"{when}; water about {t['min'] * 9 / 5 + 32:.0f}-{t['max'] * 9 / 5 + 32:.0f} F"
    if k == "RESPONSE":
        f = rule["feature"]["featureId"]
        if f == "waterTempBand":
            return f"{when}; " + _temp_phrase(rule["feature"]["states"])
        return f"{when}; " + " or ".join(mo.PHRASE.get((f, s), f"{f} is {s}") for s in rule["feature"]["states"])
    h = rule["habitat"]
    gates = [(_temp_phrase(q["states"]) if q["featureId"] == "waterTempBand" else " or ".join(mo.PHRASE.get((q["featureId"], s), f"{q['featureId']} is {s}") for s in q["states"])) for q in rule.get("requires") or []]
    return f"{when}" + ("; " + "; ".join(gates) if gates else "")


def conclusion(rule: dict) -> str:
    if rule["kind"] == "RESPONSE":
        return CONCLUSION[rule["response"]]
    if rule["kind"] == "PHENOLOGY":
        return "Spawning window: fish are in spawning habitat and easier to find"
    return "More fish expected here" if rule["habitat"]["direction"] == "FAVOR" else "Fewer fish expected here"


def meaning(rule: dict) -> str:
    if rule["kind"] == "RESPONSE":
        return MEANING.get((rule["feature"]["featureId"], rule["response"])) or rule.get("statement", "")[:140]
    if rule["kind"] == "PHENOLOGY":
        return "Concentrate on the spawning habitat (shallow cover, flooded margins, creek mouths) while water is in this range."
    h = rule["habitat"]
    return HAB_MEANING[h["direction"]] + mo.WHERE.get(h["habitatClass"], h["habitatClass"]) + (" (shallow, under about 1.5 m)" if h.get("depthClass") in ("LT_0_5M", "M0_5_1_5") else "") + "."


def strength(rule: dict) -> str:
    n = len({e["streamId"] for e in rule["evidence"] if e.get("counts")})
    return f"{rule['confidence']} confidence from {n} independent inspected source{'s' if n != 1 else ''}"


def regional(rule: dict) -> str:
    t = rule["transferability"]["southeastReservoir"]
    return {"TRANSFERS": "HIGH (Southeast evidence)", "PARTIAL": "MEDIUM (partly Southeast / similar systems)", "UNTESTED": "LOW (not yet shown in the Southeast)"}[t]


def sources(rule: dict, titles: dict | None = None) -> str:
    out = []
    for e in rule["evidence"]:
        if not e.get("counts"):
            continue
        t = (titles or {}).get(f"{rule['speciesId']}:{e['sourceNo']}") or f"{e['packet']} {e['sourceNo']}"
        out.append(t[:70])
    return "; ".join(out[:3]) or "(no inspected source)"


def package(rules: list[dict], labels: dict, titles: dict | None = None) -> tuple[str, list[dict]]:
    """Markdown package (targets first, common carp first) + a blank answer sheet. Only usable rules are listed."""
    order = lambda s: (0 if ts.role(s) == "TARGET" else 1 if ts.role(s) == "SECONDARY" else 2, s != "common_carp", s)      # noqa: E731
    by: dict = {}
    for r in rules:
        if r["status"] in ("RECONCILED", "APPROVED"):
            by.setdefault(r["speciesId"], []).append(r)
    md = ["# Biological rule review (PRIVATE: contains rule content)", "", "For each line choose **ACCEPT**, **REJECT** or **NEEDS_MORE_EVIDENCE**. ACCEPT means 'this matches how the fish behave'. It does not mean field-validated.",
          "Write your decision in the answer sheet (same order). The author cannot review their own rules.", ""]
    sheet = []
    for sid in sorted(by, key=order):
        md += [f"## {labels.get(sid, sid)}  ({ts.role(sid).replace('_', ' ').lower()})", "", "| # | Condition | Sector conclusion | On the water | Evidence | Regional | Sources | Decision |", "|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(sorted(by[sid], key=lambda x: x["ruleId"]), 1):
            md.append(f"| {i} | {condition(r)} | {conclusion(r)} | {meaning(r)} | {strength(r)} | {regional(r)} | {sources(r, titles)} | ACCEPT / REJECT / NEEDS_MORE_EVIDENCE |")
            sheet.append({"ruleId": r["ruleId"], "ruleVersion": r["ruleVersion"], "fish": labels.get(sid, sid), "decision": "", "reviewer": "", "reviewerRole": "", "date": "", "note": ""})
        md.append("")
    return "\n".join(md), sheet
