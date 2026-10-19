"""Shoreline exposure ranking and sheltered alternatives: the runtime interface to the FROZEN ranking rules.

No ranking logic is re-implemented here. Ordering, exposure rank, confidence, alternatives and reasons are exactly
`sector_wind.bowfishing.rank_banks_for_wind` / `evaluate_bank` / `nearby_alternatives` (frozen in BWIS v1 §Ranking). This module
only adapts inputs (runtime fetch objects, canonical lake ids), bounds the output, and attaches V2 semantics.
"""
from __future__ import annotations

from .. import bowfishing as BF
from ..brain.state import decode_fetch_table
from . import semantics as S

DEFAULT_TOP = 5
MAX_TOP = 25            # bounded payloads: the full ranking is an artifact (`full_ranking`), never inlined


def geometry(fetch_obj: dict, lake_id: str) -> dict:
    """Runtime fetch object (archive `fetch/…`, or a fixture with the same layout) -> the lake dict the frozen functions take."""
    banks, table = decode_fetch_table(fetch_obj)
    return {"lake": fetch_obj.get("lake"), "lakeId": lake_id, "banks": banks, "table": table,
            "tableSha256": fetch_obj.get("tableSha256"), "sourceTableSha256": fetch_obj.get("sourceTableSha256"),
            "geometry": fetch_obj.get("geometry"), "subset": fetch_obj.get("selection")}


def _index(L):
    if "_ix" not in L:
        L["_ix"] = {b["id"]: i for i, b in enumerate(L["banks"])}
    return L["_ix"]


def rank(L: dict, speed_ms: float, dir_from: float, duration_h: float = BF.STEADY_H, top: int = DEFAULT_TOP,
         bank_ids: tuple = (), alternatives: bool = True) -> dict:
    """Bounded shoreline answer for one wind: most sheltered, most exposed, requested banks, each with V2 semantics, plus
    sheltered alternatives for every HIGH/EXTREME bank shown. Unknown banks are counted and never ranked."""
    top = max(1, min(int(top), MAX_TOP))
    r = BF.rank_banks_for_wind(L, speed_ms, dir_from, None, duration_h, top=top)
    allr = r["all"]
    by_id = {x["bankId"]: x for x in allr}
    ix = _index(L)

    def v2(row):
        out = S.describe(row, L["lakeId"], speed_ms, duration_h)
        if alternatives and row.get("exposureRank") in S.EXPOSED:
            out["lessExposedAlternatives"] = [_alt(a) for a in BF.nearby_alternatives(L, allr, row)]
            out["nearestSheltered"] = nearest_sheltered(allr, row)
        return out

    requested, missing = [], []
    for bid in bank_ids:
        if bid in by_id:
            requested.append(v2(by_id[bid]))
        elif bid in ix:            # below resolution: evaluate_bank returns the frozen UNKNOWN row
            requested.append(v2(BF.evaluate_bank(L, ix[bid], speed_ms, dir_from, duration_h)))
        else:
            missing.append(bid)
    sheltered = [v2(x) for x in r["best"] if x["exposureRank"] in S.SHELTERED]
    exposed = [v2(x) for x in r["worst"] if x["exposureRank"] in S.EXPOSED]
    return {"sheltered": sheltered, "exposed": exposed, "requested": requested, "requestedNotFound": missing,
            "_all": allr}


ACCESS_NOTE = ("Straight-line distance on the same lake. Less wind exposure only: not checked for fish, access, launch, "
               "private property, navigation or safety.")
SHELTER_RADIUS_M = 10000


def _alt(a: dict) -> dict:
    """One FROZEN nearby alternative (BWIS v1: lower surface class, or >= 50 % shorter fetch and no worse class, nearest first
    within 2 / 5 / 10 km). Frozen rule = LESS exposed, which is not necessarily sheltered."""
    code = a["exposureRank"]
    return {"bankId": a["bankId"], "distanceM": a["distanceM"], "searchRadiusM": a["radiusM"],
            "windExposure": {"code": code, "label": S.EXPOSURE_LABEL[code]}, "effectiveFetchM": a["effectiveFetchM"],
            "predictedSurfaceLabel": S.SURFACE_LABEL[next(k for k, v in BF.CHOP.items() if v == a["predictedSurfaceLabel"])],
            "reason": a["reason"], "rule": "frozen BWIS v1 nearby alternative", "note": ACCESS_NOTE}


def nearest_sheltered(allr: list, bank: dict, n: int = 3, radius_m: float = SHELTER_RADIUS_M) -> list[dict]:
    """V2 rule (knowledgeVersion 1.0.0): the nearest banks within 10 km whose exposure for THIS wind is Sheltered or Low
    (modeled waves < 3 in), nearest first. Uses the same ranked rows as the frozen rules; UNKNOWN banks never qualify
    (they are not in the ranked rows)."""
    c = []
    for r in allr:
        if r["bankId"] == bank["bankId"] or r["exposureRank"] not in S.SHELTERED:
            continue
        dist = BF.km(r["anchor"], bank["anchor"])
        if dist <= radius_m:
            c.append((dist, r))
    c.sort(key=lambda t: (t[0], t[1]["predictedSurfaceClass"]))
    return [{"bankId": r["bankId"], "distanceM": round(dist), "windExposure": {"code": r["exposureRank"], "label": S.EXPOSURE_LABEL[r["exposureRank"]]},
             "effectiveFetchM": r["effectiveFetchM"], "waveHeightIn": round(r["predictedHm0In"], 1),
             "predictedSurfaceLabel": S.SURFACE_LABEL[r["predictedSurfaceClass"]], "reason": r["reason"],
             "rule": "V2 nearest sheltered (exposure Sheltered/Low within 10 km)", "note": ACCESS_NOTE} for dist, r in c[:n]]


def lake_summary(allr: list, L: dict) -> dict:
    n = len(allr)
    unknown = sum(1 for b in L["banks"] if b.get("belowResolution"))
    counts = {k: sum(1 for x in allr if x["exposureRank"] == k) for k in S.EXPOSURE_LABEL if k != "UNKNOWN"}
    boundary = sum(1 for x in allr if x["confidence"] == "boundary")
    return {"resolvableBanks": n, "unknownBanks": unknown, "exposureCounts": counts,
            "shelteredPct": round(100.0 * (counts["PROTECTED"] + counts["LOW_EXPOSURE"]) / n, 1) if n else None,
            "exposedPct": round(100.0 * (counts["HIGH_EXPOSURE"] + counts["EXTREME_EXPOSURE"]) / n, 1) if n else None,
            "boundaryPct": round(100.0 * boundary / n, 1) if n else None,
            "geometryScope": "subset" if L.get("subset") else "full lake table"}


def full_ranking(allr: list, lake_id: str) -> list[dict]:
    """Every resolvable bank, compact, for a storage artifact (never inlined in the decision)."""
    return [{"bankId": x["bankId"], "exposure": x["exposureRank"], "surfaceClass": x["predictedSurfaceClass"],
             "waveHeightIn": x["predictedHm0In"], "effectiveFetchM": x["effectiveFetchM"], "lakePercentile": x["relativeLakePercentile"],
             "confidence": x["confidence"]} for x in allr]
