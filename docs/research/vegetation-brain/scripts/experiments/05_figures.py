import sys, json, glob, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import roc_curve
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import importlib; M = importlib.import_module("04_metrics"); s2lib = M.s2lib
FIG = ROOT/"out"/"figures"; FIG.mkdir(exist_ok=True)

def maps(mode, lakes):
    for nm in lakes:
        p = ROOT/"out"/f"stack_{mode}_{nm}.npz"
        if not p.exists(): continue
        d = M.load(str(p), mode, "single")
        if d is None: continue
        use, neg, cl = M.pixels(d, mode)
        fig, ax = plt.subplots(1, 3, figsize=(15, 5))
        rgb = None
        z = np.load(p, allow_pickle=True)
        ax[0].imshow(np.where(d["valid"], d["F"]["NDVI"], np.nan), vmin=-0.2, vmax=0.8, cmap="RdYlGn"); ax[0].set_title(f"{nm} NDVI  {d['info']}")
        L = np.zeros(d["lake"].shape + (3,)); L[d["lake"]] = (0.8, 0.8, 0.8)
        L[cl["submerged"]] = (0.2, 0.4, 0.9); L[cl["surface"]] = (0.9, 0.5, 0.1)
        ax[1].imshow(L); ax[1].set_title("ground truth: orange=surface, blue=submerged, grey=unmapped")
        pred = M.SECTOR(d["F"]); P = np.zeros(d["lake"].shape + (3,)); P[d["lake"]] = (0.8, 0.8, 0.8); P[pred & d["valid"] & (d["lake"] | cl["surface"])] = (0.1, 0.7, 0.2)
        ax[2].imshow(P); ax[2].set_title("Sector rule NDVI>=0.30 (green)")
        for a in ax: a.axis("off")
        plt.tight_layout(); plt.savefig(FIG/f"map_{mode}_{nm}.png", dpi=110); plt.close()

def roc_and_bars(mode):
    r = json.load(open(ROOT/"out"/f"metrics_{mode}.json"))["pooled"]
    for variant in r:
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
        for j, g in enumerate(["surface", "submerged"]):
            c = r[variant]["classes"].get(g)
            if not c: continue
            ks = list(c["idx"]); au = [c["idx"][k]["AUC"] for k in ks]
            ax[j].barh(ks, au, color="#3a7"); ax[j].axvline(0.5, c="k", lw=.5); ax[j].set_xlim(0.3, 1)
            ax[j].set_title(f"{mode} {variant}: {g} AUC (n_pos={c['n_pos']})")
        plt.tight_layout(); plt.savefig(FIG/f"auc_{mode}_{variant}.png", dpi=110); plt.close()

if __name__ == "__main__":
    mode = sys.argv[1]
    names = [Path(p).stem.split(f"stack_{mode}_")[1] for p in glob.glob(str(ROOT/"out"/f"stack_{mode}_*.npz"))]
    maps(mode, names); roc_and_bars(mode)
