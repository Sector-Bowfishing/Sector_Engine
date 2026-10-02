"""Stage 10 DEVELOPMENT-ONLY historical check of the frozen P2 and P1S (PREREGISTRATION_P2.md section 6).
Not certification; nothing here may change a frozen file. Uses the frozen modules unchanged, with the
comparators' held-out predictions (Stage 8 c6_research.py, re-run and verified byte-identical)."""
import io, contextlib, runpy, json, math, csv, collections, shutil, filecmp, os, sys, hashlib
import numpy as np

S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D6, D7, D8, D10 = (f"{S}/stage{i}" for i in (6, 7, 8, 10))
sys.path.insert(0, f"{D10}/frozen")
man = json.load(open(f"{D10}/frozen_manifest.json"))
for k, p in (("stage10/frozen/p2.py", "p2.py"), ("stage10/frozen/p1.py", "p1.py"), ("stage10/frozen/models.py", "models.py"),
             ("stage10/frozen/metrics.py", "metrics.py"), ("stage10/frozen/c3_frozen.json", "c3_frozen.json")):
    assert hashlib.sha256(open(f"{D10}/frozen/{p}", "rb").read()).hexdigest() == man["files"][k], f"{p} changed since the freeze"
import p2 as P2, models, metrics
from p1 import p1 as P1

os.makedirs(f"{D10}/_s8_check", exist_ok=True)
for f in ("c6_results.json", "c6_model.json"):
    shutil.copy(f"{D8}/{f}", f"{D10}/_s8_check/{f}")
cwd = os.getcwd()
with contextlib.redirect_stdout(io.StringIO()):
    g8 = runpy.run_path(f"{D8}/c6_research.py")
os.chdir(cwd)
repro = {f: filecmp.cmp(f"{D8}/{f}", f"{D10}/_s8_check/{f}", shallow=False) for f in ("c6_results.json", "c6_model.json")}
g7 = g8["g"]
G, N, Gc, Nc, evaluate, cls = g7["G"], g7["N"], g7["Gc"], g7["Nc"], g7["evaluate"], g7["cls"]
Gall, fit, pred, predict, num = g8["Gall"], g7["fit"], g7["pred"], g8["predict"], g7["num"]

# raw bands, sun and B11 per row (same loops as stage9/p1_research.py)
rd = {}
for f in ("readouts.csv", "readouts_old.csv"):
    for r in csv.DictReader(open(f"{D6}/{f}")):
        if not r["error"]:
            rd[(r["id"], r["item"])] = r
i = 0
for m in json.load(open(f"{D6}/matchups.json")):
    r = rd[(m["id"], m["item"])]
    b = {k: num(r[f"rho_{k}_v"]) for k in ("blue", "green", "red", "rededge1")}
    if any(v is None for v in b.values()):
        continue
    gr = G[i]; i += 1
    assert gr["id"] == m["id"]
    gr["raw"] = {"blue": b["blue"], "green": b["green"], "red": b["red"], "re1": b["rededge1"]}
    gr["sun"] = num(r["sun_elev"]) if r.get("sun_elev") else m.get("sunElev")
    gr["swir"] = num(r.get("rho_swir16_v"))
i = 0
for m in json.load(open(f"{D7}/national_rows.json")):
    b = {k: num(m[f"rho_{k}"]) for k in ("blue", "green", "red", "rededge1")}
    if any(v is None for v in b.values()):
        continue
    nr = N[i]; i += 1
    nr["raw"] = {"blue": b["blue"], "green": b["green"], "red": b["red"], "re1": b["rededge1"]}
    nr["sun"] = num(m["sun_elev"]); nr["swir"] = num(m.get("rho_swir16"))
F = json.load(open(f"{D8}/fresh_rows.json"))
fr = {(r["id"], r["item"]): r for r in csv.DictReader(open(f"{D8}/fresh_readouts.csv"))}
bC3 = fit(Nc, "C3")
for r in F:
    x = fr[(r["id"], r["item"])]
    r["raw"] = {"blue": num(x["rho_blue_v"]), "green": num(x["rho_green_v"]), "red": num(x["rho_red_v"]), "re1": num(x["rho_rededge1_v"])}
    r["sun"] = num(x["sun_elev"]); r["swir"] = num(x.get("rho_swir16_v")); r["kind"] = None; r["turb"] = None
    r["C0"] = r["champ"]; r["C3n"] = pred(bC3, r, "C3"); r["C6n"] = predict(g8["mall"], r, local=False)
for r in Nc:
    r["C0"] = r["champ"]
for r in Gall:
    r.setdefault("C0", r["champ"])


def run(rows, c3key, tag):
    for r in rows:
        z, why, _ = P1(r["raw"], r["sun"]); r["P1"], r["P1_why"] = z, why
        rt = P2.route(r["raw"], r["sun"], r["swir"], c3_value=r.get(c3key))
        r[tag], r[tag + "_path"], r[tag + "_reason"], r[tag + "_S"], r["srr"] = rt["ft"], rt["path"], rt["reason"], rt["S"], rt["srr"]
        zs, _, _ = models.p1s(r["raw"], r["sun"], r["swir"]); r["P1S"] = zs


run(Gall, "C3_year_NG", "P2y"); run(Gall, "C3_site_NG", "P2s")
# contaminated rows carry no held-out C3 (Stage 7 fitted C3 on clean rows only): route with the frozen C3 value
for r in Gall:
    if r.get("C3_year_NG") is None:
        rt = P2.route(r["raw"], r["sun"], r["swir"]); r["P2y"], r["P2y_path"], r["P2y_reason"] = rt["ft"], rt["path"], rt["reason"]
run(Nc, "C3_CV", "P2n"); run(F, "C3n", "P2f")

med = lambda rows, k: round(float(np.median([r[k] - r["secchi"] for r in rows if r.get(k) is not None])), 2) if any(r.get(k) is not None for r in rows) else None
res = {"freeze": json.load(open(f"{D10}/FREEZE.json")), "stage8Reproduced": repro}

# routing breakdown (clean G)
def cl_name(ft): return ("clear >=6", "normal 3-6", "stained 2-3", "limited <2")[cls(ft)]
res["routes"] = {"G clean": dict(collections.Counter(r["P2y_path"] for r in Gc)),
                 "G clean by class": {c: dict(collections.Counter(r["P2y_path"] for r in Gc if cl_name(r["secchi"]) == c)) for c in ("clear >=6", "normal 3-6", "stained 2-3", "limited <2")},
                 "G clean by kind": {k: dict(collections.Counter(r["P2y_path"] for r in Gc if r["kind"] == k)) for k in ("arm", "mainStem")},
                 "G reasons": dict(collections.Counter(r["P2y_reason"].split(" (")[0] for r in Gc)),
                 "N clean": dict(collections.Counter(r["P2n_path"] for r in Nc)), "F": dict(collections.Counter(r["P2f_path"] for r in F))}
def q(v): v = [x for x in v if x is not None and math.isfinite(x)]; return [round(float(np.percentile(v, p)), 2) for p in (10, 50, 90)] if v else None
res["S_by_class"] = {c: {"S p10/50/90": q([r["P2y_S"] for r in Gc if cl_name(r["secchi"]) == c]),
                         "B05/B11 p10/50/90": q([r["srr"] for r in Gc if cl_name(r["secchi"]) == c]),
                         "S infinite": sum(1 for r in Gc if cl_name(r["secchi"]) == c and r["P2y_S"] is not None and not math.isfinite(r["P2y_S"]))}
                     for c in ("clear >=6", "normal 3-6", "stained 2-3", "limited <2")}
res["S_by_kind"] = {k: {"S p10/50/90": q([r["P2y_S"] for r in Gc if r["kind"] == k]), "B05/B11 p10/50/90": q([r["srr"] for r in Gc if r["kind"] == k])} for k in ("arm", "mainStem")}

# paired comparison on the rows P2 answers
res["paired"] = {}
for sch, tag, c3k, c6k in (("LOYO", "P2y", "C3_year_NG", "C6_year"), ("LOSO", "P2s", "C3_site_NG", "C6_site")):
    A = [r for r in Gc if r[tag] is not None]
    e = {"P2": evaluate(A, tag), "C0": evaluate(A, "C0"), "C3": evaluate(A, c3k), "C6": evaluate(A, c6k)}
    A1 = [r for r in A if r["P1"] is not None]
    e["P1 (rows P1 also answers)"] = evaluate(A1, "P1")
    e["P2 (same rows as P1)"] = evaluate(A1, tag)
    res["paired"][sch] = e
    res.setdefault("gates", {})[sch] = metrics.gates(e["P2"], e["C0"])
NA = [r for r in Nc if r["P2n"] is not None]
def ev_n(rows, key):
    return {"n": len(rows), "spearman": metrics.sp([r[key] for r in rows], [r["secchi"] for r in rows]),
            "medianSigned": round(float(np.median([r[key] - r["secchi"] for r in rows])), 2),
            "MAE": round(float(np.mean([abs(r[key] - r["secchi"]) for r in rows])), 2),
            "medAE": round(float(np.median([abs(r[key] - r["secchi"]) for r in rows])), 2)}
res["N_paired"] = {m: {"all": ev_n(NA, k), "AL": ev_n([r for r in NA if r["state"] == "AL"], k)} for m, k in (("P2", "P2n"), ("C0", "C0"), ("C3", "C3_CV"), ("C6", "C6_CV"))}
n2, n0 = res["N_paired"]["P2"], res["N_paired"]["C0"]
res["gates"]["9 N medAE<=1.1x and AL MAE<=1.2x"] = bool(n2["all"]["medAE"] <= 1.1 * n0["all"]["medAE"] and n2["AL"]["MAE"] <= 1.2 * n0["AL"]["MAE"])
FA = [r for r in F if r["P2f"] is not None]
def ev_f(rows, key):
    st_ = [r for r in rows if 2 <= r["secchi"] < 3]; cl_ = [r for r in rows if r["secchi"] >= 6]
    return {"n": len(rows), "spearman": metrics.sp([r[key] for r in rows], [r["secchi"] for r in rows])[0], "medianSigned": med(rows, key),
            "medAE": round(float(np.median([abs(r[key] - r["secchi"]) for r in rows])), 2),
            "classAcc": round(float(np.mean([cls(r[key]) == cls(r["secchi"]) for r in rows])), 3),
            "stained": med(st_, key), "stainedN": len(st_), "clear": med(cl_, key), "clearN": len(cl_)}
res["F_paired"] = {m: ev_f(FA, k) for m, k in (("P2", "P2f"), ("C0", "C0"), ("C3", "C3n"), ("C6", "C6n"))}
FA1 = [r for r in FA if r["P1"] is not None]
res["F_paired"]["P1 (rows P1 also answers)"] = ev_f(FA1, "P1"); res["F_paired"]["P2 (same rows as P1)"] = ev_f(FA1, "P2f")

# the pre-registered water-type subsets (clean G), LOYO comparators
def subsets(rows):
    arm = lambda r: r["kind"] == "arm"
    return {"dark algal water": [r for r in rows if arm(r) and ((r["chl"] is not None and r["chl"] >= 15) or (r["chl"] is None and r["ndci"] > 0))],
            "stained arms": [r for r in rows if arm(r) and r["secchi"] <= 3],
            "stained 2-3 ft": [r for r in rows if 2 <= r["secchi"] < 3],
            "sediment-muddy": [r for r in rows if ((r.get("turb") or 0) >= 8 or r["secchi"] <= 3) and r["chl"] is not None and r["chl"] < 10],
            "very clear channel": [r for r in rows if r["kind"] == "mainStem" and r["secchi"] >= 6],
            "normal 3-6 ft": [r for r in rows if 3 <= r["secchi"] < 6],
            "tug-of-war (measured)": [r for r in rows if r["chl"] is not None and r["chl"] >= 15 and ((r.get("turb") or 0) >= 8 or (r.get("tss") or 0) >= 10)]}
res["subsets"] = {}
for lab, rows in subsets(Gc).items():
    ans = [r for r in rows if r["P2y"] is not None]
    res["subsets"][lab] = {"n": len(rows), "P2 answered": len(ans), "P2 paths": dict(collections.Counter(r["P2y_path"] for r in rows)),
                           "P2": med(ans, "P2y"), "C0": med(ans, "C0"), "C3": med(ans, "C3_year_NG"), "C6": med(ans, "C6_year"),
                           "P1 (same rows, where P1 answers)": med([r for r in ans if r["P1"] is not None], "P1"),
                           "P2 on those rows": med([r for r in ans if r["P1"] is not None], "P2y"),
                           "P1S": med([r for r in rows if r["P1S"] is not None], "P1S"), "P1S n": sum(r["P1S"] is not None for r in rows)}

# section 6: PROMISING criteria (LOYO primary)
A = [r for r in Gc if r["P2y"] is not None]
st = [r for r in A if 2 <= r["secchi"] < 3]; st1 = [r for r in st if r["P1"] is not None]
alg = [r for r in A if r["kind"] == "arm" and ((r["chl"] is not None and r["chl"] >= 15) or (r["chl"] is None and r["ndci"] > 0))]
clr = [r for r in A if r["kind"] == "mainStem" and r["secchi"] >= 6]
nor = [r for r in A if 3 <= r["secchi"] < 6]
allst = [r for r in Gc if 2 <= r["secchi"] < 3]
c = {"1 stained <= +1.0 and within 0.5 ft of P1": {"P2": med(st, "P2y"), "P1": med(st1, "P1"), "P2 on P1's rows": med(st1, "P2y"),
         "pass": med(st, "P2y") is not None and med(st, "P2y") <= 1.0 and med(st1, "P1") is not None and abs(med(st1, "P2y") - med(st1, "P1")) <= 0.5},
     "2 dark algal |median| <= 1.0": {"P2": med(alg, "P2y"), "pass": med(alg, "P2y") is not None and abs(med(alg, "P2y")) <= 1.0},
     "3 clear channel >= C3 - 0.5": {"P2": med(clr, "P2y"), "C3": med(clr, "C3_year_NG"), "pass": med(clr, "P2y") is not None and med(clr, "P2y") >= med(clr, "C3_year_NG") - 0.5},
     "4 normal |median| <= 1.0": {"P2": med(nor, "P2y"), "pass": med(nor, "P2y") is not None and abs(med(nor, "P2y")) <= 1.0},
     "5 coverage >= 80% clean and stained": {"clean": round(len(A) / len(Gc), 3), "stained": round(len(st) / len(allst), 3),
         "pass": len(A) / len(Gc) >= 0.8 and len(st) / len(allst) >= 0.8}}
res["promisingCriteria"] = c
res["promising"] = "PROMISING" if all(v["pass"] for v in c.values()) else "NOT PROMISING"

# section 5: the SWIR experiment P1S
S1 = [r for r in Gc if r["P1S"] is not None]
def m2(rows, k): return med(rows, k)
arms1 = [r for r in S1 if r["kind"] == "arm"]; ch1 = [r for r in S1 if r["kind"] == "mainStem"]
clr1 = [r for r in S1 if r["kind"] == "mainStem" and r["secchi"] >= 6]; st1b = [r for r in S1 if 2 <= r["secchi"] < 3]
alg1 = [r for r in S1 if r["kind"] == "arm" and ((r["chl"] is not None and r["chl"] >= 15) or (r["chl"] is None and r["ndci"] > 0))]
p1ok = lambda rows: [r for r in rows if r["P1"] is not None]
eS = evaluate(S1, "P1S") if S1 else {}
cS = {"i clear >= -1.5 and >= 1.5 ft closer than P1": {"P1S": m2(clr1, "P1S"), "P1": m2(p1ok(clr1), "P1"),
         "pass": m2(clr1, "P1S") is not None and m2(clr1, "P1S") >= -1.5 and abs(m2(clr1, "P1S")) <= abs(m2(p1ok(clr1), "P1")) - 1.5},
      "ii stained |median| <= 1.0 and <= 0.5 ft worse than P1": {"P1S": m2(st1b, "P1S"), "P1": m2(p1ok(st1b), "P1"),
         "pass": m2(st1b, "P1S") is not None and abs(m2(st1b, "P1S")) <= 1.0 and abs(m2(st1b, "P1S")) <= abs(m2(p1ok(st1b), "P1")) + 0.5},
      "iii dark algal |median| <= 1.0": {"P1S": m2(alg1, "P1S"), "pass": m2(alg1, "P1S") is not None and abs(m2(alg1, "P1S")) <= 1.0},
      "iv coverage >= 80% (clean, stained); arms and channel separately": {"clean": round(len(S1) / len(Gc), 3), "stained": round(len(st1b) / len(allst), 3),
         "arms": m2(arms1, "P1S"), "channel": m2(ch1, "P1S"), "pass": len(S1) / len(Gc) >= 0.8 and len(st1b) / len(allst) >= 0.8},
      "v nine gates": {"gates": metrics.gates(eS, evaluate(S1, "C0")) if S1 else None}}
cS["v nine gates"]["pass"] = bool(cS["v nine gates"]["gates"]) and all(cS["v nine gates"]["gates"].values())
res["P1S"] = {"criteria": cS, "evaluate": {k: eS.get(k) for k in ("n", "spearman", "medianSigned", "MAE", "medAE", "AUC_clearChannel_vs_stainedArm", "classAcc", "classAccConstant", "monotone")},
              "subsets": eS.get("subsets"), "refusals": dict(collections.Counter("answered" if r["P1S"] is not None else "refused" for r in Gc)),
              "verdict": "P1S PASSES ITS DEVELOPMENT CRITERIA" if all(v.get("pass") for v in cS.values()) else "P1S FAILS ITS DEVELOPMENT CRITERIA"}
# confusion (LOYO)
m = [[0] * 4 for _ in range(4)]
for r in A: m[cls(r["secchi"])][cls(r["P2y"])] += 1
res["confusion_P2_LOYO"] = m
# every stained row
res["stained"] = [{"date": r["date"], "station": r["name"], "kind": r["kind"], "secchi": round(r["secchi"], 2), "P1": r["P1"] and round(r["P1"], 2),
                   "P2": r["P2y"] and round(r["P2y"], 2), "path": r["P2y_path"], "S": r["P2y_S"] if r["P2y_S"] is None or not math.isfinite(r["P2y_S"]) else round(r["P2y_S"], 2),
                   "B05/B11": r["srr"] and round(r["srr"], 1), "C3": round(r["C3_year_NG"], 2), "P1S": r["P1S"] and round(r["P1S"], 2), "ndci": round(r["ndci"], 3)}
                  for r in sorted(allst, key=lambda r: (r["date"], r["name"]))]
json.dump(res, open(f"{D10}/dev_results.json", "w"), indent=1, default=str)
print("stage8 reproduced", repro)
print("PROMISING?", res["promising"]); print(json.dumps(c, indent=0))
print(json.dumps(res["routes"], indent=0)); print(json.dumps(res["S_by_class"])); print(json.dumps(res["S_by_kind"]))
for sch in ("LOYO", "LOSO"):
    for k, e in res["paired"][sch].items():
        sub = e["subsets"]
        print(f"{sch} {k}: n {e['n']} sp {e['spearman'][0]:+.2f} medS {e['medianSigned']:+.2f} MAE {e['MAE']:.2f} medAE {e['medAE']:.2f} stBal {e['stationBalancedMedianSigned']:+.2f} "
              f"AUC {e['AUC_clearChannel_vs_stainedArm']} cls {e['classAcc']:.2f}/{e['classAccConstant']:.2f} mono {e['monotone']} | stained {sub['stained 2-3 ft'].get('medianSigned')} (n {sub['stained 2-3 ft']['n']}) "
              f"clear {sub['clear channel'].get('medianSigned')} (n {sub['clear channel']['n']}) algal {sub['algal arms'].get('medianSigned')} sed {sub['sediment turbid'].get('medianSigned')}")
print(json.dumps(res["gates"])); print("N", json.dumps(res["N_paired"])); print("F", json.dumps(res["F_paired"]))
print(json.dumps(res["subsets"], indent=0)); print(res["P1S"]["verdict"], json.dumps(cS, default=str))
