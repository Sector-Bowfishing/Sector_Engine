import json, hashlib, os
from pathlib import Path
R = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain")
H = R/"experiments/adoption/prod_harness"
M = R/"MANIFEST.jsonl"
have = set()
for l in open(M):
    try: have.add(json.loads(l)["path"])
    except Exception: pass
rows = []
files = [p for p in H.rglob("*") if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")] + [R/"notes/06_production_observer_scoring.md"]
for p in sorted(files):
    if str(p) in have: continue
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    kind = "script" if p.suffix == ".py" else "report" if p.suffix == ".md" and p.parent.name == "notes" else "figure" if p.suffix == ".png" else "result" if p.suffix in (".json", ".md", ".log") else "cache" if p.suffix == ".npz" else "data"
    rows.append(dict(kind=kind, path=str(p), bytes=p.stat().st_size, sha256=h.hexdigest(),
                     source_url=("https://earth-search.aws.element84.com/v1 (sentinel-2-c1-l2a, Apr-Oct 2025, Guntersville)" if "guntersville" in p.name and p.suffix == ".npz" else "local"),
                     retention="keep" if kind != "cache" else "regenerable", note="note-06 production-observer scoring (adoption/prod_harness)"))
with open(M, "a") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
print(len(rows), "rows appended;", sum(r["bytes"] for r in rows) / 1e6, "MB")
