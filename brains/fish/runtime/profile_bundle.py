"""Species profiles for a whole bundle (still pure given the bundle's files). Used by the publisher dry-run, the generator CLI and tests.

Inputs are read from the bundle only: species profiles, `movement/<speciesId>.json` cards (with per-source verification), the rules + season assertions, the review ledger,
and the prediction / observation logs. If any of them changes, the profile changes; nothing else feeds a profile.
"""
from __future__ import annotations

import json

import features as ft
import species_profile as sp
import target_set as ts

FIELD_CANDIDATES = ("common_carp", "spotted_gar", "longnose_gar", "smallmouth_buffalo")      # proposed first field predictions; not an authorization


def _jsonl(raw: bytes | None) -> list[dict]:
    return [json.loads(x) for x in (raw or b"").decode().splitlines() if x.strip()]


def validation_counts(files: dict) -> dict:
    preds, obs, trips, last = {}, {}, {}, {}
    for p in _jsonl(files.get("validation/predictions.jsonl")):
        preds[p["speciesId"]] = preds.get(p["speciesId"], 0) + 1
    seen: dict = {}
    for o in _jsonl(files.get("validation/observations.jsonl")):
        s = o["speciesId"]
        obs[s] = obs.get(s, 0) + 1
        seen.setdefault(s, set()).add(o["tripId"])
        last[s] = max(last.get(s, ""), o["observedAt"])
    trips = {s: len(v) for s, v in seen.items()}
    return {"predictions": preds, "observations": obs, "trips": trips, "lastObservation": last, "validated": {}, "fieldCandidates": FIELD_CANDIDATES}


def ledger_decisions(files: dict) -> dict:
    out = {}
    for e in _jsonl(files.get("rules/review_ledger.jsonl")):
        out[e["ruleId"]] = e["decision"]
    return out


def profiles_from_bundle(b) -> dict:
    rs = b.ruleset
    ledger, val = ledger_decisions(b.files), validation_counts(b.files)
    gen = {"researchVersion": b.research_version, "rulesVersion": rs.rules_version if rs else None, "featuresVersion": ft.FEATURES_VERSION, "bundleCreatedAt": b.manifest.get("createdAt")}
    out = {}
    for sid, prof in sorted(b.profiles.items()):
        card = json.loads(b.files[f"movement/{sid}.json"]) if f"movement/{sid}.json" in b.files else None
        rules = [r for r in rs.by_species.get(sid, []) if rs.is_active(r)] if rs else []
        out[sid] = sp.build_profile(sid, profile=prof, card=card, rules=rules, ledger=ledger, validation=val, generated_from=gen, season_assertions=(rs.season_assertions if rs else {}))
    return out


def coverage_matrix(profiles: dict) -> dict:
    """Biological-wide structured matrix (targets first): species x category -> {coverage, confidence, priority}; plus per-species summary."""
    order = lambda s: ({"TARGET": 0, "SECONDARY": 1}.get(ts.role(s), 2), s)      # noqa: E731
    rows = []
    for sid in sorted(profiles, key=order):
        p = profiles[sid]
        rows.append({"speciesId": sid, "sectorLabel": p["identity"]["sectorLabel"], "role": p["identity"]["role"], "knowledgeStatus": p["summary"]["knowledgeStatus"],
                     "bowfisherKnowledge": p["summary"]["bowfisherKnowledge"], "speciesV2Score": p["summary"]["speciesV2Score"],
                     "categories": {c: {"coverage": v["status"], "completeness": v["completeness"], "evidence": v["evidence"], "priority": p["knowledgeGapMatrix"][c]["researchPriority"]} for c, v in p["knowledgeCoverage"].items()},
                     "topGap": (p["researchPriorities"]["top"] or [None])[0]})
    return {"contract": sp.CONTRACT, "categories": list(sp.CATEGORIES), "coverageVocabulary": list(sp.COVERAGE), "species": rows}
