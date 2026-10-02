"""Stage 18P freeze: the adopted physical-pass consensus (M-iuw, +-10 d, <= 3 independent passes, no rain rule, S2C off).
Production parameters pooled from the DEVELOPMENT lake-held-out predictions only, exactly as stage18/freeze18.py did for
the item-based challenger: sigma by tier from anchor residuals, kappa from anchor-neighbour pairs of independent passes,
n=2 / n>=3 posteriors from the outer-fold consensus predictions. Writes engine/candidate18p.json and updates
FREEZE_STAGE18P.json. No refit of the C-gbm; no Secchi value outside development."""
import json, hashlib, datetime, sys, numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"]
src = open(f"{S}/stage18p/dev18p.py").read().split("RES = {}")[0]
sys.argv = ["dev18p.py"]; ns = {"__name__": "freeze18p"}; exec(compile(src, "dev18p_prefix", "exec"), ns)
PRED, NB, EVENTS, corp, fit_post, build = ns["PRED"], ns["NB"], ns["EVENTS"], ns["corp"], ns["fit_post"], ns["build"]
an = [(PRED[(e["id"], "outer", e["fold"])]["anchor"], e["y"], e["tier"]) for e in EVENTS if PRED[(e["id"], "outer", e["fold"])]["anchor"] is not None and e["tier"] in (1, 2)]
mad = lambda r: 1.4826 * float(np.median(np.abs(np.array(r) - np.median(r))))
sig = {t: mad([y - p for p, y, tt in an if tt == t]) for t in (1, 2)}
dd, sep = [], []
for e in EVENTS:
    pr = PRED[(e["id"], "outer", e["fold"])]
    if pr["anchor"] is None or e["tier"] not in (1, 2): continue
    for n, p in zip(NB.get(e["id"], []), pr["nb"]): dd.append((p - pr["anchor"]) ** 2); sep.append(abs(n["dt"]) + abs(int(corp[e["id"]].get("dt") or 0)))
coef = np.linalg.lstsq(np.vstack([np.ones(len(sep)), sep]).T, np.array(dd), rcond=None)[0]
kappa = max(0.0, float(coef[1]))
ys = [e["y"] for e in EVENTS]
par = {"sig": sig, "kappa": kappa, "mu0": float(np.mean(ys)), "s0": float(np.std(ys))}
R16 = json.load(open(f"{S}/stage16/engine/rule16.json"))
post = {"post1": {int(b): tuple(v) for b, v in R16["post1"].items()}, "post2": {int(b): tuple(v) for b, v in R16["post2"].items()}}
grp = {"n2": [], "n3": []}
for e in EVENTS:
    o = build(e, (e["id"], "outer", e["fold"]), "M-iuw", 10, "H0", "S-off", par, post, {})
    if o.get("consensus") and o.get("n_use", 1) >= 2: grp["n2" if o["n_use"] == 2 else "n3"].append((o["p"], e["y"]))
cal = {g: {str(b): list(v) for b, v in fit_post(rows).items()} for g, rows in grp.items()}
CH = {"engine": "Stage 18P candidate: inverse-uncertainty weighting of frozen C-gbm scene predictions over +-10 days, up to 3 physically independent passes, no rain rule, S2C off",
      "physical_pass": "(platform, UTC sensing date); one representative item per pass (most valid Sen2Cor pixels, then lowest scene cloud, then item id); the anchor's own pass is never a neighbour",
      "scene_predictor": "stage14/engine/frozen_gbm.pkl (unchanged)", "scene_path": "stage14/cert/run_cert_aco_a1.py (unchanged)",
      "neighbours": "<= 3 nearest independent passes (production gates, >= 5 px) within +-10 days; tiers 1-2 only; S2C excluded",
      "sigma_tier": sig, "kappa_per_day": kappa, "kappa_unclipped": float(coef[1]), "posteriors_n2": cal.get("n2"), "posteriors_n3": cal.get("n3"),
      "n_calibration": {g: len(v) for g, v in grp.items()}, "n_pairs": len(dd),
      "gate": {"t1": R16["t1"], "t2": R16["t2"], "tier2_only": "boundary-only (Stage 16)"}, "fallback": "Stage 16 product when no full-authority scene contributes",
      "strong_rule": ">= 2 compatible full-authority scenes from different physical passes whose states contain the answer, none disjoint, posterior >= 0.90",
      "status": "UNCERTIFIED development candidate (Stage 18P adoption rule passed); not deployed"}
import os; os.makedirs(f"{S}/stage18p/engine", exist_ok=True)
json.dump(CH, open(f"{S}/stage18p/engine/candidate18p.json", "w"), indent=1)
F = json.load(open(f"{S}/stage18p/FREEZE_STAGE18P.json"))
h = lambda p: hashlib.sha256(open(f"{S}/{p}", "rb").read()).hexdigest()
F["candidate_frozen_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
for p in ["stage18p/dev18p.py", "stage18p/dev18p.json", "stage18p/post18p.json", "stage18p/freeze18p.py", "stage18p/engine/candidate18p.json"]: F["files"][p] = h(p)
json.dump(F, open(f"{S}/stage18p/FREEZE_STAGE18P.json", "w"), indent=1)
print(json.dumps({k: CH[k] for k in ("sigma_tier", "kappa_per_day", "kappa_unclipped", "n_calibration", "n_pairs")}), F["candidate_frozen_utc"])
