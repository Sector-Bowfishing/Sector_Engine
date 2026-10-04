"""Stage 24 sections 2-4 (PREREGISTRATION_STAGE24.md): N0513 path selection on T2N (derivation, reused) and validation on T24N
(new). No truth. Writes eval24_n0513.json."""
import json, os, sys, glob, hashlib, collections, numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]; os.chdir(f"{S}/stage23")
F24 = json.load(open(f"{S}/stage24/FREEZE_STAGE24.json"))
assert hashlib.sha256(open(f"{S}/stage24/PREREGISTRATION_STAGE24.md", "rb").read()).hexdigest() == F24["prereg_sha256"]
assert hashlib.sha256(open(f"{S}/stage24/derived24.json", "rb").read()).hexdigest() == F24["derived24_sha256"]
sys.argv = ["anal23.py"]; exec(open("anal23.py").read().split("# ---------------- section 3: the floor")[0])
def load_dir(d):
    out = {}
    for f in glob.glob(f"{d}/*.json"):
        r = json.load(open(f)); run, var = os.path.basename(f)[:-5].split("__")
        for c in r.get("crops", []):
            for k, p in (c.get("points") or {}).items():
                out[(run, var, k)] = {"m0": p.get("M0"), "m3": p.get("M3"), "diag": (c.get("diag") or {}).get(k) or {}, "dsf": c.get("dsf") or {}, "toa_sub": r.get("toa_sub")}
    return out
VERS24 = {"N0": ("K0", None), "N1": ("C1", A22.SBAF), "N2": ("N2", A22.SBAF)}
def build24(P, name):
    v, corr = VERS24[name]; pr = []
    for p in P:
        r = A22.scene(p["ref"]); c = A22.scene(p["c"].get(v), corr)
        if r and c: pr.append({"c": c, "r": r, "p": p})
    return pr
# T2N (Stage 23, reused) + N2 from the separate Stage 24 re-run
T2N = pairs23("T2N", "res23_T2N", True); RN2 = load_dir(f"{S}/stage24/res24_T2N_N2")
TT = {(t["pair"]["site"], t["pair"]["c"]): t["run"] for t in json.load(open(f"{S}/stage23/tasks23_T2N.json")) if "_C_" in t["run"]}
for p in T2N: p["c"]["N2"] = RN2.get((TT[(p["site"], p["meta"]["c"])], "N2", p["key"]))
T2N = [p for p in T2N if (sun(p["c"].get("K0")) or 0) >= 25 and A22.ice_ok(p)]
# T24N (new)
R24 = load_dir(f"{S}/stage24/res24_T24N"); T24 = []
for t in json.load(open(f"{S}/stage24/tasks24_T24N.json")):
    if "_R_" not in t["run"]: continue
    q = t["pair"]; pk = f"{q['site']}|{q['o']}|{q['c']}"; cr = t["run"].replace("_R_", "_C_")
    p = {"set": "T24N", "key": pk, "site": q["site"], "region": q["region"], "baseline": "N0513", "ref": R24.get((t["run"], "A", pk)), "c": {v: R24.get((cr, v, pk)) for v in ("K0", "C1", "N2")}, "meta": q}
    if (sun(p["c"].get("K0")) or 0) >= 25 and A22.ice_ok(p): T24.append(p)
out = {"derivation_T2N": {}, "validation_T24N": {}}
for nm in VERS24: out["derivation_T2N"][nm] = dist(build24(T2N, nm)); out["validation_T24N"][nm] = dist(build24(T24, nm))
J = {nm: abs(out["derivation_T2N"][nm]["dp_median"]) for nm in VERS24 if out["derivation_T2N"][nm]["n"]}
order = ["N0", "N1", "N2"]; jmin = min(J.values()); win = min([nm for nm in J if J[nm] <= jmin + 0.005], key=order.index)
v = out["validation_T24N"]; val = {"abs_dp_le_0.03": abs(v[win]["dp_median"]) <= 0.03, "closer_than_N1": abs(v[win]["dp_median"]) < abs(v["N1"]["dp_median"])}
out["selection"] = {"J": J, "winner": win, "validation": val, "validation_passed": all(val.values()) if win != "N1" else None, "update_path": bool(win != "N1" and all(val.values()))}
out["validation_regions"] = {nm: {rg: dist([x for x in build24(T24, nm) if x["p"]["region"] == rg])["dp_median"] for rg in sorted({p["region"] for p in T24}) if any(x["p"]["region"] == rg for x in build24(T24, nm))} for nm in VERS24}
# seasonal control: Stage 22 Sep-Oct 2025 N0511 2-day pairs
SC = [p for s_ in ("T2D", "T2H") for p in A22.pairs_for(s_) if p["meta"]["c_time"][:7] in ("2025-09", "2025-10") and (sun(p["c"].get("K0")) or 0) >= 25]
out["seasonal_control_SepOct2025_N0511"] = {nm: dist(build(SC, ver)) for nm, ver in (("raw", "A"), ("C3", "C3"))}
json.dump(out, open(f"{S}/stage24/eval24_n0513.json", "w"), indent=1, default=str)
for part in ("derivation_T2N", "validation_T24N"):
    for nm, d in out[part].items(): print(part, nm, "n", d["n"], "dp", round(d["dp_median"], 4) if d["n"] else None, "ratios", {b: round(x, 3) for b, x in (d.get("band_ratio_median") or {}).items() if x}, "state", d.get("state_overlap"), "jumps", round(d.get("jump_rate") or 0, 3))
print("SELECTION", out["selection"]); print("REGIONS", out["validation_regions"])
for nm, d in out["seasonal_control_SepOct2025_N0511"].items(): print("SEASONAL", nm, d["n"], round(d["dp_median"], 4) if d["n"] else None)
