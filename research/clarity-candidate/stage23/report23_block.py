
# ======================= Stage 23 sections 10-17 reporting (appended to the patched dev19 by dev23.py; same namespace)
import json as _json
IQ23 = E14["interval_q"]; ERA = "2025-01-21"
era = lambda cid: (corp.get(cid, {}).get("date") or "") >= ERA
def okey(e): return (e["id"], "outer", e["fold"])
EV = {e["id"]: e for e in EVENTS}
# ---- Stage 16 single scene with Stage 12 retired (S2C anchors on C3), this mode's authority
A16 = []
for e in EVENTS:
    key = okey(e)
    if key not in PRED: continue
    o = base23(e, key); sc_, oc, h, sv = op_score(o, e["c"], e["secchi"])
    ev_ = "unavailable" if o["state"] not in CONTAINS else "weak" if o["authority"] == "lower" else ("strong" if (o.get("conf") or 0) >= 0.90 and e["tier"] == 1 and not o.get("s2c") and not o.get("algal") else "moderate")
    A16.append({"id": e["id"], "lake": e["lake"], "c": e["c"], "y": e["y"], "secchi": e["secchi"], "tier": e["tier"], "platform": e["platform"], "fold": e["fold"], "o": o,
                "score": sc_, "outcome": oc, "harmful": h, "severe": sv, "ev": ev_, "insitu_type": e["insitu_type"], "turb": e["turb"]})
SA16 = summarize(A16); SA16.update(extra(A16))
Wsel = SEL if SEL else WIN19[0]; ROWS23 = Crows
def used(r, W):
    e = EV[r["id"]]; return [s for s in scene_list(e, okey(e), W, "H0", "S-off") if FA(s)]
# ---- section 10: evidence density (independent prior full-authority views), before (S2A/B) and after (+ S2C >= 25 with a valid C3 sample)
def density(W, with_s2c, ev_filter=None):
    ev = [e for e in EVENTS if ev_filter is None or ev_filter(e["id"])]
    v = [sum(1 for n in NB.get(e["id"], []) if n["age"] <= W and (n["platform"] != "sentinel-2c" or (with_s2c and (n.get("sun") or 0) >= LOWSUN))) for e in ev]
    return {"n_events": len(ev), "dist": {str(m) if m < 3 else "3+": sum(1 for x in v if min(3, x) == m) / len(ev) for m in range(4)}, "at_least_one": sum(1 for x in v if x >= 1) / len(ev)}
dens = {str(W): {"all_before": density(W, False), "all_after": density(W, True), "era_before": density(W, False, era), "era_after": density(W, True, era)} for W in sorted(set(WIN19) | {5, 10, 15})}
ages, plat = [], collections.Counter()
for r in ROWS23:
    if not (r["o"].get("consensus") and r["o"].get("n_use", 0) >= 1): continue
    for s in used(r, Wsel):
        plat[s["platform"]] += 1
        if not s["anchor"]: ages.append(s["adt"])
tot = sum(plat.values()) or 1
# ---- section 11: Strong
def strong_by_class(rows):
    out = {}
    for k, n in enumerate(CLASSES):
        sub = [r for r in rows if r["c"] == k and r["ev"] != "unavailable"]; st = [r for r in sub if r["ev"] == "strong"]
        out[n] = {"usable": len(sub), "strong_share": len(st) / len(sub) if sub else None, "strong_acc": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in st])) if st else None}
    return out
nsup = []
for r in ROWS23:
    if r["ev"] != "strong": continue
    e = EV[r["id"]]; k = e["fold"]
    nsup.append(sum(1 for s in used(r, Wsel) if scene_state(s, POST[k]) and CONTAINS[scene_state(s, POST[k])] >= CONTAINS[r["o"]["state"]]))
# ---- section 12: stained
pv = lambda r: r["o"].get("p") if r["o"].get("p") is not None else bmap[r["id"]].get("p")
def stained(rows):
    st = [r for r in rows if r["c"] == 2]; sh = [r for r in st if shown(r["o"]) and pv(r) is not None]; x = extra(rows)["stained"]
    x["median_log10_feet_error"] = float(np.median([abs(pv(r) - r["y"]) for r in sh])) if sh else None; x["feet_shown_share"] = len(sh) / len(st) if st else None
    return x
pr_ = [{"id": r["id"], "lake": bmap[r["id"]]["lake"], "c": r["c"]} for r in ROWS23]
m23 = {r["id"]: r for r in ROWS23}; m16 = {r["id"]: r for r in A16}
def dst(x): ids = [r["id"] for r in x if r["c"] == 2]; return float(np.mean([m23[i]["score"] for i in ids]) - np.mean([m16[i]["score"] for i in ids]))
stained_vs16 = {"diff": dst(pr_), "ci95": lake_boot_diff(pr_, dst, B=2000, seed=23)}
# ---- section 13: harmful taxonomy (diagnostic only)
def cats(r, W):
    e = EV[r["id"]]; o = r["o"]; st = o["state"]; C = CONTAINS.get(st, set()); k = e["fold"]; out = set()
    if C:
        if r["c"] < min(C): out.add("too_murky")
        if r["c"] > max(C): out.add("too_clear")
        if len(C) == 2: out.add("boundary_state")
    if abs(int(corp[r["id"]].get("dt") or 0)) >= 3: out.add("stale_anchor")
    sc = used(r, W) if o.get("consensus") else []
    a = [s for s in sc if s["anchor"]]; sa = scene_state(a[0], POST[k]) if a else None
    if sa and any((not s["anchor"]) and s["adt"] >= 3 and scene_state(s, POST[k]) and not (CONTAINS[scene_state(s, POST[k])] & CONTAINS[sa]) for s in sc): out.add("stale_prior_disagreement")
    if (e["platform"] == "sentinel-2c" and (ASUN.get(r["id"]) or 0) < LOWSUN) or any(s["platform"] == "sentinel-2c" and (s.get("sun") or 0) < LOWSUN for s in sc): out.add("low_sun_s2c")
    if o.get("algal"): out.add("algae_flagged")
    if r["tier"] == 2: out.add("tier2")
    if not o.get("consensus") or o.get("n_use", 1) <= 1: out.add("single_scene")
    if o.get("consensus") and (o.get("disjoint") or o.get("agree", 0) < o.get("n_use", 0)): out.add("multi_scene_disagreement")
    cf_ = o.get("conf")
    if cf_ is not None and cf_ >= 0.90: out.add("high_posterior_wrong" if r["harmful"] else "high_posterior")
    if cf_ is not None and cf_ < 0.70: out.add("low_posterior")
    if cf_ is None and C: out.add("posterior_unavailable")
    return out
def taxonomy(rows, W):
    ans = [r for r in rows if r["o"]["state"] in CONTAINS]; H = [r for r in rows if r["harmful"]]; CH = {r["id"]: cats(r, W) for r in ans}
    names = ["too_murky", "too_clear", "boundary_state", "stale_anchor", "stale_prior_disagreement", "low_sun_s2c", "algae_flagged", "tier2", "single_scene", "multi_scene_disagreement", "high_posterior_wrong", "low_posterior", "posterior_unavailable"]
    out = {"n_rows": len(rows), "n_answered": len(ans), "n_harmful": len(H), "categories": {}}
    for nm in names:
        hn = sum(1 for r in H if nm in CH[r["id"]]); pop = sum(1 for r in ans if (nm in CH[r["id"]]) or (nm == "high_posterior_wrong" and "high_posterior" in CH[r["id"]]))
        out["categories"][nm] = {"harmful_n": hn, "share_of_harmful": hn / len(H) if H else None, "population": pop, "harmful_rate_in_population": hn / pop if pop else None}
    top = sorted([(v["harmful_n"], k) for k, v in out["categories"].items() if k not in ("too_murky", "too_clear")], reverse=True)[:3]
    out["direction"] = {"too_murky": out["categories"]["too_murky"]["harmful_n"], "too_clear": out["categories"]["too_clear"]["harmful_n"]}
    out["top_causes"] = [k for n, k in top]
    return out
tax = taxonomy(ROWS23, Wsel)
# ---- section 14: severe audit
def severe_audit(rows, W):
    out = []
    for r in rows:
        if not r["severe"]: continue
        e = EV[r["id"]]; o = r["o"]; sc = used(r, W) if o.get("consensus") else []
        out.append({"id": r["id"], "lake": r["lake"], "truth_class": CLASSES[r["c"]], "secchi_ft": r["secchi"], "answer": o["state"], "answer_ft": (10 ** pv(r)) if pv(r) is not None else None,
                    "scene_age_days": abs(int(corp[r["id"]].get("dt") or 0)), "satellite": r["platform"], "authority": o["authority"], "evidence": r["ev"], "algal": o.get("algal"),
                    "posterior": o.get("conf"), "tier": r["tier"], "independent_passes": max(1, o.get("n_use", 1)) if o.get("consensus") else 1,
                    "s2c_participated": e["platform"] == "sentinel-2c" or any(s["platform"] == "sentinel-2c" for s in sc), "sun": ASUN.get(r["id"]),
                    "removed_by_strong_only": r["ev"] != "strong", "removed_by_unknown_below_0.70": (o.get("conf") is not None and o["conf"] < 0.70)})
    return out
sev_a = severe_audit(ROWS23, Wsel)
# ---- section 15: exact feet
def feet(rows):
    sh = [r for r in rows if shown(r["o"]) and pv(r) is not None]
    def blk(x):
        if not x: return {"n": 0}
        e_ = [pv(r) - r["y"] for r in x]
        return {"n": len(x), "multiplicative_error_median": float(10 ** np.median(np.abs(e_))), "signed_bias_log10_median": float(np.median(e_)),
                "interval_coverage": float(np.mean([pv(r) + IQ23[0] <= r["y"] <= pv(r) + IQ23[1] for r in x]))}
    out = {"availability": len(sh) / len(rows), "all": blk(sh), "by_class": {n: blk([r for r in sh if r["c"] == k]) for k, n in enumerate(CLASSES)},
           "by_evidence": {ev_: blk([r for r in sh if r["ev"] == ev_]) for ev_ in ("strong", "moderate", "weak")}}
    return out
SUMM23 = SUM19[Ckey] if Ckey in SUM19 else summarize(ROWS23); SUMM23.update(extra(ROWS23))
cap = out["exact_feet_capability"]["C"]
rep = {"mode": MODE23, "selected_window": SEL, "engine_key": str(Ckey), "summary": SUMM23, "stage16_c3": SA16, "drops": DROP23,
       "s2c_anchors": {"n": sum(1 for e in EVENTS if e["platform"] == "sentinel-2c"), "with_c3": len(AF23), "sun_ge25": sum(1 for c in AF23 if (ASUN.get(c) or 0) >= LOWSUN)},
       "density": dens, "support": {"median_age_supporting_prior_days": float(np.median(ages)) if ages else None, "platform_share": {k: v / tot for k, v in plat.items()}},
       "strong": {"share": SUMM23["strong_share_usable"], "acc": SUMM23["strong_acc"], "n": SUMM23["n_strong"], "median_supporting_passes": float(np.median(nsup)) if nsup else None,
                  "by_class": strong_by_class(ROWS23), "detail": out["strong_detail"].get(str(Wsel))},
       "stained": {"stage16_c3": stained(A16), "this": stained(ROWS23), "vs_stage16_c3": stained_vs16},
       "harmful_taxonomy": tax, "severe_audit": sev_a, "exact_feet": {"capability": cap, "this": feet(ROWS23), "stage16_c3": feet(A16)},
       "bars": {"stage16": bars(SUMM23), "dev9": dev9(SUMM23)}}
_json.dump(A16, open(f"{S}/stage23/dev23_{MODE23}_stage16c3_rows.json", "w"), default=str)
_json.dump(rep, open(f"{S}/stage23/dev23_{MODE23}_report.json", "w"), indent=1, default=str)
print("STAGE23", MODE23, "selected", SEL, fmt(SUMM23), "| stage16-c3", fmt(SA16), "| exact feet", cap, "| drops", DROP23)
print("  density 5d era before/after", dens["5"]["era_before"]["dist"], dens["5"]["era_after"]["dist"], "| top harmful causes", tax["top_causes"], tax["direction"], "| severe", len(sev_a))
