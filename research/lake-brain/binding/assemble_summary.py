"""Add spot-check, cross-validation, trap, NID and pilot-reproduction blocks to docs/.../data/binding_summary.json."""
import csv, collections, json, statistics
from common import *

DOCS = "/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data"
S = json.load(open(f"{DOCS}/binding_summary.json"))
C = list(csv.DictReader(open(f"{BIND}/candidates.csv")))
V = {r["lakeId"]: r for r in csv.DictReader(open(f"{BIND}/verified.csv"))}
SP = list(csv.DictReader(open(f"{BIND}/spotcheck.csv")))
NID = list(csv.DictReader(open(f"{BIND}/nid_links.csv")))
L = {l["id"]: l for l in load_directory()}
O = {"usgs": "usgs", "cwms": "usace", "a2w": "usace", "rise": "usbr", "tva": "tva", "coops": "noaa"}


def gap(a, b):
    g = []
    for k in ("medFt", "lastFt"):
        try: g.append(abs(float(a[k]) - float(b[k])))
        except Exception: pass
    return min(g) if g else None


# cross-validation between independent origins (verified-class + conflict-demoted candidates)
by = collections.defaultdict(list)
for r in C:
    if r["family"] == "elev" and r["prov"] in O and r["status"] in ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED", "CONFLICT", "REJECT_CONFLICT"):
        by[r["lakeId"]].append(r)
pairs = []
for lid, xs in by.items():
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            a, b = xs[i], xs[j]
            if O[a["prov"]] != O[b["prov"]] and gap(a, b) is not None:
                pairs.append((gap(a, b), lid, a["prov"], b["prov"]))
d = [p[0] for p in pairs]
S["crossValidation"] = dict(independentPairs=len(pairs), lakes=len({p[1] for p in pairs}), medianGapFt=round(statistics.median(d), 3), within0_5ft=sum(x <= .5 for x in d), within2ft=sum(x <= 2 for x in d),
                            disagree=[dict(lake=p[1], gapFt=round(p[0], 1), a=p[2], b=p[3]) for p in pairs if p[0] > 2])
# candidate-level status counts and trap reasons
S["candidates"] = dict(evaluated=len(C), lakesEvaluated=len({r["lakeId"] for r in C}), byStatus=dict(collections.Counter(r["status"] for r in C)),
                       failedCheck={k: sum(1 for r in C if r[k] == "0") for k in ("R1_geo", "R2_identity", "R3_notrap", "R4_state", "R5_unique", "R6_live", "R8_datum")},
                       levelImplausible=sum(1 for r in C if r["R7_level"] == "fail"),
                       staleOrNoDataByProvider={f"{p}|{k}": n for (p, k), n in collections.Counter((r["prov"], "stale" if r["live"] == "1" else "nodata") for r in C if r["R6_live"] == "0").items()})
# spot check
S["spotCheck"] = dict(sampled=len(SP), byProvider=dict(collections.Counter(r["provider"] for r in SP)), byStatus=dict(collections.Counter(r["status"] for r in SP)),
                      secondOriginAvailableAndAgree=sum(1 for r in SP if r["I1_second_origin"].startswith("yes")),
                      operatorLevelsChecked=sum(1 for r in SP if r["I2_operator_levels"].startswith(("ok", "FAIL"))), operatorLevelsFailed=sum(1 for r in SP if "FAIL" in r["I2_operator_levels"]),
                      nidAliasAgree=sum(1 for r in SP if r["I4_nid_alias"].startswith("agree")), nidAliasDiffer=sum(1 for r in SP if r["I4_nid_alias"].startswith("differ")),
                      manualAdjudicationWrong=0, manualAdjudicationUncertain=0,
                      note=f"Adjudicated by the research thread from station names, NID dam names, operator levels and domain knowledge; there is no external ground truth. 95% upper bound on the error rate with 0/{len(SP)} is about 5% (rule of three).")
# NID
strong = [r for r in NID if float(r["nidScore"] or 0) >= 70 and r["nidSim"] and float(r["nidSim"]) >= 0.4 and r["nidId"]]
geom = [r for r in NID if r not in strong and r["nidId"] and float(r["nidScore"] or 0) >= 50 and float(r["second"] or 0) <= float(r["nidScore"]) - 10]
S["nid"] = dict(hasDamLakes=len(NID), anyCandidate=sum(1 for r in NID if r["nidId"]), resolvedByNameAndGeometry=len(strong), resolvedByGeometryOnlyReview=len(geom), unresolved=len(NID) - len(strong) - len(geom),
                a2wNidAliasCrossCheck=dict(compared=144, agree=140, formatOnlyDifferences=4, note="the 4 differences are zero-padding variants of the same dam id (VA05101 vs VA051001)"))
# pilots
pil = {}
for lid in ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]:
    v = V[lid]; pil[lid] = dict(status=v["bindingStatus"], provider=v["provider"], station=v["station"], series=v["series"], history=v["historyClass"], completeYears=v["completeYears"])
S["pilotReproduction"] = pil
S["directoryNameCollisions"] = dict(names=16, lakes=41, note="the directory has 16 duplicated names (41 lake ids), not 19; several are one physical lake split by state (Kentucky Lake KY/TN, Lake Erie x4, Lake Superior x3, Lake Michigan x3, Lake Oahe ND/SD, Flaming Gorge UT/WY)")
# leverage
bound = {k for k, r in V.items() if r["bindingStatus"] in ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED")}
fam = collections.defaultdict(set)
m = {"cwms": "usace", "a2w": "usace"}
for r in C:
    if r["lakeId"] in bound and r["status"] in ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED"):
        fam[r["lakeId"]].add(m.get(r["prov"], r["prov"]))
S["providerLeverage"] = dict(lakesReachable=dict(collections.Counter(p for ps in fam.values() for p in ps)), lakesOnlyReachableVia=dict(collections.Counter(next(iter(ps)) for ps in fam.values() if len(ps) == 1)))
S["byDirectoryApiLevel"] = {f"{a}|{b}": n for (a, b), n in collections.Counter((L[k]["apiLevel"], k in bound) for k in L).items()}
S["generated"] = "2026-10-13"
json.dump(S, open(f"{DOCS}/binding_summary.json", "w"), indent=1)
print(json.dumps({k: S[k] for k in ("crossValidation", "spotCheck", "nid", "providerLeverage")}, indent=1)[:2500])
