"""The Intelligence-facing view (v2 adds movementOutlook, freshness and validation) of one Biological State: flat, no research internals, no free text, no rule text.

Intelligence consumes THIS (or the identical `species[].responses[]` it is derived from); it never re-evaluates rules and never reads evidence.
Every band is Level 3 (Sector-derived predictive intelligence) with maturity NOT_VALIDATED until the validation record says otherwise.
`consumable` is False while the state is PILOT_INTERNAL: the shape is stable, the lifecycle decides whether anyone may use it.
Pure, stdlib only.
"""
from __future__ import annotations

import bands as bd
import bio_state as bs
import movement_outlook as mo
import target_set as ts

VIEW_VERSION = "biological-evaluated-view-v2"
SPECIES_STATUS = ("EVALUATED", "NOT_EVALUATED")


def intelligence_view(state: dict) -> dict:
    species = []
    for sp in state.get("species") or []:
        o = mo.species_outlook(sp)
        row = {"speciesId": sp["speciesId"], "role": ts.role(sp["speciesId"]),
               "movementOutlook": {"state": o["state"], "movement": o["movement"], "activity": o["activity"], "where": o["where"], "why": o["why"], "cautions": o["cautions"], "confidence": o["confidence"]},
               "status": "EVALUATED" if sp.get("evaluated") else "NOT_EVALUATED",
               "presenceState": (sp.get("presence") or {}).get("presenceState"), "knowledgeState": (sp.get("knowledge") or {}).get("state")}
        if not sp.get("evaluated"):
            row["bands"] = []
            species.append(row)
            continue
        row["bands"] = [{"featureId": r["featureId"], "featureState": r["featureState"], "band": r["response"],
                         "confidence": r.get("confidence"), "transferability": r.get("transferability"),
                         "independentStreams": (r.get("evidenceBasis") or {}).get("independentStreams")}
                        for r in sp.get("responses") or [] if r["response"] != "UNKNOWN"]
        row["unknownFeatures"] = sorted({r["featureId"] for r in sp.get("responses") or [] if r["response"] == "UNKNOWN"})
        row["spawnWindow"] = (sp.get("spawnWindow") or {}).get("state")
        species.append(row)
    return {"viewVersion": VIEW_VERSION, "lakeId": state["lakeId"], "generatedAt": state["generatedAt"], "stateVersion": state["stateVersion"],
            "stateFingerprint": bs.state_fingerprint(state), "rulesVersion": (state.get("provenance") or {}).get("rulesVersion"),
            "status": state["status"], "consumable": state["status"] != "PILOT_INTERNAL",
            "claim": {"level": 3, "maturity": (state.get("validation") or {}).get("status", "NOT_VALIDATED")},
            "inputStatus": {k: v.get("status") for k, v in (state.get("inputs") or {}).items()},
            "freshness": {k: {"status": v.get("status"), "ageHours": v.get("ageHours")} for k, v in (state.get("inputs") or {}).items()},
            "validation": {"status": (state.get("validation") or {}).get("status", "NOT_VALIDATED")}, "species": species}


def validate_view(v: dict) -> list[str]:
    """Problems with a view (empty = valid): shape, claim level, band vocabulary, no UNKNOWN band masquerading as a band."""
    e = []
    if v.get("viewVersion") != VIEW_VERSION:
        e.append("viewVersion")
    if (v.get("claim") or {}).get("level") != 3:
        e.append("species responses are Level 3 regardless of maturity")
    if v.get("status") == "PILOT_INTERNAL" and v.get("consumable") is not False:
        e.append("a PILOT_INTERNAL state is not consumable")
    for sp in v.get("species") or []:
        if sp.get("status") not in SPECIES_STATUS:
            e.append(f"{sp.get('speciesId')}: status")
        if sp.get("status") == "NOT_EVALUATED" and sp.get("bands"):
            e.append(f"{sp.get('speciesId')}: a not-evaluated species carries no bands")
        mo_ = sp.get("movementOutlook") or {}
        if mo_.get("state") not in mo.STATES:
            e.append(f"{sp.get('speciesId')}: movementOutlook.state")
        if sp.get("status") == "NOT_EVALUATED" and mo_.get("state") != "UNKNOWN":
            e.append(f"{sp.get('speciesId')}: a not-evaluated species has an UNKNOWN outlook")
        if mo_.get("state") == "UNKNOWN" and mo_.get("confidence") is not None:
            e.append(f"{sp.get('speciesId')}: an UNKNOWN outlook carries no confidence")
        for b in sp.get("bands") or []:
            if b.get("band") not in bd.BAND_VALUES or b.get("band") == "UNKNOWN":
                e.append(f"{sp.get('speciesId')}.{b.get('featureId')}: band")
    return e
