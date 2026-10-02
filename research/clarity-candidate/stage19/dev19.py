"""Stage 19 (PREREGISTRATION_STAGE19.md): the Stage 18 physical-pass consensus run CAUSALLY - the anchor (current pass)
plus up to 3 independent passes sensed strictly before it (stage19/neighbors19.json), ages measured from the anchor.
Shares the frozen data loading and fold predictions of stage18p/dev18p.py (itself the frozen dev17 code).
Stage 18P (PREREGISTRATION_STAGE18P.md): the frozen Stage 17 consensus code, rebuilt on unique PHYSICAL passes.
Identical to stage17/analysis/dev17.py except: neighbours from stage18p/neighbors18.json (<= 3 independent passes, the
anchor's own pass excluded), samples from res_nb + res_nb18, no hydrology rule (H0), S2C off, and the Stage 18P
selection/decisions. Originally: Stage 17 (PREREGISTRATION_STAGE17.md) on DEVELOPMENT rows only, whole-lake held out with nested calibration.
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
sel = json.load(open(f"{S}/stage19/neighbors19.json")); rain = json.load(open(f"{S}/stage17/scenes/rain17.json"))
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
# neighbour scene samples
P = {}
for f in glob.glob(f"{S}/stage17/scenes/res_nb/*.json") + glob.glob(f"{S}/stage18p/res_nb18/*.json") + glob.glob(f"{S}/stage19/res_nb19/*.json"):
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
        NB[cid].append({"item": n["item"], "dt": n["dt"], "tier": tier, "platform": n["platform"], "x": [F[k] for k in L.FEATS6 + ["F_kd"]], "date": n["pass_date"], "pass_key": n["pass_key"], "age": n["age"], "pass_time": n["pass_time"]})
# no physical pass twice: the anchor's pass and every neighbour's are distinct (asserted)
for cid, v in NB.items():
    a = corp[cid]; keys = [f"{a['platform']}|{a['item'].split('_')[2][:8]}"] + [n["pass_key"] for n in v]
    assert len(keys) == len(set(keys)), cid
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
METHODS = ["M-agree", "M-iuw", "M-robust", "M-bayes"]; WINS = [3, 5, 7, 10]; HS = ["H0"]; SMS = ["S-off"]
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

# ======================= Stage 19: causal consensus (PREREGISTRATION_STAGE19.md sections 3-9)
from lib14 import hard_std
# summarize(): verbatim from stage17/analysis/dev17.py
def summarize(rows):
    s = op_summary(rows); u = [r for r in rows if r["ev"] != "unavailable"]; st = [r for r in rows if r["ev"] == "strong"]
    stn = [r for r in rows if r["c"] == 2 and r["o"]["state"] in CONTAINS and r["o"]["authority"] == "full"]
    return {"bal": s["balanced"], "harm": s["harmful_rate"], "sev": s["severe_rate"], "per_class": {n: v["mean"] for n, v in s["per_class"].items()},
            "strong_share_usable": len(st) / len(u) if u else 0, "strong_acc": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in st])) if st else None, "n_strong": len(st),
            "evidence": dict(collections.Counter(r["ev"] for r in rows)), "stained_harm": float(np.mean([r["harmful"] for r in rows if r["c"] == 2])),
            "stained_answer_acc": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in stn])) if stn else None,
            "mean_conf": float(np.mean([r["o"].get("conf") or 0 for r in rows if r["o"]["state"] in CONTAINS])), "outcomes": s["outcomes"]}
assert all(n["age"] >= 0 for v in NB.values() for n in v)            # never a future pass (sensing time < anchor asserted in passes19.py)
def scene_list(e, key, W, H, smode):
    """Causal: the anchor (age 0, newest evidence) and prior passes with age <= W, nearest first."""
    cid = e["id"]; pr = PRED[key]; out = []
    if pr["anchor"] is not None and e["tier"] in (1, 2):
        out.append({"p": pr["anchor"], "tier": e["tier"], "platform": e["platform"], "adt": 0, "anchor": True})
    for n, p in zip(NB.get(cid, []), pr["nb"]):
        if n["age"] > W: continue
        out.append({"p": p, "tier": n["tier"], "platform": n["platform"], "adt": n["age"], "anchor": False, "age": n["age"]})
    return out
# Stage 18 uncertainty parameters, per fold, unchanged (sigma by tier, kappa); POST[k] (Stage 16 posteriors) recomputed identically
P18 = json.load(open(f"{S}/stage18p/dev18p.json"))["params"]
for k in range(5):
    PAR[k]["sig"] = {int(t): v for t, v in P18[str(k)]["sig"].items()}; PAR[k]["kappa"] = P18[str(k)]["kappa"]
WIN19 = [3, 5, 7, 10, 15]; PRIMARY = [3, 5, 7, 10]
CAL = {}
def run(W, guard=False):
    rows = []
    for k in range(5):
        ins = [e for e in EVENTS if e["fold"] != k and (e["id"], "inner", k) in PRED]
        grp = {"n2": [], "n3": []}
        for e in ins:
            o = build(e, (e["id"], "inner", k), "M-iuw", W, "H0", "S-off", PAR[k], POST[k], {})
            if o.get("consensus") and o.get("n_use", 1) >= 2: grp["n2" if o["n_use"] == 2 else "n3"].append((o["p"], e["y"]))
        cal = {g: fit_post(v) for g, v in grp.items() if len(v) >= 40}; CAL[(W, k)] = {g: len(v) for g, v in grp.items()}
        for e in EVENTS:
            if e["fold"] != k: continue
            key = (e["id"], "outer", k)
            o = build(e, key, "M-iuw", W, "H0", "S-off", PAR[k], POST[k], cal)
            if guard: o = guard_g1(e, key, W, k, cal, o)
            sc_, oc, h, sv = op_score(o, e["c"], e["secchi"])
            rows.append({"id": e["id"], "lake": e["lake"], "c": e["c"], "y": e["y"], "secchi": e["secchi"], "tier": e["tier"], "platform": e["platform"], "insitu_type": e["insitu_type"],
                         "turb": e["turb"], "fold": k, "o": o, "score": sc_, "outcome": oc, "harmful": h, "severe": sv, "ev": evidence(o)})
    return rows
def prior_state(e, key, W, k, cal):
    """The gate state of the prior-only consensus (anchor excluded), S2A/B full-authority scenes."""
    pr = [s for s in scene_list(e, key, W, "H0", "S-off") if not s["anchor"] and s["platform"] != "sentinel-2c"]
    if not pr: return None, None
    pc = combine(pr, "M-iuw", PAR[k], None); allt2 = all(s["tier"] == 2 for s in pr); n = len(pr)
    Pp = (POST[k]["post2"] if allt2 else POST[k]["post1"]) if n == 1 else cal.get("n2" if n == 2 else "n3", POST[k]["post1"])
    return gate(pc, Pp, T1G, T2G, boundary_only=allt2)[0], pc
def guard_g1(e, key, W, k, cal, o):
    a = [s for s in scene_list(e, key, W, "H0", "S-off") if s["anchor"]]
    if not a or e["platform"] == "sentinel-2c" or not o.get("consensus"): return o
    st_a = scene_state(a[0], POST[k]); st_p, _ = prior_state(e, key, W, k, cal)
    if st_a and st_p and not (CONTAINS[st_a] & CONTAINS[st_p]): return dict(B16[e["id"]]["o"], n_full=o.get("n_full"), agree=0, consensus=False, guarded=True)
    return o
RES19 = {W: run(W) for W in WIN19}
SUM19 = {W: summarize(v) for W, v in RES19.items()}
base = [dict(r, ev=None) for r in B16.values()]
for r in base: r["ev"] = ("unavailable" if r["o"]["state"] not in CONTAINS else "weak" if r["o"]["authority"] == "lower" else "strong" if (r["o"].get("conf") or 0) >= 0.90 and r["tier"] == 1 and not r["o"]["s2c"] and not r["o"]["algal"] else "moderate")
bmap = {r["id"]: r for r in base}
B18 = json.load(open(f"{S}/stage18p/dev18p_rows.json")); b18 = {r["id"]: r for r in B18}
for r in B18: r["lake"] = bmap[r["id"]]["lake"]
A = summarize(base); Bs = summarize(B18)
def pval(r): return r["o"].get("p") if r["o"].get("consensus") else bmap[r["id"]].get("p")
def extra(rows):
    ans = [r for r in rows if r["o"]["state"] in CONTAINS]; st = [r for r in rows if r["c"] == 2]; sta = [r for r in st if r["o"]["state"] in CONTAINS]
    stf = [r for r in sta if r["o"]["authority"] == "full"]
    return {"unknown_share": 1 - len(ans) / len(rows), "n_consensus_2plus": sum(1 for r in rows if r["o"].get("consensus") and r["o"].get("n_use", 0) >= 2),
            "stained": {"n": len(st), "operational": float(np.mean([r["score"] for r in st])), "truth_in_answer": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in stf])) if stf else None,
                        "harmful": float(np.mean([r["harmful"] for r in st])), "severe": float(np.mean([r["severe"] for r in st])),
                        "conf": float(np.mean([r["o"].get("conf") or 0 for r in sta])) if sta else None, "unknown": 1 - len(sta) / len(st)}}
for s_, rows in [(A, base), (Bs, B18)] + [(SUM19[W], RES19[W]) for W in WIN19]: s_.update(extra(rows))
shown = lambda o: o["state"] in CONTAINS and o["authority"] == "full" and o.get("display") in ("exact", "approx")
def feet_same(rows_list):
    """median |log10 error| on rows where every system shows feet, overall and stained."""
    ids = [r["id"] for r in base if all(shown(m[r["id"]]["o"]) and pv(m[r["id"]]) is not None for m, pv in rows_list)]
    out = {}
    for name, (m, pv) in zip(["A", "B", "C"], rows_list):
        out[name] = float(np.median([abs(pv(m[i]) - m[i]["y"]) for i in ids])); out[name + "_stained"] = float(np.median([abs(pv(m[i]) - m[i]["y"]) for i in ids if m[i]["c"] == 2]))
    out["n"] = len(ids); out["n_stained"] = sum(1 for i in ids if bmap[i]["c"] == 2); return out
pA = lambda r: r.get("p"); pB = lambda r: r["o"].get("p") if r["o"].get("consensus") else bmap[r["id"]].get("p")
src = open(f"{S}/stage13/analysis/capscore13.py").read()
def capscore(rr):
    ns = {}; code = src.split("rows = [r for r in")[0].replace('M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]', 'ENG = "dev19"')
    code += "\nrows = RR\n" + "out = {" + src.split("out = {", 1)[1].split("json.dump(out")[0]; ns["RR"] = rr; exec(code, ns); return ns["out"]
def recs(rows, pv):
    o_ = []
    for r in rows:
        o = r["o"]; p = pv(r)
        pred = CLASSES[hard_std(p)] if (p is not None and r["tier"] in (1, 2)) else ("clear" if o["state"] == "Clear" else "unknown")
        o_.append({"true": CLASSES[r["c"]], "pred": pred, "ft": 10 ** p if (shown(o) and p is not None) else None, "secchi": r["secchi"], "feet": bool(shown(o) and p is not None),
                   "insitu_type": r["insitu_type"], "turb": r["turb"]})
    return o_
bars = lambda s: int(round(10 * s["bal"] + 1e-9)) >= 7 and min(s["per_class"].values()) >= 0.60 and s["harm"] <= 0.15 and s["sev"] <= 0.02
dev9 = lambda s: s["bal"] >= 0.85 and min(s["per_class"].values()) >= 0.80 and s["harm"] <= 0.05 and s["sev"] <= 0.005 and s["strong_share_usable"] >= 0.50 and (s["strong_acc"] or 0) >= 0.90
def boot(rows_c, rows_ref):
    mc = {r["id"]: r for r in rows_c}; mr = {r["id"]: r for r in rows_ref}
    pr = [{"id": r["id"], "lake": bmap[r["id"]]["lake"], "c": r["c"]} for r in rows_c]
    def d(x, c=None, f="score"):
        ids = [r["id"] for r in x if c is None or r["c"] == c]
        return float(np.mean([float(mc[i][f]) for i in ids]) - np.mean([float(mr[i][f]) for i in ids]))
    def dbal(x):
        cs = [c for c in range(4) if any(r["c"] == c for r in x)]
        return float(np.mean([np.mean([mc[r["id"]]["score"] for r in x if r["c"] == c]) - np.mean([mr[r["id"]]["score"] for r in x if r["c"] == c]) for c in cs]))
    return {"stained": d(pr, 2), "stained_ci": lake_boot_diff(pr, lambda x: d(x, 2), B=2000, seed=19), "bal": dbal(pr), "bal_ci": lake_boot_diff(pr, dbal, B=2000, seed=19),
            "harm": d(pr, None, "harmful"), "harm_ci": lake_boot_diff(pr, lambda x: d(x, None, "harmful"), B=2000, seed=19),
            "severe": d(pr, None, "severe"), "severe_ci": lake_boot_diff(pr, lambda x: d(x, None, "severe"), B=2000, seed=19)}
out = {"A_stage16": A, "B_stage18": Bs, "C_causal": {str(W): SUM19[W] for W in WIN19}, "params_stage18": P18, "calibration_rows": {f"{W}|{k}": v for (W, k), v in CAL.items()}}
out["vs_stage16"] = {str(W): boot(RES19[W], base) for W in WIN19}; out["vs_stage18"] = {str(W): boot(RES19[W], B18) for W in WIN19}
# ---- prior-pass availability (valid scenes, per window)
avail = {}
for W in WIN19:
    cnt = collections.Counter(); cnt_full = collections.Counter()
    for e in EVENTS:
        v = [n for n in NB.get(e["id"], []) if n["age"] <= W]
        cnt[min(3, len(v))] += 1; cnt_full[min(3, sum(1 for n in v if n["platform"] != "sentinel-2c"))] += 1
    avail[str(W)] = {"valid_prior_passes": {n: cnt[n] / len(EVENTS) for n in range(4)}, "valid_prior_s2ab": {n: cnt_full[n] / len(EVENTS) for n in range(4)}}
out["prior_availability"] = avail
# ---- window selection (section 5)
cands = [W for W in PRIMARY if bars(SUM19[W])]
SEL = None
if cands:
    best = max(cands, key=lambda W: SUM19[W]["bal"]); eq = {}
    for W in cands:
        if W == best: eq[W] = True; continue
        b = boot(RES19[W], RES19[best]); eq[W] = (b["bal_ci"][0] <= 0 <= b["bal_ci"][1]) and (b["stained_ci"][0] <= 0 <= b["stained_ci"][1]); out.setdefault("equivalence", {})[str(W)] = {"vs_best": best, **b, "equivalent": eq[W]}
    SEL = min(W for W in cands if eq[W])
out["candidates"] = cands; out["selected_window"] = SEL
Wd = SEL if SEL else 10; S_ = SUM19[Wd]; V = out["vs_stage16"][str(Wd)]
# ---- Strong (section 6)
def strong_detail(W):
    ages, nsup = [], []
    for r in RES19[W]:
        if r["ev"] != "strong": continue
        e = next(x for x in EVENTS if x["id"] == r["id"]); k = r["fold"]; key = (e["id"], "outer", k)
        sc = [s for s in scene_list(e, key, W, "H0", "S-off") if s["platform"] != "sentinel-2c"]
        sup = [s for s in sc if (scene_state(s, POST[k]) and CONTAINS[scene_state(s, POST[k])] >= CONTAINS[r["o"]["state"]])]
        nsup.append(len(sup)); ages += [s["adt"] for s in sup if not s["anchor"]]
    return {"n": len(nsup), "median_age_of_supporting_prior_passes": float(np.median(ages)) if ages else None, "share_2": float(np.mean([n == 2 for n in nsup])) if nsup else None,
            "share_3plus": float(np.mean([n >= 3 for n in nsup])) if nsup else None}
out["strong_detail"] = {str(W): strong_detail(W) for W in WIN19}
# ---- current-pass priority (section 7)
def priority(W):
    res = {"D1_nonadjacent": [], "D1_disjoint": [], "D2_class_jump": [], "D3_numeric": []}; pop = 0
    for r in RES19[W]:
        b = bmap[r["id"]]; o = r["o"]
        if r["tier"] not in (1, 2) or r["platform"] == "sentinel-2c" or b["o"]["state"] not in CONTAINS or b["o"]["authority"] != "full": continue
        if not (o.get("consensus") and o.get("n_use", 0) >= 2) or b.get("p") is None: continue
        pop += 1; A_, C_ = CONTAINS[b["o"]["state"]], CONTAINS.get(o["state"], set())
        if C_ and not (A_ & C_):
            res["D1_disjoint"].append(r)
            if min(abs(a - c) for a in A_ for c in C_) >= 2: res["D1_nonadjacent"].append(r)
        if abs(hard_std(o["p"]) - hard_std(b["p"])) >= 2: res["D2_class_jump"].append(r)
        if abs(o["p"] - b["p"]) >= 0.176: res["D3_numeric"].append(r)
    rep = {"population": pop}
    for kk, rs in res.items():
        rep[kk] = {"n": len(rs), "consensus_truth_in_answer": float(np.mean([r["c"] in CONTAINS.get(r["o"]["state"], set()) for r in rs])) if rs else None,
                   "anchor_truth_in_answer": float(np.mean([r["c"] in CONTAINS[bmap[r["id"]]["o"]["state"]] for r in rs])) if rs else None,
                   "consensus_harmful": float(np.mean([r["harmful"] for r in rs])) if rs else None, "anchor_harmful": float(np.mean([bmap[r["id"]]["harmful"] for r in rs])) if rs else None,
                   "consensus_closer": float(np.mean([abs(r["o"]["p"] - r["y"]) < abs(bmap[r["id"]]["p"] - r["y"]) for r in rs])) if rs else None}
        x = rep[kk]; x["problem"] = bool(x["n"] >= 20 and ((x["consensus_truth_in_answer"] < x["anchor_truth_in_answer"]) or (x["consensus_harmful"] > x["anchor_harmful"])))
    return rep
out["priority"] = {str(W): priority(W) for W in WIN19}
TRIG = any(v["problem"] for kk, v in out["priority"][str(Wd)].items() if kk != "population")
out["guard_triggered"] = TRIG
if TRIG:
    G = run(Wd, guard=True); SG = summarize(G); SG.update(extra(G)); bg = boot(G, base)
    adopt_g = ((SG["bal"] > S_["bal"] + 1e-9) or (SG["harm"] < S_["harm"] - 1e-9)) and (SG["per_class"]["stained"] >= S_["per_class"]["stained"] - 0.01) and bars(SG)
    out["guard_G1"] = {"summary": SG, "vs_stage16": bg, "guarded_events": sum(1 for r in G if r["o"].get("guarded")), "adopted": adopt_g}
    if adopt_g: RES19[f"{Wd}+G1"] = G; S_ = SG; V = bg
# ---- S2C anchors (section 8)
s2 = {"anchors": 0, "with_prior_s2ab_10d": 0, "share_a_class": [], "contains": [], "signed_diff": []}
for e in EVENTS:
    if e["platform"] != "sentinel-2c": continue
    s2["anchors"] += 1; k = e["fold"]; key = (e["id"], "outer", k)
    if key not in PRED or PRED[key]["anchor"] is None or e["tier"] not in (1, 2): continue
    st_p, pc = prior_state(e, key, 10, k, {})
    if pc is None: continue
    s2["with_prior_s2ab_10d"] += 1; st_a = scene_state({"p": PRED[key]["anchor"], "tier": e["tier"]}, POST[k]); s2["signed_diff"].append(PRED[key]["anchor"] - pc)
    if st_a and st_p: s2["share_a_class"].append(bool(CONTAINS[st_a] & CONTAINS[st_p])); s2["contains"].append(bool(CONTAINS[st_a] >= CONTAINS[st_p]))
out["s2c_anchors"] = {"anchors": s2["anchors"], "with_prior_s2ab_10d": s2["with_prior_s2ab_10d"], "with_both_states": len(s2["share_a_class"]),
                      "share_a_class": float(np.mean(s2["share_a_class"])) if s2["share_a_class"] else None, "contains": float(np.mean(s2["contains"])) if s2["contains"] else None,
                      "signed_diff_log10_median": float(np.median(s2["signed_diff"])) if s2["signed_diff"] else None,
                      "signed_diff_log10_iqr": [float(np.percentile(s2["signed_diff"], 25)), float(np.percentile(s2["signed_diff"], 75))] if s2["signed_diff"] else None}
# ---- hydrology context (diagnostic only)
wn = tot = 0
for e in EVENTS:
    for n in NB.get(e["id"], []):
        if n["age"] <= Wd and n["platform"] != "sentinel-2c":
            R_ = (rain.get(e["id"]) or {}).get("rain") or {}
            if n["date"] in R_: tot += 1; wn += bool(wet(e["id"], n["date"]))
out["hydrology_context"] = {"prior_scenes_with_rain_record": tot, "would_be_excluded_by_stage17_rule": wn}
# ---- exact feet
Ckey = f"{Wd}+G1" if f"{Wd}+G1" in RES19 else Wd; Crows = RES19[Ckey]; mC = {r["id"]: r for r in Crows}
out["feet_same_rows"] = feet_same([(bmap, pA), (b18, pB), (mC, pB)])
out["exact_feet_capability"] = {"A": capscore(recs(base, pA))["EXACT_FEET_CAPABILITY"], "B": capscore(recs(B18, pB))["EXACT_FEET_CAPABILITY"], "C": capscore(recs(Crows, pB))["EXACT_FEET_CAPABILITY"]}
# ---- decisions (section 9)
useful = bool(SEL and bars(S_) and V["stained"] >= 0.05 and V["stained_ci"][0] > 0 and (S_["strong_acc"] or 0) >= 0.90)
g, ci = V["stained"], V["stained_ci"]
out["decisions"] = {"engine": str(Ckey), "CAUSAL_CONSENSUS_USEFUL": useful,
                    "STAGE18_GAIN_SURVIVES": "YES" if (g >= 0.05 and ci[0] > 0) else "PARTIAL" if (ci[0] > 0 or g >= 0.05) else "NO",
                    "stained_gain_retained": g / (Bs["per_class"]["stained"] - A["per_class"]["stained"]), "operational_gain_retained": (S_["bal"] - A["bal"]) / (Bs["bal"] - A["bal"]),
                    "STAGE16_BARS": bars(S_ if useful else Bs), "DEV9": dev9(S_ if useful else Bs), "SCORE": int(round(10 * (S_ if useful else Bs)["bal"] + 1e-9)),
                    "READY_S2C_STAGE": useful, "READY_FREEZE_AFTER_S2C": bool(useful and bars(S_) and (S_["strong_acc"] or 0) >= 0.90)}
json.dump(Crows, open(f"{S}/stage19/dev19_rows.json", "w"), default=str)
json.dump(out, open(f"{S}/stage19/dev19.json", "w"), indent=1, default=str)
fmt = lambda s: f"bal {s['bal']:.3f} clear {s['per_class']['clear']:.3f} normal {s['per_class']['normal']:.3f} stained {s['per_class']['stained']:.3f} limited {s['per_class']['limited']:.3f} harm {s['harm']:.3f} sev {s['sev']:.4f} unk {s['unknown_share']:.3f} strong {s['strong_share_usable']:.3f}/{(s['strong_acc'] or 0):.3f}"
print("A Stage 16 ", fmt(A)); print("B Stage 18 ", fmt(Bs))
for W in WIN19: print(f"C past {W:2d} d", fmt(SUM19[W]), "bars", bars(SUM19[W]), "| vs16 stained", round(out["vs_stage16"][str(W)]["stained"], 3), out["vs_stage16"][str(W)]["stained_ci"])
print("SELECTED", SEL, "guard triggered", TRIG, "decisions", out["decisions"])
