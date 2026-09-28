"""The repaired membership as drop-in lake-profile assets (Clarity Fusion
Stage 1) -- CANDIDATES, not applied to the app. The iOS impact test reads
them to measure what adopting them would change.

  Guntersville.segments.json.gz     the shipped file with five fields replaced:
      tributaryId          the arm the bank's water is reached from first
                           (None on the main stem)
      lakeRegion           that arm's name (county added where two creeks
                           share a name), "mainstem" otherwise
      basinClass           mainstem | largeTributaryArm | minorTributary
      distanceToTributaryM through the water to the arm's mouth (main-stem
                           banks: to the nearest arm mouth)
      distanceToChannelM   through the water to the Tennessee's channel
  Guntersville.tributaries.json.gz  the registry rebuilt from the graph

usage: geo/bin/python repaired_profile.py <final dir> <out dir> [--identity-only]

--identity-only  replace only tributaryId and lakeRegion on the segments (the
                 variant adopted 2026-09-27: no attraction or huntability score
                 moves; basinClass and both distances keep the shipped values)

Both variants add throughWaterToArmMouthM, the Tributary Influence layer's own
through-water distance to the mouth of the bank's arm (null off the arms).
"""
import os, sys, json, gzip, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_arm_graph as B

final, out = sys.argv[1], sys.argv[2]
IDENTITY_ONLY = "--identity-only" in sys.argv
os.makedirs(out, exist_ok=True)
graph = json.load(open(os.path.join(final, "guntersville.hydrology.json")))
mem = {m["id"]: m for m in json.load(open(os.path.join(final, "segment_membership.json")))["segments"]}
arms = {a["id"]: a for a in graph["arms"]}
seg_file = json.load(gzip.open(os.path.join(B.ASSETS, "GuntersvilleSegments.dataset", "Guntersville.segments.json.gz")))
reg_file = json.load(gzip.open(os.path.join(B.ASSETS, "GuntersvilleTributaries.dataset", "Guntersville.tributaries.json.gz")))

names = collections.Counter(a["name"] for a in graph["arms"])
def display(a):
    if names[a["name"]] > 1 and a.get("mouthCounty"):
        return f"{a['name']} ({a['mouthCounty'].replace(' County', ' Co.')})"
    return a["name"]

changed = collections.Counter()
for s in seg_file["segments"]:
    m = mem[s["id"]]
    if m["arm"] is None and m["tributaryId"] not in arms:
        changed["unresolved (kept as shipped)"] += 1   # no water cell to place it by
        continue
    tid = m["tributaryId"]
    new = {"tributaryId": tid,
           "lakeRegion": display(arms[tid]) if tid in arms else "mainstem",
           "basinClass": m["basinClass"],
           "distanceToTributaryM": m["throughWaterToMouthM"] if tid else m["throughWaterToNearestMouthM"],
           "distanceToChannelM": m["throughWaterToChannelM"] if m["throughWaterToChannelM"] is not None else s["distanceToChannelM"]}
    if IDENTITY_ONLY:
        new = {k: new[k] for k in ("tributaryId", "lakeRegion")}
    # The Tributary Influence layer's own distance (Stage 3A hardening): through
    # the water to the mouth of the bank's own arm. Only that layer reads it;
    # the species models keep distanceToTributaryM.
    new["throughWaterToArmMouthM"] = m["throughWaterToMouthM"] if tid in arms else None
    for k, v in new.items():
        if s.get(k) != v:
            changed[k] += 1
        s[k] = v
seg_file["properties"]["generatorVersion"] = seg_file["properties"].get("generatorVersion", "") + (
    "+hydrology-identity" if IDENTITY_ONLY else "+hydrology-stage1-candidate")
json.dump(seg_file, gzip.open(os.path.join(out, "Guntersville.segments.json.gz"), "wt"))
json.dump(seg_file, open(os.path.join(out, "Guntersville.segments.json"), "w"))

members = collections.defaultdict(list)
for s in seg_file["segments"]:
    if s["tributaryId"]:
        members[s["tributaryId"]].append(s["id"])
tribs = []
for a in graph["arms"]:
    site = a["usgsDischargeSite"]
    tribs.append({"id": a["id"], "name": display(a), "confluence": a["mouth"], "embaymentHead": a["head"],
                  "naturalChannelKm": a["naturalChannelKm"] or 0.0, "reservoirPathKm": a["reservoirPathKm"] or 0.0,
                  "huc8": (a["huc12"] or "")[:8] or reg_file["properties"]["huc8"],
                  "reachCode": (a["nhdReachCodes"] or [""])[0],
                  "usgsSite": site, "usgsSiteName": a["usgsDischargeSiteName"],
                  "usgsParameters": ["00060", "00065"] if site else [],
                  "nwmFeatureId": a["nwmFeatureId"], "hydrologicClass": "unknown", "armClass": a["armClass"],
                  "flowSupport": {"measuredUSGS": "measured", "modeledNWM": "modeled"}.get(a["flowSource"], "unavailable"),
                  "segmentIds": sorted(members.get(a["id"], [])),
                  "source": "NHD HR flow network + through-water allocation (scripts/hydrology, Stage 1)"})
reg_file["tributaries"] = tribs
reg_file["properties"]["generatorVersion"] = seg_file["properties"]["generatorVersion"]
json.dump(reg_file, gzip.open(os.path.join(out, "Guntersville.tributaries.json.gz"), "wt"))
json.dump(reg_file, open(os.path.join(out, "Guntersville.tributaries.json"), "w"))
print("fields changed:", dict(changed), "| tributaries:", len(tribs))
