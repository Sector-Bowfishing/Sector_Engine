"""wind-hourly CLI.

  python main.py hourly   --store local:/path            # latest NBM cycle + last hour of RTMA-RU + METAR
  python main.py backfill --store local:/path --start 2026-09-22 --end 2026-10-05 [--leads 1,3,6,12]
  python main.py validate --store local:/path --start ... --end ...
  python main.py pw15     --store local:/path            # risky-night flag shadow: record the last 24 h of synoptic NBM cycles (no output; needs WIND_PW15_SHADOW=1)
  python main.py status   --store local:/path --start ... --end ...

Default store is local. A gs:// store refuses to open without SECTOR_WIND_GCS_APPROVED=yes
(Michael's approval) and never opens the shared production buckets."""
import argparse, json, os, sys, concurrent.futures as cf
from datetime import datetime, timedelta, timezone

from sector_wind.ingest import (DEFAULT_LEADS, ingest_metar_day, ingest_nbm_cycle, ingest_rtma, latest_nbm_cycle, load_config)
from sector_wind.store import open_store
from sector_wind import validate as V


def day(s):
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["retention"]:                       # archive retention on a runner's LOCAL store (dry run by default; its own options)
        from sector_wind import retention
        return retention.main(args[1:])
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hourly", "backfill", "validate", "status", "milestone", "pw15"])
    ap.add_argument("--store", default="local:./archive")
    ap.add_argument("--start"); ap.add_argument("--end")
    ap.add_argument("--leads", default=None)
    ap.add_argument("--no-qmd", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    cfg = load_config(); store = open_store(a.store)
    leads = [int(x) for x in a.leads.split(",")] if a.leads else DEFAULT_LEADS
    now = datetime.now(timezone.utc)
    if a.cmd == "pw15":
        from sector_wind import points, pw15
        if not pw15.enabled():
            print("REFUSED: set WIND_PW15_SHADOW=1 to record the shadow", file=sys.stderr); return 2
        newest = latest_nbm_cycle(now); out = {}
        if newest:
            t = newest - timedelta(hours=newest.hour % 6)
            for _ in range(4):                               # the last 24 h of synoptic cycles (qmd probability fields exist only there)
                key = f"pw15-shadow/{t:%Y%m%d%H}.json.gz"
                o = store.get_json(key) if store.exists(key) else None
                if not (o and o.get("status") == "complete"):
                    try:
                        out[t.isoformat()] = pw15.ingest_pw15_shadow(store, points.load_points(), t)
                    except Exception as e:
                        out[t.isoformat()] = {"status": "error", "error": repr(e)[:200]}
                t -= timedelta(hours=6)
        store.flush_ledger()
        print(json.dumps(out, default=str)); return 1 if any(v.get("status") == "error" for v in out.values()) else 0
    if a.cmd == "hourly":
        from sector_wind.live import run_hourly
        try:
            res = run_hourly(store, cfg, now, leads)
        finally:
            store.flush_ledger()          # the ledger is written even when the run fails
        print(json.dumps(res, default=str)[:4000])
        # WindBrain (additive, opt-in): publish the wind slot of the Brain RTDB from what this run archived.
        # It never raises and never changes this job's exit code: a Brain RTDB failure cannot affect the archive.
        brain_url = os.environ.get("SECTOR_WIND_BRAIN_RTDB_URL")
        if brain_url:
            from sector_wind.brain.publish import safe_publish
            from sector_wind.brain.writer import RtdbWriter
            shadow = os.environ.get("WIND_SHADOW_EQUIVALENCE") == "on" and os.environ.get("WIND_SHADOW_EVIDENCE_BUCKET")
            writer = None
            try:
                writer = RtdbWriter(brain_url)
                if shadow:                          # 7-day shadow equivalence (OFF by default): records what the legacy writer sent, nothing else changes
                    from sector_wind.brain.shadow_equivalence import RecordingWriter
                    writer = RecordingWriter(writer)
                brain = safe_publish(store, cfg, writer, now=now, run_summary=res)
            except Exception as e:                  # writer construction (bad URL) — still never fatal
                brain = {"ok": False, "errors": [repr(e)]}
            print("windbrain", json.dumps(brain, default=str)[:1500])
            if shadow and writer is not None and hasattr(writer, "patches"):
                try:                                # never fatal and never changes the exit code; evidence only (digests), GET-only readback
                    from sector_wind.brain import shadow_equivalence as SE
                    from sector_wind.brain.publish import deployment_version
                    from sector_brain_platform.object_bucket import GcsRestObjectStore
                    from sector_brain_platform.rtdb import TokenProvider
                    ev = SE.safe_record(writer, GcsRestObjectStore(shadow, TokenProvider()), now=now, code_version=deployment_version() or "wind@unknown")
                except Exception as e:
                    ev = {"verdict": "ERROR", "stored": False, "error": repr(e)[:200]}
                print("windshadow", json.dumps(ev, default=str)[:600])
        # A failed run must be visible as a failed Cloud Run execution, never a silent success.
        return 1 if res["errors"] else 0
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
    if a.cmd == "milestone":
        from sector_wind.monitor import milestone
        print(json.dumps(milestone(store, cfg, start, end), indent=1, default=str)); return 0
    if a.cmd == "status":
        print(json.dumps({"NBM": V.archive_success(store, "NBM", start, end, 60, list(cfg["lakes"])),
                          "RTMA-RU (hourly :00)": V.archive_success(store, "RTMA", start, end, 60, list(cfg["lakes"]))}, indent=1))
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                       # KnowledgeReleaseError: no approved memory -> refuse (exit 2), never a crash or a fallback
        if type(e).__name__ != "KnowledgeReleaseError":
            raise
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
