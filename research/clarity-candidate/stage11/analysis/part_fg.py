"""Stage 11 Parts F and G (PREREGISTRATION_STAGE11.md sections 8 and 9).
F: Landsat 8/9 (Dogliotti FNU on OLI B4) and Sentinel-3 OLCI (TSM_NN) against the S2 production FNU; agreement sets;
   S2+Landsat fusion. G: temporal consistency over every pass within +-10 days (same extractor, same disk).
Writes part_fg.json."""
import json, math, collections, random, csv, os
import numpy as np
from common import *
rows = {x["id"]: x for x in load() if x["secchi"] and x["secchi"] > 0}
res = {}
def eS(fnu, S):
    return math.log10(champ(fnu) / S)
def boot_diff(a_rows, b_rows, fn, B=3000, seed=11):
    g = random.Random(seed); v = []
    for _ in range(B):
        a = [a_rows[g.randrange(len(a_rows))] for _ in a_rows]; b = [b_rows[g.randrange(len(b_rows))] for _ in b_rows]
        v.append(fn(a) - fn(b))
    v.sort(); return [round(v[int(.025 * B)], 3), round(v[int(.975 * B) - 1], 3)]
# ---------------- F: Landsat
L = json.load(open(f"{D11}/multisensor/landsat.json")) if os.path.exists(f"{D11}/multisensor/landsat.json") else {}
LS = []
for k, v in L.items():
    x = rows.get(k)
    if not x: continue
    ps = [p for p in v.get("passes", []) if p.get("fnu") is not None and p.get("valid", 0) >= 5]
    if not ps: continue
    p = min(ps, key=lambda p: abs((np.datetime64(p["datetime"][:19]) - np.datetime64(x["date"] + "T16:00:00")).astype("timedelta64[h]").astype(int)))
    x["ls_fnu"] = p["fnu"]; x["ls_platform"] = p["platform"]
    LS.append(x)
res["F_landsat"] = {"rows_with_read": len(LS), "lakes": len({x["lake"] for x in LS})}
if len(LS) >= 20:
    lr = [math.log10(max(x["ls_fnu"], 0.1) / max(x["fnu"], 0.1)) for x in LS]
    res["F_landsat"]["S2_vs_Landsat_log_ratio"] = {"median": round(float(np.median(lr)), 3), "median_abs": round(float(np.median(np.abs(lr))), 3),
                                                   "spearman": round(float(np.corrcoef(np.argsort(np.argsort([x['fnu'] for x in LS])), np.argsort(np.argsort([x['ls_fnu'] for x in LS])))[0, 1]), 3)}
    agree = [x for x, r in zip(LS, lr) if abs(r) <= 0.15]; dis = [x for x, r in zip(LS, lr) if abs(r) > 0.15]
    f = lambda R: float(np.median([abs(eS(x["fnu"], x["secchi"])) for x in R]))
    res["F_landsat"]["agree"] = {"n": len(agree), "median_abs_eS": round(f(agree), 3) if agree else None}
    res["F_landsat"]["disagree"] = {"n": len(dis), "median_abs_eS": round(f(dis), 3) if dis else None}
    if len(agree) >= 30 and len(dis) >= 30:
        res["F_landsat"]["agree_minus_disagree_ci"] = boot_diff(agree, dis, f)
        res["F_landsat"]["agree_relative_reduction"] = round((f(dis) - f(agree)) / f(dis), 3)
    fused = lambda x: 10 ** ((math.log10(max(x["fnu"], 0.1)) + math.log10(max(x["ls_fnu"], 0.1))) / 2)
    e_s2 = [abs(eS(x["fnu"], x["secchi"])) for x in LS]; e_fu = [abs(eS(fused(x), x["secchi"])) for x in LS]
    e_ls = [abs(eS(x["ls_fnu"], x["secchi"])) for x in LS]
    res["F_landsat"]["S2 alone median_abs_eS"] = round(float(np.median(e_s2)), 3)
    res["F_landsat"]["Landsat alone median_abs_eS"] = round(float(np.median(e_ls)), 3)
    res["F_landsat"]["fused median_abs_eS"] = round(float(np.median(e_fu)), 3)
    idx = list(range(len(LS))); g = random.Random(11); dd = []
    for _ in range(3000):
        s = [idx[g.randrange(len(idx))] for _ in idx]; dd.append(float(np.median([e_fu[i] for i in s]) - np.median([e_s2[i] for i in s])))
    dd.sort(); res["F_landsat"]["fused_minus_S2_ci"] = [round(dd[75], 3), round(dd[2924], 3)]
    T = [x for x in LS if x.get("turb") is not None]
    if len(T) >= 20:
        res["F_landsat"]["eT"] = {"n": len(T), "S2 median_abs_eT": round(float(np.median([abs(math.log10(max(x['fnu'], .1) / max(x['turb'], .1))) for x in T])), 3),
                                  "Landsat median_abs_eT": round(float(np.median([abs(math.log10(max(x['ls_fnu'], .1) / max(x['turb'], .1))) for x in T])), 3),
                                  "fused median_abs_eT": round(float(np.median([abs(math.log10(fused(x) / max(x['turb'], .1))) for x in T])), 3)}
    wp = (res["F_landsat"].get("agree_relative_reduction", 0) >= 0.25 and res["F_landsat"].get("agree_minus_disagree_ci", [0, 0])[1] < 0) or \
         (len(LS) >= 50 and (np.median(e_s2) - np.median(e_fu)) / np.median(e_s2) >= 0.10 and res["F_landsat"]["fused_minus_S2_ci"][1] < 0)
    res["F_landsat"]["worth_pursuing_by_rule"] = bool(wp)
# ---------------- F: OLCI
O = json.load(open(f"{D11}/multisensor/olci.json")) if os.path.exists(f"{D11}/multisensor/olci.json") else {}
OS = []
for k, v in O.items():
    x = rows.get(k)
    if not x: continue
    ps = [p for p in v.get("passes", []) if p.get("tsm_log10") is not None]
    if ps:
        x["olci_tsm"] = 10 ** float(np.median([p["tsm_log10"] for p in ps])); x["olci_chl"] = 10 ** float(np.median([p["chl_nn_log10"] for p in ps if p.get("chl_nn_log10") is not None] or [np.nan]))
        OS.append(x)
res["F_olci"] = {"rows_attempted": len(O), "rows_with_read": len(OS), "lakes": len({x["lake"] for x in OS})}
if len(OS) >= 20:
    lr = [math.log10(max(x["olci_tsm"], 0.1) / max(x["fnu"], 0.1)) for x in OS]
    res["F_olci"]["TSM_vs_S2_FNU_log_ratio"] = {"median": round(float(np.median(lr)), 3), "spread_p10_p90": [round(float(np.percentile(lr, 10)), 3), round(float(np.percentile(lr, 90)), 3)]}
    agree = [x for x, r in zip(OS, lr) if abs(r - np.median(lr)) <= 0.15]; dis = [x for x, r in zip(OS, lr) if abs(r - np.median(lr)) > 0.15]
    f = lambda R: float(np.median([abs(eS(x["fnu"], x["secchi"])) for x in R]))
    res["F_olci"]["agree (after median TSM/FNU offset)"] = {"n": len(agree), "median_abs_eS": round(f(agree), 3) if agree else None}
    res["F_olci"]["disagree"] = {"n": len(dis), "median_abs_eS": round(f(dis), 3) if dis else None}
    if len(agree) >= 30 and len(dis) >= 30:
        res["F_olci"]["agree_minus_disagree_ci"] = boot_diff(agree, dis, f)
    T = [x for x in OS if x.get("turb") is not None]
    if len(T) >= 10:
        res["F_olci"]["TSM_vs_insitu_turbidity"] = {"n": len(T), "spearman_rank": round(float(np.corrcoef(np.argsort(np.argsort([x['olci_tsm'] for x in T])), np.argsort(np.argsort([x['turb'] for x in T])))[0, 1]), 3),
                                                   "S2 FNU spearman_rank": round(float(np.corrcoef(np.argsort(np.argsort([x['fnu'] for x in T])), np.argsort(np.argsort([x['turb'] for x in T])))[0, 1]), 3)}
# ---------------- G: temporal consistency
NB = collections.defaultdict(list)
p = f"{D11}/temporal/neighbors_readouts.csv"
if os.path.exists(p):
    for r in csv.DictReader(open(p)):
        if r.get("error") or not r.get("fnu_prod") or int(float(r.get("n_valid") or 0)) < 5:
            continue
        NB[r["id"]].append((r["item"], r["pass_date"], float(r["fnu_prod"])))
flag, unf, repl = [], [], []
for k, x in rows.items():
    nb = NB.get(k.split(":", 1)[1] if ":" in k else k) or NB.get(k)
    if not nb: continue
    others = [f for it, d, f in nb if it != x["item"]]
    if len(others) < 2: continue
    lo = np.log10(np.maximum(others, 0.1)); m = float(np.median(lo)); mad = float(np.median(np.abs(lo - m)))
    t = math.log10(max(x["fnu"], 0.1))
    x["tflag"] = abs(t - m) > 0.30 and mad <= 0.15
    x["tmed"] = 10 ** m
    (flag if x["tflag"] else unf).append(x)
res["G"] = {"rows_with_neighbors": len(flag) + len(unf), "flagged": len(flag), "flag_rate": round(len(flag) / max(1, len(flag) + len(unf)), 3)}
if flag:
    fm = float(np.median([abs(eS(x["fnu"], x["secchi"])) for x in flag])); um = float(np.median([abs(eS(x["fnu"], x["secchi"])) for x in unf]))
    rm = float(np.median([abs(eS(x["tmed"], x["secchi"])) for x in flag]))
    res["G"].update({"flagged median_abs_eS": round(fm, 3), "unflagged median_abs_eS": round(um, 3), "ratio": round(fm / um, 2),
                     "flagged after replacement median_abs_eS": round(rm, 3), "replacement_reduction": round((fm - rm) / fm, 3),
                     "useful_by_rule": bool(len(flag) >= 20 and fm >= 1.5 * um and (fm - rm) / fm >= 0.20)})
    # EXPLORATORY (not pre-registered): refusing flagged passes instead of replacing them
    am = float(np.median([abs(eS(x["fnu"], x["secchi"])) for x in flag + unf]))
    res["G"]["exploratory_refuse"] = {"all rows median_abs_eS": round(am, 3), "after refusing flagged": round(um, 3),
                                      "relative_reduction": round((am - um) / am, 3), "coverage_kept": round(len(unf) / (len(flag) + len(unf)), 3)}
json.dump(res, open(f"{D11}/analysis/part_fg.json", "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
