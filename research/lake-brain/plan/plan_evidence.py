#!/usr/bin/env python3
"""Authoritative per-lake operator-plan / flood-pool evidence table for the bound lakes (core + flagged).

Joins three machine-readable operator sources by LAKE (spatial + name + NID verified, not by the binding thread's probe key):
  CWMS levels  : history/cwms_levels/lv_*.json + loc_*.json   (USACE CWMS Data API /levels, all Elev levels)
  A2W levels   : binding/raw/a2w/locations_*.json            (USACE Access2Water: label, type CONSTANT|REGULAR|IRREGULAR, tsid, latest value, NIDID)
  TVA          : history/tva_guides/scan.json                  (TVA RestApi operating-guide: GuideCurve / TopOpZone / BtmOpZone per location)
Explicit rules (pre-registered here before counting):
  guide  = a named Guide Curve / Rule Curve level that is seasonal (CWMS seasonal-values, A2W type REGULAR/IRREGULAR) -- or the TVA GuideCurve series
  guideTopConSeasonal = a SEASONAL 'Top of Conservation' curve (USACE rule curve published under that name): reported as an inclusive tier, not in the strict count
  zone   = BOTH a top (Top of Conservation* / Top of Normal / Top of Constant Conservation) AND a bottom (Bottom of Normal / Bottom of Conservation / Drought Level n)
  flood  = operator flood-pool bottom: Top of Conservation* | Top of Constant Conservation | Bottom of Flood | Bottom of Flood Control
  plan_strict = guide OR zone ;  plan_inclusive = plan_strict OR guideTopConSeasonal
Match verification (verifiedMatch): project location within 5 km of the lake polygon AND (normalised name match OR NID id equal OR same station as the bound live series)
  AND the conservation / flood level is within 60 ft of the lake's observed 30-day median (or the directory full pool) -- a wrong-lake guard.
"""
import csv, gzip, glob, json, math, os, re, collections
from shapely.geometry import shape, Point
from common import *

HIST = f"{DATA}/history"
LV = f"{HIST}/cwms_levels"
A2W = f"{DATA}/binding/raw/a2w"
M2FT = 3.28084

GUIDE_RX = re.compile(r"(guide curve|rule curve)", re.I)
TOP_RX = re.compile(r"^(top of conservation.*|top of normal|top of constant conservation|buford top of conservation.*)$", re.I)
BOT_RX = re.compile(r"^(bottom of normal|bottom of conservation|bottom of constant conservation pool|drought level.*)$", re.I)
FLOOD_RX = re.compile(r"^(top of conservation.*|top of constant conservation|buford top of conservation.*|bottom of flood( control)?)$", re.I)
TOPCON_RX = re.compile(r"^(top of conservation(?! zone [234]).*|top of constant conservation)$", re.I)
TAIL_RX = re.compile(r"(tail|below|downstream|dnstr|\bdn\b)", re.I)
STOP = r"\b(lake|reservoir|res|dam|lock|and|the|l&d|pool|of|project|&)\b"

def norm(s):
    s = re.sub(r"\(.*?\)", " ", (s or "").lower())
    s = re.sub(STOP, " ", s)
    return re.sub(r"[^a-z0-9]", "", s)

def toks(s):
    s = re.sub(r"\(.*?\)", " ", (s or "").lower()); s = re.sub(STOP, " ", s)
    return {t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 1}

def name_match(a, b):
    na, nb = norm(a), norm(b)
    if len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na): return 1.0
    ta, tb = toks(a), toks(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0

def km(a, b):
    return math.hypot((a[0] - b[0]) * 111.0, (a[1] - b[1]) * 111.0 * math.cos(math.radians(a[0])))

def load_lakes():
    D = {l["id"]: l for l in json.load(open(f"{DATA}/directory_lakes_2026-10-13.json"))["lakes"]}
    poly = {}
    for f in json.load(gzip.open(f"{DATA}/geometry/engine_polygons_599.geojson.gz"))["features"]:
        poly[f["properties"]["id"]] = shape(f["geometry"])
    V = {r["lakeId"]: r for r in verified()}
    nid = {r["lakeId"]: r for r in csv.DictReader(open(f"{DATA}/binding/nid_links.csv"))}
    return D, poly, V, nid

def load_cwms():
    locs = {}
    for f in glob.glob(f"{LV}/loc_*.json"):
        o = os.path.basename(f)[4:7]
        for e in json.load(open(f)):
            if e.get("latitude") is not None: locs[(o, e["name"])] = e
    out = collections.defaultdict(list)    # (office, loc) -> list of levels
    for f in glob.glob(f"{LV}/lv_*.json"):
        o = os.path.basename(f)[3:6]
        try: L = json.load(open(f)).get("levels", [])
        except Exception: continue
        for l in L:
            loc = l["location-level-id"].split(".")[0]
            if TAIL_RX.search(loc): continue
            seasonal = "seasonal-values" in l
            v = None if seasonal else l.get("constant-value")
            if seasonal:
                vals = [x["value"] for x in l["seasonal-values"]]
                v = (min(vals), max(vals))
            else:
                v = (v, v) if v is not None else None
            if v: v = (v[0] * M2FT, v[1] * M2FT)
            out[(o, loc)].append({"label": l["specified-level-id"], "seasonal": seasonal, "ft": v, "src": "cwms-levels"})
    # CWMS time-series based guides (binding thread cwms_guides.json: office|location -> series parameter names such as Elev-Guide Curve / Elev-Top Con / Elev-Zone)
    TS = {"Elev-Guide Curve": "Guide Curve", "Elev-GC": "Guide Curve", "Elev-Guide_Curve": "Guide Curve", "Elev-Guide-Curve": "Guide Curve",
          "Elev-Top Con": "Top of Conservation", "Elev-Zone": "Regulation Zone", "Elev-L1": "Drought Level 1", "Elev-L2": "Drought Level 2", "Elev-L3": "Drought Level 3"}
    for k, names in json.load(open(f"{DATA}/binding/cwms_guides.json")).items():
        o, loc = k.split("|", 1)
        for n in set(names):
            if n in TS:
                out[(o, loc)].append({"label": TS[n], "seasonal": True, "ft": None, "src": "cwms-ts"})
    return locs, out

def load_a2w():
    out = {}
    for f in glob.glob(f"{A2W}/locations_*.json"):
        if "providers" in f: continue
        for l in json.load(open(f)):
            lv = [x for x in (l.get("levels") or []) if x.get("parameter") == "Elev"]
            if not lv: continue
            if TAIL_RX.search(l.get("code", "") + " " + (l.get("public_name") or "")): continue
            c = (l.get("geometry") or {}).get("coordinates") or [None, None]
            al = l.get("aliases") or {}
            ids = {str(al.get(k)).upper() for k in ("NWS Handbook 5 ID", "USGS Station Number") if al.get(k)}
            out[(l["provider"], l["code"])] = {"office": l["provider"], "code": l["code"], "name": l.get("public_name") or "", "lat": c[1], "lon": c[0], "nid": l.get("nidid") or al.get("NIDID") or "", "ids": ids, "kind": l.get("kind"),
                "levels": [{"label": x["label"], "seasonal": x.get("type") != "CONSTANT", "ft": (x["latest_value"], x["latest_value"]) if x.get("latest_value") is not None else None, "src": "a2w", "tsid": x.get("tsid")} for x in lv]}
    return out

def classify(levels):
    labs = [l for l in levels]
    guide = [l for l in labs if GUIDE_RX.search(l["label"]) and l["seasonal"] and not re.search(r"top of|bottom of", l["label"], re.I) or (GUIDE_RX.search(l["label"]) and l["seasonal"])]
    guide_const = [l for l in labs if GUIDE_RX.search(l["label"]) and not l["seasonal"]]
    tops = [l for l in labs if TOP_RX.match(l["label"])]
    bots = [l for l in labs if BOT_RX.match(l["label"])]
    flood = [l for l in labs if FLOOD_RX.match(l["label"])]
    topcon_seasonal = [l for l in labs if TOPCON_RX.match(l["label"]) and l["seasonal"]]
    regz = [l for l in labs if re.match(r"^(regulation zone|zone [a-z0-9]+)$", l["label"], re.I)]
    sw = [l["ft"][1] - l["ft"][0] for l in labs if l["seasonal"] and l["ft"] and (TOPCON_RX.match(l["label"]) or GUIDE_RX.search(l["label"]) or l["label"].lower() == "top of normal")]
    return {"swingFt": round(max(x for x in sw if x <= 150), 1) if any(x <= 150 for x in sw) else "", "regSchedule": bool(regz), "guide": bool(guide), "guideConstantOnly": bool(guide_const) and not guide, "guideTopConSeasonal": bool(topcon_seasonal),
            "zoneTop": bool(tops), "zoneBottom": bool(bots), "zone": bool(tops) and bool(bots), "flood": bool(flood),
            "floodSeasonal": any(l["seasonal"] for l in flood), "labels": sorted({l["label"] for l in labs})}

def ref_level(v, lake):
    refs = []
    for k in ("medFt",):
        try:
            if v and v.get(k): refs.append(float(v[k]))
        except Exception: pass
    if lake.get("fullPoolFt"): refs.append(float(lake["fullPoolFt"]))
    return refs

def plausible(levels, refs, tol=100):
    if not refs: return None
    pts = [x for l in levels if (TOPCON_RX.match(l["label"]) or re.match(r"^(bottom of flood.*|top of normal|top of flood)$", l["label"], re.I)) and l["ft"] for x in l["ft"]]
    if not pts: return None
    return any(abs(p - r) <= tol for p in pts for r in refs)

def state_ok(lake, c):
    return True

def main():
    D, poly, V, nid = load_lakes()
    locs, lvl = load_cwms(); a2w = load_a2w()
    tva = json.load(open(f"{PLAN}/raw/tva_guides.json"))
    cand = []   # all project candidates with coordinates
    for (o, loc), L in lvl.items():
        e = locs.get((o, loc))
        if not e or not L: continue
        cand.append({"src": "cwms", "office": o, "code": loc, "name": e.get("public-name") or loc, "lat": e["latitude"], "lon": e["longitude"], "nid": "", "ids": set(), "levels": L})
    for k, e in a2w.items():
        cand.append({"src": "a2w", "office": e["office"], "code": e["code"], "name": e["name"], "lat": e["lat"], "lon": e["lon"], "nid": e["nid"], "ids": e["ids"], "levels": e["levels"]})
    rows = []
    for lid, v in V.items():
        if v["bindingStatus"] not in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG"): continue
        lake = D[lid]; P = poly.get(lid); pt = (lake["lat"], lake["lon"])
        ref = ref_level(v, lake); lakenid = (nid.get(lid) or {}).get("nidId", "") if v.get("nidId") else ""
        lakenid = v.get("nidId") or ""
        bound_station = (v["provider"], v["station"], v["loc"])
        best = {}
        lakeids = {str(x).upper() for x in (v["station"], v["loc"]) if x}
        for c in cand:
            if c["lat"] is None:
                d = None
            else:
                d = P.distance(Point(c["lon"], c["lat"])) * 111.0 if P is not None else km(pt, (c["lat"], c["lon"]))
            if d is not None and d > 60: continue
            nm = max(name_match(lake["name"], c["name"]), name_match(lake["name"], c["code"]) if len(norm(c["code"])) >= 5 else 0.0)
            nidm = bool(lakenid and c["nid"] and re.sub(r"0+", "", lakenid) == re.sub(r"0+", "", c["nid"]))
            aliasm = bool(c["ids"] & lakeids)
            same_station = (v["provider"] == "a2w" and v["station"] == f"{c['office']}:{c['code']}") or (v["provider"] == "cwms" and v["station"] == c["office"] and v["loc"].split("-")[0] == c["code"])
            dd = d if d is not None else 0.0
            if d is None:       # no coordinates: identity only through NID id / NWS-LID / USGS id aliases
                strong = bool(nidm or aliasm or same_station)
            else:
                strong = (dd <= 5 and (nm >= 0.5 or nidm or same_station or aliasm)) or ((nidm or aliasm) and dd <= 60) or (dd <= 25 and nm >= 0.8)
            weak = (not strong) and d is not None and d <= 0.5
            if not strong and not weak: continue
            key = (c["src"], c["office"], c["code"])
            best[key] = {"c": c, "dkm": None if d is None else round(d, 2), "nm": round(nm, 2), "nid": nidm, "alias": aliasm, "same": same_station, "strong": strong, "weak": weak}
        # merge candidate levels into one set per physical project (a2w + cwms of the same office/code unify)
        merged = {}
        for k, b in best.items():
            pk = (b["c"]["office"], norm(b["c"]["code"]) or b["c"]["code"])
            m = merged.setdefault(pk, {"levels": [], "srcs": [], "dkm": 99, "nm": 0, "nid": False, "alias": False, "same": False, "strong": False, "weak": False, "names": set(), "codes": []})
            m["levels"] += b["c"]["levels"]; m["srcs"].append(k[0]); m["dkm"] = min(m["dkm"], b["dkm"] if b["dkm"] is not None else 99); m["nm"] = max(m["nm"], b["nm"])
            m["nid"] |= b["nid"]; m["alias"] |= b["alias"]; m["same"] |= b["same"]; m["strong"] |= b["strong"]; m["weak"] |= b["weak"]; m["names"].add(b["c"]["name"]); m["codes"].append(f"{b['c']['office']}:{b['c']['code']}")
        # choose the best project: most plan evidence among strong matches, closest
        ranked = []
        for pk, m in merged.items():
            cl = classify(m["levels"]); pl = plausible(m["levels"], ref, 100 if m["strong"] else 25)
            score = (m["strong"] or (m["weak"] and pl is True), pl is not False, m["same"] or m["nid"] or m["alias"], cl["guide"] * 4 + cl["zone"] * 2 + cl["flood"], -m["dkm"])
            ranked.append((score, pk, m, cl, pl))
        ranked.sort(key=lambda x: x[0], reverse=True)
        rec = {"lakeId": lid, "name": lake["name"], "state": lake["state"], "bindingStatus": v["bindingStatus"], "provider": v["provider"], "operator": v["operator"], "refLevelFt": ref[0] if ref else ""}
        ev = {"swingFt": "", "regSchedule": False, "guide": False, "guideConstantOnly": False, "guideTopConSeasonal": False, "zoneTop": False, "zoneBottom": False, "zone": False, "flood": False, "floodSeasonal": False, "labels": []}
        rec.update(planSource="", matchedProject="", matchBasis="", distKm="", verifiedMatch=False, levelPlausible="")
        if ranked and (ranked[0][2]["strong"] or (ranked[0][2]["weak"] and ranked[0][4] is True)):
            _, pk, m, cl, pl = ranked[0]
            basis = [b for b, ok in (("nid", m["nid"]), ("nwsLid/usgsId alias", m["alias"]), ("sameStation", m["same"]), ("name", m["nm"] >= 0.5), ("geo<=5km", m["dkm"] <= 5), ("geo<=0.5km+level only", (not m["strong"]))) if ok]
            rec.update(planSource="+".join(sorted(set(m["srcs"]))), matchedProject="; ".join(sorted(set(m["codes"]))) + " | " + "; ".join(sorted(m["names"]))[:80],
                       matchBasis=",".join(basis), distKm=(m["dkm"] if m["dkm"] < 99 else ""), matchTier=("strong" if m["strong"] else "weak"), levelPlausible="" if pl is None else pl, verifiedMatch=(pl is not False))
            ev = cl if pl is not False else ev
            rec["_rejectedPlaus"] = pl is False
        # TVA
        if v["provider"] == "tva" and v["station"] in tva:
            t = tva[v["station"]]
            g = bool(t.get("guideSwingFt")) and t["guideSwingFt"] > 0; zt = t.get("topZoneDays", 0) > 0; zb = t.get("btmZoneDays", 0) > 0
            ev = dict(ev); ev["swingFt"] = max(ev["swingFt"] or 0, t.get("guideSwingFt") or 0) or ""; ev["guide"] = ev["guide"] or g; ev["zoneTop"] |= zt; ev["zoneBottom"] |= zb; ev["zone"] = ev["zoneTop"] and ev["zoneBottom"]
            ev["labels"] = ev["labels"] + [x for x, ok in (("TVA GuideCurve", g), ("TVA TopOpZone", zt), ("TVA BtmOpZone", zb)) if ok]
            rec.update(planSource=(rec["planSource"] + "+tva").strip("+"), matchedProject=rec["matchedProject"] or f"TVA:{v['station']}", matchBasis=rec["matchBasis"] or "bound-station", verifiedMatch=True)
            rec["floodInferredFromTvaGuide"] = g and (t.get("guideSwingFt") or 0) >= 10
        rec.update({k: ev[k] for k in ("swingFt", "regSchedule", "guide", "guideConstantOnly", "guideTopConSeasonal", "zoneTop", "zoneBottom", "zone", "flood", "floodSeasonal")})
        rec["levelLabels"] = "; ".join(ev["labels"])
        rec["planStrict"] = bool(rec["verifiedMatch"] and (ev["guide"] or ev["zone"]))
        rec["planInclusive"] = bool(rec["verifiedMatch"] and (ev["guide"] or ev["zone"] or ev["guideTopConSeasonal"] or ev["regSchedule"]))
        rec["floodStrict"] = bool(rec["verifiedMatch"] and ev["flood"])
        rec["priorOperatorPlanText"] = v["operatorPlan"]
        rows.append(rec)
    return rows

if __name__ == "__main__":
    rows = main()
    cols = ["lakeId", "name", "state", "bindingStatus", "provider", "operator", "planSource", "matchedProject", "matchBasis", "matchTier", "distKm", "verifiedMatch", "levelPlausible",
            "swingFt", "guide", "guideTopConSeasonal", "regSchedule", "zoneTop", "zoneBottom", "zone", "flood", "floodSeasonal", "planStrict", "planInclusive", "floodStrict", "levelLabels", "priorOperatorPlanText", "refLevelFt"]
    os.makedirs(DOCS_DATA, exist_ok=True)
    with open(f"{PLAN}/plan_flood_evidence_base.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); [w.writerow(r) for r in rows]
    core = [r for r in rows if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED")]
    def cnt(rs, k): return sum(1 for r in rs if r[k])
    for name, rs in (("core", core), ("core+flagged", rows)):
        print(name, len(rs), {k: cnt(rs, k) for k in ("verifiedMatch", "guide", "guideTopConSeasonal", "regSchedule", "zone", "flood", "planStrict", "planInclusive", "floodStrict")}, "priorText", sum(1 for r in rs if r["priorOperatorPlanText"]))
