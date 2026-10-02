"""Stage 12 Part 4 (section 4). Refuses to run before reflectance.json exists. Every fitted model is fitted on training
lake-folds only (Stage 11 folds). Selection on non-Guntersville rows with a valid ACOLITE disk. Writes models12.json
and preds12.json (held-out predictions + the Part 5 exact-feet authorisation from inner folds)."""
import json, math, os, sys, collections, random
from common12 import *
if not os.path.exists(f"{D12}/analysis/reflectance.json"): sys.exit("reflectance.json missing: section 3 requires the reflectance evaluation first")
R = load12()
E = [x for x in R if x["aco_valid"] and x["secchi"] and x["secchi"] > 0]
for x in E:
    a = x["aco"]; x["rho"] = {"blue": a["B02"], "green": a["B03"], "red": a["B04"], "re1": a["B05"]}
    x["swir"] = a.get("B11") if isinstance(a.get("B11"), (int, float)) and math.isfinite(a["B11"]) else 0.0
    x["fnu_aco"] = dog(a["B04"]); x["owt"] = owt_from(x["rho"], x["fnu_aco"], x["sun_elev"], x["swir"])
SEL = [x for x in E if not x["gunt"]]
ORDER = ["champion", "P1", "champion_refit", "N1", "N2", "C3", "C6", "P2"]
def feats(m, x):
    r = x["rho"]; lr = math.log10(max(r["red"], 0.001)); nd = ndci(r)
    if m == "champion_refit": return [1.0, math.log10(max(x["fnu_aco"], 0.1))]
    if m == "N1": return [1.0, lr]
    if m == "N2": return [1.0, lr, math.log10(max(r["green"], 0.001) / max(r["red"], 0.001))]
    if m == "C3": a = 1.0 if nd > 0 else 0.0; return [1 - a, (1 - a) * lr, a, a * lr]
    if m == "C6": return [1.0, lr, nd, nd * lr]
FIT = ["champion_refit", "N1", "N2", "C3", "C6"]
def fitm(tr, m):
    X = np.array([feats(m, x) for x in tr]); y = np.array([math.log10(x["secchi"]) for x in tr])
    return np.linalg.lstsq(X, y, rcond=None)[0]
def predict_all(tr, te):
    B = {m: fitm(tr, m) for m in FIT}; out = collections.defaultdict(list)
    for x in te:
        out["champion"].append(champ(x["fnu_aco"]))
        z, _, _ = P1(x["rho"], x["sun_elev"]); out["P1"].append(z)
        for m in FIT: out[m].append(10 ** float(np.dot(B[m], feats(m, x))))
        out["P2"].append(P2.route(x["rho"], x["sun_elev"], x["swir"])["ft"])
    return out, B
for k in range(5):
    tr = [x for x in SEL if fold(x["lake"]) != k]; te = [x for x in E if fold(x["lake"]) == k and not x["gunt"]]
    P, _ = predict_all(tr, te)
    for i, x in enumerate(te): x["pred"] = {m: P[m][i] for m in ORDER}
Gr = [x for x in E if x["gunt"]]
if Gr:
    P, _ = predict_all(SEL, Gr)
    for i, x in enumerate(Gr): x["pred"] = {m: P[m][i] for m in ORDER}
def le(x, m):
    v = x["pred"].get(m); return None if v is None or v <= 0 else math.log10(v / x["secchi"])
def st(rows, m):
    ok = [x for x in rows if le(x, m) is not None]
    if len(ok) < 10: return {"n": len(ok), "note": "INSUFFICIENT"}
    ft = [x["pred"][m] - x["secchi"] for x in ok]
    return {"n": len(ok), "lakes": len({x["lake"] for x in ok}), "coverage": round(len(ok) / len(rows), 3),
            "median_abs_log": round(float(np.median([abs(le(x, m)) for x in ok])), 4), "median_signed_ft": round(float(np.median(ft)), 2),
            "class_acc": round(float(np.mean([cls(x["pred"][m]) == cls(x["secchi"]) for x in ok])), 3)}
res = {"rows_selection": len(SEL), "lakes_selection": len({x["lake"] for x in SEL}), "all": {m: st(SEL, m) for m in ORDER}}
# production baseline on the same rows: the frozen champion on Sen2Cor FNU
for x in E: x["pred"]["production"] = champ(x["fnu"])
res["production_sen2cor_champion_same_rows"] = st(SEL, "production")
elig = [m for m in ORDER if res["all"][m].get("coverage", 0) >= 0.90]
def mdiff(rows, a, b):
    c = [x for x in rows if le(x, a) is not None and le(x, b) is not None]
    return float(np.median([abs(le(x, a)) for x in c]) - np.median([abs(le(x, b)) for x in c])) if c else None
def boot(rows, a, b):
    c = [x for x in rows if le(x, a) is not None and le(x, b) is not None]
    by = collections.defaultdict(list)
    for x in c: by[x["lake"]].append(x)
    L = sorted(by); g = random.Random(12); v = []
    for _ in range(2000):
        smp = [x for _ in L for x in by[L[g.randrange(len(L))]]]
        v.append(float(np.median([abs(le(x, a)) for x in smp]) - np.median([abs(le(x, b)) for x in smp])))
    v.sort(); return [round(v[50], 4), round(v[1949], 4)]
def choose(cands):
    best = min(cands, key=lambda m: res["all"][m]["median_abs_log"])
    eq = {}
    for m in cands:
        if ORDER.index(m) < ORDER.index(best):
            ci = boot(SEL, m, best); eq[m] = {"diff": round(mdiff(SEL, m, best), 4), "ci95": ci, "equivalent": ci[1] <= 0.010}
    simplest = next((m for m in ORDER if m in cands and (m == best or eq.get(m, {}).get("equivalent"))), best)
    return best, simplest, eq
best, engine, eq = choose(elig)
res["eligible"] = elig; res["best"] = best; res["equivalence_vs_best"] = eq; res["engine_before_guard"] = engine
# the C3 guard
alg = [x for x in SEL if x["owt"] == "algal"]
res["by_owt"] = {s: {m: st([x for x in SEL if x["owt"] == s], m) for m in ORDER} for s in ("clear", "algal", "sediment", "mixed", "unsupported")}
if engine == "C3":
    others = [m for m in elig if m != "C3" and res["by_owt"]["algal"][m].get("median_abs_log") is not None]
    bo = min(others, key=lambda m: res["by_owt"]["algal"][m]["median_abs_log"]) if others else None
    ok = bo is None or res["by_owt"]["algal"]["C3"]["median_abs_log"] <= res["by_owt"]["algal"][bo]["median_abs_log"] + 0.01
    res["c3_guard"] = {"best_other_in_algal": bo, "passes": bool(ok)}
    if not ok:
        best, engine, eq = choose([m for m in elig if m != "C3"]); res["engine_after_guard"] = engine
res["engine"] = engine
# nested routing (Stage 11 machinery on ACOLITE water types; models 1-7)
RM = ["champion", "P1", "champion_refit", "N1", "N2", "C3", "C6"]
STATES = ["clear", "algal", "sediment", "mixed", "unsupported"]
def inner_choice(tr):
    for x in tr: x["ipred"] = {}
    for j in range(4):
        itr = [x for x in tr if (fold(x["lake"], 20) % 4) != j]; ite = [x for x in tr if (fold(x["lake"], 20) % 4) == j]
        if len(itr) < 30 or not ite: continue
        P, _ = predict_all(itr, ite)
        for i, x in enumerate(ite): x["ipred"] = {m: P[m][i] for m in RM}
    ch = {}
    for s in STATES:
        rows = [x for x in tr if x["owt"] == s and x["ipred"]]; bm, bv = None, None
        for m in RM:
            e = [math.log10(x["ipred"][m] / x["secchi"]) for x in rows if x["ipred"].get(m) and x["ipred"][m] > 0]
            if len(e) < 10 or len(e) < 0.5 * len(rows): continue
            v = float(np.median(np.abs(e)))
            if bv is None or v < bv: bm, bv = m, v
        ch[s] = bm if (bm is not None and bv <= 0.25) else None
    return ch
choices = {}
for k in range(5):
    tr = [x for x in SEL if fold(x["lake"]) != k]; ch = inner_choice(tr); choices[k] = ch
    for x in SEL:
        if fold(x["lake"]) == k:
            m = ch.get(x["owt"]); x["pred"]["routed"] = x["pred"].get(m) if m else None
res["routing_choices"] = choices; res["routed"] = st(SEL, "routed")
rr = [x for x in SEL if le(x, "routed") is not None and le(x, engine) is not None]
rv = float(np.median([abs(le(x, "routed")) for x in rr])); ev = float(np.median([abs(le(x, engine)) for x in rr]))
ci = boot(SEL, "routed", engine)
stable = {s: collections.Counter(c.get(s) for c in choices.values() if c.get(s)).most_common(1) for s in STATES}
res["routing_test"] = {"routed_same_rows": round(rv, 4), "engine_same_rows": round(ev, 4), "relative_gain": round((ev - rv) / ev, 3), "diff_ci95": ci,
                       "coverage": res["routed"].get("coverage"), "stable": {s: (v[0][1] >= 4 if v else None) for s, v in stable.items()}}
res["routing_adopted"] = bool((ev - rv) / ev >= 0.10 and ci[1] < 0 and (res["routed"].get("coverage") or 0) >= 0.70 and all(v for v in res["routing_test"]["stable"].values() if v is not None))
FINAL = "routed" if res["routing_adopted"] else engine
res["final_engine"] = FINAL
# section 5: exact-feet authorisation per predicted class, from the inner folds of each outer training set
BAR = {"clear": 1.5, "normal": 1.0, "stained": 0.75, "limited": 0.75}
auth = {}
for k in range(5):
    tr = [x for x in SEL if fold(x["lake"]) != k]; inner = []
    for j in range(4):
        itr = [x for x in tr if (fold(x["lake"], 20) % 4) != j]; ite = [x for x in tr if (fold(x["lake"], 20) % 4) == j]
        if len(itr) < 30 or not ite: continue
        P, _ = predict_all(itr, ite)
        for i, x in enumerate(ite):
            if FINAL == "routed":
                m = choices[k].get(x["owt"]); v = P[m][i] if m else None
            else:
                v = P[FINAL][i]
            inner.append((x, v))
    ok = []
    for c in CLASSES:
        sub = [(x, v) for x, v in inner if v and v > 0 and cname(v) == c]
        if len(sub) < 10: continue
        lg = float(np.median([abs(math.log10(v / x["secchi"])) for x, v in sub])); sg = float(np.median([v - x["secchi"] for x, v in sub]))
        if lg <= 0.15 and abs(sg) <= BAR[c]: ok.append(c)
    auth[k] = ok
res["feet_authorisation"] = auth
# per-class errors of the final engine (and production on the same rows)
groups = {**{c: [x for x in SEL if cname(x["secchi"]) == c] for c in CLASSES}, **{t: [x for x in SEL if x["insitu_type"] == t] for t in ("algal", "sediment", "mixed")}}   # erratum 2026-09-30: an in-situ "clear" key used to overwrite the Secchi class "clear"
res["per_class"] = {g: {"engine": st(rows, FINAL), "production": st(rows, "production")} for g, rows in groups.items()}
res["guntersville"] = {"engine": st(Gr, FINAL if FINAL != "routed" else engine), "production": st(Gr, "production")}
# platform (section 2 condition b): held-out median signed log error by platform vs the others
plat = {}
for p in ("sentinel-2a", "sentinel-2b", "sentinel-2c"):
    a = [x for x in SEL if x["platform"] == p and le(x, FINAL) is not None]; b = [x for x in SEL if x["platform"] != p and le(x, FINAL) is not None]
    if len(a) < 30: plat[p] = {"n": len(a), "note": "fewer than 30 rows"}; continue
    fn = lambda rows: float(np.median([le(x, FINAL) for x in rows if x["platform"] == p]) - np.median([le(x, FINAL) for x in rows if x["platform"] != p]))
    plat[p] = {"n": len(a), "diff": round(fn(a + b), 4), "ci95": lake_boot(a + b, fn)}
res["platform"] = plat
# engine production fit (all selection rows) for the tandem class test
if FINAL in FIT: res["engine_production_coef"] = [float(v) for v in fitm(SEL, FINAL)]
json.dump(res, open(f"{D12}/analysis/models12.json", "w"), indent=1, default=str)
json.dump([{k: x[k] for k in ("id", "lake", "set", "secchi", "insitu_type", "owt", "gunt", "platform", "sun_elev", "turb", "chl")} | {"pred": x["pred"], "fnu_aco": x["fnu_aco"], "rho": x["rho"], "swir": x["swir"]} for x in E],
          open(f"{D12}/analysis/preds12.json", "w"))
print(json.dumps({k: res[k] for k in ("rows_selection", "eligible", "best", "equivalence_vs_best", "engine", "routing_test", "routing_adopted", "final_engine")}, indent=1, default=str))
for m in ORDER + ["production"]: print(m, res["all"].get(m) or res["production_sen2cor_champion_same_rows"])
