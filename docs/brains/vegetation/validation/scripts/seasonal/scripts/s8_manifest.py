"""Append new files (bytes, sha256) to MANIFEST.jsonl: outputs/scripts/figs/geom/note per file; s2 caches aggregated per lake."""
import json, hashlib, glob, os
from common import *
M = R/"MANIFEST.jsonl"
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
rows = []
def add(kind, p, ret, note, src="local"):
    rows.append(dict(kind=kind, path=str(p), bytes=os.path.getsize(p), sha256=sha(p), source_url=src, retention=ret, note=note))
for p in sorted(glob.glob(str(H/"scripts/*"))):
    if os.path.isfile(p): add("script", p, "keep", "note-08 seasonal back-test script")
for p in sorted(glob.glob(str(H/"figs/*.png"))): add("figure", p, "keep", "note-08 seasonal back-test figure")
for p in sorted(glob.glob(str(H/"geom/*.gz"))): add("ground_truth_geometry", p, "regenerable", "registry analysis polygon", "https://storage.googleapis.com/sector-lake-registry/lakes/"+os.path.basename(p).split(".")[0]+"/geometry.v1.analysis.geojson.gz")
for p in sorted(glob.glob(str(H/"out/*"))):
    if os.path.isfile(p):
        k = "derived_summary" if p.endswith((".json", ".jsonl", ".md", ".csv", ".log")) else "derived_stack"
        add(k, p, "keep" if p.endswith((".json", ".jsonl", ".md")) else "regenerable", "note-08 seasonal back-test output")
add("report", R/"notes/08_seasonal_backtest.md", "keep", "note-08 seasonal back-test (observer A, accepted-pass belt share, LOYO climatology vs baselines)")
for d in sorted((H/"cache").iterdir()):
    fs = sorted(glob.glob(str(d/"*")))
    if d.name == "_pair": fs = sorted(glob.glob(str(d/"*/*.npz")))
    if not fs: continue
    hs = hashlib.sha256()
    for f in fs: hs.update(sha(f).encode())
    rows.append(dict(kind="s2_window_cache", path=str(d), bytes=sum(os.path.getsize(f) for f in fs), sha256=hs.hexdigest(), source_url="https://earth-search.aws.element84.com/v1 (sentinel-2-c1-l2a / sentinel-2-l2a)", retention="regenerable", note=f"aggregate of {len(fs)} files (per-scene int16 reflectance windows + stage-1 SCL json); sha256 = sha256 of concatenated per-file sha256 in sorted order"))
with open(M, "a") as f:
    for r in rows: f.write(json.dumps(r)+"\n")
print(len(rows), "rows appended")
