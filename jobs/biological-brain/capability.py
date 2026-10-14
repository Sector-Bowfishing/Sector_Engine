"""Derive the Biological State lifecycle from VERIFIED capability, never from a hand-set flag.

The registry's `responsibilities.biologicalState.status` feeds the canonical Brain score (`biological-state-score-v1`). It must
reflect real implemented capability, so the publisher computes it here from artifacts carried in the (private) canonical bundle:

  rules/            valid machine rules with at least one RECONCILED/APPROVED rule (biological-rule-v1)
  validation/       a hash-chained frozen-rule register covering every usable rule (and optionally a prediction log)
  state/pilot_*.json an internal pilot Biological State produced from those rules with at least one published specialist input

All present and consistent -> IN_PROGRESS. Anything missing, inconsistent or tampered -> NOT_STARTED with the blockers listed.
This module can NEVER return LIVE or VALIDATED: those are lifecycle decisions (approval + field validation), not computed.
"""
from __future__ import annotations

import json

import features as ft
import rules as rl
import validation_log as vl

NOT_STARTED_NOTE = "Per-lake Biological State is not built; it requires separate approval."
IN_PROGRESS_NOTE = ("Internal pilot only: researched rules are evaluated against published specialist Brain states for pilot lakes. "
                    "Nothing is written to /lakes/{k}/states/biology and no customer path reads it. Not LIVE; not validated.")


def _jsonl(raw: bytes) -> list[dict]:
    return [json.loads(line) for line in raw.decode().splitlines() if line.strip()]


def assess(files: dict[str, bytes]) -> dict:
    """`files` = verified bundle artifacts by path. Returns {status, validation, blockers, facts}."""
    if "rules/rules_manifest.json" not in files:
        return {"status": "NOT_STARTED", "validation": "NOT_STARTED", "blockers": ["no rules artifacts in the bundle"], "facts": {}}
    blockers, facts = [], {}
    try:
        man = json.loads(files["rules/rules_manifest.json"])
        rules = []
        for f in man["files"]:
            rules += json.loads(files[f"rules/{f['path']}"])["rules"]
        rs = rl.RuleSet(rules, man["rulesVersion"], source="bundle", retired=man.get("retired"), season_assertions=man.get("seasonAssertions"))
    except (KeyError, ValueError, rl.RuleError) as e:
        return {"status": "NOT_STARTED", "validation": "NOT_STARTED", "blockers": [f"rules invalid: {e}"], "facts": {}}
    usable = [r for r in rs.active_rules() if r["status"] in rl.USABLE_STATUSES]
    facts |= {"rulesVersion": rs.rules_version, "usableRules": len(usable), "draftRules": sum(r["status"] == "DRAFT" for r in rs.active_rules()), "retiredRules": len(rs.retired),
              "speciesWithUsableRules": len({r["speciesId"] for r in usable}), "speciesWithRules": len({r["speciesId"] for r in rs.active_rules()})}
    tally = {t: 0 for t in rl.TRANSFER}
    for r in usable:
        tally[r["transferability"]["southeastReservoir"]] += 1
    facts["transferSummary"] = {"usableRules": len(usable), "byTransferability": tally,
                                "note": "TRANSFERS needs a counting evidence stream from a Southeast reservoir; every other rule is a northern/foreign/other-system finding applied by analogy."}
    import target_readiness as _tr      # raw per-target counts for a scorer; no score is computed here
    facts["targetReadiness"] = _tr.build(rs)
    facts["ruleCountsBySpecies"] = {sid: {"usable": rs.counts(sid)["usable"], "draft": rs.counts(sid)["draft"]} for sid in sorted(rs.by_species) if rs.counts(sid)["total"]}
    if not usable:
        blockers.append("no RECONCILED/APPROVED rule")

    reg_raw = files.get("validation/frozen_rules.jsonl")
    if reg_raw is None:
        blockers.append("no frozen rule register")
    else:
        try:
            entries = _jsonl(reg_raw)
            vl._chain(entries, "frozen rule register")
            frozen = {(e["ruleId"], e["ruleVersion"]): e["ruleSha256"] for e in entries}
            missing = [r["ruleId"] for r in usable if frozen.get((r["ruleId"], r["ruleVersion"])) != rl.rule_hash(r)]
            if missing:
                blockers.append(f"{len(missing)} usable rule(s) not frozen with a matching hash (e.g. {missing[0]})")
            facts["frozenRules"] = len(entries)
        except (vl.LogError, KeyError, ValueError) as e:
            blockers.append(f"frozen rule register invalid: {e}")

    pred_raw = files.get("validation/predictions.jsonl")
    if pred_raw is not None:
        try:
            pes = _jsonl(pred_raw)
            vl._chain(pes, "prediction log")
            facts["predictionsLogged"] = len(pes)
        except (vl.LogError, ValueError) as e:
            blockers.append(f"prediction log invalid: {e}")

    obs_raw = files.get("validation/observations.jsonl")
    if obs_raw is not None:
        try:
            oes = _jsonl(obs_raw)
            vl._chain(oes, "observation store")
            facts["observationsLogged"] = len(oes)
            facts["independentTrips"] = len({o["tripId"] for o in oes if o.get("speciesIdConfidence") in ("CONFIRMED", "LIKELY")})
        except (vl.LogError, KeyError, ValueError) as e:
            blockers.append(f"observation store invalid: {e}")

    pilots = []
    for path, raw in sorted(files.items()):
        if not (path.startswith("state/pilot_") and path.endswith(".json")):
            continue
        try:
            st = json.loads(raw)
        except ValueError:
            blockers.append(f"{path} is not JSON")
            continue
        usable_inputs = [k for k, v in (st.get("inputs") or {}).items() if v.get("status") in ft.USABLE_INPUT_STATUS]
        ok = (st.get("kind") == "biological-state" and st.get("status") == "PILOT_INTERNAL" and (st.get("customerPath") or {}).get("consumed") is False
              and (st.get("provenance") or {}).get("rulesVersion") == rs.rules_version
              and (st.get("provenance") or {}).get("featuresVersion") == ft.FEATURES_VERSION
              and usable_inputs and (st.get("summary") or {}).get("speciesEvaluated", 0) >= 1)
        if ok:
            pilots.append(st["lakeId"])
        else:
            blockers.append(f"{path} does not verify against these rules/features or used no published specialist input")
    if not pilots:
        blockers.append("no verifying pilot Biological State artifact")
    facts["pilotLakes"] = pilots
    status = "IN_PROGRESS" if not blockers else "NOT_STARTED"
    return {"status": status, "validation": "NOT_STARTED", "blockers": blockers, "facts": facts, "ruleset": rs}
