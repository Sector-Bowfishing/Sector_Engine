#!/usr/bin/env python3
"""Automated substitute for the 60-row binding review sample (review of Sector_Engine #211, 2026-11-20): a READ-ONLY pass/fail check of every
accepted Lake binding, from a LOCAL LakeBrainJob dry run (no --rtdb, no --read-rtdb) built at the PR head.

Per accepted lake it checks:
  (a) observed   the dry run wrote a state with kind OBSERVED, an observed source capability, a value, and freshness.stale == false
  (b) fallback   where the binding has a second live provider: its latest reading is within --fallback-ft (0.5 ft) of the state's value
                 (cwms, usgs and nwps are fetched over public HTTPS, GET only; other providers report n/a)
  (c) history    the state's value is within --history-ft (5 ft) of the median of the lake's own most recent --history-days (7) daily
                 values in the local archive (history/{lakeKey}/daily.csv, last 30 days only); n/a when fewer than 3 such values.
                 Recent days, not a 365-day median, so a normal seasonal drawdown or fill doesn't fail (2026-11-21 review).
  (d) reference  the live level vs the lake's own seasonal reference when the state carries one: |differenceFromGuideFt| (guide curve),
                 else the distance outside its operatingZone; only when neither exists, |differenceFromNormalPoolFt| (the Engine
                 directory's full pool). Each must be <= --full-pool-ft (25 ft).
El Vado Lake|NM, John Martin Reservoir|CO and Don Pedro|CA are always marked HAND REVIEW (large drawdowns are expected there).

A lake PASSES when (a) passes and no other check fails (n/a does not fail). Output: a markdown table on stdout, plus --csv FILE.
Exit 0 = every lake passed (hand-review lakes excepted); 1 = at least one FAIL; 2 = bad input.

It writes nothing except the optional --csv file. It never touches a database, bucket or Pulse config.

HOW TO RUN ON THE MAC MINI (no Pulse change, no restart):
  1. Build LakeBrainJob at the PR head, exactly as for a Pulse rebuild but into a scratch folder:
       git -C ~/Sector_Engine fetch origin pull/211/head:pr211 && git -C ~/Sector_Engine archive pr211 | tar -x -C /tmp/lake-pr211
       cd /tmp/lake-pr211 && swift build -c release --product LakeBrainJob --only-use-versions-from-resolved-file
  2. Copy the archive so the dry run cannot change Pulse's own:
       cp -R "<Pulse data dir>/archive" /tmp/lake-archive-copy
  3. Dry run every accepted lake (local only; candidates are not needed because the PR marks them REVIEWED):
       /tmp/lake-pr211/.build/release/LakeBrainJob --dry-run /tmp/lake-dry --scope pilots --force \
           --archive /tmp/lake-archive-copy --seed-archive "<publication.lakeSeedArchive>" --presence "<publication.lakePresence>"
     (expect ~45-60 min for 194 lakes; run it outside :40-:59 UTC so it doesn't overlap the hourly cycle's lake work)
  4. Check:
       python3 /tmp/lake-pr211/tools/ops/lake_binding_dryrun_check.py --dry-run /tmp/lake-dry --archive /tmp/lake-archive-copy --csv /tmp/lake-check.csv
  5. Post the table on Sector_Ops #51. Remove /tmp/lake-pr211, /tmp/lake-dry and /tmp/lake-archive-copy afterwards.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PLATFORM = os.path.join(ROOT, "jobs", "brain_platform")
if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)
from sector_brain_platform.keys import lake_key   # noqa: E402

DATA = os.path.join(ROOT, "jobs", "lake-brain", "data")
BINDINGS = os.path.join(DATA, "bindings.proposed.v1.json")
ACCEPTED = os.path.join(DATA, "accepted_batch.json")
OBSERVED_CAPS = ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE")
HAND_REVIEW = ("El Vado Lake|NM", "John Martin Reservoir|CO", "Don Pedro|CA")
UA = "SectorLakeBindingCheck/1.0 (read-only; Sector_Engine #211)"


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _get(url: str, accept: str = "application/json", timeout: int = 30):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310 - fixed public HTTPS endpoints, GET only
        return json.loads(r.read().decode("utf-8"))


# ------------------------------------------------------------------------------------------------ fallback readings (GET only)
def latest_cwms(office: str, series: str):
    q = urllib.parse.urlencode({"name": series, "office": office, "begin": "PT-24H", "unit": "EN"})
    raw = _get(f"https://cwms-data.usace.army.mil/cwms-data/timeseries?{q}", accept="application/json;version=2")
    k = 0.3048 ** -1 if str(raw.get("units", "ft")).lower() == "m" else 1.0
    vals = [(row[0], row[1]) for row in raw.get("values") or [] if len(row) >= 2 and row[1] is not None]
    return (vals[-1][1] * k) if vals else None


def latest_usgs(site: str, param: str):
    raw = _get(f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={param}&period=PT24H")
    for ts in (raw.get("value") or {}).get("timeSeries") or []:
        vals = [v for blk in ts.get("values") or [] for v in blk.get("value") or []]
        good = [float(v["value"]) for v in vals if v.get("value") not in (None, "", "-999999")]
        if good:
            return good[-1]
    return None


def latest_nwps(lid: str):
    raw = _get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow/observed")
    if str(raw.get("primaryUnits", "ft")).lower() != "ft":
        return None
    vals = [r.get("primary") for r in raw.get("data") or [] if isinstance(r.get("primary"), (int, float)) and r["primary"] > -990]
    return float(vals[-1]) if vals else None


def fallback_reading(live: dict):
    p, st, se = live.get("provider"), live.get("station"), live.get("series")
    if p == "cwms" and st and se:
        v = latest_cwms(st, se)
    elif p == "usgs" and st and se:
        v = latest_usgs(st, se)
    elif p == "nwps" and st:
        v = latest_nwps(st)
    else:
        return None, f"n/a ({p} not fetched)"
    if v is None:
        return None, f"n/a ({p} {st}: no recent reading)"
    return v + float(live.get("datumOffsetFt") or 0.0), f"{p}:{st}"


# ------------------------------------------------------------------------------------------------ the checks
def history_median(archive: str | None, lake_id: str, now: dt.date, days: int = 7):
    """Median of the lake's own most recent `days` daily values within the last 30 days; None when fewer than 3."""
    if not archive:
        return None
    path = os.path.join(archive, "history", lake_key(lake_id), "daily.csv")
    if not os.path.exists(path):
        return None
    cut = (now - dt.timedelta(days=30)).isoformat()
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                if cut <= row["date"] <= now.isoformat():
                    rows.append((row["date"], float(row["elevationFt"])))
            except (KeyError, ValueError, TypeError):
                continue
    vals = [v for _, v in sorted(rows)[-days:]]
    return statistics.median(vals) if len(vals) >= 3 else None


def reference_distance(state: dict):
    """(distance ft, label) against the lake's own seasonal reference, else the directory full pool; (None, '') when none."""
    g = state.get("differenceFromGuideFt")
    if isinstance(g, (int, float)):
        return abs(g), "vs guide curve"
    z = state.get("operatingZone") or {}
    v = state.get("currentElevationFt")
    lo, hi = z.get("bottomFt"), z.get("topFt")
    if isinstance(v, (int, float)) and isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return (0.0 if lo <= v <= hi else min(abs(v - lo), abs(v - hi))), "outside operating zone"
    n = state.get("differenceFromNormalPoolFt")
    if isinstance(n, (int, float)):
        return abs(n), "vs directory full pool"
    return None, ""


def check_lake(lake_id: str, binding: dict, state: dict | None, args, today: dt.date, network: bool) -> dict:
    row = {"lakeId": lake_id, "provider": binding.get("provider"), "station": binding.get("station"),
           "value": None, "a": "FAIL", "b": "n/a", "c": "n/a", "d": "n/a", "result": "FAIL", "notes": ""}
    notes = []
    # (a) observed
    if not isinstance(state, dict):
        notes.append("no state written")
    else:
        v = state.get("currentElevationFt")
        row["value"] = v
        fresh = (state.get("freshness") or {}).get("stale") is False
        if state.get("kind") == "OBSERVED" and state.get("sourceCapability") in OBSERVED_CAPS and isinstance(v, (int, float)) and fresh:
            row["a"] = "PASS"
        else:
            notes.append(f"kind={state.get('kind')} cap={state.get('sourceCapability')} stale={(state.get('freshness') or {}).get('stale')}")
    v = row["value"]
    # (b) fallback provider
    used = ""
    if isinstance(state, dict):
        srcs = (state.get("provenance") or {}).get("sources") or []
        used = (srcs[0].get("sourceId") or "").split(":")[0] if srcs else ""
    others = [l for l in binding.get("live") or [] if l.get("provider") != used]
    if network and isinstance(v, (int, float)) and others and len(binding.get("live") or []) > 1:
        for live in others:
            try:
                fb, label = fallback_reading(live)
            except Exception as e:                                   # noqa: BLE001 - a fetch failure is n/a, not a binding failure
                fb, label = None, f"n/a ({live.get('provider')}: {type(e).__name__})"
            if fb is None:
                row["b"] = label
                continue
            d = abs(v - fb)
            row["b"] = ("PASS" if d <= args.fallback_ft else "FAIL") + f" ({label} {d:.2f} ft)"
            break
    elif not network:
        row["b"] = "n/a (--no-network)"
    # (c) own history
    med = history_median(args.archive, lake_id, today, args.history_days)
    if med is not None and isinstance(v, (int, float)):
        d = abs(v - med)
        row["c"] = ("PASS" if d <= args.history_ft else "FAIL") + f" ({d:.1f} ft vs last {args.history_days} days)"
    # (d) seasonal reference (guide curve / operating zone), else the directory full pool
    if isinstance(state, dict):
        d, label = reference_distance(state)
        if d is not None:
            row["d"] = ("PASS" if d <= args.full_pool_ft else "FAIL") + f" ({d:.1f} ft {label})"
    failed = row["a"] != "PASS" or any(str(row[k]).startswith("FAIL") for k in ("b", "c", "d"))
    row["result"] = "HAND REVIEW" if lake_id in HAND_REVIEW else ("FAIL" if failed else "PASS")
    row["notes"] = "; ".join(notes)
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", required=True, help="the LakeBrainJob --dry-run output folder")
    ap.add_argument("--archive", help="the LOCAL archive copy the dry run used (history/{lakeKey}/daily.csv)")
    ap.add_argument("--bindings", default=BINDINGS)
    ap.add_argument("--accepted", default=ACCEPTED)
    ap.add_argument("--fallback-ft", type=float, default=0.5)
    ap.add_argument("--history-ft", type=float, default=5.0)
    ap.add_argument("--history-days", type=int, default=7, help="recent daily values the history check compares against")
    ap.add_argument("--full-pool-ft", type=float, default=25.0)
    ap.add_argument("--no-network", action="store_true", help="skip check (b)")
    ap.add_argument("--csv", help="also write the table as CSV")
    a = ap.parse_args(argv)
    try:
        bindings = {r["lakeId"]: r for r in _json(a.bindings)["bindings"]}
        acc = _json(a.accepted)
        accepted = acc.get("lakeIds") if isinstance(acc, dict) else acc
    except (OSError, ValueError, KeyError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    if not os.path.isdir(a.dry_run):
        print(f"REFUSED: --dry-run {a.dry_run} is not a folder", file=sys.stderr)
        return 2
    today = dt.datetime.now(dt.timezone.utc).date()
    rows = []
    for lake_id in sorted(accepted):
        state_path = os.path.join(a.dry_run, "lakes", lake_key(lake_id), "states", "lake.json")
        state = _json(state_path) if os.path.exists(state_path) else None
        rows.append(check_lake(lake_id, bindings.get(lake_id) or {}, state, a, today, not a.no_network))
    esc = lambda s: str(s if s is not None else "").replace("|", "\\|")
    print("| Lake | Source | Value (ft) | (a) observed | (b) fallback | (c) recent history | (d) reference | Result | Notes |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {esc(r['lakeId'])} | {esc(r['provider'])}:{esc(r['station'])} | {esc(r['value'])} | {r['a']} | {esc(r['b'])} | {esc(r['c'])} | "
              f"{esc(r['d'])} | {r['result']} | {esc(r['notes'])} |")
    counts = {k: sum(1 for r in rows if r["result"] == k) for k in ("PASS", "FAIL", "HAND REVIEW")}
    print(f"\n{len(rows)} lakes: {counts['PASS']} pass, {counts['FAIL']} fail, {counts['HAND REVIEW']} hand review")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["lakeId"])
            w.writeheader()
            w.writerows(rows)
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
