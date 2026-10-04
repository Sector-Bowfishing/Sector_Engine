"""Stage 23 sections 3-6 (PREREGISTRATION_STAGE23.md): the mid-latitude S2A/S2B floor, the frozen envelope, and the C3 S2C
(sun >= 25 deg) cross-sensor evaluation on TH25, T2H25 and T2N, per baseline. No Secchi value is read. Writes eval23.json.
  python anal23.py [--extended]   (--extended adds FL23X under the section 2 extension rule)"""
import json, os, sys, glob, math, hashlib, collections
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage20", f"{S}/stage22"]
F = json.load(open(f"{S}/stage23/FREEZE_STAGE23.json"))
assert hashlib.sha256(open(f"{S}/stage23/PREREGISTRATION_STAGE23.md", "rb").read()).hexdigest() == F["prereg_sha256"], "prereg not frozen"
for f, h in F["files_sha256"].items():
    if f.startswith("tasks23_") or f == "pairs23_meta.json": assert hashlib.sha256(open(f"{S}/stage23/{f}", "rb").read()).hexdigest() == h, f
import lib20 as L20
import _anal22_lib as A22                      # Stage 22's loaders, scene builder and C3 definition (unchanged)
VIS = ["B02", "B03", "B04", "B05"]; LEG = math.log10(1.03)
EXT = "--extended" in sys.argv


def load23(resdir):
    out = {}
    for f in glob.glob(f"{S}/stage23/{resdir}/*.json"):
        r = json.load(open(f)); run, var = os.path.basename(f)[:-5].split("__")
        for c in r.get("crops", []):
            for k, p in (c.get("points") or {}).items():
                out[(run, var, k)] = {"m0": p.get("M0"), "m3": p.get("M3"), "diag": (c.get("diag") or {}).get(k) or {}, "dsf": c.get("dsf") or {}, "toa_sub": r.get("toa_sub")}
    return out


def pairs23(task, resdir, s2c):
    R = load23(resdir); out = []
    for t in json.load(open(f"{S}/stage23/tasks23_{task}.json")):
        if "_R_" not in t["run"]: continue
        q = t["pair"]; pk = f"{q['site']}|{q['o']}|{q['c']}"; cr = t["run"].replace("_R_", "_C_")
        c = {v: R.get((cr, v, pk)) for v in (("K0", "C1") if s2c else ("A",))}
        if not s2c: c = {"K0": c["A"]}
        out.append({"set": task, "key": pk, "site": q["site"], "region": q["region"], "subtype": q.get("subtype"), "baseline": "N" + (q.get("c_baseline") or "").replace(".", ""),
                    "ref": R.get((t["run"], "A", pk)), "c": c, "meta": q})
    return out


def sun(rec):
    s = ((rec or {}).get("diag") or {}).get("sza"); return 90 - s if s is not None else None


def build(P, version):
    """valid pairs [{'c': scene, 'r': scene, 'p': pair}] for one S2C version ('FLOOR' = S2B as is)."""
    v, corr = ("K0", None) if version == "FLOOR" else A22.VERS[version]
    pr = []
    for p in P:
        r = A22.scene(p["ref"]); c = A22.scene(p["c"].get(v), corr)
        if r and c: pr.append({"c": c, "r": r, "p": p})
    return pr


def dist(pr):
    """per-pair |d_b|, |dp| distributions + the lib20 pair metrics."""
    m = L20.pair_metrics(pr, tandem=True); out = {k: m.get(k) for k in ("n", "dp_median", "dp_iqr", "state_overlap", "jump_rate", "posterior_diff_median", "unknown_c", "unknown_r", "n_states")}
    out["band_median"] = {b: m["band_log_ratio"][b]["median"] for b in VIS}; out["band_iqr"] = {b: m["band_log_ratio"][b]["iqr"] for b in VIS}
    out["band_ratio_median"] = {b: (10 ** m["band_log_ratio"][b]["median"] if m["band_log_ratio"][b]["median"] is not None else None) for b in VIS}
    ab = {b: [abs(math.log10(x["c"]["a"][b] / x["r"]["a"][b])) for x in pr if x["c"]["a"].get(b, 0) > 0.001 and x["r"]["a"].get(b, 0) > 0.001] for b in VIS}
    adp = [abs(x["c"]["p"] - x["r"]["p"]) for x in pr]
    q = lambda v, k: float(np.percentile(v, k)) if v else None
    out["abs_band"] = {b: {"p50": q(ab[b], 50), "p90": q(ab[b], 90), "p95": q(ab[b], 95), "n": len(ab[b])} for b in VIS}
    out["abs_dp"] = {"p50": q(adp, 50), "p90": q(adp, 90), "p95": q(adp, 95)}
    out["legacy_3pct"] = all(out["band_median"][b] is not None and abs(out["band_median"][b]) <= LEG for b in VIS)
    out["lakes"] = len({x["p"]["site"] for x in pr if x["p"].get("site")})
    out["regions"] = dict(collections.Counter(x["p"].get("region") for x in pr)) if pr and pr[0]["p"].get("region") else None
    return out


# ---------------- section 3: the floor
FL = pairs23("FL23", "res23_FL23", False) + (pairs23("FL23X", "res23_FL23X", False) if EXT else [])
FLv = [p for p in FL if A22.ice_ok(p)]
FP = build(FLv, "FLOOR")
floor = dist(FP)
floor["subtypes"] = {st: dist([x for x in FP if x["p"]["subtype"] == st]) for st in ("tandem", "adjacent")}
floor["processed_pairs"] = len(FL); floor["after_ice_screen"] = len(FLv)
floor["usable"] = bool(floor["n"] >= 100 and floor["lakes"] >= 10 and len(floor["regions"] or {}) >= 3 and abs(floor["dp_median"]) <= 0.03)
floor["needs_extension"] = bool(not EXT and (floor["n"] < 100 or floor["lakes"] < 10 or len(floor["regions"] or {}) < 3))
# ---------------- section 4: the envelope (pooled, primary) and the tandem-subset sensitivity
def envelope(d): return {"E50": {b: d["abs_band"][b]["p50"] for b in VIS}, "E90": {b: d["abs_band"][b]["p90"] for b in VIS}, "V90": d["abs_dp"]["p90"],
                         "O": d["state_overlap"], "J": d["jump_rate"], "state_limit": min(0.95, (d["state_overlap"] or 0) - 0.03), "jump_limit": (d["jump_rate"] or 0) + 0.02}
ENV = envelope(floor); ENV_T = envelope(floor["subtypes"]["tandem"]) if floor["subtypes"]["tandem"]["n"] else None
# ---------------- section 6: S2C C3 at sun >= 25
TH = [p for p in A22.pairs_for("TH") if (sun(p["c"].get("K0")) or 0) >= 25]
T2H = [p for p in A22.pairs_for("T2H") if (sun(p["c"].get("K0")) or 0) >= 25]
T2N = [p for p in pairs23("T2N", "res23_T2N", True) if (sun(p["c"].get("K0")) or 0) >= 25 and A22.ice_ok(p)]


def judge(pr, env, full):
    d = dist(pr); n = d["n"]
    c = {"n_ge_15": n >= 15, "systematic_bands": all(d["band_median"][b] is not None and abs(d["band_median"][b]) <= env["E50"][b] for b in VIS), "visibility": abs(d["dp_median"]) <= 0.03 if n else False}
    if full:
        c.update({"spread_bands": all(d["abs_band"][b]["p90"] is not None and d["abs_band"][b]["p90"] <= env["E90"][b] for b in VIS), "spread_visibility": (d["abs_dp"]["p90"] or 9) <= env["V90"],
                  "state": (d["state_overlap"] or 0) >= env["state_limit"], "jumps": d["jump_rate"] <= env["jump_limit"]})
    d["criteria"] = c; d["pass"] = all(c.values()); return d


ev = {"floor": floor, "envelope": ENV, "envelope_tandem_subset": ENV_T, "strata": {}, "baselines": {}, "sensitivity_tandem_envelope": {}, "raw_reference": {}}
SETS = {"TH25": (TH, True), "T2H25": (T2H, False), "T2N": (T2N, False)}
for name, (P, full) in SETS.items():
    pr = build(P, "C3"); ev["strata"][name] = judge(pr, ENV, full)
    if ENV_T: ev["sensitivity_tandem_envelope"][name] = judge(pr, ENV_T, full)["criteria"]
    ev["raw_reference"][name] = dist(build(P, "A"))
# baselines exactly as section 6: N0511 = TH25 + T2H25's N0511 pairs; N0512 = T2H25's N0512 pairs; N0513 = T2N
thp, t2p, tnp = build(TH, "C3"), build(T2H, "C3"), build(T2N, "C3")
groups = {"N0511": thp + [x for x in t2p if x["p"].get("baseline") == "N0511"], "N0512": [x for x in t2p if x["p"].get("baseline") == "N0512"], "N0513": tnp}
for bl, pr in groups.items(): ev["baselines"][bl] = judge(pr, ENV, False)
ev["t2h25_pairs_outside_groups"] = sum(1 for x in t2p if x["p"].get("baseline") not in ("N0511", "N0512"))
st = ev["strata"]; bl = ev["baselines"]
ev["sensor_decision"] = {"floor_usable": floor["usable"], "TH25": st["TH25"]["pass"], "T2H25": st["T2H25"]["pass"], "T2N": st["T2N"]["pass"],
                         "baselines": {k: v["pass"] for k, v in bl.items()},
                         "outcome_before_secchi": ("B" if not (floor["usable"] and st["TH25"]["pass"]) else
                                                    "A-pending-secchi" if (st["T2H25"]["pass"] and st["T2N"]["pass"] and all(v["pass"] for v in bl.values())) else "C")}
json.dump(ev, open(f"{S}/stage23/eval23.json", "w"), indent=1, default=str)
f3 = lambda x: "—" if x is None else f"{x:+.4f}"
print("FLOOR n", floor["n"], "lakes", floor["lakes"], "regions", floor["regions"], "usable", floor["usable"], "needs extension", floor["needs_extension"])
print("  median d", {b: f3(floor["band_median"][b]) for b in VIS}, "dp", f3(floor["dp_median"]), "overlap", floor["state_overlap"], "jumps", floor["jump_rate"], "legacy 3%", floor["legacy_3pct"])
print("  ENV E50", {b: round(v, 4) for b, v in ENV["E50"].items()}, "E90", {b: round(v, 4) for b, v in ENV["E90"].items()}, "V90", round(ENV["V90"], 4), "state>=", round(ENV["state_limit"], 3), "jumps<=", round(ENV["jump_limit"], 3))
for st_ in ("tandem", "adjacent"):
    d = floor["subtypes"][st_]; print("  ", st_, "n", d["n"], "median d", {b: f3(d["band_median"][b]) for b in VIS}, "|d| p50", {b: round(d["abs_band"][b]["p50"] or 0, 4) for b in VIS}, "dp", f3(d["dp_median"]), "overlap", d["state_overlap"], "jumps", d["jump_rate"])
for name, d in st.items(): print(name, "n", d["n"], "median d", {b: f3(d["band_median"][b]) for b in VIS}, "p90|d|", {b: round(d["abs_band"][b]["p90"] or 0, 4) for b in VIS}, "dp", f3(d["dp_median"]), "p90|dp|", round(d["abs_dp"]["p90"] or 0, 4), "overlap", d["state_overlap"], "jumps", d["jump_rate"], "legacy", d["legacy_3pct"], "PASS", d["pass"], d["criteria"])
for k, d in bl.items(): print(k, "n", d["n"], "dp", f3(d["dp_median"]), "PASS", d["pass"], d["criteria"])
print("SENSOR DECISION", ev["sensor_decision"])
