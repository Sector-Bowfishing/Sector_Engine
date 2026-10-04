"""Stage 22 analysis (PREREGISTRATION_STAGE22.md sections 3-6).
  python anal22.py derive   derivation sets only (TD, T2D): mechanism tests + candidate selection -> cand22.json (frozen)
  python anal22.py eval     after the freeze: held-out TH, S, T2H, FLOOR (+ mechanism on every set) -> eval22.json
No Secchi value is read."""
import json, os, sys, glob, math, hashlib, datetime, collections, itertools
import numpy as np
from scipy.stats import theilslopes, spearmanr
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage20", f"{S}/stage22"]
import lib20 as L20
MODE = sys.argv[1]
F = json.load(open(f"{S}/stage22/FREEZE_STAGE22.json"))
assert hashlib.sha256(open(f"{S}/stage22/PREREGISTRATION_STAGE22.md", "rb").read()).hexdigest() == F["prereg_sha256"]
B5 = json.load(open(f"{S}/stage21/corr21.json"))["b05_l2w"]; SBAF = L20.c_param({"B05": {"g": B5["g"], "k": B5["k"]}})
C21 = json.load(open(f"{S}/stage21/corr21.json"))["bands"]["B11"]
VERS = {"A": ("K0", None), "B": ("K1", SBAF), "K1": ("K1", None), "C1": ("C1", None), "C2": ("C2", None), "C3": ("C1", SBAF), "S12": ("K0", L20.c_stage12)}   # B = Stage 21 K2; S12 = Stage 12 on raw (reference only, never selectable)
floor20 = json.load(open(f"{S}/stage20/floor20.json")); FLOOR20 = {"state_overlap": floor20["state_overlap"], "jump_rate": floor20["jump_rate"]}


def load(resdir):
    out = {}
    for f in glob.glob(f"{S}/stage22/{resdir}/*.json"):
        r = json.load(open(f)); run, var = os.path.basename(f)[:-5].split("__")
        for c in r.get("crops", []):
            for k, p in (c.get("points") or {}).items():
                out[(run, var, k)] = {"m0": p.get("M0"), "m3": p.get("M3"), "diag": (c.get("diag") or {}).get(k) or {}, "dsf": c.get("dsf") or {}, "toa_sub": r.get("toa_sub")}
    return out


def modal_b1(dsf):
    m = dsf.get("selected_model")
    if not m or m not in dsf: return None
    b = [x for x in dsf[m].get("b1", []) if x]
    return collections.Counter(b).most_common(1)[0][0] if b else None


def scene(rec, corr=None):
    if not rec: return None
    d = rec["diag"]; sza = d.get("sza")
    return L20.scene(rec["m0"], rec["m3"], sza, corr) if sza is not None else None


def pairs_for(set_name):
    """-> list of {key, meta, ref, c: {variant: rec}} for one set."""
    out = []
    if set_name in ("TD", "TH"):
        R = load(f"res22_{set_name}")
        for t in json.load(open(f"{S}/stage22/tasks22_{set_name}.json")):
            if "_A_" not in t["run"]: continue
            key = t["run"].split("_A_", 1)[1]; cr = t["run"].replace("_A_", "_C_")
            for c in t["crops"]:
                for la, lo, pk in c["points"]:
                    out.append({"set": set_name, "key": pk, "unit": key, "season": "winter", "geo": "global" if pk.startswith("G:") else "US",
                                "ref": R.get((t["run"], "A", pk)), "c": {v: R.get((cr, v, pk)) for v in ("K0", "K1", "C1", "C2")}, "baseline": "N0511"})
    else:
        res = {"T2D": "res22_T2", "T2H": "res22_T2", "S": "res22_S", "FLOOR": "res22_FL"}[set_name]
        task = {"T2D": "T2", "T2H": "T2", "S": "S", "FLOOR": "FL"}[set_name]
        R = load(res)
        for t in json.load(open(f"{S}/stage22/tasks22_{task}.json")):
            if "_R_" not in t["run"]: continue
            q = t["pair"]
            if set_name.startswith("T2") and q.get("split") != set_name: continue
            pk = f"{q['site']}|{q['o']}|{q['c']}"; cr = t["run"].replace("_R_", "_C_")
            cv = ("A",) if set_name == "FLOOR" else ("K0", "K1", "C1", "C2")
            out.append({"set": set_name, "key": pk, "unit": f"{q['c_time'][:10]}|{q['c_orbit']}", "season": "warm", "geo": "global" if pk.startswith(("G:", "H:")) else "US", "site": q["site"],
                        "ref": R.get((t["run"], "A", pk)), "c": {("K0" if set_name == "FLOOR" else v): R.get((cr, v, pk)) for v in cv}, "baseline": "N" + (q.get("c_baseline") or "").replace(".", ""), "meta": q})
    return out


def ice_ok(p):
    for rec in (p["ref"], p["c"].get("K0")):
        if not rec: return False
        d = rec["diag"]
        if (d.get("rhot") or {}).get("B03", 0) > 0.15: return False
        if ((rec["m0"] or {}).get("B03") or 0) > 0.05: return False
    return True


def metrics(P, version, floor, tandem):
    v, corr = VERS[version] if version in VERS else (version, None)
    pr = []
    for p in P:
        r = scene(p["ref"]); c = scene(p["c"].get(v), corr)
        if r and c: pr.append({"c": c, "r": r, "p": p})
    m = L20.pair_metrics(pr, floor=floor, tandem=tandem); m["_pairs"] = pr
    return m


def mech(P):
    """section 3-4 diagnostics on K0 vs the reference scene (and K0 -> partial corrections)."""
    rows = []
    for p in P:
        r, c0 = p["ref"], p["c"].get("K0")
        R_, C_ = scene(r), scene(c0)
        if not (R_ and C_): continue
        dr, dc = r["diag"], c0["diag"]
        row = {"key": p["key"], "set": p["set"], "season": p["season"], "dp": C_["p"] - R_["p"], "ref_hard": R_["hard"], "sun_c": 90 - dc.get("sza", 90),
               "ref_b04": (r["m0"] or {}).get("B04"), "ref_b11_rhot": (dr.get("rhot") or {}).get("B11"), "baseline": p.get("baseline"),
               "model_ref": dr.get("ac_model"), "model_c": dc.get("ac_model"), "b1_ref": modal_b1(r["dsf"]), "b1_c": modal_b1(c0["dsf"]),
               "aot_ref": dr.get("aot_550"), "aot_c": dc.get("aot_550"), "rhogref_ref": dr.get("rhog_ref"), "rhogref_c": dc.get("rhog_ref"),
               "rhog_ref": dr.get("rhog") or {}, "rhog_c": dc.get("rhog") or {}, "rhos_ref": dr.get("rhos") or {}, "rhos_c": dc.get("rhos") or {}, "rhot_ref": dr.get("rhot") or {}, "rhot_c": dc.get("rhot") or {}}
        row["switch"] = bool(row["model_ref"] != row["model_c"] or (row["b1_ref"] and row["b1_c"] and row["b1_ref"] != row["b1_c"]))
        for v in ("C1", "C2", "K1"):
            Cv = scene(p["c"].get(v))
            row[f"dp_{v}"] = (Cv["p"] - R_["p"]) if Cv else None
            dv = (p["c"].get(v) or {}).get("diag") or {}
            row[f"model_{v}"] = dv.get("ac_model"); row[f"b1_{v}"] = modal_b1((p["c"].get(v) or {}).get("dsf") or {}); row[f"aot_{v}"] = dv.get("aot_550"); row[f"rhogref_{v}"] = dv.get("rhog_ref")
        sub = (p["c"].get("C1") or {}).get("toa_sub") or {}
        row["m_C"] = (sub.get("B11") - C21["alpha"]) / C21["beta"] if sub.get("B11") is not None else None
        rows.append(row)
    return rows


def med(v): v = [x for x in v if x is not None and math.isfinite(x)]; return float(np.median(v)) if v else None


def mech_summary(rows):
    if not rows: return {"n": 0}
    sw = [r for r in rows if r["switch"]]; ns = [r for r in rows if not r["switch"]]
    out = {"n": len(rows), "switch_share": len(sw) / len(rows), "dp_switch": med([r["dp"] for r in sw]), "dp_no_switch": med([r["dp"] for r in ns]),
           "model_differs": float(np.mean([r["model_ref"] != r["model_c"] for r in rows])), "b1_differs": float(np.mean([bool(r["b1_ref"] and r["b1_c"] and r["b1_ref"] != r["b1_c"]) for r in rows])),
           "b1_ref_counts": dict(collections.Counter(r["b1_ref"] for r in rows)), "b1_c_counts": dict(collections.Counter(r["b1_c"] for r in rows)),
           "d_aot": med([(r["aot_c"] - r["aot_ref"]) for r in rows if r["aot_c"] is not None and r["aot_ref"] is not None]),
           "d_rhogref": med([(r["rhogref_c"] - r["rhogref_ref"]) for r in rows if r["rhogref_c"] is not None and r["rhogref_ref"] is not None])}
    for b in ("B02", "B03", "B04", "B05", "B8A"):
        out[f"d_rhog_{b}"] = med([r["rhog_c"].get(b, np.nan) - r["rhog_ref"].get(b, np.nan) for r in rows])
        out[f"d_rhos_{b}"] = med([r["rhos_c"].get(b, np.nan) - r["rhos_ref"].get(b, np.nan) for r in rows])
        out[f"d_rhot_{b}"] = med([r["rhot_c"].get(b, np.nan) - r["rhot_ref"].get(b, np.nan) for r in rows])
    for k, xs in (("slope_dp_vs_drhog_B04", [(r["rhog_c"].get("B04", np.nan) - r["rhog_ref"].get("B04", np.nan), r["dp"]) for r in rows]),
                  ("slope_dp_vs_daot", [((r["aot_c"] or np.nan) - (r["aot_ref"] or np.nan), r["dp"]) for r in rows])):
        v = [(x, y) for x, y in xs if math.isfinite(x) and math.isfinite(y)]
        if len(v) >= 8: sl, ic, lo, hi = theilslopes([y for x, y in v], [x for x, y in v]); out[k] = {"slope": float(sl), "ci": [float(lo), float(hi)], "n": len(v)}
    for v in ("C1", "C2", "K1"):
        out[f"dp_{v}"] = med([r[f"dp_{v}"] for r in rows]); out[f"change_K0_to_{v}"] = med([(r[f"dp_{v}"] - r["dp"]) for r in rows if r[f"dp_{v}"] is not None])
        out[f"aot_change_K0_to_{v}"] = med([(r[f"aot_{v}"] - r["aot_c"]) for r in rows if r[f"aot_{v}"] is not None and r["aot_c"] is not None])
        out[f"rhogref_change_K0_to_{v}"] = med([(r[f"rhogref_{v}"] - r["rhogref_c"]) for r in rows if r[f"rhogref_{v}"] is not None and r["rhogref_c"] is not None])
        out[f"path_change_K0_to_{v}"] = float(np.mean([bool(r[f"model_{v}"] != r["model_c"] or (r[f"b1_{v}"] and r["b1_c"] and r[f"b1_{v}"] != r["b1_c"])) for r in rows]))
    return out


def strata(rows):
    q = lambda k: np.percentile([r[k] for r in rows if r[k] is not None], [33.3, 66.7]) if any(r[k] is not None for r in rows) else [0, 0]
    b4, b11 = q("ref_b04"), q("ref_b11_rhot")
    fns = {"season": lambda r: r["season"], "sun": lambda r: "<25" if r["sun_c"] < 25 else "25-40" if r["sun_c"] < 40 else ">=40",
           "brightness": lambda r: None if r["ref_b04"] is None else "dark" if r["ref_b04"] < b4[0] else "mid" if r["ref_b04"] < b4[1] else "bright",
           "swir_dark": lambda r: None if r["ref_b11_rhot"] is None else "darkest" if r["ref_b11_rhot"] < b11[0] else "mid" if r["ref_b11_rhot"] < b11[1] else "brightest",
           "state": lambda r: L20.CLASSES[r["ref_hard"]], "baseline": lambda r: r["baseline"]}
    out = {}
    for name, fn in fns.items():
        g = collections.defaultdict(list)
        for r in rows: g[fn(r)].append(r)
        out[name] = {str(k): {"n": len(v), "dp_K0": med([r["dp"] for r in v]), "dp_C1": med([r["dp_C1"] for r in v]), "dp_C2": med([r["dp_C2"] for r in v]), "dp_K1": med([r["dp_K1"] for r in v]),
                              "switch_share": float(np.mean([r["switch"] for r in v])), "d_rhog_B04": med([r["rhog_c"].get("B04", np.nan) - r["rhog_ref"].get("B04", np.nan) for r in v])}
                     for k, v in sorted(g.items(), key=lambda kv: str(kv[0])) if k is not None and len(v) >= 5}
    return out


def strip(m): return {k: v for k, v in m.items() if not k.startswith("_")}


if MODE == "derive":
    TD, T2D = pairs_for("TD"), pairs_for("T2D")
    out = {"n_pairs": {"TD": len(TD), "T2D": len(T2D)}, "mechanism": {"TD": mech_summary(mech(TD)), "T2D": mech_summary(mech(T2D))}, "strata": strata(mech(TD) + mech(T2D)), "candidates": {}}
    for v in ("A", "B", "K1", "C1", "C2", "C3"):
        mt, m2 = metrics(TD, v, None, True), metrics(T2D, v, FLOOR20, False)
        out["candidates"][v] = {"TD": strip(mt), "T2D": strip(m2), "J": max(abs(mt.get("dp_median", 9)), abs(m2.get("dp_median", 9))),
                                "constraints_ok": bool(mt.get("n") and (mt.get("state_overlap") or 0) >= 0.95 and mt.get("jump_rate", 1) <= 0.02)}
    # D eligibility: one scene-level x, two members, Spearman >= 0.4 and J lower by >= 0.01 than the best single candidate
    fam = ["A", "C1", "C2", "C3"]
    best_single = min((c for c in fam if out["candidates"][c]["constraints_ok"]), key=lambda c: (round(out["candidates"][c]["J"], 3), fam.index(c)), default=None)
    rows = {}
    for setn, P in (("TD", TD), ("T2D", T2D)):
        for p in P:
            R_ = scene(p["ref"]); d0 = ((p["c"].get("K0") or {}).get("diag") or {})
            if not R_: continue
            x = {"sun": 90 - d0["sza"] if d0.get("sza") is not None else None, "rhogref": d0.get("rhog_ref"), "aot": d0.get("aot_550")}
            sub = (p["c"].get("C1") or {}).get("toa_sub") or {}; x["m_C"] = (sub["B11"] - C21["alpha"]) / C21["beta"] if sub.get("B11") is not None else None
            dps = {}
            for v in fam:
                vv, corr = VERS[v]; C_ = scene(p["c"].get(vv), corr); dps[v] = (C_["p"] - R_["p"]) if C_ else None
            rows.setdefault(setn, []).append({"x": x, "dp": dps})
    elig = []
    for xn in ("sun", "rhogref", "aot", "m_C"):
        allr = [r for s in rows.values() for r in s if r["x"][xn] is not None]
        if len(allr) < 20: continue
        thr = float(np.median([r["x"][xn] for r in allr]))
        for m1, m2 in itertools.combinations(fam, 2):
            v = [(r["x"][xn], r["dp"][m1] - r["dp"][m2]) for r in allr if r["dp"][m1] is not None and r["dp"][m2] is not None]
            if len(v) < 20: continue
            rho = float(spearmanr([a for a, b in v], [b for a, b in v]).correlation)
            if abs(rho) < 0.4: continue
            for lo_m, hi_m in ((m1, m2), (m2, m1)):
                J = max(abs(med([r["dp"][lo_m] if r["x"][xn] <= thr else r["dp"][hi_m] for r in rows[s] if r["x"][xn] is not None and r["dp"][lo_m] is not None and r["dp"][hi_m] is not None]) or 9) for s in ("TD", "T2D"))
                elig.append({"x": xn, "threshold": thr, "below": lo_m, "above": hi_m, "spearman": rho, "J": J})
    bestJ = out["candidates"][best_single]["J"] if best_single else 9
    D = min((e for e in elig if e["J"] <= bestJ - 0.01), key=lambda e: e["J"], default=None)
    out["D_candidates_tested"] = elig; out["D"] = D
    pool = [(c, out["candidates"][c]["J"]) for c in fam if out["candidates"][c]["constraints_ok"]] + ([("D", D["J"])] if D else [])
    if pool:
        jmin = min(j for c, j in pool); order = fam + ["D"]
        sel = min([c for c, j in pool if j <= jmin + 0.005], key=order.index); rule = "lowest J (ties within 0.005 to the simpler)"
    else:
        sel = min(fam, key=lambda c: out["candidates"][c]["J"]); rule = "fallback: no candidate met the TD constraints"
    cand = {"selected": sel, "rule": rule, "J": {c: out["candidates"][c]["J"] for c in out["candidates"]}, "D": D, "family": {k: list(v[:1]) + [bool(v[1])] for k, v in VERS.items()},
            "definition": {"A": "raw nominal S2C (K0)", "B": "Stage 21 K2 = K1 offsets + B05 adjustment", "C1": "B11/B12 frozen offsets only (glint-invariant)", "C2": "B08/B8A frozen offsets only (aerosol-invariant)",
                           "C3": "C1 + B05 adjustment", "D": D}.get(sel)}
    json.dump(out, open(f"{S}/stage22/derive22.json", "w"), indent=1, default=str); json.dump(cand, open(f"{S}/stage22/cand22.json", "w"), indent=1, default=str)
    F["cand22_sha256"] = hashlib.sha256(open(f"{S}/stage22/cand22.json", "rb").read()).hexdigest(); F["cand22_frozen_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(F, open(f"{S}/stage22/FREEZE_STAGE22.json", "w"), indent=1)
    for c, v in out["candidates"].items():
        print(f"{c:3s} J {v['J']:.4f} ok {v['constraints_ok']} | TD n {v['TD'].get('n')} dp {v['TD'].get('dp_median', float('nan')):+.4f} ov {v['TD'].get('state_overlap')} jump {v['TD'].get('jump_rate')} | T2D n {v['T2D'].get('n')} dp {v['T2D'].get('dp_median', float('nan')):+.4f} ov {v['T2D'].get('state_overlap')}")
    print("MECH TD", json.dumps(out["mechanism"]["TD"], default=str)[:1500]); print("MECH T2D", json.dumps(out["mechanism"]["T2D"], default=str)[:1500])
    print("D", D, "| SELECTED", sel, rule)
else:
    assert hashlib.sha256(open(f"{S}/stage22/cand22.json", "rb").read()).hexdigest() == F["cand22_sha256"], "cand22 not frozen"
    cand = json.load(open(f"{S}/stage22/cand22.json")); SELV = cand["selected"]
    sets = {s: pairs_for(s) for s in ("TD", "TH", "T2D", "T2H", "S", "FLOOR")}
    sets["S"] = [p for p in sets["S"] if ice_ok(p)]; sets["FLOOR"] = [p for p in sets["FLOOR"] if ice_ok(p)]
    flo = metrics(sets["FLOOR"], "A", None, True); FL = {"state_overlap": flo.get("state_overlap"), "jump_rate": flo.get("jump_rate"), "dp_median": flo.get("dp_median"), "n": flo.get("n")}
    out = {"selected": SELV, "floor_same_day": strip(flo), "sets": {}, "mechanism": {}, "strata": {}}
    for s in ("TH", "S", "T2H", "TD", "T2D"):
        out["sets"][s] = {v: strip(metrics(sets[s], v, FL if s.startswith("T2") else None, s in ("TH", "TD", "S"))) for v in ("A", "B", "K1", "C1", "C2", "C3", "S12")}
        rows = mech(sets[s]); out["mechanism"][s] = mech_summary(rows)
    out["strata"] = strata(mech(sets["TH"]) + mech(sets["T2H"]) + mech(sets["S"]))
    def dpick(P, D):                                     # the conditional candidate, applied per pair
        pr = []
        for p in P:
            R_ = scene(p["ref"]); d0 = ((p["c"].get("K0") or {}).get("diag") or {})
            if not R_: continue
            x = {"sun": 90 - d0["sza"] if d0.get("sza") is not None else None, "rhogref": d0.get("rhog_ref"), "aot": d0.get("aot_550")}
            sub = (p["c"].get("C1") or {}).get("toa_sub") or {}; x["m_C"] = (sub["B11"] - C21["alpha"]) / C21["beta"] if sub.get("B11") is not None else None
            if x[D["x"]] is None: continue
            v = D["below"] if x[D["x"]] <= D["threshold"] else D["above"]; vv, corr = VERS[v]; C_ = scene(p["c"].get(vv), corr)
            if C_: pr.append({"c": C_, "r": R_})
        return pr
    if SELV == "D":
        for s in ("TH", "S", "T2H"):
            out["sets"][s]["D"] = L20.pair_metrics(dpick(sets[s], cand["D"]), floor=FL if s.startswith("T2") else None, tandem=s in ("TH", "S"))
    # Decision A gating
    s_sites = len({p.get("site") for p in sets["S"]}); s_n = out["sets"]["S"][SELV].get("n", 0)
    gating = ["TH"] + (["S"] if s_n >= 15 and s_sites >= 3 else [])
    pooled = [pp["c"]["p"] - pp["r"]["p"] for s in gating for pp in (metrics(sets[s], SELV, None, True)["_pairs"] if SELV != "D" else dpick(sets[s], cand["D"]))]
    out["decisionA"] = {"gating": gating, "S_valid_pairs": s_n, "S_sites": s_sites, "TH_bars": out["sets"]["TH"][SELV].get("bars"), "S_bars": out["sets"]["S"][SELV].get("bars"),
                        "pooled_dp": med(pooled), "LIFT_BAR_PASSED": bool(len(gating) >= 2 and all(out["sets"][g][SELV]["bars"]["all"] for g in gating) and abs(med(pooled) or 9) <= 0.03),
                        "blocking": None if (len(gating) >= 2) else f"warm-season same-day stratum cannot gate: {s_n} valid pairs from {s_sites} site(s) (needs >= 15 from >= 3)"}
    json.dump(out, open(f"{S}/stage22/eval22.json", "w"), indent=1, default=str)
    print("FLOOR", {k: FL[k] for k in FL})
    for s in ("TH", "S", "T2H"):
        for v, m in out["sets"][s].items():
            if m.get("n"): print(f"{s:4s} {v:3s} n {m['n']:3d} dp {m['dp_median']:+.4f} ov {m['state_overlap']} jump {m['jump_rate']:.3f} bands {dict((b, None if x['median'] is None else round(10 ** x['median'], 3)) for b, x in m['band_log_ratio'].items())} bars {m['bars']['all']}")
    print("MECH TH", json.dumps(out["mechanism"]["TH"], default=str)[:1200]); print("DECISION A", out["decisionA"])
