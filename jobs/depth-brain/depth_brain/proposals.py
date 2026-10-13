"""Validation + promotion of evidence PROPOSALS into the reviewed data files. Proposals come from evidence workers (research agents, scripts,
people). Nothing a proposal says is trusted: it must satisfy hard, versioned rules below, or it is REJECTED with a reason. Passing the rules
is necessary, not sufficient - promotion is explicit (`promote --apply`) and every promoted record is stamped with its proposal file.

The rules cannot be relaxed to raise counts: they are asserted by tests (`tests/test_proposals.py`)."""
from __future__ import annotations

import json
import os

import re

from .datum import normalize_datum


def datum_token(v):
    """Leading datum token of a descriptive string ('NGVD29 (USGS 62614 by parameter definition)' -> NGVD29). Free text beyond the token is ignored; no token -> None."""
    m = re.match(r"\s*(NGVD\s?29|NAVD\s?88|LOCAL|PROJECT)\b", str(v or ""), re.I)
    return normalize_datum(m.group(1).replace(" ", "")) if m else normalize_datum(v)

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RULES_VERSION = "proposal-rules-1"
PAIRING_METHODS = ("hartwell-pairing", "cwms-location", "a2w-project", "operator-doc")
ALLOWED_SIGMA_MIN = 0.1
PAIRING_MAX_ABS_MEAN_FT = 0.35        # a mean offset this large is closer to a datum shift (NAVD88-NGVD29 is often 0.3 - 1+ ft) than to noise
PAIRING_MAX_SD_FT = 0.25
PAIRING_MIN_N = 20


def _has_evidence(rec: dict) -> bool:
    ev = rec.get("evidence")
    return bool(ev) and all(isinstance(e, dict) and str(e.get("url", "")).startswith(("http://", "https://", "docs/", "jobs/")) for e in ev)


def validate_pairing(lid: str, rec: dict, manifest_by_id: dict) -> tuple[bool, str]:
    c = manifest_by_id.get(lid)
    if not c:
        return False, "lake not in manifest"
    if c["shiftPossible"]:
        return False, "lake already has a defensible shift"
    if rec.get("decision") not in ("SAME_DATUM", "SAME_SOURCE"):
        return False, f"decision {rec.get('decision')!r} is not a promotable relationship"
    if not _has_evidence(rec):
        return False, "no evidence URLs"
    if rec.get("confidence") not in ("high", "medium"):
        return False, f"confidence {rec.get('confidence')!r}"
    if rec.get("method") not in PAIRING_METHODS:
        return False, f"method {rec.get('method')!r} not allowed"
    sig = rec.get("sigmaFt")
    floor = 0.0 if rec["decision"] == "SAME_SOURCE" else ALLOWED_SIGMA_MIN          # same CWMS/operator record: zero datum sigma by construction
    if not isinstance(sig, (int, float)) or sig < floor:
        return False, "sigmaFt missing or below 0.1" if floor else "sigmaFt missing or negative"
    ld, rd = datum_token(rec.get("levelDatum")), datum_token(rec.get("referenceDatum"))
    if rec["decision"] == "SAME_SOURCE" and ld in ("NGVD29", "NAVD88") and rd in ("NGVD29", "NAVD88") and ld != rd:
        return False, "same-source proposal states two different datums"
    if rec["decision"] == "SAME_DATUM":
        if ld is None or rd is None or ld != rd or ld not in ("NGVD29", "NAVD88"):
            return False, "SAME_DATUM needs identical NGVD29/NAVD88 on both sides (LOCAL/PROJECT never qualifies)"
    st = rec.get("offsetStats")
    if rec["method"] == "hartwell-pairing":
        if not st:
            return False, "pairing needs offsetStats"
        if st.get("n", 0) < PAIRING_MIN_N:
            return False, f"n={st.get('n')} < {PAIRING_MIN_N}"
        if abs(st.get("meanFt", 99)) > PAIRING_MAX_ABS_MEAN_FT or st.get("sdFt", 99) > PAIRING_MAX_SD_FT:
            return False, "offset too large or too variable to call the same datum"
        if sig < max(0.15, abs(st["meanFt"])):
            return False, "sigma smaller than the observed offset"
    if "00065" in json.dumps(rec.get("summary", "")) and "elevation" not in json.dumps(rec.get("summary", "")).lower():
        return False, "00065 gage height is not an elevation"
    return True, "ok"


def validate_provider_rule(rule: dict, manifest_by_id: dict) -> tuple[bool, str, list]:
    if rule.get("decision") not in ("SAME_DATUM", "SAME_SOURCE"):
        return False, f"decision {rule.get('decision')!r} not promotable", []
    if not _has_evidence(rule):
        return False, "no evidence URLs", []
    ld, rd = normalize_datum(rule.get("levelDatum")), normalize_datum(rule.get("referenceDatum"))
    if rule["decision"] == "SAME_DATUM" and (ld is None or ld != rd or ld not in ("NGVD29", "NAVD88")):
        return False, "levels and references must be the same documented NGVD29/NAVD88", []
    sig = rule.get("sigmaFt")
    if not isinstance(sig, (int, float)) or sig < ALLOWED_SIGMA_MIN:
        return False, "sigmaFt missing or below 0.1", []
    lakes = [l for l in rule.get("lakes", []) if l in manifest_by_id and not manifest_by_id[l]["shiftPossible"]]
    if not lakes:
        return False, "no blocked manifest lakes in scope", []
    return True, "ok", lakes


def load(path):
    return json.load(open(path)) if os.path.exists(path) else None


def plan(manifest: dict, proposals_dir: str | None = None) -> dict:
    d = proposals_dir or os.path.join(DATA, "proposals")
    by_id = {c["lakeId"]: c for c in manifest["candidates"]}
    accepted, rejected = {}, []
    pp = load(os.path.join(d, "datum_pairings.json"))
    for lid, rec in ((pp or {}).get("lakes") or {}).items():
        ok, why = validate_pairing(lid, rec, by_id)
        if ok:
            accepted[lid] = {"status": rec["decision"], "sigmaFt": rec["sigmaFt"], "levelDatum": datum_token(rec.get("levelDatum")), "referenceDatum": datum_token(rec.get("referenceDatum")),
                             "summary": rec.get("summary", ""), "evidence": rec["evidence"], "caveat": rec.get("caveat"), "method": rec["method"], "confidence": rec.get("confidence"),
                             "offsetStats": rec.get("offsetStats"), "promotedFrom": "proposals/datum_pairings.json", "rulesVersion": RULES_VERSION}
        else:
            rejected.append({"lakeId": lid, "file": "datum_pairings.json", "reason": why})
    pr = load(os.path.join(d, "provider_rules.json"))
    for rule in (pr or {}).get("rules", []):
        ok, why, lakes = validate_provider_rule(rule, by_id)
        if not ok:
            rejected.append({"provider": rule.get("provider"), "file": "provider_rules.json", "reason": why})
            continue
        for lid in lakes:
            if lid in accepted:
                continue
            accepted[lid] = {"status": rule["decision"], "sigmaFt": rule["sigmaFt"], "levelDatum": rule.get("levelDatum"), "referenceDatum": rule.get("referenceDatum"),
                             "summary": f"provider rule {rule.get('provider')}: {rule.get('scope', '')}", "evidence": rule["evidence"], "caveat": rule.get("caveat"),
                             "method": "operator-doc", "confidence": rule.get("confidence", "medium"), "promotedFrom": "proposals/provider_rules.json", "rulesVersion": RULES_VERSION}
    return {"rulesVersion": RULES_VERSION, "accepted": accepted, "rejected": rejected}


def twdb_updates(path: str | None = None) -> dict:
    """Survey reference-pool verification: only `VERIFIED` with a PASSED preregistered validation enables effective zones."""
    d = load(path or os.path.join(DATA, "proposals", "twdb_reference_pools.json")) or {}
    out = {}
    for lid, r in (d.get("lakes") or {}).items():
        if r.get("referenceStatus") == "VERIFIED" and r.get("referencePoolFt") is not None and normalize_datum(r.get("referencePoolDatum")) and _has_evidence(r) \
                and (r.get("validation") or {}).get("passed") is True:
            out[lid] = {"referenceStatus": "VERIFIED", "referencePoolFt": float(r["referencePoolFt"]), "referencePoolDatum": normalize_datum(r["referencePoolDatum"]),
                        "surveyYear": r.get("surveyYear"), "evidence": r["evidence"]}
    return out


def promote(manifest: dict, overrides_path: str, apply: bool = False, proposals_dir: str | None = None) -> dict:
    res = plan(manifest, proposals_dir)
    cur = json.load(open(overrides_path)) if os.path.exists(overrides_path) else {}
    new = {k: v for k, v in res["accepted"].items() if k not in cur}
    res["newOverrides"] = len(new)
    if apply and new:
        cur.update(new)
        json.dump(cur, open(overrides_path, "w"), indent=1, sort_keys=True)
    return res
