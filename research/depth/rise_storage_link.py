"""RISE elevation <-> storage consistency against Reclamation TSC capacity tables (read-only GETs; cached outside git).
Idea: Reclamation computes the published daily storage from the published daily elevation with its capacity table. If the RISE elevation series is on the table's datum,
table(RISE elevation) reproduces RISE storage; a datum offset d shows up as storage(E) = table(E + d). Fit d by least squares over d in [-3, 3] ft (0.01 ft grid) and report the
residual. d near 0 with a small residual means the RISE elevation is on the table's (project) datum - the residual link in the RPVD document chain.
Output: docs/brains/depth/data/rise_storage_link.json"""
import json, os, sys
import numpy as np
import pandas as pd
from datum_pair_common import get_json

R3 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/rise/")
TAB = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5/tsc_tables.json")
OUT = os.path.join(os.path.dirname(__file__), "../../docs/brains/depth/data/rise_storage_link.json")
H = {"Accept": "application/vnd.api+json"}
EQ = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5/tsc_equations.json")
MAP = {  # lake -> the survey table whose datum the RISE elevation is tested against (newest parsed; equation form preferred, 1-ft table otherwise)
    "Cheney Reservoir|KS": "CheneyReservoir2015AreaCapacityTables_Final508.pdf",
    "Bighorn Lake|WY": "BighornReservoirAreaCapacityTables2017_Final508.pdf",
    "El Vado Lake|NM": "ElVado2018_tables.pdf",
    "Elephant Butte Reservoir|NM": "Elephant_Butte_Reservoir_2017_&_2019_Area_and_Capacity_Tables.pdf",
    "Flaming Gorge Reservoir|UT": "FlamingGorgeRes2019AreaCapacityTables_final508.pdf",
    "Heron Lake|NM": "Heron_Reservoir_2010_Capacity_Tables.pdf",
    "Jamestown Reservoir|ND": "Jamestown_Reservoir_2009_Capacity_Tables.pdf",
    "Navajo Reservoir|NM": "NavajoReservoir2019AreaCapacityTables_final508VI.pdf",
    "Fresno Reservoir|MT": "Fresno_Reservoir_2010_Area_and_Capatity_Tables.pdf",
    "Swanson Reservoir|NE": "Swanson_Reservoir_2011_Capacity_Tables.pdf",
    "Blue Mesa Reservoir|CO": "BlueMesaReservoir2019AreaAndCapacityTables_Final508.pdf",
    "Patterson Lake|ND": "Edward_Arthur_Patterson_CapacityTable_2013.pdf",
    "Lake Tschida|ND": "Lake_Tschida_2013_Capacity_Tables.pdf",
    "Calamus Reservoir|NE": "Calamus_2012_Area-Capacity_table_final.pdf",
}
# RULE (fixed when the first six fits were read; disclosed in the rules doc): the RISE elevation is on the table's datum when |best offset| <= 0.10 ft AND the relative RMS at the best offset <= 0.005
PASS_OFFSET_FT, PASS_REL_RMS = 0.10, 0.005


def cap_area_curves(pdf, tabs, eqs):
    """-> (elev grid, capacity af, area ac) at 0.1 ft steps from the equation form (exact) or the 1-ft tables (linear)."""
    if pdf in eqs:
        rows = eqs[pdf]["rows"]
        lo, hi = rows[0][1], rows[-1][1] + 1.0
        grid = np.arange(lo, hi, 0.1)
        bases = np.array([r[1] for r in rows])
        idx = np.clip(np.searchsorted(bases, grid, side="right") - 1, 0, len(rows) - 1)
        x = grid - bases[idx]
        A1, A2, A3 = (np.array([r[k] for r in rows])[idx] for k in (3, 4, 5))
        return grid, A1 + A2 * x + A3 * x * x, A2 + 2 * A3 * x
    t = tabs[pdf]
    e = np.array(sorted(float(k) for k in t["cap"]))
    grid = np.arange(e.min(), e.max(), 0.1)
    cap = np.interp(grid, e, [t["cap"][str(int(k))] for k in e])
    ea = np.array(sorted(float(k) for k in t["area"]))
    return grid, cap, np.interp(grid, ea, [t["area"][str(int(k))] for k in ea])


def results(item, after):
    out, page = [], 1
    while True:
        r = get_json("https://data.usbr.gov/rise/api/result", {"itemId": item, "dateTime[after]": after, "itemsPerPage": 500, "page": page}, headers=H)
        d = r.get("data") if isinstance(r, dict) else None
        if not d or "data" not in d:
            break
        out += [(x["attributes"]["dateTime"][:10], x["attributes"]["result"]) for x in d["data"] if x["attributes"]["result"] is not None]
        if len(d["data"]) < 500:
            break
        page += 1
    return pd.Series(dict(out)).sort_index()


def storage_item(sid, loc_src):
    """The daily storage item shares the location source code with the elevation item and sits next to it in the RISE catalog; every neighbour is verified, never assumed."""
    out = []
    for dlt in (-1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -8, 8, -10, 10, -12, 12):
        r = get_json(f"https://data.usbr.gov/rise/api/catalog-item/{int(sid) + dlt}", {}, headers=H)
        d = (r or {}).get("data")
        a = ((d or {}).get("data") or {}).get("attributes") if d else None
        if a and a.get("parameterId") == 3 and a.get("locationSourceCode") == loc_src and a.get("parameterTimestep") == "daily":
            out.append({"_id": a["_id"], "parameterUnit": a.get("parameterUnit"), "title": a.get("itemTitle")})
    return out


def main():
    items = {i["lake"]: i for i in json.load(open(R3 + "rise_items.json"))}
    locs = json.load(open(R3 + "rise_records_locations.json"))
    tabs = json.load(open(TAB)); eqs = json.load(open(EQ))
    after = (pd.Timestamp.now() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    res = {}
    for lake, pdf in MAP.items():
        it = items[lake.split("#")[0]]; loc_id = locs[it["sid"]]["loc"]["_id"]
        if pdf not in tabs and pdf not in eqs:
            res[lake] = {"error": "table not parsed"}; continue
        ce, cv, _ = cap_area_curves(pdf, tabs, eqs)
        st = storage_item(it['sid'], it['locSrc'])
        if not st:
            res[lake] = {"error": "no daily storage item at the location", "locationId": loc_id}; continue
        elev = results(it["sid"], after); stor = results(st[0]["_id"], after)
        j = pd.concat([elev.rename("e"), stor.rename("s")], axis=1).dropna()
        j = j[(j.e >= ce.min() + 0.5) & (j.e <= ce.max() - 0.5) & (j.s > 0)]
        if len(j) < 60:
            res[lake] = {"error": f"only {len(j)} joined days in the table range", "storageItem": st[0]["_id"]}; continue
        unit = st[0].get("parameterUnit")
        scale = 1000.0 if unit == "taf" else 1.0
        S = j.s.values * scale
        ds = np.arange(-3.0, 3.0001, 0.01)
        rms = [float(np.sqrt(np.mean((np.interp(j.e.values + d, ce, cv) - S) ** 2))) for d in ds]
        k = int(np.argmin(rms)); k0 = int(np.argmin(np.abs(ds)))
        rel = lambda x: x / float(np.mean(S))
        res[lake] = {"table": pdf, "tableForm": "equations" if pdf in eqs else "1-ft table", "riseElevationItem": it["sid"], "riseStorageItem": st[0]["_id"], "storageUnit": unit, "n": int(len(j)), "window": [j.index.min(), j.index.max()],
                     "elevRangeFt": [round(float(j.e.min()), 2), round(float(j.e.max()), 2)], "meanStorageAf": round(float(np.mean(S)), 0),
                     "bestOffsetFt": round(float(ds[k]), 2), "rmsAtBestAf": round(rms[k], 1), "rmsAtZeroAf": round(rms[k0], 1), "relRmsAtZero": round(rel(rms[k0]), 5), "relRmsAtBest": round(rel(rms[k]), 5),
                     "rmsAtMinusOneFt": round(rms[int(np.argmin(np.abs(ds + 1.0)))], 1), "rmsAtPlusOneFt": round(rms[int(np.argmin(np.abs(ds - 1.0)))], 1)}
        res[lake]["passes"] = abs(res[lake]["bestOffsetFt"]) <= PASS_OFFSET_FT and res[lake]["relRmsAtBest"] <= PASS_REL_RMS
        print(lake, {x: res[lake][x] for x in ("n", "bestOffsetFt", "relRmsAtZero", "relRmsAtBest", "passes")}, flush=True)
    json.dump({"schema": "depth-rise-storage-link-v1", "generatedAt": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%MZ"), "results": res}, open(OUT, "w"), indent=1)


main()
