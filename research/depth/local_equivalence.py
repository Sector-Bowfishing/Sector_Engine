"""LOCAL == NGVD29 numerically, per lake, from the paired-series results (datum2/usgs_pairs.json): the A2W/CWMS series carries a LOCAL project tag, an independent-looking USGS series on
the same pool is NGVD29/NAVD88 by parameter definition (62614/72020 -> NGVD29, 62615 -> NAVD88), and the two agree at the datum an NAVD88 relationship would not (NAVD88-NGVD29 is 0.3-1+ ft).
Gate (proposals.py): n >= 20, |mean| <= 0.10 ft, SD <= 0.25 ft, not circular (the CWMS version does not name USGS). Writes depth_brain/data/local_datum_equivalence.json."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
UP = json.load(open(os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum2/usgs_pairs.json")))
CANDS = {c["lakeId"]: c for c in json.load(open(f"{HERE}/../../jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]}
SHIFT = {c["id"] if "id" in c else None: c for c in []}
out = {}
for lid, v in UP.items():
    c = CANDS.get(lid)
    if not c or (c["reference"].get("datum") or "") != "LOCAL" or v.get("circularIfUsgsGauge"):
        continue
    for p in v.get("pairs", []):
        st, pd_ = p.get("stats") or {}, p.get("paramDatum")
        if pd_ in ("NGVD29", "NAVD88") and st.get("n", 0) >= 20 and abs(st.get("meanFt", 9)) <= 0.10 and st.get("sdFt", 9) <= 0.25:
            out[lid] = {"localEquals": pd_, "usgsSite": p["site"], "usgsParam": p["param"], "km": p.get("km"), "n": st["n"], "meanFt": st["meanFt"], "sdFt": st["sdFt"], "quarterMeanRangeFt": st.get("quarterMeanRangeFt"),
                        "window": st.get("window"), "url": p.get("usgsUrl")}
            break
json.dump({"schema": "depth-local-datum-equivalence-v1", "gate": "n>=20, |mean|<=0.10 ft, SD<=0.25 ft, not circular", "lakes": out}, open(f"{HERE}/../../jobs/depth-brain/depth_brain/data/local_datum_equivalence.json", "w"), indent=1)
print(len(out), list(out))
