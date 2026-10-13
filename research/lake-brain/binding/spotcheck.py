"""Phase 6: independent spot-check of a stratified random sample of strict-verified bindings. Output: binding/spotcheck.csv"""
import csv, collections, json, random
from common import *

random.seed(20261013)
V = [r for r in csv.DictReader(open(f"{BIND}/verified.csv")) if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG")]
cand = list(csv.DictReader(open(f"{BIND}/candidates.csv")))
probes = json.load(open(f"{BIND}/probe_results.json"))
nid = {r["lakeId"]: r for r in csv.DictReader(open(f"{BIND}/nid_links.csv"))}
dams = {}
for l in open(f"{RAW}/nid/nid.jsonl"):
    d = json.loads(l); dams[d["NIDID"]] = d   # last wins (primary dam record is first; good enough for coordinates)
L = {l["id"]: l for l in load_directory()}
byprov = collections.defaultdict(list)
for r in V:
    byprov[r["provider"]].append(r)
sample = []
for prov, rs in byprov.items():
    k = max(3, round(40 * len(rs) / len(V)))
    sample += random.sample(rs, min(k, len(rs)))
flag_s = random.sample([r for r in V if r["bindingStatus"] == "VERIFIED_FLAG"], 15)
sample += [r for r in flag_s if r not in sample]
rows = []
for r in sample:
    lake = L[r["lakeId"]]
    c = [x for x in cand if x["lakeId"] == r["lakeId"] and x["prov"] == r["provider"] and x["station"] == r["station"]]
    c = c[0] if c else {}
    pr = probes.get(c.get("probeKey", ""), {})
    checks = {}
    # I1 independent origin agreement
    checks["I1_second_origin"] = "yes:" + r["corroboratedBy"] if r["corroboratedBy"] else "no"
    # I2 operator-published levels
    lv = pr.get("levels") or {}
    top = lv.get("Top of Flood|Elev"); tn = lv.get("Top of Normal|Elev"); inact = lv.get("Top of Inactive|Elev")
    med = float(r["medFt"]) if r["medFt"] else None
    if med is not None and (top or tn):
        ok = (inact is None or med >= inact - 1) and med <= (top or tn) + 2
        checks["I2_operator_levels"] = f"{'ok' if ok else 'FAIL'} (topNormal={tn}, topFlood={top}, inactive={inact})"
    else:
        checks["I2_operator_levels"] = "n/a"
    # I3 NID dam near station
    n = nid.get(r["lakeId"], {})
    d = dams.get(n.get("nidId")) if n else None
    if d and c:
        dd = haversine_m(float(c["lat"]), float(c["lon"]), d["LATITUDE"], d["LONGITUDE"])
        checks["I3_nid_dam"] = f"{d['NAME']} {int(dd)}m" + ("" if dd < 6000 else " FAR")
    else:
        checks["I3_nid_dam"] = "n/a" if str(lake["hasDam"]) != "True" else "unresolved"
    # I4 NIDID alias (A2W)
    if r["provider"] == "a2w" and pr.get("nidid"):
        checks["I4_nid_alias"] = "agree" if pr["nidid"] == n.get("nidId") else f"differ(a2w={pr['nidid']}, ours={n.get('nidId')})"
    else:
        checks["I4_nid_alias"] = "n/a"
    # I5 basic identity text
    checks["I5_name"] = f"{r['stationName'][:50]} | sim={r['nameSim']} dist={r['distM']}m"
    rows.append(dict(lakeId=r["lakeId"], provider=r["provider"], station=r["station"], status=r["bindingStatus"], level=r["medFt"], fullPool=r["fullPoolFt"], **checks))
with open(f"{BIND}/spotcheck.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), collections.Counter(r["provider"] for r in rows))
for r in rows: print(r["lakeId"][:26].ljust(26), r["provider"].ljust(5), r["station"][:14].ljust(14), r["level"], r["fullPool"], "|", r["I1_second_origin"][:22], "|", r["I2_operator_levels"][:30], "|", r["I3_nid_dam"][:30], "|", r["I4_nid_alias"][:20], "|", r["I5_name"][:45])
