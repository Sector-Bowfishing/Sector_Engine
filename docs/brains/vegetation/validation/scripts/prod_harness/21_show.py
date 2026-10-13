import json, sys
f = sys.argv[1]; neg = sys.argv[2] if len(sys.argv) > 2 else "nstrict"
r = json.load(open(f)); f3 = lambda x: "  nan" if x is None or x != x else f"{x:.3f}"
print(f, "cell", r["cell"], r["mode"], "rej", r["use_rejected"])
for o in "SAP":
    p = r["snoco"][f"{o}|{neg}"]["pooled"]; b = p["boot"]
    print(f" {o} pooled npos={p['d']['npos']} tp={p['d']['tp']} fp={p['d']['fp']} nneg={p['d']['nneg']} P_raw={f3(p['P_raw'])} P_m={f3(p['P_matched'])} R_all={f3(p['R_all'])} R_kn={f3(p['R_known'])} F1m={f3(p['F1_matched'])} F1raw={f3(p['F1_raw'])} IoUm={f3(p['IoU_matched'])} BAm={f3(p['BA_matched'])} FPRraw={f3(p['FPR_raw_all'])} FPRm={f3(p['FPR_matched'])} posUnk={f3(p['pos_unknown_share'])} F1m_CI={b['F1_matched'][:2]}")
    for nm, m in r["snoco"][f"{o}|{neg}"]["per_lake"].items():
        print(f"    {nm:10s} npos={m['d']['npos']:3d} whole={m['d']['npos_wholelake']:3d} tp={m['d']['tp']:3d} fp={m['d']['fp']:3d} P_raw={f3(m['P_raw'])} P_m={f3(m['P_matched'])} R={f3(m['R_all'])} Rwhole={f3(m['R_wholelake'])} FPR={f3(m['FPR_raw_all'])} info={m['info']}")
print("FWC")
for nm, v in r["fwc"].items():
    print(" ", nm, v["S"]["ref"], "scenes", v["S"]["n_scenes"], "/", v["S"]["n_scenes_incl_rejected"], "rej", v["S"]["n_rejected_by_prod_gate"])
    for o in "SAP":
        x = v[o]; s = x["surface_reachable"]
        print(f"    {o} n={s['n']} rec_all={f3(s['recall_all'])} rec_kn={f3(s['recall_known'])} unk={f3(s['unknown_share'])} sub={f3(x['submersed_only']['recall_all'])} bg={f3(x['background_flag_share']['share_known'])} info={x['info']}")
