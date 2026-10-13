import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, datetime as dt, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import score_lib as SL
H = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
LYS = [o for o in json.load(open(H.parent.parent/"data/pac_lakeyears.json")) if o["lake"] != "Okeechobee"]
SNOCO = ["Serene","Blackmans","Storm","Roesiger","Bosworth"]; FWC = ["Orange","Griffin","Apopka","Harris","Panasoffkee","Yale","Cypress"]
L = []
def P(s=""): L.append(s)
# --- 1. SWIR-DN scene gate
P("### SWIR-DN scene gate (dws.s2_pass: median SWIR DN over SCL water must be 900-1500)"); P()
P("| dataset | scenes within +-21 d | rejected by gate | lakes with >=1 rejected | plant-flag share of clarity cells, gate-rejected scenes (median) | same, accepted scenes (median) |"); P("|---|---|---|---|---|---|")
sets = {"snoco": [(n, np.load(H/f"out/cells50_snoco_{n}.npz", allow_pickle=True), dt.date.fromisoformat(str(np.load(H/f"out/cells50_snoco_{n}.npz", allow_pickle=True)["survey"]))) for n in SNOCO],
        "fwc_points": [(n, np.load(H/f"out/cells50_fwc_{n}.npz", allow_pickle=True), None) for n in FWC]}
for ds, items in sets.items():
    tot = rej = 0; lk = 0; fr_r = []; fr_a = []
    for n, z, ref in items:
        ref = ref or dt.date.fromisoformat(str(z["survey"])); dates = [dt.date.fromisoformat(str(d)) for d in z["dates"]]; anyrej = False
        for i, d in enumerate(dates):
            if abs((d - ref).days) > 21 or not z["ok"][i]: continue
            tot += 1; sh = float((z["grass_prod"][i] & z["clarity"]).sum() / max(1, z["clarity"].sum()))
            if str(z["rejected"][i]): rej += 1; anyrej = True; fr_r.append(sh)
            else: fr_a.append(sh)
        lk += anyrej
    P(f"| {ds} | {tot} | {rej} | {lk} / {len(items)} | {np.median(fr_r) if fr_r else float('nan'):.3f} | {np.median(fr_a):.3f} |")
tot = rej = 0; lks = set(); fr_r = []; fr_a = []; cache = {}
for o in LYS:
    f = H/f"out/pac50_{o['lake_id']}.npz"
    if not f.exists(): continue
    z = cache.setdefault(o["lake_id"], np.load(f, allow_pickle=True)); ref = dt.date.fromisoformat(o["survey_med"])
    for i, d in enumerate(z["dates"]):
        d = dt.date.fromisoformat(str(d))
        if abs((d - ref).days) > 21 or str(z["error"][i]): continue
        tot += 1; sh = float((z["grass_prod"][i] & z["clarity"]).sum() / max(1, z["clarity"].sum()))
        if str(z["rejected"][i]): rej += 1; lks.add(o["lake_id"]); fr_r.append(sh)
        else: fr_a.append(sh)
P(f"| fwc_pac (scene x lake-year pairs) | {tot} | {rej} | {len(lks)} / {len(cache)} | {np.median(fr_r) if fr_r else float('nan'):.3f} | {np.median(fr_a):.3f} |"); P()
# --- 2. unknown accounting tables
u = json.load(open(H/"out/unknown_50.json"))
for mode, ttl in (("v1", "prereg guards as written"), ("prod", "bare production"), ("v1fix", "v1 with dark-water fix")):
    P(f"### UNKNOWN / refusal accounting, {ttl}: share of ALL lake cells (incl. shore band), selected scene (S) and accepted pass (A)"); P()
    cols = ["SHORE_ADJACENT", "NO_DATA_OFF_SWATH", "CLOUD_SHADOW_STANDOFF", "HAZE_OR_CLOUD_EDGE_STANDOFF", "DARK_WATER", "NO_SCENE", "PASS_NOT_ACCEPTED", "CLEAR", "FLAG"]
    P("| dataset | obs | " + " | ".join(cols) + " | UNKNOWN total | lakes w/o scene |"); P("|---|---|" + "---|" * (len(cols) + 2))
    for ds in ("snoco", "fwc_points", "fwc_pac"):
        v = u[f"{mode}|{ds}"]
        for o in "SA":
            Lc = v["lakecells"][o]; st = v["status"][o]; unk = sum(st[c] for c in cols[:7])
            P(f"| {ds} ({v['n_units']} units) | {o} | " + " | ".join(f"{100*st[c]/Lc:.1f}%" for c in cols) + f" | {100*unk/Lc:.1f}% | {v['lakes_with_no_selected_scene'][o]} |")
    P()
P("### Non-exclusive guard hit frequency, clarity-mask cells, all scenes within +-21 d (bare production flags + prereg-only guards)"); P()
P("| dataset | cloud/shadow/insufficient (seen<50%) | no data | hidden (cloud edge/600 m standoff/haze) | of which near real cloud | dark-water (>=50% of seen px) | glint-like SWIR>0.0215 (>=50%) |"); P("|---|---|---|---|---|---|---|")
for ds in ("snoco", "fwc_points", "fwc_pac"):
    g = u[f"v1|{ds}"]["guard_hit_share_all_window_scenes"]
    P(f"| {ds} | {100*g['unseen']:.1f}% | {100*g['nodata']:.1f}% | {100*g['hidden']:.1f}% | {100*g['hidden_near_cloud']:.1f}% | {100*g['dark']:.1f}% | {100*g['glare']:.1f}% |")
P()
# --- 3. pass acceptance stats
P("### Pass acceptance (coverage of non-plant water) per dataset, scenes within +-21 d, bare production"); P()
P("| dataset | scenes | cov >= 0.50 | 0.25 <= cov < 0.50 | cov < 0.25 | median cov |"); P("|---|---|---|---|---|---|")
for ds, items in sets.items():
    covs = []
    for n, z, ref in items:
        ref = ref or dt.date.fromisoformat(str(z["survey"]))
        for s in SL.prep(z, "prod", True):
            if abs((s["date"] - ref).days) <= 21: covs.append(s["cov"])
    c = np.array(covs); P(f"| {ds} | {len(c)} | {100*np.mean(c>=.5):.0f}% | {100*np.mean((c>=.25)&(c<.5)):.0f}% | {100*np.mean(c<.25):.0f}% | {np.median(c):.2f} |")
covs = []
for lid, z in cache.items():
    zz = {k: z[k] for k in z.files}
    sc = SL.prep(zz, "prod", True)
    for o in LYS:
        if o["lake_id"] != lid: continue
        ref = dt.date.fromisoformat(o["survey_med"]); covs += [s["cov"] for s in sc if abs((s["date"] - ref).days) <= 21]
c = np.array(covs); P(f"| fwc_pac (scene x lake-year) | {len(c)} | {100*np.mean(c>=.5):.0f}% | {100*np.mean((c>=.25)&(c<.5)):.0f}% | {100*np.mean(c<.25):.0f}% | {np.median(c):.2f} |"); P()
open(H/"out/tables_extra.md", "w").write("\n".join(L)); print("\n".join(L))
