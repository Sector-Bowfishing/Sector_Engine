"""Stage 11 figures (acolite venv, which has matplotlib). Reads the analysis JSONs; writes figs/*.png."""
import json, os, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage11"
F = f"{S}/analysis/figs"; os.makedirs(F, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "font.family": "Helvetica"})
# 1. tandem
T = json.load(open(f"{S}/tandem/tandem_summary.json"))
B = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
series = [("TOA (L1C), water", "TOA water ratio C/A", "#2b6ca3"), ("TOA (L1C), land", "TOA land ratio C/A", "#9aa7b3"),
          ("Production L2A, water", "BOA (production L2A) water ratio C/A", "#d1772b"), ("ACOLITE, water", "ACOLITE water ratio C/A", "#6a9a3d")]
fig, ax = plt.subplots(figsize=(9.5, 4.2))
x = np.arange(len(B)); w = 0.2
for i, (lab, key, col) in enumerate(series):
    m = [T["bands"][b][key]["median"] if T["bands"][b].get(key) else np.nan for b in B]
    lo = [T["bands"][b][key]["ci95"][0] if T["bands"][b].get(key) else np.nan for b in B]
    hi = [T["bands"][b][key]["ci95"][1] if T["bands"][b].get(key) else np.nan for b in B]
    ax.errorbar(x + (i - 1.5) * w, m, yerr=[np.array(m) - np.array(lo), np.array(hi) - np.array(m)], fmt="o", ms=5, color=col, capsize=2, label=lab)
ax.axhline(1, color="#333", lw=0.8); ax.axhspan(0.97, 1.03, color="#dfe9f3", zorder=0, label="±3% band")
ax.set_xticks(x, B); ax.set_ylabel("Sentinel-2C / Sentinel-2A (same water, 27–32 s apart)")
ax.set_ylim(0.3, 1.65); ax.legend(ncol=3, fontsize=8, frameon=False, loc="upper left")
ax.set_title("Tandem pairs, 12 scenes, December 2024: median of per-scene medians, scene-bootstrap 95% CI", fontsize=10)
fig.tight_layout(); fig.savefig(f"{F}/tandem_bands.png", dpi=170); plt.close(fig)
# 2. decomposition by Secchi class
A = json.load(open(f"{S}/analysis/part_a.json"))
cl = ["clear >=6", "normal 3-6", "stained 2-3", "limited <2"]
rad = [-0.637 * A["by_secchi_class_dt0"][c]["median_eT"] for c in cl]; con = [A["by_secchi_class_dt0"][c]["median_eC"] for c in cl]
tot = [A["by_secchi_class_dt0"][c]["median_eS"] for c in cl]; n = [A["by_secchi_class_dt0"][c]["n"] for c in cl]
fig, ax = plt.subplots(figsize=(7.5, 3.8)); x = np.arange(len(cl))
ax.bar(x - 0.2, rad, 0.35, color="#2b6ca3", label="radiometric term, −0.637·e_T (satellite FNU vs in-situ turbidity)")
ax.bar(x + 0.2, con, 0.35, color="#d1772b", label="conversion term, e_C (champion formula on in-situ turbidity)")
ax.plot(x, tot, "kD", ms=6, label="champion Secchi error, e_S")
ax.axhline(0, color="#333", lw=0.8)
ax.set_xticks(x, [f"{c.replace('>=', '≥ ').replace('<', '< ')} ft\n(n {k})" for c, k in zip(cl, n)])
ax.set_ylabel("median log10 error (+ = reads clearer than truth)"); ax.legend(fontsize=8, frameon=False, loc="upper left"); ax.set_ylim(-0.3, 0.45)
ax.set_title("Where the champion's Secchi error comes from (same-day rows, 216 lakes)", fontsize=10)
fig.tight_layout(); fig.savefig(f"{F}/decomposition_by_class.png", dpi=170); plt.close(fig)
# 3. per-state models
E = json.load(open(f"{S}/analysis/part_de.json"))
st = ["clear", "algal", "sediment", "mixed"]; mods = ["champion", "P1", "C3", "C6", "P1-NIR"]; cols = ["#555", "#2b6ca3", "#d1772b", "#e3b23c", "#9aa7b3"]
fig, ax = plt.subplots(figsize=(8, 3.8)); x = np.arange(len(st)); w = 0.16
for i, (m, c) in enumerate(zip(mods, cols)):
    v = [E["E_by_state"][s][m].get("median_abs_log", np.nan) for s in st]
    ax.bar(x + (i - 2) * w, v, w, color=c, label=m)
ax.set_xticks(x, [f"{s}\n(n {E['E_state_counts'].get(s, 0)})" for s in st]); ax.set_ylabel("median |log10 error|, held-out lakes")
ax.set_ylim(0, 0.9); ax.legend(ncol=5, fontsize=8, frameon=False, loc="upper center")
ax.set_title("Models inside each satellite-observed water type (5 lake-group folds)", fontsize=10)
fig.tight_layout(); fig.savefig(f"{F}/models_by_state.png", dpi=170); plt.close(fig)
# 4. AERONET (if present)
p = f"{S}/analysis/part_b_aeronet.json"
if os.path.exists(p):
    Bj = json.load(open(p))
    procs = ["Sen2Cor (production)", "ACOLITE (water/cloud mask)", "C2RCC-Nets", "C2X-Nets"]; col = ["#d1772b", "#6a9a3d", "#2b6ca3", "#8a5bb8"]
    fig, axs = plt.subplots(1, 4, figsize=(12, 3.4))
    for ax, b in zip(axs, ["B02", "B03", "B04", "B05"]):
        mx = 0
        for pr, c in zip(procs, col):
            pts = [(r["truth"][b], r["proc"][pr][b]) for r in Bj["rows"] if r["truth"].get(b) and (r["proc"].get(pr) or {}).get(b) is not None]
            if pts:
                t, v = zip(*pts); ax.scatter(t, v, s=10, color=c, alpha=0.7, label=pr.replace(" (production)", "").replace(" (water/cloud mask)", ""))
                mx = max(mx, max(t), max(v))
        ax.plot([0, mx], [0, mx], "k-", lw=0.7); ax.set_title(b, fontsize=10); ax.set_xlabel("AERONET-OC ρw")
        if b == "B02": ax.set_ylabel("satellite ρw")
    axs[0].legend(fontsize=7, frameon=False)
    fig.suptitle("Atmospheric-correction paths against AERONET-OC Level 2.0 (5 sites, ±60 min)", fontsize=10)
    fig.tight_layout(); fig.savefig(f"{F}/aeronet_scatter.png", dpi=170); plt.close(fig)
print(sorted(os.listdir(F)))
