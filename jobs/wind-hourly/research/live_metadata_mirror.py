"""Build a METADATA-ONLY mirror of the live archive for scoring reliability, from the ingest ledger and run summaries.
It never opens a live NBM/RTMA/METAR/state object: each cycle object is a stub {schema, initTime, retrievedAt, status} synthesised from the
ledger line that produced its final state, so the canonical scorer (which only reads those four keys for dimension 8) cannot touch H2 values.
  python research/live_metadata_mirror.py META_DIR OUT_DIR"""
import glob, gzip, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind import SCHEMA
RANK = {"complete": 3, "partial": 2, "failed": 0}

def build(meta, out):
    if os.path.exists(out):
        shutil.rmtree(out)
    best = {}
    for f in sorted(glob.glob(os.path.join(meta, "ledger", "runs", "*.jsonl"))):
        for ln in open(f):
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r["product"] not in ("NBM", "RTMA-RU"):
                continue
            k = (r["product"], r["cycle"], r["lake"])
            if k not in best or RANK.get(r["status"], 0) > RANK.get(best[k]["status"], 0) or (RANK.get(r["status"], 0) == RANK.get(best[k]["status"], 0) and r["at"] < best[k]["at"]):
                best[k] = r
    n = {"nbm": 0, "rtma": 0}
    for (prod, cyc, lake), r in best.items():
        if r["status"] not in ("complete", "partial"):
            continue
        if prod == "NBM":
            c = cyc.replace("-", "").replace(":", "").replace("T", "")[:10]
            p = os.path.join(out, "nbm", lake, f"{c}.json.gz"); os.makedirs(os.path.dirname(p), exist_ok=True)
            with gzip.open(p, "wt") as fh:
                json.dump({"schema": SCHEMA, "initTime": cyc, "retrievedAt": r["at"], "status": r["status"], "stub": "ledger-derived metadata; no values"}, fh)
            n["nbm"] += 1
        else:
            d, hm = cyc[:10].replace("-", ""), cyc[11:16].replace(":", "")
            p = os.path.join(out, "rtma", lake, d, f"{hm}.json.gz"); os.makedirs(os.path.dirname(p), exist_ok=True)
            with gzip.open(p, "wt") as fh:
                json.dump({"stub": True}, fh)
            n["rtma"] += 1
    for f in sorted(glob.glob(os.path.join(meta, "runs", "*", "*.json"))):
        j = json.load(open(f))
        keep = {"runAt": j.get("runAt"), "errors": j.get("errors", []), "nbm": {c: v for c, v in (j.get("nbm") or {}).items()}}      # nbm = {cycle: {lake: status}}
        p = os.path.join(out, "runs", os.path.basename(os.path.dirname(f)), os.path.basename(f)); os.makedirs(os.path.dirname(p), exist_ok=True)
        with gzip.open(p + ".gz", "wt") if False else open(p, "w") as fh:
            json.dump(keep, fh)
    return n

if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2]))
