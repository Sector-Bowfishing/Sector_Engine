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


def build_manifest(directory: list[dict], flags: dict[str, dict], fleet_fetch: dict[str, dict], audited_ids: set[str]) -> dict:
    lakes, counts = {}, {t: 0 for t in TIERS}
    for l in sorted(directory, key=lambda x: x["id"]):
        i = l["id"]; f = fleet_fetch.get(i); fl = flags.get(i, {})
        tier, why = decide_tier(i in audited_ids, f is not None, bool(f and f.get("ok")), fl.get("confidence") or None,
                                f.get("nBanks") if f else None, f.get("res") if f else None)
        counts[tier] += 1
        e = {"id": i, "tier": tier, "reason": why, "geometryConfidence": fl.get("confidence") or "MISSING",
             "forecastDomain": forecast_domain(l.get("state")), "lat": l["lat"], "lon": l["lon"], "state": l.get("state"),
             "pointFlag": fl.get("point_flag") or "", "blockers": blockers(l.get("state"), fl.get("point_flag"))}
        if f and f.get("ok"):
            e["polygonFetch"] = {"rasterM": round(f["res"], 1), "banksSampled": f["nBanks"],
                                 "maxP90FetchM": int(max(f["p90FetchByDir"]))}
        lakes[i] = e
    return {"schema": "sector-wind-geometry-tiers-v1", "directoryLakes": len(lakes), "counts": counts,
            "exposureAllowedCount": sum(exposure_allowed(v) for v in lakes.values()),
            "rules": {"ESTIMATED": f"polygon fetch ok, Lake Brain confidence in {OK_CONFIDENCE}, >= {MIN_BANKS} sampled banks, raster <= {MAX_RASTER_M:g} m",
                      "AUDITED": "frozen NHD fetch table (SHA-256 verified)", "POINT_ONLY": "everything else; no bank labels"},
            "evidence": "docs/wind-research (branch docs/wind-brain-research): polygon fetch matched audited magnitude (-6%) but FAILED direction-rank agreement; ESTIMATED is not validated.",
            "lakes": lakes}


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("build")
    ap.add_argument("--directory", required=True)       # directory_lakes_*.json {"lakes": [...]}
    ap.add_argument("--flags", required=True)           # lake_geometry_flags.csv (Lake Brain)
    ap.add_argument("--fleet-fetch", required=True)     # per-lake polygon-fetch summary (list of {id, ok, nBanks, res, p90FetchByDir})
    ap.add_argument("--audited-dir", nargs="+", required=True)  # dirs/globs of *.windfetch.json.gz
    ap.add_argument("--out", default=MANIFEST)
    a = ap.parse_args()
    directory = json.load(open(a.directory))["lakes"]
    flags = {r["id"]: r for r in csv.DictReader(open(a.flags))}
    ff = {r["id"]: r for r in json.load(open(a.fleet_fetch))}
    audited = {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"}
    for pat in a.audited_dir:
        for p in glob.glob(pat):
            d = json.load(gzip.open(p)).get("directory")
            if d:
                audited.add(f"{d['name']}|{d['state']}")
    m = build_manifest(directory, flags, ff, audited)
    json.dump(m, open(a.out, "w"), indent=0, sort_keys=True, separators=(",", ":"))
    print(m["counts"], "->", a.out)


if __name__ == "__main__":
    _cli()
