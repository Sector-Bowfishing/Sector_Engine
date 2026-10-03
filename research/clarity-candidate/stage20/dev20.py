"""Stage 20 PREREGISTRATION section 8: the Stage 19 causal consensus (stage19/dev19.py, executed verbatim) with S2C at
FULL authority. Only these edits, each asserted to hit its target exactly:
  (a) S2C prior passes and S2C anchors are predicted from RAW ACOLITE + the frozen Stage 20 correction (harm20.json);
      S2C scenes on a baseline other than N0511/N0512 are dropped; fold models are trained exactly as in Stage 19;
  (b) S2C scenes count as full-authority platforms (consensus, agreement, prior state, guard, diagnostics);
  (c) S2C anchors' Stage 16 product is re-issued without the S2C lower-authority line, from the corrected prediction
      (fold posteriors POST[k] exactly as dev16/dev19);
  windows 5, 10, 15 (PRIMARY = all three); outputs to stage20/dev20*.json (Stage 19 files untouched).
Then section 8 reporting: availability before/after, Strong detail, comparison with the Stage 19 result.
  python dev20.py"""
import json, os, sys, hashlib
S = os.environ["CLARITY_RESEARCH_ROOT"]
DRY = bool(os.environ.get("DRY20"))
F = json.load(open(f"{S}/stage20/FREEZE_STAGE20.json"))
for k, p in (("prereg_sha256", "PREREGISTRATION_STAGE20.md"), ("srf20_sha256", "srf20.json"), ("harm20_sha256", "harm20.json")):
    if DRY and k not in F: continue
    assert hashlib.sha256(open(f"{S}/stage20/{p}", "rb").read()).hexdigest() == F[k], p
src = open(f"{S}/stage19/dev19.py").read()
PATCH = [
    # loaders: L1C per sample; Stage 20 correction + raw anchors
    ('P = {}\n', 'P = {}; L1C = {}\nimport sys as _s; _s.path.insert(0, f"{S}/stage20"); import lib20 as L20\n'
     'H20J = json.load(open(f"{S}/stage20/harm20.json")); SEL20 = H20J["selected"]\n'
     'C20 = {"C0": L20.c_none, "C1": L20.c_sbaf, "C2": L20.c_param(H20J["C2"]), "C3": L20.c_param(H20J["C3"])}[SEL20]\n'
     'COVERED = ("N0511", "N0512")\n'
     'def H20(a, platform, l1c):\n'
     '    if platform != "sentinel-2c": return a\n'
     '    if not l1c or l1c.split("_")[3] not in COVERED: return None\n'
     '    return C20(a)\n', 1),
    ('for k, p in (c.get("points") or {}).items(): P[k] = p\n', 'for k, p in (c.get("points") or {}).items(): P[k] = p; L1C[k] = r.get("l1c")\n', 1),
    ('        a = harm(dict(a), n["platform"]); F, q = features(a, n["sun_elev"])\n',
     '        a = H20(dict(a), n["platform"], L1C.get(f"{cid}#{n[\'item\']}"))\n        if a is None: continue\n        F, q = features(a, n["sun_elev"])\n', 1),
    ('def anchor_x(cid):\n    x = TT.get(cid)\n    return [x["F"][k] for k in L.FEATS6 + ["F_kd"]] if x else None\n',
     'R12 = {x["id"]: x for x in json.load(open(f"{S}/stage12/analysis/rows12.json"))}\nT2RAW = {}\n'
     'for _f in glob.glob(f"{S}/stage13/coverage/res/*.json"):\n'
     '    for _c in json.load(open(_f)).get("crops", []):\n'
     '        for _pid, _p in (_c.get("points") or {}).items(): T2RAW[_pid] = _p\n'
     'AF20 = {}\n'
     'def anchor_x(cid):\n    x = TT.get(cid)\n    if not x: return None\n'
     '    if x["platform"] != "sentinel-2c": return [x["F"][k] for k in L.FEATS6 + ["F_kd"]]\n'
     '    raw = R12[cid]["aco_raw"] if x["tier"] == 1 else T2RAW[cid]["M3"]\n'
     '    Fx, _ = features(C20(dict(raw)), x["sun_elev"]); AF20[cid] = Fx\n'
     '    return [Fx[k] for k in L.FEATS6 + ["F_kd"]]\n', 1),
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
     '    o2 = _p16(e["tier"], PRED[key]["anchor"], "sentinel-2a", AF20[e["id"]]["F_ndci"], None, R); o2["s2c"] = False; o2["s2c_full20"] = True; return o2\n'
     'def strong(o):\n', 1),
    # windows and outputs
    ('WIN19 = [3, 5, 7, 10, 15]; PRIMARY = [3, 5, 7, 10]', 'WIN19 = [5, 10, 15]; PRIMARY = [5, 10, 15]', 1),
    ('f"{S}/stage19/dev19_rows.json"', 'f"{S}/stage20/dev20_rows.json"', 1),
    ('f"{S}/stage19/dev19.json"', 'f"{S}/stage20/dev20.json"', 1),
]
for old, new, n in PATCH:
    c = src.count(old); assert c == n, (c, n, old[:80])
    src = src.replace(old, new)
assert "stage19/dev19.json\"" not in src and "stage19/dev19_rows" not in src
# section 8 reporting, appended
src += r'''
# ======================= Stage 20 section 8 reporting
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
rep["n_strong_passes_per_strong"] = None
json.dump(rep, open(f"{S}/stage20/dev20_report.json", "w"), indent=1, default=str)
print("STAGE20 REPORT", json.dumps({W: {"bal": v["summary"]["bal"], "harm": v["summary"]["harm"], "sev": v["summary"]["sev"], "zero_before": v["before_s2ab_only"]["none"], "zero_after": v["after_with_s2c"]["none"]} for W, v in rep["windows"].items()}))
'''
if DRY: print("patches ok", len(PATCH)); sys.exit()
exec(compile(src, "dev20(dev19 patched)", "exec"))
