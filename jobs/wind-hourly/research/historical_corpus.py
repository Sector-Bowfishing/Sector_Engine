"""Stage 3C historical NBM v5.0 corpus (pre-registered: docs/intelligence/wind/stage3c/WIND_HISTORICAL_CORPUS_PREREG.md).

  python research/historical_corpus.py nbm   [--workers 8]     # inits 2026-05-06 00Z .. 2026-10-06 23Z, leads 1/3/6/12/18
  python research/historical_corpus.py metar                     # IEM obs for the 8 frozen stations, each day of the window

Resumable: a cycle already archived complete for every lake is skipped. Writes only to the local historical store."""
import os, sys, json, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind.store import LocalStore
from sector_wind.ingest import ingest_nbm_cycle, ingest_metar_day, load_config

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
START, END = datetime(2026, 5, 6, 0, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
LEADS = [1, 3, 6, 12, 18]


def done(store, cfg, t):
    for lk in cfg["lakes"]:
        o = store.get_json(f"nbm/{lk}/{t:%Y%m%d%H}.json.gz")
        if not o or o.get("status") != "complete" or len(o["steps"]) != len(LEADS):
            return False
    return True


def one(t):
    store, cfg = LocalStore(ROOT), load_config()
    if done(store, cfg, t):
        return t, "skip"
    for attempt in range(4):
        try:
            r = ingest_nbm_cycle(store, cfg, t, LEADS, True)
            if all(v == "complete" for v in r.values()):
                return t, "ok"
        except Exception as e:
            r = repr(e)
        time.sleep(10 * (attempt + 1))
    return t, f"FAILED {r}"


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "nbm":
        from multiprocessing import Pool
        w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8
        inits = [START + timedelta(hours=h) for h in range(int((END - START).total_seconds() // 3600) + 1)]
        n = 0
        with Pool(w) as p:
            for t, st in p.imap_unordered(one, inits, chunksize=4):
                n += 1
                if st.startswith("FAILED") or n % 100 == 0:
                    print(f"{n}/{len(inits)} {t:%Y-%m-%dT%HZ} {st}", flush=True)
        print("NBM DONE", flush=True)
    elif cmd == "metar":
        store, cfg = LocalStore(ROOT), load_config()
        d = START - timedelta(days=1)
        while d <= END + timedelta(days=1):
            if not store.exists(f"metar/{d:%Y%m%d}.json.gz"):
                for a in range(3):
                    try:
                        ingest_metar_day(store, cfg, d); break
                    except Exception as e:
                        print(d.date(), repr(e), flush=True); time.sleep(5)
            d += timedelta(days=1)
        print("METAR DONE", flush=True)
