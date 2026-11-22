"""Vegetation Brain output -> the vegetation shape Fish's input contract reads (contracts_in.vegetation_habitat_state).

Two upstream shapes are recognised; anything else is "not published" (UNKNOWN), never repaired:
  * the Vegetation Brain's published lake state (stateSchema `sector-brain-vegetation-state-v1`), and
  * the fleet "A6" lake answer the Vegetation all-lakes plan defines (2026-11-22, section 2 step 6: presence,
    sceneIds, acquisitionDates, oldestPassOn, sensor, observerVersion). That shape is PROVISIONAL until the Vegetation lane agrees it.

Mapping (Vegetation owns the plant state; Fish only translates it):
  * PRESENT       -> class from broadType (EMERGENT, FLOATING_LEAF/FLOATING_MAT -> FLOATING, otherwise SURFACE_REACHING_MIXED: not classified)
  * NOT_OBSERVED  -> NONE_SIGNIFICANT, density NONE
  * UNKNOWN       -> refusal, with Vegetation's own reason
  * density       -> Vegetation's coverageClass (SPARSE -> SCATTERED, MODERATE, DENSE) only when calibrated. NOT_CALIBRATED gives NO density: nothing
                     is derived from a plant fraction or share, because Vegetation's density gate has not passed.
  * tier          -> OBSERVED_SATELLITE for accepted-pass / persistence evidence, OBSERVED_SURVEY for a survey; a single un-accepted pass or no
                     evidence is not an observation.
  * observedAt    -> A6: oldestPassOn (else the earliest acquisition date); published state: surfaceVegetation.observedAt.

The age rule is NOT applied here. contracts_in.MAX_VEG_AGE_DAYS (45 days) decides freshness, unchanged; whether a last-season reading may be
used in winter is an open decision for Michael (Fish all-lakes plan, 2026-11-22, section 7 item 4).
"""
from __future__ import annotations

import datetime as dt

import contracts_in as ci

ADAPTER_VERSION = "fish-vegetation-adapter-v1"
VEG_STATE_SCHEMA = "sector-brain-vegetation-state-v1"
BROAD_TYPE_TO_CLASS = {"EMERGENT": "EMERGENT", "FLOATING_LEAF": "FLOATING", "FLOATING_MAT": "FLOATING"}
COVERAGE_TO_DENSITY = {"SPARSE": "SCATTERED", "MODERATE": "MODERATE", "DENSE": "DENSE"}
EVIDENCE_TO_TIER = {"SATELLITE_ACCEPTED_PASS": "OBSERVED_SATELLITE", "SATELLITE_PERSISTENCE": "OBSERVED_SATELLITE", "SURVEY": "OBSERVED_SURVEY"}

NOT_PUBLISHED = "VEG_NOT_PUBLISHED"
REFUSED = "VEG_REFUSED"
NOT_AN_OBSERVATION = "VEG_NOT_AN_OBSERVATION"


def _iso_date(v) -> str | None:
    """A date or date-time string -> an aware ISO date-time (a bare date is midnight UTC). Unparseable -> None (Fish then says 'no observation date')."""
    if not isinstance(v, str) or not v:
        return None
    try:
        t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _refusal(code: str, reason: str) -> dict:
    return {"cell": None, "reasonCode": code, "reason": reason}


def _cell(presence: str, broad_type, coverage, tier, observed_at, confidence, scene_ids, source: str) -> dict:
    if presence == "NOT_OBSERVED":
        cls, density = "NONE_SIGNIFICANT", "NONE"
    else:
        cls, density = BROAD_TYPE_TO_CLASS.get(broad_type, "SURFACE_REACHING_MIXED"), COVERAGE_TO_DENSITY.get(coverage)
    cell = {"class": cls, "density": density, "tier": tier, "observedAt": observed_at, "confidence": confidence, "scope": "LAKE",
            "sceneIds": list(scene_ids or []), "source": source, "adapterVersion": ADAPTER_VERSION}
    return {"cell": {k: v for k, v in cell.items() if v is not None or k in ("density", "tier", "observedAt")}, "reasonCode": None, "reason": None}


def _from_published(state: dict) -> dict:
    sv = state.get("surfaceVegetation") or {}
    obs = state.get("observation") or {}
    pres = sv.get("status")
    if pres not in ("PRESENT", "NOT_OBSERVED"):
        return _refusal(REFUSED, f"Vegetation reports {pres or 'no status'}: {sv.get('statusReason') or 'no reason given'}")
    tier = EVIDENCE_TO_TIER.get(obs.get("evidenceKind"))
    if tier is None:
        return _refusal(NOT_AN_OBSERVATION, f"evidence kind {obs.get('evidenceKind')!r} is not an accepted observation")
    conf = (sv.get("confidence") or {}).get("level") if isinstance(sv.get("confidence"), dict) else sv.get("confidence")
    return _cell(pres, sv.get("broadType"), sv.get("coverageClass"), tier, _iso_date(sv.get("observedAt")), conf,
                 (sv.get("source") or {}).get("sceneIds"), VEG_STATE_SCHEMA)


def _from_a6(ans: dict) -> dict:
    pres = ans.get("presence", ans.get("status"))
    if pres not in ("PRESENT", "NOT_OBSERVED"):
        return _refusal(REFUSED, f"Vegetation reports {pres or 'no presence'}: {ans.get('reason') or ans.get('statusReason') or 'no reason given'}")
    if not ans.get("sceneIds"):
        return _refusal(NOT_AN_OBSERVATION, "no scene ids: not a dated satellite observation")
    dates = [d for d in (_iso_date(x) for x in ans.get("acquisitionDates") or []) if d]
    observed = _iso_date(ans.get("oldestPassOn")) or (min(dates) if dates else None)
    return _cell(pres, ans.get("broadType"), ans.get("coverageClass"), "OBSERVED_SATELLITE", observed, ans.get("confidence"), ans.get("sceneIds"),
                 f"vegetation-a6:{ans.get('observerVersion') or 'unknown'}:{ans.get('sensor') or 'unknown'}")


def adapt(veg) -> dict:
    """-> {"cell": <contracts_in vegetation shape> | None, "reasonCode", "reason"}. A cell of None always carries a reason code."""
    if not isinstance(veg, dict) or not veg:
        return _refusal(NOT_PUBLISHED, "no vegetation state published for this lake")
    if veg.get("stateSchema") == VEG_STATE_SCHEMA:
        return _from_published(veg)
    if "oldestPassOn" in veg or "acquisitionDates" in veg:
        return _from_a6(veg)
    return _refusal(NOT_PUBLISHED, "unrecognised vegetation shape")


def vegetation_habitat(veg, habitat_class: str, now: dt.datetime) -> dict:
    """TRUE / FALSE / UNKNOWN for a vegetation-owned habitat class from a Vegetation output. Freshness is contracts_in's 45-day rule, unchanged."""
    a = adapt(veg)
    if a["cell"] is None:
        return {"state": ci.UNKNOWN, "reasonCode": a["reasonCode"], "reason": a["reason"]}
    return ci.vegetation_habitat_state(a["cell"], habitat_class, now)
