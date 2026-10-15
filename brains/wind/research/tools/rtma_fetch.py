"""Stage 3D.2 §10: historical RTMA-RU analyses at the synoptic CAL inits (anchor for the pre-registered RTMA nowcast fit).

  python research/rtma_fetch.py [--workers 4]      # 2026-05-06 00Z .. 2026-08-15 18Z, every 6 h (CAL only; nothing later)

Uses the Candidate's own ingest_rtma (same decoder, self-check, lake cut-outs) into the local historical store. Resumable."""
import os, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime"))  # brains/wind/runtime
from sector_wind.store import LocalStore
from sector_wind.ingest import ingest_rtma, load_config

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
START, END = datetime(2026, 5, 6, 0, tzinfo=timezone.utc), datetime(2026, 8, 15, 18, tzinfo=timezone.utc)   # CAL window only


def one(t):
    st, cfg = LocalStore(ROOT), load_config()
    if all(st.get_json(f"rtma/{lk}/{t:%Y%m%d}/{t:%H%M}.json.gz") for lk in cfg["lakes"]):
        return t, "skip"
    return t, ingest_rtma(st, cfg, t)


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    ts, t = [], START
    while t <= END:
        ts.append(t); t += timedelta(hours=6)
    with ThreadPoolExecutor(n) as ex:
        for t, r in ex.map(one, ts):
            print(t.isoformat(), r if isinstance(r, str) else ",".join(sorted(set(r.values()))), flush=True)
    print("RTMA DONE", flush=True)
