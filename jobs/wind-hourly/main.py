"""wind-hourly CLI.

  python main.py hourly   --store local:/path            # latest NBM cycle + last hour of RTMA-RU + METAR
  python main.py backfill --store local:/path --start 2026-09-22 --end 2026-10-05 [--leads 1,3,6,12]
  python main.py validate --store local:/path --start ... --end ...
  python main.py status   --store local:/path --start ... --end ...

Default store is local. A gs:// store refuses to open without SECTOR_WIND_GCS_APPROVED=yes
(Michael's approval) and never opens the shared production buckets."""
import argparse, json, sys, concurrent.futures as cf
from datetime import datetime, timedelta, timezone

from sector_wind.ingest import (DEFAULT_LEADS, ingest_metar_day, ingest_nbm_cycle, ingest_rtma, latest_nbm_cycle, load_config)
from sector_wind.store import open_store
from sector_wind import validate as V


def day(s):
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hourly", "backfill", "validate", "status"])
    ap.add_argument("--store", default="local:./archive")
    ap.add_argument("--start"); ap.add_argument("--end")
    ap.add_argument("--leads", default=None)
    ap.add_argument("--no-qmd", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    cfg = load_config(); store = open_store(a.store)
    leads = [int(x) for x in a.leads.split(",")] if a.leads else DEFAULT_LEADS
    now = datetime.now(timezone.utc)
    if a.cmd == "hourly":
        c = latest_nbm_cycle(now)
        res = {"nbm": ingest_nbm_cycle(store, cfg, c, leads, not a.no_qmd) if c else "no cycle"}
        t0 = (now - timedelta(minutes=30)).replace(second=0, microsecond=0)
        t0 = t0.replace(minute=(t0.minute // 15) * 15)
        res["rtma"] = {f"{t:%H%M}": ingest_rtma(store, cfg, t) for t in [t0 - timedelta(minutes=15 * i) for i in range(4)]}
        for d in {now.date(), (now - timedelta(hours=3)).date()}:
            res.setdefault("metar", {})[str(d)] = ingest_metar_day(store, cfg, datetime(d.year, d.month, d.day, tzinfo=timezone.utc))
        print(json.dumps(res, default=str)); return 0
    start, end = day(a.start), day(a.end) + timedelta(hours=23)
    if a.cmd == "backfill":
        cycles = [start + timedelta(hours=h) for h in range(int((end - start).total_seconds() // 3600) + 1)]
        with cf.ThreadPoolExecutor(a.workers) as ex:
            for c, r in zip(cycles, ex.map(lambda c: ingest_nbm_cycle(store, cfg, c, leads, not a.no_qmd), cycles)):
                print("NBM", c.isoformat(), r, flush=True)
            for c, r in zip(cycles, ex.map(lambda c: ingest_rtma(store, cfg, c), cycles)):
                print("RTMA", c.isoformat(), r, flush=True)
        d = start
        while d <= end + timedelta(days=1):
            print("METAR", d.date(), ingest_metar_day(store, cfg, d), flush=True); d += timedelta(days=1)
        return 0
    if a.cmd == "validate":
        rep = {"nbm": V.skill(store, cfg, start, end, tuple(leads) if a.leads else (1, 3, 6, 12)),
               "rtma": V.rtma_skill(store, cfg, start, end)}
        store.put_json(f"reports/validation_{a.start}_{a.end}.json", rep)
        print(json.dumps(rep, indent=1, default=str)); return 0
    if a.cmd == "status":
        print(json.dumps({"NBM": V.archive_success(store, "NBM", start, end, 60, list(cfg["lakes"])),
                          "RTMA-RU (hourly :00)": V.archive_success(store, "RTMA", start, end, 60, list(cfg["lakes"]))}, indent=1))
        return 0


if __name__ == "__main__":
    sys.exit(main())
