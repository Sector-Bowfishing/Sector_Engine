"""Phase 3: apply the pre-registered REVIEW CRITERIA (see docs) to every probed candidate; pick the machine-verified binding per lake.
Outputs: binding/candidates.csv (all evaluated candidates), binding/verified_live.json (per-lake chosen + alternates)."""
import csv, collections, json, re
from common import *
from probe import load_cands

CRITERIA_VERSION = "binding-review-v1"
# tolerance windows for level plausibility vs directory fullPoolFt (ft, level minus fullPool)
STRONG = (-25.0, 8.0)     # poolBasis=fullPool & poolConfidence in {high,med}
WEAK = (-60.0, 25.0)
# WEAK: low confidence / natural surfaces / unknown basis
DRAW = (-220.0, 0)       # deep drawdown of large western reservoirs; requires strong identity
LIVE_H_SUBDAILY = 72
LIVE_H_DAILY = 192
GEO_M = 1500
OP_PROVIDERS = {"cwms": "DIRECT_OPERATOR_POOL", "rise": "DIRECT_OPERATOR_POOL", "tva": "DIRECT_OPERATOR_POOL", "a2w": "DIRECT_OPERATOR_POOL"}


ORIGIN = {'usgs': 'usgs', 'cwms': 'usace', 'a2w': 'usace', 'rise': 'usbr', 'tva': 'tva', 'twdb': 'relay', 'nwps': 'relay', 'coops': 'noaa'}
RELAY = {'relay'}


def capability(prov):
    return OP_PROVIDERS.get(prov, "DIRECT_LAKE_GAUGE")


def probe_key(r):
    if r["prov"] == "cwms":
        return f"cwms|{r['station']}|{r['extra']['loc']}"
    if r["prov"] == "rise":
        return f"rise|{r['stationName']}"
    if r["prov"] == "a2w":
        return f"a2w|{r['station']}"
    return f"{r['prov']}|{r['station']}"


def evaluate(r, lake, probes, haspoly, claim):
    pr = probes.get(probe_key(r))
    c = {}
    states = set(lake.get("states") or [lake["state"]])
    c["R1_geo"] = (r["distM"] <= GEO_M) if haspoly else ((int(r["distM"]) <= 3000 and r["nameSim"] >= 0.5) or (int(r["distM"]) <= 25000 and r["nameSim"] >= 0.6))
    lakeparam = r["prov"] == "usgs" and r["series"] in ("00062", "62614", "62615", "62616", "72020", "72022")
    inside = int(r["distM"]) <= 150
    c["R2_identity"] = bool(r["nameSim"] >= 0.5 or (inside and (r["stype"] in ("LK", "Reservoir", "Corps Reservoir", "RES", "HP") or lakeparam)))
    c["R3_notrap"] = "TRAP" not in r["reasons"]
    stt = None
    c["R4_state"] = "state-mismatch" not in r["reasons"]
    ck = claim.get(probe_key(r))
    c["R5_unique"] = not (ck and ck[0] != lake["id"] and ck[0].split("|")[0] != lake["id"].split("|")[0] and ck[1] >= r["nameSim"] + 0.2)   # same-name siblings (one physical lake split by state) do not conflict
    st = (pr or {}).get("stats") or {}
    live = bool(pr and pr.get("live") and st.get("n"))
    sub_daily = bool(pr and (pr.get("mode") == "iv" or (pr.get("step") or "") not in ("1Day", "~1Day", "") or r["prov"] in ("nwps", "coops")))
    lim = LIVE_H_SUBDAILY if sub_daily else LIVE_H_DAILY
    c["R6_live"] = bool(live and st.get("age_h") is not None and -3 <= st["age_h"] <= lim)   # future-dated stamps = forecast/misstamped, rejected
    # R7 level plausibility
    fam = (pr or {}).get("family") or r["family"]
    fp = lake.get("fullPoolFt")
    lvl = st.get("med_ft")
    plaus = "na"
    if fam == "stage" or lvl is None or fp is None:
        plaus = "na"
    else:
        d = lvl - fp
        strong_basis = lake.get("poolBasis") == "fullPool" and lake.get("poolConfidence") in ("high", "med")
        if strong_basis and STRONG[0] <= d <= STRONG[1]:
            plaus = "strong"
        elif lake.get("poolBasis") == "naturalSurface" and -15 <= d <= 10 and False:
            plaus = "strong"
        elif DRAW[0] <= d < (STRONG[0] if strong_basis else WEAK[0]) and fp > 500 and lvl / fp >= 0.80 and d <= STRONG[1]:
            plaus = "drawdown"
        elif WEAK[0] <= d <= WEAK[1]:
            plaus = "weak"
        else:
            plaus = "fail"
    c["R7_level"] = plaus
    c["R8_datum"] = bool(fam == "stage" or (r["datum"] or "") != "" or (pr and pr.get("vdi")) or r["prov"] in ("twdb", "nwps", "rise", "coops", "tva", "a2w"))
    return c, pr, st, fam, plaus


def run():
    lakes = {l["id"]: l for l in load_directory()}
    probes = json.load(open(f"{BIND}/probe_results.json"))
    cands = load_cands()
    from match import load_polys
    haspoly = set(load_polys().keys())
    # claim map: each probed site key -> best lake (by nameSim, then -dist) among all candidates with score >= 40
    allrows = list(csv.DictReader(open(f"{BIND}/candidates_all.csv")))
    claim = {}
    for r in allrows:
        r["score"] = float(r["score"]); r["extra"] = json.loads(r["extra"]); r["nameSim"] = float(r["nameSim"]); r["distM"] = int(r["distM"])
        if r["score"] < 40:
            continue
        k = probe_key(r)
        cur = claim.get(k)
        if cur is None or (r["nameSim"], -r["distM"]) > (cur[1], -cur[2]):
            claim[k] = (r["lakeId"], r["nameSim"], r["distM"])
    rows = []
    for r in cands:
        r["nameSim"] = float(r["nameSim"]); r["distM"] = int(r["distM"])
        lake = lakes[r["lakeId"]]
        c, pr, st, fam, plaus = evaluate(r, lake, probes, r["lakeId"] in haspoly, claim)
        ident = bool(r["nameSim"] >= 0.6 and r["distM"] <= 500)
        hard = all(c[k] for k in ("R1_geo", "R2_identity", "R3_notrap", "R4_state", "R5_unique", "R6_live", "R8_datum"))
        level = c["R7_level"]
        status = "REJECT"
        if hard and level == "strong":
            status = "VERIFIED"
        elif hard and level in ("weak", "drawdown") and ident:
            status = "VERIFIED_FLAG"
        elif hard and level in ("weak", "drawdown"):
            status = "PENDING_CORROBORATION"
        elif hard and level == "na":
            if fam == "stage":
                lakey = r["stype"] == "LK" or bool(re.search(r"\b(lake|lk|res|reservoir|pond|pool)\b", r["stationName"] or "", re.I))
                status = "STAGE_ONLY" if (ident and lakey) else "REJECT"
            else:
                status = "PENDING_NO_FULLPOOL"
        rows.append(dict(lakeId=r["lakeId"], lakeName=r["lakeName"], state=r["lakeState"], prov=r["prov"], station=r["station"], series=(pr or {}).get("series") or (pr or {}).get("param") or (pr or {}).get("item") or r["series"],
                         stationName=r["stationName"], stype=r["stype"], family=fam, distM=r["distM"], nameSim=r["nameSim"], matchScore=r["score"], live=int(bool(pr and pr.get("live"))),
                         lastObs=st.get("last_t"), ageH=st.get("age_h"), nObs30=st.get("n"), medFt=st.get("med_ft"), lastFt=st.get("last_ft"), fullPoolFt=lake.get("fullPoolFt"),
                         deltaFullPoolFt=(round(st["med_ft"] - lake["fullPoolFt"], 2) if st.get("med_ft") is not None and lake.get("fullPoolFt") is not None else ""),
                         **{k: (int(v) if isinstance(v, bool) else v) for k, v in c.items()}, status=status, capability=capability(r["prov"]), reasons=r["reasons"], loc=r["extra"].get("loc", ""), probeKey=probe_key(r), lat=r["lat"], lon=r["lon"], alts=json.dumps(r["alts"])))
    # corroboration: lake has >=2 candidates at distinct sites (different provider or station) that pass hard checks and agree within 2 ft (median level)
    byl = collections.defaultdict(list)
    for x in rows:
        byl[x["lakeId"]].append(x)
    for lid, xs in byl.items():
        hardpass = [x for x in xs if x["R1_geo"] and x["R2_identity"] and x["R3_notrap"] and x["R4_state"] and x["R5_unique"] and x["R6_live"] and x["medFt"] not in (None, "") and x["family"] == "elev"]
        for x in xs:
            x["corroboratedBy"] = ""
            if x["family"] != "elev" or x not in hardpass:
                continue
            for y in hardpass:
                if y is x or (y["prov"], y["station"]) == (x["prov"], x["station"]):
                    continue
                if ORIGIN.get(x["prov"]) in RELAY or ORIGIN.get(y["prov"]) in RELAY or ORIGIN.get(x["prov"]) == ORIGIN.get(y["prov"]):
                    continue   # relays / same-origin series are not independent corroboration
                if (_gap(x, y) or 99) <= 2.0:
                    x["corroboratedBy"] = f"{y['prov']}:{y['station']}"
                    break
            if x["status"] == "PENDING_CORROBORATION" and x["corroboratedBy"]:
                x["status"] = "VERIFIED_CORROBORATED"
            if x["status"] == "PENDING_NO_FULLPOOL" and x["corroboratedBy"]:
                x["status"] = "VERIFIED_CORROBORATED"
    resolve_conflicts(rows, byl)
    return rows, lakes


VER = ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED")


def _gap(a, b):
    """smallest of the 30-day-median and last-value gaps (ft); robust to cadence/lag differences"""
    g = []
    for k in ("medFt", "lastFt"):
        try:
            g.append(abs(float(a[k]) - float(b[k])))
        except Exception:
            pass
    return min(g) if g else None


def resolve_conflicts(rows, byl):
    """R9: independent verified-class series of one lake must agree within 2 ft. Strong beats flagged; relays must agree with every origin;
    two equal-class origins that disagree -> CONFLICT (not counted, needs review) unless a third origin sides with one."""
    for lid, xs in byl.items():
        vs = [x for x in xs if x["status"] in VER and x["family"] == "elev"]
        origins = [x for x in vs if ORIGIN.get(x["prov"]) not in RELAY]
        relays = [x for x in vs if ORIGIN.get(x["prov"]) in RELAY]
        bad = collections.defaultdict(set)   # candidate id -> set of disagreeing candidate ids
        for i, a in enumerate(origins):
            for b in origins[i + 1:]:
                if ORIGIN[a["prov"]] == ORIGIN[b["prov"]]:
                    continue
                g = _gap(a, b)
                if g is not None and g > 2.0:
                    bad[id(a)].add(id(b)); bad[id(b)].add(id(a))
        by_id = {id(x): x for x in vs}
        for a in origins:
            if id(a) not in bad:
                continue
            others = [by_id[o] for o in bad[id(a)]]
            if a["status"] == "VERIFIED_FLAG" and any(o["status"] in ("VERIFIED", "VERIFIED_CORROBORATED") for o in others):
                a["status"] = "REJECT_CONFLICT"
        conf = [a for a in origins if id(a) in bad and a["status"] in VER and any(by_id[o]["status"] in VER for o in bad[id(a)])]
        for a in conf:
            a["status"] = "CONFLICT"
        for rl in relays:
            for o in origins:
                if o["status"] in VER:
                    g = _gap(rl, o)
                    if g is not None and g > 2.0:
                        rl["status"] = "REJECT_CONFLICT"; break


if __name__ == "__main__":
    rows, lakes = run()
    with open(f"{BIND}/candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    best = {}
    rank = {"VERIFIED": 0, "VERIFIED_CORROBORATED": 1, "VERIFIED_FLAG": 1, "STAGE_ONLY": 2, "PENDING_CORROBORATION": 3, "PENDING_NO_FULLPOOL": 4, "CONFLICT": 8, "REJECT": 9, "REJECT_CONFLICT": 9}
    for x in rows:
        k = x["lakeId"]
        key = (rank[x["status"]], 0 if x["capability"] == "DIRECT_OPERATOR_POOL" else 1, -x["matchScore"])
        if k not in best or key < best[k][0]:
            best[k] = (key, x)
    cnt = collections.Counter(v[1]["status"] for v in best.values())
    print("lakes with >=1 probed candidate:", len(best), dict(cnt))
    print("status over all candidates:", dict(collections.Counter(x["status"] for x in rows)))
