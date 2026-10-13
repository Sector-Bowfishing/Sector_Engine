import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, datetime as dt, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import score_lib as SL
H = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
z = np.load(H/"out/cells50_guntersville_central.npz", allow_pickle=True); z = {k: z[k] for k in z.files}
dates = [dt.date.fromisoformat(str(d)) for d in z["dates"]]; cl = z["clarity"]; lake = z["lake"]
L = []; P = lambda s="": L.append(s)
out = {}
P("Lake Guntersville central/lower reach (clipped polygon, %d lake cells, %d clarity cells), Sentinel-2 C1 L2A, passes with scene cloud <= 30 %%: %d passes, %d read, %d rejected by the production SWIR-DN gate." % (lake.sum(), cl.sum(), len(dates), z["ok"].sum(), sum(1 for r in z["rejected"] if str(r) and not str(r).startswith("ERR"))))
P()
for mode in ("v1", "prod"):
    sc_all = SL.prep(z, mode, True); sc = [s for s in sc_all if not s["rejected"]]
    P(f"**mode {mode}**: scene-level (every pass; clear = lake cells seen; cov = pass-acceptance coverage; flagged % = flagged / known clarity cells; unknown % = share of clarity cells UNKNOWN)"); P()
    P("| date | gate | clear | cov | accepted | flagged % of known | flagged % of clarity cells | UNKNOWN % | haze/cloud-edge | dark | cloud/shadow |"); P("|---|---|---|---|---|---|---|---|---|---|---|")
    rows = []
    for s in sc_all:
        st = s["st"]; known = ((st == SL.CLEAR) | (st == SL.FLAG)) & cl; fl = (st == SL.FLAG) & cl
        unk = cl & ~known
        r = dict(date=str(s["date"]), rejected=s["rejected"], clear=s["clear"], cov=s["cov"], flagged_known=float(fl.sum() / max(1, known.sum())) if known.sum() else None, flagged_clarity=float(fl.sum() / cl.sum()),
                 unknown=float(unk.sum() / cl.sum()), haze=float(((st == SL.HAZE) & cl).sum() / cl.sum()), dark=float(((st == SL.DARK) & cl).sum() / cl.sum()), cloud=float((((st == SL.CLOUD) | (st == SL.NODATA)) & cl).sum() / cl.sum()))
        rows.append(r)
        P(f"| {r['date']} | {'REJ' if r['rejected'] else 'ok'} | {r['clear']:.2f} | {r['cov']:.2f} | {'Y' if r['cov']>=0.5 and not r['rejected'] else 'n'} | " + (f"{100*r['flagged_known']:.1f}" if r['flagged_known'] is not None else "n/a") + f" | {100*r['flagged_clarity']:.1f} | {100*r['unknown']:.0f} | {100*r['haze']:.0f} | {100*r['dark']:.0f} | {100*r['cloud']:.0f} |")
    P()
    out[f"{mode}_scenes"] = rows
    P(f"**mode {mode}**: observers by month (reference = 15th, window +-21 d, production gate ON)"); P()
    P("| month | candidate passes in window | gate-rejected | accepted (cov>=0.5) | S: scene gap, flagged % known, UNKNOWN % | A: scene gap/kind, flagged % known, UNKNOWN % | P: n accepted / status, flagged % known, UNKNOWN % |"); P("|---|---|---|---|---|---|---|")
    mrows = []
    for mth in range(4, 11):
        ref = dt.date(2025, mth, 15)
        win_all = [s for s in sc_all if abs((s["date"] - ref).days) <= 21]; n_gate = sum(1 for i, d_ in enumerate(dates) if abs((d_ - ref).days) <= 21 and str(z["rejected"][i]).startswith("SWIR")); n_rej = sum(1 for i, d_ in enumerate(dates) if abs((d_ - ref).days) <= 21 and str(z["rejected"][i]).startswith("SWIR")); acc = [s for s in sc if abs((s["date"] - ref).days) <= 21 and s["cov"] >= 0.5]
        cells = {}
        for o in "SAP":
            st, info = SL.OBS[o](z, sc, ref); known = ((st == SL.CLEAR) | (st == SL.FLAG)) & cl; fl = (st == SL.FLAG) & cl
            cells[o] = dict(info={k: v for k, v in info.items() if k != "A"}, flagged_known=float(fl.sum() / max(1, known.sum())) if known.sum() else None, unknown=float((cl & ~known).sum() / cl.sum()),
                            flagged_clarity=float(fl.sum() / cl.sum()))
        f = lambda c: ("n/a" if c['flagged_known'] is None else f"{100*c['flagged_known']:.1f}%") + f", {100*c['unknown']:.0f}%"
        P(f"| 2025-{mth:02d} | {len(win_all) + n_gate} | {n_rej} | {len(acc)} | gap {cells['S']['info'].get('gap')}d, {f(cells['S'])} | {cells['A']['info'].get('gap')}d {cells['A']['info'].get('kind')}, {f(cells['A'])} | {cells['P']['info'].get('n_accepted')} / {cells['P']['info'].get('persistence')}, {f(cells['P'])} |")
        mrows.append(dict(month=mth, n_window=len(win_all) + n_gate, n_rejected=n_rej, n_accepted=len(acc), **cells))
    P(); out[f"{mode}_months"] = mrows
json.dump(out, open(H/"out/guntersville_scored.json", "w"), indent=1, default=float)
open(H/"out/tables_guntersville.md", "w").write("\n".join(L)); print("\n".join(L))
