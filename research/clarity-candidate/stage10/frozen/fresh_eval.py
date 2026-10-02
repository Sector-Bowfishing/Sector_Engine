"""The frozen fresh-validation analysis (PREREGISTRATION_P2.md sections 7-9). Run it ONCE per data freeze:

  python fresh_eval.py fresh_obs.csv fresh_readouts.csv [--national national_readouts.csv] --out verdict.json

Nothing in this file may change after the freeze (frozen_manifest.json). It scores the champion, C3, C6,
P1, P2 and P1S on the fresh held-out rows with the Stage 7 metrics and the Stage 8 nine gates, applies
the coverage precondition and the minimum-sample rules, and scores the seven capabilities.
"""
import argparse, csv, json, math, collections
import numpy as np
import metrics, models, p2 as P2
from p1 import p1 as P1

num = lambda x: None if x in (None, "", "None") else float(x)
boo = lambda x: None if x in (None, "", "None") else str(x).lower() == "true"
MUDDY = ("brown", "mud", "muddy", "tan", "chocolate", "coffee", "silt", "dirty")
CLS_NAMES = ("clear", "normal", "stained", "limited")

# minimum Secchi-grade clean rows before a class may be judged (section 8)
MINIMA = {"clear channel": (20, 5, None), "normal 3-6": (25, 5, None), "stained 2-3": (30, 5, 4),
          "limited <2": (10, 3, None), "warm-season arms": (20, 4, 4), "algal": (20, 4, None), "sediment-driven": (12, 3, None)}


def best_pass(readouts):
    best = {}
    for r in csv.DictReader(open(readouts)):
        if r.get("error") or int(num(r.get("n_valid")) or 0) < 5 or num(r.get("rho_rededge1_v")) is None:
            continue
        k = (abs(int(r["dt_days"])), -int(num(r["n_valid"])))
        if r["id"] not in best or k < best[r["id"]][0]:
            best[r["id"]] = (k, r)
    return {i: v[1] for i, v in best.items()}


def rows_from(obs_path, readouts_path):
    ro = best_pass(readouts_path)
    rows = []
    for o in csv.DictReader(open(obs_path)):
        r = ro.get(o["id"])
        if r is None:
            continue
        raw = {"blue": num(r["rho_blue_v"]), "green": num(r["rho_green_v"]), "red": num(r["rho_red_v"]), "re1": num(r["rho_rededge1_v"])}
        red, re1 = max(raw["red"], 0.001), max(raw["re1"], 0.001)
        nw = int(num(r.get("n_water")) or 0)
        vegpx = nw > 0 and max(int(num(r.get("drop_ndvi")) or 0), int(num(r.get("drop_fai")) or 0)) >= 0.2 * nw
        truth, depth = num(o["truth_ft"]), num(o.get("depthFt"))
        colour = (o.get("waterColorNotes") or "").lower()
        ndci = (re1 - red) / (re1 + red)
        x = {"id": o["id"], "source": o["source"], "tier": o["tier"], "secchi": truth, "band": (num(o.get("band_low")), num(o.get("band_high"))),
             "date": o["date"], "month": int(o["date"][5:7]), "sceneDay": r["pass_date"], "dt": int(r["dt_days"]),
             "site": o["site"], "kind": o["kind"], "arm": o.get("arm") or None, "raw": raw, "sun": num(r["sun_elev"]),
             "swir": num(r.get("rho_swir16_v")), "fnu": num(r.get("fnu_prod")), "ndci": ndci, "red": red,
             "chl": num(o.get("chl")), "turb": num(o.get("turb")),
             "veg": bool(vegpx or boo(o.get("vegetationPresent"))),
             "bottom": bool(boo(o.get("bottomVisible")) or (depth and truth is not None and truth >= 0.5 * depth)),
             "colourMuddy": any(k in colour for k in MUDDY) and "green" not in colour}
        x["algal"] = ndci > 0.03 or (x["chl"] is not None and x["chl"] >= 15)
        x["sediment"] = ndci <= 0 and ((x["turb"] or 0) >= 8 or x["colourMuddy"])
        x["C0"] = models.champion(x["fnu"]); x["C3"] = models.c3(raw); x["C6"] = models.c6(raw, True)
        z, why, _ = P1(raw, x["sun"]); x["P1"], x["P1_why"] = z, why
        rt = P2.route(raw, x["sun"], x["swir"]); x["P2"], x["P2_path"], x["P2_reason"], x["P2_S"] = rt["ft"], rt["path"], rt["reason"], rt["S"]
        zs, _, _ = models.p1s(raw, x["sun"], x["swir"]); x["P1S"] = zs
        x["C3dom"] = models.c3_in_domain(raw, x["C3"])
        rows.append(x)
    return rows


def dedupe(rows):
    """One row per (site cluster, scene-day, tier): medians of truth; the first read-out (they share pixels)."""
    g = collections.defaultdict(list)
    for r in rows:
        g[(r["site"], r["sceneDay"], r["tier"])].append(r)
    out = []
    for v in g.values():
        r = dict(v[0])
        t = [x["secchi"] for x in v if x["secchi"] is not None]
        r["secchi"] = float(np.median(t)) if t else None
        r["n_reports"] = len(v)
        out.append(r)
    return out


def classes(rows, key):
    """recall/precision per class; a refusal (None) is never a hit."""
    out = {}
    for c, nm in enumerate(CLS_NAMES):
        truth = [r for r in rows if metrics.cls(r["secchi"]) == c]
        called = [r for r in rows if r.get(key) is not None and metrics.cls(r[key]) == c]
        out[nm] = {"truthN": len(truth), "called": len(called),
                   "recall": round(sum(1 for r in truth if r.get(key) is not None and metrics.cls(r[key]) == c) / len(truth), 3) if truth else None,
                   "precision": round(sum(1 for r in called if metrics.cls(r["secchi"]) == c) / len(called), 3) if called else None,
                   "refused": sum(1 for r in truth if r.get(key) is None)}
    return out


def med(rows, key):
    s = [r[key] - r["secchi"] for r in rows if r.get(key) is not None]
    return round(float(np.median(s)), 2) if s else None


def minima_met(rows, name):
    n, days, arms = MINIMA[name]
    ok = len(rows) >= n and len({r["sceneDay"] for r in rows}) >= days and (arms is None or len({r["arm"] for r in rows if r["arm"]}) >= arms)
    return {"n": len(rows), "sceneDays": len({r["sceneDay"] for r in rows}), "arms": len({r["arm"] for r in rows if r["arm"]}), "met": ok}


def capability(rows, key, alg_ppv=None):
    """The seven capabilities for one system (section 10). Returns NOT / PARTIAL / SUPPORTED / INSUFFICIENT."""
    cl = classes(rows, key); verdict = {}
    def sub(f): return [r for r in rows if f(r)]
    clear = sub(lambda r: r["kind"] == "mainStem" and r["secchi"] >= 6)
    m = minima_met(clear, "clear channel"); ms = med(clear, key); rc, pc = cl["clear"]["recall"], cl["clear"]["precision"]
    ref = (sum(1 for r in clear if r.get(key) is None) / len(clear)) if clear else None
    if not m["met"]: verdict["clear channel water"] = "INSUFFICIENT"
    elif len(clear) >= 40 and m["sceneDays"] >= 8 and ms is not None and -1.5 <= ms <= 1.5 and (rc or 0) >= 0.6 and (pc or 0) >= 0.75 and ref <= 0.3:
        verdict["clear channel water"] = "SUPPORTED"
    elif ms is not None and ms >= -2.5 and (rc or 0) >= 0.4 and (pc or 0) >= 0.6: verdict["clear channel water"] = "PARTIAL"
    else: verdict["clear channel water"] = "NOT"
    normal = sub(lambda r: 3 <= r["secchi"] < 6); m = minima_met(normal, "normal 3-6"); ms = med(normal, key)
    e = metrics.evaluate([r for r in rows if r.get(key) is not None], key) if any(r.get(key) is not None for r in rows) else {"monotone": False}
    if not m["met"]: verdict["normal 3-6 ft water"] = "INSUFFICIENT"
    elif len(normal) >= 40 and m["sceneDays"] >= 8 and ms is not None and abs(ms) <= 1.0 and (cl["normal"]["recall"] or 0) >= 0.6 and (cl["normal"]["precision"] or 0) >= 0.6 and e.get("monotone"):
        verdict["normal 3-6 ft water"] = "SUPPORTED"
    elif ms is not None and abs(ms) <= 1.5 and (cl["normal"]["recall"] or 0) >= 0.5: verdict["normal 3-6 ft water"] = "PARTIAL"
    else: verdict["normal 3-6 ft water"] = "NOT"
    st = sub(lambda r: 2 <= r["secchi"] < 3); m = minima_met(st, "stained 2-3"); ms = med(st, key)
    seasons = {("warm" if 5 <= r["month"] <= 9 else "cool") for r in st}
    if not m["met"]: verdict["stained 2-3 ft water"] = "INSUFFICIENT"
    elif len(st) >= 60 and m["sceneDays"] >= 10 and m["arms"] >= 6 and seasons == {"warm", "cool"} and ms is not None and abs(ms) <= 0.75 \
            and (cl["stained"]["recall"] or 0) >= 0.6 and (cl["stained"]["precision"] or 0) >= 0.6:
        verdict["stained 2-3 ft water"] = "SUPPORTED"
    elif ms is not None and abs(ms) <= 1.0 and (cl["stained"]["recall"] or 0) >= 0.4 and (cl["stained"]["precision"] or 0) >= 0.4:
        verdict["stained 2-3 ft water"] = "PARTIAL"
    else: verdict["stained 2-3 ft water"] = "NOT"
    alg = sub(lambda r: r["algal"]); m = minima_met(alg, "algal"); ms = med(alg, key)
    ea = metrics.evaluate([r for r in alg if r.get(key) is not None], key) if sum(r.get(key) is not None for r in alg) >= 5 else None
    if not m["met"] or alg_ppv is None: verdict["algae-affected water"] = "INSUFFICIENT"
    elif len(alg) >= 30 and m["sceneDays"] >= 5 and alg_ppv >= 0.40 and ms is not None and abs(ms) <= 1.0 and ea and ea["classAcc"] >= ea["classAccConstant"] + 0.10:
        verdict["algae-affected water"] = "SUPPORTED"
    elif alg_ppv >= 0.25: verdict["algae-affected water"] = "PARTIAL"
    else: verdict["algae-affected water"] = "NOT"
    sed = sub(lambda r: r["sediment"]); m = minima_met(sed, "sediment-driven"); ms = med(sed, key)
    bright = sum(1 for r in sed if r.get(key) is not None and r[key] >= 6 and r["secchi"] < 4) / len(sed) if sed else None
    if not m["met"]: verdict["sediment-muddy water"] = "INSUFFICIENT"
    elif len(sed) >= 20 and m["sceneDays"] >= 4 and ms is not None and abs(ms) <= 1.0 and bright <= 0.05: verdict["sediment-muddy water"] = "SUPPORTED"
    elif ms is not None and abs(ms) <= 2.0 and bright <= 0.15: verdict["sediment-muddy water"] = "PARTIAL"
    else: verdict["sediment-muddy water"] = "NOT"
    lim = sub(lambda r: r["secchi"] < 2); m = minima_met(lim, "limited <2"); ms = med(lim, key)
    if not m["met"]: verdict["badly visibility-limited water"] = "INSUFFICIENT"
    else:
        high = sum(1 for r in lim if r.get(key) is not None and r[key] >= 4) / len(lim)
        safe = sum(1 for r in lim if r.get(key) is None or r[key] < 3) / len(lim)
        if len(lim) >= 25 and m["sceneDays"] >= 5 and (cl["limited"]["recall"] or 0) >= 0.6 and (cl["limited"]["precision"] or 0) >= 0.5 and ms is not None and ms <= 0.75:
            verdict["badly visibility-limited water"] = "SUPPORTED"
        elif high <= 0.10 and safe >= 0.60: verdict["badly visibility-limited water"] = "PARTIAL"
        else: verdict["badly visibility-limited water"] = "NOT"
    # bottom-risk needs a depth input the product does not have (bathymetry is out of scope): it cannot be earned here
    verdict["bottom-risk / shallow clear water"] = "NOT (no depth input; cannot be earned in this track)"
    return verdict, cl


SCORE = {"SUPPORTED": 1.0, "PARTIAL": 0.5}


def score(verdict, prior):
    """Fresh evidence moves a capability; INSUFFICIENT keeps the prior verdict (section 10)."""
    s = 0.0; used = {}
    for k, v in verdict.items():
        v2 = prior[k] if v == "INSUFFICIENT" else v
        used[k] = v2; s += SCORE.get(v2.split(" ")[0], 0.0)
    return round(s / 7 * 10, 1), round(s / 7 * 10), used


PRIOR = {"clear channel water": "NOT", "normal 3-6 ft water": "PARTIAL", "stained 2-3 ft water": "NOT",
         "algae-affected water": "PARTIAL", "sediment-muddy water": "PARTIAL", "badly visibility-limited water": "NOT",
         "bottom-risk / shallow clear water": "NOT"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("obs"); ap.add_argument("readouts"); ap.add_argument("--national"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    allrows = dedupe(rows_from(a.obs, a.readouts))
    secchi = [r for r in allrows if r["tier"] in ("agencySecchi", "secchiDisk") and r["secchi"] is not None]
    clean = [r for r in secchi if not r["veg"] and not r["bottom"]]
    res = {"counts": {"all": len(allrows), "byTier": dict(collections.Counter(r["tier"] for r in allrows)),
                      "secchiGrade": len(secchi), "clean": len(clean)}}
    res["minima"] = {k: minima_met(v, k) for k, v in {
        "clear channel": [r for r in clean if r["kind"] == "mainStem" and r["secchi"] >= 6],
        "normal 3-6": [r for r in clean if 3 <= r["secchi"] < 6], "stained 2-3": [r for r in clean if 2 <= r["secchi"] < 3],
        "limited <2": [r for r in clean if r["secchi"] < 2], "warm-season arms": [r for r in clean if r["kind"] == "arm" and 5 <= r["month"] <= 9],
        "algal": [r for r in clean if r["algal"]], "sediment-driven": [r for r in clean if r["sediment"]]}.items()}
    # P2 coverage precondition and the nine gates, paired on P2's answered rows
    st = [r for r in clean if 2 <= r["secchi"] < 3]
    cov = {"clean": round(sum(r["P2"] is not None for r in clean) / len(clean), 3) if clean else None,
           "stained": round(sum(r["P2"] is not None for r in st) / len(st), 3) if st else None}
    cov["pass"] = bool(cov["clean"] is not None and cov["stained"] is not None and cov["clean"] >= 0.8 and cov["stained"] >= 0.8)
    res["P2coverage"] = cov
    res["P2routes"] = dict(collections.Counter(r["P2_path"] for r in clean))
    A = [r for r in clean if r["P2"] is not None and all(r[k] is not None for k in ("C0", "C3", "C6"))]
    res["paired"] = {k: metrics.evaluate(A, k) for k in ("P2", "C0", "C3", "C6")} if len(A) >= 5 else {}
    A1 = [r for r in A if r["P1"] is not None]
    if res["paired"] and len(A1) >= 5:
        res["paired"]["P1"] = metrics.evaluate(A1, "P1")
    g = {"P2": metrics.gates(res["paired"]["P2"], res["paired"]["C0"])} if res["paired"] else {}
    if a.national:
        nat = [r for r in rows_from_national(a.national)]
        n2, n0 = ev_n([r for r in nat if r["P2"] is not None], "P2"), ev_n([r for r in nat if r["P2"] is not None], "C0")
        res["national"] = {"P2": n2, "C0": n0}
        g["9 N medAE<=1.1x and AL MAE<=1.2x (paired)"] = bool(n2["all"]["medAE"] <= 1.1 * n0["all"]["medAE"] and
                                                         (n2["AL"].get("MAE") or 99) <= 1.2 * (n0["AL"].get("MAE") or 0))
    else:
        g["9 N medAE<=1.1x and AL MAE<=1.2x (paired)"] = "PENDING (no fresh national set supplied)"
    res["gates"] = g
    core = all(res["minima"][k]["met"] for k in ("clear channel", "normal 3-6", "stained 2-3"))
    passed = bool(g.get("P2")) and all(g["P2"].values()) and g["9 N medAE<=1.1x and AL MAE<=1.2x (paired)"] is True and cov["pass"]
    res["P2verdict"] = ("INSUFFICIENT DATA" if not core else "P2 READY" if passed else "P2 NOT READY")
    # the SWIR experiment, separately (section 6)
    sw = [r for r in clean if r["P1S"] is not None]
    res["P1S"] = {"n": len(sw), "arms": med([r for r in sw if r["kind"] == "arm"], "P1S"), "channel": med([r for r in sw if r["kind"] == "mainStem"], "P1S"),
                  "stained": med([r for r in sw if 2 <= r["secchi"] < 3], "P1S"), "stainedP1": med([r for r in sw if 2 <= r["secchi"] < 3 and r["P1"] is not None], "P1"),
                  "clearChannel": med([r for r in sw if r["kind"] == "mainStem" and r["secchi"] >= 6], "P1S"),
                  "clearChannelP1": med([r for r in sw if r["kind"] == "mainStem" and r["secchi"] >= 6 and r["P1"] is not None], "P1"),
                  "algal": med([r for r in sw if r["algal"]], "P1S")}
    # algal-warning PPV on fresh rows (Stage 8 definition: flag NDCI > 0.03; target champion >= 1.5 x Secchi)
    fl = [r for r in secchi if r["ndci"] > 0.03 and r["C0"] is not None]
    ppv = round(sum(r["C0"] >= 1.5 * r["secchi"] for r in fl) / len(fl), 3) if len(fl) >= 20 else None
    res["algalWarningPPV"] = {"flagged": len(fl), "ppv": ppv}
    # capabilities: the product as it runs (champion + warning), and each candidate as if deployed
    res["capabilities"] = {}
    for sysname, key in (("product today (champion + algal warning)", "C0"), ("P2", "P2"), ("P1", "P1"), ("C3", "C3"), ("C6", "C6")):
        v, cl = capability(clean, key, alg_ppv=ppv)
        exact, rounded, used = score(v, PRIOR)
        res["capabilities"][sysname] = {"verdicts": v, "used": used, "score": exact, "readiness": rounded, "classes": cl}
    # diagnostics named in the pre-registration (not gated)
    arms = [r for r in clean if r["kind"] == "arm" and r["P1"] is not None]
    if len(arms) >= 5:
        res["diagnostics"] = {"P1 error vs NDCI in arms (Spearman)": metrics.sp([r["ndci"] for r in arms], [r["P1"] - r["secchi"] for r in arms]),
                              "P1 error vs B05/B11 in arms (Spearman)": metrics.sp([(r["raw"]["re1"] / r["swir"]) if r["swir"] else 0 for r in arms], [r["P1"] - r["secchi"] for r in arms])}
    res["secondary"] = {t: {"n": sum(1 for r in allrows if r["tier"] == t)} for t in ("visualDay", "bandDay", "night")}
    json.dump(res, open(a.out, "w"), indent=1, default=str)
    print(res["P2verdict"], json.dumps(res["minima"]), json.dumps({k: v["readiness"] for k, v in res["capabilities"].items()}))


def ev_n(rows, key):
    if not rows: return {"all": {"medAE": None}, "AL": {}}
    f = lambda s: {"n": len(s), "medAE": round(float(np.median([abs(r[key] - r["secchi"]) for r in s])), 2) if s else None,
                   "MAE": round(float(np.mean([abs(r[key] - r["secchi"]) for r in s])), 2) if s else None}
    return {"all": f(rows), "AL": f([r for r in rows if r.get("state") == "AL"])}


def rows_from_national(path):
    """A fresh national read-out CSV (Stage 8 fresh_confirm format: id, state, secchi_ft, fnu_prod, rho_*_v, sun_elev)."""
    best = {}
    for r in csv.DictReader(open(path)):
        if r.get("error") or int(num(r.get("n_valid")) or 0) < 5 or not r.get("rho_rededge1_v"):
            continue
        k = (abs(int(r["dt_days"])), -int(num(r["n_valid"])))
        if r["id"] not in best or k < best[r["id"]][0]:
            best[r["id"]] = (k, r)
    out = []
    for _, r in best.values():
        raw = {"blue": num(r["rho_blue_v"]), "green": num(r["rho_green_v"]), "red": num(r["rho_red_v"]), "re1": num(r["rho_rededge1_v"])}
        x = {"state": r["state"], "secchi": float(r["secchi_ft"]), "C0": models.champion(num(r["fnu_prod"]))}
        x["P2"] = P2.route(raw, num(r["sun_elev"]), num(r.get("rho_swir16_v")))["ft"]
        if x["C0"] is not None:
            out.append(x)
    return out


if __name__ == "__main__":
    main()
