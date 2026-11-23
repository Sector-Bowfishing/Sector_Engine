#!/usr/bin/env python3
"""Moon and Night Light Brain run entry (CALIBRATION). Not scheduled (control manifest PARKED, executionTarget kind none; execution control
disabled). The live writer exists but is gated: --write refuses without an APPROVED release AND MOON_WRITE_APPROVED=1.

  python run.py --plan                                               # one JSON verdict: SKIP (no executor)
  python run.py --tonight OUT.json [--date YYYY-MM-DD] [--weather W.json] [--lakes "Guntersville|AL,..."]
                                                                     # tonight for every directory lake (or the listed ones) as a local JSON file
  python run.py --dry-run OUT.json [--date ...] [--weather ...]      # build the RTDB write set into an in-memory store and dump it; writes nothing remote
  python run.py --write                                              # publish every directory lake to the Brain RTDB: needs an APPROVED knowledge
                                                                     # release (else exit 2, BLOCKED_AWAITING_APPROVED_RELEASE) AND
                                                                     # MOON_WRITE_APPROVED=1 (operator intent; else exit 3). Cloud input: each
                                                                     # lake's published Weather state (GET), used only within WEATHER_MAX_AGE_HOURS

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
from moon_brain.publish import LIVE_MODE, publish  # noqa: E402
from moon_brain.state import build_state  # noqa: E402
from moon_brain.writer import DryRunWriter  # noqa: E402
from sector_brain_platform import lake_key  # noqa: E402

RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
WRITE_INTENT_ENV = "MOON_WRITE_APPROVED"
WEATHER_MAX_AGE_HOURS = 3        # == control manifest moon -> weather dependency maxAgeHours (Weather's staleAfterHours); tested
DRY_RUN_ONLY = ("date", "weather", "lakes")


def _directory(only: str | None) -> dict:
    d = L.load()
    if only:
        want = {s.strip() for s in only.split(",") if s.strip()}
        unknown = want - {r["lakeId"] for r in d["lakes"]}
        if unknown:
            raise L.LakeRegistryError(f"not directory lakes: {sorted(unknown)}")
        d = {**d, "lakes": [r for r in d["lakes"] if r["lakeId"] in want]}
    return d


def read_weather(writer, directory: dict, now: dt.datetime) -> tuple[dict, dict]:
    """{lakeId: Weather state} from the Brain RTDB (GET /lakes/{k}/states/weather), keeping only states generated within WEATHER_MAX_AGE_HOURS.
    An absent, unreadable-time or older state is NOT used: that lake gets the moon-only answer, labelled as such. Counts are reported."""
    used, counts = {}, {"used": 0, "absent": 0, "tooOld": 0, "noGeneratedAt": 0}
    for r in directory["lakes"]:
        st = writer.get(f"lakes/{lake_key(r['lakeId'])}/states/weather")
        if not isinstance(st, dict):
            counts["absent"] += 1
            continue
        try:
            gen = dt.datetime.fromisoformat(str(st["generatedAt"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            counts["noGeneratedAt"] += 1
            continue
        if gen.tzinfo is None or (now - gen).total_seconds() > WEATHER_MAX_AGE_HOURS * 3600:
            counts["tooOld"] += 1
            continue
        used[r["lakeId"]] = st
        counts["used"] += 1
    return used, counts


def write_gate(a, d: dict) -> int:
    """0 when a live write may proceed; else the refusal exit code. Order: release approval (raises, exit 2), then operator intent (exit 3)."""
    L.require_approved(d)
    if os.environ.get(WRITE_INTENT_ENV) != "1":
        print(f"refusing: --write needs {WRITE_INTENT_ENV}=1 (operator intent; owner approval of the first Moon write)", file=sys.stderr)
        return 3
    given = [o for o in DRY_RUN_ONLY if getattr(a, o)]
    if given:
        print(f"refusing: {', '.join('--' + o for o in given)} are dry-run options; a live write reads Weather from the Brain RTDB", file=sys.stderr)
        return 3
    return 0


def live_write(d: dict) -> int:
    from moon_brain.writer import RtdbWriter
    w = RtdbWriter(RTDB_URL)
    now = dt.datetime.now(dt.timezone.utc)
    weather, wc = read_weather(w, d, now)
    rep = publish(d, w, None, weather, now=now, publish_mode=LIVE_MODE)
    print(json.dumps({**{k: rep.get(k) for k in ("ok", "evaluated", "skippedUnchanged", "readinessCounts", "darknessClass", "basis", "errors", "writes")},
                      "weatherInput": wc, "knowledgeRelease": d.get("release"), "published": True}, default=str))
    return 0 if rep.get("ok") else 1


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
        d = L.load()                                                   # verify first: missing/tampered -> LakeRegistryError (exit 2)
        rc = write_gate(a, d)                                           # unapproved -> KnowledgeNotApproved (exit 2, BLOCKED)
        return rc or live_write(d)
    if a.plan:
        print(json.dumps({"brainId": C.BRAIN_ID, "action": "SKIP", "status": "NOT_SCHEDULED",
                          "reason": "no executor (control manifest executionTarget none, PARKED); the live writer is gated (APPROVED release and MOON_WRITE_APPROVED=1)"}))
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
