"""Figures: per-lake panels + pooled summaries. Writes figs/*.png"""
import json, numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import *
from s4_analysis import load, build_curve, curve_at, NB, BW, CAL, ORDER
A = json.load(open(H/"out/analysis.json"))["lakes"]
INK = "#222"; MUTE = "#6b7280"; BLUE = "#2563eb"; ORG = "#d97706"; GREY = "#9ca3af"; GRN = "#15803d"; RED = "#b91c1c"
STC = {"ACCEPTED": GRN, "FALLBACK": "#84cc16", "REFUSED": ORG, "CLOUD": GREY, "ICE": "#0ea5e9", "NODATA": "#e5e7eb", "SKIPPED_SUBSAMPLE": "#d1d5db", "ERR": RED}
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTE, "axes.labelcolor": INK, "xtick.color": MUTE, "ytick.color": MUTE, "axes.spines.top": False, "axes.spines.right": False})
(H/"figs").mkdir(exist_ok=True)
for lk, cls, lab in LAKES:
    df = load(lk); L = A[lk]; a = df[(df.status == "ACCEPTED") & df.belt_share.notna()]
    fig = plt.figure(figsize=(12, 8.4)); gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1.1, 0.9], hspace=0.55, wspace=0.22)
    ax = fig.add_subplot(gs[0, :]); ax.scatter(a.date, a.belt_share*100, s=14, c=BLUE, label="belt share (35-90 m), accepted pass")
    al = df[(df.status == "ACCEPTED") & df.lake_share.notna()]; ax.scatter(al.date, al.lake_share*100, s=10, c=ORG, marker="s", label="whole-lake plant-cell share")
    ax.set_ylabel("% of seen cells"); ax.set_title(f"{lab} ({cls}) - accepted-pass time series, 2017-2025 (n accepted = {L['n_accepted']})", loc="left", color=INK)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    ax2 = fig.add_subplot(gs[1, 0])
    for y, g in a.groupby("year"): ax2.plot(g.doy, g.belt_share*100, lw=0.8, alpha=0.45, color=GREY, marker=".", ms=3)
    if "curve" in L:
        cs = np.array(L["curve"]); xs = np.arange(1, 366); ax2.plot(xs, curve_at(cs, xs)*100, color=BLUE, lw=2.2, label="lake climatology (median of yearly bin medians)")
        lo, hi = L["clim_amp"]
        for u, ls in ((0.2, ":"), (0.8, ":")): ax2.axhline((lo+u*(hi-lo))*100, color=MUTE, lw=0.7, ls=ls)
    for m0, m1 in ((7, 8),): ax2.axvspan(pd.Timestamp(2021, 7, 1).dayofyear, pd.Timestamp(2021, 8, 31).dayofyear, color="#fde68a", alpha=0.35, lw=0)
    for m0, m1 in ((12, 12), (1, 2)): pass
    ax2.axvspan(1, 59, color="#bfdbfe", alpha=0.3, lw=0); ax2.axvspan(335, 365, color="#bfdbfe", alpha=0.3, lw=0)
    ax2.set_xlabel("day of year (yellow = calendar 'peak Jul-Aug', blue = calendar 'dormant Dec-Feb'; dotted = u 0.2/0.8 of own range)", fontsize=7.5); ax2.set_ylabel("belt share %"); ax2.legend(frameon=False, fontsize=7.5, loc="upper left")
    ax2.set_title("lake-specific annual cycle (thin grey = individual years)", loc="left", color=INK, fontsize=9)
    ax3 = fig.add_subplot(gs[1, 1]); mo = pd.DataFrame(L["monthly"]).set_index("month")
    bottom = np.zeros(12)
    for c in ["ACCEPTED", "FALLBACK", "REFUSED", "CLOUD", "ICE", "NODATA", "SKIPPED_SUBSAMPLE"]:
        v = mo[c].values/np.maximum(mo.tot.values, 1)*100; ax3.bar(mo.index, v, bottom=bottom, color=STC[c], width=0.8, label=c.replace("SKIPPED_SUBSAMPLE", "not read (subsample)").title() if c != "ICE" else "Ice/snow"); bottom += v
    ax3.set_xticks(range(1, 13)); ax3.set_ylabel("% of S2 dates (tile cloud<85)"); ax3.set_title("what happens to each overpass, by month", loc="left", color=INK, fontsize=9)
    ax3.legend(frameon=False, fontsize=6.5, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax4 = fig.add_subplot(gs[2, :]); ag = L["age_imp"]; ms = list(range(1, 13))
    ax4.bar([m-0.2 for m in ms], [ag[str(m)]["med"] for m in ms], width=0.4, color=BLUE, label="median age of newest accepted pass (days)")
    ax4.bar([m+0.2 for m in ms], [ag[str(m)]["p90"] for m in ms], width=0.4, color=ORG, label="90th percentile")
    ax4.set_xticks(ms); ax4.set_ylabel("days"); ax4.legend(frameon=False, fontsize=7.5); ax4.set_title("observation age on a random day (skipped dates imputed)", loc="left", color=INK, fontsize=9)
    fig.savefig(H/f"figs/lake_{lk}.png", dpi=130, bbox_inches="tight"); plt.close(fig)
# pooled: agreement bars
rows = []
for lk, cls, lab in LAKES:
    i = A[lk]["loyo"]["belt_share"]
    if "clim_vs_obs" in i: rows.append((lab, i["clim_vs_obs"]["exact"], i["cal_vs_obs"]["exact"], i["common_pers"]["exact"], i["clim_vs_obs"]["w1"]))
if rows:
    fig, ax = plt.subplots(figsize=(11, 4.6)); x = np.arange(len(rows)); w = 0.26
    ax.bar(x-w, [r[1] for r in rows], w, color=BLUE, label="lake climatology (LOYO)"); ax.bar(x, [r[2] for r in rows], w, color=GREY, label="generic calendar rule"); ax.bar(x+w, [r[3] for r in rows], w, color=ORG, label="persistence of last observation")
    ax.set_xticks(x); ax.set_xticklabels([r[0] for r in rows], rotation=30, ha="right"); ax.set_ylabel("exact state agreement"); ax.set_ylim(0, 1); ax.legend(frameon=False, ncol=3)
    ax.set_title("Exact agreement with observed state class, belt share, leave-one-year-out", loc="left"); fig.savefig(H/"figs/agreement_by_lake.png", dpi=130, bbox_inches="tight"); plt.close(fig)
# gap heatmap
fig, ax = plt.subplots(figsize=(9, 5)); M = np.array([[A[lk]["age_imp"][str(m)]["p90"] for m in range(1, 13)] for lk, _, _ in LAKES])
im = ax.imshow(M, aspect="auto", cmap="Blues"); ax.set_yticks(range(len(LAKES))); ax.set_yticklabels([l for _, _, l in LAKES]); ax.set_xticks(range(12)); ax.set_xticklabels(list("JFMAMJJASOND"))
for i in range(M.shape[0]):
    for j in range(12): ax.text(j, i, f"{M[i,j]:.0f}", ha="center", va="center", fontsize=7, color="white" if M[i, j] > M.max()*0.6 else INK)
ax.set_title("90th-percentile age (days) of the newest accepted pass, by month", loc="left"); fig.colorbar(im, label="days"); fig.savefig(H/"figs/observation_age_p90.png", dpi=130, bbox_inches="tight"); plt.close(fig)
# overlaid climatologies normalised
fig, ax = plt.subplots(figsize=(10, 5)); xs = np.arange(1, 366)
for lk, cls, lab in LAKES:
    if "curve" in A[lk]:
        cs = np.array(A[lk]["curve"]); lo, hi = A[lk]["clim_amp"]; ax.plot(xs, (curve_at(cs, xs)-lo)/max(hi-lo, 1e-9), lw=1.3, label=lab)
ax.axvspan(182, 243, color="#fde68a", alpha=0.3, lw=0); ax.set_xlabel("day of year (yellow = Jul-Aug)"); ax.set_ylabel("belt share, scaled to each lake's own min-max"); ax.legend(frameon=False, fontsize=7, ncol=2)
ax.set_title("Lake-specific climatologies of belt share (scaled 0-1 per lake)", loc="left"); fig.savefig(H/"figs/climatologies_overlay.png", dpi=130, bbox_inches="tight"); plt.close(fig)
print("figs done")
