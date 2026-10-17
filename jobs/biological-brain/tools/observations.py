"""Observation intake and reporting for Biological validation (local files only; never writes a cloud service).

  python3 tools/observations.py validate trips.json                 # check a list of observations; prints every problem
  python3 tools/observations.py append  store.jsonl trips.json      # validate, then append (append-only, hash-chained; duplicates refused)
  python3 tools/observations.py summary store.jsonl                 # counts, independent trips, non-encounter share, effort hours
  python3 tools/observations.py evaluate predictions.jsonl store.jsonl   # hit rate + effort-adjusted shootable-encounter rates (descriptive, no verdict)
  python3 tools/observations.py from-csv trips.csv trips.json       # a tester's spreadsheet -> observation JSON (local time + lake timezone -> UTC)

A trips file is a JSON list of observation objects (schemas/observation.schema.json). One observation = one zone on one trip, with its effort;
NON-encounters are recorded (encountered=false) because a rule cannot be validated from successful trips alone.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import validation_log as vl   # noqa: E402


def _load(path):
    data = json.load(open(path))
    return data if isinstance(data, list) else [data]


def cmd_validate(trips_path):
    bad = 0
    for i, o in enumerate(_load(trips_path)):
        errs = vl.validate_observation(o)
        if errs:
            bad += 1
            print(f"#{i} {o.get('observationId')}: " + "; ".join(errs))
    print("OK: all observations valid" if not bad else f"{bad} invalid observation(s)")
    return 1 if bad else 0


def cmd_append(store_path, trips_path):
    st = vl.ObservationStore(store_path)
    obs = _load(trips_path)
    errs = {o.get("observationId"): vl.validate_observation(o) for o in obs}
    if any(errs.values()):                                   # all-or-nothing: a partly valid batch is not half-written
        for k, v in errs.items():
            if v:
                print(f"{k}: " + "; ".join(v))
        print("nothing appended")
        return 1
    for o in obs:
        st.append(o)
    print(f"appended {len(obs)}; store now {st.verify()} observation(s)")
    return 0


def summarize(entries):
    sp = [o for o in entries if o["speciesIdConfidence"] in ("CONFIRMED", "LIKELY")]
    return {"observations": len(entries), "independentTrips": len({o["tripId"] for o in entries}), "speciesLevelObservations": len(sp),
            "nonEncounters": sum(1 for o in entries if not o["encountered"]), "effortHours": round(sum(o["effortMinutes"] for o in entries) / 60.0, 2),
            "groupLevelOnly": sum(1 for o in entries if o["speciesIdConfidence"] in ("GROUP_ONLY", "UNCERTAIN"))}


def cmd_summary(store_path):
    print(json.dumps(summarize(vl.ObservationStore(store_path).entries()), indent=1))
    return 0


def cmd_evaluate(pred_path, store_path):
    preds = [json.loads(x) for x in open(pred_path) if x.strip()]
    obs = vl.ObservationStore(store_path).entries()
    print(json.dumps({"hitRate": vl.evaluate(preds, obs), "effortAdjusted": vl.effort_adjusted_rates(preds, obs)}, indent=1))
    return 0


LAKE_TZ = {"Guntersville|AL": "America/Chicago", "Lake Hartwell|SC": "America/New_York"}
CSV_COLUMNS = ("tripId", "observerId", "lakeId", "localDateTime", "species", "speciesIdConfidence", "speciesGroup", "encountered", "count", "shootableCount", "effortMinutes", "zone",
               "depthClass", "vegetation", "waterTempF", "clarityBand", "windBand", "levelContext", "spawnBehaviorObserved", "observerConfidence", "notes")


def _yes(v):
    v = str(v).strip().lower()
    return True if v in ("y", "yes", "true", "1") else False if v in ("n", "no", "false", "0") else None


def rows_to_observations(rows):
    """Spreadsheet rows -> observation dicts. Blank optional cells are omitted (never defaulted). The observationId is derived from the row, so re-running is idempotent."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    out, problems = [], []
    for n, r in enumerate(rows, start=2):
        r = {k: (v or "").strip() for k, v in r.items() if k}
        try:
            tz = ZoneInfo(LAKE_TZ.get(r["lakeId"], "UTC"))
            local = dt.datetime.strptime(r["localDateTime"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            o = {"tripId": r["tripId"], "observerId": r["observerId"], "lakeId": r["lakeId"], "observedAt": local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "speciesId": r["species"] or "unidentified", "speciesIdConfidence": r["speciesIdConfidence"].upper(), "encountered": _yes(r["encountered"]),
                 "effortMinutes": float(r["effortMinutes"]), "zone": r["zone"], "observerConfidence": (r["observerConfidence"] or "MEDIUM").upper()}
            if r.get("speciesGroup"):
                o["speciesGroup"] = r["speciesGroup"]
            for k in ("count", "shootableCount"):
                if r.get(k):
                    o[k] = int(r[k])
            if o["encountered"] is False:
                o["count"] = 0
                if "shootableCount" not in o:
                    o["shootableCount"] = 0
            for k in ("depthClass", "vegetation", "clarityBand", "windBand", "levelContext"):
                if r.get(k):
                    o[k] = r[k].upper() if k != "depthClass" else r[k]
            if r.get("waterTempF"):
                o["waterTempF"] = float(r["waterTempF"])
            if r.get("spawnBehaviorObserved"):
                o["spawnBehaviorObserved"] = _yes(r["spawnBehaviorObserved"]) if _yes(r["spawnBehaviorObserved"]) is not None else "UNKNOWN"
            if r.get("notes"):
                o["notes"] = r["notes"]
            import hashlib
            o["observationId"] = "o_" + hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()[:16]
            out.append(o)
        except (KeyError, ValueError) as e:
            problems.append(f"row {n}: {type(e).__name__}: {e}")
    return out, problems


def cmd_from_csv(csv_path, out_path):
    import csv
    rows = list(csv.DictReader(open(csv_path, newline="")))
    obs, problems = rows_to_observations(rows)
    for i, o in enumerate(obs):
        errs = vl.validate_observation(o)
        if errs:
            problems.append(f"row {i + 2}: " + "; ".join(errs))
    if problems:
        print("\n".join(problems))
        print("nothing written")
        return 1
    json.dump(obs, open(out_path, "w"), indent=1)
    print(f"wrote {len(obs)} observation(s) to {out_path}")
    return 0


def main(argv):
    cmds = {"from-csv": (cmd_from_csv, 2), "validate": (cmd_validate, 1), "append": (cmd_append, 2), "summary": (cmd_summary, 1), "evaluate": (cmd_evaluate, 2)}
    if len(argv) < 2 or argv[1] not in cmds or len(argv) - 2 != cmds[argv[1]][1]:
        print(__doc__)
        return 2
    return cmds[argv[1]][0](*argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
