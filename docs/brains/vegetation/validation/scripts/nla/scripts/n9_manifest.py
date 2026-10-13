"""Append bytes + sha256 for every new file of the NLA adoption experiment to MANIFEST.jsonl."""
import json, hashlib, sys
from pathlib import Path
H = Path(__file__).resolve().parents[1]; R = H.parents[2]
done = set()
for l in open(R/"MANIFEST.jsonl"):
    try: done.add(json.loads(l)["path"])
    except Exception: pass
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
rows = []
def add(p, kind, retention, src="local", note="note-07 NLA x S2 validation"):
    p = str(p)
    if p in done: return
    rows.append(dict(kind=kind, path=p, bytes=Path(p).stat().st_size, sha256=sha(p), source_url=src, retention=retention, note=note))
for f in sorted((H/"scripts").glob("*.py")): add(f, "script", "keep")
for f in sorted((H/"out").glob("*")):
    if f.is_file(): add(f, "result", "keep")
def agg(d, pat, kind, retention, src, note):
    fs = sorted(Path(d).glob(pat)); 
    if str(d) in done or not fs: return
    h = hashlib.sha256()
    for f in fs: h.update(sha(f).encode())
    rows.append(dict(kind=kind, path=str(d), bytes=sum(f.stat().st_size for f in fs), sha256=h.hexdigest(), source_url=src, retention=retention,
                     note=f"aggregate of {len(fs)} files; sha256 = sha256 of concatenated per-file sha256 in sorted order; {note}"))
agg(H/"out/cells", "*", "result", "keep", "local", "note-07 per-scene cell states + per-lake logs/status")
agg(H/"data/geom", "*", "data", "keep", "https://storage.googleapis.com/sector-lake-registry/lakes/<key>/geometry.v1.analysis.geojson.gz", "analysis polygons for the 79 bbox-hit lakes")
agg(H/"out/s2cache_nla", "*.npz", "s2_window_cache", "cache-deletable", "https://earth-search.aws.element84.com/v1 (sentinel-2-l2a / c1-l2a COG window reads)", "raw uint16 DN windows red/nir08/swir16/scl, note-07")
add(R/"notes/07_nla_sentinel2_validation.md", "report", "keep", note="note 07 deliverable")
with open(R/"MANIFEST.jsonl", "a") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
print("appended", len(rows))
