"""Run the CANONICAL Wind scorers against the ledger-derived metadata mirror (no live values opened; H2 sealed).
  1. Wind Certification: sector_wind.scoreboard.compute (frozen rubric v1) with the frozen evidence dir.
  2. BWIS v1: sector_wind.bowfishing_score (frozen definition) with SECTOR_WIND_LIVE_MIRROR -> metadata mirror.
Does NOT append to the private score log and does NOT touch Engine frozen-scores.json: it reports.
  python research/canonical_rescore.py META_MIRROR OUT.json"""
import json, os, subprocess, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind import scoreboard
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config

DOCS = os.path.expanduser("~/Desktop/Development/iOS/sector-wind/docs/intelligence/wind")
EVID = DOCS + "/stage3a/evidence"
LOG = DOCS + "/WIND_SCORE_CHANGE_LOG.jsonl"
mirror, out = sys.argv[1], sys.argv[2]
now = datetime.now(timezone.utc)
s = scoreboard.compute(LocalStore(mirror), load_config(), EVID, now)
prev = [json.loads(l) for l in open(LOG) if l.strip()][-1]
env = dict(os.environ, SECTOR_WIND_LIVE_MIRROR=mirror)
bw_path = out.replace(".json", "_bwis.json")
subprocess.run([sys.executable, "-m", "sector_wind.bowfishing_score", "--json", bw_path], env=env, check=True, capture_output=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
bw = json.load(open(bw_path))
prev_bwis = json.load(open(os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/bowfishing/bwis.json")))
dims_prev = prev["dimensionPoints"]
moved = {k: {"before": dims_prev.get(str(k)), "after": round(v["points"], 2), "why": v["why"]} for k, v in s["dimensions"].items() if abs((dims_prev.get(str(k)) or 0) - v["points"]) > 1e-6}
unchanged = [k for k in s["dimensions"] if k not in moved]
bw_moved = {k: {"before": round(prev_bwis["points"][k]["sum"], 2), "after": round(v["sum"], 2)} for k, v in bw["points"].items() if abs(prev_bwis["points"][k]["sum"] - v["sum"]) > 1e-6}
res = {"computedAt": s["computedAt"], "asOf": "metadata mirror (ledger-derived); H2 values not opened",
       "certification": {"previous": prev["newScore"], "previousRaw": prev["raw"], "new": s["official"], "newRaw": s["raw"], "rawPoints": s["rawPoints"], "caps": s["caps"],
                         "dimensionsChanged": moved, "dimensionsUnchanged": unchanged, "dimensions": {k: {"name": v["name"], "weight": v["weight"], "points": round(v["points"], 2), "credit": round(v["credit"], 3), "why": v["why"]} for k, v in s["dimensions"].items()}},
       "bwis": {"previous": prev_bwis["BWIS"], "previousTotal": round(prev_bwis["total"], 2), "new": bw["BWIS"], "newTotal": round(bw["total"], 2), "dimensionsChanged": bw_moved,
                "E": bw["metrics"]["E"]},
       "engineFrozenBlock": "docs/brains/scoring/frozen-scores.json (Wind 3.1 FROZEN 2026-10-12T06:16Z) is NOT updated by this script"}
json.dump(res, open(out, "w"), indent=1, default=str); print(scoreboard.render(s)); print(json.dumps({k: res[k] for k in ("certification", "bwis")}, indent=1, default=str)[:3500])
