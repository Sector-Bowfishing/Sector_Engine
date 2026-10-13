"""Evaluate the DEV grid and apply the A4 selection rule. Writes out/grid_dev_table.md, out/grid_dev.json and (always) out/chosen_params.frozen.json with a timestamp."""
from v2metrics import *
from v2jobs import DEV_SNOCO, TEST_SNOCO, SNOCO, FWC_IDS, nla_split
import pickle
install_guard()
D = pickle.load(open(OUT2 / "grid_dev_raw.pkl", "rb"))
CLS = pd.read_csv(NLA / "out/nla_lake_classes.csv").set_index("lakeKey")
rows = []
for hs in GRID_HS:
    for hp in GRID_HP:
        key = pair_key(hs, hp)
        ev = snoco_eval(D["snoco"], key, DEV_SNOCO, "A", "strict")
        p = ev["pooled"]
        negs = []
        for r in D["nla"]:
            if CLS.loc[r["lakeKey"], "cls"] != "NEG": continue
            o = r.get("runs", {}).get(key, {}).get("obs", {}).get("A") if "runs" in r else None
            if o is None: negs.append((r["lakeKey"], None)); continue
            bs = o.get("belt_share", float("nan"))
            negs.append((r["lakeKey"], None if bs != bs else bs))
        scored = [(k, v) for k, v in negs if v is not None]
        nacc = sum(D["snoco"][f"snoco|{n}"]["runs"][key]["sel"]["n_accepted"] for n in DEV_SNOCO); nin = sum(D["snoco"][f"snoco|{n}"]["runs"][key]["sel"]["n_inwindow"] for n in DEV_SNOCO)
        f1 = p["F1_raw"]; f1 = 0.0 if f1 != f1 else f1
        c1_evid = p["neg_known"] > 0; c1 = c1_evid and p["FPR_known"] <= 0.02
        c2_evid = len(scored) > 0; c2 = c2_evid and all(v <= 0.02 for _, v in scored)
        rows.append(dict(hs=hs, hp=hp, TP=p["TP"], FP=p["FP"], FN=p["FN"], P=p["P_raw"], R=p["R_int"], F1=f1, FPR_known=p["FPR_known"], neg_known=p["neg_known"], neg_cells=p["nneg"],
                         unk_share=p["interior_unknown_share"], acc_scenes=nacc, inwin=nin, nla_neg_scored=len(scored), nla_neg_each=dict(negs), nla_neg_max=max([v for _, v in scored], default=None),
                         nla_neg_mean=(float(np.mean([v for _, v in scored])) if scored else None), c1=c1, c1_evidenced=c1_evid, c2=c2, c2_evidenced=c2_evid, admissible=bool(c1 and c2),
                         per_lake={k: dict(TP=v["TP"], FN=v["FN"], FP=v["FP"], npos=v["npos_int"]) for k, v in ev["per_lake"].items()}))
adm = [r for r in rows if r["admissible"]]
best = None
if adm:
    mx = max(r["F1"] for r in adm)
    top = [r for r in adm if r["F1"] >= mx - 1e-9]
    top.sort(key=lambda r: (round(r["unk_share"], 12), -r["hs"], r["hp"]))
    best = top[0]
frozen_by_vacuous = None
vac = [r for r in rows if r["c1_evidenced"] and r["c1"] and (not r["c2_evidenced"] or r["c2"])]
if vac:
    mx = max(r["F1"] for r in vac); top = [r for r in vac if r["F1"] >= mx - 1e-9]; top.sort(key=lambda r: (round(r["unk_share"], 12), -r["hs"], r["hp"])); frozen_by_vacuous = (top[0]["hs"], top[0]["hp"])
res = dict(chosen=None if best is None else dict(haze_swir=best["hs"], haze_standoff_px=best["hp"]), verdict=("ADMISSIBLE_SETTING_CHOSEN" if best else "NO_ADMISSIBLE_SETTING"),
           n_admissible=len(adm), dev_max_F1_over_admissible=(best["F1"] if best else None), vacuous_reading_would_choose=frozen_by_vacuous)
frozen = dict(haze_swir=(best["hs"] if best else DEFAULT[0]), haze_standoff_px=(best["hp"] if best else DEFAULT[1]), source=("A4 DEV tuning rule" if best else "NO ADMISSIBLE SETTING: defaults kept (A4)"),
              verdict=res["verdict"], written_at=dt.datetime.now().isoformat(timespec="seconds"), written_before_test_scoring=True, observer_used_for_tuning="A", dev_sets=dict(snoco=DEV_SNOCO, nla_n=len(D["nla"])))
json.dump(dict(summary=res, rows=rows), open(OUT2 / "grid_dev.json", "w"), indent=1, default=float)
f = lambda x, n=3: "n/a" if x is None or x != x else f"{x:.{n}f}"
L = ["| haze_swir | standoff px | TP | FP | FN | P | R int | F1 | open-water FPR known (FP/known) | unk interior | acc/in-win scenes | NLA dev negs scored | each negative belt share | C1 (FPR<=2%) | C2 (neg each<=2%) | admissible |", "|" + "---|" * 16]
for r in rows:
    ne = "; ".join(f"{k.split('_')[0]}:{'unsc' if v is None else f'{v:.3f}'}" for k, v in r["nla_neg_each"].items())
    L.append(f"| {r['hs']:.2f} | {r['hp']} | {r['TP']} | {r['FP']} | {r['FN']} | {f(r['P'])} | {f(r['R'])} | {f(r['F1'])} | {r['FP']}/{r['neg_known']} = {f(r['FPR_known'])} | {f(r['unk_share'])} | {r['acc_scenes']}/{r['inwin']} | {r['nla_neg_scored']} | {ne} | {'Y' if r['c1'] else ('N' if r['c1_evidenced'] else 'unevid')} | {'Y' if r['c2'] else ('N' if r['c2_evidenced'] else 'unevid')} | {'**YES**' if r['admissible'] else 'no'} |")
open(OUT2 / "grid_dev_table.md", "w").write("\n".join(L) + "\n")
json.dump(frozen, open(OUT2 / "chosen_params.frozen.json", "w"), indent=1)
print("\n".join(L)); print(json.dumps(res, indent=1)); print(frozen)
