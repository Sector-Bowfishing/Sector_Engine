"""binding-review-v1 re-run with OPTIONAL v1.1 rule extensions (labelled; counts reported with and without).
v1.1 additions (each can be switched off; thresholds R6/R7/R9 are NOT changed):
  R1b  dam-gauge geometry   : polygon distance <= 5 km AND the lake's linked NID dam within 4 km of the gauge AND name sim >= 0.75; only a 'strong' R7 level can pass this way.
  R2b  identity via dam     : an NID dam within 1.5 km of the gauge, within 6 km of the lake polygon, whose name/other/former name is similar (>=0.5) to the gauge name,
                              or an Access2Water record whose NIDID equals the lake's linked NID id (zero-padding tolerant); only a 'strong' R7 level can pass this way.
  R4b  state waiver         : state mismatch ignored when the gauge is inside the polygon (<=150 m) or dam-confirmed as in R2b, and name sim >= 0.6 or dam-confirmed
                              (cross-state reservoirs: Kerr, Thurmond, Youghiogheny, Flaming Gorge).
  R5b  sibling waiver       : two directory entries of one physical lake (same linked NID id, or polygons within 3 km) may share a series.
  R2c  inside + dam token  : gauge inside the polygon (<=150 m) sharing a significant token (>=5 letters) with the linked NID dam name (Garrison Dam & Reservoir vs 'Garrison Dam - Snake Creek Embankment'); strong R7 only.
  R2d  inside + operator pool: USACE/USBR pool elevation series whose gauge sits inside the polygon (<=150 m) with a strong or weak R7 level (Lake Pepin: 'Mississippi River at Lake City').
  R8c  published pool        : datum label absent but the provider itself publishes a full-pool elevation within 3 ft of the directory full pool (SRP, utahlake.gov); the level class (strong/weak/drawdown) is still tested by R7.
  RI   identity widening     : strong identity (needed for the flagged tier) also when the gauge is inside the polygon (<=150 m) and name similarity >= 0.5, or within 1.5 km with similarity >= 0.6 and the lake polygon >= 20 km2.
  R1c  big-lake gauge        : lake gauge (USGS LK or a state/operator lake page) with name similarity >= 0.6 within 5 km of a polygon >= 20 km2 (also counts as strong identity); the flagged tier at most unless R7 is strong.
  RGL  Great Lakes          : lakes without polygon in the Great Lakes class: gauge on that lake (name sim >= 0.6) within 80 km of the directory point and the same state.
"""
import csv, json, collections, re, sys, math
from common2 import *
import verify as V
from match import load_polys, to_planar
from shapely.geometry import Point

GL = {"Lake Erie", "Lake Michigan", "Lake Superior", "Lake Huron", "Lake Ontario", "Green Bay", "Lake St. Clair", "Lake of the Woods", "Great Salt Lake"}
_NID = {}


def nid_by_id():
    if not _NID:
        for l in open(f"{RAW}/nid/nid.jsonl"):
            d = json.loads(l)
            _NID[d["NIDID"]] = d
    return _NID


def nid_norm(x):
    return re.sub(r"[^A-Z0-9]", "", (x or "").upper()).replace("0", "") if x else ""


def lake_dams():
    """lakeId -> dam record (NID) for strongly linked lakes (score>=60 & sim>=0.3, or score>=70)."""
    nid = nid_by_id()
    out = {}
    for r in csv.DictReader(open(f"{BIND}/nid_links.csv")):
        try:
            sc, sim = float(r["nidScore"] or 0), float(r["nidSim"] or 0)
        except ValueError:
            continue
        if r["nidId"] and (sc >= 70 or (sc >= 60 and sim >= 0.3)) and r["nidId"] in nid:
            out[r["lakeId"]] = nid[r["nidId"]]
    return out


def dam_names(d):
    return [x for x in [d.get("NAME") or ""] + re.split(r"[;|]", d.get("OTHER_NAMES") or "") + re.split(r"[;|]", d.get("FORMER_NAMES") or "") if x]


_IDX = {}


def dam_index():
    if not _IDX:
        from shapely.strtree import STRtree
        nid = [d for d in nid_by_id().values() if d.get("LATITUDE") and d.get("LONGITUDE")]
        _IDX["dams"] = nid
        _IDX["tree"] = STRtree([Point(d["LONGITUDE"], d["LATITUDE"]) for d in nid])
    return _IDX


def dams_near(lat, lon, rad_m):
    ix = dam_index()
    pad = rad_m / 80000.0
    from shapely.geometry import box
    out = []
    for i in ix["tree"].query(box(lon - pad, lat - pad, lon + pad, lat + pad)):
        d = ix["dams"][i]
        m = haversine_m(lat, lon, d["LATITUDE"], d["LONGITUDE"])
        if m <= rad_m:
            out.append((m, d))
    return sorted(out, key=lambda x: x[0])


def evaluate11(r, lake, probes, haspoly, claim, ctx, flags):
    c, pr, st, fam, plaus = V.evaluate(r, lake, probes, haspoly, claim)
    notes = []
    dam = ctx["dams"].get(lake["id"])
    dist = int(r["distM"])
    nm = r["stationName"] or ""
    dd = haversine_m(float(r["lat"]), float(r["lon"]), dam["LATITUDE"], dam["LONGITUDE"]) if dam and r.get("lat") not in (None, "") else None
    a2w_nid = (r["extra"] or {}).get("nidid") if isinstance(r.get("extra"), dict) else None
    a2w_match = bool(dam and a2w_nid and nid_norm(a2w_nid) == nid_norm(dam["NIDID"]))
    strong = c["R7_level"] == "strong"
    dam_conf = False
    if (flags.get("R2b") or flags.get("R4b")) and r.get("lat") not in (None, "") and not (c["R2_identity"] and c["R4_state"] and c["R1_geo"]):
        poly = ctx["polys"].get(lake["id"])
        for m, d in dams_near(float(r["lat"]), float(r["lon"]), 1500):
            if max((name_sim(nm, n) for n in dam_names(d)), default=0) < 0.5:
                continue
            if poly is not None:
                pdm = to_planar(poly, lake["lat"]).distance(Point(*proj_xy(d["LONGITUDE"], d["LATITUDE"], lake["lat"])))
                if pdm > 6000:
                    continue
            dam_conf = True; break
    if flags.get("R1b") and not c["R1_geo"] and haspoly and dd is not None and dd <= 4000 and dist <= 5000 and r["nameSim"] >= 0.75 and strong:
        c["R1_geo"] = True; notes.append("R1b")
    dam_tok = set(t for n in dam_names(dam) for t in norm_tokens(n) if len(t) >= 5) if dam else set()
    tok_share = bool(dam_tok & set(norm_tokens(nm)))
    linked_sim = max((name_sim(nm, n) for n in dam_names(dam)), default=0.0) if dam else 0.0
    if flags.get("R2b") and not c["R2_identity"] and strong and (dam_conf or a2w_match or (dist <= 150 and (linked_sim >= 0.5 or (flags.get('R2c') and tok_share)))):
        c["R2_identity"] = True; notes.append("R2b")
    if flags.get("R4b") and not c["R4_state"] and (dist <= 150 or dam_conf) and (r["nameSim"] >= 0.6 or dam_conf):
        c["R4_state"] = True; notes.append("R4b")
    if flags.get("R5b") and not c["R5_unique"]:
        ck = claim.get(V.probe_key(r))
        if ck and sibling(lake["id"], ck[0], ctx):
            c["R5_unique"] = True; notes.append("R5b")
    if flags.get("RGL") and not haspoly and lake["name"] in GL:
        lw = bool(r.get("lakeWide"))      # lake-wide mean series (e.g. CWMS LRE): identity by series name, no station location
        lvl = c["R7_level"] in ("strong", "weak") and st.get("med_ft") is not None and lake.get("fullPoolFt") is not None and abs(float(st["med_ft"]) - lake["fullPoolFt"]) <= 6
        near = dist <= (150000 if r.get('greatLakesStation') else 80000) or lw
        if near and lvl and (r["nameSim"] >= 0.5 or r.get("greatLakesStation")) and c["R4_state"]:
            c["R1_geo"] = True; c["R2_identity"] = True; notes.append("RGL")
    if flags.get("R2d") and not c["R2_identity"] and dist <= 150 and str(r["prov"]).startswith(("cwms", "a2w", "rise")) and fam == "elev" and c["R7_level"] in ("strong", "weak") and c["R3_notrap"]:
        c["R2_identity"] = True; notes.append("R2d")
    big = False
    poly_ = ctx["polys"].get(lake["id"])
    if poly_ is not None:
        big = to_planar(poly_, lake["lat"]).area >= 20e6
    if flags.get("R1c") and not c["R1_geo"] and haspoly and big and dist <= 5000 and r["nameSim"] >= 0.6 and c["R4_state"] and (r["stype"] == "LK" or r["prov"] not in ("usgs", "nwps")):
        c["R1_geo"] = True; notes.append("R1c")
    if flags.get("R8c") and not c["R8_datum"] and fam == "elev" and not r.get("derived") and r.get("fullPoolHint") is not None and lake.get("fullPoolFt") is not None and abs(float(r["fullPoolHint"]) - lake["fullPoolFt"]) <= 3:
        c["R8_datum"] = True; notes.append("R8c")
    if flags.get("R8b") and not c["R8_datum"] and fam == "elev" and c["R7_level"] == "strong" and not r.get("derived"):
        c["R8_datum"] = True; notes.append("R8b")
    ident = bool(r["nameSim"] >= 0.6 and dist <= 500) or ("R2b" in notes) or ("RGL" in notes) or ("R1c" in notes) or ("R2d" in notes)
    if flags.get("RI") and not ident and ((dist <= 150 and r["nameSim"] >= 0.5) or (dist <= 1500 and r["nameSim"] >= 0.6 and big)):
        ident = True; notes.append("RI")
    return c, pr, st, fam, plaus, ident, notes


def proj_xy(lon, lat, lat0):
    k = math.cos(math.radians(lat0))
    return (lon * 111320.0 * k, lat * 110574.0)


def sibling(a, b, ctx):
    da, db = ctx["dams"].get(a), ctx["dams"].get(b)
    if da and db and da["NIDID"] == db["NIDID"]:
        return True
    pa, pb = ctx["polys"].get(a), ctx["polys"].get(b)
    if pa is not None and pb is not None:
        la = ctx["lakes"][a]; 
        return to_planar(pa, la["lat"]).distance(to_planar(pb, la["lat"])) < 3000
    return False


def status_of(c, fam, level, ident, r):
    hard = all(c[k] for k in ("R1_geo", "R2_identity", "R3_notrap", "R4_state", "R5_unique", "R6_live", "R8_datum"))
    status = "REJECT"
    if hard and level == "strong":
        status = "VERIFIED"
    elif hard and level in ("weak", "drawdown") and ident:
        status = "VERIFIED_FLAG"
    elif hard and level in ("weak", "drawdown"):
        status = "PENDING_CORROBORATION"
    elif hard and level == "na":
        if fam == "stage":
            lakey = (r["stype"] == "LK" or bool(re.search(r"\b(lake|lk|res|reservoir|pond|pool)\b", r["stationName"] or "", re.I))) and \
                    (r["stype"] == "LK" or not re.search(r"\b(river|creek|canal|rv|brook)\b", r["stationName"] or "", re.I))
            status = "STAGE_ONLY" if (ident and lakey) else "REJECT"
        else:
            status = "PENDING_NO_FULLPOOL"
    if status == "REJECT" and not c["R6_live"] and all(c[k] for k in ("R1_geo", "R2_identity", "R3_notrap", "R4_state", "R5_unique", "R8_datum")) and \
            (level == "strong" or (level in ("weak", "drawdown") and ident)) and fam == "elev":
        status = "HISTORY_ONLY"
    return status


def run(flags, cand_rows=None, probes=None, extra_claim_rows=()):
    """flags: dict of v1.1 switches. cand_rows: wave-1 candidates.csv-like (default: reconstruct from probed set)."""
    lakes = {l["id"]: l for l in load_directory()}
    probes = probes or json.load(open(f"{BIND}/probe_results.json"))
    polys = load_polys()
    ctx = dict(dams=lake_dams(), polys=polys, lakes=lakes)
    from probe import load_cands
    cands = cand_rows if cand_rows is not None else load_cands()
    allrows = list(csv.DictReader(open(f"{BIND}/candidates_all.csv")))
    claim = {}
    for r in allrows:
        r["score"] = float(r["score"]); r["extra"] = json.loads(r["extra"]); r["nameSim"] = float(r["nameSim"]); r["distM"] = int(r["distM"])
    for r in list(allrows) + list(extra_claim_rows):
        if r["score"] < 40:
            continue
        k = V.probe_key(r)
        cur = claim.get(k)
        if cur is None or (r["nameSim"], -r["distM"]) > (cur[1], -cur[2]):
            claim[k] = (r["lakeId"], r["nameSim"], r["distM"])
    rows = []
    for r in cands:
        r["nameSim"] = float(r["nameSim"]); r["distM"] = int(r["distM"])
        lake = lakes[r["lakeId"]]
        c, pr, st, fam, plaus, ident, notes = evaluate11(r, lake, probes, r["lakeId"] in polys, claim, ctx, flags)
        status = status_of(c, fam, c["R7_level"], ident, r)
        rows.append(dict(lakeId=r["lakeId"], lakeName=r["lakeName"], state=r["lakeState"], prov=r["prov"], station=r["station"],
                         series=(pr or {}).get("series") or (pr or {}).get("param") or (pr or {}).get("item") or r["series"], stationName=r["stationName"], stype=r["stype"],
                         family=fam, distM=r["distM"], nameSim=r["nameSim"], matchScore=r["score"], live=int(bool(pr and pr.get("live"))), lastObs=st.get("last_t"), ageH=st.get("age_h"),
                         nObs30=st.get("n"), medFt=st.get("med_ft"), lastFt=st.get("last_ft"), fullPoolFt=lake.get("fullPoolFt"),
                         deltaFullPoolFt=(round(st["med_ft"] - lake["fullPoolFt"], 2) if st.get("med_ft") is not None and lake.get("fullPoolFt") is not None else ""),
                         **{k: (int(v) if isinstance(v, bool) else v) for k, v in c.items()}, status=status, capability=r.get("capOverride") or V.capability(r["prov"]), reasons=r["reasons"], loc=r["extra"].get("loc", ""),
                         probeKey=V.probe_key(r), lat=r["lat"], lon=r["lon"], alts=json.dumps(r["alts"]), v11=",".join(notes), ident=int(ident)))
    byl = collections.defaultdict(list)
    for x in rows:
        byl[x["lakeId"]].append(x)
    corroborate(rows, byl)
    V.resolve_conflicts(rows, byl)
    return rows, lakes


def corroborate(rows, byl):
    for lid, xs in byl.items():
        hardpass = [x for x in xs if x["R1_geo"] and x["R2_identity"] and x["R3_notrap"] and x["R4_state"] and x["R5_unique"] and x["R6_live"] and x["medFt"] not in (None, "") and x["family"] == "elev"]
        for x in xs:
            x["corroboratedBy"] = ""
            if x["family"] != "elev" or x not in hardpass:
                continue
            for y in hardpass:
                if y is x or (y["prov"], y["station"]) == (x["prov"], x["station"]):
                    continue
                ox, oy = V.ORIGIN.get(x["prov"]), V.ORIGIN.get(y["prov"])
                if ox in V.RELAY or oy in V.RELAY or ox == oy:
                    continue
                if (V._gap(x, y) or 99) <= 2.0:
                    x["corroboratedBy"] = f"{y['prov']}:{y['station']}"; break
            if x["status"] in ("PENDING_CORROBORATION", "PENDING_NO_FULLPOOL") and x["corroboratedBy"]:
                x["status"] = "VERIFIED_CORROBORATED"


RANK = {"VERIFIED": 0, "VERIFIED_CORROBORATED": 1, "VERIFIED_FLAG": 1, "STAGE_ONLY": 2, "PENDING_CORROBORATION": 3, "PENDING_NO_FULLPOOL": 4, "CONFLICT": 8, "HISTORY_ONLY": 8, "REJECT": 9, "REJECT_CONFLICT": 9}


def best_per_lake(rows):
    best = {}
    for x in rows:
        key = (RANK[x["status"]], 0 if x["capability"] == "DIRECT_OPERATOR_POOL" else 1, -x["matchScore"])
        if x["lakeId"] not in best or key < best[x["lakeId"]][0]:
            best[x["lakeId"]] = (key, x)
    return {k: v[1] for k, v in best.items()}


if __name__ == "__main__":
    base = {k: 0 for k in ("R1b", "R2b", "R4b", "R5b", "RGL", "R8b", "R2c", "R8c", "RI", "R1c", "R2d")}
    for name, fl in [("v1 (reproduction)", base), ("v1.1 all", {k: 1 for k in base})] + [(f"v1 + {k}", {**base, k: 1}) for k in base]:
        rows, lakes = run(fl)
        b = best_per_lake(rows)
        cnt = collections.Counter(v["status"] for v in b.values())
        core = cnt["VERIFIED"] + cnt["VERIFIED_CORROBORATED"]
        print(f"{name:20s} core={core} flag={cnt['VERIFIED_FLAG']} stage={cnt['STAGE_ONLY']} pend={cnt['PENDING_CORROBORATION']+cnt['PENDING_NO_FULLPOOL']} hist_only={cnt['HISTORY_ONLY']} conflict={cnt['CONFLICT']}")
