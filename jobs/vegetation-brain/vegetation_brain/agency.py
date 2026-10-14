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


def agency_block(record: dict | None, now_year: int) -> dict:
    """The compact Level-1 block for the state. Never inferred: absent record => NOT_ASSESSED with a reason."""
    if not record or not record.get("rows"):
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
    out["summary"] = (f"{src['agency'].split(' (')[0]} survey {latest}: vegetation covers {last[0]['pac']} % of the lake surface and occupies "
                      f"{last[0]['pvi']} % of its water volume" + (" (several sectors reported)" if len(last) > 1 else "")
                      + (" - historical" if out["historical"] else ""))
    return out
