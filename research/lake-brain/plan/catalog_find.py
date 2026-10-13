"""Search the binding-thread series catalog (36,785 series) compactly: catalog_find.py <regex on name> [prov] [family]"""
import sys, json, re, collections
from common import *
rx = re.compile(sys.argv[1], re.I); prov = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None; fam = sys.argv[3] if len(sys.argv) > 3 else None
g = collections.OrderedDict()
for l in open(f"{DATA}/binding/catalog.jsonl"):
    r = json.loads(l)
    if prov and r["prov"] != prov: continue
    if fam and r["family"] != fam: continue
    if not rx.search(r["name"] or "") : continue
    g.setdefault((r["prov"], r["station"], r["name"], r["family"]), []).append(r)
for k, v in g.items():
    b = min((x["begin"] or "9") for x in v); e = max((x["end"] or "0") for x in v)
    print(k, f"n={len(v)}", b, e, "e.g.", v[0]["sid"][:90], v[0].get("lat"), v[0].get("lon"))
