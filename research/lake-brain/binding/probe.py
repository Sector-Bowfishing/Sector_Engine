"""Phase 2: live probe of the top candidates per lake (actual data queries). Output: binding/probe_results.json"""
import csv, collections, json, sys, datetime as dt
from common import *
from providers import *

MIN_SCORE, PER_LAKE = 40, 5


def load_cands():
    rows = list(csv.DictReader(open(f"{BIND}/candidates_all.csv")))
    by = collections.defaultdict(list)
    for r in rows:
        r["score"] = float(r["score"]); r["alts"] = json.loads(r["alts"]); r["extra"] = json.loads(r["extra"])
        by[r["lakeId"]].append(r)
    sel = []
    for lid, rs in by.items():
        rs.sort(key=lambda x: -x["score"])
        for r in rs[:PER_LAKE]:
            if r["score"] >= MIN_SCORE:
                sel.append(r)
    return sel


def gkey(r):
    return f"{r['prov']}|{r['station']}|{r['stationName'] if r['prov'] in ('rise',) else json.loads(json.dumps(r['extra'])).get('loc','') if r['prov']=='cwms' else ''}"


def probe_usgs(cands, res):
    sites = {}
    for r in cands:
        sites.setdefault(r["station"], r)
    todo = list(sites)
    iv = {}
    # group params per site; batch by identical param-sets
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        ps = sorted({a["series"] if False else a["sid"].split(":")[2] for s in batch for a in sites[s]["alts"] if a["family"] in ("elev", "stage")})
        part = usgs_iv_batch(batch, ps)
        for s, d in part.items():
            iv[s] = d
    for s, r in sites.items():
        alts = [a for a in r["alts"] if a["family"] in ("elev", "stage")]
        best = None
        d = iv.get(s, {})
        for par, pts in d.items():
            sm = summarize(pts)
            if sm["n"] and (best is None or sm["last_t"] > best[1]["last_t"] or (sm["last_t"] == best[1]["last_t"] and sm["n"] > best[1]["n"])):
                best = (par, sm, "iv")
        if best is None:  # dv-only?
            for par in sorted({a["sid"].split(":")[2] for a in alts}):
                pts = usgs_dv_recent(s, par)
                sm = summarize(pts)
                if sm["n"] and (best is None or sm["last_t"] > best[1]["last_t"]):
                    best = (par, sm, "dv")
        res[f"usgs|{s}"] = dict(prov="usgs", station=s, name=r["stationName"], live=bool(best), param=best[0] if best else None, mode=best[2] if best else None,
                                stats=best[1] if best else {"n": 0}, unit="ft", datumSite=r["datum"], altm=r["extra"].get("alt"), stype=r["stype"],
                                family=("stage" if best and best[0] == "00065" else "elev"))


def pref_key(a):
    """CWMS series preference: finer instantaneous, then catalog end date."""
    order = {"1Minute": 0, "5Minutes": 1, "10Minutes": 2, "15Minutes": 3, "20Minutes": 4, "30Minutes": 5, "1Hour": 6, "2Hours": 7, "3Hours": 8, "4Hours": 9, "6Hours": 10, "1Day": 11, "~1Day": 12}
    return (-(a["end"] or ""  and 0), order.get(a["step"], 20))


def probe_cwms(cands, res):
    for r in cands:
        loc = r["extra"]["loc"]
        k = f"cwms|{r['station']}|{loc}"
        if k in res:
            continue
        alts = [a for a in r["alts"] if a["family"] in ("elev", "stage")]
        # eligible: parse sid for name; skip forecast/stat via role check done in match; order by catalog end desc then finer step
        alts.sort(key=lambda a: (a["end"] or "", ), reverse=True)
        alts = alts[:4]
        best = None; tried = []
        for a in alts:
            name = a["sid"].split(":", 2)[2]
            v = cwms_recent(r["station"], name)
            if not v:
                tried.append((name, "err")); continue
            pts = v["pts"]; unit = (v["info"] or {}).get("units") or "ft"
            sm = summarize(pts, unit)
            tried.append((name, sm.get("last_t"), sm.get("n")))
            if sm["n"] and (best is None or sm["last_t"] > best[1]["last_t"] or (sm["last_t"] == best[1]["last_t"] and a["step"] < best[3]["step"])):
                best = (name, sm, (v["info"] or {}).get("vertical-datum-info"), a)
        res[k] = dict(prov="cwms", station=r["station"], loc=loc, name=r["stationName"], live=bool(best), series=best[0] if best else None,
                      stats=best[1] if best else {"n": 0}, vdi=best[2] if best else None, step=best[3]["step"] if best else None, tried=tried, stype=r["stype"],
                      family=best[3]["family"] if best else r["family"])


def probe_rise(cands, res):
    for r in cands:
        k = f"rise|{r['stationName']}"
        if k in res:
            continue
        best = None
        for a in r["alts"]:
            if a["family"] != "elev":
                continue
            item = a["sid"].split(":")[1]
            pts = rise_recent(item)
            sm = summarize(pts or [])
            if sm["n"] and (best is None or sm["last_t"] > best[1]["last_t"]):
                best = (item, sm, a)
        res[k] = dict(prov="rise", station=r["station"], name=r["stationName"], live=bool(best), item=best[0] if best else None, stats=best[1] if best else {"n": 0},
                      datumSite=best[2]["datum"] if best else None, family="elev")


def probe_twdb(cands, res):
    d = json.load(open(f"{RAW}/twdb/recent-conditions.json"))
    for r in cands:
        k = f"twdb|{r['station']}"
        v = d.get(r["station"])
        if not v:
            continue
        t = dt.datetime.fromisoformat(v["timestamp"]).replace(tzinfo=dt.timezone.utc).timestamp() + 12 * 3600
        res[k] = dict(prov="twdb", station=r["station"], name=r["stationName"], live=v.get("elevation") is not None, stats=dict(n=1, last_t=v["timestamp"], age_h=round((NOW.timestamp() - t) / 3600 + 12, 1) if False else round((NOW.timestamp() - (t - 12 * 3600)) / 3600, 1),
                      last_ft=v["elevation"], med_ft=v["elevation"]), conservationPool=v.get("conservation_pool_elevation"), flood=v.get("flood_control_lake"), family="elev")


def probe_nwps(cands, res):
    for r in cands:
        k = f"nwps|{r['station']}"
        ex = r["extra"]
        s, d = get_json(f"https://api.water.noaa.gov/nwps/v1/gauges/{r['station']}", timeout=60, sleep=0.3)
        obs = ((d or {}).get("status") or {}).get("observed") or {}
        vt = obs.get("validTime"); val = obs.get("primary")
        if vt and val is not None and val > -999:
            t = dt.datetime.fromisoformat(vt.replace("Z", "+00:00")).timestamp()
            st = dict(n=1, last_t=vt, age_h=round((NOW.timestamp() - t) / 3600, 1), last_ft=val, med_ft=val)
            live = True
        else:
            st, live = {"n": 0}, False
        res[k] = dict(prov="nwps", station=r["station"], name=r["stationName"], live=live, stats=st, family=r["family"], datumInfo={kk: (d or {}).get(kk) for kk in ("pedts",)}, usgsId=(d or {}).get("usgsId"), usaceId=(d or {}).get("usaceId"),
                      datums=(d or {}).get("datums"))


TZ = {"CDT": -5, "CST": -6, "EDT": -4, "EST": -5}


def tva_observed(loc):
    s, b = http_get(f"https://www.tva.com/RestApi/observed-data-48-hours/{loc}", {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/120"}, timeout=60, sleep=0.5)
    if s != 200:
        return None
    try:
        rows = json.loads(b)
    except Exception:
        return None
    pts = []
    for r in rows:
        try:
            tm, ap, tz = r["Time"].split()
            h = int(tm) % 12 + (12 if ap == "PM" else 0)
            if tm == "12" and ap == "AM":
                h = 0
            d = dt.datetime.strptime(r["Day"], "%m/%d/%Y").replace(hour=h, tzinfo=dt.timezone(dt.timedelta(hours=TZ.get(tz, -5))))
            v = r.get("ReservoirElevation")
            if v not in (None, "", "-"):
                pts.append((d.timestamp(), float(str(v).replace(",", ""))))
        except Exception:
            pass
    return pts


def probe_tva(cands, res):
    for r in cands:
        k = f"tva|{r['station']}"
        pts = tva_observed(r["station"])
        sm = summarize(pts or [])
        res[k] = dict(prov="tva", station=r["station"], name=r["stationName"], live=bool(sm["n"]), stats=sm if sm["n"] else {"n": 0}, step="1Hour", family="elev")


def probe_a2w(cands, res):
    for r in cands:
        k = f"a2w|{r['station']}"
        # best forebay/pool series of this location = latest observation; the reporting API already returns latest_time/value
        best = None
        for a in r["alts"]:
            pass
        ex = r["extra"]
        res[k] = dict(prov="a2w", station=r["station"], name=r["stationName"], live=False, stats={"n": 0}, family="elev", step=r["step"])
        lt, lv = ex.get("latest_time"), ex.get("latest_value")
        if lt and lv is not None:
            t = dt.datetime.fromisoformat(lt.replace("Z", "+00:00")).timestamp()
            res[k].update(live=True, stats=dict(n=1, last_t=lt, age_h=round((NOW.timestamp() - t) / 3600, 1), last_ft=lv, med_ft=lv), tsid=ex.get("tsid"), levels=ex.get("levels"), nidid=ex.get("nidid"))


def probe_coops(cands, res):
    for r in cands:
        k = f"coops|{r['station']}"
        s, d = get_json(f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station={r['station']}&product=water_level&datum=IGLD&units=english&time_zone=gmt&application=SectorEngineResearch&format=json", timeout=60, sleep=0.3)
        v = (d or {}).get("data") or []
        if v:
            t = dt.datetime.strptime(v[-1]["t"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp()
            st = dict(n=1, last_t=v[-1]["t"], age_h=round((NOW.timestamp() - t) / 3600, 1), last_ft=float(v[-1]["v"]), med_ft=float(v[-1]["v"]))
        else:
            st = {"n": 0}
        res[k] = dict(prov="coops", station=r["station"], name=r["stationName"], live=bool(v), stats=st, family="elev", err=(d or {}).get("error"))


if __name__ == "__main__":
    sel = load_cands()
    print("candidates to probe:", len(sel), collections.Counter(r["prov"] for r in sel))
    out_f = f"{BIND}/probe_results.json"
    res = json.load(open(out_f)) if os.path.exists(out_f) else {}
    by = collections.defaultdict(list)
    for r in sel:
        by[r["prov"]].append(r)
    for prov, fn in [("twdb", probe_twdb), ("tva", probe_tva), ("a2w", probe_a2w), ("usgs", probe_usgs), ("cwms", probe_cwms), ("rise", probe_rise), ("nwps", probe_nwps), ("coops", probe_coops)]:
        if prov in by and (len(sys.argv) < 2 or prov in sys.argv[1:]):
            # unique stations for expensive ones
            seen, uniq = set(), []
            for r in by[prov]:
                kk = (r["station"], r["extra"].get("loc") if prov == "cwms" else r["stationName"] if prov == "rise" else "")
                if kk not in seen:
                    seen.add(kk); uniq.append(r)
            print(prov, len(uniq), flush=True)
            fn(uniq, res)
            json.dump(res, open(out_f, "w"))
    print("probed", len(res), "live", sum(1 for v in res.values() if v.get("live")))
