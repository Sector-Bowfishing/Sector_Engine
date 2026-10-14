"""Fleet geometry tiers: which of the directory lakes can carry bank-exposure output, and at what evidence level.

  AUDITED    frozen NHD fetch table, SHA-256 verified, QA'd (BWIS B1). The only tier with a QA claim.
  ESTIMATED  polygon-derived fetch (estimate.py) on a HIGH/MEDIUM-confidence Lake Brain polygon. Same physics; NOT audited,
             failed the registered direction-rank agreement vs audited tables; label every output ESTIMATED.
  POINT_ONLY wind direction/speed/tonight only. No bank labels, never 'Protected'.

The decision is pure (`decide_tier`) and the committed manifest is deterministic from its inputs, so a tier cannot change
silently: `python -m sector_wind.brain.fleet build ...` regenerates it and the diff is reviewed."""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import os

TIERS = ("AUDITED", "ESTIMATED", "POINT_ONLY")
OK_CONFIDENCE = ("HIGH", "MEDIUM")
MIN_BANKS = 20
MAX_RASTER_M = 40.0
MANIFEST = os.path.join(os.path.dirname(__file__), "data", "geometry_tiers.json")


def forecast_domain(state: str | None) -> str:
    return {"AK": "AK", "HI": "HI", "PR": "PR", "VI": "PR"}.get(state or "", "CONUS")


def decide_tier(audited: bool, polygon_present: bool, fetch_ok: bool | None, confidence: str | None, n_banks: int | None,
                raster_m: float | None) -> tuple[str, str]:
    if audited:
        return "AUDITED", "frozenFetchTable"
    if not polygon_present:
        return "POINT_ONLY", "noPolygon"
    if not fetch_ok:
        return "POINT_ONLY", "polygonFetchFailed"
    if confidence not in OK_CONFIDENCE:
        return "POINT_ONLY", f"geometryConfidence:{confidence or 'MISSING'}"
    if (n_banks or 0) < MIN_BANKS:
        return "POINT_ONLY", "tooFewBanks"
    if raster_m is None or raster_m > MAX_RASTER_M:
        return "POINT_ONLY", "coarseRaster"
    return "ESTIMATED", "polygonFetch"


AUDITED_AREA_RATIO = (0.8, 1.25)   # registry shoreline area / area of the NHD feature the audited table was built from


def registry_flags(entry: dict) -> dict:
    """Map a Lake Registry v1 index entry to the flag vocabulary used here (confidence, point_flag). MISSING when the registry has no geometry."""
    gc = (entry.get("geometryConfidence") or {}).get("level") or "MISSING"
    pf = entry.get("pointFlag") or ""
    return {"confidence": gc, "point_flag": {"identity-risk": "identity_risk", "off-water": "off_water", "ok": "ok"}.get(pf, pf)}


def audited_check_blockers(check: dict | None) -> list[str]:
    """Blockers from the audited-table vs registry cross-check (research/audited_vs_registry.py): the table may not describe the registry's water."""
    if not check:
        return []
    b = []
    r = check.get("areaRatio")
    if r is not None and not (AUDITED_AREA_RATIO[0] <= r <= AUDITED_AREA_RATIO[1]):
        b.append("auditedGeometryAreaMismatch")
    if check.get("registryAreaKm2") is None and not check.get("dev"):
        b.append("registryGeometryMissing")
    return b


def blockers(state: str | None, point_flag: str | None) -> list[str]:
    """Hard blockers that withhold ANY bank-exposure label even when a tier exists (checked in the manifest, enforced by exposure_allowed)."""
    b = []
    d = forecast_domain(state)
    if d != "CONUS":
        b.append(f"nbm{d}DomainNotTested")
    if point_flag == "identity_risk":
        b.append("lakeIdentityRisk")
    return b


def exposure_allowed(entry: dict) -> bool:
    """Bank labels may be produced only for AUDITED/ESTIMATED lakes with no hard blocker. Everything else: wind/tonight only."""
    return entry.get("tier") in ("AUDITED", "ESTIMATED") and not entry.get("blockers")


def load_manifest(path: str = MANIFEST) -> dict:
    return json.load(open(path))


def tier_for(lake_id: str, manifest: dict | None = None) -> dict:
    """Manifest entry for a lake; unknown lakes are POINT_ONLY (never silently promoted)."""
    m = manifest or load_manifest()
    return m["lakes"].get(lake_id, {"id": lake_id, "tier": "POINT_ONLY", "reason": "notInManifest", "forecastDomain": "CONUS"})


def build_manifest(directory: list[dict], flags: dict[str, dict], fleet_fetch: dict[str, dict], audited_ids: set[str], registry: dict | None = None,
                   audited_checks: dict[str, dict] | None = None) -> dict:
    """flags: {lakeId: {'confidence','point_flag'}} (from Lake Registry v1 via registry_flags, or the older research CSV). registry: the index (for memberIds + provenance).
    audited_checks: {lakeId: row from audited_vs_registry.py}."""
    lakes, counts = {}, {t: 0 for t in TIERS}
    reg = {l["lakeId"]: l for l in (registry or {}).get("lakes", [])}
    for l in sorted(directory, key=lambda x: x["id"]):
        i = l["id"]; f = fleet_fetch.get(i); fl = flags.get(i, {})
        tier, why = decide_tier(i in audited_ids, f is not None, bool(f and f.get("ok")), fl.get("confidence") or None,
                                f.get("nBanks") if f else None, f.get("res") if f else None)
        counts[tier] += 1
        e = {"id": i, "tier": tier, "reason": why, "geometryConfidence": fl.get("confidence") or "MISSING",
             "forecastDomain": forecast_domain(l.get("state")), "lat": l["lat"], "lon": l["lon"], "state": l.get("state"),
             "pointFlag": fl.get("point_flag") or "", "blockers": blockers(l.get("state"), fl.get("point_flag")) + (audited_check_blockers((audited_checks or {}).get(i)) if tier == "AUDITED" else [])}
        if i in reg:
            e["memberIds"] = reg[i].get("memberIds") or [i]
            if reg[i].get("geometry") is None:
                e["geometryMissing"] = reg[i].get("geometryMissingStatus") or "unknown"
        if f and f.get("ok"):
            e["polygonFetch"] = {"rasterM": round(f["res"], 1), "banksSampled": f["nBanks"],
                                 "maxP90FetchM": int(max(f["p90FetchByDir"]))}
        lakes[i] = e
    prov = {"registry": {"schema": registry.get("schema"), "geometryVersion": registry.get("geometryVersion"), "generatedAt": registry.get("generatedAt"), "count": registry.get("count")}} if registry else {}
    return {"schema": "sector-wind-geometry-tiers-v1", "directoryLakes": len(lakes), "counts": counts, "inputs": prov,
            "exposureAllowedCount": sum(exposure_allowed(v) for v in lakes.values()),
            "rules": {"ESTIMATED": f"polygon fetch ok, Lake Brain confidence in {OK_CONFIDENCE}, >= {MIN_BANKS} sampled banks, raster <= {MAX_RASTER_M:g} m",
                      "AUDITED": "frozen NHD fetch table (SHA-256 verified)", "POINT_ONLY": "everything else; no bank labels"},
            "evidence": "docs/wind-research (branch docs/wind-brain-research): polygon fetch matched audited magnitude (-6%) but FAILED direction-rank agreement; ESTIMATED is not validated.",
            "lakes": lakes}


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("build")
    ap.add_argument("--directory", required=True)       # directory_lakes_*.json {"lakes": [...]}
    ap.add_argument("--flags")                          # legacy: lake_geometry_flags.csv (Lake Brain research copy)
    ap.add_argument("--registry")                       # PREFERRED: published Lake Registry v1 index (registry/lakes.v1.json)
    ap.add_argument("--audited-check")                  # audited_vs_registry.json
    ap.add_argument("--fleet-fetch", required=True)     # per-lake polygon-fetch summary (list of {id, ok, nBanks, res, p90FetchByDir})
    ap.add_argument("--audited-dir", nargs="+", required=True)  # dirs/globs of *.windfetch.json.gz
    ap.add_argument("--out", default=MANIFEST)
    a = ap.parse_args()
    directory = json.load(open(a.directory))["lakes"]
    registry = json.load(open(a.registry)) if a.registry else None
    flags = {l["lakeId"]: registry_flags(l) for l in registry["lakes"]} if registry else {r["id"]: r for r in csv.DictReader(open(a.flags))}
    checks = {r["lakeId"]: r for r in json.load(open(a.audited_check))} if a.audited_check else None
    ff = {r["id"]: r for r in json.load(open(a.fleet_fetch))}
    audited = {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"}
    for pat in a.audited_dir:
        for p in glob.glob(pat):
            d = json.load(gzip.open(p)).get("directory")
            if d:
                audited.add(f"{d['name']}|{d['state']}")
    m = build_manifest(directory, flags, ff, audited, registry, checks)
    json.dump(m, open(a.out, "w"), indent=0, sort_keys=True, separators=(",", ":"))
    print(m["counts"], "->", a.out)


if __name__ == "__main__":
    _cli()
