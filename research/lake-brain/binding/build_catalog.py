"""Normalise the raw provider catalogs into one series table: binding/catalog.jsonl.
Each record: prov, sid (stable series id), station, name, lat, lon, stype, family(elev|stage|storage), param, unit,
datum, begin, end, count, step(dv|iv|hourly|daily...), extra{}."""
import csv, glob, io, json, os, re, sys
from common import *

ELEV = {"00062", "62614", "62615", "62616", "72020", "72022"}
STORAGE = {"72036", "00054"}


def parse_rdb(path):
    rows, hdr = [], None
    for ln in open(path, errors="replace"):
        if ln.startswith("#") or ln.startswith("<"):
            continue
        p = ln.rstrip("\n").split("\t")
        if hdr is None:
            hdr = p
            continue
        if re.match(r"^\d+[sdn]$", p[0]):
            continue
        rows.append(dict(zip(hdr, p)))
    return rows


def usgs_records():
    out = []
    for f in sorted(glob.glob(f"{RAW}/usgs/*.rdb")):
        lkfile = os.path.basename(f).startswith("lk_")
        for r in parse_rdb(f):
            if r["data_type_cd"] not in ("dv", "uv", "iv") or not r["parm_cd"]:
                continue
            pc = r["parm_cd"]
            if pc in ELEV:
                fam = "elev"
            elif pc in STORAGE:
                fam = "storage"
            elif pc == "00065" and r["site_tp_cd"] == "LK":
                fam = "stage"
            else:
                continue
            try:
                lat, lon = float(r["dec_lat_va"]), float(r["dec_long_va"])
            except ValueError:
                continue
            out.append(dict(prov="usgs", sid=f"usgs:{r['site_no']}:{pc}:{r['data_type_cd']}:{r['stat_cd'] or 'inst'}", station=r["site_no"],
                            name=r["station_nm"], lat=lat, lon=lon, stype=r["site_tp_cd"], family=fam, param=pc,
                            unit="ft" if fam != "storage" else "af", datum=(r["alt_datum_cd"] or "").strip(), begin=r["begin_date"], end=r["end_date"],
                            count=int(r["count_nu"] or 0), step={"dv": "daily", "uv": "iv", "iv": "iv"}[r["data_type_cd"]],
                            extra=dict(alt=r["alt_va"].strip(), stat=r["stat_cd"])))
    # de-dup (a site can appear in both lk_ and ot_ files)
    seen, res = set(), []
    for x in out:
        if x["sid"] in seen:
            continue
        seen.add(x["sid"]); res.append(x)
    return res


def cwms_records():
    out = []
    for lf in sorted(glob.glob(f"{RAW}/cwms/loc_*.json")):
        off = os.path.basename(lf)[4:-5]
        locs = {}
        for e in json.load(open(lf))["entries"]:
            locs[e["name"]] = e
        tf = f"{RAW}/cwms/ts_{off}.json"
        if not os.path.exists(tf):
            continue
        for e in json.load(open(tf))["entries"]:
            nm = e["name"]
            parts = nm.split(".")
            if len(parts) < 6:
                continue
            loc, param = parts[0], parts[1]
            base = loc.split("-")[0]
            L = locs.get(loc) or locs.get(base) or {}
            ex = (e.get("extents") or [{}])[0]
            fam = "elev" if param.startswith("Elev") else "storage" if param.startswith("Stor") else "stage" if param.startswith("Stage") else "other"
            out.append(dict(prov="cwms", sid=f"cwms:{off}:{nm}", station=off, name=L.get("long-name") or L.get("public-name") or loc, lat=L.get("latitude"), lon=L.get("longitude"),
                            stype=L.get("type") or L.get("kind"), family=fam, param=param, unit=e.get("units"), datum=L.get("vertical-datum"),
                            begin=(ex.get("earliest-time") or "")[:10], end=(ex.get("latest-time") or "")[:10], count=None,
                            step=parts[3], extra=dict(loc=loc, version=parts[5], ptype=parts[2], state=L.get("state"), kind=L.get("kind"), locelev=L.get("elevation"), active=L.get("active"))))
    return out


def rise_records():
    locs = {}
    for l in json.load(open(f"{RAW}/rise/locations.json")):
        a = l["attributes"]
        c = (a.get("locationCoordinates") or {}).get("coordinates") or [None, None]
        locs[a["_id"]] = dict(name=a["locationName"], lon=c[0], lat=c[1], elev=a.get("elevation"), datum=((a.get("verticalDatum") or {}).get("_id")))
    out = []
    for it in json.load(open(f"{RAW}/rise/catalog_items_level.json")):
        a = it["attributes"]
        pn = a.get("parameterName") or ""
        fam = "elev" if "elevation" in pn.lower() else "storage" if "storage" in pn.lower() else "stage" if "stage" in pn.lower() else "other"
        # locationId may be inside relationships
        lid = None
        for ci in (a.get("catalogRecords") or []):
            pass
        loc_id = (a.get("locationId") or (a.get("locationSourceCode")))
        out.append(dict(prov="rise", sid=f"rise:{a['_id']}", station=str(a["_id"]), name=a.get("itemTitle"), lat=None, lon=None, stype="RES", family=fam,
                        param=pn, unit=a.get("parameterUnit"), datum=(a.get("verticalDatum") or {}).get("_id") if isinstance(a.get("verticalDatum"), dict) else a.get("verticalDatum"),
                        begin=(a.get("temporalStartDate") or "")[:10], end=(a.get("temporalEndDate") or "")[:10], count=None, step=a.get("parameterTimestep"),
                        extra=dict(model=a.get("isModeled"), src=a.get("sourceCode"), locsrc=a.get("locationSourceCode"), keys=[k for k in a.keys()][:0])))
    return out, locs


def rise_records2():
    locs = {}
    for l in json.load(open(f"{RAW}/rise/locations.json")):
        a = l["attributes"]
        c = ((a.get("locationCoordinates") or {}).get("coordinates") or [None, None]) + [None, None]
        st = [x["id"].rsplit("/", 1)[1] for x in (l["relationships"].get("states") or {}).get("data", [])]
        locs[a["_id"]] = dict(name=a["locationName"], lon=c[0], lat=c[1], elev=a.get("elevation"), datum=((a.get("verticalDatum") or {}).get("_id")), type=a.get("locationTypeName"), states=st, projects=a.get("projectNames"))
    i2l = json.load(open(f"{RAW}/rise/item2loc.json"))
    out = []
    for it in json.load(open(f"{RAW}/rise/catalog_items_level.json")):
        a = it["attributes"]
        pn = a.get("parameterName") or ""
        if pn not in ("Lake/Reservoir Elevation", "Lake/Reservoir Storage"):
            continue
        if a.get("isModeled"):
            continue
        L = locs.get(i2l.get(str(a["_id"])))
        if not L or L["lat"] is None:
            continue
        out.append(dict(prov="rise", sid=f"rise:{a['_id']}", station=str(a["_id"]), name=L["name"], lat=L["lat"], lon=L["lon"], stype=L["type"],
                        family="elev" if "Elevation" in pn else "storage", param=pn, unit=a.get("parameterUnit"), datum=L["datum"] or "",
                        begin=(a.get("temporalStartDate") or "")[:10], end=(a.get("temporalEndDate") or "")[:10], count=None, step="daily",
                        extra=dict(src=a.get("sourceCode"), locsrc=a.get("locationSourceCode"), states=L["states"], title=a.get("itemTitle"), projects=L["projects"])))
    return out


def twdb_records():
    d = json.load(open(f"{RAW}/twdb/recent-conditions.json"))
    out = []
    for k, v in d.items():
        g = (v.get("gauge_location") or {}).get("coordinates") or [None, None]
        if v.get("elevation") is None or g[0] is None:
            continue
        out.append(dict(prov="twdb", sid=f"twdb:{k}", station=k, name=v.get("full_name") or k, lat=g[1], lon=g[0], stype="RES", family="elev", param="water_level",
                        unit="ft", datum="NGVD29?", begin="", end=v.get("timestamp") or "", count=None, step="daily",
                        extra=dict(conservation_pool=v.get("conservation_pool_elevation"), elevation=v.get("elevation"), flood=v.get("flood_control_lake"), dead=v.get("dead_pool_elevation"), tags=v.get("tags"))))
    return out


def nwps_records():
    out = []
    for g in json.load(open(f"{RAW}/nwps/gauges_all.json"))["gauges"]:
        pe = ((g.get("pedts") or {}).get("observed") or "")[:2]
        nm = g["name"]
        poolish = pe == "HP" or (pe == "HG" and re.search(r"\b(lake|reservoir|res)\b", nm, re.I) and not re.search(r"\b(below|near|nr|abv|above|outlet|tailwater)\b", nm, re.I))
        if not poolish or g.get("latitude") is None:
            continue
        out.append(dict(prov="nwps", sid=f"nwps:{g['lid']}", station=g["lid"], name=nm, lat=g["latitude"], lon=g["longitude"], stype=pe, family="elev" if pe == "HP" else "stage",
                        param=(g["pedts"] or {}).get("observed"), unit=(g["status"]["observed"] or {}).get("primaryUnit") or "ft", datum="", begin="", end=((g["status"]["observed"] or {}).get("validTime") or "")[:10],
                        count=None, step="iv", extra=dict(state=g["state"]["abbreviation"], last=(g["status"]["observed"] or {}).get("primary"), rfc=(g.get("rfc") or {}).get("abbreviation"))))
    return out


def tva_records():
    out = []
    p = f"{RAW}/tva/locations.json"
    if not os.path.exists(p):
        return out
    for x in json.load(open(p)):
        out.append(dict(prov="tva", sid=f"tva:{x['LocationID']}", station=x["LocationID"], name=x["Name"], lat=x["Lat"], lon=x["Long"], stype="DAM", family="elev", param="ReservoirElevation",
                        unit="ft", datum="", begin="", end="", count=None, step="hourly", extra=dict(dam=x.get("DamType"), owner=x.get("Ownership"), river=x.get("River"), topOfGates=x.get("TopOfGatesFt"))))
    return out


def a2w_records():
    out = []
    for lf in sorted(glob.glob(f"{RAW}/a2w/locations_*.json")):
        for x in json.load(open(lf)):
            g = (x.get("geometry") or {}).get("coordinates")
            if not g:
                continue
            lv = {l["label"] + "|" + l["parameter"]: l["latest_value"] for l in (x.get("levels") or []) if l["parameter"] == "Elev"}
            for t in x.get("timeseries") or []:
                p = t["parameter"]
                if not p.startswith("Elev") or re.match(r"Elev-(Tail|Down|Lower|Out)", p):
                    continue
                if re.search(r"(tail|below|down|dnstr|\btw\b|-tw\b|outlet|outflow|lower)", t["tsid"].split(".")[0], re.I):
                    continue   # trap: plain 'Elev' on a tailwater/below-dam location
                if not re.match(r"^(Elev|Elev-Pool|Elev-Forebay|Elev-Lake|Elev-Headwater|Elev-Upper|Elev-Reservoir)$", p):
                    continue
                out.append(dict(prov="a2w", sid=f"a2w:{x['provider']}:{t['tsid']}", station=f"{x['provider']}:{x['code']}", name=x["public_name"], lat=g[1], lon=g[0], stype=x["kind"], family="elev",
                                param=p, unit=t["unit"], datum=x.get("vertical_datum") or "", begin="", end=(t.get("latest_time") or "")[:10], count=None, step=t["tsid"].split(".")[3] if t["tsid"].count(".") >= 5 else "",
                                extra=dict(loc=x["code"], provider=x["provider"], state=x.get("state"), nidid=(x.get("aliases") or {}).get("NIDID") or x.get("nidid"), latest_time=t.get("latest_time"), latest_value=t.get("latest_value"), levels=lv, tsid=t["tsid"])))
    return out


def coops_records():
    out = []
    for s in json.load(open(f"{RAW}/coops/stations_waterlevels.json"))["stations"]:
        if not s.get("greatlakes"):
            continue
        out.append(dict(prov="coops", sid=f"coops:{s['id']}", station=s["id"], name=s["name"], lat=s["lat"], lng=None, lon=s["lng"], stype="GL", family="elev", param="water_level_IGLD85",
                        unit="ft", datum="IGLD85", begin="", end="", count=None, step="6min", extra=dict(state=s.get("state"))))
    return out


if __name__ == "__main__":
    recs = usgs_records() + cwms_records() + (rise_records2() if os.path.exists(f"{RAW}/rise/item2loc.json") else []) + twdb_records() + tva_records() + a2w_records() + nwps_records() + coops_records()
    with open(f"{BIND}/catalog.jsonl", "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    import collections
    print(collections.Counter((r["prov"], r["family"]) for r in recs))
