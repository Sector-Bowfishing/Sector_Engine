"""Biological response-band contract (`biological-response-bands-v1`): the Biological-owned object Sector Intelligence consumes.

Biological owns the band; Intelligence must not recreate species science. A species node carries `responseBands` only when
the species has at least one usable (RECONCILED/APPROVED) rule. No approved band => Intelligence treats the species as
UNSUPPORTED, so this module never invents a band, a threshold or an approval:

  * `status` is PROPOSED unless EVERY contributing rule is APPROVED (a recorded reviewer); this module never approves.
  * `evidenceTier` is RESEARCH (VALIDATED is impossible here: validation is decided from outcomes, not computed).
  * overlapping rules that disagree resolve to one UNKNOWN band that names the conflict (never a guess);
  * features with no usable rule are absent from `bands` and listed nowhere as supported: absence is UNKNOWN;
  * free-text rule statements and evidence text are NOT carried: reasons are templated from structured fields.

Pure functions, stdlib only.
"""
from __future__ import annotations

import features as ft
import rules as rl

CONTRACT_VERSION = "biological-response-bands-v1"
BAND_STATUS = ("PROPOSED", "APPROVED", "WITHDRAWN")
EVIDENCE_TIER = ("RESEARCH", "REVIEWED", "VALIDATED")
EVIDENCE_KIND = ("DIRECT", "INFERRED", "MIXED")
VALIDATION_TIER = ("NONE", "T1", "T2", "T3", "T4")     # T1 independent literature, T2 regional holdout, T3 state survey/occurrence, T4 Sector observations
BAND_VALUES = rl.RESPONSE_OR_UNKNOWN
MAX_REASON = 160

TIER_MEANING = {"T1": "independent literature/studies", "T2": "regional holdout evidence", "T3": "state survey / tournament / authoritative occurrence",
                "T4": "structured Sector field observations"}


def _ctx(rule: dict) -> dict:
    a = rule.get("applicability") or {}
    return {"months": sorted(a.get("months") or []) or "all", "regions": list(a.get("regions", ["any"])),
            "waterbodyTypes": list(a.get("waterbodyTypes", ["any"])), "lifeStage": rule.get("lifeStage", "ADULT")}


def _set_overlap(a, b) -> bool:
    if a == "all" or b == "all":
        return True
    if "any" in a or "any" in b:
        return True
    return bool(set(a) & set(b))


def _overlap(r1: dict, r2: dict) -> bool:
    a1, a2 = r1.get("applicability") or {}, r2.get("applicability") or {}
    m1, m2 = a1.get("months") or "all", a2.get("months") or "all"
    return (_set_overlap(m1, m2) and _set_overlap(a1.get("regions", ["any"]), a2.get("regions", ["any"]))
            and _set_overlap(a1.get("waterbodyTypes", ["any"]), a2.get("waterbodyTypes", ["any"])))


def _kind(rule_list) -> str:
    ks = {e["directness"] for r in rule_list for e in r["evidence"] if e.get("counts")}
    return "MIXED" if len(ks) > 1 else (next(iter(ks)) if ks else "INFERRED")


def _basis(rule_list) -> dict:
    streams = {s for r in rule_list for s in rl.counting_streams(r)}
    mx = max((rl.max_confidence(r) for r in rule_list), key=rl.CONFIDENCE.index)
    return {"independentStreams": len(streams), "confidenceCap": mx,
            "capRule": "1 stream -> LOW; 2 -> MEDIUM; >=3 -> HIGH only if the rule transfers to Southeast reservoirs"}


def _validation_tier(rule_list) -> str:
    # The only evidence that exists is literature (T1). T2-T4 come from the validation register, never from a rule's own claim.
    return "T1" if any(e.get("counts") for r in rule_list for e in r["evidence"]) else "NONE"


def _limits(rule_list, feature_id: str | None = None) -> list[str]:
    out = []
    tr = min((r["transferability"]["southeastReservoir"] for r in rule_list), key=rl.TRANSFER.index)
    if tr == "UNTESTED":
        out.append("Southeast reservoir transfer untested")
    elif tr == "PARTIAL":
        out.append("Southeast reservoir transfer partial")
    if len({s for r in rule_list for s in rl.counting_streams(r)}) < 2:
        out.append("single evidence stream")
    if feature_id in ("risingStage", "fallingStage", "stageTrend", "warmRise", "coldRise"):
        out.append("lake pool trend is a proxy for river/tributary stage")
    if feature_id == "rapidDischargeIncrease":
        out.append("input not yet published by any Brain")
    if any(r.get("conflicts") for r in rule_list):
        out.append("documented conflicting evidence")
    return out


def _band_meta(rule_list: list[dict]) -> dict:
    return {"ruleVersion": {"ruleIds": sorted(r["ruleId"] for r in rule_list),
                            "versions": {r["ruleId"]: r["ruleVersion"] for r in rule_list}},
            "transferability": min((r["transferability"]["southeastReservoir"] for r in rule_list), key=rl.TRANSFER.index),
            "sourceCount": sum(1 for r in rule_list for e in r["evidence"] if e.get("counts")),
            "evidenceKind": _kind(rule_list), "confidenceBasis": _basis(rule_list), "validationTier": _validation_tier(rule_list)}


def _short(s: str) -> str:
    return s if len(s) <= MAX_REASON else s[: MAX_REASON - 1] + "…"


def _clusters(resp_rules: list[dict]) -> list[list[dict]]:
    """Union rules that cover the same feature + a shared state + an overlapping context but disagree on the band."""
    parent = list(range(len(resp_rules)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, a in enumerate(resp_rules):
        for j in range(i + 1, len(resp_rules)):
            b = resp_rules[j]
            if (a["feature"]["featureId"] == b["feature"]["featureId"] and set(a["feature"]["states"]) & set(b["feature"]["states"])
                    and a["response"] != b["response"] and _overlap(a, b)):
                parent[find(i)] = find(j)
    groups: dict[int, list[dict]] = {}
    for i, r in enumerate(resp_rules):
        groups.setdefault(find(i), []).append(r)
    return list(groups.values())


def compile_species_bands(species_id: str, rule_list: list[dict], *, generated_at: str, rules_version: str) -> dict | None:
    """The `responseBands` object for one species, or None when the species has no usable rule (=> UNSUPPORTED downstream)."""
    use = [r for r in rule_list if r["speciesId"] == species_id and r["status"] in rl.USABLE_STATUSES]
    if not use:
        return None
    resp = [r for r in use if r["kind"] == "RESPONSE"]
    bands = []
    for grp in _clusters(resp):
        first = sorted(grp, key=lambda r: r["ruleId"])[0]
        fid = first["feature"]["featureId"]
        if len(grp) > 1:
            states = sorted({s for r in grp for s in r["feature"]["states"]})
            bands.append({"bandId": "+".join(sorted(r["ruleId"] for r in grp)), "featureId": fid, "featureStates": states, "behavior": None,
                          "band": "UNKNOWN", "conflict": True, "conflictsWith": sorted(r["ruleId"] for r in grp), "context": _ctx(first),
                          "confidence": None, **_band_meta(grp),
                          "reason": _short(f"applicable rules disagree on {fid}: " + ", ".join(f"{r['ruleId']}={r['response']}" for r in sorted(grp, key=lambda r: r['ruleId']))),
                          "limitations": _limits(grp, fid) + ["conflicting rules resolve to UNKNOWN"]})
            continue
        r = grp[0]
        bands.append({"bandId": r["ruleId"], "featureId": fid, "featureStates": list(r["feature"]["states"]), "behavior": r.get("behavior"),
                      "band": r["response"], "conflict": False, "context": _ctx(r), "confidence": r["confidence"], **_band_meta([r]),
                      "reason": _short(f"{fid} in {','.join(r['feature']['states'])} -> {r['response']}" + (f" ({r['behavior']})" if r.get("behavior") else "")),
                      "limitations": _limits([r], fid)})
    habitat = []
    for r in sorted((x for x in use if x["kind"] == "HABITAT"), key=lambda x: x["ruleId"]):
        h = r["habitat"]
        habitat.append({"habitatClass": h["habitatClass"], "direction": h["direction"], "depthClass": h.get("depthClass"),
                        "requires": [{"featureId": q["featureId"], "states": list(q["states"])} for q in r.get("requires", [])],
                        "behavior": r.get("behavior"), "context": _ctx(r), "confidence": r["confidence"], **_band_meta([r]),
                        "reason": _short(f"{h['direction']} {h['habitatClass']}" + (f" (depth {h['depthClass']})" if h.get("depthClass") else "")),
                        "limitations": _limits([r])})
    spawn = []
    for r in sorted((x for x in use if x["kind"] == "PHENOLOGY"), key=lambda x: x["ruleId"]):
        t = r["phenology"]["tempC"]
        spawn.append({"event": "spawn", "tempC": {"min": t["min"], "max": t["max"]}, "context": _ctx(r), "confidence": r["confidence"], **_band_meta([r]),
                      "reason": f"spawn range {t['min']:g}-{t['max']:g} C (a range, not an optimum)", "limitations": _limits([r])})
    approved = all(r["status"] == "APPROVED" for r in use)
    tier_note = ["status PROPOSED: no rule has been approved by a reviewer"] if not approved else []
    covered = sorted({b["featureId"] for b in bands})
    out = {"contractVersion": CONTRACT_VERSION, "speciesId": species_id, "status": "APPROVED" if approved else "PROPOSED", "evidenceTier": "REVIEWED" if approved else "RESEARCH",
           "rulesVersion": rules_version, "featuresVersion": ft.FEATURES_VERSION, "generatedAt": generated_at,
           "coveredFeatures": covered, "bands": bands, "habitatPreferences": habitat, "spawn": spawn,
           "limitations": tier_note + ["rules say what the fish TENDS to do; not a probability and not a fishing score",
                                       "a feature absent from `bands` is UNKNOWN for this species"]}
    return out


def validate_response_bands(rb: dict) -> list[str]:
    """Schema/consistency problems with a `responseBands` object (empty = valid)."""
    e = []
    if rb.get("contractVersion") != CONTRACT_VERSION:
        e.append("contractVersion")
    if rb.get("status") not in BAND_STATUS:
        e.append("status")
    if rb.get("evidenceTier") not in EVIDENCE_TIER or rb.get("evidenceTier") == "VALIDATED":
        e.append("evidenceTier (VALIDATED cannot be asserted by the Biological compiler)")
    if rb.get("status") == "APPROVED" and rb.get("evidenceTier") == "RESEARCH":
        e.append("APPROVED needs evidenceTier REVIEWED or higher")
    if rb.get("status") == "PROPOSED" and rb.get("evidenceTier") != "RESEARCH":
        e.append("PROPOSED bands are RESEARCH tier")
    seen = set()
    for i, b in enumerate(rb.get("bands", [])):
        p = f"bands[{i}]"
        if b.get("band") not in BAND_VALUES:
            e.append(f"{p}.band")
        spec = ft.REGISTRY.get(b.get("featureId"))
        if spec is None or spec["availability"] == "AREA":
            e.append(f"{p}.featureId")
        elif any(s not in spec["states"] for s in b.get("featureStates", [])) or not b.get("featureStates"):
            e.append(f"{p}.featureStates")
        if b.get("band") == "UNKNOWN":
            if not b.get("conflict") or b.get("confidence") is not None:
                e.append(f"{p}: an UNKNOWN band must be a conflict band without confidence")
        elif b.get("confidence") not in rl.CONFIDENCE:
            e.append(f"{p}.confidence")
        for k in ("ruleVersion", "transferability", "sourceCount", "evidenceKind", "confidenceBasis", "validationTier", "reason", "limitations", "context"):
            if k not in b:
                e.append(f"{p} missing {k}")
        if b.get("evidenceKind") not in EVIDENCE_KIND:
            e.append(f"{p}.evidenceKind")
        if b.get("validationTier") not in VALIDATION_TIER:
            e.append(f"{p}.validationTier")
        if b.get("transferability") not in rl.TRANSFER:
            e.append(f"{p}.transferability")
        if not isinstance(b.get("sourceCount"), int) or b["sourceCount"] < 1:
            e.append(f"{p}.sourceCount must be >=1 (a band without counting evidence cannot exist)")
        if b.get("confidence") in rl.CONFIDENCE and b.get("confidenceBasis", {}).get("confidenceCap") in rl.CONFIDENCE \
                and rl.CONFIDENCE.index(b["confidence"]) > rl.CONFIDENCE.index(b["confidenceBasis"]["confidenceCap"]):
            e.append(f"{p}: confidence exceeds the cap its evidence streams allow")
        for k in ("reason",):
            if len(str(b.get(k, ""))) > MAX_REASON:
                e.append(f"{p}.{k} too long")
        if b.get("bandId") in seen:
            e.append(f"{p}: duplicate bandId")
        seen.add(b.get("bandId"))
    for i, h in enumerate(rb.get("habitatPreferences", [])):
        if h.get("habitatClass") not in ft.HABITAT_CLASSES or h.get("direction") not in rl.DIRECTIONS:
            e.append(f"habitatPreferences[{i}]")
    for i, s in enumerate(rb.get("spawn", [])):
        t = s.get("tempC") or {}
        if not (isinstance(t.get("min"), (int, float)) and isinstance(t.get("max"), (int, float)) and t["min"] < t["max"]):
            e.append(f"spawn[{i}].tempC must be a range")
    if not (rb.get("bands") or rb.get("habitatPreferences") or rb.get("spawn")):
        e.append("empty: a species without a usable rule must omit responseBands")
    return e
