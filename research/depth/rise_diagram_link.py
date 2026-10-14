"""RISE elevation <-> allocation-diagram frame check, no table needed. Reclamation's allocation diagram prints (elevation, capacity) pairs; RISE publishes daily elevation AND
storage. Where the RISE (elevation, storage) cloud passes through a printed capacity, the RISE elevation at that capacity should equal the printed elevation when RISE and the diagram
are in one vertical frame. dE = (RISE elevation interpolated at the printed capacity) - (printed elevation). A frame offset d would show up as dE = d.
RULE (the nearby-days window is the most recent 60 days, adopted after the control lake Tschida failed with a pooled window; fixed before reading the first results; the 'after the diagram revision' window was added after the three-year run left most pairs outside the observed range): pass = at least one printed pair inside the observed RISE range with >= 8 nearby daily points, and every such pair has |dE| <= 0.10 ft.
Control: Calamus, Swanson, Tschida, Patterson (frame already shown by their survey tables). Output: docs/brains/depth/data/rise_diagram_link.json"""
import json, os
import numpy as np
import pandas as pd
from datum_pair_common import get_json
R3 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/rise/")
D5 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5")
OUT = os.path.join(os.path.dirname(__file__), "../../docs/brains/depth/data/rise_diagram_link.json")
H = {"Accept": "application/vnd.api+json"}
MAP = {"angostura": "Angostura Reservoir|SD", "box_butte": "Box Butte Reservoir|NE", "boysen": "Boysen Reservoir|WY", "buffalo_bill": "Buffalo Bill Reservoir|WY", "fresno": "Fresno Reservoir|MT",
       "glendo": "Glendo Reservoir|WY", "horsetooth": "Horsetooth Reservoir|CO", "jamestown": "Jamestown Reservoir|ND", "keyhole": "Keyhole Reservoir|WY", "lake_granby": "Lake Granby|CO",
       "merritt": "Merritt Reservoir|NE", "pactola": "Pactola Reservoir|SD", "pathfinder": "Pathfinder Reservoir|WY", "ruedi": "Ruedi Reservoir|CO",
       "calamus": "Calamus Reservoir|NE", "swanson_resaloc": "Swanson Reservoir|NE", "lake_tschida": "Lake Tschida|ND", "dickinson": "Patterson Lake|ND"}
CONTROL = {"Calamus Reservoir|NE", "Swanson Reservoir|NE", "Lake Tschida|ND", "Patterson Lake|ND"}


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
    for dlt in (-1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -8, 8, -10, 10, -12, 12):
        r = get_json(f"https://data.usbr.gov/rise/api/catalog-item/{int(sid) + dlt}", {}, headers=H)
        a = (((r or {}).get("data") or {}).get("data") or {}).get("attributes")
        if a and a.get("parameterId") == 3 and a.get("locationSourceCode") == loc_src and a.get("parameterTimestep") == "daily":
            return a["_id"], a.get("parameterUnit")
    return None, None


def main():
    items = {i["lake"]: i for i in json.load(open(R3 + "rise_items.json"))}
    pairs = json.load(open(D5 + "/resaloc_pairs.json"))
    res = {}
    for key, lake in MAP.items():
        fn = [k for k in pairs if k.endswith(f"resaloc_{key}_pdf.pdf") or k == f"{key}.pdf"]
        if not fn or lake not in items:
            continue
        it = items[lake]; sid, unit = storage_item(it["sid"], it["locSrc"])
        if not sid:
            res[lake] = {"error": "no daily storage item"}; continue
        rev = pairs[fn[0]]["revised"]
        try:
            rd = pd.to_datetime(rev, format="%m/%d/%y" if len(rev.split("/")[-1]) == 2 else "%m/%d/%Y") + pd.Timedelta(days=30) if rev else None
        except Exception:
            rd = None
        # only days AFTER the diagram's revision (+30 d): RISE storage then comes from the table the revised diagram describes; no revision date -> the last three years
        after = (rd if rd is not None else pd.Timestamp.now() - pd.Timedelta(days=1100)).strftime("%Y-%m-%d")
        j = pd.concat([results(it["sid"], after).rename("e"), results(sid, after).rename("s")], axis=1).dropna()
        S = j.s * (1000.0 if unit == "taf" else 1.0)
        rec = {"control": lake in CONTROL, "diagram": fn[0], "revised": pairs[fn[0]]["revised"], "afterDate": after, "riseStorageItem": sid, "days": int(len(j)), "pairs": []}
        for E, C in pairs[fn[0]]["pairs"]:
            near = j[(S - C).abs() <= 0.02 * C + 5] if C > 0 else j.iloc[0:0]
            if len(near) < 8 or not (S.min() < C < S.max()):
                rec["pairs"].append({"printedElevFt": E, "printedAf": C, "status": "outside observed range" if not (S.min() < C < S.max()) else f"only {len(near)} nearby days"}); continue
            near = near.sort_index().iloc[-60:]                  # the most recent 60 nearby days: the table in force now (pooling all days after the revision mixed table versions at the control lake Tschida)
            sl, ic = np.polyfit(S[near.index].values, near.e.values, 1)
            eh = sl * C + ic
            rec["pairs"].append({"printedElevFt": E, "printedAf": C, "n": int(len(near)), "window": [near.index.min(), near.index.max()], "riseElevAtCapacityFt": round(float(eh), 3), "dEFt": round(float(eh - E), 3)})
        use = [p for p in rec["pairs"] if "dEFt" in p]
        rec["passes"] = bool(use) and all(abs(p["dEFt"]) <= 0.10 for p in use)
        res[lake] = rec
        print(lake, "CONTROL" if lake in CONTROL else "", rec["passes"], [(p["printedElevFt"], p.get("dEFt", p.get("status"))) for p in rec["pairs"]], flush=True)
    json.dump({"schema": "depth-rise-diagram-link-v1", "generatedAt": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%MZ"), "results": res}, open(OUT, "w"), indent=1)


main()
