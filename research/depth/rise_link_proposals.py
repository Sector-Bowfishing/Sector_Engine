"""Datum proposals for Reclamation RISE lakes whose RISE elevation was shown (rise_storage_link.py) to sit on the survey table's project datum, and whose pool figure is in that
frame (TSC survey statement; for Great Plains lakes with an allocation diagram, exact capacity matches by reclamation_pool_frame.py). Writes proposals/datum_pairings_5.json."""
import json, os, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
LINK = json.load(open(f"{ROOT}/docs/brains/depth/data/rise_storage_link.json"))["results"]
FRAME = json.load(open(f"{ROOT}/docs/brains/depth/data/reclamation_pool_frame.json"))["results"]
RULE = [r for r in json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/proposals/provider_rules.json"))["rules"] if r["provider"] == "rise" and r["decision"] == "SAME_DATUM"][0]
CANDS = {c["lakeId"]: c for c in json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]}
TIER_A = set(RULE["lakes"])
TSC = "https://www.usbr.gov/tsc/techreferences/reservoir/"
URL = {"CheneyReservoir2015AreaCapacityTables_Final508.pdf": "CheneyReservoir2015AreaCapacityTables_Final508.pdf", "BighornReservoirAreaCapacityTables2017_Final508.pdf": "BighornReservoirAreaCapacityTables2017_Final508.pdf",
       "ElVado2018_tables.pdf": "ElVadoReservoir2018AreaAndCapacityTables_Final(508).pdf", "Elephant_Butte_Reservoir_2017_&_2019_Area_and_Capacity_Tables.pdf": "Elephant Butte Reservoir 2017 & 2019 Area and Capacity Tables.pdf",
       "Heron_Reservoir_2010_Capacity_Tables.pdf": "Heron Reservoir 2010 Capacity Tables.pdf", "NavajoReservoir2019AreaCapacityTables_final508VI.pdf": "NavajoReservoir2019AreaCapacityTables_final508VI.pdf",
       "Swanson_Reservoir_2011_Capacity_Tables.pdf": "Swanson Reservoir 2011 Capacity Tables.pdf", "Edward_Arthur_Patterson_CapacityTable_2013.pdf": "Edward_Arthur_Patterson CapacityTable 2013.pdf",
       "Lake_Tschida_2013_Capacity_Tables.pdf": "Lake Tschida 2013 Capacity Tables.pdf", "Calamus_2012_Area-Capacity_table_final.pdf": "Calamus 2012 Area-Capacity table_final.pdf"}
RESALOC = {"Calamus Reservoir|NE": "https://www.usbr.gov/gp/aop/resaloc/calamus.pdf", "Swanson Reservoir|NE": "https://www.usbr.gov/gp/aop/resaloc/swanson_lake.pdf",
           "Lake Tschida|ND": "https://www.usbr.gov/gp/aop/resaloc/lake_tschida.pdf", "Patterson Lake|ND": "https://www.usbr.gov/gp/aop/resaloc/dickinson.pdf"}


def main():
    out = {}
    for lake, r in LINK.items():
        if not r.get("passes") or lake == "Cheney Reservoir|KS" or lake not in CANDS:
            continue
        c = CANDS[lake]
        ev = [{"url": TSC + urllib.parse.quote(URL[r["table"]]), "says": f"Reclamation TSC area-capacity tables ({r['tableForm']}) in the project vertical datum; RISE daily elevation reproduces RISE daily storage through this table "
                                                                          f"(best datum offset {r['bestOffsetFt']:+.2f} ft, relative RMS {r['relRmsAtBest']}, n {r['n']}, {r['window'][0]}..{r['window'][1]})"},
              {"url": "docs/brains/depth/data/rise_storage_link.json", "says": "storage-consistency fit for this lake (research/depth/rise_storage_link.py)"},
              {"url": f"https://data.usbr.gov/rise/api/catalog-item/{r['riseElevationItem']}", "says": "RISE daily Lake/Reservoir Elevation item bound by Lake Brain"},
              {"url": f"https://data.usbr.gov/rise/api/catalog-item/{r['riseStorageItem']}", "says": "RISE daily Lake/Reservoir Storage item at the same location"}]
        for e in RULE["evidence"]:
            if e["says"].startswith(lake.split("|")[0]):
                ev.append({"url": e["url"], "says": e["says"]})
        fr = FRAME.get(lake)
        if fr and fr["poolPairMatches"]:
            ev.append({"url": RESALOC[lake], "says": "allocation diagram elevation/capacity pairs equal the table's capacity at those elevations (" + ", ".join(f"{p['elevFt']} ft = {int(p['diagramAf'])} af" for p in fr["pairs"]) + "): the pool figure is in the table's frame"})
        tier_a = lake in TIER_A
        out[lake] = {"decision": "SAME_SOURCE", "group": "RISE-storage-link", "levelDatum": None, "referenceDatum": None, "method": "operator-doc", "confidence": "high" if tier_a else "medium", "sigmaFt": 0.1,
                     "summary": ("RISE elevation, the survey table and the pool figure are one Reclamation project vertical datum: the RISE elevation reproduces RISE storage through the survey table with offset "
                                 f"{r['bestOffsetFt']:+.2f} ft; the pool figure is stated in that datum" + (" and equals a capacity-matched allocation-diagram elevation." if fr and fr["poolPairMatches"] else " by the TSC survey report.")),
                     "evidence": ev,
                     "caveat": "Project vertical datum: shift only, never converted to NGVD29/NAVD88. Fit tolerance |offset| <= 0.10 ft and relative RMS <= 0.005 was fixed after the first six fits were read."}
    json.dump({"schema": "depth-datum-proposals-v1", "generatedAt": "2026-10-14", "sigmaRule": "0.1 ft (provider rule precedent for project datums)", "lakes": out},
              open(f"{ROOT}/jobs/depth-brain/depth_brain/data/proposals/datum_pairings_5.json", "w"), indent=1)
    print(len(out), list(out))


main()
