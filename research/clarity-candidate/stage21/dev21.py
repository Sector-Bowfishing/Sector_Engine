"""Stage 21 PREREGISTRATION section 7: the Stage 19 causal consensus (stage19/dev19.py, executed verbatim) with S2C as
FULL-authority evidence, using the Stage 21 corrected S2C re-runs (res_s2c21 K1 = frozen pre-ACOLITE offsets, + the B05
band adjustment = K2). Built from stage20/dev20.py's patches; the edits, each asserted to hit its target exactly:
  (a) S2C prior passes and S2C anchors are predicted from the K2 samples; an S2C scene without a valid K2 sample is
      dropped; the Stage 12 path is used for no S2C scene; fold models are trained exactly as in Stage 19;
  (b) S2C scenes count as full-authority platforms (consensus, agreement, prior state, guard, diagnostics);
  (c) S2C anchors' Stage 16 product is re-issued without the S2C lower-authority line, from the K2 prediction
      (fold posteriors POST[k] exactly as dev16/dev19);
  windows 5, 10, 15 (PRIMARY = all three); outputs to stage21/dev21*.json (Stage 19 and 20 files untouched).
Then the section 7 reporting (availability and Strong, all events and 2025-26 events; adoption rule).
  python dev21.py"""
import json, os, sys, hashlib
S = os.environ["CLARITY_RESEARCH_ROOT"]
DRY = bool(os.environ.get("DRY21"))
F = json.load(open(f"{S}/stage21/FREEZE_STAGE21.json"))
for k, p in (("prereg_sha256", "PREREGISTRATION_STAGE21.md"), ("corr21_sha256", "corr21.json")):
    if DRY and k not in F: continue
    assert hashlib.sha256(open(f"{S}/stage21/{p}", "rb").read()).hexdigest() == F[k], p
src = open(f"{S}/stage19/dev19.py").read()
PATCH = [
    # loaders: L1C per sample; Stage 20 correction + raw anchors
    ('P = {}\n', 'P = {}; L1C = {}\nimport sys as _s; _s.path.insert(0, f"{S}/stage20"); import lib20 as L20\n'
     'B5J = json.load(open(f"{S}/stage21/corr21.json"))["b05_l2w"]; K2F = L20.c_param({"B05": {"g": B5J["g"], "k": B5J["k"]}})\n'
     'SEL20 = "K2 (Stage 21: pre-ACOLITE offsets + B05 band adjustment)"; COVERED = ("N0511", "N0512", "N0513")\n'
     'RS21 = {}\n'
     'for _f in glob.glob(f"{S}/stage21/res_s2c21/K1_*.json"):\n'
     '    for _c in json.load(open(_f)).get("crops", []):\n'
     '        for _k, _p in (_c.get("points") or {}).items(): RS21[_k] = _p\n'
     'def S21(key):\n'
     '    p = RS21.get(key) or {}\n'
     '    return L20.pick(p.get("M0"), p.get("M3"))\n'
     'AT21 = {}\n', 1),
    ('for k, p in (c.get("points") or {}).items(): P[k] = p\n', 'for k, p in (c.get("points") or {}).items(): P[k] = p; L1C[k] = r.get("l1c")\n', 1),
    ('        a = harm(dict(a), n["platform"]); F, q = features(a, n["sun_elev"])\n',
     '        if n["platform"] == "sentinel-2c":\n'
     '            tier, a = S21(f"{cid}#{n[\'item\']}")\n'
     '            if tier is None: continue\n'
     '            a = K2F(dict(a))\n'
     '        F, q = features(a, n["sun_elev"])\n', 1),
    ('def anchor_x(cid):\n    x = TT.get(cid)\n    return [x["F"][k] for k in L.FEATS6 + ["F_kd"]] if x else None\n',
     'AF20 = {}\n'
     'def anchor_x(cid):\n    x = TT.get(cid)\n    if not x: return None\n'
     '    if x["platform"] != "sentinel-2c": return [x["F"][k] for k in L.FEATS6 + ["F_kd"]]\n'
     '    tier, a = S21(cid)\n'
     '    if tier is None: return None\n'
     '    AT21[cid] = tier; Fx, _ = features(K2F(dict(a)), x["sun_elev"]); AF20[cid] = Fx\n'
     '    return [Fx[k] for k in L.FEATS6 + ["F_kd"]]\n', 1),
    ('        out.append({"p": pr["anchor"], "tier": e["tier"], "platform": e["platform"], "adt": 0, "anchor": True})\n',
     '        out.append({"p": pr["anchor"], "tier": AT21.get(cid, e["tier"]), "platform": e["platform"], "adt": 0, "anchor": True})\n', 1),
    # (b) S2C as a full-authority platform
    ('    full = [s for s in sc if s["platform"] != "sentinel-2c"]\n', '    full = list(sc)\n', 1),
    ('(s["platform"] != "sentinel-2c" or smode == "S-agree")', 'True', 2),
    ('if not s["anchor"] and s["platform"] != "sentinel-2c"]', 'if not s["anchor"]]', 1),
    ('if not a or e["platform"] == "sentinel-2c" or not o.get("consensus"): return o', 'if not a or not o.get("consensus"): return o', 1),
    ('        sc = [s for s in scene_list(e, key, W, "H0", "S-off") if s["platform"] != "sentinel-2c"]\n', '        sc = scene_list(e, key, W, "H0", "S-off")\n', 1),
    ('if r["tier"] not in (1, 2) or r["platform"] == "sentinel-2c" or b["o"]["state"] not in CONTAINS', 'if r["tier"] not in (1, 2) or b["o"]["state"] not in CONTAINS', 1),
    # (c) S2C anchors' Stage 16 product at full authority (fold posteriors)
    ('    base = B16[e["id"]]["o"]\n    sc = scene_list(e, key, W, H, smode)\n',
     '    base = base20(e, key)\n    sc = scene_list(e, key, W, H, smode)\n', 1),
    ('def strong(o):\n',
     'from lib16 import product16 as _p16\n'
     'def base20(e, key):\n'
     '    o = B16[e["id"]]["o"]\n'
     '    if e["platform"] != "sentinel-2c" or e["tier"] not in (1, 2) or PRED[key]["anchor"] is None: return o\n'
     '    k = key[2]; R = {**POST[k], "t1": T1G, "t2": T2G, "t2opt": R16["t2opt"], "tier3_allowed": E14["tier3_allowed_states"]}\n'
     '    o2 = _p16(AT21.get(e["id"], e["tier"]), PRED[key]["anchor"], "sentinel-2a", AF20[e["id"]]["F_ndci"], None, R); o2["s2c"] = False; o2["s2c_full21"] = True; return o2\n'
     'def strong(o):\n', 1),
    # windows and outputs
    ('WIN19 = [3, 5, 7, 10, 15]; PRIMARY = [3, 5, 7, 10]', 'WIN19 = [5, 10, 15]; PRIMARY = [5, 10, 15]', 1),
    ('f"{S}/stage19/dev19_rows.json"', 'f"{S}/stage21/dev21_rows.json"', 1),
    ('f"{S}/stage19/dev19.json"', 'f"{S}/stage21/dev21.json"', 1),
]
for old, new, n in PATCH:
    c = src.count(old); assert c == n, (c, n, old[:80])
    src = src.replace(old, new)
assert "stage19/dev19.json\"" not in src and "stage19/dev19_rows" not in src
# section 8 reporting, appended
src += r'''
# ======================= Stage 21 section 7 reporting
S19 = json.load(open(f"{S}/stage19/dev19.json")); R19 = {r["id"]: r for r in json.load(open(f"{S}/stage19/dev19_rows.json"))}
def zero_prior(W, with_s2c):
    v = [sum(1 for n in NB.get(e["id"], []) if n["age"] <= W and (with_s2c or n["platform"] != "sentinel-2c")) for e in EVENTS]
    return {"none": sum(1 for x in v if x == 0) / len(v), "dist": {str(m): sum(1 for x in v if min(3, x) == m) / len(v) for m in range(4)}}
rep = {"selected_correction": SEL20, "covered_baselines": list(COVERED), "windows": {}}
for W in WIN19:
    rep["windows"][str(W)] = {"summary": SUM19[W], "before_s2ab_only": zero_prior(W, False), "after_with_s2c": zero_prior(W, True),
                              "s2c_scenes_used": sum(r["o"].get("s2c_used", 0) for r in RES19[W]),
                              "events_with_s2c_scene": sum(1 for e in EVENTS if any(n["platform"] == "sentinel-2c" and n["age"] <= W for n in NB.get(e["id"], [])) or (e["platform"] == "sentinel-2c" and e["tier"] in (1, 2)))}
rep["stage19_reference_5d"] = S19["C_causal"]["5"]; rep["stage19_selected"] = S19.get("selected_window")
sel_rows = RES19[Ckey]; rep["selected_window"] = SEL; rep["engine_key"] = str(Ckey)
rep["vs_stage19_5d"] = boot(sel_rows, list(R19.values()))
rep["s2c_anchor_rows"] = {"n": sum(1 for r in sel_rows if r["platform"] == "sentinel-2c"), "summary": summarize([r for r in sel_rows if r["platform"] == "sentinel-2c"]) if any(r["platform"] == "sentinel-2c" for r in sel_rows) else None,
                          "stage19_summary": summarize([r for r in R19.values() if r["platform"] == "sentinel-2c"]) if any(r["platform"] == "sentinel-2c" for r in R19.values()) else None}
rep["strong_detail_selected"] = out["strong_detail"].get(str(SEL if SEL else 10))
corp21 = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
era = lambda e: corp21[e["id"]]["date"] >= "2025-01-21"
def zero_era(W, with_s2c):
    ev = [e for e in EVENTS if era(e)]
    v = [sum(1 for n in NB.get(e["id"], []) if n["age"] <= W and (with_s2c or n["platform"] != "sentinel-2c")) for e in ev]
    return {"n_events": len(ev), "none": sum(1 for x in v if x == 0) / len(ev)}
def strong_share(rows):
    u = [r for r in rows if r["ev"] != "unavailable"]; st = [r for r in rows if r["ev"] == "strong"]
    return {"n": len(rows), "usable": len(u), "strong_share": len(st) / len(u) if u else 0, "strong_acc": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in st])) if st else None}
Wsel = SEL if SEL else 10
rep["era_2025_26"] = {"zero_before": zero_era(Wsel, False), "zero_after": zero_era(Wsel, True),
                      "strong_stage19_5d": strong_share([r for r in R19.values() if corp21[r["id"]]["date"] >= "2025-01-21"]),
                      "strong_stage21": strong_share([r for r in sel_rows if corp21[r["id"]]["date"] >= "2025-01-21"])}
for W in WIN19:
    rep["windows"][str(W)]["era_zero_before"] = zero_era(W, False); rep["windows"][str(W)]["era_zero_after"] = zero_era(W, True)
E_ = rep["era_2025_26"]
rep["material"] = {"zero_prior_lower_by_5pts": (E_["zero_before"]["none"] - E_["zero_after"]["none"]) >= 0.05,
                   "strong_raised_2pts_acc90": (E_["strong_stage21"]["strong_share"] - E_["strong_stage19_5d"]["strong_share"]) >= 0.02 and (E_["strong_stage21"]["strong_acc"] or 0) >= 0.90}
S5 = S19["C_causal"]["5"]; SS = SUM19[Wsel]
rep["adopt"] = bool(SEL and bars(SS) and SS["harm"] <= S5["harm"] + 0.01)
json.dump(rep, open(f"{S}/stage21/dev21_report.json", "w"), indent=1, default=str)
print("STAGE21 REPORT", json.dumps({"selected": SEL, "adopt": rep["adopt"], "material": rep["material"], "era": {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk in ("none", "strong_share", "strong_acc", "n_events", "usable")}) for k, v in E_.items()},
      "windows": {W: {"bal": v["summary"]["bal"], "harm": v["summary"]["harm"], "sev": v["summary"]["sev"], "zero_before": v["before_s2ab_only"]["none"], "zero_after": v["after_with_s2c"]["none"]} for W, v in rep["windows"].items()}}))
'''
if DRY: print("patches ok", len(PATCH)); sys.exit()
exec(compile(src, "dev21(dev19 patched)", "exec"))
