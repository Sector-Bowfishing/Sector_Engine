"""Field-truth scoring (pre-registration §3, §4, §6). Used in Stage 3; built and tested now so the
protocol cannot drift once data exists.

Calibration/holdout assignment is deterministic and fixed before any data exists."""
from __future__ import annotations

import hashlib
import json
import os
import random

SALT = "wind-stage2-salt-2026-10-06|"
CAL_SHARE = 40
TEXTURE_FLOOR = {"T1": 1, "T2": 2, "T3": 2, "T4": 3}


def session_id(lake: str, local_date: str, observer: str) -> str:
    return f"{lake}|{local_date}|{observer}"


def assignment(sid: str) -> str:
    h = int(hashlib.sha256((SALT + sid).encode()).hexdigest()[:8], 16)
    return "calibration" if h % 100 < CAL_SHARE else "holdout"


def predicted_class(chop_class: int, texture_state: str) -> int:
    """Scoring-only map onto the observed 5-level scale (§2.8). Not a product output."""
    return max(chop_class, TEXTURE_FLOOR[texture_state])


def severe_miss(p: int, o: int) -> bool:
    return (p == 1 and o >= 4) or (p >= 4 and o == 1) or abs(p - o) >= 3


def surface_metrics(rows: list[dict]) -> dict:
    """rows: {'predicted': int, 'observed': int}."""
    n = len(rows)
    if n == 0:
        return {"n": 0}
    ex = sum(r["predicted"] == r["observed"] for r in rows) / n
    pm1 = sum(abs(r["predicted"] - r["observed"]) <= 1 for r in rows) / n
    sev = sum(severe_miss(r["predicted"], r["observed"]) for r in rows) / n
    return {"n": n, "exact": ex, "within1": pm1, "severe": sev}


def concordance(pairs: list[dict], tie_ratio: float = 0.20, boot: int = 2000, seed: int = 7) -> dict:
    """pairs: {'session','hm0_A','hm0_B','obs_A','obs_B'} with A the bank predicted MORE exposed.
    Prediction ties (Hm0 within 20%) are excluded and counted."""
    elig, ties, lakes, quads = [], 0, set(), set()
    for p in pairs:
        hi, lo = max(p["hm0_A"], p["hm0_B"]), min(p["hm0_A"], p["hm0_B"])
        if hi <= 0 or (hi - lo) / hi < tie_ratio:
            ties += 1; continue
        a_more = p["hm0_A"] >= p["hm0_B"]
        oa, ob = (p["obs_A"], p["obs_B"]) if a_more else (p["obs_B"], p["obs_A"])
        elig.append((p["session"], 1.0 if oa > ob else 0.5 if oa == ob else 0.0))
        if p.get("lake"):
            lakes.add(p["lake"])
        if p.get("dirFromDeg") is not None:
            quads.add(int(((p["dirFromDeg"] + 45) % 360) // 90))
    if not elig:
        return {"n": 0, "predictionTies": ties}
    c = sum(v for _, v in elig) / len(elig)
    rng = random.Random(seed)
    sessions = sorted({s for s, _ in elig})
    by = {s: [v for ss, v in elig if ss == s] for s in sessions}
    bs = []
    for _ in range(boot):
        pick = [rng.choice(sessions) for _ in sessions]
        vals = [v for s in pick for v in by[s]]
        bs.append(sum(vals) / len(vals))
    bs.sort()
    return {"n": len(elig), "concordance": c, "ci95": [bs[int(0.025 * boot)], bs[int(0.975 * boot)]], "predictionTies": ties,
            "lakes": len(lakes), "quadrants": len(quads)}     # over eligible (non-tie) pairs; used by the addendum v1 credit


def certify(store_root: str, calibration_freeze: str, holdout_rows: list[dict], holdout_pairs: list[dict]) -> dict:
    """One-shot holdout evaluation. Refuses without a calibration freeze; appends to a ledger;
    refuses a second run for the same freeze hash."""
    if not os.path.exists(calibration_freeze):
        raise PermissionError("certification needs WIND_CALIBRATION_FREEZE.json (pre-registration §6)")
    fh = hashlib.sha256(open(calibration_freeze, "rb").read()).hexdigest()
    ledger = os.path.join(store_root, "ledger", "certification.jsonl")
    os.makedirs(os.path.dirname(ledger), exist_ok=True)
    if os.path.exists(ledger) and any(json.loads(l).get("freezeSha256") == fh for l in open(ledger) if l.strip()):
        raise PermissionError("this calibration freeze was already certified; a new run needs a new written stage")
    surf, conc = surface_metrics(holdout_rows), concordance(holdout_pairs)
    enough = surf.get("n", 0) >= 36 and conc.get("n", 0) >= 24
    res = {"freezeSha256": fh, "surface": surf, "exposure": conc, "sufficient": enough}
    with open(ledger, "a") as f:
        f.write(json.dumps(res) + "\n")
    return res


# ── Stage 3 AUXILIARY diagnostics ──────────────────────────────────────────────────────────────
# These never feed `certify`, `surface_metrics` or `concordance` (the frozen Dimension 6/7 metrics).
# They exist to explain failures: texture vs chop, shelter misses, geometry misses, pair contrast.

TEXTURE_ORDER = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}


def texture_metrics(rows: list[dict]) -> dict:
    """rows: {'predictedTexture': 'T1'..'T4', 'observedTexture': 'T1'..'T4'} (Stage 3 required field)."""
    rows = [r for r in rows if r.get("predictedTexture") in TEXTURE_ORDER and r.get("observedTexture") in TEXTURE_ORDER]
    if not rows:
        return {"n": 0}
    d = [TEXTURE_ORDER[r["predictedTexture"]] - TEXTURE_ORDER[r["observedTexture"]] for r in rows]
    return {"n": len(rows), "exact": sum(x == 0 for x in d) / len(d), "within1": sum(abs(x) <= 1 for x in d) / len(d),
            "meanSignedError": sum(d) / len(d)}   # > 0: Candidate predicts rougher texture than observed


def chop_only_metrics(rows: list[dict]) -> dict:
    """Chop class alone vs the observed 5-level class (diagnostic; the frozen map is predicted_class)."""
    rows = [r for r in rows if r.get("chopClass") and r.get("observed")]
    if not rows:
        return {"n": 0}
    d = [r["chopClass"] - r["observed"] for r in rows]
    return {"n": len(rows), "exact": sum(x == 0 for x in d) / len(d), "within1": sum(abs(x) <= 1 for x in d) / len(d),
            "meanSignedError": sum(d) / len(d)}   # > 0: CEM overpredicts chop


def tags(row: dict) -> list[str]:
    """Failure tags for analysis. possibleShelterMiss: Candidate rougher than observed where the observer
    saw shelter (bluff / tree line / lee shoreline). possibleGeometryMiss: rougher than observed with
    emergent vegetation or a shoreline the NHD polygon treats as open water."""
    out = []
    p, o = row.get("predicted"), row.get("observed")
    if p and o and p > o:
        if set(row.get("shelterFeatures") or []) & {"bluff", "tree line", "lee shoreline"}:
            out.append("possibleShelterMiss")
        if row.get("vegetationNoted") or "grass" in (row.get("notes") or "").lower():
            out.append("possibleGeometryMiss")
    if p and o and p < o:
        out.append("candidateUnderpredicts")
    return out


def pair_contrast(key: dict, a: dict, b: dict) -> dict:
    """Pair diagnostics (Stage 3 §19). key: sealed-key entries for X and Y; a/b: the two Candidate
    snapshots (fetchM, hm0M, windMS, texture)."""
    ratio = lambda x, y: (x / y) if (x and y) else None
    return {"fetchA": a.get("fetchM"), "fetchB": b.get("fetchM"), "fetchRatio": ratio(a.get("fetchM"), b.get("fetchM")),
            "hm0A": a.get("hm0M"), "hm0B": b.get("hm0M"), "hm0Ratio": ratio(a.get("hm0M"), b.get("hm0M")),
            "windDifferenceAtoB": (a.get("windMS") - b.get("windMS")) if a.get("windMS") is not None and b.get("windMS") is not None else None,
            "texturePredictionA": a.get("texture"), "texturePredictionB": b.get("texture")}
