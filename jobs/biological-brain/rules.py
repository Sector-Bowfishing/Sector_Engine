"""Biological machine rules (`biological-rule-v1`): parsing, validation, applicability and response-band evaluation.

A rule says what a researched species TENDS to do under a condition feature (docs/brains/BIOLOGICAL_RULES_AND_STATE_CONTRACT.md).
The rule CONTENT for real species lives in the PRIVATE bundle; this public module only knows the shape, the evidence
discipline and the evaluator. Its tests use synthetic species.

Evidence discipline enforced here, so a rule cannot claim more than its evidence carries:
  * snippet-only / unopened / profile-carried sources never count (`counts` is forced false);
  * confidence is capped by the number of INDEPENDENT evidence streams (one cohort or one dataset = one stream, however
    many papers report it): 1 stream -> LOW, 2 -> MEDIUM, >=3 -> HIGH only if the rule transfers to Southeast reservoirs;
  * a RECONCILED or APPROVED rule needs at least one counting source that was actually read (full text or abstract);
  * APPROVED needs a recorded reviewer; nothing here approves a rule.
Conflicting rules (same species + feature state, different response) resolve to UNKNOWN with the conflict listed, never to a guess.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

import features as ft

RULE_SCHEMA_VERSION = 1
RESPONSES = ("FAVORABLE", "WORKABLE", "LIMITING", "BLOCKING")
RESPONSE_OR_UNKNOWN = RESPONSES + ("UNKNOWN",)
KINDS = ("RESPONSE", "HABITAT", "PHENOLOGY")
STATUSES = ("DRAFT", "RECONCILED", "APPROVED", "RETIRED")
USABLE_STATUSES = ("RECONCILED", "APPROVED")
CONFIDENCE = ("LOW", "MEDIUM", "HIGH")
TRANSFER = ("UNTESTED", "PARTIAL", "TRANSFERS")           # worst -> best
REGIONS = ("south", "lowerMid", "north", "west", "any")      # Engine Region vocabulary
WATERBODIES = ("run_of_river", "storage_reservoir", "natural_lake", "river", "any")
LIFE_STAGES = ("ADULT", "JUVENILE", "ANY")
READ_STATUS = ("READ-FULL", "READ-ABSTRACT", "SNIPPET-ONLY", "LEAD-NOT-OPENED", "PROFILE-CARRIED", "PROFILE-REVIEWED")
COUNTING_READ = ("READ-FULL", "READ-ABSTRACT", "PROFILE-REVIEWED")
DIRECTNESS = ("DIRECT", "INFERRED")
DIRECTIONS = ("FAVOR", "AVOID")
RULE_ID = re.compile(r"^[A-Z]{2,4}-[A-Z]{2,5}-\d{2}[A-Za-z]?$")
SPECIES_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class RuleError(ValueError):
    """A rules bundle is missing, corrupted or violates the rule contract."""


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def rule_hash(rule: dict) -> str:
    return hashlib.sha256(canonical(rule)).hexdigest()


def counting_streams(rule: dict) -> set:
    return {e["streamId"] for e in rule.get("evidence", []) if e.get("counts")}


def max_confidence(rule: dict) -> str:
    n = len(counting_streams(rule))
    if n >= 3 and rule.get("transferability", {}).get("southeastReservoir") == "TRANSFERS":
        return "HIGH"
    if n >= 2:
        return "MEDIUM"
    return "LOW"


def validate_rule(rule: dict) -> list[str]:
    """All problems with one rule (empty = valid). Does not mutate."""
    e: list[str] = []
    g = rule.get
    if g("schemaVersion") != RULE_SCHEMA_VERSION:
        e.append("schemaVersion must be 1")
    rid = g("ruleId", "")
    if not RULE_ID.match(str(rid)):
        e.append(f"ruleId {rid!r} must look like SC-HYD-01")
    if not SPECIES_ID.match(str(g("speciesId", ""))):
        e.append("speciesId must be snake_case")
    if not isinstance(g("ruleVersion"), int) or g("ruleVersion") < 1:
        e.append("ruleVersion must be an integer >= 1")
    if g("kind") not in KINDS:
        e.append(f"kind must be one of {KINDS}")
    if g("status") not in STATUSES:
        e.append(f"status must be one of {STATUSES}")
    if g("confidence") not in CONFIDENCE:
        e.append(f"confidence must be one of {CONFIDENCE}")
    tr = (g("transferability") or {}).get("southeastReservoir")
    if tr not in TRANSFER:
        e.append(f"transferability.southeastReservoir must be one of {TRANSFER}")
    if g("lifeStage", "ADULT") not in LIFE_STAGES:
        e.append("lifeStage")

    app = g("applicability") or {}
    months = app.get("months")
    if months is not None and (not isinstance(months, list) or any((not isinstance(m, int)) or not 1 <= m <= 12 for m in months)):
        e.append("applicability.months must be a list of 1-12")
    for r in app.get("regions", ["any"]):
        if r not in REGIONS:
            e.append(f"applicability.regions: {r!r}")
    for w in app.get("waterbodyTypes", ["any"]):
        if w not in WATERBODIES:
            e.append(f"applicability.waterbodyTypes: {w!r}")

    kind = g("kind")
    if kind == "RESPONSE":
        f = g("feature") or {}
        spec = ft.REGISTRY.get(f.get("featureId"))
        if spec is None:
            e.append(f"feature.featureId {f.get('featureId')!r} is not a registered feature")
        else:
            sts = f.get("states")
            if not sts or any(s not in spec["states"] for s in sts):
                e.append(f"feature.states must be a non-empty subset of {list(spec['states'])}")
            if spec["availability"] == "AREA":
                e.append("RESPONSE rules cannot target an area-level habitat class; use a HABITAT rule")
            if f.get("featureId") == "spawnWindow":
                e.append("spawnWindow is derived from a PHENOLOGY rule")
        if g("response") not in RESPONSES:
            e.append(f"response must be one of {RESPONSES}")
    elif kind == "HABITAT":
        h = g("habitat") or {}
        if h.get("habitatClass") not in ft.HABITAT_CLASSES:
            e.append(f"habitat.habitatClass must be one of {ft.HABITAT_CLASSES}")
        if h.get("direction") not in DIRECTIONS:
            e.append(f"habitat.direction must be one of {DIRECTIONS}")
        if h.get("depthClass") is not None and h["depthClass"] not in ft.DEPTH_CLASSES:
            e.append(f"habitat.depthClass must be one of {ft.DEPTH_CLASSES}")
        for rq in g("requires", []) or []:
            spec = ft.REGISTRY.get(rq.get("featureId"))
            if spec is None or not rq.get("states") or any(s not in spec["states"] for s in rq["states"]):
                e.append(f"requires: bad feature/states {rq!r}")
    elif kind == "PHENOLOGY":
        p = g("phenology") or {}
        if p.get("event") != "spawn":
            e.append("phenology.event must be 'spawn'")
        t = p.get("tempC") or {}
        if not all(isinstance(t.get(k), (int, float)) for k in ("min", "max")) or t.get("min", 0) >= t.get("max", 0):
            e.append("phenology.tempC needs numeric min < max (a RANGE; no single optimum is allowed)")
        if "optimalC" in p or "peakC" in p:
            e.append("no single optimum/peak temperature: preserve the range")

    ev = g("evidence") or []
    if not ev:
        e.append("evidence is required (rules must trace to the private evidence bundle)")
    for i, x in enumerate(ev):
        for k in ("evidenceId", "packet", "sourceNo", "readStatus", "streamId", "directness", "counts"):
            if k not in x:
                e.append(f"evidence[{i}] missing {k}")
        if x.get("readStatus") not in READ_STATUS:
            e.append(f"evidence[{i}].readStatus {x.get('readStatus')!r}")
        if x.get("directness") not in DIRECTNESS:
            e.append(f"evidence[{i}].directness")
        if x.get("counts") and x.get("readStatus") not in COUNTING_READ:
            e.append(f"evidence[{i}] counts but readStatus {x.get('readStatus')} is not a read source (snippet-only/unopened never count)")
    if g("status") in USABLE_STATUSES:
        if not any(x.get("counts") and x.get("readStatus") in ("READ-FULL", "READ-ABSTRACT", "PROFILE-REVIEWED") for x in ev):
            e.append("RECONCILED/APPROVED needs at least one counting, read source")
    if g("status") == "APPROVED" and not (g("review") or {}).get("reviewer"):
        e.append("APPROVED needs review.reviewer")
    if g("confidence") in CONFIDENCE and CONFIDENCE.index(g("confidence")) > CONFIDENCE.index(max_confidence(rule)):
        e.append(f"confidence {g('confidence')} exceeds what {len(counting_streams(rule))} independent stream(s) support ({max_confidence(rule)})")
    if tr == "TRANSFERS" and not any(x.get("counts") and x.get("southeast") for x in ev):
        e.append("transferability TRANSFERS needs a counting evidence stream flagged southeast")
    return e


def validate_rule_set(rules: list[dict]) -> list[str]:
    errs, seen = [], set()
    for r in rules:
        key = (r.get("ruleId"), r.get("ruleVersion"))
        if key in seen:
            errs.append(f"duplicate rule {key}")
        seen.add(key)
        errs += [f"{r.get('ruleId')}: {m}" for m in validate_rule(r)]
    return errs


class RuleSet:
    """Rules for many species, indexed. Validated on construction (fail closed).

    `retired` supersedes a frozen rule WITHOUT touching its content: [{ruleId, ruleVersion, supersededBy:{ruleId, ruleVersion}|None, reason, retiredAt}].
    A retired (ruleId, version) stays in `rules` (and in the frozen register, for audit) but is never active, so a revised rule gets a new
    version and a new frozen identity instead of being edited after it was frozen."""

    def __init__(self, rules: list[dict], rules_version: str, source: str = "memory", retired: list[dict] | None = None):
        errs = validate_rule_set(rules)
        keys = {(r["ruleId"], r["ruleVersion"]): r for r in rules}
        self.retired: dict[tuple, dict] = {}
        for x in retired or []:
            k = (x.get("ruleId"), x.get("ruleVersion"))
            sb = x.get("supersededBy")
            if k not in keys:
                errs.append(f"retired rule {k} does not exist")
            elif sb is not None:
                sk = (sb.get("ruleId"), sb.get("ruleVersion"))
                if sk not in keys or sb.get("ruleId") != x["ruleId"] or not sb.get("ruleVersion", 0) > x["ruleVersion"] or keys[sk]["speciesId"] != keys[k]["speciesId"]:
                    errs.append(f"retired rule {k}: supersededBy must be a later version of the same rule")
            if not x.get("reason"):
                errs.append(f"retired rule {k} needs a reason")
            self.retired[k] = x
        if errs:
            raise RuleError("; ".join(errs[:8]) + (f" (+{len(errs) - 8} more)" if len(errs) > 8 else ""))
        self.rules_version, self.source = rules_version, source
        self.rules = list(rules)
        self.by_species: dict[str, list[dict]] = {}
        for r in rules:
            self.by_species.setdefault(r["speciesId"], []).append(r)

    def is_active(self, r: dict) -> bool:
        return (r["ruleId"], r["ruleVersion"]) not in self.retired

    def active_rules(self) -> list[dict]:
        return [r for r in self.rules if self.is_active(r)]

    def for_species(self, sid: str, statuses=USABLE_STATUSES) -> list[dict]:
        return [r for r in self.by_species.get(sid, []) if r["status"] in statuses and self.is_active(r)]

    def counts(self, sid: str) -> dict:
        rs = [r for r in self.by_species.get(sid, []) if self.is_active(r)]
        return {"usable": sum(r["status"] in USABLE_STATUSES for r in rs), "draft": sum(r["status"] == "DRAFT" for r in rs), "total": len(rs),
                "retired": sum(not self.is_active(r) for r in self.by_species.get(sid, []))}


def load_rules_dir(root: str) -> RuleSet:
    """`root/rules_manifest.json` lists `{path, sha256, bytes}`; each file is {speciesId, rules:[...]}. Hash mismatch -> RuleError."""
    with open(os.path.join(root, "rules_manifest.json"), "rb") as fh:
        man = json.loads(fh.read())
    rules = []
    for f in man["files"]:
        raw = open(os.path.join(root, f["path"]), "rb").read()
        if hashlib.sha256(raw).hexdigest() != f["sha256"] or len(raw) != f["bytes"]:
            raise RuleError(f"rules file hash/size mismatch: {f['path']}")
        doc = json.loads(raw)
        rules += doc["rules"]
    return RuleSet(rules, man["rulesVersion"], source=root, retired=man.get("retired"))


# ---------------------------------------------------------------- applicability
def applicable(rule: dict, ctx: dict, check_season: bool = True) -> tuple[bool, str]:
    """ctx = {month, region, waterbodyType}. A rule with no months applies in every month."""
    app = rule.get("applicability") or {}
    months = app.get("months")
    if check_season and months and ctx.get("month") is not None and ctx["month"] not in months:
        return False, "season"
    regions = app.get("regions", ["any"])
    if "any" not in regions and ctx.get("region") not in regions:
        return False, "region"
    wb = app.get("waterbodyTypes", ["any"])
    if "any" not in wb and ctx.get("waterbodyType") not in wb:
        return False, "waterbody"
    if rule.get("lifeStage", "ADULT") == "JUVENILE":
        return False, "lifeStage"
    return True, ""


def _down(c: str) -> str:
    return CONFIDENCE[max(0, CONFIDENCE.index(c) - 1)]


def evaluate_responses(rules: list[dict], feats: dict, ctx: dict) -> list[dict]:
    """Species x feature response bands. A band is emitted only for features that at least one applicable rule covers."""
    covered: dict[str, list[dict]] = {}
    for r in rules:
        if r["kind"] != "RESPONSE":
            continue
        ok, _ = applicable(r, ctx)
        if ok:
            covered.setdefault(r["feature"]["featureId"], []).append(r)
    out = []
    for fid, rs in sorted(covered.items()):
        fe = feats.get(fid) or {"state": ft.UNKNOWN, "reason": "feature not evaluated"}
        base = {"featureId": fid, "featureState": fe["state"]}
        if fe["state"] == ft.UNKNOWN:
            out.append(base | {"response": "UNKNOWN", "confidence": None, "reason": f"input unknown: {fe.get('reason')}",
                               "evidenceBasis": {"ruleIds": sorted(r["ruleId"] for r in rs)}})
            continue
        matched = [r for r in rs if fe["state"] in r["feature"]["states"]]
        if not matched:
            out.append(base | {"response": "UNKNOWN", "confidence": None, "reason": "no rule covers this feature state",
                               "evidenceBasis": {"ruleIds": sorted(r["ruleId"] for r in rs)}})
            continue
        resp = {r["response"] for r in matched}
        ids = sorted(r["ruleId"] for r in matched)
        if len(resp) > 1:
            out.append(base | {"response": "UNKNOWN", "confidence": None, "conflict": True,
                               "reason": "applicable rules disagree: " + ", ".join(f"{r['ruleId']}={r['response']}" for r in matched),
                               "evidenceBasis": {"ruleIds": ids}})
            continue
        conf = max((r["confidence"] for r in matched), key=CONFIDENCE.index)
        if fe.get("degraded"):
            conf = _down(conf)
        streams = {s for r in matched for s in counting_streams(r)}
        out.append(base | {
            "response": resp.pop(), "confidence": conf,
            "evidenceBasis": {"ruleIds": ids, "independentStreams": len(streams), "directness": sorted({x["directness"] for r in matched for x in r["evidence"] if x["counts"]})},
            "regionApplicability": {"ruleRegions": sorted({g for r in matched for g in (r.get("applicability") or {}).get("regions", ["any"])}),
                                    "requestedRegion": ctx.get("region"), "applies": True},
            "seasonApplicability": {"ruleMonths": sorted({m for r in matched for m in (r.get("applicability") or {}).get("months", [])}) or "all",
                                    "requestedMonth": ctx.get("month"), "applies": True},
            "transferability": min((r["transferability"]["southeastReservoir"] for r in matched), key=TRANSFER.index),
            "behavior": sorted({r["behavior"] for r in matched if r.get("behavior")}) or None,
            "reason": f"{ids[0] if len(ids) == 1 else str(len(ids)) + ' rules'} -> {fe['state']}"})
    for o in out:
        for k in [k for k, v in o.items() if v is None]:
            del o[k]
    return out


def evaluate_habitat(rules: list[dict], feats: dict, ctx: dict) -> list[dict]:
    """Habitat-class implications for Intelligence to apply per area. `requires` gates a rule on lake-level features."""
    out = []
    for r in rules:
        if r["kind"] != "HABITAT":
            continue
        ok, _ = applicable(r, ctx)
        if not ok:
            continue
        gate, unknown = "ACTIVE", []
        for rq in r.get("requires") or []:
            st = (feats.get(rq["featureId"]) or {}).get("state", ft.UNKNOWN)
            if st == ft.UNKNOWN:
                unknown.append(rq["featureId"])
            elif st not in rq["states"]:
                gate = "INACTIVE"
        if gate == "INACTIVE":
            continue
        h = r["habitat"]
        out.append({"habitatClass": h["habitatClass"], "direction": h["direction"], "depthClass": h.get("depthClass"),
                    "state": "CONDITIONAL_UNKNOWN" if unknown else "ACTIVE", "unknownInputs": unknown or None,
                    "confidence": r["confidence"], "transferability": r["transferability"]["southeastReservoir"],
                    "ruleId": r["ruleId"], "independentStreams": len(counting_streams(r)), "behavior": r.get("behavior")})
    # opposing directions for the same class/depth are surfaced as a conflict, not resolved
    seen: dict[tuple, set] = {}
    for h in out:
        seen.setdefault((h["habitatClass"], h["state"]), set()).add(h["direction"])
    for h in out:
        if len(seen[(h["habitatClass"], h["state"])]) > 1:
            h["conflict"] = True
    return [{k: v for k, v in h.items() if v is not None} for h in out]


def phenology_window(rules: list[dict], ctx: dict) -> dict | None:
    """The applicable spawn window ({months, tempC}) for a species, or None. Overlapping windows for one region are not
    merged or guessed: the first by ruleId is returned, so authors must not publish two for the same region."""
    ps = [r for r in rules if r["kind"] == "PHENOLOGY" and applicable(r, ctx, check_season=False)[0]]
    if not ps:
        return None
    p = sorted(ps, key=lambda r: r["ruleId"])[0]
    return {"months": (p.get("applicability") or {}).get("months"), "tempC": p["phenology"]["tempC"], "ruleId": p["ruleId"],
            "confidence": p["confidence"], "transferability": p["transferability"]["southeastReservoir"]}
