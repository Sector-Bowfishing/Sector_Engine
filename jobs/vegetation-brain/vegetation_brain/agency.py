"""LEVEL 1 - agency vegetation observations, shown as-is.

An authoritative provider already owns this truth, so Sector does not re-derive it: verify SOURCE, DATE, UNITS, sanity and
provenance, then pass it through. Nothing here is a Sector prediction and a failure of a Level-3 claim never disables it.

First source (conservative, open, fleet-matched): Florida FWC Long-Term Monitoring lake PAC / PVI
  layer  https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/41   (LTM_lakes_PAC_PVI)
  PAC    percent of the lake surface area with vegetation growing (FWC definition, myfwc.com plant-mapping page)
  PVI    percent of the lake's water column occupied by vegetation (lake mean)
  It describes ALL vegetation the agency's sonar sees (including submerged). That is the AGENCY's observation; it is not Sector observing
  submerged vegetation and it does not change `submergedVegetation.observed = false`.
Survey date precision is the YEAR (FWC's LTM mapping runs May-Oct; the month is not published).
Customer use of these values is NOT cleared (licence UNCONFIRMED): the block is marked internalOnly until a licence answer exists."""
from __future__ import annotations

from dataclasses import dataclass

AGENCY_STALE_YEARS = 2          # an agency survey older than this is shown as historical
SOURCE_FWC = {
    "id": "fwc-ltm-pac-pvi", "agency": "Florida Fish and Wildlife Conservation Commission (Freshwater Fisheries Research)",
    "layer": "https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/41",
    "definitionsUrl": "https://myfwc.com/research/freshwater/monitoring/plant-mapping/",
    "units": {"pac": "percent of lake surface area with vegetation", "pvi": "percent of the water column occupied by vegetation (lake mean)"},
    "datePrecision": "YEAR", "vegetationScope": "all vegetation seen by agency sonar (emergent, floating and submerged)",
    "licence": "UNCONFIRMED_FOR_CUSTOMER_USE", "internalOnly": True,
}

# Fleet lake -> FWC lake name (verified by name against the layer; one-to-one reviewed by hand)
FWC_NAME_MAP = {
    "Apopka|FL": "Apopka", "Griffin|FL": "Griffin", "Harris|FL": "Harris+Little Harris", "Istokpoga|FL": "Istokpoga",
    "Kissimmee|FL": "Kissimmee", "Lochloosa|FL": "Lochloosa", "East Lake Tohopekaliga|FL": "East Lake Tohopekaliga",
    "Tohopekaliga (Toho)|FL": "Tohopekaliga", "Okeechobee|FL": "Okeechobee",
}
MATCH_NOTES = {"Harris|FL": "FWC reports the Harris + Little Harris chain together",
               "Okeechobee|FL": "FWC reports several sector rows per year; they are listed, never averaged by Sector"}


class AgencyError(ValueError):
    pass


def validate_row(r: dict) -> list[str]:
    """Return sanity problems for one source row (empty = clean)."""
    bad = []
    for k in ("pac", "pvi"):
        v = r.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0 <= v <= 100):
            bad.append(f"{k} out of range or not numeric: {v!r}")
    if not isinstance(r.get("year"), int) or not (1990 <= r["year"] <= 2100):
        bad.append(f"year invalid: {r.get('year')!r}")
    if not bad and r["pvi"] > r["pac"] + 1:
        bad.append("PVI exceeds PAC: volume infested cannot exceed area covered (unit or column mix-up)")
    return bad


def build_record(lake_id: str, fwc_rows: list, retrieved_on: str) -> dict:
    """fwc_rows: attribute dicts from the FWC layer for ONE lake name. Rows failing sanity are dropped and counted, never repaired."""
    rows, dropped = [], []
    for a in fwc_rows:
        r = {"year": a.get("Year"), "pac": a.get("PAC"), "pvi": a.get("PVI"), "label": (a.get("Label") or "").strip()}
        p = validate_row(r)
        (dropped if p else rows).append({**r, "problems": p} if p else r)
    rows.sort(key=lambda r: (r["year"], r["label"]))
    return {"lakeId": lake_id, "source": {k: SOURCE_FWC[k] for k in SOURCE_FWC}, "fwcLakeName": FWC_NAME_MAP.get(lake_id),
            "matchNote": MATCH_NOTES.get(lake_id), "retrievedOn": retrieved_on, "rows": rows, "rowsDropped": dropped,
            "multipleRowsPerYear": len({r["year"] for r in rows}) != len(rows)}


def agency_block(record: dict | None, now_year: int, extra: list | None = None) -> dict:
    """The compact Level-1 block for the state. Never inferred: absent record => NOT_ASSESSED with a reason."""
    extras = [b for b in (extra or []) if b]
    if not record or not record.get("rows"):
        if extras:
            return {**extras[0], "additional": extras[1:]} if len(extras) > 1 else dict(extras[0])
        return {"status": "NOT_ASSESSED", "reason": "no agency vegetation survey ingested for this lake", "level": 1}
    latest = max(r["year"] for r in record["rows"])
    last = [r for r in record["rows"] if r["year"] == latest]
    age = now_year - latest
    src = record["source"]
    out = {"status": "PROVIDER_VERIFIED", "level": 1, "sourceId": src["id"], "agency": src["agency"], "surveyYear": latest,
           "datePrecision": src["datePrecision"], "ageYears": age, "historical": age > AGENCY_STALE_YEARS,
           "values": [{"pac": r["pac"], "pvi": r["pvi"], **({"label": r["label"]} if record.get("multipleRowsPerYear") else {})} for r in last],
           "units": src["units"], "scope": src["vegetationScope"], "yearsAvailable": sorted({r["year"] for r in record["rows"]}),
           "retrievedOn": record["retrievedOn"], "licence": src["licence"], "internalOnly": src["internalOnly"],
           "verified": ["source identity (agency layer)", "units (agency definitions)", "survey year", "range sanity (0-100, PVI <= PAC)"]}
    if record.get("matchNote"):
        out["matchNote"] = record["matchNote"]
    if extras:
        out["additional"] = extras
    out["summary"] = (f"{src['agency'].split(' (')[0]} survey {latest}: vegetation covers {last[0]['pac']} % of the lake surface and occupies "
                      f"{last[0]['pvi']} % of its water volume" + (" (several sectors reported)" if len(last) > 1 else "")
                      + (" - historical" if out["historical"] else ""))
    return out


# --------------------------------------------------------------------------------------------- source 2: SFWMD Okeechobee littoral map
SOURCE_SFWMD_OKEE = {
    "id": "sfwmd-okeechobee-littoral", "agency": "South Florida Water Management District",
    "layer": "https://services1.arcgis.com/sDAPyc2rGRn7vf9B/arcgis/rest/services/VEG_OKE_2016/FeatureServer/0",
    "units": {"areaKm2": "km2 of 1-hectare grid cells (cell count x 0.01 km2) classified by dominant vegetation"},
    "datePrecision": "MONTH", "surveyYear": 2016, "surveyMonth": 6,
    "scope": "Moore Haven and the south islands part of the Lake Okeechobee marsh only; dominant class per 1 ha cell, photo-interpreted from June 2016 stereo aerial imagery",
    "licence": "AS_IS_ACKNOWLEDGEMENT_REQUESTED", "internalOnly": True,
}
SFWMD_MAX_CLASSES = 6
OPEN_WATER_CODE = "OW"


def build_sfwmd_record(lake_id: str, class_counts: list, retrieved_on: str, mercator_area_km2: dict | None = None) -> dict:
    """class_counts: [{'code','desc','n'}] (n = 1-ha cells). Area = n x 0.01 km2 (the layer's Shape__Area is web-mercator inflated).
    mercator_area_km2 {code: km2 from Shape__Area} lets the builder check the cell-count area against the geometry at the lake's latitude."""
    classes = [{"code": c["code"], "label": c["desc"].replace(" :", ":").strip(), "cells": int(c["n"]), "areaKm2": round(int(c["n"]) * 0.01, 2)}
               for c in class_counts if int(c["n"]) > 0]
    classes.sort(key=lambda c: -c["cells"])
    total = round(sum(c["areaKm2"] for c in classes), 1)
    ow = next((c["areaKm2"] for c in classes if c["code"] == OPEN_WATER_CODE), 0.0)
    veg = [c for c in classes if c["code"] != OPEN_WATER_CODE]
    return {"lakeId": lake_id, "source": dict(SOURCE_SFWMD_OKEE), "retrievedOn": retrieved_on, "mappedKm2": total, "openWaterKm2": ow,
            "classes": veg[:SFWMD_MAX_CLASSES], "classesOmitted": max(0, len(veg) - SFWMD_MAX_CLASSES), "classCount": len(classes),
            "mercatorAreaCheck": mercator_area_km2}


def validate_sfwmd(rec: dict) -> list:
    bad = []
    if not rec.get("classes"):
        bad.append("no classes")
    if rec.get("mappedKm2", 0) <= 0:
        bad.append("mapped area not positive")
    if any(c["areaKm2"] < 0 or c["cells"] < 0 for c in rec.get("classes", [])):
        bad.append("negative area")
    top = rec.get("classes", [])
    if top and sum(c["areaKm2"] for c in top) + rec.get("openWaterKm2", 0) > rec["mappedKm2"] + 0.5:
        bad.append("class areas exceed mapped area")
    return bad


def littoral_block(rec: dict | None, now_year: int) -> dict | None:
    if not rec or validate_sfwmd(rec):
        return None
    s = rec["source"]
    age = now_year - s["surveyYear"]
    return {"status": "PROVIDER_VERIFIED", "level": 1, "sourceId": s["id"], "agency": s["agency"], "surveyYear": s["surveyYear"],
            "surveyMonth": s["surveyMonth"], "datePrecision": s["datePrecision"], "ageYears": age, "historical": age > AGENCY_STALE_YEARS,
            "scope": s["scope"], "units": s["units"], "mappedKm2": rec["mappedKm2"], "openWaterKm2": rec["openWaterKm2"],
            "classes": [{"label": c["label"], "areaKm2": c["areaKm2"]} for c in rec["classes"]], "classesOmitted": rec["classesOmitted"],
            "retrievedOn": rec["retrievedOn"], "licence": s["licence"], "internalOnly": s["internalOnly"],
            "verified": ["source identity", "units (1 ha cells)", "survey month/year", "class areas consistent with mapped area"],
            "summary": f"{s['agency']} marsh map {s['surveyMonth']:02d}/{s['surveyYear']} (Moore Haven and south islands only): largest vegetation class "
                       f"{rec['classes'][0]['label']} {rec['classes'][0]['areaKm2']} km2" + (" - historical" if age > AGENCY_STALE_YEARS else "")}
