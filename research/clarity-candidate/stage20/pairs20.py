"""Stage 20 (value-blind): assemble every pair set of PREREGISTRATION_STAGE20.md section 2 from the frozen-path samples,
with the section 3 split. Writes pairs20.json. No Secchi value is read.
  B   preliminary tandem (res_prelim20): A (S2A), C (S2C as distributed), E (S2C re-calibrated to nominal)
  C25 / C26  operational nominal S2C vs S2A/S2B 1-2 days (res_ops20)
  H4  Stage 19 neighbour pairs S2C vs S2A/S2B 1-2 days;  FLOOR  Stage 19 neighbour pairs S2A vs S2B 1-2 days"""
import json, os, glob, collections, sys
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage20")
from lib20 import split
out = []


def samp(resfile, key):
    if not os.path.exists(resfile): return None
    r = json.load(open(resfile))
    for c in r.get("crops", []):
        p = (c.get("points") or {}).get(key); d = (c.get("diag") or {}).get(key)
        if p is not None: return {"m0": p.get("M0"), "m3": p.get("M3"), "sza": (d or {}).get("sza"), "l1c": r["l1c"], "baseline": r["l1c"].split("_")[3], "diag": d}
    return None


# ---- B: preliminary tandem
T = json.load(open(f"{S}/stage20/tasks20_prelim.json"))
for t in T:
    if not t["run"].startswith("C_"): continue
    lc = t["l1c"]; la = next(u["l1c"] for u in T if u["run"].startswith("A_") and u["crops"] == t["crops"])
    unit = f"{lc.split('_')[2][:8]}|{lc.split('_')[4]}"
    for c in t["crops"]:
        for lat, lon, key in c["points"]:
            site = key.split("|S2A_")[0]
            rec = {"set": "B", "unit": unit, "site": site, "geo": "global" if site.startswith("G:") else "US",
                   "ref": samp(f"{S}/stage20/res_prelim20/A_{la}.json", key), "c": samp(f"{S}/stage20/res_prelim20/C_{lc}.json", key),
                   "e": samp(f"{S}/stage20/res_prelim20/E_{lc}.json", key)}
            for k in ("ref", "c", "e"):
                if rec[k]: rec[k]["platform"] = "sentinel-2a" if k == "ref" else "sentinel-2c"
            out.append(rec)
# ---- C25 / C26: operational
for m in json.load(open(f"{S}/stage20/ops20_pairs.json")):
    key = f"{m['site']}|{m['other']}|{m['s2c']}"; lc, lo = m["l1c_c"], m["l1c_o"]
    rec = {"set": f"C{str(m['year'])[2:]}", "unit": f"{lc.split('_')[2][:8]}|{lc.split('_')[4]}", "site": m["site"], "geo": "global" if m["site"].startswith("G:") else "US",
           "gap_days": m["gap_days"], "ref": samp(f"{S}/stage20/res_ops20/O{m['year']}_{lo}_{m['site']}.json", key), "c": samp(f"{S}/stage20/res_ops20/S{m['year']}_{lc}_{m['site']}.json", key)}
    if rec["ref"]: rec["ref"]["platform"] = "sentinel-2a" if lo.startswith("S2A") else "sentinel-2b"
    if rec["c"]: rec["c"]["platform"] = "sentinel-2c"
    out.append(rec)
# ---- H4 / FLOOR: Stage 19 neighbour scenes (never training rows)
P, L1C = {}, {}
for f in glob.glob(f"{S}/stage17/scenes/res_nb/*.json") + glob.glob(f"{S}/stage18p/res_nb18/*.json") + glob.glob(f"{S}/stage19/res_nb19/*.json"):
    r = json.load(open(f))
    for c in r.get("crops", []):
        for k, p in (c.get("points") or {}).items(): P[k] = p; L1C[k] = r.get("l1c")
dev = {r["id"]: r for r in json.load(open(f"{S}/stage16/analysis/dev16_rows.json"))}
sel = json.load(open(f"{S}/stage19/neighbors19.json")); seen = set()
for cid, v in sel.items():
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            a, b = v[i], v[j]
            if not (1 <= abs(a["age"] - b["age"]) <= 2): continue
            plats = {a["platform"], b["platform"]}
            if "sentinel-2c" in plats and len(plats) == 2: kind = "H4"
            elif plats == {"sentinel-2a", "sentinel-2b"}: kind = "FLOOR"
            else: continue
            c_, r_ = (a, b) if (a["platform"] == "sentinel-2c" or (kind == "FLOOR" and a["platform"] == "sentinel-2b")) else (b, a)
            lake = dev[cid]["lake"]; dk = (kind, lake, c_["pass_key"], r_["pass_key"])
            if dk in seen: continue
            def sm(n):
                k = f"{cid}#{n['item']}"; p = P.get(k)
                if not p or n.get("sun_elev") is None or not L1C.get(k): return None
                return {"m0": p.get("M0"), "m3": p.get("M3"), "sza": 90.0 - n["sun_elev"], "l1c": L1C[k], "baseline": L1C[k].split("_")[3], "platform": n["platform"]}
            rec = {"set": kind, "unit": c_["pass_key"], "site": lake, "geo": "US", "gap_days": abs(a["age"] - b["age"]), "event": cid, "c": sm(c_), "ref": sm(r_)}
            if rec["c"] and rec["ref"]: seen.add(dk); out.append(rec)
# ---- section 3 splits
for s_, force in (("B", ("20241215|R056",)), ("C25", ())):
    cnt = collections.Counter(x["unit"] for x in out if x["set"] == s_)
    d, h = split(cnt, force)
    for x in out:
        if x["set"] == s_: x["split"] = ("D1" if s_ == "B" else "D2") if x["unit"] in d else ("H1" if s_ == "B" else "H2")
for x in out:
    if x["set"] == "C26": x["split"] = "H3"
    if x["set"] == "H4": x["split"] = "H4"
    if x["set"] == "FLOOR": x["split"] = "FLOOR"
json.dump(out, open(f"{S}/stage20/pairs20.json", "w"), default=str)
c = collections.Counter((x["set"], x["split"]) for x in out)
print({f"{a}/{b}": n for (a, b), n in sorted(c.items())})
print("baselines S2C:", collections.Counter((x["set"], x["c"]["baseline"]) for x in out if x.get("c")))
