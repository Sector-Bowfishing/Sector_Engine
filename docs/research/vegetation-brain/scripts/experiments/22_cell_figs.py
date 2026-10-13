import sys, numpy as np, importlib, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
M = importlib.import_module("12_cell_metrics")
fig, ax = plt.subplots(2, 4, figsize=(17, 8.5))
for r, nm in enumerate(["Roesiger", "Storm"]):
    z = np.load(ROOT/f"out/cell_snoco_{nm}.npz", allow_pickle=True); m, i0, N, d0, good, votes, info = M.methods(z, 45)
    lake = z["lake"]; fl = np.nan_to_num(z["truth_floating_leaf"])
    ys, xs = np.where(lake); sl = (slice(ys.min()-2, ys.max()+3), slice(xs.min()-2, xs.max()+3))
    def show(a, t, k):
        img = np.where(lake, a.astype(float), np.nan); ax[r, k].imshow(img[sl], cmap="Greens", vmin=0, vmax=1); ax[r, k].set_title(t, fontsize=9); ax[r, k].axis("off")
    show(fl, f"{nm}: mapped floating-leaf (cell share)", 0)
    show(m["single (closest clear date)"], f"Sector cell vote, closest clear date {d0}", 1)
    show(m["SHIPPED pass (cov>=0.5, closest to survey)"], f"Sector, shipped-style pass {info['ship']} (cov {info['cov_ship']})", 2)
    show(m["median g' >= 0.5"], f"median of {N} dates, g'>=0.5", 3)
plt.tight_layout(); plt.savefig(ROOT/"out/figures/cell_snoco_Roesiger_Storm.png", dpi=105)
