"""Pool figure <-> TSC table frame check. Reclamation's reservoir-allocation diagrams (Great Plains `resaloc`) print `Elev. E (C Acre-Feet)` pairs for the dead, inactive, active-conservation,
flood and surcharge levels. If the table's capacity at E equals C, the diagram's elevations (the pool figure Depth uses is its `Top of Active Conservation` / spillway elevation) are in the
frame of the table, to well under 0.01 ft (1 ft is thousands of acre-feet). Run with: PYTHONPATH=<datum4/w2/pylib> /opt/homebrew/bin/python3 reclamation_pool_frame.py"""
import json, os, re
from pypdf import PdfReader

D3 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3")
D5 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../docs/brains/depth/data/reclamation_pool_frame.json")
CASES = {  # lake: (diagram pdf, table file, directory pool ft)
    "Calamus Reservoir|NE": (D3 + "/pdf/https___www_usbr_gov_gp_aop_resaloc_calamus_pdf.pdf", "Calamus_2012_Area-Capacity_table_final.pdf", 2244.0),
    "Swanson Reservoir|NE": (D5 + "/dl/swanson_resaloc.pdf", "Swanson_Reservoir_2011_Capacity_Tables.pdf", 2752.0),
    "Bighorn Lake|WY": (D3 + "/pdf/https___www_usbr_gov_gp_aop_resaloc_bighorn_lake_pdf.pdf", "BighornReservoirAreaCapacityTables2017_Final508.pdf", 3640.0),
    "Lake Tschida|ND": (D3 + "/pdf/https___www_usbr_gov_gp_aop_resaloc_lake_tschida_pdf.pdf", "Lake_Tschida_2013_Capacity_Tables.pdf", 2064.5),
    "Patterson Lake|ND": (D3 + "/pdf/https___www_usbr_gov_gp_aop_resaloc_dickinson_pdf.pdf", "Edward_Arthur_Patterson_CapacityTable_2013.pdf", 2420.0),
}
PAIR = re.compile(r"Elev\.?\s*([\d,]+(?:\.\d+)?)\s*\(\s*([\d,]+)\s*Acre")


def main():
    eqs = json.load(open(D5 + "/tsc_equations.json")); tabs = json.load(open(D5 + "/tsc_tables.json"))
    res = {}
    for lake, (dg, tf, pool) in CASES.items():
        txt = "\n".join((p.extract_text() or "") for p in PdfReader(dg).pages)
        txt = re.sub(r"[ ]+", " ", txt)
        pairs = [(float(a.replace(",", "")), float(b.replace(",", ""))) for a, b in PAIR.findall(txt)]
        if tf in eqs:
            rows = eqs[tf]["rows"]
            def cap(E):
                r = [x for x in rows if x[1] <= E]
                if not r or E > rows[-1][1] + 1:
                    return None
                r = r[-1]; x = E - r[1]; return r[3] + r[4] * x + r[5] * x * x
        else:
            cp = {float(k): v for k, v in tabs[tf]["cap"].items()}
            ks = sorted(cp)
            def cap(E):
                if E < ks[0] or E > ks[-1]:
                    return None
                lo = max(k for k in ks if k <= E); hi = min(k for k in ks if k >= E)
                return cp[lo] if hi == lo else cp[lo] + (E - lo) / (hi - lo) * (cp[hi] - cp[lo])
        chk = []
        for E, C in pairs:
            c = cap(E)
            if c is not None:
                chk.append({"elevFt": E, "diagramAf": C, "tableAf": round(c), "relDiff": round((c - C) / max(C, 1), 5)})
        res[lake] = {"diagram": os.path.basename(dg), "table": tf, "poolFt": pool, "pairs": chk,
                     "poolPairMatches": any(abs(x["elevFt"] - pool) < 0.05 and abs(x["relDiff"]) <= 0.005 for x in chk),
                     "maxAbsRelDiff": max((abs(x["relDiff"]) for x in chk), default=None)}
        print(lake, res[lake]["poolPairMatches"], res[lake]["maxAbsRelDiff"], len(chk), flush=True)
    json.dump({"schema": "depth-reclamation-pool-frame-v1", "results": res}, open(OUT, "w"), indent=1)


main()
