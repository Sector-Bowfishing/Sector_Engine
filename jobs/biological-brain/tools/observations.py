"""Observation intake and reporting for Biological validation (local files only; never writes a cloud service).

  python3 tools/observations.py validate trips.json                 # check a list of observations; prints every problem
  python3 tools/observations.py append  store.jsonl trips.json      # validate, then append (append-only, hash-chained; duplicates refused)
  python3 tools/observations.py summary store.jsonl                 # counts, independent trips, non-encounter share, effort hours
  python3 tools/observations.py evaluate predictions.jsonl store.jsonl   # hit rate + effort-adjusted shootable-encounter rates (descriptive, no verdict)

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


def main(argv):
    cmds = {"validate": (cmd_validate, 1), "append": (cmd_append, 2), "summary": (cmd_summary, 1), "evaluate": (cmd_evaluate, 2)}
    if len(argv) < 2 or argv[1] not in cmds or len(argv) - 2 != cmds[argv[1]][1]:
        print(__doc__)
        return 2
    return cmds[argv[1]][0](*argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
