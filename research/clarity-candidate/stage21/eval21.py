"""Stage 21 PREREGISTRATION sections 4-6 (after the freeze): held-out tandem TH, fresh current-era F25/F26 (gating),
Stage 20's C25/C26/H4 (secondary), the TOA residual check, and the verdicts PRE-ACOLITE VALID / LIFT BAR.
Versions: K0 raw S2C, K1 TOA offsets, K2 = K1 + B05 band adjustment (the decision version), B = Stage 12 on K0.
Writes eval21.json. No Secchi value is read."""
import json, os, sys, glob, hashlib, collections
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage20", f"{S}/stage21"]
import lib20 as L20
F = json.load(open(f"{S}/stage21/FREEZE_STAGE21.json"))
for k, p in (("prereg_sha256", "PREREGISTRATION_STAGE21.md"), ("corr21_sha256", "corr21.json")):
    assert hashlib.sha256(open(f"{S}/stage21/{p}", "rb").read()).hexdigest() == F[k], p
CORR = json.load(open(f"{S}/stage21/corr21.json")); B5 = CORR["b05_l2w"]
K2 = L20.c_param({"B05": {"g": B5["g"], "k": B5["k"]}})
floor = json.load(open(f"{S}/stage20/floor20.json")); floor = {"state_overlap": floor["state_overlap"], "jump_rate": floor["jump_rate"]}


def samples(resdir_glob):
    P = {}
    for f in glob.glob(resdir_glob):
        r = json.load(open(f))
        for c in r.get("crops", []):
            for k, p in (c.get("points") or {}).items():
                d = (c.get("diag") or {}).get(k) or {}
                P[(os.path.basename(f)[:-5], k)] = {"m0": p.get("M0"), "m3": p.get("M3"), "sza": d.get("sza")}
    return P


def sc(s, corr=None): return L20.scene(s["m0"], s["m3"], s["sza"], corr) if s else None


def versions(ref, k0, k1):
    """-> {version: [pair dicts]} for pairs where both scenes are valid."""
    out = collections.defaultdict(list)
    for r, a, b in zip(ref, k0, k1):
        R = sc(r)
        if not R: continue
        for name, s, corr in (("K0", a, None), ("K1", b, None), ("K2", b, K2), ("B", a, L20.c_stage12)):
            C = sc(s, corr)
            if C: out[name].append({"c": C, "r": R})
    return out


strata = {}
# ---- TH: held-out tandem
P = samples(f"{S}/stage21/res_tandem21/*.json"); ref, k0, k1, geo, early = [], [], [], [], []
for t in [t for t in json.load(open(f"{S}/stage21/tasks21_tandem.json")) if t["run"].startswith("A_")]:
    key = t["run"][2:]
    for c in t["crops"]:
        for la, lo, pk in c["points"]:
            ref.append(P.get((f"A_{key}", pk))); k0.append(P.get((f"C0_{key}", pk))); k1.append(P.get((f"C1_{key}", pk)))
            geo.append("global" if pk.startswith("G:") else "US"); early.append(key.split("_")[-1] < "2024-12-12")
strata["TH"] = versions(ref, k0, k1)
strata["TH_before_12Dec"] = versions([r for r, e in zip(ref, early) if e], [a for a, e in zip(k0, early) if e], [b for b, e in zip(k1, early) if e])
strata["TH_12_18Dec"] = versions([r for r, e in zip(ref, early) if not e], [a for a, e in zip(k0, early) if not e], [b for b, e in zip(k1, early) if not e])
strata["TH_global"] = versions([r for r, g in zip(ref, geo) if g == "global"], [a for a, g in zip(k0, geo) if g == "global"], [b for b, g in zip(k1, geo) if g == "global"])
# ---- F25 / F26: fresh current era
Pr = samples(f"{S}/stage21/res_ops21/*.json"); Pc = samples(f"{S}/stage21/res_ops21c/*.json")
for year in (2025, 2026):
    ref, k0, k1 = [], [], []
    for m in [m for m in json.load(open(f"{S}/stage21/ops21_pairs.json")) if m["year"] == year]:
        pk = f"{m['site']}|{m['other']}|{m['s2c']}"
        ref.append(Pr.get((f"O{year}_{m['l1c_o']}_{m['site']}", pk))); k0.append(Pc.get((f"S0{year}_{m['l1c_c']}_{m['site']}", pk))); k1.append(Pc.get((f"S1{year}_{m['l1c_c']}_{m['site']}", pk)))
    strata[f"F{str(year)[2:]}"] = versions(ref, k0, k1)
# ---- secondary: Stage 20 C25/C26 (K0 = Stage 20 raw runs; K1 = Stage 21 re-runs), H4 (Stage 19 neighbours)
P20 = samples(f"{S}/stage20/res_ops20/*.json"); P20c = samples(f"{S}/stage21/res_ops20c/*.json")
for year in (2025, 2026):
    ref, k0, k1 = [], [], []
    for m in [m for m in json.load(open(f"{S}/stage20/ops20_pairs.json")) if m["year"] == year]:
        pk = f"{m['site']}|{m['other']}|{m['s2c']}"
        ref.append(P20.get((f"O{year}_{m['l1c_o']}_{m['site']}", pk))); k0.append(P20.get((f"S{year}_{m['l1c_c']}_{m['site']}", pk))); k1.append(P20c.get((f"S1{year}_{m['l1c_c']}_{m['site']}", pk)))
    strata[f"C{str(year)[2:]}_stage20"] = versions(ref, k0, k1)
Pn = samples(f"{S}/stage21/res_s2c21/*.json")
pairs20 = [x for x in json.load(open(f"{S}/stage20/pairs20.json")) if x["set"] == "H4"]
ref, k0, k1 = [], [], []
for x in pairs20:
    key = f"{x['event']}#" + next(n["item"] for n in json.load(open(f"{S}/stage19/neighbors19.json"))[x["event"]] if n["pass_key"] == x["unit"])
    l1c = x["c"]["l1c"]; ref.append(x["ref"]); k0.append(Pn.get((f"K0_{l1c}", key))); k1.append(Pn.get((f"K1_{l1c}", key)))
strata["H4_stage19"] = versions(ref, k0, k1)
# ---- metrics and bars
GATING = {"TH": True, "F25": False, "F26": False}
out = {"floor": floor, "strata": {}}
for name, V in strata.items():
    tandem = name.startswith("TH")
    out["strata"][name] = {v: L20.pair_metrics(V.get(v, []), floor=floor, tandem=tandem) for v in ("K0", "K1", "K2", "B")}
gating = [s for s in GATING if out["strata"][s]["K2"].get("gating")]
pooled = [p["c"]["p"] - p["r"]["p"] for s in GATING for p in strata[s].get("K2", [])]
out["pooled_K2"] = {"n": len(pooled), "dp_median": float(np.median(pooled)) if pooled else None}
lift = ("TH" in gating and len(gating) >= 2 and all(out["strata"][s]["K2"]["bars"]["all"] for s in gating) and abs(out["pooled_K2"]["dp_median"]) <= 0.03)
no_spec = all(all(out["strata"][s]["K2"]["bars"][k] for k in ("visibility", "state", "harm")) for s in gating)
# ---- TOA residual (held-out tiles)
H = [json.load(open(f)) for f in glob.glob(f"{S}/stage21/toa21_H/*.json")]
H = [h for h in H if h.get("raw", {}).get("n_water", 0) >= 200]
res = {b: {"raw_median": float(np.median([h["raw"]["bands"][b]["delta_tile"] for h in H])), "corrected_median": float(np.median([h["corrected"]["bands"][b]["delta_tile"] for h in H])),
           "corrected_iqr": [float(np.percentile([h["corrected"]["bands"][b]["delta_tile"] for h in H], q)) for q in (25, 75)]} for b in ("B08", "B8A", "B11", "B12")} if H else {}
out["toa_residual_TH"] = {"n_tiles": len(H), "bands": res, "b05_raw_median": float(np.median([h["raw"]["bands"]["B05"]["delta_tile"] for h in H])) if H else None}
toa_ok = bool(res) and all(abs(v["corrected_median"]) <= 0.0003 for v in res.values())
th = out["strata"]["TH"]["K2"]
valid = toa_ok and th.get("n", 0) >= 15 and all(th["bars"][k] for k in ("visibility", "state", "harm"))
out["verdicts"] = {"gating_strata": gating, "PRE_ACOLITE_VALID": bool(valid), "toa_residual_ok": toa_ok, "LIFT_BAR_PASSED": bool(lift), "lift_without_spectral_context_only": bool(no_spec and "TH" in gating and len(gating) >= 2)}
json.dump(out, open(f"{S}/stage21/eval21.json", "w"), indent=1, default=str)
for s, V in out["strata"].items():
    for v, m in V.items():
        if m.get("n"): print(f"{s:16s} {v:3s} n {m['n']:3d} dp {m['dp_median']:+.4f} ov {m['state_overlap'] if m['state_overlap'] is None else round(m['state_overlap'], 3)} jump {m['jump_rate']:.3f} "
                             f"bands {dict((b, None if x['median'] is None else round(10 ** x['median'], 3)) for b, x in m['band_log_ratio'].items())} bars {m['bars']['all']} {dict((k, m['bars'][k]) for k in ('spectral', 'visibility', 'state', 'harm'))}")
print("pooled K2", out["pooled_K2"]); print("TOA residual", out["toa_residual_TH"]); print("VERDICTS", out["verdicts"])
