"""Stage 3D.2 §13–15: Visual Crossing historical ISSUED forecasts vs direct NBM on identical rows (CAL + H1 only; H2 sealed).

  VISUAL_CROSSING_KEY=… python research/vc_retro.py fetch [--datasets]   # immutable raw per basis date / station
  python research/vc_retro.py eval OUT.json                               # same-row metrics + decision value

forecastBasisDate = the day the forecast was run (Visual Crossing: one 00 UTC basis per day). Each basis is paired with the
NBM 00Z init of the same day; lead = valid − 00Z, so only leads present in the NBM corpus (1/3/6/12/18) are scored.
--datasets also pulls forecastDataset=ndfd,hrrr,gfs,ecmwf (single-model output), each kept as its own product.
Without a key the script stops at the credential boundary (nothing is guessed or substituted)."""
import json, os, pickle, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime"))  # brains/wind/runtime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sector_wind_research.provider_bakeoff import visual_crossing_request, _strip, UA, POINTS
import hashlib

RAW = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50/visualcrossing")
ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
START, END = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 5, tzinfo=timezone.utc)   # H2 (>= 10-07) never requested
STATIONS = ["8A1", "4A6", "DCU", "HSV", "9A4", "MSL", "SNH", "15M"]


def fetch(datasets):
    key = os.environ.get("VISUAL_CROSSING_KEY")
    if not key:
        sys.exit("CREDENTIAL BOUNDARY: VISUAL_CROSSING_KEY (with historical-forecast access) is required; see WIND_PROVIDER_BAKEOFF.md")
    d = START
    while d <= END:
        for sid in STATIONS:
            for ds in [None] + (["ndfd", "hrrr", "gfs", "ecmwf"] if datasets else []):
                p = os.path.join(RAW, ds or "blend", f"{d:%Y%m%d}", f"{sid}.json")
                if os.path.exists(p):
                    continue
                url = visual_crossing_request(*POINTS[sid], f"{d:%Y-%m-%d}", f"{d + timedelta(days=1):%Y-%m-%d}", key, basis_date=f"{d:%Y-%m-%d}", dataset=ds)
                body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "w").write(json.dumps({"request": _strip(url), "basisDate": f"{d:%Y-%m-%d}", "retrievedAt": datetime.now(timezone.utc).isoformat(),
                                               "sha256": hashlib.sha256(body).hexdigest(), "payload": body.decode()})); os.chmod(p, 0o444)
                time.sleep(0.2)
        d += timedelta(days=1)
    print("VC FETCH DONE")


def eval_(outp):
    import stage3d2_eval as E
    R = pickle.load(open(ROWS, "rb"))
    idx = {(r["station"], r["init"], r["lead"]): r for r in R if r["set"] in ("CAL", "H1")}
    res = {}
    for prod in sorted(os.listdir(RAW)) if os.path.isdir(RAW) else []:
        P = []
        for day in sorted(os.listdir(os.path.join(RAW, prod))):
            init = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc)
            for f in os.listdir(os.path.join(RAW, prod, day)):
                sid = f[:-5]; js = json.loads(json.load(open(os.path.join(RAW, prod, day, f)))["payload"])
                for dd in js.get("days", []):
                    for h in dd.get("hours", []):
                        vt = datetime.fromtimestamp(h["datetimeEpoch"], timezone.utc); L = int((vt - init).total_seconds() // 3600)
                        r = idx.get((sid, init, L))
                        if r and h.get("windspeed") is not None:
                            P.append((r, (h["windspeed"], h.get("winddir"), h.get("windgust"))))
        res[prod] = E.block(P, E.cem_table("6.0")); print(prod, len(P))
    if not res:
        sys.exit("no Visual Crossing data fetched (credential boundary)")
    json.dump(res, open(outp, "w"), indent=1); print("wrote", outp)


if __name__ == "__main__":
    {"fetch": lambda: fetch("--datasets" in sys.argv), "eval": lambda: eval_(sys.argv[2])}[sys.argv[1]]()
