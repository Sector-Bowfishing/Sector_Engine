"""Datum proposals for Great Plains / Rocky Mountain Reclamation lakes whose pool figure is printed on the allocation diagram (the pool source) and whose RISE elevation reproduces the diagram's
printed capacities (rise_diagram_link.py; controls with survey tables pass at <= 0.003 ft). Writes proposals/datum_pairings_6.json."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..", "..")
LINK = json.load(open(f"{ROOT}/docs/brains/depth/data/rise_diagram_link.json"))["results"]
CANDS = {c["lakeId"]: c for c in json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]}
PAIRS = json.load(open(os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5/resaloc_pairs.json")))
URL = {"swanson_resaloc.pdf": "https://www.usbr.gov/gp/aop/resaloc/swanson_lake.pdf"}


def main():
    out = {}
    for lake, r in LINK.items():
        if r.get("control") or not r.get("passes") or lake not in CANDS:
            continue
        c = CANDS[lake]; P = c["reference"]["poolFt"]
        printed = [p for p in PAIRS[r["diagram"]]["pairs"]]
        if not any(abs(P - e) < 0.05 for e, _ in printed) or not str(c["reference"].get("source", "")).startswith("https://www.usbr.gov/gp/aop/resaloc/"):
            continue                                              # the pool must BE a printed diagram elevation, otherwise the diagram says nothing about it
        used = [p for p in r["pairs"] if "dEFt" in p]
        sid = c["levelSource"]["series"]
        out[lake] = {"decision": "SAME_SOURCE", "group": "RISE-diagram-link", "levelDatum": None, "referenceDatum": None, "method": "operator-doc", "confidence": "high", "sigmaFt": 0.1,
                     "summary": ("Pool figure is a printed elevation of Reclamation's allocation diagram; RISE daily elevation reproduces RISE daily storage at the diagram's printed capacity "
                                 f"({', '.join(str(p['printedElevFt']) + ' ft = ' + format(int(p['printedAf']), ',') + ' af: ' + format(p['dEFt'], '+.3f') + ' ft' for p in used)}), so RISE and the pool are in one Reclamation vertical frame."),
                     "evidence": [{"url": c["reference"]["source"], "says": f"allocation diagram (revised {r['revised']}) prints pool {P} ft and its capacity; the Depth reference pool IS this diagram's elevation"},
                                  {"url": f"https://data.usbr.gov/rise/api/catalog-item/{sid}", "says": "RISE daily Lake/Reservoir Elevation item bound by Lake Brain"},
                                  {"url": f"https://data.usbr.gov/rise/api/catalog-item/{r['riseStorageItem']}", "says": "RISE daily Lake/Reservoir Storage item at the same location"},
                                  {"url": "docs/brains/depth/data/rise_diagram_link.json", "says": "fit of RISE elevation at the printed capacity (research/depth/rise_diagram_link.py); controls Calamus, Tschida and Patterson reproduce their survey-table frame at <= 0.003 ft"}],
                     "caveat": "Project vertical frame: shift only, never converted. The test shows RISE elevation and the diagram share a frame, not the frame's name. " + ("The 2010 TSC table for Fresno does not reproduce RISE storage (-0.27 ft, 1.5% RMS), so the table behind the diagram/RISE is a later one." if lake.startswith("Fresno") else "")}
    json.dump({"schema": "depth-datum-proposals-v1", "generatedAt": "2026-10-14", "sigmaRule": "0.1 ft (provider rule precedent for project datums)", "lakes": out}, open(f"{ROOT}/jobs/depth-brain/depth_brain/data/proposals/datum_pairings_6.json", "w"), indent=1)
    print(len(out), list(out))


main()
