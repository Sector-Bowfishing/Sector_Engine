"""Science-preservation golden generator for the Water Clarity Brain (C1).

  python3 gen_golden.py <runtime-dir>            # print the canonical JSON of every builder output on the synthetic fixtures

The golden (`clarity_science_baseline.json`) was produced from the PRE-MOVE tree (`jobs/water-clarity-brain` @ origin/main 4ff9bed0) and is compared by
`test_clarity_certification.py` against the canonical `brains/water-clarity/runtime`. It uses only the public catalog plus the SYNTHETIC overlay shipped in
tests/fixtures (never the private catalog), a fixed clock and the committed fixtures, so it is deterministic and public-safe.
"""
import copy
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(os.path.dirname(HERE), "fixtures")
NOW = dt.datetime(2026, 10, 12, 6, 30, tzinfo=dt.timezone.utc)


def fx(name):
    return json.load(open(os.path.join(FX, name)))


def generate(runtime_dir: str) -> dict:
    os.environ["CLARITY_PRIVATE_CATALOG"] = os.path.join(FX, "catalog.overlay.example.json")
    sys.path.insert(0, runtime_dir)
    import brain_platform as bp          # noqa: E402
    import clarity_brain as cb           # noqa: E402
    gunt, ky, alek = fx("engine_guntersville_rain_decay.json"), fx("engine_kentucky_discharge_gauge.json"), fx("engine_aleknagik_openmeteo.json")
    latest, meta = fx("bucket_guntersville_latest.json"), fx("bucket_guntersville_meta.json")

    def gauge(trend, algal=False):
        c = copy.deepcopy(gunt)
        c["clarityVisibility"] = {"centralFt": 3.21, "lowFt": None if algal else 1.33, "highFt": None if algal else 4.45, "confidence": "medium",
                                  "model": "secchi-power-v1", "source": "inSituGauge", "provenance": "USGS 03575100 Tennessee River measuring 7.1 FNU",
                                  "limitations": ["Visibility converted from turbidity."]}
        c["clarityGauges"] = [{"siteCode": "03575100", "siteName": "x", "parameterCode": "63680", "parameterName": "Turbidity", "role": "turbidity", "value": 7.1,
                               "unit": "FNU", "trend": trend, "change": -0.4, "distanceMiles": 2.0, "latitude": 34.5, "longitude": -86.2, "driving": True}]
        return c
    norain = copy.deepcopy(gunt)
    norain["clarityVisibility"].update(source="noRainData", provenance="No turbidity gauge and no rain data")
    norain["clarityRain"] = None
    partial = {"clarityVisibility": {"centralFt": 2.0, "model": "rain-decay-v0", "source": "rainDecayModel"}}
    scen = {"guntersvilleRain": ("Guntersville|AL", gunt, True), "gaugeFalling": ("Gauge A|AL", gauge("falling"), True), "gaugeRising": ("Gauge B|AL", gauge("rising"), True),
            "gaugeAlgal": ("Gauge C|AL", gauge("steady", True), True), "kentuckyDischarge": ("Kentucky|KY", ky, True), "aleknagik": ("Aleknagik|AK", alek, False),
            "noRain": ("NoRain|AL", norain, True), "partial": ("Partial|AL", partial, True), "malformed": ("Bad|AL", {}, True)}
    out = {"brainVersion": cb.BRAIN_VERSION, "catalogDetail": cb.CATALOG_DETAIL, "scenarios": {}}
    results = {}
    for name, (lid, cond, poly) in sorted(scen.items()):
        est = cb.engine_estimate(cond, lid)
        sat = cb.satellite_evidence(latest if poly else None, meta if poly else None, poly, 16 if poly else None, NOW)
        layers, geo = cb.map_layers(latest if poly else None, meta if poly else None)
        state = cb.build_state(lid, est, sat, layers, geo, NOW, "sector-engine-00072-way")
        lake = {"id": lid, "lat": 34.5, "lon": -86.2, "name": lid.split("|")[0], "state": lid.split("|")[1]}
        try:
            profile = cb.build_profile(lake, est, sat, poly, NOW)
        except Exception as e:                      # a golden records a builder's failure too
            profile = {"_error": type(e).__name__}
        out["scenarios"][name] = {"estimate": est, "satellite": sat, "layers": layers, "layerGeo": geo, "state": state, "profile": profile,
                                  "lakeWrites": cb.lake_writes(lid, profile if "_error" not in profile else None, state, NOW),
                                  "qualityFlags": cb.quality_flags(est, sat)}
        results[lid] = {"state": state, "profile": profile if "_error" not in profile else None, "error": None}
    out["staleSatellite"] = cb.satellite_evidence(latest, meta, True, 16, NOW + dt.timedelta(days=20))
    out["missedLake"] = {"writes": cb.lake_writes("A|AL", None, None, NOW, "timeout"),
                         "freshCarry": cb.stale_carry("A|AL", {"lastUpdatedAt": bp.iso(NOW - dt.timedelta(hours=3))}, NOW),
                         "oldCarry": cb.stale_carry("A|AL", {"lastUpdatedAt": bp.iso(NOW - dt.timedelta(hours=40))}, NOW)}
    ids = sorted(results)
    prev_fleet = {bp.lake_key(ids[0]): {"slots": {cb.SLOT: {"readiness": "BETA", "lastUpdatedAt": bp.iso(NOW - dt.timedelta(hours=2))}}}}
    run_rec = {"day": "2026-10-11", "tasks": 8, "lakes": 10, "errors": 0, "outcomes": {"published": 3, "upToDate": 5, "noUsablePass": 2, "noPassInWindow": 0, "error": 0},
               "finishedAt": "2026-10-11T09:14:57Z"}
    out["registry"] = cb.registry_entry(results, prev_fleet, NOW, "HEALTHY", None, "sector-engine-00072-way", ids, "2026-10-12T06:30:00Z")
    out["sources"] = cb.source_records(results, NOW, run_rec)
    prev_registry = {"version": "1.0.0"}
    out["activity"] = cb.activity_events(prev_registry, prev_fleet, results, NOW, "DEGRADED")
    out["runHealth"] = [cb.run_health(n, k, n - k, s, a) for n, k, s, a in ((0, 0, None, False), (10, 10, True, False), (10, 9, True, False), (10, 7, True, False), (10, 10, False, False), (10, 0, None, True))]
    return json.loads(json.dumps(out, sort_keys=True, default=str))


if __name__ == "__main__":
    sys.stdout.write(json.dumps(generate(os.path.abspath(sys.argv[1])), indent=1, sort_keys=True) + "\n")
