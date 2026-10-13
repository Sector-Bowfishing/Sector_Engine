"""Biological validation foundation: frozen rule register, prediction log, structured observations, honest evaluation.

Starts the validation clock without claiming validation. Local, append-only, hash-chained JSONL stores; nothing here
writes to a cloud service (where the production log will live is a separate decision).

  1. FrozenRuleRegister   a rule version is frozen BEFORE it is used in a prediction; a frozen (ruleId, version) can never change.
  2. PredictionLog        predictions are appended with the frozen rule hashes they used; no update/delete API; any edit
                          to the stored bytes breaks the hash chain and `verify()` reports it.
  3. Observations         structured Sector field observations (including NON-encounters and species-ID confidence).
  4. evaluate()           joins predictions to observations without ever re-reading a prediction after seeing an outcome,
                          reports counts and a naive-baseline lift, and refuses to claim anything below a stated sample size.

Evidence streams are never double counted: observations from one trip are one stream (tripId).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re

import features as ft
import rules as rl

GENESIS = "0" * 64


class LogError(ValueError):
    """The register/log is invalid, tampered with, or an append would violate immutability."""


def _h(obj) -> str:
    return hashlib.sha256(rl.canonical(obj)).hexdigest()


def _read(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _append(path: str, entry: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")


def _chain(entries: list[dict], what: str) -> None:
    prev = GENESIS
    for i, e in enumerate(entries):
        body = {k: v for k, v in e.items() if k != "entryHash"}
        if e.get("prevHash") != prev or e.get("entryHash") != _h(body):
            raise LogError(f"{what}: hash chain broken at entry {i} ({e.get('ruleId') or e.get('predictionId')})")
        prev = e["entryHash"]


def _iso(now: dt.datetime) -> str:
    return now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 1. frozen rule register
class FrozenRuleRegister:
    def __init__(self, path: str):
        self.path = path
        self.verify()

    def entries(self) -> list[dict]:
        return _read(self.path)

    def verify(self) -> int:
        es = self.entries()
        _chain(es, "frozen rule register")
        return len(es)

    def get(self, rule_id: str, version: int) -> dict | None:
        return next((e for e in self.entries() if e["ruleId"] == rule_id and e["ruleVersion"] == version), None)

    def freeze(self, rule: dict, now: dt.datetime, by: str) -> dict:
        errs = rl.validate_rule(rule)
        if errs:
            raise LogError(f"cannot freeze an invalid rule: {errs[0]}")
        if rule["status"] not in rl.USABLE_STATUSES:
            raise LogError("only RECONCILED/APPROVED rules can be frozen")
        h = rl.rule_hash(rule)
        prior = self.get(rule["ruleId"], rule["ruleVersion"])
        if prior:
            if prior["ruleSha256"] != h:
                raise LogError(f"{rule['ruleId']} v{rule['ruleVersion']} is already frozen with different content; bump ruleVersion")
            return prior
        es = self.entries()
        _chain(es, "frozen rule register")
        e = {"ruleId": rule["ruleId"], "ruleVersion": rule["ruleVersion"], "speciesId": rule["speciesId"], "ruleSha256": h,
             "frozenAt": _iso(now), "frozenBy": by, "prevHash": es[-1]["entryHash"] if es else GENESIS}
        e["entryHash"] = _h(e)
        _append(self.path, e)
        return e


# ---------------------------------------------------------------- 2. prediction log
PRED_FIELDS = ("lakeId", "speciesId", "predictedAt", "ruleRefs", "seasonState", "expected", "confidence", "evidenceBasis")
# Optional context frozen WITH the prediction so it can be judged later without hindsight (older entries predate these fields and stay valid).
PRED_OPTIONAL = ("zone", "environment", "inputs", "expectedResponses", "featuresVersion")
EXPECTED_KEYS = ("habitat", "depthClass", "movementState", "temperatureAlignment", "spawnState", "vegetationAssociation")


def validate_prediction(p: dict) -> list[str]:
    e = [f"missing {k}" for k in PRED_FIELDS if k not in p]
    if e:
        return e
    if not re.match(r"^[a-z][a-z0-9_]{1,63}$", str(p["speciesId"])):
        e.append("speciesId")
    if not p["ruleRefs"] or any(not {"ruleId", "ruleVersion", "ruleSha256"} <= set(r) for r in p["ruleRefs"]):
        e.append("ruleRefs must be non-empty {ruleId, ruleVersion, ruleSha256}")
    extra = set(p) - set(PRED_FIELDS) - set(PRED_OPTIONAL) - {"predictionId", "prevHash", "entryHash"}
    if extra:
        e.append(f"unexpected prediction keys {sorted(extra)}")
    if not isinstance(p["expected"], dict) or set(p["expected"]) - set(EXPECTED_KEYS):
        e.append(f"expected keys must be within {EXPECTED_KEYS}")
    if p["confidence"] not in rl.CONFIDENCE + ("UNKNOWN",):
        e.append("confidence")
    for h in (p["expected"] or {}).get("habitat", []) if isinstance(p.get("expected"), dict) else []:
        if h not in ft.HABITAT_CLASSES:
            e.append(f"expected.habitat {h!r}")
    return e


class PredictionLog:
    """Append-only. There is intentionally no update, delete, or outcome field here; outcomes live in observations."""

    def __init__(self, path: str, register: FrozenRuleRegister):
        self.path, self.register = path, register
        self.verify()

    def entries(self) -> list[dict]:
        return _read(self.path)

    def verify(self) -> int:
        es = self.entries()
        _chain(es, "prediction log")
        return len(es)

    def append(self, pred: dict) -> dict:
        errs = validate_prediction(pred)
        if errs:
            raise LogError("invalid prediction: " + "; ".join(errs))
        for r in pred["ruleRefs"]:
            fr = self.register.get(r["ruleId"], r["ruleVersion"])
            if not fr or fr["ruleSha256"] != r["ruleSha256"]:
                raise LogError(f"rule {r['ruleId']} v{r['ruleVersion']} is not frozen with that hash")
            if fr["frozenAt"] > pred["predictedAt"]:
                raise LogError(f"rule {r['ruleId']} was frozen after the prediction time")
        es = self.entries()
        _chain(es, "prediction log")
        pid = _h({k: pred[k] for k in PRED_FIELDS + PRED_OPTIONAL if k in pred})[:24]
        if any(e["predictionId"] == pid for e in es):
            raise LogError(f"prediction {pid} already logged (predictions are immutable and not duplicated)")
        e = dict(pred) | {"predictionId": pid, "prevHash": es[-1]["entryHash"] if es else GENESIS}
        e["entryHash"] = _h(e)
        _append(self.path, e)
        return e


def _activated(s: dict) -> bool:
    """A supported rule is genuinely ACTIVATED by the current state: a response band that is not UNKNOWN, an ACTIVE habitat rule, or the
    spawn window actually IN_WINDOW. Conditional-unknown habitat, TEMP_ONLY/OUTSIDE spawn states and UNKNOWN bands are not predictions."""
    return (any(r["response"] != "UNKNOWN" for r in s.get("responses", [])) or any(h["state"] == "ACTIVE" for h in s.get("habitat", []))
            or (s.get("spawnWindow") or {}).get("state") == "IN_WINDOW")


def predictions_from_state(state: dict, register: FrozenRuleRegister, rules_by_id: dict, now: dt.datetime) -> list[dict]:
    """Machine predictions from a Biological State: one per evaluated species with a genuinely activated, frozen rule.
    Each carries the environment it was made under, the expected response bands and the input versions."""
    env_keys = ("waterTempBand", "temperatureTrend", "stageTrend", "warmRise", "coldRise", "clarityBand", "daypart")
    env = {k: state["features"][k]["state"] for k in env_keys if k in state["features"]}
    inputs = {k: {x: v for x, v in d.items() if x in ("brainId", "status", "generatedAt", "ageHours", "brainVersion")} for k, d in state["inputs"].items()}
    out = []
    for s in state["species"]:
        if not s.get("evaluated") or not _activated(s):
            continue
        habitat = sorted({h["habitatClass"] for h in s.get("habitat", []) if h["direction"] == "FAVOR" and h["state"] == "ACTIVE"})
        depth = sorted({h["depthClass"] for h in s.get("habitat", []) if h["direction"] == "FAVOR" and h["state"] == "ACTIVE" and h.get("depthClass")})
        veg = [h["habitatClass"] for h in s.get("habitat", []) if h["habitatClass"] in ("shallowVegetatedHabitat", "floodedVegetation")
               and h["direction"] == "FAVOR" and h["state"] == "ACTIVE"]
        moves = sorted({b for r in s.get("responses", []) if r["response"] in ("FAVORABLE", "WORKABLE") for b in (r.get("behavior") or [])})
        used_ids = {r_id for r in s.get("responses", []) if r["response"] != "UNKNOWN" for r_id in r["evidenceBasis"]["ruleIds"]}
        used_ids |= {h["ruleId"] for h in s.get("habitat", []) if h["state"] == "ACTIVE"}
        sw = s.get("spawnWindow") or {}
        if sw.get("ruleId") and sw.get("state") == "IN_WINDOW":
            used_ids.add(sw["ruleId"])
        refs = []
        for rid in sorted(used_ids):
            r = rules_by_id.get(rid)
            fr = register.get(rid, r["ruleVersion"]) if r else None
            if fr and fr["ruleSha256"] == rl.rule_hash(r):
                refs.append({"ruleId": rid, "ruleVersion": r["ruleVersion"], "ruleSha256": fr["ruleSha256"]})
        if not refs:
            continue
        confs = [r["confidence"] for r in s.get("responses", []) if r["response"] != "UNKNOWN"] + [h["confidence"] for h in s.get("habitat", []) if h["state"] == "ACTIVE"]
        out.append({"lakeId": state["lakeId"], "speciesId": s["speciesId"], "predictedAt": _iso(now), "ruleRefs": refs, "zone": "LAKE",
                    "seasonState": s["seasonState"], "environment": env, "inputs": inputs, "featuresVersion": state["provenance"]["featuresVersion"],
                    "expectedResponses": [{"featureId": r["featureId"], "featureState": r["featureState"], "band": r["response"], "confidence": r.get("confidence")}
                                          for r in s.get("responses", []) if r["response"] != "UNKNOWN"],
                    "expected": {k: v for k, v in {"habitat": habitat, "depthClass": depth, "movementState": moves,
                                                   "temperatureAlignment": sw.get("state"), "spawnState": sw.get("state"),
                                                   "vegetationAssociation": veg}.items() if v},
                    "confidence": max(confs, key=rl.CONFIDENCE.index) if confs else "UNKNOWN",
                    "evidenceBasis": {"rulesVersion": state["provenance"]["rulesVersion"], "stateVersion": state["provenance"]["stateVersion"], "ruleCount": len(refs)}})
    return out


def is_repeat(entries: list[dict], pred: dict, window_hours: float = 24.0) -> bool:
    """True if the latest logged prediction for the same lake+species is materially identical and recent, so a re-run does not inflate the log."""
    def t(s):
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    prior = [e for e in entries if e["lakeId"] == pred["lakeId"] and e["speciesId"] == pred["speciesId"]]
    if not prior:
        return False
    last = prior[-1]
    same = all(last.get(k) == pred.get(k) for k in ("ruleRefs", "expected", "seasonState", "environment"))
    return same and (t(pred["predictedAt"]) - t(last["predictedAt"])).total_seconds() / 3600.0 < window_hours


# ---------------------------------------------------------------- 3. observations
SPECIES_ID_CONFIDENCE = ("CONFIRMED", "LIKELY", "GROUP_ONLY", "UNCERTAIN")
SPECIES_GROUPS = ("buffalo", "gar", "carp_asian", "carpsucker", "other")        # field-ID-unreliable groups
VEG = ("NONE", "SUBMERGED", "EMERGENT", "FLOODED", "UNKNOWN")
WIND_BANDS = ("CALM", "LIGHT", "MODERATE", "STRONG", "UNKNOWN")
LEVEL_CONTEXT = ("RISING", "STABLE", "FALLING", "UNKNOWN")
OBSERVER_CONF = ("HIGH", "MEDIUM", "LOW")
OBS_REQUIRED = ("observationId", "tripId", "observerId", "lakeId", "observedAt", "speciesId", "speciesIdConfidence", "encountered",
                "effortMinutes", "zone", "observerConfidence")


def validate_observation(o: dict) -> list[str]:
    e = [f"missing {k}" for k in OBS_REQUIRED if k not in o]
    if e:
        return e
    if o["speciesIdConfidence"] not in SPECIES_ID_CONFIDENCE:
        e.append("speciesIdConfidence")
    if o["speciesIdConfidence"] in ("GROUP_ONLY", "UNCERTAIN"):
        if o.get("speciesGroup") not in SPECIES_GROUPS:
            e.append("GROUP_ONLY/UNCERTAIN needs speciesGroup")
    elif not re.match(r"^[a-z][a-z0-9_]{1,63}$", str(o["speciesId"])):
        e.append("speciesId")
    if not isinstance(o["encountered"], bool):
        e.append("encountered must be a boolean (record NON-encounters too)")
    elif not o["encountered"] and o.get("count") not in (None, 0):
        e.append("count must be 0/absent when encountered is false")
    elif o["encountered"] and not (isinstance(o.get("count"), int) and o["count"] >= 1):
        e.append("encountered requires count >= 1")
    if not isinstance(o["effortMinutes"], (int, float)) or not 1 <= o["effortMinutes"] <= 720:
        e.append("effortMinutes must be 1-720 (effort is required so absence can be interpreted)")
    if o["zone"] not in ft.HABITAT_CLASSES + ("openWater", "unknown"):
        e.append(f"zone {o['zone']!r}")
    if o.get("depthClass") is not None and o["depthClass"] not in ft.DEPTH_CLASSES:
        e.append("depthClass")
    if o.get("vegetation") is not None and o["vegetation"] not in VEG:
        e.append("vegetation")
    if o.get("windBand") is not None and o["windBand"] not in WIND_BANDS:
        e.append("windBand")
    if o.get("levelContext") is not None and o["levelContext"] not in LEVEL_CONTEXT:
        e.append("levelContext")
    if o.get("clarityBand") is not None and o["clarityBand"] not in ft.REGISTRY["clarityBand"]["states"]:
        e.append("clarityBand")
    if o.get("waterTempF") is not None and not (30 <= o["waterTempF"] <= 105):
        e.append("waterTempF out of range")
    if o.get("spawnBehaviorObserved") not in (None, True, False, "UNKNOWN"):
        e.append("spawnBehaviorObserved")
    if o["observerConfidence"] not in OBSERVER_CONF:
        e.append("observerConfidence")
    if len(str(o.get("notes", ""))) > 280:
        e.append("notes max 280 chars")
    if re.search(r"@|\+?\d{3}[-. ]\d{3}[-. ]\d{4}", str(o.get("notes", ""))) or "@" in str(o.get("observerId")):
        e.append("no contact details: observerId must be pseudonymous and notes must not contain email/phone")
    return e


class ObservationStore:
    """Append-only, hash-chained like the prediction log (observations are evidence; edits would be silent corruption)."""

    def __init__(self, path: str):
        self.path = path
        self.verify()

    def entries(self) -> list[dict]:
        return _read(self.path)

    def verify(self) -> int:
        es = self.entries()
        self._chain_obs(es)
        return len(es)

    @staticmethod
    def _chain_obs(es):
        prev = GENESIS
        for i, e in enumerate(es):
            body = {k: v for k, v in e.items() if k != "entryHash"}
            if e.get("prevHash") != prev or e.get("entryHash") != _h(body):
                raise LogError(f"observation store: hash chain broken at entry {i}")
            prev = e["entryHash"]

    def append(self, obs: dict) -> dict:
        errs = validate_observation(obs)
        if errs:
            raise LogError("invalid observation: " + "; ".join(errs))
        es = self.entries()
        self._chain_obs(es)
        if any(e["observationId"] == obs["observationId"] for e in es):
            raise LogError("duplicate observationId")
        e = dict(obs) | {"prevHash": es[-1]["entryHash"] if es else GENESIS}
        e["entryHash"] = _h(e)
        _append(self.path, e)
        return e


# ---------------------------------------------------------------- 4. evaluation
def evaluate(predictions: list[dict], observations: list[dict], *, min_streams: int = 30, window_hours: float = 36.0) -> dict:
    """Score each confirmed/likely observation against the single latest prior prediction for that species and lake within `window_hours`.

    Reports counts only. `claim` stays 'INSUFFICIENT_EVIDENCE' until >= min_streams independent trips (tripId) have been
    compared; even then it is a hit-rate with a naive-baseline lift, not a validation verdict (the threshold for VALIDATED is a
    product/science decision). Group-level observations never score a species-level prediction."""
    def t(s):
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    scored, trips = [], set()
    for o in observations:
        if o["speciesIdConfidence"] not in ("CONFIRMED", "LIKELY"):
            continue                                   # group-level or uncertain IDs never score a species-level prediction
        ot = t(o["observedAt"])
        cands = [p for p in predictions if p["lakeId"] == o["lakeId"] and p["speciesId"] == o["speciesId"] and (p.get("expected") or {}).get("habitat")
                 and t(p["predictedAt"]) <= ot and (ot - t(p["predictedAt"])).total_seconds() / 3600.0 <= window_hours]
        if not cands:
            continue
        p = max(cands, key=lambda x: x["predictedAt"])   # ONE prediction per observation: the latest made before it (no double scoring)
        exp_h = p["expected"]["habitat"]
        scored.append({"predictionId": p["predictionId"], "tripId": o["tripId"], "encountered": o["encountered"], "hit": bool(o["encountered"] and o["zone"] in exp_h),
                       "predictedClasses": len(exp_h), "classesAvailable": len(ft.HABITAT_CLASSES)})
        trips.add(o["tripId"])
    enc = [s for s in scored if s["encountered"]]
    hit_rate = (sum(s["hit"] for s in enc) / len(enc)) if enc else None
    baseline = (sum(s["predictedClasses"] / s["classesAvailable"] for s in enc) / len(enc)) if enc else None
    return {"comparisons": len(scored), "encounterComparisons": len(enc), "independentTrips": len(trips),
            "hitRate": hit_rate, "naiveBaselineHitRate": baseline,
            "lift": (hit_rate / baseline) if hit_rate is not None and baseline else None,
            "claim": "INSUFFICIENT_EVIDENCE" if len(trips) < min_streams else "SAMPLE_REACHED_NOT_A_VALIDATION_VERDICT",
            "note": "Counts only. VALIDATED requires a decision on the success criterion; non-encounters are retained for effort-adjusted analysis."}
