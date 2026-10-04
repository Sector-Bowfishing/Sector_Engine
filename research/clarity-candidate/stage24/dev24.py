"""Stage 24 PREREGISTRATION sections 7-16: geometry-aware causal consensus. stage19/dev19.py executed verbatim with
stage23/dev23.py's R0 patches (C3 samples, S2C lower authority, base23) plus:
  (g1) every scene in the causal scene list carries its STAC geometry (stage24/geom24_items.json);
  (g2) build(): the reference pass (anchor if valid, else the newest used prior); each used scene is Compatible (same side) or
       Conflicted (opposite side: wrapped view-azimuth difference > 90 deg) with it; METHOD24 selects
       G0 (no geometry), G1 (variance + gamma for conflicted), G2 (G0, but revert to the anchor's Stage 16 product if a conflicted
       scene's state is disjoint from the issued state), G3 (conflicted scenes dropped);
  (g3) per-answer provenance (contributing passes, geometry, base/geometry/final weights) and the compatible-agreement count.
dev19's own main body runs G0 at 5/10/15; report24_block.py (appended) runs G1-G3 and all section 7-16 reporting.
  python dev24.py"""
import json, os, sys, hashlib
S = os.environ["CLARITY_RESEARCH_ROOT"]; os.environ["MODE23"] = "R0"
F24 = json.load(open(f"{S}/stage24/FREEZE_STAGE24.json"))
assert hashlib.sha256(open(f"{S}/stage24/PREREGISTRATION_STAGE24.md", "rb").read()).hexdigest() == F24["prereg_sha256"]
assert hashlib.sha256(open(f"{S}/stage24/derived24.json", "rb").read()).hexdigest() == F24["derived24_sha256"]
DRY = bool(os.environ.get("DRY24"))
d23 = open(f"{S}/stage23/dev23.py").read(); ns = {"__name__": "dev23lib"}
exec(d23.split("for old, new, n in PATCH:")[0], ns)
src, PATCH = ns["src"], ns["PATCH"]
PATCH = [p for p in PATCH if not p[0].startswith("WIN19 = [3, 5, 7, 10, 15]")]
PATCH.append(('WIN19 = [3, 5, 7, 10, 15]; PRIMARY = [3, 5, 7, 10]', 'WIN19 = [5, 10, 15]; PRIMARY = [5, 10, 15]', 1))
PATCH = [(o, n.replace("stage23/dev23_", "stage24/dev24_G0_"), c) for o, n, c in PATCH]
for old, new, n in PATCH:
    c = src.count(old); assert c == n, (c, n, old[:80]); src = src.replace(old, new)
P24 = [
    ('def FA(s):\n',
     'G24 = json.load(open(f"{S}/stage24/geom24_items.json")); GAMMA24 = json.load(open(f"{S}/stage24/derived24.json"))["gamma"]["value"]; METHOD24 = "G0"\n'
     'def DAZ(a, b): return abs((a - b + 180) % 360 - 180)\n'
     'def CONFLICT(s, ref):\n'
     '    a, b = s.get("geo"), ref.get("geo")\n'
     '    return bool(a and b and s is not ref and DAZ(a["view_az"], b["view_az"]) > 90)\n'
     'def FA(s):\n', 1),
    ('"pass_time": n["pass_time"], "sun": n["sun_elev"]})\n', '"pass_time": n["pass_time"], "sun": n["sun_elev"], "geo": G24.get(n["item"])})\n', 1),
    ('"anchor": True, "sun": ASUN.get(cid)})\n', '"anchor": True, "sun": ASUN.get(cid), "geo": G24.get(corp[cid]["item"]), "item": corp[cid]["item"]})\n', 1),
    ('"age": n["age"], "sun": n.get("sun")})\n', '"age": n["age"], "sun": n.get("sun"), "geo": n.get("geo"), "item": n["item"]})\n', 1),
    # build(): reference pass, compatibility, G3 filter
    ('    full = [s for s in sc if FA(s)]\n    if not full: return dict(base, n_full=0, agree=0, consensus=False)\n',
     '    full = [s for s in sc if FA(s)]\n    if not full: return dict(base, n_full=0, agree=0, consensus=False)\n'
     '    ref = next((s for s in full if s["anchor"]), None) or min(full, key=lambda s: s["adt"])\n'
     '    for s in full: s["conf_geo"] = CONFLICT(s, ref)\n'
     '    if METHOD24 == "G3": full = [s for s in full if not s["conf_geo"]]\n', 1),
    # G1: geometry variance in the inverse-uncertainty weights
    ('    v = np.array([par["sig"][s["tier"]] ** 2 + par["kappa"] * s["adt"] for s in sc]); p = np.array([s["p"] for s in sc]); w = 1 / v\n',
     '    v = np.array([par["sig"][s["tier"]] ** 2 + par["kappa"] * s["adt"] + (GAMMA24 if (METHOD24 == "G1" and s.get("conf_geo")) else 0.0) for s in sc]); p = np.array([s["p"] for s in sc]); w = 1 / v\n', 1),
    # G2 refusal + provenance + compatible agreement
    ('    o.update(n_full=len(full), n_use=n, agree=agree, disjoint=disjoint, consensus=True, s2c_used=len(use) - len(full))\n    return o\n',
     '    o.update(n_full=len(full), n_use=n, agree=agree, disjoint=disjoint, consensus=True, s2c_used=len(use) - len(full))\n'
     '    o["agree_c"] = sum(1 for s_, x in zip(ags, states) if st and x and CONTAINS[x] >= CONTAINS[st] and not s_.get("conf_geo"))\n'
     '    o["n_conflicted"] = sum(1 for s_ in use if s_.get("conf_geo"))\n'
     '    bv = [par["sig"][s_["tier"]] ** 2 + par["kappa"] * s_["adt"] for s_ in use]; gv = [(GAMMA24 if (METHOD24 == "G1" and s_.get("conf_geo")) else 0.0) for s_ in use]\n'
     '    wt = [1 / (a_ + b_) for a_, b_ in zip(bv, gv)]; tw = sum(wt)\n'
     '    o["prov"] = [{"item": s_.get("item"), "platform": s_["platform"], "anchor": s_["anchor"], "age_days": s_["adt"], "tier": s_["tier"], "geo": s_.get("geo"), "conflicted": s_.get("conf_geo"),\n'
     '                  "base_var": a_, "geometry_var": b_, "weight": w_ / tw, "state": x} for s_, a_, b_, w_, x in zip(use, bv, gv, wt, [scene_state(s__, post) for s__ in use])]\n'
     '    if METHOD24 == "G2" and st and any(s_.get("conf_geo") and x and not (CONTAINS[x] & CONTAINS[st]) for s_, x in zip(use, [scene_state(s__, post) for s__ in use])):\n'
     '        return dict(base, n_full=len(full), agree=0, consensus=False, geo_refused=True, prov=o["prov"])\n'
     '    return o\n', 1),
]
for old, new, n in P24:
    c = src.count(old); assert c == n, (c, n, old[:80]); src = src.replace(old, new)
src += open(f"{S}/stage24/report24_block.py").read()
if DRY: print("patches ok", len(PATCH), "+", len(P24)); sys.exit()
exec(compile(src, "dev24(dev19 patched)", "exec"))
