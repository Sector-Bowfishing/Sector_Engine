"""Systematic USGS live scan (binding2): for every lake still unbound after wave 1 (and every flagged / stage-only lake, for a second origin),
ask the NWIS instantaneous-values service for ALL live lake-elevation (00062, 62614, 62615, 62616, 72020, 72022) and gage-height (00065) series inside a bounding box
around the lake polygon (+0.08 deg) for the last 30 days, then read the gage datum altitude from the site service (siteOutput=expanded) and emit candidates in the binding2 SPEC format.
No relaxed geometry here; distances are computed centrally in verify2.py. Output: cand/usgs_scan.jsonl"""
import csv, json, collections, statistics, datetime as dt, urllib.parse
from common2 import *
from providers import summarize
from match import load_polys

ELEV = ["00062", "62614", "62615", "62616", "72020", "72022"]
TARGET_STATUS = ("NONE", "VERIFIED_FLAG", "STAGE_ONLY")


def targets():
    out = []
    for r in csv.DictReader(open(f"{BIND}/verified.csv")):
        if r["bindingStatus"] in TARGET_STATUS:
            out.append(r["lakeId"])
    return out


def fetch_iv(bbox):
    u = ("https://waterservices.usgs.gov/nwis/iv/?format=json&bBox=%.4f,%.4f,%.4f,%.4f&parameterCd=%s&period=P30D&siteStatus=all" % (*bbox, ",".join(ELEV + ["00065"])))
    s, d = get_json(u, timeout=120, sleep=0.8)
    return s, d


def site_info(ids):
    out = {}
    for i in range(0, len(ids), 20):
        s, b = http_get("https://waterservices.usgs.gov/nwis/site/?format=rdb&siteOutput=expanded&sites=" + ",".join(ids[i:i + 20]), timeout=90, sleep=0.5)
        if s != 200:
            continue
        hdr = None
        for ln in b.splitlines():
            if ln.startswith("#") or not ln.strip():
                continue
            p = ln.split("\t")
            if hdr is None:
                hdr = p; continue
            if p[0].endswith("s") and p[0][:-1].isdigit():
                continue
            r = dict(zip(hdr, p)); out[r["site_no"]] = r
    return out


def main():
    lakes = {l["id"]: l for l in load_directory()}
    polys = load_polys()
    found = collections.defaultdict(dict)   # (lakeId) -> site -> param -> pts
    meta = {}
    for n, lid in enumerate(targets()):
        l = lakes[lid]
        if lid in polys:
            minx, miny, maxx, maxy = polys[lid].bounds
        else:
            minx, maxx, miny, maxy = l["lon"] - .05, l["lon"] + .05, l["lat"] - .05, l["lat"] + .05
        pad = 0.08
        bbox = (round(minx - pad, 4), round(miny - pad, 4), round(maxx + pad, 4), round(maxy + pad, 4))
        if (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) > 20:
            bbox = (l["lon"] - 1, l["lat"] - 1, l["lon"] + 1, l["lat"] + 1)
        s, d = fetch_iv(bbox)
        if not d:
            print(lid, "status", s); continue
        for ts in d["value"]["timeSeries"]:
            si = ts["sourceInfo"]; site = si["siteCode"][0]["value"]; par = ts["variable"]["variableCode"][0]["value"]
            nd = ts["variable"].get("noDataValue", -999999)
            pts = []
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        x = float(v["value"])
                    except Exception:
                        continue
                    if x == nd:
                        continue
                    pts.append((dt.datetime.fromisoformat(v["dateTime"]).timestamp(), x))
            if pts:
                found[lid].setdefault(site, {}).setdefault(par, []).extend(pts)
                meta[site] = (si["siteName"], si["geoLocation"]["geogLocation"]["latitude"], si["geoLocation"]["geogLocation"]["longitude"])
        if n % 25 == 0:
            print(n, lid, len(found[lid]), flush=True)
    sites = sorted({s for v in found.values() for s in v})
    info = site_info(sites)
    out = open(f"{B2}/cand/usgs_scan.jsonl", "w")
    cnt = 0
    for lid, ss in found.items():
        for site, pars in ss.items():
            ep = {p: v for p, v in pars.items() if p in ELEV}
            gh = pars.get("00065")
            inf = info.get(site, {})
            name, lat, lon = meta[site]
            try:
                alt = float(inf.get("alt_va") or "")
            except ValueError:
                alt = None
            rec = dict(lakeId=lid, prov="usgs2", origin="usgs", relay=False, station=site, stationName=name, lat=lat, lon=lon, stype=inf.get("site_tp_cd", ""), vdatum=(inf.get("alt_datum_cd") or "").strip() or "unknown",
                       unit="ft", apiUrl="https://waterservices.usgs.gov/nwis/iv/?bBox=...&parameterCd=ELEV+00065&period=P30D", pageUrl=f"https://waterdata.usgs.gov/monitoring-location/{site}/", altVa=alt, altAcy=inf.get("alt_acy_va"))
            if ep:
                par, pts = max(ep.items(), key=lambda kv: (summarize(kv[1])["last_t"], summarize(kv[1])["n"]))
                sm = summarize(pts)
                out.write(json.dumps({**rec, "series": par, "family": "elev", "lastObs": sm["last_t"], "ageH": sm["age_h"], "n30": sm["n"], "medFt": sm["med_ft"], "lastFt": sm["last_ft"], "histPath": None, "notes": "absolute elevation parameter"}) + "\n"); cnt += 1
            if gh and alt not in (None, 0.0) and rec["vdatum"] in ("NAVD88", "NGVD29", "NAD83", "NAVD88 "):
                sm = summarize(gh)
                # derived elevation = gage height + gage datum altitude (flagged class: derived, not published as an elevation)
                out.write(json.dumps({**rec, "series": "00065+alt_va", "family": "elev", "derived": True, "lastObs": sm["last_t"], "ageH": sm["age_h"], "n30": sm["n"],
                                      "medFt": round(sm["med_ft"] + alt, 3), "lastFt": round(sm["last_ft"] + alt, 3), "stageMedFt": sm["med_ft"], "histPath": None,
                                      "notes": "derived = 00065 gage height + alt_va (gage datum altitude); calibration: binding2/usgs_stage_calibration.json"}) + "\n"); cnt += 1
    out.close()
    print("candidates written:", cnt, "lakes with any live series:", len(found))


if __name__ == "__main__":
    main()
