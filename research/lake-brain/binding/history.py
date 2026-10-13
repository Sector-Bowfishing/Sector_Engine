"""Phase 4: pull daily-value history for candidates that passed the live review (R1-R6,R8) and compute year-completeness
(>=90% of days per calendar year = complete; baseline rule of LAKE_BRAIN_INTEGRATION s6). Output: binding/history_results.json"""
import csv, collections, json, re, sys, datetime as dt
from common import *
from providers import *


_CW = None


def cwms_index():
    global _CW
    if _CW is None:
        _CW = {}
        for l in open(f"{BIND}/catalog.jsonl"):
            r = json.loads(l)
            if r["prov"] == "cwms" and r["family"] == "elev" and re.match(r"^(Elev|Elev-Pool|Elev-Forebay|Elev-Lake|Elev-Headwater|Elev-Upper|Elev-Reservoir)$", r["param"]) \
                    and not re.search(r"forecast|HourlyRAS|M0D0R0|Fcst|qpf|rating|Model", r["extra"]["version"], re.I) and r["extra"]["ptype"] in ("Inst", "Ave"):
                _CW.setdefault(r["extra"]["loc"].upper(), []).append(r)
                b = r["extra"]["loc"].split("-")[0].upper()
                if b != r["extra"]["loc"].upper():
                    _CW.setdefault("~" + r["station"] + ":" + b, []).append(r)
    return _CW


def hist_options(row, cand_alts, probe):
    """Ordered list of (label, fetch_fn) daily-history candidates for this physical site."""
    prov = row["prov"]; opts = []
    if prov == "usgs":
        par = probe.get("param")
        dvs = []
        for a in cand_alts:
            p = a["sid"].split(":")
            if p[3] == "dv" and a["family"] == "elev":
                dvs.append((0 if p[2] == par else 1, -(a["count"] or 0), p[2]))
        seen = set()
        for _, _, q in sorted(dvs):
            if q in seen:
                continue
            seen.add(q)
            opts.append((f"usgs:{row['station']}:{q}:dv", lambda s=row["station"], q=q: usgs_dv_history(s, q)))
    elif prov == "cwms":
        names = [a for a in cand_alts if a["family"] == "elev"]
        def key(a):
            daily = a["step"] in ("1Day", "~1Day")
            return (0 if daily else 1, a["begin"] or "9999")
        names.sort(key=key)
        for a in names[:2]:
            name = a["sid"].split(":", 2)[2]
            daily = a["step"] in ("1Day", "~1Day")
            by = int((a["begin"] or "1990")[:4])
            since = None if daily else max(by, NOW.year - 8)
            opts.append((f"cwms:{row['station']}:{name}", lambda o=row["station"], n=name, sy=since: cwms_history(o, n, sy)))
    elif prov == "a2w":
        loc = row["loc"].upper()
        rs = cwms_index().get(loc, [])
        if not rs:
            for off in ({row["station"].split(":")[0], "NWDP", "NWDM"}):
                rs = rs or cwms_index().get("~" + off + ":" + loc, [])
            prov_off = row["station"].split(":")[0]
            rs = rs or [r for k, v in cwms_index().items() if k.startswith("~" + prov_off + ":") and loc in k for r in v]
        def key2(a):
            daily = a["step"] in ("1Day", "~1Day")
            return (0 if daily else 1, a["begin"] or "9999")
        rs = sorted(rs, key=key2)
        for a in rs[:2]:
            name = a["sid"].split(":", 2)[2]; off = a["station"]
            daily = a["step"] in ("1Day", "~1Day")
            since = None if daily else max(int((a["begin"] or "1990")[:4]), NOW.year - 8)
            opts.append((f"cwms:{off}:{name}", lambda o=off, n=name, sy=since: cwms_history(o, n, sy)))
    elif prov == "rise":
        item = probe.get("item")
        if item:
            opts.append((f"rise:{item}", lambda i=item: rise_history(i)))
    elif prov == "twdb":
        opts.append((f"twdb:{row['station']}", lambda s=row["station"]: twdb_history(s)))
    return opts


def site_task(r, probes):
    alts = json.loads(r["alts"]); probe = probes.get(r["probeKey"], {})
    best = None; tried = []
    for label, fn in hist_options(r, alts, probe):
        try:
            daily = fn()
        except Exception as e:
            tried.append((label, f"err {e}")); continue
        if not daily:
            tried.append((label, "empty")); continue
        comp = year_completeness(daily); comp["series"] = label
        tried.append((label, comp["completeYears"]))
        if best is None or comp["completeYears"] > best["completeYears"]:
            best = comp
        if best["completeYears"] >= 5:
            break
    return dict(best=best, tried=tried)


def run(statuses=("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG", "HISTORY_ONLY", "STAGE_ONLY", "PENDING_CORROBORATION", "PENDING_NO_FULLPOOL")):
    from concurrent.futures import ThreadPoolExecutor
    rows = list(csv.DictReader(open(f"{BIND}/candidates.csv")))
    probes = json.load(open(f"{BIND}/probe_results.json"))
    out_f = f"{BIND}/history_results.json"
    res = json.load(open(out_f)) if os.path.exists(out_f) else {}
    todo = [r for r in rows if r["status"] in statuses and r["prov"] not in ("nwps", "coops")]
    sites = {}
    for r in todo:
        sites.setdefault((r["prov"], r["station"], r["loc"], r["stationName"] if r["prov"] == "rise" else ""), r)
    print("history candidates:", len(todo), "unique sites:", len(sites), flush=True)
    done = {}
    def job(item):
        site, r = item
        try:
            return site, site_task(r, probes)
        except Exception as e:
            return site, dict(best=None, tried=[("err", str(e))])
    with ThreadPoolExecutor(4) as ex:
        for n, (site, v) in enumerate(ex.map(job, sites.items())):
            done[site] = v
            if n % 10 == 0:
                print(n, len(sites), flush=True)
    for r in rows:
        site = (r["prov"], r["station"], r["loc"], r["stationName"] if r["prov"] == "rise" else "")
        if site in done:
            res[f"{r['lakeId']}|{r['prov']}|{r['station']}|{r['loc']}"] = done[site]
    json.dump(res, open(out_f, "w"))
    print("done", len(res))


if __name__ == "__main__":
    run()
