#!/usr/bin/env python3
"""Step 3b (group 4, USGS-served lakes). For every DATUM_UNKNOWN lake whose live level is a USGS series:
  * pull one year of USGS iv for the bound parameter and every sibling elevation parameter at the same site (00062, 62614, 62615, 72020);
    compare at identical UTC instants (offset = bound - sibling) to establish what a 00062 series is at that site (T1 trap) and the site's NGVD29/NAVD88 shift;
  * where the pool is a CWMS location level (Thurmond, W.F. George), also pair the USGS series with the CWMS series for the same pool (Hartwell pattern);
  * 00065 gage height is never used as an elevation (reported as unusable).
Read-only. Output <cache>/usgs_lakes.json
Run: venv python -I research/depth/datum_pair_usgs_lakes.py"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datum_pair_common import *
from datum_pair_usgs import compare

REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption")
CAND = json.load(open(f"{REPO}/jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]
BIND = {r["lake_id"]: r for r in csv.DictReader(open(os.path.expanduser("~/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/verified_bindings_v2.csv")))}
POOL = {r["id"]: r for r in csv.DictReader(open(f"{REPO}/docs/data/full_pool.csv"))}
SIB = ["00062", "62614", "62615", "72020"]
# CWMS series that carry the same pool as the USGS gauge (Hartwell pattern); office, tsid chosen from the SAS/SAM catalogs
CWMS_PARTNER = {
    "Clarks Hill / J.S. Thurmond|GA": ("SAS", "Thurmond.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS", "Thurmond"),
    "Lake Strom Thurmond (Clarks Hill)|SC": ("SAS", "Thurmond.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS", "Thurmond"),
    "Walter F. George / Eufaula|GA": ("SAM", "WalterFGeorge.Elev.Inst.1Hour.0.Raw-USGS", "WalterFGeorge"),
    "Eufaula / W.F. George|AL": ("SAM", "WalterFGeorge.Elev.Inst.1Hour.0.Raw-USGS", "WalterFGeorge"),
    "Kerr Reservoir (Buggs Island)|VA": ("SAW", "ROA JHK.Elev.Inst.5Minutes.0.USGS-raw", "ROA JHK"),
}


# Independent USGS gauge on the same pool with a datum-defined parameter (anchor): lake -> (site, param). Different gauge = independent measurement.
ANCHORS = {"Walter F. George / Eufaula|GA": ("0234296910", "62614"), "Eufaula / W.F. George|AL": ("02343240", "00062")}


def main():
    end = pd.Timestamp.now(tz="UTC").normalize(); begin = end - pd.Timedelta(days=365)
    out = {}
    for c in CAND:
        if "DATUM_UNKNOWN" not in c["blockedReasons"] or c["levelSource"]["provider"] not in ("usgs", "usgs-d"):
            continue
        lid = c["lakeId"]; b = BIND[lid]; site = b["station"]; param = b["series_or_param"].split("+")[0]
        rec = {"lake": lid, "provider": c["levelSource"]["provider"], "site": site, "param": param, "poolFt": c["reference"]["poolFt"], "poolSource": (POOL.get(lid) or {}).get("source"), "series": {}, "cwmsPartner": None}
        if param == "00065":
            rec["note"] = "00065 gage height is not an elevation; no pairing attempted"; out[lid] = rec; continue
        data = {}
        for p in dict.fromkeys([param] + SIB):
            s, _, urls = usgs_series(site, p, begin, end, "iv")
            if s is not None and len(s):
                data[p] = s; rec["series"][p] = {"n": int(len(s)), "first": str(s.index.min()), "last": str(s.index.max()), "lastValue": float(s.iloc[-1]), "url": urls[0] if urls else None}
        rec["siblingOffsets"] = {}
        if param in data:
            for p, s in data.items():
                if p == param:
                    continue
                j = compare(data[param], s, tol_min=3)
                if len(j) >= 100:
                    rec["siblingOffsets"][p] = offset_stats(j["usgs"] - j["cwms"])   # (sibling - bound)
        # siblings among themselves (site shift 62615-62614)
        if "62615" in data and "62614" in data:
            j = compare(data["62614"], data["62615"], tol_min=3)
            if len(j) >= 100:
                rec["siteShift62615minus62614"] = offset_stats(j["usgs"] - j["cwms"])
        if lid in ANCHORS and param in data:
            asite, aparam = ANCHORS[lid]
            a, _, aurls = usgs_series(asite, aparam, begin, end, "iv")
            if a is not None and len(a) >= 100:
                j = compare(data[param], a, tol_min=3)
                if len(j) >= 100:
                    rec["anchor"] = {"site": asite, "param": aparam, "paramDatum": {"62614": "NGVD29", "62615": "NAVD88"}.get(aparam), "n": int(len(j)), "url": aurls[0] if aurls else None,
                                     "offset_anchor_minus_bound": offset_stats(j["usgs"] - j["cwms"])}
        if lid in CWMS_PARTNER and param in data:
            off, tsid, loc = CWMS_PARTNER[lid]
            cw, meta, curls = cwms_series(off, tsid, begin.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"))
            lr = cwms("locations/" + loc.replace(" ", "%20"), office=off)
            rec["cwmsPartner"] = {"office": off, "tsid": tsid, "n": 0 if cw is None else int(len(cw)), "locationDatum": ((lr.get("data") or {}).get("vertical-datum")), "locationUrl": lr.get("_url"), "urls": curls[:2],
                                  "circular": "usgs" in tsid.lower(), "vdi": (meta or {}).get("vertical-datum-info")}
            if cw is not None and len(cw) >= 100:
                j = compare(cw, data[param], tol_min=7)
                if len(j) >= 20:
                    rec["cwmsPartner"]["offset_usgs_minus_cwms"] = offset_stats(j["usgs"] - j["cwms"])
        out[lid] = rec
        print(lid, param, {p: v["n"] for p, v in rec["series"].items()}, {p: (v.get("meanFt"), v.get("sdFt")) for p, v in rec["siblingOffsets"].items()}, (rec["cwmsPartner"] or {}).get("offset_usgs_minus_cwms", {}).get("meanFt"), flush=True)
    json.dump(out, open(f"{ROOT}/usgs_lakes.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
