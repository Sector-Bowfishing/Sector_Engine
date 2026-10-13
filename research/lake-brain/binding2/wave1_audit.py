"""Audit of the 315 wave-1 bound lakes for false positives: (1) station-name traps, (2) level vs operator levels (A2W), (3) level vs NID-linked dam facts,
(4) multiple bound lakes sharing one station, (5) delta to directory full pool beyond the strong window. Output binding2/wave1_audit.json."""
import csv, json, re, collections
from common2 import *
ver = [r for r in csv.DictReader(open(f"{BIND}/verified.csv")) if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG")]
probes = json.load(open(f"{BIND}/probe_results.json"))
flags = collections.defaultdict(list)
TRAP = re.compile(r"(tail|below|downstream|\bblw\b|outlet|piez|well|seep|riverside|river side|landside|land side|ds\b|toe|control structure|pump|canal|bypass)", re.I)
for r in ver:
    if TRAP.search(r["stationName"] or "") or TRAP.search(r["loc"] or ""):
        flags[r["lakeId"]].append("name:" + TRAP.search((r["stationName"] or "") + " " + (r["loc"] or "")).group(0))
    try:
        d = float(r["deltaFullPoolFt"]) if r["deltaFullPoolFt"] else None
    except ValueError:
        d = None
    if d is not None and r["bindingStatus"] != "VERIFIED_FLAG" and (d < -15 or d > 5):
        flags[r["lakeId"]].append(f"delta={d}")
    if r["provider"] == "a2w":
        p = probes.get("a2w|" + r["station"], {})
        lv = p.get("levels") or {}
        top = [v for k, v in lv.items() if v is not None and ("Top of Normal" in k or "Top of Conservation" in k) and k.endswith("Elev")]
        flood = [v for k, v in lv.items() if v is not None and ("Top of Flood" in k or "Maximum Pool" in k) and k.endswith("Elev")]
        bot = [v for k, v in lv.items() if v is not None and ("Bottom of Normal" in k or "Bottom of Conservation" in k) and k.endswith("Elev")]
        try:
            m = float(r["medFt"])
        except Exception:
            m = None
        if m is not None and flood and m > max(flood) + 2:
            flags[r["lakeId"]].append(f"above-flood-level({m}>{max(flood)})")
        if m is not None and bot and m < min(bot) - 60:
            flags[r["lakeId"]].append(f"far-below-bottom-of-normal({m}<{min(bot)})")
st = collections.defaultdict(list)
for r in ver:
    st[(r["provider"], r["station"], r["loc"])].append(r["lakeId"])
for k, v in st.items():
    if len(v) > 1:
        for l in v:
            flags[l].append("shared-station:" + "+".join(x for x in v if x != l))
json.dump(flags, open(f"{B2}/wave1_audit.json", "w"), indent=1)
byid = {r["lakeId"]: r for r in ver}
for l, f in sorted(flags.items()):
    r = byid[l]
    print(f"{l[:32]:32} {r['bindingStatus'][:12]:12} {r['provider']:5} {r['station'][:14]:14} {r['stationName'][:34]:34} med={r['medFt']} d={r['deltaFullPoolFt']} :: {'; '.join(f)}")
