"""Stage 23 PREREGISTRATION section 9: the Stage 19 causal consensus (stage19/dev19.py, executed verbatim) with the stage21/dev21.py
pattern of asserted patches, changed only in that:
  (a) S2C anchors and prior passes are predicted from their C3 samples (stage22 res22_truth C1 + the re-run _res_syke row, then the
      B05 band adjustment); an S2C scene without a valid C3 sample is dropped (an S2C tier-1/2 anchor without one is Unknown);
      fold models are trained exactly as in Stage 19;
  (b) MODE23=R1: S2C scenes with sun >= 25 deg are full-authority platforms (consensus, agreement, prior state, guard, Strong
      support, diagnostics); S2C < 25 deg stays excluded exactly as Stage 19 excluded all S2C (S-off).
      MODE23=R0 (the Stage 22 live-development reference): every S2C scene excluded (Stage 19), S2C anchors on C3 lower authority;
  (c) S2C anchors' Stage 16 product: R1 and sun >= 25 -> full authority from the C3 prediction (fold posteriors, as dev21 base20);
      otherwise the C3 lower-authority product (product16 with platform sentinel-2c); tier-3/0 anchors keep their Stage 16 product;
  (d) windows: R1 5/10/15 (all primary, Stage 19 selection rule); R0 5 only;
  (e) no future scene (the age >= 0 assertion is kept); exact feet use the C3 prediction for S2C single-scene rows.
Then the section 10-15 reporting (appended). Writes stage23/dev23_<MODE>.json, dev23_<MODE>_rows.json, dev23_<MODE>_report.json.
  MODE23=R0 python dev23.py ; MODE23=R1 python dev23.py   (R1 only after decide23.json records outcome A)"""
import json, os, sys, hashlib
S = os.environ["CLARITY_RESEARCH_ROOT"]; MODE = os.environ["MODE23"]; assert MODE in ("R0", "R1")
DRY = bool(os.environ.get("DRY23"))
F = json.load(open(f"{S}/stage23/FREEZE_STAGE23.json"))
assert hashlib.sha256(open(f"{S}/stage23/PREREGISTRATION_STAGE23.md", "rb").read()).hexdigest() == F["prereg_sha256"]
if MODE == "R1" and not DRY:
    D = json.load(open(f"{S}/stage23/decide23.json")); assert D["outcome"] == "A", "the consensus runs only under outcome A"
src = open(f"{S}/stage19/dev19.py").read()
PATCH = [
    # (a) loaders: C3 samples, sun, full-authority predicate
    ('P = {}\n', 'P = {}\nimport sys as _s; _s.path.insert(0, f"{S}/stage20"); import lib20 as L20\n'
     'B5J = json.load(open(f"{S}/stage21/corr21.json"))["b05_l2w"]; C3F = L20.c_param({"B05": {"g": B5J["g"], "k": B5J["k"]}})\n'
     'MODE23 = __import__("os").environ["MODE23"]; LOWSUN = 25.0\n'
     'RS23 = {}\n'
     'for _f in sorted(glob.glob(f"{S}/stage22/res22_truth/*__C1.json")) + sorted(glob.glob(f"{S}/stage22/_res_syke/*__C1.json")):\n'
     '    for _c in json.load(open(_f)).get("crops", []):\n'
     '        for _k, _p in (_c.get("points") or {}).items(): RS23[_k] = _p\n'
     'def S23(key):\n'
     '    p = RS23.get(key) or {}\n'
     '    return L20.pick(p.get("M0"), p.get("M3"))\n'
     'AT23 = {}; AF23 = {}; ASUN = {}; DROP23 = {"prior_no_c3": 0}\n'
     'def FA(s):\n'
     '    return s["platform"] != "sentinel-2c" or (MODE23 == "R1" and (s.get("sun") or 0) >= LOWSUN)\n', 1),
    ('        a = harm(dict(a), n["platform"]); F, q = features(a, n["sun_elev"])\n',
     '        if n["platform"] == "sentinel-2c":\n'
     '            tier, a = S23(f"{cid}#{n[\'item\']}")\n'
     '            if tier is None: DROP23["prior_no_c3"] += 1; continue\n'
     '            a = C3F(dict(a))\n'
     '        F, q = features(a, n["sun_elev"])\n', 1),
    ('"age": n["age"], "pass_time": n["pass_time"]})\n', '"age": n["age"], "pass_time": n["pass_time"], "sun": n["sun_elev"]})\n', 1),
    ('def anchor_x(cid):\n    x = TT.get(cid)\n    return [x["F"][k] for k in L.FEATS6 + ["F_kd"]] if x else None\n',
     'def anchor_x(cid):\n    x = TT.get(cid)\n    if not x: return None\n    ASUN[cid] = x.get("sun_elev")\n'
     '    if x["platform"] != "sentinel-2c": return [x["F"][k] for k in L.FEATS6 + ["F_kd"]]\n'
     '    tier, a = S23(cid)\n'
     '    if tier is None: return None\n'
     '    AT23[cid] = tier; Fx, _ = features(C3F(dict(a)), x["sun_elev"]); AF23[cid] = Fx\n'
     '    return [Fx[k] for k in L.FEATS6 + ["F_kd"]]\n', 1),
    ('        out.append({"p": pr["anchor"], "tier": e["tier"], "platform": e["platform"], "adt": 0, "anchor": True})\n',
     '        out.append({"p": pr["anchor"], "tier": AT23.get(cid, e["tier"]), "platform": e["platform"], "adt": 0, "anchor": True, "sun": ASUN.get(cid)})\n', 1),
    ('        out.append({"p": p, "tier": n["tier"], "platform": n["platform"], "adt": n["age"], "anchor": False, "age": n["age"]})\n',
     '        out.append({"p": p, "tier": n["tier"], "platform": n["platform"], "adt": n["age"], "anchor": False, "age": n["age"], "sun": n.get("sun")})\n', 1),
    # (b) authority
    ('    full = [s for s in sc if s["platform"] != "sentinel-2c"]\n', '    full = [s for s in sc if FA(s)]\n', 1),
    ('(s["platform"] != "sentinel-2c" or smode == "S-agree")', 'FA(s)', 2),
    ('if not s["anchor"] and s["platform"] != "sentinel-2c"]', 'if not s["anchor"] and FA(s)]', 1),
    ('if not a or e["platform"] == "sentinel-2c" or not o.get("consensus"): return o', 'if not a or not FA(a[0]) or not o.get("consensus"): return o', 1),
    ('        sc = [s for s in scene_list(e, key, W, "H0", "S-off") if s["platform"] != "sentinel-2c"]\n', '        sc = [s for s in scene_list(e, key, W, "H0", "S-off") if FA(s)]\n', 1),
    ('if r["tier"] not in (1, 2) or r["platform"] == "sentinel-2c" or b["o"]["state"] not in CONTAINS',
     'if r["tier"] not in (1, 2) or (r["platform"] == "sentinel-2c" and not (MODE23 == "R1" and (ASUN.get(r["id"]) or 0) >= LOWSUN)) or b["o"]["state"] not in CONTAINS', 1),
    # (c) S2C anchors' Stage 16 product on the C3 path
    ('    base = B16[e["id"]]["o"]\n    sc = scene_list(e, key, W, H, smode)\n', '    base = base23(e, key)\n    sc = scene_list(e, key, W, H, smode)\n', 1),
    ('def strong(o):\n',
     'from lib16 import product16 as _p16\n'
     'def base23(e, key):\n'
     '    o = B16[e["id"]]["o"]\n'
     '    if e["platform"] != "sentinel-2c" or e["tier"] not in (1, 2): return o\n'
     '    if PRED[key]["anchor"] is None or e["id"] not in AF23:\n'
     '        return {"tier": 0, "state": "Unknown / Low Authority", "authority": "none", "display": "none", "floor_D": None, "withheld": None, "algal": None, "s2c": True, "conf": None, "p": None, "s2c_path": "stage22-c3", "no_c3_sample": True}\n'
     '    k = key[2]; R = {**POST[k], "t1": T1G, "t2": T2G, "t2opt": R16["t2opt"], "tier3_allowed": E14["tier3_allowed_states"]}\n'
     '    full = MODE23 == "R1" and (ASUN.get(e["id"]) or 0) >= LOWSUN\n'
     '    o2 = _p16(AT23.get(e["id"], e["tier"]), PRED[key]["anchor"], "sentinel-2a" if full else "sentinel-2c", AF23[e["id"]]["F_ndci"], None, R)\n'
     '    o2["s2c"] = not full; o2["s2c_path"] = "stage22-c3"; o2["s2c_full23"] = full; o2["p"] = PRED[key]["anchor"]; return o2\n'
     'def strong(o):\n', 1),
    # (e) exact feet: S2C single-scene rows use their C3 prediction
    ('pB = lambda r: r["o"].get("p") if r["o"].get("consensus") else bmap[r["id"]].get("p")',
     'pB = lambda r: r["o"].get("p") if (r["o"].get("consensus") or r["o"].get("s2c_path")) else bmap[r["id"]].get("p")', 1),
    # (d) windows and outputs
    ('WIN19 = [3, 5, 7, 10, 15]; PRIMARY = [3, 5, 7, 10]', ('WIN19 = [5, 10, 15]; PRIMARY = [5, 10, 15]' if MODE == "R1" else 'WIN19 = [5]; PRIMARY = [5]'), 1),
    ('f"{S}/stage19/dev19_rows.json"', f'f"{{S}}/stage23/dev23_{MODE}_rows.json"', 1),
    ('f"{S}/stage19/dev19.json"', f'f"{{S}}/stage23/dev23_{MODE}.json"', 1),
]
for old, new, n in PATCH:
    c = src.count(old); assert c == n, (c, n, old[:80])
    src = src.replace(old, new)
assert "stage19/dev19.json\"" not in src and "stage19/dev19_rows" not in src
src += open(f"{S}/stage23/report23_block.py").read()
if DRY: print("patches ok", len(PATCH)); sys.exit()
exec(compile(src, f"dev23[{MODE}](dev19 patched)", "exec"))
