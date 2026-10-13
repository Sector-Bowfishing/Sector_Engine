import sys, json, re
from common import *
rx = re.compile(sys.argv[1], re.I); fam = sys.argv[2] if len(sys.argv) > 2 else None
for l in open(f"{DATA}/binding/catalog.jsonl"):
    r = json.loads(l)
    if r["prov"] != "cwms" or (fam and r["family"] != fam) or not rx.search(r["name"] or ""): continue
    print(r["sid"][5:], r["begin"], r["end"], r.get("count"), r["unit"], r.get("datum"))
