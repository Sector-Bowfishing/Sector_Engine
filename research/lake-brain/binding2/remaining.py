"""Classify the lakes still unbound after wave 2: tier, best attempted source result (scout notes), failure class, and proxy remarks. Output binding2/remaining_unbound.json"""
import json, collections, glob
from common2 import *
out = json.load(open(f"{B2}/assembled_v2.json"))
prof = {p["lakeId"]: p for p in json.load(open(f"{B2}/unbound_profile.json"))}
notes = []
for f in sorted(glob.glob(f"{B2}/notes/*.json")):
    if "series_check" in f:
        continue
    for r in json.load(open(f)):
        r["_area"] = os.path.basename(f)[:-5]; notes.append(r)
RK = {"WORKS": 0, "PARTIAL": 1, "STALE": 2, "REQUIRES_LOGIN": 3, "PORTAL_ONLY": 3, "NO_API": 3, "BLOCKED": 3, "NO_DATA": 4}
rem = []
cands_by_lake = collections.defaultdict(list)
import glob as g
for p in g.glob(f"{B2}/cand/*.jsonl"):
    for l in open(p):
        r = json.loads(l); cands_by_lake[r["lakeId"]].append(r)
for r in out:
    if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG", "VERIFIED_ENVELOPE"):
        continue
    lid = r["lakeId"]; p = prof.get(lid, {})
    ns = [n for n in notes if lid in (n.get("scope") or [])]
    ns.sort(key=lambda n: RK.get(n.get("result"), 9))
    best = ns[0] if ns else None
    cls = ("STAGE_ONLY (local datum, no usable offset)" if r["bindingStatus"] == "STAGE_ONLY" else
           "live candidate failed review rules" if cands_by_lake.get(lid) else
           "source exists but not live/stale" if best and best["result"] == "STALE" else
           "portal/PDF/login only" if best and best["result"] in ("PORTAL_ONLY", "NO_API", "REQUIRES_LOGIN", "BLOCKED") else
           "no public level data found" if best else "not researched in scope")
    rem.append(dict(lakeId=lid, state=r["state"], tier=p.get("bowTier"), areaKm2=p.get("areaKm2"), operator=r["operator"], hasDam=r["hasDam"], w1Status=r["w1Status"], status=r["bindingStatus"], cls=cls,
                    bestSource=(best or {}).get("source"), bestResult=(best or {}).get("result"), evidence=((best or {}).get("evidence") or "")[:260], nCands=len(cands_by_lake.get(lid, []))))
json.dump(rem, open(f"{B2}/remaining_unbound.json", "w"), indent=1)
C = collections.Counter
print(len(rem), C(r["cls"] for r in rem))
print("tier", C(r["tier"] for r in rem))
print("tier x cls", sorted(C((str(r["tier"]), r["cls"]) for r in rem).items()))
print("state", sorted(C(r["state"] for r in rem).items(), key=lambda x: -x[1])[:25])
