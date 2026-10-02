"""Stage 17 (PREREGISTRATION_STAGE17.md) on DEVELOPMENT rows only, whole-lake held out with nested calibration.
Every scene (anchor and neighbours) is predicted by the fold model trained without that event's lake (outer) or by the
inner-fold model (for calibration). 64 variants: method x window x hydrology x S2C. Writes dev17.json, dev17_rows.json.
  python dev17.py [--smoke]"""
import json, math, collections, itertools, sys, glob, datetime as dt
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage16/analysis")
from lib16 import fit_post, posterior, gate, CONTAINS, op_score, op_summary, PAIR, SINGLE
from lib14 import dev_rows, fit_gbm, fold, harm, valid, features, prep, lake_boot_diff, CLASSES
import models13_lib as L
SMOKE = "--smoke" in sys.argv
E14 = json.load(open(f"{S}/stage14/engine/frozen_engine.json")); R16 = json.load(open(f"{S}/stage16/engine/rule16.json"))
T1G, T2G = R16["t1"], R16["t2"]
ALL, T1, T2, REST = dev_rows(); TT = {x["id"]: x for x in T1 + T2}
B16 = {r["id"]: r for r in json.load(open(f"{S}/stage16/analysis/dev16_rows.json"))}
sel = json.load(open(f"{S}/stage17/scenes/neighbors.json")); rain = json.load(open(f"{S}/stage17/scenes/rain17.json"))
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
# neighbour scene samples
P = {}
for f in glob.glob(f"{S}/stage17/scenes/res_nb/*.json"):
    r = json.load(open(f))
    for c in r.get("crops", []):
        for k, p in (c.get("points") or {}).items(): P[k] = p
NB = collections.defaultdict(list)
for cid, v in sel.items():
    for n in v:
        p = P.get(f"{cid}#{n['item']}")
        if not p: continue
        m0, m3 = p.get("M0"), p.get("M3")
        tier, a = (1, m0) if valid(m0) else (2, m3) if valid(m3) else (None, None)
        if tier is None or n.get("sun_elev") is None: continue
        a = harm(dict(a), n["platform"]); F, q = features(a, n["sun_elev"])
        NB[cid].append({"item": n["item"], "dt": n["dt"], "tier": tier, "platform": n["platform"], "x": [F[k] for k in L.FEATS6 + ["F_kd"]], "date": n["pass_date"]})
print("events with >= 1 usable neighbour scene:", sum(1 for v in NB.values() if v), "scenes", sum(len(v) for v in NB.values()), flush=True)
if SMOKE: sys.exit()
def wet(cid, d2):
    """section 3: incompatible if >= 20 mm total or any day >= 12.7 mm between the truth date and the scene date."""
    R = (rain.get(cid) or {}).get("rain") or {}; d1 = corp[cid]["date"]
    a, b = sorted([d1, d2]); days = [k for k in R if a <= k <= b and R[k] is not None]
    if not days: return False
    return sum(R[k] for k in days) >= 20 or max(R[k] for k in days) >= 12.7
inner = lambda x: fold(x["lake"], 20) % 4
EVENTS = [r for r in B16.values()]
def anchor_x(cid):
    x = TT.get(cid)
    return [x["F"][k] for k in L.FEATS6 + ["F_kd"]] if x else None
# ---------------- predictions: outer (by g_k) and inner (by g_kj), for anchors and neighbours
PRED = {}      # (cid, "outer"|"inner", k) -> {"anchor": p or None, "nb": [p...]}
for k in range(5):
    gk = fit_gbm([x for x in T1 if fold(x["lake"]) != k])
    gkj = {j: fit_gbm([x for x in T1 if fold(x["lake"]) != k and inner(x) != j]) for j in range(4)}
    for e in EVENTS:
        cid = e["id"]; ax = anchor_x(cid); xs = [n["x"] for n in NB.get(cid, [])]
        if e["fold"] == k: g = gk; key = (cid, "outer", k)
        else:
            if fold(e["lake"]) == k: continue
            g = gkj[fold(e["lake"], 20) % 4]; key = (cid, "inner", k)
        X = ([ax] if ax else []) + xs
        pr = [float(v) for v in g.predict(np.array(X))] if X else []
        PRED[key] = {"anchor": pr[0] if ax else None, "nb": pr[1:] if ax else pr}
    print("fold", k, "predicted", flush=True)
def scene_list(e, key, W, H, smode):
    """contributing scenes [(p, tier, platform, |dt|, is_anchor)] under window W, hydrology H, S2C mode."""
    cid = e["id"]; pr = PRED[key]; out = []
    if pr["anchor"] is not None and e["tier"] in (1, 2):
        out.append({"p": pr["anchor"], "tier": e["tier"], "platform": e["platform"], "adt": abs(int(corp[cid]["dt"])) if corp[cid].get("dt") is not None else 0, "anchor": True})
    for n, p in zip(NB.get(cid, []), pr["nb"]):
        if abs(n["dt"]) > W: continue
        if H == "H1" and wet(cid, n["date"]): continue
        out.append({"p": p, "tier": n["tier"], "platform": n["platform"], "adt": abs(n["dt"]), "anchor": False})
    return out
def scene_state(s, post):
    P = post["post2"] if s["tier"] == 2 else post["post1"]
    st, conf, w = gate(s["p"], P, T1G, T2G, boundary_only=(s["tier"] == 2)); return st
def combine(sc, method, par, anchor_p):
    if method == "M-agree": return anchor_p
    v = np.array([par["sig"][s["tier"]] ** 2 + par["kappa"] * s["adt"] for s in sc]); p = np.array([s["p"] for s in sc]); w = 1 / v
    if method == "M-iuw" or len(sc) == 1: return float(np.sum(w * p) / np.sum(w))
    if method == "M-robust":
        mu = float(np.sum(w * p) / np.sum(w))
        for _ in range(25):
            r = (p - mu) / np.sqrt(v); hw = w * np.minimum(1.0, 1.5 / np.maximum(np.abs(r), 1e-9)); mu = float(np.sum(hw * p) / np.sum(hw))
        return mu
    if method == "M-bayes":
        return float((par["mu0"] / par["s0"] ** 2 + np.sum(p / v)) / (1 / par["s0"] ** 2 + np.sum(1 / v)))
def build(e, key, method, W, H, smode, par, post, cal):
    """-> product dict o (Stage 15 rubric fields) + meta."""
    base = B16[e["id"]]["o"]
    sc = scene_list(e, key, W, H, smode)
    full = [s for s in sc if s["platform"] != "sentinel-2c"]
    if not full: return dict(base, n_full=0, agree=0, consensus=False)
    s2c = [s for s in sc if s["platform"] == "sentinel-2c"]
    use = list(full)
    if smode == "S-agree" and s2c:
        pf = combine(full, "M-iuw", par, None); stf = gate(pf, post["post1"], T1G, T2G)[0]
        for s in s2c:
            st = scene_state(s, post)
            if st and stf and (CONTAINS[st] & CONTAINS[stf]): use.append(s)
    anchor_p = next((s["p"] for s in full if s["anchor"]), None)
    if method == "M-agree":
        # section 4: the prediction AND the state stay the anchor's (Stage 16); neighbours change only the evidence level
        if anchor_p is None or base["state"] not in CONTAINS or base["authority"] != "full": return dict(base, n_full=len(full), agree=0, consensus=False)
        ags = [s for s in use if (s["platform"] != "sentinel-2c" or smode == "S-agree")]
        states = [scene_state(s, post) for s in ags]
        o = dict(base); st = base["state"]
        o.update(n_full=len(full), n_use=len(use), consensus=True, s2c_used=len(use) - len(full), p=anchor_p,
                 agree=sum(1 for x in states if x and CONTAINS[x] >= CONTAINS[st]), disjoint=any(x and not (CONTAINS[x] & CONTAINS[st]) for x in states))
        return o
    pc = combine(use, method, par, anchor_p)
    n = len(use); allt2 = all(s["tier"] == 2 for s in use)
    if method == "M-agree" or n == 1: Pp = post["post2"] if (allt2 and n == 1) else post["post1"]
    else: Pp = cal.get("n2" if n == 2 else "n3", post["post1"])
    st, conf, w = gate(pc, Pp, T1G, T2G, boundary_only=allt2)
    o = {"tier": 1 if not allt2 else 2, "state": st or "Unknown / Low Authority", "authority": "full" if st else "none", "display": "exact" if st else "none",
         "floor_D": None, "withheld": None if st else w, "algal": None, "s2c": False, "conf": conf, "p": pc}
    ags = [s for s in use if (s["platform"] != "sentinel-2c" or smode == "S-agree")]
    states = [scene_state(s, post) for s in ags]
    agree = sum(1 for x in states if st and x and CONTAINS[x] >= CONTAINS[st])        # section 6: the scene's state contains the issued state
    disjoint = any(st and x and not (CONTAINS[x] & CONTAINS[st]) for x in states)
    o.update(n_full=len(full), n_use=n, agree=agree, disjoint=disjoint, consensus=True, s2c_used=len(use) - len(full))
    return o
def strong(o):
    return o["state"] in CONTAINS and o["authority"] == "full" and (o.get("conf") or 0) >= 0.90 and o.get("agree", 0) >= 2 and not o.get("disjoint", False)
def evidence(o):
    if o["state"] not in CONTAINS: return "unavailable"
    if o["authority"] == "lower": return "weak"
    return "strong" if strong(o) else "moderate"
# ---------------- per fold parameters (inner), then the 64 variants
METHODS = ["M-agree", "M-iuw", "M-robust", "M-bayes"]; WINS = [3, 5, 7, 10]; HS = ["H1", "H0"]; SMS = ["S-off", "S-agree"]
PAR, POST = {}, {}
for k in range(5):
    ins = [e for e in EVENTS if e["fold"] != k and (e["id"], "inner", k) in PRED]
    an = [(PRED[(e["id"], "inner", k)]["anchor"], e["y"], e["tier"]) for e in ins if PRED[(e["id"], "inner", k)]["anchor"] is not None and e["tier"] in (1, 2)]
    POST[k] = {"post1": fit_post([(p, y) for p, y, t in an if t == 1]), "post2": fit_post([(p, y) for p, y, t in an if t == 2])}
    mad = lambda r: 1.4826 * float(np.median(np.abs(np.array(r) - np.median(r))))
    sig = {t: mad([y - p for p, y, tt in an if tt == t]) for t in (1, 2)}
    dd, sep = [], []
    for e in ins:
        pr = PRED[(e["id"], "inner", k)]
        if pr["anchor"] is None or e["tier"] not in (1, 2): continue
        for n, p in zip(NB.get(e["id"], []), pr["nb"]):
            dd.append((p - pr["anchor"]) ** 2); sep.append(abs(n["dt"]) + abs(int(corp[e["id"]].get("dt") or 0)))
    A = np.vstack([np.ones(len(sep)), sep]).T; coef = np.linalg.lstsq(A, np.array(dd), rcond=None)[0] if dd else [0, 0]
    ys = [e["y"] for e in ins]
    PAR[k] = {"sig": sig, "kappa": max(0.0, float(coef[1])), "mu0": float(np.mean(ys)), "s0": float(np.std(ys)), "n_pairs": len(dd)}
    print("fold", k, "sigma", {t: round(v, 3) for t, v in sig.items()}, "kappa", round(PAR[k]["kappa"], 5), "pairs", len(dd), flush=True)
RES = {}
for method, W, H, sm in itertools.product(METHODS, WINS, HS, SMS):
    rows = []
    for k in range(5):
        ins = [e for e in EVENTS if e["fold"] != k and (e["id"], "inner", k) in PRED]
        cal = {}
        if method != "M-agree":
            grp = {"n2": [], "n3": []}
            for e in ins:
                o = build(e, (e["id"], "inner", k), method, W, H, sm, PAR[k], POST[k], {})
                if o.get("consensus") and o.get("n_use", 1) >= 2: grp["n2" if o["n_use"] == 2 else "n3"].append((o["p"], e["y"]))
            cal = {g: fit_post(v) for g, v in grp.items() if len(v) >= 40}
        for e in EVENTS:
            if e["fold"] != k: continue
            o = build(e, (e["id"], "outer", k), method, W, H, sm, PAR[k], POST[k], cal)
            sc_, oc, h, sv = op_score(o, e["c"], e["secchi"])
            rows.append({"id": e["id"], "lake": e["lake"], "c": e["c"], "y": e["y"], "secchi": e["secchi"], "tier": e["tier"], "platform": e["platform"], "insitu_type": e["insitu_type"], "turb": e["turb"],
                         "o": o, "score": sc_, "outcome": oc, "harmful": h, "severe": sv, "ev": evidence(o), "p_c": o.get("p", e.get("p"))})
    RES[(method, W, H, sm)] = rows
def summarize(rows):
    s = op_summary(rows); u = [r for r in rows if r["ev"] != "unavailable"]; st = [r for r in rows if r["ev"] == "strong"]
    stn = [r for r in rows if r["c"] == 2 and r["o"]["state"] in CONTAINS and r["o"]["authority"] == "full"]
    return {"bal": s["balanced"], "harm": s["harmful_rate"], "sev": s["severe_rate"], "per_class": {n: v["mean"] for n, v in s["per_class"].items()},
            "strong_share_usable": len(st) / len(u) if u else 0, "strong_acc": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in st])) if st else None, "n_strong": len(st),
            "evidence": dict(collections.Counter(r["ev"] for r in rows)), "stained_harm": float(np.mean([r["harmful"] for r in rows if r["c"] == 2])),
            "stained_answer_acc": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in stn])) if stn else None,
            "mean_conf": float(np.mean([r["o"].get("conf") or 0 for r in rows if r["o"]["state"] in CONTAINS])), "outcomes": s["outcomes"]}
SUM = {"|".join(map(str, k)): summarize(v) for k, v in RES.items()}
base = [dict(r, ev=None) for r in B16.values()]
for r in base: r["ev"] = ("unavailable" if r["o"]["state"] not in CONTAINS else "weak" if r["o"]["authority"] == "lower" else "strong" if (r["o"].get("conf") or 0) >= 0.90 and r["tier"] == 1 and not r["o"]["s2c"] and not r["o"]["algal"] else "moderate")
B = summarize(base)
order = lambda k: (METHODS.index(k[0]), WINS.index(k[1]), HS.index(k[2]), SMS.index(k[3]))
cands = [k for k in RES if SUM["|".join(map(str, k))]["harm"] <= B["harm"] + 1e-9 and SUM["|".join(map(str, k))]["sev"] <= B["sev"] + 1e-9]
best = max((SUM["|".join(map(str, k))]["bal"] for k in cands), default=None)
SELK = min([k for k in cands if SUM["|".join(map(str, k))]["bal"] >= best - 0.01], key=order) if cands else None
out = {"baseline_stage16": B, "variants": SUM, "n_candidates": len(cands), "params": PAR}
if SELK:
    rows = RES[SELK]; s = SUM["|".join(map(str, SELK))]
    bmap = {r["id"]: r for r in base}
    for r in rows: r["lake"] = bmap[r["id"]]["lake"]
    def dstained(rs):
        ids = [r["id"] for r in rs if r["c"] == 2]; m = {r["id"]: r for r in rows}
        return float(np.mean([m[i]["score"] for i in ids]) - np.mean([bmap[i]["score"] for i in ids]))
    pairs = [{"id": r["id"], "lake": r["lake"], "c": r["c"]} for r in rows]
    ci = lake_boot_diff(pairs, dstained, B=2000, seed=17)
    useful = (s["per_class"]["stained"] - B["per_class"]["stained"] >= 0.05 and ci is not None and ci[0] > 0 and s["harm"] <= B["harm"] + 1e-9 and s["sev"] <= B["sev"] + 1e-9 and s["bal"] >= B["bal"] - 1e-9)
    # S2C upgrade test (section 5): S-agree vs S-off at the selected method/window/hydro
    ka, ko = (SELK[0], SELK[1], SELK[2], "S-agree"), (SELK[0], SELK[1], SELK[2], "S-off")
    ra, ro = {r["id"]: r for r in RES[ka]}, {r["id"]: r for r in RES[ko]}
    rank = {"unavailable": 0, "weak": 1, "moderate": 2, "strong": 3}
    up = [ra[i] for i in ra if ra[i]["o"].get("s2c_used", 0) > 0 and rank[ra[i]["ev"]] > rank[ro[i]["ev"]]]
    up_acc = float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in up])) if up else None
    s2c_yes = bool(len(up) >= 30 and up_acc is not None and up_acc >= 0.90 and SUM["|".join(map(str, ka))]["harm"] <= SUM["|".join(map(str, ko))]["harm"] + 1e-9)
    dev9 = s["bal"] >= 0.85 and min(s["per_class"].values()) >= 0.80 and s["harm"] <= 0.05 and s["sev"] <= 0.005 and s["strong_share_usable"] >= 0.50 and (s["strong_acc"] or 0) >= 0.90
    s16bars = int(round(10 * s["bal"] + 1e-9)) >= 7 and min(s["per_class"].values()) >= 0.60 and s["harm"] <= 0.15 and s["sev"] <= 0.02
    out.update({"selected": list(SELK), "selected_summary": s, "useful": useful, "stained_diff_ci": ci, "s2c_upgrade": {"n_upgraded": len(up), "accuracy": up_acc, "YES": s2c_yes},
                "dev9_passed": dev9, "stage16_bars_met": s16bars, "capability": int(round(10 * s["bal"] + 1e-9))})
    # feet: exact feet from the consensus prediction on full-authority answers (Stage 12 rubric)
    src = open(f"{S}/stage13/analysis/capscore13.py").read()
    def capscore(rr):
        ns = {}; code = src.split("rows = [r for r in")[0].replace('M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]', 'ENG = "dev17"')
        code += "\nrows = RR\n" + "out = {" + src.split("out = {", 1)[1].split("json.dump(out")[0]; ns["RR"] = rr; exec(code, ns); return ns["out"]
    from lib14 import hard_std
    def recs(rs):
        o_ = []
        for r in rs:
            o = r["o"]; shown = o["state"] in CONTAINS and o["authority"] == "full" and o.get("display") in ("exact", "approx")
            pv = o.get("p") if o.get("consensus") else bmap[r["id"]]["p"]
            pred = CLASSES[hard_std(pv)] if (pv is not None and r["tier"] in (1, 2)) else ("clear" if o["state"] == "Clear" else "unknown")
            o_.append({"true": CLASSES[r["c"]], "pred": pred, "ft": 10 ** pv if (shown and pv is not None) else None, "secchi": r["secchi"], "feet": bool(shown and pv is not None), "insitu_type": r["insitu_type"], "turb": r["turb"]})
        return o_
    out["feet_selected"] = capscore(recs(rows))["EXACT_FEET_CAPABILITY"]; out["feet_stage16"] = capscore(recs(base))["EXACT_FEET_CAPABILITY"]
    out["feet_err_selected"] = float(np.median([abs(r["o"]["p"] - r["y"]) for r in rows if r["o"].get("consensus") and r["o"]["state"] in CONTAINS]))
    out["feet_err_stage16_same_rows"] = float(np.median([abs(bmap[r["id"]]["p"] - r["y"]) for r in rows if r["o"].get("consensus") and r["o"]["state"] in CONTAINS and bmap[r["id"]]["p"] is not None]))
    json.dump(rows, open(f"{S}/stage17/analysis/dev17_rows.json", "w"), default=str)
EXTRA = {}
bm = {r["id"]: r for r in base}
for k in [("M-iuw", 10, "H0", "S-off"), ("M-bayes", 10, "H0", "S-agree"), ("M-agree", 10, "H0", "S-off")]:
    rs = RES[k]; m = {r["id"]: r for r in rs}
    pr = [{"id": r["id"], "lake": bm[r["id"]]["lake"], "c": r["c"]} for r in rs]
    def dst(x, c=None, f="score"):
        ids = [r["id"] for r in x if c is None or r["c"] == c]
        return float(np.mean([float(m[i][f]) for i in ids]) - np.mean([float(bm[i][f]) for i in ids]))
    def dbal(x):
        cs = [c for c in range(4) if any(r["c"] == c for r in x)]
        return float(np.mean([np.mean([m[r["id"]]["score"] for r in x if r["c"] == c]) - np.mean([bm[r["id"]]["score"] for r in x if r["c"] == c]) for c in cs]))
    EXTRA["|".join(map(str, k))] = {"stained_diff_ci": lake_boot_diff(pr, lambda x: dst(x, 2), B=2000, seed=17), "harm_diff_ci": lake_boot_diff(pr, lambda x: dst(x, None, "harmful"), B=2000, seed=17),
                                     "bal_diff_ci": lake_boot_diff(pr, dbal, B=2000, seed=17),
                                     "feet_err": float(np.median([abs(r["o"]["p"] - r["y"]) for r in rs if r["o"].get("consensus") and r["o"].get("p") is not None])),
                                     "feet_err_anchor_same_rows": float(np.median([abs(bm[r["id"]]["p"] - r["y"]) for r in rs if r["o"].get("consensus") and r["o"].get("p") is not None and bm[r["id"]].get("p") is not None])),
                                     "n_consensus": sum(1 for r in rs if r["o"].get("consensus"))}
out["extra"] = EXTRA
json.dump(out, open(f"{S}/stage17/analysis/dev17.json", "w"), indent=1, default=str)
print("Stage 16 baseline", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in B.items() if k not in ("outcomes", "evidence")})
for k in sorted(SUM, key=lambda k: -SUM[k]["bal"])[:12]:
    v = SUM[k]; print(f"{k:28s} bal {v['bal']:.3f} harm {v['harm']:.3f} sev {v['sev']:.4f} stained {v['per_class']['stained']:.3f} strong {v['strong_share_usable']:.2f}/{(v['strong_acc'] or 0):.2f}")
print("SELECTED", out.get("selected"), "useful", out.get("useful"), "CI", out.get("stained_diff_ci"), "S2C", out.get("s2c_upgrade"), "dev9", out.get("dev9_passed"), "s16bars", out.get("stage16_bars_met"))
