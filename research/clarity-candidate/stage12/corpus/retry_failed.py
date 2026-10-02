"""Addendum D retry: move aside result files whose crops failed with the osgeo-shim ogr error (before the fallback
existed) or whose item failed on a missing file (a SAFE shared by two items and deleted by the other); run_corpus.py then
reruns only those items."""
import json, glob, os, shutil
D = os.path.dirname(os.path.abspath(__file__)); os.makedirs(f"{D}/res_retried", exist_ok=True); n = 0
for f in glob.glob(f"{D}/res/*.json"):
    r = json.load(open(f))
    bad = ("No such file" in (r.get("error") or "")) or any("ogr.Open not implemented" in ((c.get("raw") or {}).get("error") or "") or
                                                              "No such file" in ((c.get("raw") or {}).get("error") or "") for c in r.get("crops", []))
    if bad: shutil.move(f, f"{D}/res_retried/{os.path.basename(f)}"); n += 1
print("moved for retry:", n)
