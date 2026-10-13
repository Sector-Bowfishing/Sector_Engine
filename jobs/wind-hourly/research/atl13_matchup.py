"""Stage 3C: ATL13 crossings (QC v1.1) vs the frozen Candidate at the crossing midpoint (diagnostic, Class B/D).

  python research/atl13_matchup.py OUT.json

One record per crossing (file, beam, lake): median of the UNIQUE SWH values (ATL13 repeats the long-segment value at
each short segment). Sector inputs from the NBM v5.0 corpus as they existed: the cycle initialised 1 h before the
nearest valid hour, lead +1; bilinear at the midpoint; duration from the 12 preceding +1 h steps (frozen rule);
fetch from the midpoint (open water, no standoff) with the frozen raster/ray code on the development-lake NHD polygon."""
import json, os, sys, subprocess
from datetime import datetime, timedelta, timezone
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.expanduser("~/Desktop/Development/iOS/sector-wind/scripts/wind"))
import build_fetch_tables as B
from sector_wind.store import LocalStore
from sector_wind.interp import CutoutIndex, blend_wind

ST = LocalStore(os.path.expanduser("~/Library/Caches/sector-wind/historical/v50"))
PTS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/icesat2/pilot_points.json")
WIND_CEM = os.path.expanduser("~/Library/Caches/sector-wind/swiftpm/release/wind-cem")
EPOCH = datetime(2018, 1, 1, tzinfo=timezone.utc)    # ATLAS SDP epoch; delta_time is GPS seconds since it (leap offset ignored, < 20 s)


def nbm_at(lake, vt, lat, lon):
    c = ST.get_json(f"nbm/{lake}/{vt - timedelta(hours=1):%Y%m%d%H}.json.gz")
    if not c:
        return None, None
    st = next((s for s in c["steps"] if s["leadHours"] == 1), None)
    g = ST.get_json(c["grid"]); w = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"]).weights(lat, lon)
    return blend_wind(st["speedMS"], st["dirFromDeg"], w) if st else (None, None)


def main(outp):
    from pyproj import Transformer
    P = [p for p in json.load(open(PTS))["points"] if p["qcPass"]]
    cross = {}
    for p in P:
        cross.setdefault((p["file"], p["beam"], p["lake"]), []).append(p)
    rasters, rows, recs = {}, [], []
    to = Transformer.from_crs(4326, 32616, always_xy=True).transform
    for (fn, beam, lake), v in sorted(cross.items()):
        uniq = sorted({round(q["swh"], 4) for q in v})
        swh = float(np.median(uniq)); lat = float(np.median([q["lat"] for q in v])); lon = float(np.median([q["lon"] for q in v]))
        t = EPOCH + timedelta(seconds=float(np.median([q["deltaTime"] for q in v])))
        vt = (t + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
        if not (datetime(2026, 5, 6, 1, tzinfo=timezone.utc) <= vt <= datetime(2026, 10, 7, tzinfo=timezone.utc)):
            continue
        u, d = nbm_at(lake, vt, lat, lon)
        if u is None:
            continue
        if lake not in rasters:
            wgs, utm, _, _ = B.load_geometry(lake); mask, origin = B.rasterize(utm); rasters[lake] = (mask, origin)
        mask, origin = rasters[lake]; x, y = to(lon, lat)
        fetch = B.nine_ray_mean(B.ray_table(mask, origin, np.array([x]), np.array([y]))[0], d) if d is not None else 0.0
        ser = []
        for k in range(12, -1, -1):
            uu, dd = nbm_at(lake, vt - timedelta(hours=k), lat, lon)
            ser.append({"speedMS": uu, "dirFromDeg": dd})
        rid = f"{fn}|{beam}|{lake}"
        rows.append({"id": rid, "windMS": u, "fetchM": fetch, "series": ser})
        recs.append({"id": rid, "lake": lake, "timeUTC": t.isoformat(), "local": (t - timedelta(hours=5)).strftime("%H:%M CDT"),
                     "atl13Swh": swh, "uniqueValues": len(uniq), "segments": len(v), "windMS": round(u, 2),
                     "dirFromDeg": None if d is None else round(d), "fetchM": round(fetch)})
    tmp = outp + ".rows.jsonl"; open(tmp, "w").write("".join(json.dumps(r) + "\n" for r in rows))
    subprocess.run([WIND_CEM, "--in", tmp, "--out", outp + ".pred.jsonl"], check=True)
    pred = {json.loads(l)["id"]: json.loads(l) for l in open(outp + ".pred.jsonl")}
    for r in recs:
        q = pred[r["id"]]; r.update({"sectorHm0": round(q["hm0MidM"], 4), "sectorClass": q["chopClass"], "regime": q["regime"]})
    o = np.array([r["atl13Swh"] for r in recs]); p = np.array([r["sectorHm0"] for r in recs])
    cls = lambda h: 1 + sum(h >= b for b in (0.0254, 0.0762, 0.1524, 0.3048))
    summ = {"crossings": len(recs), "atl13Swh": {"median": float(np.median(o)), "p10": float(np.percentile(o, 10)), "p90": float(np.percentile(o, 90)),
                                                 "atFloor0.02": int((o <= 0.021).sum())},
            "sectorHm0": {"median": float(np.median(p)), "p90": float(np.percentile(p, 90))},
            "bias_sector_minus_atl13": float((p - o).mean()), "mae": float(np.abs(p - o).mean()),
            "spearman": float(np.corrcoef(np.argsort(np.argsort(p)), np.argsort(np.argsort(o)))[0, 1]) if len(o) > 2 else None,
            "classAgreement": float(np.mean([cls(a) == cls(b) for a, b in zip(p, o)])),
            "note": "ATL13 RMSE ≈ 0.19–0.26 m vs buoys (Li et al. 2024); values below ~0.3 m are within noise. Diagnostic only (addendum v1: B/D)."}
    json.dump({"summary": summ, "crossings": recs}, open(outp, "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
