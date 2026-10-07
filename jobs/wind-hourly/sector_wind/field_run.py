"""Score field data (Stage 3). Input: predictions.jsonl from `wind-eval` (the app's Candidate code,
evaluated as of each record's time). Practice records never count.

  python -m sector_wind.field_run calibration predictions.jsonl         # calibration share ONLY
  python -m sector_wind.field_run coverage predictions.jsonl            # stratification + blinding (no accuracy)
  python -m sector_wind.field_run certify predictions.jsonl FREEZE.json # holdout, once; refuses without a freeze
  python -m sector_wind.field_run gaps predictions.jsonl [--qa evaluated/*.qa.jsonl]   # what do we still need? (counts only)
  python -m sector_wind.field_run calstatus predictions.jsonl [--qa ...]              # may calibration run yet?
  python -m sector_wind.field_run diagnostics predictions.jsonl --raw raw/*/records.jsonl  # geometry/shelter misses, CALIBRATION share only

Holdout accuracy is never computed by `calibration` or `coverage` (pre-registration §6, Stage 3 §26)."""
import json, math, sys
from collections import Counter, defaultdict
from . import field as F

WIND_BINS = [(0, 2, "<2"), (2, 4, "2-4"), (4, 6.5, "4-6.5"), (6.5, 99, "6.5-9+")]
FETCH_BINS = [(0, 250, "<250 m"), (250, 1000, "250-1000 m"), (1000, 3000, "1-3 km"), (3000, 1e9, ">3 km")]


def load(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    rows = [r for r in rows if "practice" not in (r.get("tags") or [])]
    for r in rows:
        r["split"] = F.assignment(r["sessionId"])
        r["predicted"] = F.predicted_class(r["chopClass"], r["predictedTexture"]) if r.get("chopClass") and r.get("predictedTexture") else None
    return rows


def pairs_from(rows):
    by = defaultdict(list)
    for r in rows:
        if r.get("pairId") and r.get("hm0M") is not None:
            by[r["pairId"]].append(r)
    out = []
    for pid, rs in by.items():
        if len(rs) != 2: continue
        a, b = rs
        out.append({"session": a["sessionId"], "hm0_A": a["hm0M"], "hm0_B": b["hm0M"], "obs_A": a["observed"], "obs_B": b["observed"]})
    return out


def binof(v, bins):
    if v is None or (isinstance(v, float) and math.isnan(v)): return "unknown"
    return next(l for lo, hi, l in bins if lo <= v < hi)


def coverage(rows):
    n = len(rows)
    quad = lambda d: None if d is None else ["N", "E", "S", "W"][int(((d + 45) % 360) // 90)]
    per_bank = Counter(r.get("bankId") for r in rows); per_night = Counter(r["createdAtUTC"][:10] for r in rows)
    return {"n": n, "pairs": len(pairs_from(rows)),
            "wind": Counter(binof(r.get("windMS"), WIND_BINS) for r in rows),
            "fetch": Counter(binof(r.get("fetchM"), FETCH_BINS) for r in rows),
            "geometry": Counter(r.get("geometryType") or "unrecorded" for r in rows),
            "lakes": Counter(r["lake"] for r in rows), "quadrants": Counter(quad(r.get("dirFromDeg")) for r in rows),
            "maxBankShare": max(per_bank.values()) / n if n else None, "maxNightShare": max(per_night.values()) / n if n else None,
            "blinded": sum(r["observerWasBlinded"] for r in rows), "unknownPredictions": sum(r.get("predicted") is None for r in rows),
            "splits": Counter(r["split"] for r in rows)}


def calibration(rows):
    cal = [r for r in rows if r["split"] == "calibration" and r.get("predicted")]
    return {"split": "calibration", "surface": F.surface_metrics([{"predicted": r["predicted"], "observed": r["observed"]} for r in cal]),
            "exposure": F.concordance(pairs_from(cal)), "texture": F.texture_metrics(cal), "chopOnly": F.chop_only_metrics(cal),
            "tags": Counter(t for r in cal for t in F.tags(r))}


# ── Stage 3A: gaps, calibration readiness, miss diagnostics ────────────────────────────────────

GEOMETRY_TYPES = ["open main lake", "cove", "behind a point", "island-shielded", "creek arm"]
TARGETS = {"observations": 60, "pairs": 40, "lakes": 2, "quadrants": 3, "binShare": 0.10, "geometryEach": 5,
           "maxBankShare": 0.05, "maxNightShare": 0.15}
# Calibration readiness is NOT in the pre-registration. These are proposed thresholds (40% of each
# certification target, the calibration share) so the one-time calibration is not wasted on too little
# data. They decide only when to RUN calibration; Michael/ChatGPT confirm them before first use.
CAL_READY = {"observations": 24, "pairs": 16, "lakes": 2, "quadrants": 3, "binShare": 0.10}


def eligible_only(rows, qa_paths):
    """Keep rows whose record passed QA as ELIGIBLE (practice and ineligible never count)."""
    if not qa_paths:
        return rows, None
    import glob
    st = {}
    for p in qa_paths:
        for path in glob.glob(p):
            for l in open(path):
                if l.strip():
                    q = json.loads(l); st[q["recordId"]] = q
    keep = [r for r in rows if st.get(r.get("recordId"), {}).get("status") == "ELIGIBLE"]
    return keep, {"eligible": len(keep), "dropped": len(rows) - len(keep)}


def _mark(ok):
    return "\u2713" if ok else "NEED"


def gaps(rows) -> dict:
    """Stratification against the frozen §5 targets. Counts and shares only: no accuracy, either split."""
    c = coverage(rows)
    n = c["n"]
    sh = lambda counter, k: (counter.get(k, 0) / n) if n else 0.0
    out = {"observations": [n, TARGETS["observations"], _mark(n >= TARGETS["observations"])],
           "pairs": [c["pairs"], TARGETS["pairs"], _mark(c["pairs"] >= TARGETS["pairs"])],
           "wind": {lab: [round(sh(c["wind"], lab), 3), _mark(sh(c["wind"], lab) >= TARGETS["binShare"])] for _, _, lab in WIND_BINS},
           "fetch": {lab: [round(sh(c["fetch"], lab), 3), _mark(sh(c["fetch"], lab) >= TARGETS["binShare"])] for _, _, lab in FETCH_BINS},
           "geometry": {g: [c["geometry"].get(g, 0), TARGETS["geometryEach"], _mark(c["geometry"].get(g, 0) >= TARGETS["geometryEach"])] for g in GEOMETRY_TYPES},
           "quadrants": {q: _mark(c["quadrants"].get(q, 0) > 0) for q in "NESW"},
           "quadrantsCovered": [sum(c["quadrants"].get(q, 0) > 0 for q in "NESW"), TARGETS["quadrants"]],
           "lakes": [len([k for k in c["lakes"] if k]), TARGETS["lakes"], dict(c["lakes"])],
           "concentration": {"maxBankShare": c["maxBankShare"], "maxNightShare": c["maxNightShare"]},
           "splitCounts": dict(c["splits"]), "blinded": c["blinded"]}
    return out


def calstatus(rows) -> dict:
    cal = [r for r in rows if r["split"] == "calibration"]
    c = coverage(cal); n = c["n"]
    sh = lambda lab: (c["wind"].get(lab, 0) / n) if n else 0.0
    checks = {"records": (n, CAL_READY["observations"], n >= CAL_READY["observations"]),
              "pairs": (c["pairs"], CAL_READY["pairs"], c["pairs"] >= CAL_READY["pairs"]),
              "windStrata": ({lab: round(sh(lab), 3) for _, _, lab in WIND_BINS}, ">= 10% each", all(sh(lab) >= 0.10 for _, _, lab in WIND_BINS)),
              "fetchStrata": ({lab: c["fetch"].get(lab, 0) for _, _, lab in FETCH_BINS}, ">= 10% each",
                              n > 0 and all(c["fetch"].get(lab, 0) / n >= 0.10 for _, _, lab in FETCH_BINS)),
              "geometryStrata": ({g: c["geometry"].get(g, 0) for g in GEOMETRY_TYPES}, ">= 2 each (40% of 5)",
                                 all(c["geometry"].get(g, 0) >= 2 for g in GEOMETRY_TYPES)),
              "lakes": (len(c["lakes"]), CAL_READY["lakes"], len(c["lakes"]) >= CAL_READY["lakes"]),
              "directionQuadrants": (sum(c["quadrants"].get(q, 0) > 0 for q in "NESW"), CAL_READY["quadrants"],
                                     sum(c["quadrants"].get(q, 0) > 0 for q in "NESW") >= CAL_READY["quadrants"])}
    import os
    freeze_exists = os.path.exists("WIND_CALIBRATION_FREEZE.json")
    return {"checks": {k: {"have": v[0], "need": v[1], "pass": v[2]} for k, v in checks.items()},
            "readyForCalibration": all(v[2] for v in checks.values()) and not freeze_exists,
            "calibrationAlreadyFrozen": freeze_exists,
            "note": "readiness thresholds are proposed (not pre-registered); calibration may adjust only §6 (a)-(c), once"}


VEG = ("grass", "vegetation", "hydrilla", "milfoil", "lily", "lilies", "pads", "emergent", "reeds", "cattail", "button")
FEATURES = {"emergent vegetation": VEG, "marsh": ("marsh", "swamp", "wetland"), "shallow grass flat": ("flat", "flats", "shallow"),
            "pool extent / drawdown": ("drawdown", "pool", "flooded", "low water", "high water", "mudflat"),
            "creek mouth": ("creek mouth", "mouth of"), "island": ("island",)}


def diagnostics(rows, raw_paths) -> dict:
    """Where do possibleGeometryMiss / possibleShelterMiss cluster? CALIBRATION share only: tags compare
    prediction with observation, so they are accuracy information and the holdout stays sealed."""
    import glob
    raw = {}
    for p in raw_paths or []:
        for path in glob.glob(p):
            for l in open(path):
                if l.strip():
                    r = json.loads(l); raw[r.get("id")] = r
    cal = [r for r in rows if r["split"] == "calibration" and r.get("predicted")]
    for r in cal:
        x = raw.get(r.get("recordId"), {})
        r["notes"] = x.get("notes") or ""
        r["vegetationNoted"] = any(k in r["notes"].lower() for k in VEG)
    tagged = [(r, F.tags(r)) for r in cal]
    def cluster(tag):
        hit = [r for r, t in tagged if tag in t]
        feat = Counter()
        for r in hit:
            txt = r["notes"].lower()
            for name, keys in FEATURES.items():
                if any(k in txt for k in keys):
                    feat[name] += 1
            if r.get("geometryType") == "island-shielded":
                feat["island (geometry type)"] += 1
            if r.get("geometryType") == "creek arm":
                feat["creek arm (geometry type)"] += 1
            for s_ in r.get("shelterFeatures") or []:
                feat[f"shelter: {s_}"] += 1
        return {"n": len(hit), "of": len(cal), "features": dict(feat)}
    return {"split": "calibration only", "possibleGeometryMiss": cluster("possibleGeometryMiss"),
            "possibleShelterMiss": cluster("possibleShelterMiss"), "candidateUnderpredicts": cluster("candidateUnderpredicts"),
            "rule": "no algorithm change from these counts alone; a future stage needs a repeated, systematic pattern"}


def _opt(name):
    out, a = [], sys.argv
    for i, x in enumerate(a):
        if x == name and i + 1 < len(a):
            out.append(a[i + 1])
    return out


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    rows = load(path)
    if cmd in ("gaps", "calstatus", "diagnostics"):
        rows, info = eligible_only(rows, _opt("--qa"))
        if cmd == "gaps": print(json.dumps({"qa": info, **gaps(rows)}, indent=1, default=str))
        elif cmd == "calstatus": print(json.dumps({"qa": info, **calstatus(rows)}, indent=1, default=str))
        else: print(json.dumps(diagnostics(rows, _opt("--raw")), indent=1, default=str))
        sys.exit(0)
    if cmd == "coverage": print(json.dumps(coverage(rows), indent=1, default=str))
    elif cmd == "calibration": print(json.dumps(calibration(rows), indent=1, default=str))
    elif cmd == "certify":
        hold = [r for r in rows if r["split"] == "holdout" and r.get("predicted")]
        res = F.certify(sys.argv[4] if len(sys.argv) > 4 else ".", sys.argv[3],
                        [{"predicted": r["predicted"], "observed": r["observed"]} for r in hold], pairs_from(hold))
        print(json.dumps(res, indent=1))
