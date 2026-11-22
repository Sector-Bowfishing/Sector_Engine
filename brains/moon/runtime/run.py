#!/usr/bin/env python3
"""Moon and Night Light Brain run entry (CALIBRATION). Not scheduled (control manifest PARKED, executionTarget kind none; execution control
disabled) and NO live writer.

  python run.py --plan                                               # one JSON verdict: SKIP (no executor, no writer)
  python run.py --tonight OUT.json [--date YYYY-MM-DD] [--weather W.json] [--lakes "Guntersville|AL,..."]
                                                                     # tonight for every directory lake (or the listed ones) as a local JSON file
  python run.py --dry-run OUT.json [--date ...] [--weather ...]      # build the RTDB write set into an in-memory store and dump it; writes nothing remote
  python run.py --write                                              # REFUSED (exit 2): no publication path is approved

--date is the evening's calendar date at the lakes. Without it each lake gets ITS OWN current night: the night whose span (local solar noon to
local solar noon) contains the run time, or the coming evening once that night's sunrise has passed (night.evening_date). Never the UTC date, which is the wrong
evening for a US lake after 6-8 PM local.
--weather is the OPTIONAL cloud input: {lakeId: the Weather Brain state document} (sector-brain-weather-state-v1, /lakes/{k}/states/weather;
only forecast.hourly[].cloudCoverPct and sky.cloudCoverPct are read). Without it every lake gets the moon-only answer, labelled as such."""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import moon_brain  # noqa: E402,F401  (bootstraps the platform path)
from moon_brain import contract as C, lakes as L  # noqa: E402
from moon_brain.night import evening_date  # noqa: E402
from moon_brain.publish import publish  # noqa: E402
from moon_brain.state import build_state  # noqa: E402
from moon_brain.writer import DryRunWriter  # noqa: E402


def _directory(only: str | None) -> dict:
    d = L.load()
    if only:
        want = {s.strip() for s in only.split(",") if s.strip()}
        unknown = want - {r["lakeId"] for r in d["lakes"]}
        if unknown:
            raise L.LakeRegistryError(f"not directory lakes: {sorted(unknown)}")
        d = {**d, "lakes": [r for r in d["lakes"] if r["lakeId"] in want]}
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--tonight", metavar="OUT.json")
    g.add_argument("--dry-run", metavar="OUT.json")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--weather", metavar="W.json")
    ap.add_argument("--lakes")
    a = ap.parse_args(argv)
    if a.write:
        print("REFUSED (nothing published): the Moon and Night Light Brain has no approved publication path; customer publication is off "
              "and execution control has it disabled.", file=sys.stderr)
        return 2
    if a.plan:
        print(json.dumps({"brainId": C.BRAIN_ID, "action": "SKIP", "status": "NOT_SCHEDULED",
                          "reason": "no executor (control manifest executionTarget none, PARKED) and no live writer"}))
        return 0
    date = dt.date.fromisoformat(a.date) if a.date else None
    now = dt.datetime.now(dt.timezone.utc)
    weather = json.load(open(a.weather, encoding="utf-8")) if a.weather else {}
    d = _directory(a.lakes)
    if a.tonight:
        out = {"schema": "moon-night-light-run-v1", "brainId": C.BRAIN_ID, "brainVersion": C.BRAIN_VERSION, "date": date.isoformat() if date else "PER_LAKE_CURRENT_NIGHT",
               "lakeRegistry": {k: d[k] for k in ("source", "registry", "count", "digest")}, "weatherInput": "PROVIDED" if weather else "ABSENT",
               "lakes": {r["lakeId"]: build_state(r, date or evening_date(r["lat"], r["lon"], now), weather.get(r["lakeId"])) for r in d["lakes"]}}
        with open(a.tonight, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print(json.dumps({"ok": True, "lakes": len(out["lakes"]), "date": out["date"], "out": a.tonight, "published": False}))
        return 0
    w = DryRunWriter()
    rep = publish(d, w, date, weather, now=now)
    w.dump(a.dry_run)
    print(json.dumps({**{k: rep.get(k) for k in ("ok", "evaluated", "skippedUnchanged", "readinessCounts", "darknessClass", "basis", "errors", "writes")},
                      "dryRunFile": a.dry_run, "published": False}, default=str))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except L.LakeRegistryError as e:
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
