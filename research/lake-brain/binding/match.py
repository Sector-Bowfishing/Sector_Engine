"""Spatial + name + type candidate matcher: 621 directory lakes -> level-series candidates (static scoring, pre-probe)."""
import csv, gzip, json, math, re, sys, collections
from shapely.geometry import shape, Point
from shapely.ops import transform
from shapely.strtree import STRtree
from common import *

ST_NAMES = {}  # filled lazily

POOL_PARAM = re.compile(r"^(Elev|Elev-Pool|Elev-Forebay|Elev-Lake|Elev-Headwater|Elev-Head|Elev-Upper|Elev-Reservoir|Elev-Res|Stage-Pool|Stage-Lake|Stage|Stage-Headwater|Stage-Upper)$")
REJECT_LOC = re.compile(r"(tail|downstream|\bdown\b|-tw\b|\btw\b|outlet|outflow|lower|-lw|tlwtr|discharge|stilling|below|\bblw\b|\bbl\b|dnstr|\bds\b|-dn\b|PZ\d|piez|well|seep|toe)", re.I)
TAIL_NAME = re.compile(r"\b(below|blw|bl|tailwater|tailrace|downstream|dnstrm|ds|outlet|outflow|abv|above|nr|near|at|bridge|creek|river|rv|r)\b", re.I)


def role_cwms(r):
    p, loc = r["param"], r["extra"]["loc"]
    if r["family"] == "storage" or r["family"] == "other":
        return "storage" if r["family"] == "storage" else "other"
    if p.startswith("Elev-") and re.match(r"Elev-(Tail|Down|Lower)", p):
        return "tailwater"
    if re.match(r"Elev-(GC|Guide|L\d|Top|Zone|Float|Bottom|Con|Flood|Inactive|Surcharge|Max|Min|Drought|Cons)", p, re.I):
        return "guide"
    if re.search(r"(^|-)(Tail|TW|Down)", loc, re.I) or REJECT_LOC.search(loc):
        return "tailwater"
    if re.search(r"forecast|HourlyRAS|M0D0R0|Fcst|qpf|rating|Model", r["extra"]["version"], re.I):
        return "forecast"
    if r["extra"]["ptype"] != "Inst" and not (r["extra"]["ptype"] == "Ave" and r["step"] in ("1Day", "~1Day")):
        return "stat"
    if POOL_PARAM.match(p):
        return "pool"
    return "other"


def lake_name_alts(l):
    n = l["name"]
    alts = [a.strip() for a in re.split(r"[/(),]| aka ", n) if a.strip()]
    return alts or [n]


def best_sim(l, text):
    return max((name_sim(a, text) for a in lake_name_alts(l)), default=0.0)


def proj(lat0):
    k = math.cos(math.radians(lat0))
    return lambda x, y, z=None: (x * 111320.0 * k, y * 110574.0)


def to_planar(geom, lat0):
    import numpy as np, shapely
    k = math.cos(math.radians(lat0))
    return shapely.transform(geom, lambda a: np.column_stack((a[:, 0] * 111320.0 * k, a[:, 1] * 110574.0)))


def load_polys():
    d = json.load(gzip.open(POLYS))
    return {f["properties"]["id"]: shape(f["geometry"]) for f in d["features"]}


def run():
    lakes = load_directory()
    polys = load_polys()
    cat = [json.loads(x) for x in open(f"{BIND}/catalog.jsonl")]
    # candidate-eligible records: elev & stage families, with coordinates; plus remember storage/guide for context
    elig, guides = [], collections.defaultdict(list)
    for r in cat:
        if r["lat"] is None or r["lon"] is None:
            continue
        if r["prov"] == "cwms":
            r["role"] = role_cwms(r)
            if r["role"] == "guide":
                guides[(r["station"], r["extra"]["loc"].split("-")[0])].append(r["param"])
            if r["role"] != "pool" or r["family"] not in ("elev", "stage"):
                continue
        elif r["prov"] == "usgs":
            r["role"] = "gauge"
            if r["family"] == "storage":
                continue
        else:
            r["role"] = "gauge"
            if r["family"] == "storage":
                continue
        elig.append(r)
    pts = [Point(r["lon"], r["lat"]) for r in elig]
    tree = STRtree(pts)
    out = []
    for l in lakes:
        lat0, lon0 = l["lat"], l["lon"]
        poly = polys.get(l["id"])
        pj = proj(lat0)
        if poly is not None:
            minx, miny, maxx, maxy = poly.bounds
            pad = 0.12
            q = Point(0, 0).buffer(0).envelope  # dummy
            from shapely.geometry import box
            idx = tree.query(box(minx - pad, miny - pad, maxx + pad, maxy + pad))
            ppoly = to_planar(poly, lat0)
            radius = 8000
        else:
            from shapely.geometry import box
            pad = 0.6
            idx = tree.query(box(lon0 - pad, lat0 - pad, lon0 + pad, lat0 + pad))
            ppoly = Point(*pj(lon0, lat0))
            radius = 12000
        cands = []
        for i in idx:
            r = elig[i]
            p = Point(*pj(r["lon"], r["lat"]))
            d = ppoly.distance(p)
            if d > radius and not (poly is None and d <= 60000 and best_sim(l, r["name"] or "") >= 0.5):
                continue
            cands.append((d, r))
        for d, r in cands:
            out.append(score(l, poly is not None, d, r))
    return out, lakes, guides


def score(l, haspoly, d, r):
    states = set(l.get("states") or [l["state"]])
    rstate = (r["extra"].get("state") or (r["extra"].get("states") or [None])[0] if r["prov"] in ("cwms", "nwps", "rise", "a2w") else None)
    if r["prov"] == "usgs":
        m = re.search(r",\s*([A-Z]{2})\b", r["name"] or "")
        rstate = m.group(1) if m else None
    sim = best_sim(l, r["name"] or "")
    if r["prov"] == "cwms":
        sim = max(sim, best_sim(l, r["extra"]["loc"].split("-")[0]))
    # geo score
    if d <= 150: g = 1.0
    elif d <= 600: g = 0.9
    elif d <= 1500: g = 0.75
    elif d <= 3000: g = 0.5
    elif d <= 6000: g = 0.25
    else: g = 0.1
    if not haspoly:
        g *= 0.6
    pts = 40 * g + 35 * min(1.0, sim * 1.3)
    reasons = [f"dist={int(d)}m", f"nameSim={sim}"]
    # type bonus
    if r["prov"] == "usgs":
        if r["stype"] == "LK": pts += 10; reasons.append("siteType=LK")
        elif r["family"] == "elev": pts += 5; reasons.append("siteType=ST+reservoir-elevation-param")
        if r["family"] == "stage": pts -= 12; reasons.append("stage-only(local datum)")
    elif r["prov"] == "cwms":
        pts += 9; reasons.append("CWMS pool/elev series")
        if r["family"] == "stage": pts -= 8
    elif r["prov"] in ("rise", "twdb", "tva", "a2w"):
        pts += 10; reasons.append(f"{r['prov']} reservoir elevation")
    elif r["prov"] == "nwps":
        pts += 6 if r["family"] == "elev" else 0; reasons.append("NWPS " + r["param"])
    elif r["prov"] == "coops":
        pts += 5
    # state
    if rstate:
        if rstate in states: pts += 5; reasons.append("state=ok")
        else: pts -= 25; reasons.append(f"state-mismatch({rstate})")
    # traps
    nm = r["name"] or ""
    if r["prov"] in ("usgs", "nwps") and re.search(r"\b(below|blw|tailwater|tailrace|downstream|dnstrm|bl)\b", nm, re.I) and not re.search(r"\b(lake|res|reservoir)\b[^,]*\bnear\b", nm, re.I):
        pts -= 30; reasons.append("TRAP:below/tailwater-in-name")
    if r["prov"] == "usgs" and r["stype"] == "ST" and re.search(r"\b(river|creek|rv|cr|ck|brook|canal)\b", nm, re.I) and not re.search(r"\b(lake|res|reservoir|pool|pond|dam)\b", nm, re.I):
        pts -= 15; reasons.append("TRAP:river-gauge-name")
    # operator consistency
    op = (l["operatorName"] or "").lower()
    if r["prov"] == "cwms" and ("usace" in op or l.get("cwmsOffice") == r["station"]): pts += 5; reasons.append("operator=USACE")
    if r["prov"] == "a2w" and "usace" in op: pts += 5; reasons.append("operator=USACE")
    if r["prov"] == "tva" and "tva" in op: pts += 5; reasons.append("operator=TVA")
    if r["prov"] == "rise" and ("usbr" in op or "bureau" in op): pts += 5; reasons.append("operator=USBR")
    # freshness from catalog end date (coarse; real probe later)
    pts = max(0, min(100, pts))
    return dict(lakeId=l["id"], lakeName=l["name"], lakeState=l["state"], prov=r["prov"], sid=r["sid"], station=r["station"], series=r["param"] if r["prov"] != "cwms" else r["sid"].split(":", 2)[2],
                stationName=nm, stype=r["stype"], family=r["family"], unit=r["unit"], datum=r["datum"], begin=r["begin"], end=r["end"], count=r["count"], step=r["step"],
                lat=r["lat"], lon=r["lon"], distM=int(d), nameSim=sim, score=round(pts, 1), reasons=";".join(reasons), extra=json.dumps(r["extra"]))


def group_key(r):
    if r["prov"] == "usgs":
        return r["station"]
    if r["prov"] == "cwms":
        return r["station"] + ":" + json.loads(r["extra"])["loc"]
    if r["prov"] == "a2w":
        return r["station"]
    return r["station"] if r["prov"] != "rise" else r["stationName"]


def group_sites(rows):
    """Collapse series rows into site-level candidates; keep the series list in 'alts'."""
    g = collections.OrderedDict()
    for r in rows:
        g.setdefault((r["lakeId"], r["prov"], group_key(r)), []).append(r)
    out = []
    for k, rs in g.items():
        rs.sort(key=lambda x: (-x["score"], "".join(chr(255 - ord(c)) for c in (json.loads(x["extra"]).get("latest_time") or "") if x["prov"] == "a2w")))
        top = dict(rs[0])
        top["alts"] = json.dumps([dict(sid=x["sid"], series=x["series"], family=x["family"], unit=x["unit"], datum=x["datum"], begin=x["begin"], end=x["end"], count=x["count"], step=x["step"]) for x in rs])
        top["nSeries"] = len(rs)
        out.append(top)
    return out


if __name__ == "__main__":
    rows, lakes, guides = run()
    rows = group_sites(rows)
    rows.sort(key=lambda x: (x["lakeId"], -x["score"]))
    keep, per = [], collections.Counter()
    for r in rows:
        per[r["lakeId"]] += 1
        if per[r["lakeId"]] <= 12:
            keep.append(r)
    with open(f"{BIND}/candidates_all.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(keep[0].keys()))
        w.writeheader(); w.writerows(keep)
    json.dump({f"{k[0]}|{k[1]}": v for k, v in guides.items()}, open(f"{BIND}/cwms_guides.json", "w"))
    byl = collections.defaultdict(list)
    for r in keep: byl[r["lakeId"]].append(r)
    print("lakes with any candidate:", len(byl), "of", len(lakes))
    print("lakes with candidate score>=60:", sum(1 for v in byl.values() if v[0]["score"] >= 60))
    print("lakes with candidate score>=75:", sum(1 for v in byl.values() if v[0]["score"] >= 75))
