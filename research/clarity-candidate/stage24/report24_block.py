
# ======================= Stage 24 sections 7-16 (appended to the patched dev19 by dev24.py; same namespace)
import json as _json
from lib16 import posterior as _post
from lib14 import lake_boot_diff as _lbd
IQ24 = E14["interval_q"]; EV = {e["id"]: e for e in EVENTS}; WINS = [5, 10, 15]
pv = lambda r: r["o"].get("p") if r["o"].get("p") is not None else bmap[r["id"]].get("p")
def fl(rows):
    sh = [r for r in rows if shown(r["o"]) and pv(r) is not None]; e_ = [pv(r) - r["y"] for r in sh]
    return {"availability": len(sh) / len(rows), "mult_error": float(10 ** np.median(np.abs(e_))) if sh else None, "signed_bias": float(np.median(e_)) if sh else None,
            "coverage": float(np.mean([pv(r) + IQ24[0] <= r["y"] <= pv(r) + IQ24[1] for r in sh])) if sh else None}
def cov(rows):
    ans = [r for r in rows if r["o"]["state"] in CONTAINS]
    return {"answered": len(ans) / len(rows), "unknown": 1 - len(ans) / len(rows), "mean_passes": float(np.mean([r["o"].get("n_use", 1) if r["o"].get("consensus") else 1 for r in ans])) if ans else None}
def too_clear(r):
    C = CONTAINS.get(r["o"]["state"], set()); return bool(r["harmful"] and C and r["c"] > max(C))
def cls_block(rows, k):
    st = [r for r in rows if r["c"] == k]; sa = [r for r in st if r["o"]["state"] in CONTAINS]; sf = [r for r in sa if r["o"]["authority"] == "full"]
    sh = [r for r in st if shown(r["o"]) and pv(r) is not None]; u = [r for r in st if r["ev"] != "unavailable"]
    return {"n": len(st), "operational": float(np.mean([r["score"] for r in st])), "truth_in_answer": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in sf])) if sf else None,
            "harmful": float(np.mean([r["harmful"] for r in st])), "severe": float(np.mean([r["severe"] for r in st])), "unknown": 1 - len(sa) / len(st),
            "feet_bias": float(np.median([pv(r) - r["y"] for r in sh])) if sh else None, "feet_err": float(np.median([abs(pv(r) - r["y"]) for r in sh])) if sh else None,
            "posterior": float(np.mean([r["o"].get("conf") or 0 for r in sa])) if sa else None, "strong_share": sum(1 for r in u if r["ev"] == "strong") / len(u) if u else None}
def murky(rows):
    M = [r for r in rows if r["c"] in (2, 3)]; M3 = [r for r in rows if r["secchi"] <= 3.0]; sh = [r for r in M if shown(r["o"]) and pv(r) is not None]
    con = [r for r in M if r["o"].get("consensus")]; pri = [x for r in con for x in (r["o"].get("prov") or []) if not x["anchor"]]
    return {"n": len(M), "n_secchi_le3": len(M3), "operational": float(np.mean([r["score"] for r in M])), "harmful": float(np.mean([r["harmful"] for r in M])), "severe": float(np.mean([r["severe"] for r in M])),
            "too_clear_rate": sum(too_clear(r) for r in M) / len(M), "too_clear_rate_secchi_le3": sum(too_clear(r) for r in M3) / len(M3) if M3 else None,
            "feet_bias": float(np.median([pv(r) - r["y"] for r in sh])) if sh else None, "feet_err": float(np.median([abs(pv(r) - r["y"]) for r in sh])) if sh else None,
            "unknown": float(np.mean([r["o"]["state"] not in CONTAINS for r in M])), "posterior": float(np.mean([r["o"].get("conf") or 0 for r in M if r["o"]["state"] in CONTAINS])),
            "mean_passes": float(np.mean([r["o"].get("n_use", 1) if r["o"].get("consensus") else 1 for r in M])), "conflicted_share_of_used_priors": float(np.mean([x["conflicted"] for x in pri])) if pri else None}
def strong_geo(rows):
    st = [r for r in rows if r["ev"] == "strong"]; c = sum(1 for r in st if r["o"].get("n_conflicted", 0) > 0)
    return {"n": len(st), "with_conflicted_pass": c, "compatible_only": len(st) - c,
            "acc_compatible_only": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in st if not r["o"].get("n_conflicted")])) if len(st) - c else None,
            "acc_with_conflicted": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in st if r["o"].get("n_conflicted")])) if c else None,
            "by_class": {n: {"usable": sum(1 for r in rows if r["c"] == k and r["ev"] != "unavailable"), "share": (sum(1 for r in st if r["c"] == k) / max(1, sum(1 for r in rows if r["c"] == k and r["ev"] != "unavailable"))),
                             "acc": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in st if r["c"] == k])) if any(r["c"] == k for r in st) else None} for k, n in enumerate(CLASSES)}}
def full_summary(rows):
    s = summarize(rows); s.update(extra(rows)); s.update({"coverage": cov(rows), "feet": fl(rows), "murky": murky(rows), "classes": {n: cls_block(rows, k) for k, n in enumerate(CLASSES)}, "strong_geo": strong_geo(rows)}); return s
def boot24(rc, rr):
    mc = {r["id"]: r for r in rc}; mr = {r["id"]: r for r in rr}; pr = [{"id": r["id"], "lake": bmap[r["id"]]["lake"], "c": r["c"]} for r in rc]
    def d(x, c=None, f="score"):
        ids = [r["id"] for r in x if c is None or r["c"] == c]; return float(np.mean([float(mc[i][f]) for i in ids]) - np.mean([float(mr[i][f]) for i in ids]))
    def dbal(x):
        cs = [c for c in range(4) if any(r["c"] == c for r in x)]
        return float(np.mean([np.mean([mc[r["id"]]["score"] for r in x if r["c"] == c]) - np.mean([mr[r["id"]]["score"] for r in x if r["c"] == c]) for c in cs]))
    out = {"op": dbal(pr), "op_ci": _lbd(pr, dbal, B=2000, seed=24)}
    for nm, fn in (("harm", lambda x: d(x, None, "harmful")), ("sev", lambda x: d(x, None, "severe")), ("stained", lambda x: d(x, 2)), ("limited", lambda x: d(x, 3))):
        out[nm] = fn(pr); out[nm + "_ci"] = _lbd(pr, fn, B=2000, seed=24)
    return out
# ---------------- run every candidate at every window
RES24, SUMS = {}, {}
RES24[("G0", 5)] = RES19[5]; RES24[("G0", 10)] = RES19[10]; RES24[("G0", 15)] = RES19[15]
for m in ("G1", "G2", "G3"):
    METHOD24 = m
    for W in WINS: RES24[(m, W)] = run(W)
METHOD24 = "G0"
for k, rows in RES24.items(): SUMS[k] = full_summary(rows)
R0rows = RES24[("G0", 5)]; R0s = SUMS[("G0", 5)]
sel = {}
for m in ("G0", "G1", "G2", "G3"):
    cands = [W for W in WINS if bars(SUMS[(m, W)])]
    if not cands: sel[m] = None; continue
    best = max(cands, key=lambda W: SUMS[(m, W)]["bal"]); eq = {}
    for W in cands:
        if W == best: eq[W] = True; continue
        b = boot(RES24[(m, W)], RES24[(m, best)]); eq[W] = (b["bal_ci"][0] <= 0 <= b["bal_ci"][1]) and (b["stained_ci"][0] <= 0 <= b["stained_ci"][1])
    sel[m] = min(W for W in cands if eq[W])
covok = lambda s: s["coverage"]["unknown"] <= R0s["coverage"]["unknown"] + 0.05 and s["feet"]["availability"] >= R0s["feet"]["availability"] - 0.05
pool = [(m, sel[m]) for m in ("G1", "G2", "G3") if sel[m] and covok(SUMS[(m, sel[m])])]
BEST = max(pool, key=lambda k: SUMS[k]["bal"]) if pool else None
VS = {f"{m}@{W}": boot24(RES24[(m, W)], R0rows) for m in ("G1", "G2", "G3") for W in WINS}
A16 = []
for e in EVENTS:
    key = (e["id"], "outer", e["fold"]); o = base23(e, key); sc_, oc, h, sv = op_score(o, e["c"], e["secchi"])
    ev_ = "unavailable" if o["state"] not in CONTAINS else "weak" if o["authority"] == "lower" else ("strong" if (o.get("conf") or 0) >= 0.90 and e["tier"] == 1 and not o.get("s2c") and not o.get("algal") else "moderate")
    A16.append({"id": e["id"], "lake": e["lake"], "c": e["c"], "y": e["y"], "secchi": e["secchi"], "tier": e["tier"], "platform": e["platform"], "fold": e["fold"], "o": o, "score": sc_, "outcome": oc, "harmful": h, "severe": sv, "ev": ev_,
                "insitu_type": e["insitu_type"], "turb": e["turb"]})
S16 = full_summary(A16)
adopt = None
if BEST:
    b = VS[f"{BEST[0]}@{BEST[1]}"]; s = SUMS[BEST]; capB = capscore(recs(RES24[BEST], pB))["EXACT_FEET_CAPABILITY"]
    crit = {"stage16_bars": bars(s), "op_material": b["op"] >= 0.02 and b["op_ci"][0] > 0, "harm": b["harm"] <= 0 or b["harm_ci"][1] <= 0.01, "severe": b["sev"] <= 0 or b["sev_ci"][1] <= 0.003,
            "stained": b["stained"] >= -0.01, "limited": b["limited"] >= -0.02, "strong_acc": (s["strong_acc"] or 0) >= 0.90, "exact_feet": capB["score_of_10"] >= 8, "coverage": covok(s), "no_future": True}
    adopt = {"candidate": f"{BEST[0]}@{BEST[1]}", "criteria": crit, "adopted": all(crit.values()), "vs_R0": b, "exact_feet": capB}
FINAL = BEST if (adopt and adopt["adopted"]) else ("G0", 5); FR = RES24[FINAL]; FS = SUMS[FINAL]
capF = capscore(recs(FR, pB))["EXACT_FEET_CAPABILITY"]
# ---------------- SG (reported): Strong also needs >= 2 agreeing compatible passes, on the best (or R0)
SGk = BEST or ("G0", 5); sgr = [dict(r, ev=("moderate" if (r["ev"] == "strong" and r["o"].get("agree_c", 0) < 2) else r["ev"])) for r in RES24[SGk]]; SG = summarize(sgr)
# ---------------- boundary states, confident-but-wrong, single-scene counterfactual (on FINAL and R0)
def bnd(rows):
    A = [r for r in rows if r["o"]["state"] in CONTAINS and r["o"]["authority"] == "full"]
    isb = lambda r: len(CONTAINS[r["o"]["state"]]) == 2; one = lambda r: not (r["o"].get("consensus") and r["o"].get("n_use", 1) >= 2); cf_ = lambda r: r["o"].get("n_conflicted", 0) > 0
    rate = lambda R: (float(np.mean([r["harmful"] for r in R])), len(R)) if R else (None, 0)
    out = {"boundary": rate([r for r in A if isb(r)]), "plain": rate([r for r in A if not isb(r)])}
    for k, n in enumerate(CLASSES): out[f"{n}_boundary"] = rate([r for r in A if isb(r) and r["c"] == k]); out[f"{n}_plain"] = rate([r for r in A if not isb(r) and r["c"] == k])
    for nm, f in (("one_scene", one), ("multi_scene", lambda r: not one(r)), ("compatible", lambda r: not one(r) and not cf_(r)), ("conflicted", lambda r: not one(r) and cf_(r))):
        out[f"boundary_{nm}"] = rate([r for r in A if isb(r) and f(r)]); out[f"plain_{nm}"] = rate([r for r in A if not isb(r) and f(r)])
    return out
def psi24(g):
    import math as _m
    ts, tv, d = _m.radians(90 - g["sun_elev"]), _m.radians(g["view_inc"]), _m.radians(g["sun_az"] - g["view_az"])
    return _m.degrees(_m.acos(max(-1, min(1, _m.cos(ts) * _m.cos(tv) - _m.sin(ts) * _m.sin(tv) * _m.cos(d)))))
def confwrong(rows):
    A = [r for r in rows if r["o"]["state"] in CONTAINS and r["o"]["authority"] == "full" and (r["o"].get("conf") or 0) >= 0.90]; H = [r for r in A if r["harmful"]]
    def comp(R):
        if not R: return {"n": 0}
        g = [G24.get(corp[r["id"]]["item"]) for r in R]; ps = [psi24(x) for x in g if x]
        return {"n": len(R), "one_scene": float(np.mean([not (r["o"].get("consensus") and r["o"].get("n_use", 1) >= 2) for r in R])), "with_conflicted": float(np.mean([r["o"].get("n_conflicted", 0) > 0 for r in R])),
                "anchor_glint_psi_median": float(np.median(ps)) if ps else None, "s2b_share": float(np.mean([r["platform"] == "sentinel-2b" for r in R])),
                "truth": dict(collections.Counter(CLASSES[r["c"]] for r in R)), "too_clear": float(np.mean([too_clear(r) for r in R]))}
    return {"all_high_posterior": comp(A), "harmful_high_posterior": comp(H), "harmful_rate": len(H) / len(A) if A else None}
def counterfactual(rows):
    n = hh = ss = fixed_h = fixed_s = 0
    for r in rows:
        o = r["o"]
        if o["state"] not in SINGLE or o["authority"] != "full" or (o.get("consensus") and o.get("n_use", 1) >= 2) or r["ev"] == "strong" or (o.get("conf") or 1) >= 0.90 or pv(r) is None: continue
        e = EV[r["id"]]; P = POST[e["fold"]]["post2" if r["tier"] == 2 else "post1"]; pi = _post(pv(r), P); k = SINGLE.index(o["state"])
        adj = [j for j in (k - 1, k + 1) if 0 <= j < 4]; j = max(adj, key=lambda j: pi[j]); n += 1; hh += r["harmful"]; ss += r["severe"]
        if r["harmful"] and r["c"] in (k, j): fixed_h += 1
        if r["severe"] and r["c"] in (k, j): fixed_s += 1
    return {"lone_moderate_plain_below_0.90": n, "of_which_harmful": hh, "severe": ss, "harmful_converted_to_boundary_hits": fixed_h, "severe_converted": fixed_s}
# ---------------- truth-free check: anchor-prior disagreement by side and age (outer predictions)
tf = collections.defaultdict(list)
for e in EVENTS:
    key = (e["id"], "outer", e["fold"]); pr = PRED.get(key)
    if not pr or pr["anchor"] is None or e["tier"] not in (1, 2): continue
    ga = G24.get(corp[e["id"]]["item"])
    for n_, p in zip(NB.get(e["id"], []), pr["nb"]):
        gb = n_.get("geo")
        if not (ga and gb): continue
        side = "opposite" if DAZ(ga["view_az"], gb["view_az"]) > 90 else "same"; ab = "le5" if n_["age"] <= 5 else "6-10" if n_["age"] <= 10 else "11-15"
        tf[f"{side}|{ab}"].append(abs(p - pr["anchor"]))
truthfree = {k: {"n": len(v), "median_abs_dp": float(np.median(v))} for k, v in sorted(tf.items())}
# ---------------- provenance (FINAL and R0) and output
def prov(rows): return [{"id": r["id"], "state": r["o"]["state"], "evidence": r["ev"], "consensus": bool(r["o"].get("consensus")), "passes": r["o"].get("prov")} for r in rows]
_json.dump(prov(FR), open(f"{S}/stage24/dev24_final_provenance.json", "w"), default=str)
_json.dump(FR, open(f"{S}/stage24/dev24_final_rows.json", "w"), default=str)
rep = {"selected_windows": sel, "best_candidate": f"{BEST[0]}@{BEST[1]}" if BEST else None, "adoption": adopt, "final": f"{FINAL[0]}@{FINAL[1]}",
       "summaries": {f"{m}@{W}": SUMS[(m, W)] for (m, W) in SUMS}, "stage16_c3": S16, "vs_R0": VS, "SG_strong_alt": {"on": f"{SGk[0]}@{SGk[1]}", "summary": SG},
       "boundary": {"final": bnd(FR), "R0": bnd(R0rows)}, "confident_wrong": {"final": confwrong(FR), "R0": confwrong(R0rows)},
       "single_scene_counterfactual": {"final": counterfactual(FR), "R0": counterfactual(R0rows)}, "truth_free_anchor_prior": truthfree,
       "final_vs_stage16": boot24(FR, A16), "exact_feet_final": capF, "gamma": GAMMA24,
       "checks_final": {"stage16_bars": bars(FS), "dev8": FS["bal"] >= 0.75 and min(FS["per_class"].values()) >= 0.65 and FS["harm"] <= 0.10 and FS["sev"] <= 0.010 and FS["strong_share_usable"] >= 0.25 and (FS["strong_acc"] or 0) >= 0.90 and capF["score_of_10"] >= 8, "dev9": dev9(FS)}}
_json.dump(rep, open(f"{S}/stage24/dev24_report.json", "w"), indent=1, default=str)
for (m, W), s in sorted(SUMS.items()): print(f"{m}@{W:2d}", fmt(s), "| unk", round(s["coverage"]["unknown"], 3), "feet avail", round(s["feet"]["availability"], 3), "| murky too-clear", round(s["murky"]["too_clear_rate"], 4), "| bars", bars(s), "| vs R0", {k: round(v, 4) for k, v in VS.get(f"{m}@{W}", {}).items() if not k.endswith("_ci")} if m != "G0" else "")
print("SELECTED", sel, "BEST", BEST, "ADOPT", adopt and adopt["adopted"], adopt and adopt["criteria"], "FINAL", FINAL, "feet", capF)
