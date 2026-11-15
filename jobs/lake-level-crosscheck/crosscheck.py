"""Lake level cross-check collector: the level the Engine shows for a lake, logged next to an independent operator gauge.

Owner approval: Sector_Ops #51, 2026-11-11 ~23:40Z, decision 4 ("start a 30-day collector on the Mac mini logging Barkley's
live level next to USACE's ... runs under Pulse"). Evidence it answers: now-test LK-NOW-1 (Barkley UNVERIFIED: an independent
USACE gauge exists, but no overlapping record of the Engine's own source).

Pairs (fixed):
  Lake Barkley|KY  engine = NWPS KYDK2 observed pool (what WaterLevelService.reservoirs maps Barkley to: the Kentucky Lake pool)
                   independent = USACE CWMS LRN  BAHK2-BARKLEY.Elev-Pool.Inst.1Hour.0.dcp-rev  (Barkley Dam pool, USACE's own gauge)

Read-only public GETs; appends JSON lines under --data; never overwrites a stored (source, obsTime). After --until it records
nothing and exits 0.

usage: crosscheck.py collect --data DIR [--until 2026-12-12T00:00:00Z]
       crosscheck.py summarize --data DIR [--tolerance-ft 0.25]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request

PAIRS = {"Lake Barkley|KY": {
    "engine": {"kind": "nwps", "lid": "KYDK2"},
    "independent": {"kind": "cwms", "office": "LRN", "name": "BAHK2-BARKLEY.Elev-Pool.Inst.1Hour.0.dcp-rev"}}}
UA = {"User-Agent": "SectorPulse/1.0 (lake-level-crosscheck)"}


def _get(url: str, headers: dict | None = None, timeout: int = 60) -> dict:
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_time(s: str) -> str:
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return iso(t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc))


def read_nwps(lid: str, get=_get) -> list[tuple[str, float]]:
    d = get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow")
    o = d.get("observed") or {}
    if o.get("primaryUnits") != "ft":
        raise RuntimeError(f"NWPS {lid} units {o.get('primaryUnits')!r}")
    out = []
    for p in o.get("data") or []:
        v, t = p.get("primary"), p.get("validTime")
        if isinstance(v, (int, float)) and v > -900 and isinstance(t, str):
            out.append((norm_time(t), float(v)))
    return out


def read_cwms(office: str, name: str, now: dt.datetime, hours: int = 48, get=_get) -> list[tuple[str, float]]:
    q = {"name": name, "office": office, "begin": iso(now - dt.timedelta(hours=hours)), "end": iso(now)}
    d = get("https://cwms-data.usace.army.mil/cwms-data/timeseries?" + urllib.parse.urlencode(q), {"Accept": "application/json;version=2"})
    if d.get("units") != "ft":
        raise RuntimeError(f"CWMS {name} units {d.get('units')!r}")
    out = []
    for v in d.get("values") or []:
        if not isinstance(v, list) or len(v) < 2 or not isinstance(v[0], (int, float)) or not isinstance(v[1], (int, float)):
            continue
        # CWMS quality is a bit mask: bit 0 = screened; bits 2/3/4 = missing / questionable / rejected (when screened).
        q = v[2] if len(v) >= 3 and isinstance(v[2], int) else 0
        if q & 1 and q & (4 | 8 | 16):
            continue
        out.append((iso(dt.datetime.fromtimestamp(v[0] / 1000, dt.timezone.utc)), float(v[1])))
    return out


def stored(data: str) -> set:
    keys = set()
    for f in glob.glob(os.path.join(data, "*.jsonl")):
        for line in open(f):
            try:
                o = json.loads(line)
                keys.add((o["lake"], o["role"], o["obsTime"]))
            except (ValueError, KeyError):
                continue
    return keys


def collect(data: str, until: dt.datetime | None, now: dt.datetime | None = None, get=_get) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    if until and now >= until:
        return {"status": "WINDOW_ENDED", "until": iso(until), "added": 0}
    os.makedirs(data, exist_ok=True)
    have = stored(data)
    added, errors = 0, []
    path = os.path.join(data, f"{now:%Y-%m}.jsonl")
    with open(path, "a") as f:
        for lake, p in PAIRS.items():
            for role, src in p.items():
                try:
                    pts = read_nwps(src["lid"], get) if src["kind"] == "nwps" else read_cwms(src["office"], src["name"], now, get=get)
                except Exception as e:  # one source's failure or format change must not stop the other
                    errors.append(f"{lake} {role}: {type(e).__name__}: {str(e)[:160]}"); continue
                for t, v in pts:
                    if (lake, role, t) in have:
                        continue
                    f.write(json.dumps({"lake": lake, "role": role, "source": src, "obsTime": t, "valueFt": v, "fetchedAt": iso(now)}) + "\n")
                    have.add((lake, role, t)); added += 1
    return {"status": "OK" if not errors else "PARTIAL", "added": added, "errors": errors}


def summarize(data: str, tol: float = 0.25) -> dict:
    acc = {}
    for f in sorted(glob.glob(os.path.join(data, "*.jsonl"))):
        for line in open(f):
            try:
                o = json.loads(line)
                acc.setdefault(o["lake"], {}).setdefault(o["role"], {}).setdefault(norm_time(o["obsTime"])[:13], []).append(float(o["valueFt"]))
            except (ValueError, KeyError, TypeError):
                continue
    rows = {lk: {role: {h: statistics.mean(v) for h, v in hs.items()} for role, hs in r.items()} for lk, r in acc.items()}
    out = {}
    for lake, r in rows.items():
        e, i = r.get("engine", {}), r.get("independent", {})
        hours = sorted(set(e) & set(i))
        days = {}
        for h in hours:
            days.setdefault(h[:10], []).append((e[h], i[h]))
        dd = [(statistics.mean(a for a, _ in v), statistics.mean(b for _, b in v)) for v in days.values() if len(v) >= 12]
        diffs = [a - b for a, b in dd]
        out[lake] = {"matchedHours": len(hours), "matchedDays": len(dd),
                     "shareDaysWithinTol": round(sum(abs(x) <= tol for x in diffs) / len(diffs), 3) if diffs else None,
                     "meanDiffFt": round(statistics.mean(diffs), 3) if diffs else None,
                     "maxAbsDiffFt": round(max(abs(x) for x in diffs), 3) if diffs else None, "toleranceFt": tol}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect"); c.add_argument("--data", required=True); c.add_argument("--until")
    s = sub.add_parser("summarize"); s.add_argument("--data", required=True); s.add_argument("--tolerance-ft", type=float, default=0.25)
    a = ap.parse_args(argv)
    if a.cmd == "collect":
        until = dt.datetime.fromisoformat(a.until.replace("Z", "+00:00")) if a.until else None
        if until is not None and until.tzinfo is None:
            until = until.replace(tzinfo=dt.timezone.utc)
        r = collect(a.data, until)
        print(json.dumps(r))
        return 0 if r["status"] in ("OK", "WINDOW_ENDED") else 1
    print(json.dumps(summarize(a.data, a.tolerance_ft), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
