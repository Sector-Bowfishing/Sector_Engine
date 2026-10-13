#!/usr/bin/env python3
"""Step 2: CWMS-native datum pairing. For each USACE-served lake: (a) confirm the live level series exists in the public CWMS Data API
under the same tsid as Access2Water shows and that the values agree at the same instants; (b) read the CWMS `vertical-datum` of the level
series' location; (c) resolve the reference-pool figure to a CWMS location level (or note that it is a document, not a CWMS level), confirm the
pool figure equals the level's value, and read the vertical-datum of the level's location; (d) apply the decision rule.
Read-only GETs, cached under ~/Desktop/Development/Sector_Research_Data/depth-brain/datum2/http_cache.
Output: <cache>/cwms_pairs.json  (consumed by datum_pair_build.py)
Run: venv python -I research/depth/datum_pair_cwms.py"""
import csv, datetime as dt, json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datum_pair_common import *

REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption")
CAND = {c["lakeId"]: c for c in json.load(open(f"{REPO}/jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]}
POOL = {r["id"]: r for r in csv.DictReader(open(f"{REPO}/docs/data/full_pool.csv"))}
BIND = {r["lake_id"]: r for r in csv.DictReader(open(os.path.expanduser("~/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/verified_bindings_v2.csv")))}
A2WS = json.load(open(f"{ROOT}/a2w_series.json"))
SERIES_OFFICES = {"NWO": ["NWDM", "NWO"], "NWK": ["NWDM", "NWK"], "NWS": ["NWDP", "NWS"], "NWW": ["NWDP", "NWW"], "NWP": ["NWDP", "NWP"], "MVP": ["MVP"]}
UNKNOWN_DATUM = (None, "", "null")

_loc_cache = {}


def location(office, name):
    k = (office, name)
    if k not in _loc_cache:
        r = cwms(f"locations/{urllib.parse.quote(name, safe='')}", office=office)
        d = r.get("data") if isinstance(r, dict) else None
        _loc_cache[k] = ({"office": office, "name": name, "verticalDatum": d.get("vertical-datum"), "kind": d.get("location-kind") or d.get("location-type"), "elevation": d.get("elevation"),
                          "elevationUnits": d.get("elevation-units"), "publicName": d.get("public-name"), "lat": d.get("latitude"), "lon": d.get("longitude"), "url": r.get("_url")} if d else
                         {"office": office, "name": name, "error": r.get("error") if isinstance(r, dict) else "?", "url": r.get("_url") if isinstance(r, dict) else None})
    return _loc_cache[k]


def ts_values(office, tsid, begin, end, unit="ft"):
    r = cwms("timeseries", office=office, name=tsid, begin=begin, end=end, unit=unit)
    d = r.get("data") if isinstance(r, dict) else None
    if not d or "values" not in d:
        return None, r
    return d, r


def parse_pool_source(src):
    """-> dict(kind, loc, level, office, mask, note). kind in cwms-level / cwms-url / cwms-ts-url / doc / tva-zone / none"""
    s = (src or "").strip()
    if not s:
        return {"kind": "none"}
    if s.startswith("USACE published pool, inside TVA"):
        return {"kind": "tva-zone"}
    if s.startswith("http"):
        u = urllib.parse.urlparse(s); q = urllib.parse.parse_qs(u.query)
        if "cwms-data.usace.army.mil" in u.netloc and u.path.endswith("/levels"):
            return {"kind": "cwms-url", "office": (q.get("office") or [None])[0], "mask": (q.get("level-id-mask") or [None])[0]}
        if "cwms" in u.netloc and u.path.endswith("/timeseries"):
            return {"kind": "cwms-ts-url", "name": (q.get("name") or [None])[0]}
        return {"kind": "doc", "url": s}
    if s.startswith("CWMS "):
        t = s[5:]
        office = None
        m = re.match(r"(NWDM|NWDP|NWD)\s+(.*)", t)
        if m:
            office, t = m.group(1), m.group(2)
        lvl = re.search(r"(Top of [A-Za-z\- ]+?|Guide Curve)(?:\s*[\(/]|\s+max|\s*$)", t)
        loc = re.split(r"\.Elev|\s+Top of|\s+Guide", t)[0].strip()
        return {"kind": "cwms-level", "office": office, "loc": loc, "level": lvl.group(1).strip() if lvl else None, "raw": s}
    return {"kind": "doc", "url": s}


def level_values(l):
    vals = []
    if l.get("constant-value") is not None:
        vals.append(float(l["constant-value"]))
    vals += [float(x["value"]) for x in l.get("seasonal-values", []) if x.get("value") is not None]
    return vals


def find_levels(offices, mask):
    for off in offices:
        r = cwms("levels", office=off, **{"level-id-mask": mask, "unit": "EN"})
        d = r.get("data") if isinstance(r, dict) else None
        if d and d.get("levels"):
            return off, d["levels"], r.get("_url")
    return None, [], None


POOL_LIKE = ("top of conservation", "top of normal", "top of multi-purpose", "top of multipurpose", "top of power", "guide curve", "top of recreation", "top of summer", "top of winter",
             "bottom of flood", "top of conservation pool")


def split_loc(levelid):
    return levelid.split(".")[0]


def search_levels(offices, bases, pool_ft, want_name=None):
    """All CWMS Elev location levels whose location name starts with one of `bases` (masks '<base>*', filtered here because the mask is a glob) and whose
    value (constant or any seasonal) equals the pool figure within 0.06 ft. -> list of hit dicts (deduped)."""
    hits, seen, urls = [], set(), []
    for off in offices:
        for base in bases:
            r = cwms("levels", office=off, **{"level-id-mask": f"{base}*", "unit": "EN"})
            d = r.get("data") if isinstance(r, dict) else None
            if not d or not d.get("levels"):
                continue
            urls.append(r.get("_url"))
            for l in d["levels"]:
                lid = l["location-level-id"]; loc = split_loc(lid)
                if not (loc == base or loc.startswith(base + "-") or loc.startswith(base + "_")):
                    continue
                if not str(l.get("parameter-id", "")).startswith("Elev"):
                    continue
                vals = level_values(l)
                if not any(abs(v - pool_ft) < 0.06 for v in vals):
                    continue
                key = (off, lid, l.get("level-date"))
                if key in seen:
                    continue
                seen.add(key)
                spec = l.get("specified-level-id", "")
                hits.append({"office": off, "levelId": lid, "location": loc, "specifiedLevel": spec, "values": sorted(set(round(v, 3) for v in vals)), "levelDate": l.get("level-date"),
                             "poolLike": any(spec.lower().startswith(x) for x in POOL_LIKE), "nameMatch": bool(want_name) and spec.lower() == want_name.lower(), "url": r.get("_url")})
    return hits, urls


def pool_bases(rec_loc, ps, a2w_code):
    b = []
    for x in [ps.get("loc"), rec_loc, rec_loc.split("-")[0] if rec_loc else None, a2w_code]:
        if x and x not in b:
            b.append(x)
    if ps.get("mask"):
        m = ps["mask"].split(".")[0].rstrip("*")
        if m and m not in b:
            b.append(m)
    return b


def series_for(lid, rec):
    """-> (office list, tsid, a2w latest) for the lake's level series."""
    b = BIND[lid]
    if rec["provider"] == "a2w":
        want = b["series_or_param"]
        cands = [t for t in rec.get("a2wElevSeries", []) if t["parameter"] == want and t["unit"] == "ft"]
        cands.sort(key=lambda t: (t.get("sort_order") is None, t.get("sort_order")))
        office = b["station"].split(":")[0]
        return SERIES_OFFICES.get(office, [office]), (cands[0] if cands else None), cands
    if rec["provider"] == "cwms-saw":
        return [b["station"].split(":")[0]], {"tsid": b["series_or_param"], "latest_time": None, "latest_value": None}, []
    if rec["provider"] == "cwms-nwdp":
        return ["NWDP"], {"tsid": f"{b['station']}.{b['series_or_param']}", "latest_time": None, "latest_value": None}, []
    return [b["station"]], {"tsid": b["series_or_param"], "latest_time": None, "latest_value": None}, []


def main():
    out = {}
    end = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    for lid, rec in A2WS.items():
        c = CAND[lid]; p = POOL.get(lid, {}); pool_ft = float(c["reference"]["poolFt"]) if c["reference"]["poolFt"] is not None else None
        offices, t, alts = series_for(lid, rec)
        o = {"lake": lid, "provider": rec["provider"], "poolFt": pool_ft, "poolSource": p.get("source"), "poolNote": p.get("note"), "alternateElevSeries": [a["tsid"] for a in alts[1:]]}
        if not t:
            o["series"] = {"error": "no A2W Elev series with that parameter"}; out[lid] = o; continue
        tsid = t["tsid"]; o["series"] = {"tsid": tsid, "a2wLatestTime": t.get("latest_time"), "a2wLatestValue": t.get("latest_value")}
        # (a) series exists in CWMS API; compare with A2W latest
        got = None
        for off in offices:
            d, r = ts_values(off, tsid, (end - dt.timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"))
            if d and d.get("values"):
                got = (off, d, r); break
        if got:
            off, d, r = got
            vals = [(v[0], v[1]) for v in d["values"] if v[1] is not None]
            o["series"].update({"cwmsOffice": off, "cwmsUrl": r.get("_url"), "cwmsUnits": d.get("units"), "nRecent": len(vals), "verticalDatumInfo": d.get("vertical-datum-info"), "interval": d.get("interval")})
            if vals and t.get("latest_time"):
                lt = dt.datetime.fromisoformat(t["latest_time"].replace("Z", "+00:00")).timestamp() * 1000
                m = [v for v in vals if abs(v[0] - lt) < 1000]
                if m:
                    o["series"].update({"sameInstantCwmsValue": m[0][1], "sameInstantDiffFt": round(m[0][1] - t["latest_value"], 3)})
            o["seriesLocationName"] = tsid.split(".")[0]
            o["seriesLocation"] = location(off, tsid.split(".")[0])
        else:
            o["series"]["error"] = "tsid not returned by CWMS data API for offices " + ",".join(offices)
            for off in offices:
                loc = location(off, tsid.split(".")[0])
                if loc.get("verticalDatum"):
                    o["seriesLocationName"] = tsid.split(".")[0]; o["seriesLocation"] = loc; break
        # parent / A2W project location datum
        if rec["provider"] == "a2w":
            o["a2wProjectDatum"] = rec["a2wLocation"]["vertical_datum"]; o["a2wProjectCode"] = rec["a2wLocation"]["code"]
        # (c) pool: any CWMS Elev location level at/under the project whose value equals the pool figure
        ps = parse_pool_source(p.get("source")); o["poolSourceKind"] = ps["kind"]
        if pool_ft is not None:
            offs = []
            for x in [ps.get("office") if ps.get("office") not in ("NWD", None) else None, o.get("series", {}).get("cwmsOffice"), c.get("cwmsOffice"), "NWDM" if o["series"].get("cwmsOffice") == "NWDM" else None] + offices:
                if x and x not in offs:
                    offs.append(x)
            if ps["kind"] == "cwms-url" and ps.get("office") and ps["office"] in offs:
                offs.remove(ps["office"]); offs.insert(0, ps["office"])
            code = rec.get("a2wLocation", {}).get("code") if rec["provider"] == "a2w" else None
            bases = pool_bases(o.get("seriesLocationName"), ps, code)
            hits, urls = search_levels(offs, bases, pool_ft, ps.get("level"))
            for h in hits:
                h["locationRecord"] = location(h["office"], h["location"])
            o["poolLevelHits"] = hits
        out[lid] = o
    json.dump(out, open(f"{ROOT}/cwms_pairs.json", "w"), indent=1)
    print(len(out), "lakes")


if __name__ == "__main__":
    main()
