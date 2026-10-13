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


def resolve_pool_level(lake, ps, pool_ft, cwms_office):
    """-> dict with matched CWMS location level(s) or reason."""
    offices = [o for o in [ps.get("office") if ps.get("office") not in ("NWD",) else None, cwms_office, "NWDM"] if o]
    seen, uniq = set(), []
    for o in offices:
        if o not in seen:
            seen.add(o); uniq.append(o)
    if ps["kind"] == "cwms-url":
        mask = ps["mask"]; cand_masks = [mask]; uniq = [ps["office"]] + [o for o in uniq if o != ps["office"]]
    else:
        loc = ps["loc"]
        cand_masks = [f"{loc}.Elev*", f"{loc}.*"]
    for m in cand_masks:
        off, levels, url = find_levels(uniq, m)
        levels = [l for l in levels if str(l.get("parameter-id", "")).startswith("Elev")]
        if not levels:
            continue
        want = (ps.get("level") or "").lower()
        hits = []
        for l in levels:
            lid = l["location-level-id"]; spec = l.get("specified-level-id", "")
            vals = level_values(l)
            val_match = any(abs(v - pool_ft) < 0.06 for v in vals)
            name_match = bool(want) and spec.lower() == want
            if ps["kind"] == "cwms-url":
                # URL points at the whole location; accept any Elev level that equals the pool figure
                if val_match:
                    hits.append((l, "value"))
            elif name_match or (val_match and want and want.split()[-1] in spec.lower()):
                hits.append((l, "name+value" if (name_match and val_match) else ("name" if name_match else "value")))
        if hits:
            out = []
            for l, how in hits:
                out.append({"levelId": l["location-level-id"], "specifiedLevel": l.get("specified-level-id"), "values": sorted(set(round(v, 3) for v in level_values(l))),
                            "levelDate": l.get("level-date"), "match": how, "poolFtMatches": any(abs(v - pool_ft) < 0.06 for v in level_values(l))})
            return {"office": off, "levelsUrl": url, "hits": out}
    return {"office": uniq[0] if uniq else None, "hits": [], "reason": "no CWMS Elev location level matched the pool figure/name"}


def series_for(lid, rec):
    """-> (office list, tsid, a2w latest) for the lake's level series."""
    b = BIND[lid]
    if rec["provider"] == "a2w":
        want = b["series_or_param"]
        cands = [t for t in rec.get("a2wElevSeries", []) if t["parameter"] == want and t["unit"] == "ft"]
        cands.sort(key=lambda t: (t.get("sort_order") is None, t.get("sort_order")))
        office = b["station"].split(":")[0]
        return SERIES_OFFICES.get(office, [office]), (cands[0] if cands else None), cands
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
            o["series"].update({"cwmsOffice": off, "cwmsUrl": r.get("_url"), "cwmsUnits": d.get("units"), "nRecent": len(vals)})
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
        # (c) pool
        ps = parse_pool_source(p.get("source")); o["poolSourceKind"] = ps["kind"]
        if ps["kind"] in ("cwms-level", "cwms-url") and pool_ft is not None:
            pr = resolve_pool_level(lid, ps, pool_ft, c.get("cwmsOffice"))
            o["poolLevel"] = pr
            hits = pr.get("hits") or []
            if hits:
                lvl_loc_name = hits[0]["levelId"].split(".")[0]
                o["poolLevelLocationName"] = lvl_loc_name
                o["poolLevelLocation"] = location(pr["office"], lvl_loc_name)
        out[lid] = o
    json.dump(out, open(f"{ROOT}/cwms_pairs.json", "w"), indent=1)
    print(len(out), "lakes")


if __name__ == "__main__":
    main()
