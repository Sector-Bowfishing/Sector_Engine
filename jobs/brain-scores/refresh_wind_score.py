#!/usr/bin/env python3
"""Admit a candidate Wind certification block (produced by the canonical Wind scorer / block generator) into frozen-scores.json.

  python3 refresh_wind_score.py --candidate CANDIDATE.json                 # dry run: prints ACCEPT / HOLD / NO_CHANGE + reasons
  python3 refresh_wind_score.py --candidate CANDIDATE.json --write         # ACCEPT -> splice the wind block + append history

CANDIDATE.json is either a bare wind block or a frozen-scores.json copy (its "wind" entry is used). Writes only repository files
(frozen-scores.json, wind-score-history.jsonl); publication to /scores/wind stays with score_brains.py --write. Never touches RTDB.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
from sector_brain_platform.wind_score_refresh import refresh  # noqa: E402

SCORING = os.path.join(HERE, "..", "..", "docs", "brains", "scoring")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--frozen", default=os.path.join(SCORING, "frozen-scores.json"))
    ap.add_argument("--history", default=os.path.join(SCORING, "wind-score-history.jsonl"))
    ap.add_argument("--now", default=None, help="evaluation clock (ISO, tests/demos)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    cand = json.load(open(a.candidate))
    cand = cand.get("wind", cand) if "scoreVersion" not in cand else cand
    now = dt.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else dt.datetime.now(dt.timezone.utc)
    line = refresh(a.frozen, a.history, cand, now, write=a.write)
    print(json.dumps(line, indent=1))
    print(f"\n{line['decision']}" + (" (written)" if a.write and line["decision"] == "ACCEPT" else " (dry run)" if not a.write else ""))
    return 0 if line["decision"] in ("ACCEPT", "NO_CHANGE") else 2


if __name__ == "__main__":
    sys.exit(main())
