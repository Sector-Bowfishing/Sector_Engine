"""Pilot Biological State runner (INTERNAL; writes only local files, never the Brain RTDB).

  python3 run_state.py --lake "Guntersville|AL" --rules /path/to/private/rules --live --out out/      # reads the Brain RTDB (GET only)
  python3 run_state.py --lake "Guntersville|AL" --rules DIR --snapshot snap.json --presence presence.json --now 2026-10-13T03:00:00Z

`--rules` is a staged PRIVATE rules directory (rules_manifest.json + <species>.json); real rules are never read from this repository.
Missing or stale upstream inputs make features UNKNOWN. Nothing is published and no customer path reads the output.

Fleet mode (OFF by default; refused unless the environment sets FISH_FLEET_RUNNER=1):

  FISH_FLEET_RUNNER=1 python3 run_state.py --fleet --directory lakes.json --rules DIR (--live | --inputs-dir DIR) [--lake-context ctx.json] --out out/

`--directory` is the Engine lake directory response ({"lakes": [{"id", "lat", "lon", ...}]}, or a bare list). Every directory lake is run. A lake's
region and waterbody type come from PILOT_LAKES or from `--lake-context` ({lakeId: {"region", "waterbodyType"}} in the rules vocabulary); the
directory itself carries neither, so a lake without a reviewed context is REFUSED with NO_LAKE_CONTEXT, never guessed. `--inputs-dir` holds
<lakeKey>.snapshot.json and <lakeKey>.presence.json per lake (a missing file is an empty input, so UNKNOWN). Outputs stay local files, as for a pilot.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bio_state as bs      # noqa: E402
import rules as rl         # noqa: E402

PILOT_LAKES = {
    "Guntersville|AL": {"key": "Guntersville_AL", "region": "south", "waterbodyType": "run_of_river", "lat": 34.4, "lon": -86.3},
    "Wheeler|AL": {"key": "Wheeler_AL", "region": "south", "waterbodyType": "run_of_river", "lat": 34.63, "lon": -87.03},
    "Wilson|AL": {"key": "Wilson_AL", "region": "south", "waterbodyType": "run_of_river", "lat": 34.77, "lon": -87.45},
    "Pickwick Lake|TN": {"key": "Pickwick_Lake_TN", "region": "south", "waterbodyType": "run_of_river", "lat": 35.05, "lon": -88.2},
    # second independent system for transfer testing (Savannah basin, Corps storage reservoir). Internal dry runs only; not part of any bundle yet.
    "Lake Hartwell|SC": {"key": "Lake_Hartwell_SC", "region": "south", "waterbodyType": "storage_reservoir", "lat": 34.5, "lon": -82.9},
}


FLEET_SWITCH_ENV = "FISH_FLEET_RUNNER"
FLEET_SWITCH_ON = "1"
NO_LAKE_CONTEXT = "NO_LAKE_CONTEXT"


def fleet_enabled(environ=None) -> bool:
    """The fleet switch. OFF unless the environment says exactly FISH_FLEET_RUNNER=1; any other value, or none, is OFF."""
    return (os.environ if environ is None else environ).get(FLEET_SWITCH_ENV) == FLEET_SWITCH_ON


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake")
    ap.add_argument("--rules", required=True, help="staged private rules directory")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--live", action="store_true", help="read the published snapshot + species presence from the Brain RTDB (GET only)")
    g.add_argument("--snapshot", help="local snapshot JSON (the /snapshots/{k}/latest shape)")
    g.add_argument("--inputs-dir", help="fleet only: <lakeKey>.snapshot.json / <lakeKey>.presence.json per lake")
    ap.add_argument("--presence", help="local presence JSON ({speciesId: {presenceState,...}}); required with --snapshot")
    ap.add_argument("--now", help="ISO time (default: now)")
    ap.add_argument("--out", default="out")
    ap.add_argument("--fleet", action="store_true", help=f"run every directory lake (refused unless {FLEET_SWITCH_ENV}={FLEET_SWITCH_ON})")
    ap.add_argument("--directory", help="fleet only: Engine lake directory JSON")
    ap.add_argument("--lake-context", help="fleet only: reviewed {lakeId: {region, waterbodyType}}")
    a = ap.parse_args(argv)
    if a.fleet:
        return run_fleet(a)
    if a.lake is None:
        ap.error("the following arguments are required: --lake")
    if not (a.live or a.snapshot):
        ap.error("one of the arguments --live --snapshot is required")
    if a.inputs_dir or a.directory or a.lake_context:
        ap.error("--inputs-dir, --directory and --lake-context are fleet-only (--fleet)")
    meta = PILOT_LAKES.get(a.lake)
    if not meta:
        raise SystemExit(f"{a.lake!r} is not a pilot lake; the pilot is limited to {sorted(PILOT_LAKES)}")
    now = dt.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else dt.datetime.now(dt.timezone.utc)
    ruleset = rl.load_rules_dir(a.rules)
    species_info, recorder = {}, None
    if a.live:
        import brain_platform as bp
        recorder = bp.ConsumptionRecorder("biological-state")                                       # consumption-lineage-v1: what this pilot run really read
        r = bp.BrainRtdb(bp.BRAIN_RTDB_URL, bp.TokenProvider(), brain_id="biological-state", recorder=recorder)      # ownership-checked; only GET is used here
        snap = r.get(f"snapshots/{meta['key']}/latest")
        presence = r.get(f"lakes/{meta['key']}/speciesPresence") or {}
        for sid in presence:
            sp = r.get(f"species/{sid}") or {}
            species_info[sid] = {k: v for k, v in {"researchMaturity": sp.get("researchMaturity"), "knowledgeScore": (sp.get("knowledge") or {}).get("overallRounded"), "assessment": sp.get("assessment")}.items() if v is not None}
    else:
        snap = json.load(open(a.snapshot))
        presence = json.load(open(a.presence)) if a.presence else {}
    inputs = bs.normalize_inputs(snap, now)
    state = bs.build_lake_state(a.lake, region=meta["region"], waterbody_type=meta["waterbodyType"], now=now, inputs=inputs,
                                daypart=bs.daypart_for(meta["lat"], meta["lon"], now), presence=presence, ruleset=ruleset, species_info=species_info,
                                roster=sorted(ruleset.by_species))           # no presence record = UNKNOWN, listed, not dropped
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"biological_state_{meta['key']}.json")
    fp = bs.state_fingerprint(state)
    if os.path.exists(path):
        try:
            if bs.state_fingerprint(json.load(open(path))) == fp:
                print(json.dumps({"written": None, "unchanged": True, "fingerprint": fp[:16], "note": "no material input change since the last run: nothing written"}, indent=1))
                return 0
        except (ValueError, KeyError):
            pass
    json.dump(state, open(path, "w"), indent=1, ensure_ascii=False)
    out = {"written": path, "fingerprint": fp[:16], "status": state["status"], "rulesVersion": state["provenance"]["rulesVersion"], **state["summary"]}
    if recorder is not None:
        out["consumed"] = r.consumed()                    # ACTUAL reads (live runs only); absent for --snapshot runs, where nothing was read from the platform
    print(json.dumps(out, indent=1))
    return 0


def _load_directory(path: str) -> list[dict]:
    doc = json.load(open(path))
    lakes = doc.get("lakes") if isinstance(doc, dict) else doc
    if not isinstance(lakes, list) or not all(isinstance(x, dict) and isinstance(x.get("id"), str) for x in lakes):
        raise SystemExit(f"{path}: not a lake directory (expected {{'lakes': [{{'id': ...}}]}})")
    return lakes


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def lake_context(lake: dict, contexts: dict) -> dict | None:
    """{region, waterbodyType, lat, lon} or None. Pilots keep their hardcoded context; any other lake needs a reviewed context entry whose values are
    in the rules vocabulary ('any' is not a lake's context). Nothing is inferred from the name, state or coordinates."""
    lid = lake["id"]
    if lid in PILOT_LAKES:
        m = PILOT_LAKES[lid]
        return {"region": m["region"], "waterbodyType": m["waterbodyType"], "lat": m["lat"], "lon": m["lon"]}
    c = (contexts or {}).get(lid)
    if not isinstance(c, dict) or c.get("region") not in rl.REGIONS or c.get("waterbodyType") not in rl.WATERBODIES or "any" in (c.get("region"), c.get("waterbodyType")):
        return None
    return {"region": c["region"], "waterbodyType": c["waterbodyType"], "lat": _num(lake.get("lat")), "lon": _num(lake.get("lon"))}


def _read_json(path: str, default):
    return json.load(open(path)) if os.path.exists(path) else default


def run_fleet(a) -> int:
    """Every directory lake through the same per-lake path as a pilot. Behind FISH_FLEET_RUNNER (OFF by default); writes local files only."""
    if not fleet_enabled():
        raise SystemExit(f"fleet mode is OFF: set {FLEET_SWITCH_ENV}={FLEET_SWITCH_ON} to run it (default off; the pilot is limited to {sorted(PILOT_LAKES)})")
    if a.lake or a.snapshot or a.presence:
        raise SystemExit("--fleet runs every directory lake: --lake, --snapshot and --presence do not apply (use --live or --inputs-dir)")
    if not a.directory or not (a.live or a.inputs_dir):
        raise SystemExit("--fleet needs --directory and one of --live / --inputs-dir")
    import brain_platform as bp
    lakes = _load_directory(a.directory)
    keys = bp.lake_keys([x["id"] for x in lakes])                       # raises on a key collision: nothing is written
    contexts = json.load(open(a.lake_context)) if a.lake_context else {}
    now = dt.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else dt.datetime.now(dt.timezone.utc)
    ruleset = rl.load_rules_dir(a.rules)
    roster = sorted(ruleset.by_species)
    r, recorder, species_cache = None, None, {}
    if a.live:
        recorder = bp.ConsumptionRecorder("biological-state")
        r = bp.BrainRtdb(bp.BRAIN_RTDB_URL, bp.TokenProvider(), brain_id="biological-state", recorder=recorder)      # GET only
    os.makedirs(a.out, exist_ok=True)
    rows, counts = {}, {"lakes": len(lakes), "written": 0, "unchanged": 0, "refused": 0, "error": 0}
    for lake in sorted(lakes, key=lambda x: x["id"]):
        lid, k = lake["id"], keys[lake["id"]]
        ctx = lake_context(lake, contexts)
        if ctx is None:
            rows[lid] = {"lakeKey": k, "result": "REFUSED", "reasonCode": NO_LAKE_CONTEXT,
                         "reason": "no reviewed region/waterbodyType for this lake: the directory carries neither and nothing is guessed"}
            counts["refused"] += 1
            continue
        species_info = {}
        if a.live:
            try:                                                        # one lake's failed read is that lake's ERROR row, not the end of the run
                snap = r.get(f"snapshots/{k}/latest")
                presence = r.get(f"lakes/{k}/speciesPresence") or {}
                for sid in presence:
                    if sid not in species_cache:
                        sp = r.get(f"species/{sid}") or {}
                        species_cache[sid] = {kk: v for kk, v in {"researchMaturity": sp.get("researchMaturity"), "knowledgeScore": (sp.get("knowledge") or {}).get("overallRounded"), "assessment": sp.get("assessment")}.items() if v is not None}
                    species_info[sid] = species_cache[sid]
            except Exception as e:                                      # noqa: BLE001
                rows[lid] = {"lakeKey": k, "result": "ERROR", "reasonCode": "READ_FAILED", "error": repr(e)[:200]}
                counts["error"] += 1
                continue
        else:
            snap = _read_json(os.path.join(a.inputs_dir, f"{k}.snapshot.json"), None)
            presence = _read_json(os.path.join(a.inputs_dir, f"{k}.presence.json"), {})
        daypart = bs.daypart_for(ctx["lat"], ctx["lon"], now) if ctx["lat"] is not None and ctx["lon"] is not None else None
        state = bs.build_lake_state(lid, region=ctx["region"], waterbody_type=ctx["waterbodyType"], now=now, inputs=bs.normalize_inputs(snap, now),
                                    daypart=daypart, presence=presence, ruleset=ruleset, species_info=species_info, roster=roster)
        path = os.path.join(a.out, f"biological_state_{k}.json")
        fp = bs.state_fingerprint(state)
        unchanged = False
        if os.path.exists(path):
            try:
                unchanged = bs.state_fingerprint(json.load(open(path))) == fp
            except (ValueError, KeyError):
                pass
        if not unchanged:
            json.dump(state, open(path, "w"), indent=1, ensure_ascii=False)
        counts["unchanged" if unchanged else "written"] += 1
        rows[lid] = {"lakeKey": k, "result": "UNCHANGED" if unchanged else "WRITTEN", "fingerprint": fp[:16], **state["summary"]}
    summary = {"mode": "fleet", "switch": f"{FLEET_SWITCH_ENV}={FLEET_SWITCH_ON}", "status": "PILOT_INTERNAL", "rulesVersion": ruleset.rules_version,
               "now": now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "counts": counts, "lakes": rows}
    json.dump(summary, open(os.path.join(a.out, "fleet_run.json"), "w"), indent=1, ensure_ascii=False, sort_keys=True)
    out = {"fleetSummary": os.path.join(a.out, "fleet_run.json"), **counts}
    if recorder is not None:
        out["consumedDependencies"] = sorted({e["dependencyId"] for e in r.consumed() if isinstance(e, dict) and "dependencyId" in e})
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
