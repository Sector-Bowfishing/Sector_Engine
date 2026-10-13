import json, numpy as np, sys
from pathlib import Path
H = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
f3 = lambda x: "n/a" if x is None or x != x else f"{x:.3f}"
f2 = lambda x: "n/a" if x is None or x != x else f"{x:.2f}"
L = []
def P(s=""): L.append(s)

def snoco_table(fn, neg="nstrict", title=""):
    r = json.load(open(H/"out"/fn)); P(f"**{title}** (`{fn}`, negatives = {neg})"); P()
    P("| obs | TP | FP | FN(all) | P raw | **P matched (50% prev.)** | P matched (raw prev.) | F1 matched (raw prev.) | R (UNKNOWN=miss) | R (known only) | F1 matched | IoU matched | BalAcc matched | FPR raw (all open-water cells) | FPR raw (known) | pos UNKNOWN | F1m lake-bootstrap 95% |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for o in "SAP":
        p = r["snoco"][f"{o}|{neg}"]["pooled"]; d = p["d"]; b = p["boot"]["F1_matched"]
        ci = "n/a" if b[0] is None else f"{b[0]:.2f}-{b[1]:.2f} (n={b[2]})"
        ph, nh = np.array(p["pos_hist"]), np.array(p["neg_hist"]); ok_ = (ph > 0) & (nh > 0); c = nh[ok_].sum() / max(1, ph[ok_].sum())
        fpr_ = d["fpw"] * c; Pmr = d["tp"] / (d["tp"] + fpr_) if d["tp"] + fpr_ > 0 else float("nan"); Rr = p["R_all"]; Fmr = 2 * Pmr * Rr / (Pmr + Rr) if Pmr + Rr > 0 else float("nan")
        P(f"| {o} | {d['tp']} | {d['fp']} | {d['npos']-d['tp']} | {f3(p['P_raw'])} | {f3(p['P_matched'])} | {f3(Pmr)} | {f3(Fmr)} | {f3(p['R_all'])} | {f3(p['R_known'])} | {f3(p['F1_matched'])} | {f3(p['IoU_matched'])} | {f3(p['BA_matched'])} | {f3(p['FPR_raw_all'])} | {f3(p['FPR_raw_known'])} | {f3(p['pos_unknown_share'])} | {ci} |")
    P()

def snoco_perlake(fn, neg="nstrict"):
    r = json.load(open(H/"out"/fn)); P(f"Per lake (`{fn}`): positives reachable (outside 40 m shore band) / whole-lake, TP, FP, P raw, P matched, R reachable, R whole-lake, FPR raw, scene (gap d, cov).")
    P(); P("| lake | obs | pos reach / whole | TP | FP | P raw | P matched | R reach | R whole-lake | FPR raw | scene used |"); P("|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in ["Serene","Blackmans","Storm","Roesiger","Bosworth"]:
        for o in "SAP":
            m = r["snoco"][f"{o}|{neg}"]["per_lake"][nm]; d = m["d"]; i = m["info"]
            sc = f"{i.get('kind')} gap {i.get('gap')}d" + (f" cov {i['cov']:.2f}" if 'cov' in i else "") + (f", n_acc {i['n_accepted']}, {i['persistence']}" if o == "P" else "")
            P(f"| {nm} | {o} | {d['npos']} / {d['npos_wholelake']} | {d['tp']} | {d['fp']} | {f3(m['P_raw'])} | {f3(m['P_matched'])} | {f3(m['R_all'])} | {f3(m['R_wholelake'])} | {f3(m['FPR_raw_all'])} | {sc} |")
    P()

def fwc_table(fn, title):
    r = json.load(open(H/"out"/fn)); P(f"**{title}** (`{fn}`)"); P()
    P("| lake (survey) | obs | scene (gap d) | point cells (surface, reachable) | recall (UNKNOWN=miss) | recall (known only) | UNKNOWN share of point cells | submersed-only cells flagged | unsurveyed cells flagged (not an FPR) |"); P("|---|---|---|---|---|---|---|---|---|")
    agg = {o: {"hit": 0, "n": 0, "kn_hit": 0, "kn_n": 0, "g7": [0, 0], "g21": [0, 0], "sub": [0, 0]} for o in "SAP"}
    for nm, v in r["fwc"].items():
        for o in "SAP":
            x = v[o]; s = x["surface_reachable"]; i = x["info"]
            P(f"| {nm} ({x['ref']}) | {o} | {i.get('kind')} {i.get('date','')} ({i.get('gap')}) | {s['n']} | {f3(s['recall_all'])} | {f3(s['recall_known'])} | {f3(s['unknown_share'])} | {f3(x['submersed_only']['recall_all'])} | {f3(x['background_flag_share']['share_known'])} |")
            a = agg[o]; a["hit"] += s["tp"]; a["n"] += s["n"]; kn = round(s["tp"] / s["recall_known"]) if s["recall_known"] > 0 else None
            if kn: a["kn_hit"] += s["tp"]; a["kn_n"] += kn
            g = i.get("gap")
            if g is not None: (a["g7"] if g <= 7 else a["g21"]).__setitem__(0, (a["g7"] if g <= 7 else a["g21"])[0] + s["tp"]); (a["g7"] if g <= 7 else a["g21"]).__setitem__(1, (a["g7"] if g <= 7 else a["g21"])[1] + s["n"])
            sb = x["submersed_only"]; a["sub"][0] += sb["tp"]; a["sub"][1] += sb["n"]
    P(); P("Pooled (cell-weighted) recall on surface point cells:"); P()
    P("| obs | recall (UNKNOWN=miss) | recall (known only) | gap <= 7 d | gap 8-21 d | submersed-only cells flagged |"); P("|---|---|---|---|---|---|")
    for o in "SAP":
        a = agg[o]
        P(f"| {o} | {a['hit']}/{a['n']} = {f3(a['hit']/max(1,a['n']))} | {a['kn_hit']}/{a['kn_n']} = {f3(a['kn_hit']/max(1,a['kn_n']))} | {a['g7'][0]}/{a['g7'][1]} = {f3(a['g7'][0]/max(1,a['g7'][1]))} | {a['g21'][0]}/{a['g21'][1]} = {f3(a['g21'][0]/max(1,a['g21'][1]))} | {a['sub'][0]}/{a['sub'][1]} = {f3(a['sub'][0]/max(1,a['sub'][1]))} |")
    P()

def pac_table(fn, title):
    r = json.load(open(H/"out"/fn)); P(f"**{title}** (`{fn}`)"); P()
    P("| obs | lake-years scored (lakes) | refused lake-years | Spearman vs PVI [95% lake-bootstrap] | Spearman vs PAC [95%] | AUC PVI>=20 vs <5 (n) [95%] | AUC PAC>=50 vs <20 (n) [95%] | per-lake-mean rho PVI | belt (40-90 m) rho PVI | rho PVI gap<=7 d (n) | rho PVI gap 8-21 d (n) |"); P("|---|---|---|---|---|---|---|---|---|---|---|")
    ci = lambda c: "n/a" if not c else f"[{c[0]:.2f}, {c[1]:.2f}]"
    for o in "SAP":
        e = r["observers"][o]; a = e["all"]
        P(f"| {o} | {a['n']} ({a['n_lakes']}) | {e['n_refused']} {e['refused_reasons']} | {f2(a.get('rho_PVI'))} {ci(a['ci']['rho_PVI'])} | {f2(a.get('rho_PAC'))} {ci(a['ci']['rho_PAC'])} | {f2(a['auc_PVI20v5'])} ({a['n_PVI_hi_lo'][0]}/{a['n_PVI_hi_lo'][1]}) {ci(a['ci']['auc_PVI20v5'])} | {f2(a['auc_PAC50v20'])} ({a['n_PAC_hi_lo'][0]}/{a['n_PAC_hi_lo'][1]}) {ci(a['ci']['auc_PAC50v20'])} | {f2(a['per_lake_mean'].get('rho_PVI'))} | {f2(e['belt'].get('rho_PVI'))} | {f2(e['gap_le7'].get('rho_PVI'))} ({e['gap_le7']['n']}) | {f2(e['gap_8_21'].get('rho_PVI'))} ({e['gap_8_21']['n']}) |")
    P()

snoco_table("score_50_v1_rej0.json", title="Snohomish, PRIMARY: v1 guards as written, 50 m cell, production scene gate ON, +-21 d")
snoco_perlake("score_50_v1_rej0.json")
snoco_table("score_50_prod_rej0.json", title="Snohomish, bare production (no prereg-only guards), 50 m")
snoco_table("score_50_v1fix_rej0.json", title="Snohomish, v1 with dark-water fix, 50 m")
snoco_table("score_50_v1_rej1.json", title="Snohomish, v1, production scene gate OFF (sensitivity)")
snoco_table("score_36_v1_rej0.json", title="Snohomish, v1, production daily 36 m frame")
snoco_table("score_50_v1_rej0.json", neg="nbuf", title="Snohomish, v1, buffered-none negatives (no label within 2 cells)")
fwc_table("score_50_v1_rej0.json", "FWC points, PRIMARY v1, 50 m")
fwc_table("score_50_prod_rej0.json", "FWC points, bare production, 50 m")
fwc_table("score_50_v1fix_rej0.json", "FWC points, v1 with dark fix")
fwc_table("score_50_prod_rej1.json", "FWC points, bare production, production scene gate OFF (sensitivity)")
pac_table("pac_50_v1_rej0.json", "PAC/PVI, PRIMARY v1, 50 m")
pac_table("pac_50_prod_rej0.json", "PAC/PVI, bare production")
pac_table("pac_50_prod_rej1.json", "PAC/PVI, bare production, gate OFF (sensitivity)")
pac_table("pac_50_v1fix_rej0.json", "PAC/PVI, v1 with dark fix")
open(H/"out/tables.md", "w").write("\n".join(L)); print("\n".join(L))
