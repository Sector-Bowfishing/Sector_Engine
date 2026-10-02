"""EXPLORATORY (not pre-registered; no verdict uses it). Same folds, same Part 5 rubric, other inputs:
 A. production: the frozen champion on Sen2Cor FNU, all corpus rows (Sen2Cor always has a disk);
 B. C3 refitted on Sen2Cor reflectance, all corpus rows (lake-held-out);
 C. C3 refitted on Sen2Cor reflectance on the same 1,206 rows as the ACOLITE engine (attributes the Part 4 gain);
 D. the ACOLITE C3 engine on rows with a valid ACOLITE disk only (capability conditional on a retrieval).
Exact-feet authorisation from inner folds exactly as models12.py. Writes explore12.json."""
import json, math, collections, subprocess, sys
from common12 import *
R = [x for x in load12() if x["processed"] and not x["gunt"] and x["secchi"] and x["secchi"] > 0]
def c3f(raw):
    lr = math.log10(max(raw["red"], 0.001)); nd = ndci(raw); a = 1.0 if nd > 0 else 0.0
    return [1 - a, (1 - a) * lr, a, a * lr]
def fitc3(tr, key):
    X = np.array([c3f(key(x)) for x in tr]); y = np.array([math.log10(x["secchi"]) for x in tr]); return np.linalg.lstsq(X, y, rcond=None)[0]
s2 = lambda x: x["sen2cor"]
def heldout(rows, predfn_fit):
    out = {}
    for k in range(5):
        tr = [x for x in rows if fold(x["lake"]) != k]; te = [x for x in rows if fold(x["lake"]) == k]
        f = predfn_fit(tr)
        for x in te: out[x["id"]] = f(x)
    return out
def inner_auth(rows, predfn_fit, bars={"clear": 1.5, "normal": 1.0, "stained": 0.75, "limited": 0.75}):
    auth = {}
    for k in range(5):
        tr = [x for x in rows if fold(x["lake"]) != k]; inner = []
        for j in range(4):
            itr = [x for x in tr if (fold(x["lake"], 20) % 4) != j]; ite = [x for x in tr if (fold(x["lake"], 20) % 4) == j]
            f = predfn_fit(itr); inner += [(x, f(x)) for x in ite]
        ok = []
        for c in CLASSES:
            sub = [(x, v) for x, v in inner if v and cname(v) == c]
            if len(sub) < 10: continue
            if np.median([abs(math.log10(v / x["secchi"])) for x, v in sub]) <= 0.15 and abs(np.median([v - x["secchi"] for x, v in sub])) <= bars[c]: ok.append(c)
        auth[k] = set(ok)
    return auth
champ_fit = lambda tr: (lambda x: champ(x["fnu"]))
c3s_fit = lambda tr: (lambda b: (lambda x: 10 ** float(np.dot(b, c3f(s2(x))))))(fitc3(tr, s2))
def rubric(rows, pred, auth, unknown=lambda x: False):
    import importlib
    rec = []
    for x in rows:
        ft = None if unknown(x) else pred.get(x["id"])
        c_pred = cname(ft) if ft else "unknown"
        rec.append({"true": cname(x["secchi"]), "pred": c_pred, "ft": ft, "secchi": x["secchi"], "feet": ft is not None and c_pred in auth[fold(x["lake"])],
                    "insitu_type": x["insitu_type"], "turb": x.get("turb")})
    n = len(rec)
    def rp(c):
        tp = sum(1 for r in rec if r["true"] == c and r["pred"] == c); nt = sum(1 for r in rec if r["true"] == c); npred = sum(1 for r in rec if r["pred"] == c)
        return (tp / nt if nt else 0, tp / npred if npred else 0)
    res = {"rows": n, "unknown": round(sum(r["pred"] == "unknown" for r in rec) / n, 3), "feet_published": round(sum(r["feet"] for r in rec) / n, 3),
           "median_abs_log_all": round(float(np.median([abs(math.log10(r["ft"] / r["secchi"])) for r in rec if r["ft"]])), 4),
           "class_recall_precision": {c: tuple(round(v, 3) for v in rp(c)) for c in CLASSES},
           "class_accuracy_answered": round(float(np.mean([r["true"] == r["pred"] for r in rec if r["pred"] != "unknown"])), 3)}
    return res
out = {}
A = {x["id"]: champ(x["fnu"]) for x in R}
out["A_production_all_rows"] = rubric(R, A, inner_auth(R, champ_fit))
B = heldout(R, c3s_fit); out["B_C3_on_Sen2Cor_all_rows"] = rubric(R, B, inner_auth(R, c3s_fit))
V = [x for x in R if x["aco_valid"]]
Cp = heldout(V, c3s_fit); out["C_C3_on_Sen2Cor_same_rows_as_ACOLITE"] = rubric(V, Cp, inner_auth(V, c3s_fit))
P = {x["id"]: x["pred"].get("C3") for x in json.load(open(f"{D12}/analysis/preds12.json")) if not x["gunt"]}
M = json.load(open(f"{D12}/analysis/models12.json")); au = {int(k): set(v) for k, v in M["feet_authorisation"].items()}
out["D_ACOLITE_C3_valid_rows_only"] = rubric(V, P, au)
out["E_ACOLITE_C3_all_rows (Unknown where no disk)"] = rubric(R, P, au, unknown=lambda x: not x["aco_valid"])
json.dump(out, open(f"{D12}/analysis/explore12.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
