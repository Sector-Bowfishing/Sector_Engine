import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, datetime as dt, warnings, json
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pathlib import Path
import score_lib as SL
H = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
cmap = ListedColormap(["white", "#cfe3f2", "#2e7d32", "#9e9e9e", "#ffb74d", "#8e24aa", "#212121", "#e53935", "#e53935"])
def code_img(st):
    m = np.zeros(st.shape, int); m[st == SL.CLEAR] = 1; m[st == SL.FLAG] = 2
    for c, k in ((SL.SHORE, 3), (SL.CLOUD, 4), (SL.NODATA, 4), (SL.HAZE, 5), (SL.DARK, 6), (SL.NOSCENE, 7), (SL.NOTACC, 7)): m[st == c] = k
    return m
fig, ax = plt.subplots(2, 5, figsize=(17, 9))
for r, nm in enumerate(["Roesiger", "Storm"]):
    z = np.load(H/f"out/cells50_snoco_{nm}.npz", allow_pickle=True); z = {k: z[k] for k in z.files}; ref = dt.date.fromisoformat(str(z["survey"]))
    sc = SL.prep(z, "v1", False)
    tf = np.nan_to_num(z["truth_floating_leaf"]); a = ax[r, 0]; a.imshow(np.where(z["lake"], 1, 0), cmap="Blues", vmin=0, vmax=2); a.imshow(np.ma.masked_where(tf < 0.5, tf), cmap="Greens", vmin=0, vmax=1.2); a.set_title(f"{nm}: truth floating-leaf >= 0.5 (survey {ref})", fontsize=9)
    for j, o in enumerate("SAP"):
        st, info = SL.OBS[o](z, sc, ref); ax[r, 1 + j].imshow(code_img(st), cmap=cmap, vmin=0, vmax=8, interpolation="nearest")
        ax[r, 1 + j].set_title(f"{o} (v1): {info.get('kind')} gap {info.get('gap')}d", fontsize=9)
    st, info = SL.observer_A(z, SL.prep(z, "prod", False), ref)
    ax[r, 4].imshow(code_img(st), cmap=cmap, vmin=0, vmax=8, interpolation="nearest"); ax[r, 4].set_title("A, bare production (no prereg guards)", fontsize=9)
for a in ax.ravel(): a.set_xticks([]); a.set_yticks([])
import matplotlib.patches as mp
fig.legend(handles=[mp.Patch(color=c, label=l) for c, l in zip(["#cfe3f2", "#2e7d32", "#9e9e9e", "#ffb74d", "#8e24aa", "#212121", "#e53935"], ["CLEAR", "FLAG (plant)", "SHORE_ADJACENT", "CLOUD/NO DATA", "HAZE/CLOUD-EDGE standoff", "DARK_WATER", "NO_SCENE/NOT_ACCEPTED"])], loc="lower center", ncol=7, fontsize=9)
plt.tight_layout(rect=(0, 0.04, 1, 1)); plt.savefig(H/"figs/snoco_Roesiger_Storm_SAP.png", dpi=110)
# PAC scatter
r = json.load(open(H/"out/pac_50_prod_rej1.json")); fig, ax = plt.subplots(1, 3, figsize=(14, 4))
rows = r["rows"]["S"]
x = [q["PVI"] for q in rows]; y = [100*q["share"] for q in rows]
ax[0].scatter(x, y, s=14); ax[0].set_xlabel("sonar PVI (%)"); ax[0].set_ylabel("observer S plant share of known cells (%)"); ax[0].set_title("bare production S, gate off (n=%d)" % len(rows))
r2 = json.load(open(H/"out/pac_50_v1_rej0.json")); rows2 = r2["rows"]["S"]
ax[1].scatter([q["PVI"] for q in rows2], [100*q["share"] for q in rows2], s=14, c="C1"); ax[1].set_xlabel("sonar PVI (%)"); ax[1].set_title("v1 guards as written, S, gate on (n=%d)" % len(rows2))
ax[2].bar(["bare prod S", "bare prod S\ngate off", "v1 S", "v1 A", "v1fix S", "v1fix A"], [r["observers"]["S"]["all"]["n"] if False else v for v in [
    json.load(open(H/"out/pac_50_prod_rej0.json"))["observers"]["S"]["all"]["n"], r["observers"]["S"]["all"]["n"], r2["observers"]["S"]["all"]["n"], r2["observers"]["A"]["all"]["n"],
    json.load(open(H/"out/pac_50_v1fix_rej0.json"))["observers"]["S"]["all"]["n"], json.load(open(H/"out/pac_50_v1fix_rej0.json"))["observers"]["A"]["all"]["n"]]])
ax[2].set_title("lake-years the observer could score (of 143)"); plt.tight_layout(); plt.savefig(H/"figs/pac_lake_level.png", dpi=110)
print("ok")
