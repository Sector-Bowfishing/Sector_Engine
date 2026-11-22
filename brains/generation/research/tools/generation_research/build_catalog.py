"""Build the Generation Brain dam catalog (runtime/knowledge/dams.json) from repository evidence only. Offline; no network.

Inputs (all inside the Engine repository):
  * the Engine lake directory (Sources/SectorEngine/Support/LakeDirectory.swift): the 621 lakes, `hasDam`, `operatorName`, `cwmsOffice`;
  * Lake Brain's reviewed bindings (jobs/lake-brain/data/bindings.proposed.v1.json): NID dam record and the CWMS / Access2Water location
    of each bound lake (the location token of its pool series);
  * records/tva_locations.json and records/swpa_projects.json (each entry names its evidence).

Every lake with a dam gets one record with an operator group, the sources that can carry its release, and a coverage state with a stated reason.
Nothing is guessed: a source whose series or id is not evidenced is DISCOVERY_PENDING, never bound. Lakes without a dam are counted, not listed.

  python -m generation_research.build_catalog --repo <engine checkout> [--check]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDS = os.path.join(HERE, "records")
CATALOG_SCHEMA = "generation-dam-catalog-v1"
CATALOG_VERSION = "generation-dams-2026-11-22.1"

UTILITY_TOKENS = ("power", "energy", "electric", "hydro", "brookfield", "firstlight", "duke", "dominion", "entergy", "ameren", "nipsco", "srp",
                  "santee cooper", "utilities", "utility", "lcra", "grand river dam authority", "seattle city light", "pg&e", "cnppid", "nppd",
                  "constellation", "crisp county", "greenwood county cpw", "alliant", "xcel", "empire/liberty", "cube hydro", "eagle creek",
                  "minnkota", "city water light", "tid/mid", "great river hydro", "aep", "portland general")

COVERAGE = ("BOUND", "BOUND_ACCESS_CHECK", "DISCOVERY_PENDING", "PERMISSION_REQUIRED", "NO_KNOWN_PUBLIC_RELEASE_DATA")


def directory(repo: str) -> list[dict]:
    src = open(os.path.join(repo, "Sources", "SectorEngine", "Support", "LakeDirectory.swift"), encoding="utf-8").read()
    rows = [json.loads(m) for m in re.findall(r'^(\{"name".*\}),?$', src, re.M)]
    if not rows:
        raise SystemExit("lake directory not found or unparseable")
    return rows


def lake_bindings(repo: str) -> dict[str, dict]:
    p = os.path.join(repo, "jobs", "lake-brain", "data", "bindings.proposed.v1.json")
    return {b["lakeId"]: b for b in json.load(open(p, encoding="utf-8"))["bindings"]}


def group_of(operator: str, lake_id: str, swpa: dict) -> str:
    o = operator.lower()
    if o.startswith("tva"):
        return "TVA"
    if "usace nashville" in o:
        return "TVA_CUMBERLAND"
    if lake_id in swpa:
        return "SWPA_USACE"
    if "usace" in o:
        return "USACE"
    if "usbr" in o:
        return "USBR"
    if any(t in o for t in UTILITY_TOKENS):
        return "UTILITY_OR_POWER_AUTHORITY"
    return "OTHER_OPERATOR"


def cwms_location(binding: dict | None) -> dict | None:
    """The CWMS location of a lake's reviewed pool series (the token before the first '.'), with its office. Access2Water reads the same
    district database, so its `district:location` names the CWMS location too."""
    if not binding:
        return None
    for live in binding.get("live") or []:
        if live.get("provider") == "cwms" and live.get("series"):
            return {"office": live["station"], "location": live["series"].split(".")[0], "evidence": f"Lake binding cwms {live['station']} {live['series']}"}
    for live in binding.get("live") or []:
        if live.get("provider") == "a2w" and ":" in (live.get("station") or ""):
            office, loc = live["station"].split(":", 1)
            return {"office": office, "location": loc, "evidence": f"Lake binding a2w {live['station']} {live.get('series')}"}
    return None


def build(repo: str) -> dict:
    rows = directory(repo)
    bindings = lake_bindings(repo)
    tva = {x["lakeId"]: x for x in json.load(open(os.path.join(RECORDS, "tva_locations.json")))["locations"]}
    swpa = {x["lakeId"]: x for x in json.load(open(os.path.join(RECORDS, "swpa_projects.json")))["projects"]}
    ids = {f"{r['name']}|{r['state']}" for r in rows}
    unknown = sorted((set(tva) | set(swpa)) - ids)
    if unknown:
        raise SystemExit(f"records name lakes that are not in the directory: {unknown}")
    dams = []
    for r in rows:
        if not r["hasDam"]:
            continue
        lid = f"{r['name']}|{r['state']}"
        b = bindings.get(lid)
        g = group_of(r["operatorName"], lid, swpa)
        nid = (b or {}).get("dam") or {}
        rec = {"lakeId": lid, "name": r["name"], "state": r["state"], "lat": r["lat"], "lon": r["lon"], "operatorName": r["operatorName"], "group": g,
               "dam": {"name": nid.get("damName"), "nidId": nid.get("nidId"), "hydropower": nid.get("hydropower"),
                       "source": nid.get("source") if nid else None},
               "cwmsOffice": r.get("cwmsOffice"), "sources": [], "usgsTailwater": {"status": "PROBE_PENDING",
                                                                                     "note": "downstream USGS discharge (00060) gauge not yet located (NLDI probe)"}}
        loc = cwms_location(b)
        if g in ("TVA", "TVA_CUMBERLAND") and lid in tva:
            t = tva[lid]
            rec["sources"].append({"provider": "tva", "status": "BOUND", "locationId": t["locationId"], "roles": ["schedule", "units", "discharge", "tailwater"],
                                   "evidence": t["evidence"]})
        elif g in ("TVA", "TVA_CUMBERLAND"):
            rec["sources"].append({"provider": "tva", "status": "DISCOVERY_PENDING", "roles": ["schedule", "units", "discharge", "tailwater"],
                                   "reason": "TVA LocationID not evidenced in the repository; resolve by exact dam name against TVA /locations (probe_tva_roster)"})
        if g == "SWPA_USACE":
            s = swpa[lid]
            rec["sources"].append({"provider": "swpa", "status": "BOUND", "project": s["abbr"], "units": s["units"], "roles": ["schedule"],
                                   "evidence": "records/swpa_projects.json (SWPA project table)"})
        if g in ("TVA_CUMBERLAND", "SWPA_USACE", "USACE"):
            rec["sources"].append({"provider": "cwms", "status": "DISCOVERY_PENDING", "office": (loc or {}).get("office") or r.get("cwmsOffice"),
                                   "location": (loc or {}).get("location"), "locationEvidence": (loc or {}).get("evidence"),
                                   "roles": ["discharge", "turbine", "spill", "generation", "tailwater"],
                                   "reason": ("outflow / turbine / spill series not yet bound: run probe_cwms_release on the location's catalog"
                                              if loc else "CWMS location not yet resolved for this lake (no reviewed Lake binding); office from the directory")})
        elif loc:
            rec["sources"].append({"provider": "cwms", "status": "DISCOVERY_PENDING", "office": loc["office"], "location": loc["location"],
                                   "locationEvidence": loc["evidence"], "roles": ["discharge", "turbine", "spill", "generation", "tailwater"],
                                   "reason": "USACE CWMS carries this non-USACE project (Lake Brain reads its pool there); release series not yet bound"})
        rise_item = next((l.get("station") for l in (b or {}).get("live") or [] if l.get("provider") == "rise"), None)
        if g == "USBR" or rise_item:
            rec["sources"].append({"provider": "rise", "status": "DISCOVERY_PENDING", "roles": ["discharge"], "elevationItemId": rise_item,
                                   "reason": "RISE release item (Lake/Reservoir Release) not yet bound: run probe_rise_release"
                                             + (" from the location of elevation item " + str(rise_item) if rise_item else "")})
        rec["coverage"], rec["reason"] = coverage(rec)
        dams.append(rec)
    return {"schema": CATALOG_SCHEMA, "catalogVersion": CATALOG_VERSION,
            "inputs": {"directory": "Sources/SectorEngine/Support/LakeDirectory.swift", "lakeBindings": "jobs/lake-brain/data/bindings.proposed.v1.json",
                       "records": ["research/tools/generation_research/records/tva_locations.json", "research/tools/generation_research/records/swpa_projects.json"]},
            "directoryLakeCount": len(rows), "noDamLakeCount": sum(1 for r in rows if not r["hasDam"]), "damLakeCount": len(dams),
            "counts": {"byGroup": dict(sorted(Counter(d["group"] for d in dams).items())),
                       "byCoverage": dict(sorted(Counter(d["coverage"] for d in dams).items()))},
            "dams": sorted(dams, key=lambda d: d["lakeId"])}


def coverage(rec: dict) -> tuple[str, str]:
    st = {(s["provider"], s["status"]) for s in rec["sources"]}
    if ("tva", "BOUND") in st:
        return "BOUND", "TVA publishes this dam's unit schedule and hourly release (bound LocationID)"
    if ("swpa", "BOUND") in st:
        return "BOUND_ACCESS_CHECK", "SWPA schedule bound but its page access check is open; CWMS release series pending discovery"
    if any(s == "DISCOVERY_PENDING" for _, s in st):
        prov = sorted(p for p, s in st if s == "DISCOVERY_PENDING")
        return "DISCOVERY_PENDING", f"an allowed official source ({', '.join(prov)}) covers this operator; the release series is not yet bound"
    if rec["group"] == "UTILITY_OR_POWER_AUTHORITY":
        return "PERMISSION_REQUIRED", "the operator publishes release or generation only on its own web pages; permission first (owner rule); USGS tailwater discharge probe pending"
    return "NO_KNOWN_PUBLIC_RELEASE_DATA", "the operator is not known to publish release data; USGS tailwater discharge probe pending"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "..", "runtime", "knowledge", "dams.json"))
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed catalog differs from a rebuild")
    a = ap.parse_args(argv)
    cat = build(a.repo)
    text = json.dumps(cat, indent=1, sort_keys=False) + "\n"
    if a.check:
        same = os.path.exists(a.out) and open(a.out, encoding="utf-8").read() == text
        print("catalog up to date" if same else "catalog differs from a rebuild")
        return 0 if same else 1
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(json.dumps({"damLakeCount": cat["damLakeCount"], **cat["counts"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
