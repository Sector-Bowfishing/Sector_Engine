"""Hourly hydrology inputs for a lake with a hydrologic arm graph
(Clarity Fusion Stage 1 item 3, and the Stage 2 history).

Each run, for the hour T = now - 2 h (MRMS Pass 2 is gauge-corrected with
~2 h latency):

  rain    basin-mean rain over each arm's drainage (catchment_rain weights):
          the MRMS Pass 2 1/6/12/24/48/72 h accumulations valid at T, the
          current storm (from the hourly record: back to 6 dry hours), and the
          7 days before the 72 h window. Arms with no resolvable drainage are
          "unavailable" -- never zero.
  flows   every arm: its own USGS gauge (measuredUSGS) when it has one, and
          the National Water Model analysis for its reach (modeledNWM) when it
          has one -- both kept, never merged, so the two can be compared.
  tva     Nickajack and Guntersville Dam: release, pool, tailwater (measuredTVA).
  lake    the reservoir's own surface ("_lakeSurface"): the main stem's direct rain.

Publishes (Cloud Storage BUCKET, or OUT_DIR locally):
  rain/<slug>/catchments.json          what the engine's CatchmentRainfallFeed reads
  hydrology/<slug>/hourly/<date>.json  one row per hour: rain1h per arm, flows, tva
  hydrology/<slug>/latest.json         the newest hour's summary

The first run backfills the hourly record (BACKFILL_HOURS, default 720 = 30 days).

usage: python hourly.py [--hour YYYY-MM-DDTHH]
env:   BUCKET or OUT_DIR; LAKE_SLUG (Guntersville_AL); BACKFILL_HOURS
"""
import os, sys, json, tempfile, argparse, datetime as dt, urllib.request, time, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catchment_rain as C

SLUG = os.environ.get("LAKE_SLUG", "Guntersville_AL")
BACKFILL_HOURS = int(os.environ.get("BACKFILL_HOURS", "720"))
LATENCY_H = 2
NWPS = "https://api.water.noaa.gov/nwps/v1/reaches"
TVA = "https://www.tva.com/RestApi/observed-data-48-hours"


class Store:
    def __init__(self):
        self.bucket_name = os.environ.get("BUCKET")
        self.root = os.environ.get("OUT_DIR", "out")
        if self.bucket_name:
            from google.cloud import storage
            self.bucket = storage.Client().bucket(self.bucket_name)

    def read_json(self, key):
        try:
            if self.bucket_name:
                return json.loads(self.bucket.blob(key).download_as_bytes())
            return json.load(open(os.path.join(self.root, key)))
        except Exception:
            return None

    def write_json(self, key, obj, cache="public, max-age=300"):
        data = json.dumps(obj, separators=(",", ":")).encode()
        if self.bucket_name:
            b = self.bucket.blob(key); b.cache_control = cache
            b.upload_from_string(data, content_type="application/json")
        else:
            path = os.path.join(self.root, key); os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").write(data)


def get_json(url, headers=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "sector-hydrology/1.0", **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def hourly_rain(weights, t, tmp):
    """Basin-mean rain in the hour ending at t, per arm (None where missing)."""
    p = C.fetch(C.PRODUCTS[1], t, tmp)
    if p is None:
        return None
    try:
        return {a: (None if v is None else round(v, 4)) for a, v in C.basin_means(p, weights).items()}
    finally:
        os.remove(p)


def usgs_latest(site):
    d = get_json(f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd=00060&period=PT3H")
    try:
        v = d["value"]["timeSeries"][0]["values"][0]["value"][-1]
        cfs = float(v["value"])
        return {"cfs": cfs, "at": v["dateTime"], "site": site} if cfs >= 0 else None   # -999999 = no value
    except Exception:
        return None


def nwm_latest(reach):
    d = get_json(f"{NWPS}/{reach}/streamflow")
    try:
        pts = [p for p in d["analysisAssimilation"]["series"]["data"] if p.get("flow") is not None and p["flow"] >= 0]
        last = pts[-1]          # NWPS marks a missing value -9999
        return {"cfs": float(last["flow"]), "validTime": last["validTime"], "reach": reach}
    except Exception:
        return None


def tva_latest(dam):
    d = get_json(f"{TVA}/{dam}")
    try:
        x = d[-1]
        num = lambda s: float(s.replace(",", "")) if s not in (None, "", "N/A") else None
        return {"releaseCfs": num(x.get("AverageHourlyDischarge")), "poolFt": num(x.get("ReservoirElevation")),
                "tailwaterFt": num(x.get("TailwaterElevation")), "day": x["Day"], "time": x["Time"]}
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--hour", default=None); a = ap.parse_args()
    store = Store()
    W = json.load(open(os.path.join(HERE, "mrms_weights.json")))
    graph = json.load(open(os.path.join(HERE, "hydrology.json")))
    weights = {k: v for k, v in W["arms"].items() if v["cells"]}
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    T = dt.datetime.strptime(a.hour, "%Y-%m-%dT%H") if a.hour else now - dt.timedelta(hours=LATENCY_H)
    tmp = tempfile.mkdtemp()
    print(f"hydrology hourly for {SLUG} at {T:%Y-%m-%dT%H}Z", flush=True)

    # ── the hourly record: fill every missing hour back to BACKFILL_HOURS
    def day_key(t): return f"hydrology/{SLUG}/hourly/{t:%Y-%m-%d}.json"
    days = {}
    def day(t):
        k = day_key(t)
        if k not in days:
            days[k] = store.read_json(k) or {"lake": SLUG, "rows": {}}
        return days[k]
    missing = []
    for h in range(BACKFILL_HOURS):
        t = T - dt.timedelta(hours=h)
        r = day(t)["rows"].get(f"{t:%Y-%m-%dT%H}")
        # an hour read before a catchment was added is refilled for it
        if not r or r.get("rain1h") is None or any(k not in r["rain1h"] for k in weights):
            missing.append(t)
    print(f"  {len(missing)} hours of rain to fill", flush=True)
    with cf.ThreadPoolExecutor(4) as ex:
        for t, rr in zip(missing, ex.map(lambda t: hourly_rain(weights, t, tmp), missing)):
            row = day(t)["rows"].setdefault(f"{t:%Y-%m-%dT%H}", {})
            row["rain1h"] = rr
    # ── flows and TVA as they read now, filed under the hour they were read
    # (rain is filed under T; the record only has what was live at the time)
    arms = graph["arms"]
    row = day(now)["rows"].setdefault(f"{now:%Y-%m-%dT%H}", {})
    def flow(arm):
        out = {}
        if arm.get("usgsDischargeSite"):
            out["usgs"] = usgs_latest(arm["usgsDischargeSite"])
        if arm.get("nwmFeatureId"):
            out["nwm"] = nwm_latest(arm["nwmFeatureId"])
        return arm["id"], out
    with cf.ThreadPoolExecutor(8) as ex:
        row["flows"] = dict(ex.map(flow, arms))
    row["tva"] = {d["tva"]: tva_latest(d["tva"]) for d in (graph["mainStem"]["upstreamDam"], graph["mainStem"]["downstreamDam"])}
    row["recordedAt"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for k, v in days.items():
        store.write_json(k, v, cache="public, max-age=300")

    # ── the rain windows at T (accumulation products), storm and antecedent
    res = {aid: {"basis": v["basis"], "drainageKm2": v.get("drainageKm2")} for aid, v in W["arms"].items()}
    for hours, prod in C.PRODUCTS.items():
        p = C.fetch(prod, T, tmp)
        if p is None:
            continue
        for aid, m in C.basin_means(p, weights).items():
            res[aid][f"last{hours}hIn"] = None if m is None else round(m, 3)
        os.remove(p)
    ante = {aid: 0.0 for aid in weights}; ok = True
    for back, prod in ((72, C.PRODUCTS[72]), (144, C.PRODUCTS[72]), (216, C.PRODUCTS[24])):
        p = C.fetch(prod, T - dt.timedelta(hours=back), tmp)
        if p is None:
            ok = False; break
        for aid, m in C.basin_means(p, weights).items():
            ante[aid] = None if (m is None or ante[aid] is None) else ante[aid] + m
        os.remove(p)
    for aid in weights:
        res[aid]["antecedent7dBeforeWindowIn"] = round(ante[aid], 3) if ok and ante[aid] is not None else None
    # current storm from the hourly record
    for aid in weights:
        total, dry, known = 0.0, 0, True
        for h in range(C.MAX_STORM_HOURS):
            t = T - dt.timedelta(hours=h)
            rr = (day(t)["rows"].get(f"{t:%Y-%m-%dT%H}") or {}).get("rain1h")
            if rr is None or rr.get(aid) is None:
                known = False; break
            v = rr[aid]
            if v < C.DRY_IN:
                dry += 1
                if dry >= C.DRY_HOURS:
                    break
            else:
                dry = 0; total += v
        res[aid]["currentStormIn"] = round(total, 3) if known else None
    feed = {"validTime": f"{T:%Y-%m-%dT%H}:00:00Z", "source": "NOAA MRMS MultiSensor QPE Pass 2 (s3://noaa-mrms-pds)",
            "arms": res}
    store.write_json(f"rain/{SLUG}/catchments.json", feed)
    store.write_json(f"hydrology/{SLUG}/latest.json", {"lake": SLUG, "hour": f"{T:%Y-%m-%dT%H}",
                                                        "rainFeed": f"rain/{SLUG}/catchments.json",
                                                        "hourlyRecord": day_key(T)})
    print("  published", flush=True)


if __name__ == "__main__":
    main()
