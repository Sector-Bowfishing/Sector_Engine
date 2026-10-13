"""Pilot Biological State runner (INTERNAL; writes only local files, never the Brain RTDB).

  python3 run_state.py --lake "Guntersville|AL" --rules /path/to/private/rules --live --out out/      # reads the Brain RTDB (GET only)
  python3 run_state.py --lake "Guntersville|AL" --rules DIR --snapshot snap.json --presence presence.json --now 2026-10-13T03:00:00Z

`--rules` is a staged PRIVATE rules directory (rules_manifest.json + <species>.json); real rules are never read from this repository.
Missing or stale upstream inputs make features UNKNOWN. Nothing is published and no customer path reads the output.
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
    # second independent system for transfer testing (Savannah basin, Corps storage reservoir). Internal dry runs only; not part of any bundle yet.
    "Lake Hartwell|SC": {"key": "Lake_Hartwell_SC", "region": "south", "waterbodyType": "storage_reservoir", "lat": 34.5, "lon": -82.9},
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", required=True)
    ap.add_argument("--rules", required=True, help="staged private rules directory")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--live", action="store_true", help="read the published snapshot + species presence from the Brain RTDB (GET only)")
    g.add_argument("--snapshot", help="local snapshot JSON (the /snapshots/{k}/latest shape)")
    ap.add_argument("--presence", help="local presence JSON ({speciesId: {presenceState,...}}); required with --snapshot")
    ap.add_argument("--now", help="ISO time (default: now)")
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)
    meta = PILOT_LAKES.get(a.lake)
    if not meta:
        raise SystemExit(f"{a.lake!r} is not a pilot lake; the pilot is limited to {sorted(PILOT_LAKES)}")
    now = dt.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else dt.datetime.now(dt.timezone.utc)
    ruleset = rl.load_rules_dir(a.rules)
    species_info = {}
    if a.live:
        import brain_platform as bp
        r = bp.BrainRtdb(bp.BRAIN_RTDB_URL, bp.TokenProvider(), brain_id="biological-state")      # ownership-checked; only GET is used here
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
                                daypart=bs.daypart_for(meta["lat"], meta["lon"], now), presence=presence, ruleset=ruleset, species_info=species_info)
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
    print(json.dumps({"written": path, "fingerprint": fp[:16], "status": state["status"], "rulesVersion": state["provenance"]["rulesVersion"], **state["summary"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
