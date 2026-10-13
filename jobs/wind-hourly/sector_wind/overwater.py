"""Observed-wind station import + over-water comparison (Stage 3A Track E). No hardware is bought here.

Generic format (CSV with '# key=value' header lines, or JSONL whose first line is {"meta": {...}}):

  stationId, network, lat, lon, timestampUTC, sensorHeightM, speedMS, directionFromDeg, gustMS,
  averagingSeconds, gustDefinition, airTemperatureC (optional), waterTemperatureC (optional), qcFlag

The file MUST declare `evidenceClass`: either `measured` or `SYNTHETIC — NOT SCIENTIFIC EVIDENCE`.
  - Sensor height is never assumed (no default 10 m): a row without it is rejected.
  - qcFlag: good | suspect | bad. `bad` rows are rejected; `suspect` rows are kept and counted separately.
  - Rows become WindSample(kind=observed) with the station, network, height and averaging carried along.
  - Synthetic files are stored under synthetic/ and are refused by `compare` unless the caller passes
    allow_synthetic=True (tests only); their output is stamped and can never reach `scoreboard`.

  python -m sector_wind.overwater import FILE --store local:$DIR
  python -m sector_wind.overwater compare --store local:$MIRROR --station ID --start 2026-11-01 --end 2026-11-30

Comparison: station observed vs RTMA-RU vs NBM +1/+3/+6/+12/+18 h, with bias, MAE, RMSE, circular direction
error, gust metrics, and stability splits when air and water temperatures exist. The station is compared
RAW at its own height. A 1/7-power height adjustment and the CEM R_L = 1.2 land-to-water factor appear only
as labelled sensitivity rows, never as the comparison itself (pre-registration §2.6, §3.3)."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .interp import CutoutIndex, blend, blend_wind
from .sample import Observed, iso, make_sample, parse_iso
from .validate import _metrics

SYNTHETIC = "SYNTHETIC — NOT SCIENTIFIC EVIDENCE"
MEASURED = "measured"
DECODER = "sector-wind overwater-import 1.0.0"
REQUIRED = ["stationId", "network", "lat", "lon", "timestampUTC", "sensorHeightM", "speedMS", "directionFromDeg", "gustMS",
            "averagingSeconds", "gustDefinition", "qcFlag"]
OPTIONAL = ["airTemperatureC", "waterTemperatureC"]
LEADS = (1, 3, 6, 12, 18)


def _num(v):
    if v is None or (isinstance(v, str) and v.strip() in ("", "null", "NA", "nan")):
        return None
    x = float(v)
    return None if math.isnan(x) else x


def parse(text: str, name: str = "") -> dict:
    meta, rows = {}, []
    if text.lstrip().startswith("{"):
        lines = [l for l in text.splitlines() if l.strip()]
        first = json.loads(lines[0])
        if "meta" in first:
            meta = first["meta"]; lines = lines[1:]
        rows = [json.loads(l) for l in lines]
    else:
        body = []
        for l in text.splitlines():
            if l.startswith("#"):
                k, _, v = l[1:].partition("=")
                meta[k.strip()] = v.strip()
            elif l.strip():
                body.append(l)
        rows = list(csv.DictReader(io.StringIO("\n".join(body))))
    ec = meta.get("evidenceClass")
    if ec not in (MEASURED, SYNTHETIC):
        raise ValueError(f"{name}: evidenceClass must be '{MEASURED}' or '{SYNTHETIC}' (got {ec!r})")
    good, rejected = [], []
    for i, r in enumerate(rows):
        why = [k for k in REQUIRED if k not in r or (r[k] in (None, "") and k not in ("gustMS", "directionFromDeg"))]
        try:
            t = parse_iso(r["timestampUTC"]) if "timestampUTC" in r else None
            h, s, d, g = _num(r.get("sensorHeightM")), _num(r.get("speedMS")), _num(r.get("directionFromDeg")), _num(r.get("gustMS"))
            avg = _num(r.get("averagingSeconds"))
        except Exception as e:
            rejected.append({"row": i, "reasons": [f"unparseable: {e!r}"]}); continue
        if h is None or h <= 0:
            why.append("sensorHeightM missing or <= 0 (never assumed)")
        if s is None or s < 0:
            why.append("speedMS missing or negative")
        if d is not None and not (0 <= d < 360):
            why.append("directionFromDeg outside [0, 360)")
        if g is not None and s is not None and g < s:
            why.append("gust below sustained speed")
        if avg is None or avg <= 0:
            why.append("averagingSeconds missing")
        qc = (r.get("qcFlag") or "").lower()
        if qc not in ("good", "suspect", "bad"):
            why.append(f"qcFlag {qc!r} not good|suspect|bad")
        if qc == "bad":
            why.append("qcFlag bad")
        if why:
            rejected.append({"row": i, "reasons": sorted(set(why))}); continue
        smp = make_sample(Observed(r["stationId"], r["network"], h, f"{int(avg)}-s"), t, datetime.now(timezone.utc),
                          float(r["lat"]), float(r["lon"]), s, d, g, f"import:{name}", DECODER)
        good.append({"sample": smp, "gustDefinition": r["gustDefinition"], "qc": qc,
                     "airTemperatureC": _num(r.get("airTemperatureC")), "waterTemperatureC": _num(r.get("waterTemperatureC"))})
    return {"meta": meta, "evidenceClass": ec, "accepted": good, "rejected": rejected}


def _row(x):
    s = x["sample"]
    return {"stationId": s.kind.station, "network": s.kind.network, "sensorHeightM": s.kind.sensorHeightM, "averaging": s.kind.averaging,
            "kind": s.kind.kind, "validTime": iso(s.validTime), "lat": s.lat, "lon": s.lon, "speedMS": s.speedMS, "dirFromDeg": s.dirFromDeg,
            "gustMS": s.gustMS, "isCalm": s.isCalm, "gustDefinition": x["gustDefinition"], "qc": x["qc"],
            "airTemperatureC": x["airTemperatureC"], "waterTemperatureC": x["waterTemperatureC"]}


def store_import(store, parsed: dict) -> dict:
    """Day files per station. Synthetic data lives under synthetic/ only."""
    base = "synthetic/overwater" if parsed["evidenceClass"] == SYNTHETIC else "overwater"
    by = defaultdict(list)
    for x in parsed["accepted"]:
        r = _row(x)
        by[(r["stationId"], r["validTime"][:10].replace("-", ""))].append(r)
    for (sid, day), rows in by.items():
        key = f"{base}/{sid}/{day}.json.gz"
        old = store.get_json(key) or {"rows": []}
        seen = {r["validTime"] for r in old["rows"]}
        merged = old["rows"] + [r for r in rows if r["validTime"] not in seen]
        store.put_json(key, {"schema": "sector-wind-overwater-v1", "evidenceClass": parsed["evidenceClass"], "station": sid,
                             "rows": sorted(merged, key=lambda r: r["validTime"])})
    return {"evidenceClass": parsed["evidenceClass"], "accepted": len(parsed["accepted"]), "rejected": len(parsed["rejected"]), "files": len(by)}


def load_station(store, sid, start, end, allow_synthetic=False):
    rows, classes = [], set()
    for base in (["overwater"] + (["synthetic/overwater"] if allow_synthetic else [])):
        d = start
        while d <= end:
            o = store.get_json(f"{base}/{sid}/{d:%Y%m%d}.json.gz")
            if o:
                classes.add(o["evidenceClass"]); rows += o["rows"]
            d += timedelta(days=1)
    return rows, classes


def _lake_for(cfg, lat, lon):
    for k, v in cfg["lakes"].items():
        b = v["bbox"]
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]:
            return k
    return None


def stability(r):
    if r.get("airTemperatureC") is None or r.get("waterTemperatureC") is None:
        return "unknown"
    d = r["airTemperatureC"] - r["waterTemperatureC"]
    return "unstable (air < water - 1 °C)" if d < -1 else "stable (air > water + 1 °C)" if d > 1 else "near-neutral"


def compare(store, cfg, sid, start, end, allow_synthetic=False) -> dict:
    rows, classes = load_station(store, sid, start, end + timedelta(days=1), allow_synthetic)
    if SYNTHETIC in classes and not allow_synthetic:
        raise PermissionError("synthetic rows present; refusing")
    if not rows:
        return {"station": sid, "n": 0, "note": "no observations in the window"}
    lake = _lake_for(cfg, rows[0]["lat"], rows[0]["lon"])
    if not lake:
        return {"station": sid, "n": len(rows), "note": "station outside every archived lake cut-out"}
    nbm_g = store.get_json(f"grids/nbm/{lake}.json"); rtma_g = store.get_json(f"grids/rtma/{lake}.json")
    wn = CutoutIndex(nbm_g["cells"], nbm_g["lat"], nbm_g["lon"], nbm_g["nx"]).weights(rows[0]["lat"], rows[0]["lon"])
    wr = CutoutIndex(rtma_g["cells"], rtma_g["lat"], rtma_g["lon"], rtma_g["nx"]).weights(rows[0]["lat"], rows[0]["lon"]) if rtma_g else None
    at_hour = {}
    for r in rows:
        t = parse_iso(r["validTime"])
        h = (t + timedelta(minutes=30)).replace(minute=0, second=0)
        if abs((t - h).total_seconds()) <= 600 and start <= h <= end + timedelta(hours=23):
            at_hour.setdefault(h, r)
    out = {"station": sid, "lake": lake, "evidenceClass": sorted(classes), "observations": len(at_hour),
           "comparison": "station RAW at its own sensor height vs 10 m forcing (no conversion)", "sources": {}, "byStability": {}, "sensitivity": {}}
    recs = defaultdict(list); stab = defaultdict(lambda: defaultdict(list))
    for h, r in sorted(at_hour.items()):
        o = (r["speedMS"], r["dirFromDeg"], r["gustMS"])
        if wr:
            a = store.get_json(f"rtma/{lake}/{h:%Y%m%d}/{h:%H%M}.json.gz")
            if a:
                s, d = blend_wind(a["speedMS"], a["dirFromDeg"], wr)
                if s is not None:
                    recs["RTMA-RU"].append((s, d, blend(a["gustMS"], wr), *o)); stab["RTMA-RU"][stability(r)].append(recs["RTMA-RU"][-1])
        for lead in LEADS:
            c = store.get_json(f"nbm/{lake}/{h - timedelta(hours=lead):%Y%m%d%H}.json.gz")
            st = next((x for x in (c or {}).get("steps", []) if x["leadHours"] == lead), None)
            if st:
                s, d = blend_wind(st["speedMS"], st["dirFromDeg"], wn)
                if s is not None:
                    k = f"NBM +{lead}h"
                    recs[k].append((s, d, blend(st["gustMS"], wn), *o)); stab[k][stability(r)].append(recs[k][-1])
    for k, v in recs.items():
        out["sources"][k] = _metrics(v)
        out["byStability"][k] = {s: _metrics(x) for s, x in stab[k].items()}
    h0 = rows[0]["sensorHeightM"]
    base = next((k for k in [f"NBM +{l}h" for l in LEADS] if k in recs), None)
    if base:
        pw = (10.0 / h0) ** (1 / 7)
        out["sensitivity"] = {
            "label": f"SENSITIVITY ONLY — not the comparison, not used by the Candidate (vs {base})",
            f"station adjusted to 10 m by 1/7 power (x{pw:.3f})": _metrics([(f, fd, fg, s * pw, d, (g * pw if g else None)) for f, fd, fg, s, d, g in recs[base]]),
            f"{base} forcing x R_L 1.2": _metrics([(f * 1.2, fd, (fg * 1.2 if fg else None), s, d, g) for f, fd, fg, s, d, g in recs[base]])}
    if SYNTHETIC in classes:
        out["BANNER"] = SYNTHETIC + " — software test output; never evidence, never scored"
    return out


def main(argv=None):
    from .store import open_store
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["import", "compare"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--store", required=True)
    ap.add_argument("--station"); ap.add_argument("--start"); ap.add_argument("--end")
    a = ap.parse_args(argv)
    store = open_store(a.store)
    if a.cmd == "import":
        p = parse(open(a.path).read(), os.path.basename(a.path))
        print(json.dumps({**store_import(store, p), "rejectedRows": p["rejected"][:20]}, indent=1))
    else:
        cfg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lakes.json")))
        s = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc); e = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc)
        print(json.dumps(compare(store, cfg, a.station, s, e), indent=1, default=str))


if __name__ == "__main__":
    main()
