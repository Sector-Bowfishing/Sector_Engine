"""Score field data (Stage 3). Input: predictions.jsonl from `wind-eval` (the app's Candidate code,
evaluated as of each record's time). Practice records never count.

  python -m sector_wind.field_run calibration predictions.jsonl         # calibration share ONLY
  python -m sector_wind.field_run coverage predictions.jsonl            # stratification + blinding (no accuracy)
  python -m sector_wind.field_run certify predictions.jsonl FREEZE.json # holdout, once; refuses without a freeze

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


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    rows = load(path)
    if cmd == "coverage": print(json.dumps(coverage(rows), indent=1, default=str))
    elif cmd == "calibration": print(json.dumps(calibration(rows), indent=1, default=str))
    elif cmd == "certify":
        hold = [r for r in rows if r["split"] == "holdout" and r.get("predicted")]
        res = F.certify(sys.argv[4] if len(sys.argv) > 4 else ".", sys.argv[3],
                        [{"predicted": r["predicted"], "observed": r["observed"]} for r in hold], pairs_from(hold))
        print(json.dumps(res, indent=1))
