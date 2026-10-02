"""Fresh Guntersville observations -> the read-out input CSV for stage6/extract.py (frozen, unchanged).

  python build_observations.py --reports export1.json [export2.json ...] \
      --agency wqp_secchi.csv --stations wqp_stations.csv [--chl wqp_chl.csv] [--turb wqp_turb.csv] \
      --out fresh_obs.csv
  python ../../stage6/extract.py fresh_obs.csv fresh_readouts.csv --max-dt 1

Only observations made AFTER the freeze (../FREEZE.json) are admitted. Stage 8's seven 2026 agency
records (stage8/g2026_secchi.csv: fetched before this pre-registration; dates seen, values never read)
are excluded by organisation + site + date. Field reports keep their provenance: tier is decided from
the report's own answers, never upgraded.
"""
import argparse, csv, json, os, collections, datetime as dt
import regions

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(os.path.dirname(HERE))
FREEZE = json.load(open(os.path.join(os.path.dirname(HERE), "FREEZE.json")))["frozenAtUTC"]
FT = 3.28084
UNITS = {"m": FT, "ft": 1.0, "in": 1 / 12.0, "cm": FT / 100.0}
COLS = ["id", "lat", "lon", "date", "source", "tier", "truth_ft", "band_low", "band_high", "site", "kind", "arm", "zone",
        "bottomVisible", "depthFt", "vegetationPresent", "waterColorNotes", "measuredWithSecchiDisk", "chl", "turb"]


def tier(r):
    if r.get("underLights"):
        return "night"
    if r.get("visibilityFt") is None:
        return "bandDay"
    return "secchiDisk" if r.get("measuredWithSecchiDisk") is True else "visualDay"


def reports(paths):
    out = []
    for p in paths:
        for r in json.load(open(p)):
            if r.get("source") != "fieldReport" or r.get("lakeId") != "Guntersville|AL":
                continue
            if r.get("lat") is None or r.get("lon") is None or r["observedAt"] < FREEZE:
                continue
            w = regions.where(r["lat"], r["lon"])
            if w["kind"] == "offLake":
                continue
            rr, cc = regions.cell(r["lat"], r["lon"])
            out.append({"id": "fr-" + r["id"], "lat": r["lat"], "lon": r["lon"], "date": r["observedAt"][:10],
                        "source": "fieldReport", "tier": tier(r), "truth_ft": r.get("visibilityFt"),
                        "band_low": r.get("bandLowFt"), "band_high": r.get("bandHighFt"),
                        "site": f"cell{rr}_{cc}", "kind": w["kind"], "arm": w["arm"], "zone": w["zone"],
                        "bottomVisible": r.get("bottomVisible"), "depthFt": r.get("depthFt"),
                        "vegetationPresent": r.get("vegetationPresent"), "waterColorNotes": r.get("waterColorNotes"),
                        "measuredWithSecchiDisk": r.get("measuredWithSecchiDisk")})
    return out


def wqp_by_site_day(path):
    d = collections.defaultdict(list)
    for r in csv.DictReader(open(path)):
        try:
            d[(r["MonitoringLocationIdentifier"], r["ActivityStartDate"])].append(float(r["ResultMeasureValue"]))
        except (ValueError, KeyError):
            pass
    return {k: sorted(v)[len(v) // 2] for k, v in d.items()}


def agency(path, stations, chl_path=None, turb_path=None):
    excl = {(r["OrganizationIdentifier"], r["MonitoringLocationIdentifier"], r["ActivityStartDate"])
            for r in csv.DictReader(open(os.path.join(S, "stage8", "g2026_secchi.csv")))}
    loc = {r["MonitoringLocationIdentifier"]: (float(r["LatitudeMeasure"]), float(r["LongitudeMeasure"]))
           for r in csv.DictReader(open(stations)) if r.get("LatitudeMeasure")}
    chl = wqp_by_site_day(chl_path) if chl_path else {}
    turb = wqp_by_site_day(turb_path) if turb_path else {}
    freeze_day = FREEZE[:10]
    out = []
    for r in csv.DictReader(open(path)):
        if r.get("CharacteristicName") != "Depth, Secchi disk depth":
            continue
        site, day, org = r["MonitoringLocationIdentifier"], r["ActivityStartDate"], r["OrganizationIdentifier"]
        if day < "2026-01-01" or (org, site, day) in excl or site not in loc:
            continue
        # 2026 records dated before the freeze are admitted only if published after it (never fetched before)
        u = (r.get("ResultMeasure/MeasureUnitCode") or "").strip().lower()
        try:
            v = float(r["ResultMeasureValue"]) * UNITS[u]
        except (ValueError, KeyError):
            continue
        lat, lon = loc[site]
        w = regions.where(lat, lon)
        if w["kind"] == "offLake":
            continue
        out.append({"id": f"ag-{org}-{site}-{day}", "lat": lat, "lon": lon, "date": day, "source": "agency",
                    "tier": "agencySecchi", "truth_ft": round(v, 3), "site": site, "kind": w["kind"], "arm": w["arm"],
                    "zone": w["zone"], "chl": chl.get((site, day)), "turb": turb.get((site, day)),
                    "preFreezeDate": day < freeze_day})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", nargs="*", default=[]); ap.add_argument("--agency"); ap.add_argument("--stations")
    ap.add_argument("--chl"); ap.add_argument("--turb"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = reports(a.reports) + (agency(a.agency, a.stations, a.chl, a.turb) if a.agency else [])
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS + ["preFreezeDate"], extrasaction="ignore"); w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"{len(rows)} observations -> {a.out}", collections.Counter(r["tier"] for r in rows))
