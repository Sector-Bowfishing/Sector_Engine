import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def tab(mode, sfx=""):
    r = json.load(open(ROOT/"out"/f"metrics_{mode}{sfx}.json")); L = []
    for var, o in r["pooled"].items():
        L.append(f"\n#### {mode}{sfx} / {var} (pooled {o['n']:,} px)\n")
        for g, c in o["classes"].items():
            L.append(f"**{g}**: positives {c['n_pos']:,}, background {c['n_neg']:,}, raw prevalence {c['prev']:.4f}\n")
            L.append("| index | AUC raw | AUC shore-matched | best-F1 thr (matched) | P | R | F1 | IoU | LOLO F1 |\n|---|---|---|---|---|---|---|---|---|")
            for k, x in c["idx"].items():
                m = x["matched"]; L.append(f"| {k} | {x['AUC']} | {x['AUC_matched']} | {m['thr']} | {m['P']} | {m['R']} | {m['F1']} | {m['IoU']} | {x['LOLO_matched']['F1']} |")
            L.append("\nSector rules (fixed thresholds), raw prevalence / shore-matched:\n")
            L.append("| rule | P raw | R | F1 raw | IoU raw | P matched | F1 matched | IoU matched |\n|---|---|---|---|---|---|---|---|")
            for k, x in c["sector"].items():
                m = x["matched"]; L.append(f"| {k} | {x['P']} | {x['R']} | {x['F1']} | {x['IoU']} | {m['P']} | {m['F1']} | {m['IoU']} |")
            L.append("")
        L.append("Sector rule false-positive rate on background pixels: " + json.dumps(o.get("sector_FPR_on_background")) + "\n")
        L.append("| subclass | n px | AUC NDVI (m) | AUC NDAVI (m) | AUC FAI (m) | AUC NDRE1 (m) | recall NDVI>=0.30 | recall NDVI>=0.30 or FAI>0.005 |\n|---|---|---|---|---|---|---|---|")
        for n, x in o["subclass"].items():
            L.append(f"| {n} | {x['n_pos']} | {x['AUC_matched_NDVI']} | {x['AUC_matched_NDAVI']} | {x['AUC_matched_FAI']} | {x['AUC_matched_NDRE1']} | {x['recall_sector_ndvi>=0.30']} | {x['recall_sector_ndvi|fai']} |")
    L.append("\n#### per-lake AUC [raw, shore-matched] (NDVI / NDAVI / FAI / NDRE1)\n")
    L.append("| lake | variant | scene(s) | class | NDVI | NDAVI | FAI | NDRE1 |\n|---|---|---|---|---|---|---|---|")
    for lk, v in r["per_lake"].items():
        for var, row in v.items():
            for g, a in row["auc"].items():
                L.append(f"| {lk} | {var} | {row['info']} | {g} | {a['NDVI']} | {a['NDAVI']} | {a['FAI']} | {a['NDRE1']} |")
    return "\n".join(L)
if __name__ == "__main__":
    out = "\n".join([tab("snoco"), tab("fwc"), tab("fwc", "_max3")]); (ROOT/"out"/"tables.md").write_text(out); print(len(out))
