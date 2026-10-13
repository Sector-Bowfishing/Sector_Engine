#!/usr/bin/env python3
"""Lake Brain binding review pack generator (adoption work package A1).

Builds the human review pack Michael uses to accept or reject machine-verified Lake Brain level-source bindings:
  * binding_review_sample.{html,csv}   stratified acceptance sample (~60 rows) of the STRICT, eligible set
  * binding_review_flagged57.{html,csv} the 57 wave-1 FLAGGED rows, full review (no sampling)
  * held_back_coordinate_flags.csv     strict rows held back because the directory coordinate is flagged
  * strict_population.csv              every eligible strict row with its stratum and sample flag (ingestion input)
  * pack_manifest.json                 counts, strata, allocation, seed, input hashes
  * START HERE - README.md

Strict set = binding-review-v1 as pre-registered: waves w1 and w2-v1 of verified_bindings_v2.csv with status VERIFIED or
VERIFIED_CORROBORATED, minus (a) Clinton Lake|IL (relies on a v1.1 rule), (b) lakes whose only source is an undocumented
operator web endpoint, (c) any post-hoc promotion (the wave-1 row must itself be VERIFIED / VERIFIED_CORROBORATED in the
wave-1 table: Red Lake|MN was FLAGGED in wave 1 and promoted later, so it is NOT strict). Lakes whose directory coordinate is
flagged identity_risk / off_water are HELD BACK (not promoted). v1.1 extensions, R7h/VERIFIED_ENVELOPE are never used.

Research data lives outside Git; see --help for the paths. Only public-derived data (gauge ids, levels, public URLs) is written.
Nothing here marks any binding REVIEWED.
"""
import argparse
import collections
import csv
import datetime as dt
import glob
import hashlib
import json
import math
import os
import random
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from review_stats import upper_bound  # noqa: E402
import held_lakes  # noqa: E402

CRITERIA = "binding-review-v1"
DEFAULT_SEED = 20261013
TARGET_N = 60
SNAPSHOT_DATE = "2026-10-13"
STRICT_STATUSES = ("VERIFIED", "VERIFIED_CORROBORATED")
STRICT_WAVES = ("w1", "w2-v1")
EXCLUDED_LAKES = {"Clinton Lake|IL": "relies on the v1.1 rule R8c (not binding-review-v1)"}
UNDOCUMENTED = {"nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake", "aep", "eccc", "mncsg"}
HELD_FLAGS = ("identity_risk", "off_water")
HELD_SERIES_REASON = held_lakes.SERIES_MISMATCH_REASON
HELD_SERIES = set(held_lakes.SERIES_MISMATCH)
ORIGIN = {"usgs": "usgs", "cwms": "usace", "a2w": "usace", "rise": "usbr", "tva": "tva", "coops": "noaa"}

DEFAULT_RESEARCH_DOCS = "/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain"
DEFAULT_DATA = os.environ.get("LB_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
DEFAULT_OUT = "/Users/mcather/Desktop/Sector Handoffs/Sector Engine/Lake Brain Binding Review"

PROVIDER_PLAIN = {
    "a2w": "USACE Access2Water",
    "cwms": "USACE CWMS data service",
    "cwms-saw": "USACE CWMS data service (Wilmington district)",
    "rise": "US Bureau of Reclamation RISE",
    "tva": "TVA lake-level feed",
    "usgs": "USGS water gauge",
    "nwps": "NOAA/NWS water gauge (NWPS)",
    "sjrwmd": "St. Johns River Water Management District",
    "nhdes": "NH Dept. of Environmental Services dam bureau",
    "coops": "NOAA CO-OPS water-level station",
    "twdb": "Texas Water Development Board",
}
CAP_PLAIN = {
    "DIRECT_OPERATOR_POOL": "the dam operator's own pool-level feed",
    "DIRECT_LAKE_GAUGE": "a gauge on or at the lake (not the operator's pool feed)",
}
RULE_NAMES = {
    "R1": "Position", "R2": "Identity", "R3": "Not a trap", "R4": "State", "R5": "Unique",
    "R6": "Live", "R7": "Level", "R8": "Datum", "R9": "Agreement",
}
RIVERISH = re.compile(r"\b(river|creek|brook|outlet|tailwater|tailrace|below|downstream|canal|diversion|inlet)\b", re.I)


# --------------------------------------------------------------------------------------------- helpers
def fnum(x):
    try:
        if x is None or x == "":
            return None
        v = float(x)
        return None if math.isnan(v) else v
    except Exception:
        return None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fmt(v, nd=2, unit=""):
    return "n/a" if v is None else f"{v:,.{nd}f}{unit}"


def station_office_and_loc(row):
    """(office, location) for CWMS-style rows."""
    st = row["station"]
    return (st.split(":")[0], st.split(":", 1)[1]) if ":" in st else (st, row.get("loc") or "")


# --------------------------------------------------------------------------------------------- inputs
class Inputs:
    def __init__(self, research_docs, data_dir):
        self.research_docs, self.data_dir = research_docs, data_dir
        self.v2_path = os.path.join(research_docs, "data", "verified_bindings_v2.csv")
        self.full_path = os.path.join(data_dir, "binding2", "verified_v2_full.csv")
        self.w1_path = os.path.join(data_dir, "binding", "verified.csv")
        self.cand_path = os.path.join(data_dir, "binding", "candidates.csv")
        self.nid_path = os.path.join(data_dir, "binding", "nid_links.csv")
        self.dir_path = os.path.join(data_dir, "directory_lakes_2026-10-13.json")
        self.geo_path = os.path.join(data_dir, "geometry", "lake_geometry_flags.csv")
        self.probe2_path = os.path.join(data_dir, "binding2", "probe_results_v2.json")
        self.item2loc_path = os.path.join(data_dir, "binding", "raw", "rise", "item2loc.json")
        self.cj_glob = os.path.join(data_dir, "binding2", "cand", "*.jsonl")
        for p in (self.v2_path, self.full_path, self.w1_path, self.cand_path, self.nid_path, self.dir_path, self.geo_path):
            if not os.path.exists(p):
                raise SystemExit(f"missing input: {p}")
        self.v2 = read_csv(self.v2_path)
        self.full = {r["lakeId"]: r for r in read_csv(self.full_path)}
        self.w1 = {r["lakeId"]: r for r in read_csv(self.w1_path)}
        self.nid = {r["lakeId"]: r for r in read_csv(self.nid_path)}
        self.directory = {x["id"]: x for x in json.load(open(self.dir_path))["lakes"]}
        self.geo = {r["id"]: r for r in read_csv(self.geo_path)}
        self.cand_rows = read_csv(self.cand_path)
        self.cand_by_lake = collections.defaultdict(list)
        for r in self.cand_rows:
            self.cand_by_lake[r["lakeId"]].append(r)
        self.cj_by_lake = collections.defaultdict(list)
        for p in sorted(glob.glob(self.cj_glob)):
            for ln in open(p):
                ln = ln.strip()
                if ln:
                    c = json.loads(ln)
                    c["_file"] = os.path.basename(p)
                    self.cj_by_lake[c["lakeId"]].append(c)
        self.probe2 = json.load(open(self.probe2_path)) if os.path.exists(self.probe2_path) else {}
        self.item2loc = json.load(open(self.item2loc_path)) if os.path.exists(self.item2loc_path) else {}

    def hashes(self):
        out = {}
        for name in ("v2_path", "full_path", "w1_path", "cand_path", "nid_path", "dir_path", "geo_path"):
            p = getattr(self, name)
            out[os.path.basename(p)] = sha256_file(p)
        return out


# --------------------------------------------------------------------------------------------- selection
def select_strict(inp):
    """Return (eligible, held, excluded, held_series). held = coordinate-flagged strict rows; held_series = strict rows with a series/datum mismatch;
    a lake can be in both. Neither group is eligible. excluded carries the reason."""
    eligible, held, excluded, held_series = [], [], [], []
    for r in inp.v2:
        if r["wave"] not in STRICT_WAVES or r["binding_status"] not in STRICT_STATUSES:
            continue
        lid = r["lake_id"]
        reason = None
        w1 = inp.w1.get(lid)
        if lid in EXCLUDED_LAKES:
            reason = "v1.1-dependent row: " + EXCLUDED_LAKES[lid]
        elif r["provider"] in UNDOCUMENTED:
            reason = "only source is an undocumented operator web endpoint (" + r["provider"] + ")"
        elif r["wave"] == "w1" and (w1 is None or w1["bindingStatus"] not in STRICT_STATUSES):
            reason = f"post-hoc promotion: wave-1 status was {w1['bindingStatus'] if w1 else 'missing'}, later waves promoted it"
        elif "v1.1" in (r.get("checks_passed") or ""):
            reason = "row carries a v1.1 rule tag"
        if reason:
            excluded.append(dict(lake_id=lid, provider=r["provider"], wave=r["wave"], reason=reason))
            continue
        g = inp.geo.get(lid, {})
        pf = (g.get("point_flag") or "").strip()
        rec = dict(v2=r, point_flag=pf)
        if lid in HELD_SERIES:
            held_series.append(rec)
        if pf in HELD_FLAGS:
            held.append(rec)
        if pf not in HELD_FLAGS and lid not in HELD_SERIES:
            eligible.append(rec)
    key = lambda x: x["v2"]["lake_id"]
    eligible.sort(key=key)
    held.sort(key=key)
    held_series.sort(key=key)
    return eligible, held, excluded, held_series


def stratum_of(rec):
    return f"{rec['v2']['provider']} | {rec['v2']['capability_class']}"


def allocate(strata_sizes, target):
    """Proportional allocation with: all rows of strata with <= 3 rows; >= 2 rows from every larger stratum; total == target
    (largest-remainder rounding, then trimming the largest strata if the minimums overshoot)."""
    alloc = {}
    big = {}
    for s, n in strata_sizes.items():
        if n <= 3:
            alloc[s] = n
        else:
            big[s] = n
    fixed = sum(alloc.values())
    remaining = target - fixed
    tot_big = sum(big.values())
    raw = {s: remaining * n / tot_big for s, n in big.items()}
    base = {s: max(2, min(big[s], int(math.floor(raw[s])))) for s in big}
    # distribute / trim to hit the total
    def total():
        return sum(base.values())
    rem = sorted(big, key=lambda s: (-(raw[s] - math.floor(raw[s])), s))
    i = 0
    while total() < remaining:
        s = rem[i % len(rem)]
        if base[s] < big[s]:
            base[s] += 1
        i += 1
        if i > 10000:
            break
    while total() > remaining:
        cand = [s for s in big if base[s] > 2]
        s = max(cand, key=lambda s: (base[s] - raw[s], big[s], s))
        base[s] -= 1
    alloc.update(base)
    return alloc


def draw_sample(eligible, seed, target):
    strata = collections.defaultdict(list)
    for rec in eligible:
        strata[stratum_of(rec)].append(rec)
    sizes = {s: len(v) for s, v in strata.items()}
    alloc = allocate(sizes, target)
    rng = random.Random(seed)
    picked = {}
    for s in sorted(strata):
        rows = sorted(strata[s], key=lambda x: x["v2"]["lake_id"])
        k = alloc[s]
        sel = rows if k >= len(rows) else rng.sample(rows, k)
        for rec in sel:
            picked[rec["v2"]["lake_id"]] = s
    return strata, sizes, alloc, picked


# --------------------------------------------------------------------------------------------- observation lookup
def _norm_prov(p):
    return {"usgs2": "usgs", "usgs-d": "usgs"}.get(p, p)


def find_observation(inp, lake_id, prov, station, series, med):
    """Locate the probe record (last value, observation time, station coordinates) behind a chosen binding.
    Matches on lake + provider + station + series, and on the stored 30-day median equal to the table's median."""
    recs = []
    for r in inp.cand_by_lake.get(lake_id, []):
        recs.append(dict(src="candidates.csv", prov=r["prov"], station=r["station"], series=r["series"], loc=r.get("loc", ""),
                         lastFt=fnum(r["lastFt"]), medFt=fnum(r["medFt"]), lastObs=r["lastObs"], ageH=fnum(r["ageH"]),
                         lat=fnum(r["lat"]), lon=fnum(r["lon"]), stationName=r["stationName"], family=r["family"], status=r["status"],
                         corr=r.get("corroboratedBy", "")))
    # wave-2 USGS re-probe (probe-parameter bug fix): a wave-1 USGS candidate recorded as gage height (00065, STAGE_ONLY) may have a
    # live absolute-elevation parameter; those re-probed series are the corroborators for Barren River, Cross Lake, Bistineau, Ashtabula, Darling.
    for r in inp.cand_by_lake.get(lake_id, []):
        pr0 = inp.probe2.get(f"usgs|{r['station']}") if r["prov"] == "usgs" else None
        if pr0 and pr0.get("reprobed") and pr0.get("family") == "elev" and (pr0.get("stats") or {}).get("last_ft") is not None and str(pr0.get("param")) != str(r["series"]):
            st0 = pr0["stats"]
            recs.append(dict(src="reprobe", prov="usgs", station=r["station"], series=str(pr0["param"]), loc="", lastFt=fnum(st0.get("last_ft")), medFt=fnum(st0.get("med_ft")),
                             lastObs=st0.get("last_t"), ageH=fnum(st0.get("age_h")), lat=fnum(r["lat"]), lon=fnum(r["lon"]), stationName=r["stationName"], family="elev",
                             status="VERIFIED" if r["status"] in ("STAGE_ONLY", "VERIFIED", "VERIFIED_CORROBORATED") else r["status"], corr=""))
    for c in inp.cj_by_lake.get(lake_id, []):
        recs.append(dict(src="cand/" + c["_file"], prov=_norm_prov(c["prov"]), station=str(c["station"]), series=str(c.get("series")), loc="",
                         lastFt=fnum(c.get("lastFt")), medFt=fnum(c.get("medFt")), lastObs=c.get("lastObs"), ageH=fnum(c.get("ageH")),
                         lat=fnum(c.get("lat")), lon=fnum(c.get("lon")), stationName=c.get("stationName"), family=c.get("family"),
                         pageUrl=c.get("pageUrl"), apiUrl=c.get("apiUrl")))
    pk = f"{prov}|{station}"
    pr = inp.probe2.get(pk)
    if pr and (pr.get("stats") or {}).get("last_ft") is not None and str(pr.get("param") or pr.get("series")) == str(series):
        st = pr["stats"]
        recs.append(dict(src="probe_results_v2.json", prov=prov, station=station, series=str(series), loc="", lastFt=fnum(st.get("last_ft")),
                         medFt=fnum(st.get("med_ft")), lastObs=st.get("last_t"), ageH=fnum(st.get("age_h")), lat=None, lon=None,
                         stationName=pr.get("name"), family=pr.get("family")))

    def match(rec, need_series, need_med):
        if _norm_prov(rec["prov"]) != _norm_prov(prov) or str(rec["station"]) != str(station):
            return False
        if need_series and str(rec["series"]) != str(series):
            return False
        if need_med and (rec["medFt"] is None or med is None or abs(rec["medFt"] - med) > 0.02):
            return False
        return True
    for need_series, need_med in ((True, True), (False, True), (True, False)):
        hit = [r for r in recs if match(r, need_series, need_med)]
        # prefer records with a last value
        hit.sort(key=lambda r: (r["lastFt"] is None, r["src"] != "probe_results_v2.json"))
        if hit:
            best = dict(hit[0])
            best["tier"] = ("series+median" if need_series and need_med else "station+median" if need_med else "series only")
            coords = next(((r["lat"], r["lon"]) for r in hit + recs if r["lat"] is not None and _norm_prov(r["prov"]) == _norm_prov(prov) and str(r["station"]) == str(station)), (None, None))
            best["lat"], best["lon"] = coords
            return best, recs
    return None, recs


def find_corroborator(rec, chosen, recs, origin_names):
    """The independent-origin candidate behind corroboratedBy: another verified-class series of the lake, different origin,
    elevation family, 30-day-median-or-last-value gap <= 2 ft (the research R9 definition)."""
    out = None
    for y in recs:
        if y.get("src") not in ("candidates.csv", "reprobe") or y.get("status") not in ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED"):
            continue
        if y["prov"] not in ORIGIN or ORIGIN[y["prov"]] not in origin_names or y["family"] != "elev":
            continue
        if y["prov"] == chosen["prov"] and str(y["station"]) == str(chosen["station"]):
            continue
        if ORIGIN[y["prov"]] == ORIGIN.get(chosen["prov"]):
            continue
        gaps = [abs(a - b) for a, b in ((y["medFt"], chosen["medFt"]), (y["lastFt"], chosen["lastFt"])) if a is not None and b is not None]
        if not gaps or min(gaps) > 2.0:
            continue
        if out is None or min(gaps) < out[1]:
            out = (y, min(gaps))
    return out


def other_agreeing(recs, chosen, corr_station):
    """Other verified-class sources for the lake that agree within 2 ft but are NOT independent (relays / same origin)."""
    out = []
    seen = set()
    for y in recs:
        if y.get("src") not in ("candidates.csv", "reprobe") or y.get("status") not in ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED") or y["family"] != "elev":
            continue
        if (y["prov"], str(y["station"])) == (chosen["prov"], str(chosen["station"])) or (y["prov"], str(y["station"])) in seen:
            continue
        if corr_station and (y["prov"], str(y["station"])) == corr_station:
            continue
        gaps = [abs(a - b) for a, b in ((y["medFt"], chosen["medFt"]), (y["lastFt"], chosen["lastFt"])) if a is not None and b is not None]
        if gaps and min(gaps) <= 2.0:
            seen.add((y["prov"], str(y["station"])))
            out.append(dict(prov=y["prov"], station=y["station"], lastFt=y["lastFt"], name=y["stationName"]))
    return out


# --------------------------------------------------------------------------------------------- links
def source_links(inp, prov, station, series, loc, cj_hint=None, lat=None, lon=None):
    q = urllib.parse.quote
    links = []
    if prov == "usgs":
        links.append(("USGS station page (click to see the real gauge)", f"https://waterdata.usgs.gov/monitoring-location/{station}/"))
        links.append(("USGS data query (last 2 days, parameter " + str(series) + ")", f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={station}&parameterCd={series}&period=P2D"))
    elif prov in ("cwms", "cwms-saw"):
        office, _ = station_office_and_loc({"station": station, "loc": loc})
        links.append(("USACE CWMS data query (last 24 h, in feet)", f"https://cwms-data.usace.army.mil/cwms-data/timeseries?office={q(office)}&name={q(series)}&unit=EN"))
        links.append(("USACE water site (search for the project)", "https://water.usace.army.mil/"))
    elif prov == "a2w":
        district, code = station_office_and_loc({"station": station, "loc": loc})
        slug = q(code.lower())
        links.append(("Access2Water data query (project record, latest values)", f"https://water.usace.army.mil/cda/reporting/providers/{district.lower()}/locations/{slug}"))
        links.append(("Access2Water site page (opens the USACE water site; use the data query above if it does not land on the project)", f"https://water.usace.army.mil/overview/{district.lower()}/locations/{slug}"))
    elif prov == "rise":
        links.append(("USBR RISE data query (latest readings)", f"https://data.usbr.gov/rise/api/result?itemId={station}&order%5BdateTime%5D=DESC&itemsPerPage=3"))
        locid = inp.item2loc.get(str(station))
        if locid:
            links.append(("USBR RISE location record", f"https://data.usbr.gov/rise/api/location/{locid}"))
        links.append(("USBR RISE data portal", "https://data.usbr.gov/"))
    elif prov == "tva":
        links.append(("TVA data query (last 48 h)", f"https://www.tva.com/RestApi/observed-data-48-hours/{station}"))
    elif prov == "nwps":
        links.append(("NOAA water gauge page (click to see the real gauge)", f"https://water.noaa.gov/gauges/{station}"))
        links.append(("NOAA NWPS data query", f"https://api.water.noaa.gov/nwps/v1/gauges/{station}"))
    elif prov == "coops":
        links.append(("NOAA CO-OPS station page", f"https://tidesandcurrents.noaa.gov/stationhome.html?id={station}"))
    elif prov == "twdb":
        links.append(("Water Data for Texas reservoir page", f"https://www.waterdatafortexas.org/reservoirs/individual/{q(station.lower())}"))
    elif prov == "nhdes":
        links.append(("NH DES dam bureau data query", f"https://nhdes.rtiamanzi.org/api/timeseries/?location__code={station}&parameter__code=PELV"))
        links.append(("NH DES real-time platform", "https://nhdes.rtiamanzi.org/"))
    elif prov == "sjrwmd":
        links.append(("SJRWMD hydrologic data (search the station code " + station + ")", ((cj_hint or {}).get("pageUrl") or "https://mdp.sjrwmd.com/").split()[0]))
    if cj_hint and cj_hint.get("pageUrl") and prov not in ("sjrwmd", "nhdes"):
        links.append(("Provider page", cj_hint["pageUrl"].split()[0]))
    return [dict(l=a, u=b) for a, b in links]


def map_links(lat, lon, label):
    if lat is None or lon is None:
        return None
    return dict(l=label, u=f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=14/{lat}/{lon}")


# --------------------------------------------------------------------------------------------- row assembly
def rule_results(checks, r7class, corr_info, row_facts, fail_override=None):
    """R1..R9 as list of dicts {id,name,res,meaning}. res in PASS / FAIL / FLAG / n-a."""
    tokens = set(t.split("=")[0] for t in checks.split(";")[0].split(",") if t)
    d = row_facts
    def has(k):
        return k in tokens
    km = d["dist_km"]
    inside = d["dist_m"] <= 150
    rules = []
    if d["has_outline"]:
        r1 = f"The gauge is {km:.2f} km from the lake outline" + (" (inside it)" if d["dist_m"] == 0 else "") + ". Rule: within 1.5 km."
    else:
        r1 = f"The gauge is {km:.2f} km from the lake's centre point (no outline exists for this lake). Rule: within 3 km with a name match, or 25 km with a strong one."
    rules.append(("R1", has("R1"), r1))
    if d["name_sim"] >= 0.5:
        r2 = f"Gauge name and lake name are similar (similarity {d['name_sim']:.2f}; rule: 0.50 or more)."
    else:
        r2 = f"Names differ (similarity {d['name_sim']:.2f}) but the gauge sits inside the lake outline ({d['dist_m']:.0f} m) and is a lake/pool gauge. Identity rests on position, so check it."
    rules.append(("R2", has("R2"), r2))
    rules.append(("R3", has("R3"), "Not a trap: the name is not a tailwater / below-dam / river / well gauge and the series is a pool or forebay level (not a forecast or statistic)."))
    rules.append(("R4", has("R4"), f"The gauge is in the lake's state ({d['state']})."))
    rules.append(("R5", has("R5"), "No other lake with a clearly better name match claims this same gauge."))
    age = d["age_h"]
    rules.append(("R6", has("R6"), "Live: the last reading is " + ("n/a" if age is None else f"{age:.1f} h old") + " (rule: under 72 h for frequent feeds, 192 h for daily feeds)."))
    # R7
    delta = d["delta"]
    if r7class == "strong":
        r7res = "PASS"
        r7 = f"The level ({fmt(d['med'])} ft, 30-day median) is {fmt(delta)} ft vs the lake's full pool ({fmt(d['full_pool'])} ft). Rule: between -25 and +8 ft."
    else:
        r7res = "FLAG"
        r7 = (f"The level ({fmt(d['med'])} ft) is {fmt(delta)} ft vs the directory full pool ({fmt(d['full_pool'])} ft) - outside the normal window; "
              f"the machine kept it only as a '{r7class}' case (deep drawdown or an uncertain full-pool figure) needing a human.")
    rules.append(("R7", r7res, r7))
    rules.append(("R8", has("R8"), "Datum: the vertical reference (what 'zero' means for the level) is identified, so the number is feet above sea level."))
    if corr_info:
        r9res = "PASS"
        r9 = f"A second, independent agency ({corr_info['label']}) reads {fmt(corr_info['gap'])} ft different (rule: within 2 ft)."
    else:
        r9res = "n-a"
        r9 = "No second independent source exists for this lake, so there is nothing to compare (not a failure; it just means only one agency's number backs this)."
    rules.append(("R9", r9res, r9))
    out = []
    for rid, ok, meaning in rules:
        res = ok if isinstance(ok, str) else ("PASS" if ok else "FAIL")
        out.append(dict(id=rid, name=RULE_NAMES[rid], res=res, meaning=meaning))
    return out



_STOP = {"lake", "reservoir", "res", "dam", "lk", "the", "of", "near", "at", "river", "creek", "pool", "and", "nr", "below", "above", "pond",
         "flowage", "impoundment", "state", "park", "project", "tailwater", "forebay", "headwater", "elev", "stage"}
_ABBR = {"fk": "fork", "ft": "fort", "mt": "mount", "mtn": "mountain", "cr": "creek", "ck": "creek", "rv": "river", "spr": "spring", "spg": "spring", "pt": "point", "l": "lake"}


def name_tokens(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    out = []
    for t in s.split():
        t = _ABBR.get(t, t)
        if t not in _STOP and len(t) > 1:
            out.append(t)
    return out


def name_contained(lake_name, station_name):
    """True when every significant word of the lake name appears in the station name (after expanding common abbreviations)."""
    a, b = set(name_tokens(lake_name)), set(name_tokens(station_name))
    return bool(a) and a <= b


def recommend(row, kind):
    """Conservative PASS / FLAG recommendation with reasons. Returns (rec, reasons, notes)."""
    hard, points, notes = [], [], []
    near_note = None
    corr = row["second"] is not None
    d_med, d_now = row["pool"]["diff"], row["pool"]["diffNow"]
    cands = [x for x in (d_med, d_now) if x is not None]
    delta = max(cands, key=abs) if cands else None          # worst case of "30-day median" and "now" vs the directory full pool
    both = (f"{fmt(d_now, 1)} ft now, {fmt(d_med, 1)} ft as a 30-day median" if d_now is not None and d_med is not None and abs(d_now - d_med) >= 1.0 else None)
    sim = row["nameMatch"]["sim"]
    sim_raw = sim
    contained = name_contained(row["nameMatch"]["lake"], row["nameMatch"]["station"])
    if contained and sim < 0.7:
        notes.append(f"the station name contains every word of the lake name (research similarity {sim:.2f} is lowered only by extra words or abbreviations)")
        sim = 0.7
    for rr in row["rules"]:
        if rr["res"] == "FAIL":
            hard.append(f"rule {rr['id']} ({rr['name']}) FAILED")
    if kind == "flagged":
        r7 = next(r for r in row["rules"] if r["id"] == "R7")
        near = delta is not None and abs(delta) <= 3.0
        strong_id = sim >= 0.6 and row["dist"]["m"] <= 500
        if near and strong_id:
            near_note = (f"the level is within {abs(delta):.1f} ft of the directory full pool and the name/position match is strong; the machine flagged it only because the "
                         "directory full-pool figure is uncertain and one agency backs it. A quick look at the gauge page should be enough")
        else:
            hard.append("level is {} ft vs the directory full pool ({}): outside the normal window, a human has to confirm this really is the lake's level (deep drawdown or uncertain full pool)".format(both or fmt(delta, 1), fmt(row["pool"]["ft"], 1)))
        if not strong_id:
            hard.append("name/position match is not strong")
    else:
        if sim < 0.5 and not corr:
            hard.append(f"names differ (similarity {sim:.2f}); identity rests on position/dam only, and no independent source backs it")
        if delta is not None and abs(delta) >= 10 and not corr:
            hard.append(f"level is {both or fmt(delta, 1) + ' ft'} from the directory full pool and no independent source confirms it (could be real drawdown, could be the wrong pool)")
        if delta is not None and delta > 3 and not corr:
            hard.append(f"level is {both or fmt(delta, 1) + ' ft'} ABOVE the directory full pool with no independent confirmation")
    # attention points (shared)
    if 0.5 <= sim < 0.7:
        points.append(f"only a partial name match (similarity {sim:.2f})")
    if row["dist"]["m"] > 300:
        points.append(f"gauge is {row['dist']['m'] / 1000:.2f} km from the lake outline")
    if RIVERISH.search(row["stationName"] or "") and not corr and row["provider"] != "nwps":
        points.append("station name sounds like a river/creek/outlet - confirm it measures the lake")
    if row["provider"] == "nwps" and not corr:
        points.append("NOAA/NWS gauge that relays another agency's number (not an independent check)")
    if row["history"]["cls"] in ("NONE", "LIMITED", "INSUFFICIENT") and not corr and kind != "flagged":
        points.append("short or no public history")
    if kind != "flagged" and delta is not None and 5 <= abs(delta) < 10 and not corr:
        points.append(f"level is {both or fmt(delta, 1) + ' ft'} from full pool")
    if row["level"]["ageH"] is not None and row["level"]["ageH"] > 24 and row["provider"] != "rise":   # RISE publishes with a documented ~2 day lag
        points.append(f"last reading is {row['level']['ageH']:.0f} h old")
    if row["pool"]["conf"] not in ("high", None, ""):
        points.append(f"directory full-pool confidence is '{row['pool']['conf']}'")
    if not row["dist"]["outline"]:
        points.append("lake has no outline polygon; distance measured to the centre point")
    if not corr:
        notes.append("single agency only (no independent second source)")
    rec = "FLAG" if (hard or len(points) >= 2) else "PASS"
    reasons = list(hard)
    if rec == "FLAG" and not hard:
        reasons.append("several smaller concerns together: " + "; ".join(points))
    elif points:
        notes.extend(points)
    if rec == "PASS" and kind == "flagged":
        reasons = [near_note or "no hard concern"]
    elif rec == "PASS":
        base = []
        if corr:
            base.append(f"an independent source agrees within {row['second']['diff']:.2f} ft")
        base.append((f"level is {both or fmt(delta, 1) + ' ft'} from full pool") if delta is not None else "no full-pool figure")
        base.append(f"name match {sim_raw:.2f}{' (all lake-name words appear in the station name)' if contained and sim_raw < 0.7 else ''}, gauge {row['dist']['m'] / 1000:.2f} km from the outline")
        reasons = ["all checks pass: " + "; ".join(base)]
    return rec, reasons, notes


def build_row(inp, rec, kind, seq):
    """Assemble one display/CSV row from a strict (kind='sample') or a wave-1 flagged (kind='flagged') record."""
    lid = rec["lake_id"]
    full = inp.full[lid]
    w1 = inp.w1[lid]
    d = inp.directory[lid]
    g = inp.geo.get(lid, {})
    src = w1 if kind == "flagged" else full          # flagged rows show the wave-1 binding that was flagged
    prov = src["provider"]
    station = src["station"]
    series = src["series"]
    loc = src.get("loc") or ""
    med = fnum(src["medFt"])
    obs, recs = find_observation(inp, lid, prov, station, series, med)
    if obs is None:
        raise SystemExit(f"no probe record found for {lid} {prov} {station} {series}")
    cj_hint = next((c for c in inp.cj_by_lake.get(lid, []) if _norm_prov(c["prov"]) == prov and str(c["station"]) == str(station)), None)
    stationName = src["stationName"]
    dist_m = float(src["distM"])
    name_sim = float(src["nameSim"])
    has_outline = (g.get("has_polygon") or "").strip().lower() == "true"
    full_pool = fnum(src["fullPoolFt"]) if "fullPoolFt" in src else fnum(d.get("fullPoolFt"))
    if full_pool is None:
        full_pool = fnum(d.get("fullPoolFt"))
    delta = fnum(src["deltaFullPoolFt"])
    checks = src["checks"]
    r7class = checks.split("R7=")[1].split(";")[0] if "R7=" in checks else "strong"
    # independent corroboration
    corr_info = None
    corr_names = set(x for x in (src.get("corroboratedBy") or "").split(",") if x)
    if kind == "sample" and corr_names:
        hit = find_corroborator(rec, obs, recs, corr_names)
        if hit:
            y, gap = hit
            diff_last = abs(y["lastFt"] - obs["lastFt"]) if (y["lastFt"] is not None and obs["lastFt"] is not None) else None
            diff_med = abs(y["medFt"] - obs["medFt"]) if (y["medFt"] is not None and obs["medFt"] is not None) else None
            ylabel = f"{PROVIDER_PLAIN.get(y['prov'], y['prov'])} {y['station']}"
            corr_info = dict(label=ylabel, gap=gap, prov=y["prov"], station=y["station"], name=y["stationName"], lastFt=y["lastFt"], medFt=y["medFt"],
                             lastObs=y["lastObs"], diff_last=diff_last, diff_med=diff_med, links=source_links(inp, y["prov"], y["station"], y["series"], y.get("loc", "")))
        else:
            raise SystemExit(f"corroborating source not reconstructable for {lid} ({corr_names})")
    other = other_agreeing(recs, obs, (corr_info["prov"], str(corr_info["station"])) if corr_info else None)
    # nid
    n = inp.nid.get(lid, {})
    nid_id = (src.get("nidId") or "").strip()
    nid_text = None
    nid_obj = None
    if nid_id:
        nid_obj = dict(id=nid_id, name=n.get("nidName"), score=fnum(n.get("nidScore")), distM=fnum(n.get("nidDistM")), linked=True)
    elif n.get("nidId"):
        nid_obj = dict(id=n["nidId"], name=n.get("nidName"), score=fnum(n.get("nidScore")), distM=fnum(n.get("nidDistM")), linked=False)
    hist_cls = src.get("historyClass") or ""
    years = int(float(src["completeYears"])) if src.get("completeYears") not in (None, "") else 0
    first = int(float(src["firstYear"])) if src.get("firstYear") not in (None, "") else None
    lat, lon = fnum(d.get("lat")), fnum(d.get("lon"))
    facts = dict(dist_km=dist_m / 1000.0, dist_m=dist_m, has_outline=has_outline, name_sim=name_sim, state=d["state"], age_h=obs["ageH"],
                 med=med, delta=delta, full_pool=full_pool)
    rules = rule_results(checks, r7class, corr_info, facts)
    row = dict(
        seq=seq, id=lid, name=d["name"], state=d["state"], kind=kind, stratum=f"{prov} | {src['capability']}", provider=prov,
        capability=src["capability"], capPlain=CAP_PLAIN.get(src["capability"], ""), operator=d.get("operatorName"),
        wave=full.get("wave", ""), sourceLabel=f"{PROVIDER_PLAIN.get(prov, prov)} \u2014 {stationName}",
        sourceId=f"{prov}: {station}" + (f" / {series}" if series and series != station else ""), station=str(station), series=str(series),
        stationName=stationName, links=source_links(inp, prov, str(station), str(series), loc, cj_hint),
        lake=dict(lat=lat, lon=lon, map=map_links(lat, lon, "Map: lake location")),
        gauge=dict(lat=obs.get("lat"), lon=obs.get("lon"), map=map_links(obs.get("lat"), obs.get("lon"), "Map: gauge location")),
        dist=dict(m=dist_m, km=round(dist_m / 1000.0, 3), outline=has_outline,
                  text=("inside the lake outline" if dist_m == 0 and has_outline else f"{dist_m / 1000.0:.3f} km from the lake outline" if has_outline else f"{dist_m / 1000.0:.3f} km from the lake centre point (no outline available)")),
        nameMatch=dict(lake=d["name"], station=stationName, sim=name_sim),
        level=dict(lastFt=obs["lastFt"], medFt=med, obsUtc=obs["lastObs"], ageH=obs["ageH"], snapshot=SNAPSHOT_DATE),
        pool=dict(ft=full_pool, conf=d.get("poolConfidence"), basis=d.get("poolBasis"), diff=delta,
                  diffNow=(round(obs["lastFt"] - full_pool, 3) if (obs["lastFt"] is not None and full_pool is not None) else None)),
        second=None, alsoAgrees=[f"{PROVIDER_PLAIN.get(o['prov'], o['prov'])} {o['station']} ({fmt(o['lastFt'])} ft; same measurement relayed, NOT independent)" for o in other],
        rules=rules, nid=nid_obj, history=dict(years=years, first=first, cls=hist_cls, series=src.get("histSeries") or ""),
        pointFlag=(g.get("point_flag") or "").strip() or "none", pointWhy=(g.get("why") or "").strip(),
        checks=checks, status=src["bindingStatus"], r7class=r7class,
    )
    if corr_info:
        row["second"] = dict(label=corr_info["label"], station=corr_info["station"], name=corr_info["name"], lastFt=corr_info["lastFt"], medFt=corr_info["medFt"],
                             lastObs=corr_info["lastObs"], diff=corr_info["diff_last"] if corr_info["diff_last"] is not None else corr_info["gap"],
                             diffMed=corr_info["diff_med"], gapUsed=corr_info["gap"], links=corr_info["links"])
    if kind == "flagged":
        row["postHoc"] = post_hoc(inp, lid, w1, full)
    rr, reasons, notes = recommend(row, kind)
    row["rec"], row["recReasons"], row["recNotes"] = rr, reasons, notes
    return row


def post_hoc(inp, lid, w1, full):
    """What later waves did to a wave-1 flagged lake. Information only - 'post-hoc, not counted'."""
    st = full["bindingStatus"]
    env = fnum(full.get("envelopeD99"))
    same = (full["provider"], full["station"]) == (w1["provider"], w1["station"])
    if st == "VERIFIED_ENVELOPE":
        outcome = "PROMOTED by the post-hoc R7h history-envelope rule"
        detail = ("The rule promotes a flagged series when its own 99th-percentile history sits within 8 ft of the directory full pool"
                  + (f" (here {env:+.2f} ft)" if env is not None else "") + ". It was written after wave-1 failures were seen and is not a second source. Under the review decision it does NOT count.")
    elif st == "VERIFIED_CORROBORATED":
        outcome = "PROMOTED later by an independent second source"
        detail = "A later wave found an independent agency's gauge within 2 ft. This is post-hoc and does NOT count here."
    elif st == "VERIFIED_FLAG":
        outcome = "STILL FLAGGED after wave 2"
        detail = "No later wave resolved it."
    else:
        outcome = f"Later status: {st}"
        detail = ""
    if not same:
        detail += f" Later waves also re-pointed the lake to {PROVIDER_PLAIN.get(full['provider'], full['provider'])} {full['station']} (not the source shown on this card)."
    l1 = inp.full[lid].get("layer1")
    return dict(label="post-hoc, not counted", outcome=outcome, detail=detail.strip(), laterStatus=st, laterProvider=full["provider"], laterStation=full["station"],
                changedSource=(not same), laterYears=full.get("completeYears"), layer1=l1)


# --------------------------------------------------------------------------------------------- outputs
CSV_FIELDS = [
    "review_id", "lake_id", "lake_name", "state", "stratum", "recommendation", "recommendation_reason", "attention_notes",
    "proposed_source", "source_id", "provider", "capability_class", "station_name",
    "distance_to_lake_outline_km", "outline_available", "spatial_match",
    "lake_name_vs_station_name_similarity",
    "current_level_ft", "observed_at_utc", "observation_age_hours", "median_30d_ft", "snapshot_date",
    "full_pool_ft", "full_pool_confidence", "level_minus_full_pool_ft", "median_30d_minus_full_pool_ft",
    "second_source", "second_source_level_ft", "second_source_difference_ft", "other_non_independent_agreeing_sources",
    "R1_position", "R2_identity", "R3_not_a_trap", "R4_state", "R5_unique", "R6_live", "R7_level", "R8_datum", "R9_agreement",
    "R1_meaning", "R2_meaning", "R3_meaning", "R4_meaning", "R5_meaning", "R6_meaning", "R7_meaning", "R8_meaning", "R9_meaning",
    "nid_dam_id", "nid_dam_name", "nid_link_note", "history_complete_years", "history_first_year", "history_class",
    "source_links", "lake_latitude", "lake_longitude", "lake_map_link", "gauge_latitude", "gauge_longitude", "gauge_map_link",
    "directory_coordinate_flag", "found_in_wave", "machine_status", "post_hoc_outcome", "post_hoc_detail",
]


def csv_row(row):
    rules = {r["id"]: r for r in row["rules"]}
    d = dict(
        review_id=row["id"], lake_id=row["id"], lake_name=row["name"], state=row["state"], stratum=row["stratum"], recommendation=row["rec"],
        recommendation_reason=" | ".join(row["recReasons"]), attention_notes=" | ".join(row["recNotes"]),
        proposed_source=row["sourceLabel"], source_id=row["sourceId"], provider=row["provider"], capability_class=row["capability"], station_name=row["stationName"],
        distance_to_lake_outline_km=row["dist"]["km"], outline_available="yes" if row["dist"]["outline"] else "no (measured to centre point)", spatial_match=row["dist"]["text"],
        current_level_ft=row["level"]["lastFt"], observed_at_utc=row["level"]["obsUtc"], observation_age_hours=row["level"]["ageH"], median_30d_ft=row["level"]["medFt"],
        snapshot_date=SNAPSHOT_DATE, full_pool_ft=row["pool"]["ft"], full_pool_confidence=row["pool"]["conf"], level_minus_full_pool_ft=row["pool"]["diffNow"], median_30d_minus_full_pool_ft=row["pool"]["diff"],
        other_non_independent_agreeing_sources=" | ".join(row["alsoAgrees"]),
        nid_dam_id=(row["nid"] or {}).get("id", ""), nid_dam_name=(row["nid"] or {}).get("name", ""),
        nid_link_note=("" if not row["nid"] else ("linked by the research (name+geometry)" if row["nid"]["linked"] else f"weak candidate only (match score {row['nid']['score']}); not used")),
        history_complete_years=row["history"]["years"], history_first_year=row["history"]["first"] or "", history_class=row["history"]["cls"],
        source_links=" | ".join(f"{l['l']}: {l['u']}" for l in row["links"]), lake_latitude=row["lake"]["lat"], lake_longitude=row["lake"]["lon"],
        lake_map_link=(row["lake"]["map"] or {}).get("u", ""), gauge_latitude=row["gauge"]["lat"] if row["gauge"]["lat"] is not None else "",
        gauge_longitude=row["gauge"]["lon"] if row["gauge"]["lon"] is not None else "", gauge_map_link=(row["gauge"]["map"] or {}).get("u", ""),
        directory_coordinate_flag=row["pointFlag"], found_in_wave=row["wave"], machine_status=row["status"],
    )
    d["lake_name_vs_station_name_similarity"] = f"{row['nameMatch']['sim']:.3f}"
    if row["second"]:
        s = row["second"]
        d["second_source"] = f"{s['label']} ({s['name']})"
        d["second_source_level_ft"] = s["lastFt"]
        d["second_source_difference_ft"] = round(s["diff"], 3) if s["diff"] is not None else ""
    else:
        d["second_source"] = "none (single agency)"
        d["second_source_level_ft"] = ""
        d["second_source_difference_ft"] = ""
    for k, (rid, nm) in {"R1_position": ("R1", ""), "R2_identity": ("R2", ""), "R3_not_a_trap": ("R3", ""), "R4_state": ("R4", ""), "R5_unique": ("R5", ""),
                         "R6_live": ("R6", ""), "R7_level": ("R7", ""), "R8_datum": ("R8", ""), "R9_agreement": ("R9", "")}.items():
        d[k] = rules[rid]["res"]
        d[f"{rid}_meaning"] = rules[rid]["meaning"]
    if row.get("postHoc"):
        d["post_hoc_outcome"] = "post-hoc, not counted: " + row["postHoc"]["outcome"]
        d["post_hoc_detail"] = row["postHoc"]["detail"]
    else:
        d["post_hoc_outcome"] = ""
        d["post_hoc_detail"] = ""
    return {k: d.get(k, "") for k in CSV_FIELDS}


def write_csv(path, rows, fields=None, rowfn=csv_row):
    fields = fields or CSV_FIELDS
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(rowfn(r) if rowfn else r)


def json_for_html(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_html(template_path, mode, pack_id, rows, meta):
    tpl = open(template_path, encoding="utf-8").read()
    payload = dict(mode=mode, packId=pack_id, rows=rows, meta=meta)
    title = "Lake Brain binding review - acceptance sample" if mode == "sample" else "Lake Brain binding review - the 57 flagged rows"
    return (tpl.replace("__TITLE__", title).replace("__MODE__", mode).replace("__PACK_ID__", pack_id).replace("__DATA_JSON__", json_for_html(payload)))


def pack_id_for(mode, ids, seed):
    h = hashlib.sha256((mode + "|" + str(seed) + "|" + ",".join(sorted(ids))).encode()).hexdigest()[:10]
    return f"LBR-{mode.upper()}-{h}"


# --------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--research-docs", default=DEFAULT_RESEARCH_DOCS, help="docs/research/lake-brain of the research branch checkout")
    ap.add_argument("--data-dir", default=DEFAULT_DATA, help="Sector_Research_Data/lake-brain (bulk data outside Git)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="pack output directory")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--target", type=int, default=TARGET_N)
    args = ap.parse_args(argv)

    inp = Inputs(args.research_docs, args.data_dir)
    eligible, held, excluded, held_series = select_strict(inp)
    strata, sizes, alloc, picked = draw_sample(eligible, args.seed, args.target)
    n_sample = len(picked)
    assert 58 <= n_sample <= 62, n_sample

    sample_rows = [build_row(inp, rec["v2"], "sample", i + 1) for i, rec in enumerate(sorted((r for r in eligible if r["v2"]["lake_id"] in picked), key=lambda r: (stratum_of(r), r["v2"]["lake_id"])))]
    for i, r in enumerate(sample_rows):
        r["seq"] = i + 1
    flagged_ids = sorted(lid for lid, r in inp.w1.items() if r["bindingStatus"] == "VERIFIED_FLAG")
    assert len(flagged_ids) == 57, len(flagged_ids)
    flagged_rows = [build_row(inp, dict(lake_id=lid), "flagged", i + 1) for i, lid in enumerate(flagged_ids)]

    os.makedirs(args.out, exist_ok=True)
    sample_pack = pack_id_for("sample", [r["id"] for r in sample_rows], args.seed)
    flagged_pack = pack_id_for("flagged", [r["id"] for r in flagged_rows], 0)
    sample_meta = dict(seed=args.seed, eligible=len(eligible), sampleSize=n_sample, acceptRule="Accept the batch when there are 1 or fewer errors (rejected rows) in the sample of %d." % n_sample,
                       maxErrors=1, strata={s: dict(size=sizes[s], sampled=alloc[s]) for s in sorted(sizes)}, snapshot=SNAPSHOT_DATE, criteria=CRITERIA)
    flagged_meta = dict(count=len(flagged_rows), snapshot=SNAPSHOT_DATE, criteria=CRITERIA)
    tpl = os.path.join(HERE, "review_template.html")
    open(os.path.join(args.out, "binding_review_sample.html"), "w", encoding="utf-8").write(render_html(tpl, "sample", sample_pack, sample_rows, sample_meta))
    open(os.path.join(args.out, "binding_review_flagged57.html"), "w", encoding="utf-8").write(render_html(tpl, "flagged", flagged_pack, flagged_rows, flagged_meta))
    write_csv(os.path.join(args.out, "binding_review_sample.csv"), sample_rows)
    write_csv(os.path.join(args.out, "binding_review_flagged57.csv"), flagged_rows)

    # held-back list
    held_fields = ["lake_id", "lake_name", "state", "directory_coordinate_flag", "why_flagged", "repair_hint", "provider", "capability_class", "source_id", "station_name", "found_in_wave", "status"]
    with open(os.path.join(args.out, "held_back_coordinate_flags.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=held_fields)
        w.writeheader()
        for rec in held:
            v = rec["v2"]
            g = inp.geo.get(v["lake_id"], {})
            w.writerow(dict(lake_id=v["lake_id"], lake_name=inp.directory[v["lake_id"]]["name"], state=inp.directory[v["lake_id"]]["state"],
                            directory_coordinate_flag=rec["point_flag"], why_flagged=g.get("why", ""), repair_hint=g.get("repair_hint", ""),
                            provider=v["provider"], capability_class=v["capability_class"], source_id=f"{v['provider']}: {v['station']}",
                            station_name=inp.full[v["lake_id"]]["stationName"], found_in_wave=v["wave"],
                            status="HELD - coordinate review pending"))
    # committed snapshot of every held id, read by the ingestion script as a second line of defence
    json.dump(dict(criteria=CRITERIA, snapshotDate=SNAPSHOT_DATE, note="generated by build_review_pack.py; never put these lakes in accepted_batch.json",
                   coordinateFlagged=sorted(r["v2"]["lake_id"] for r in held), seriesMismatch=sorted(r["v2"]["lake_id"] for r in held_series),
                   seriesMismatchReason=HELD_SERIES_REASON), open(held_lakes.SNAPSHOT_FILE, "w"), indent=1)
    # held-back (series/datum mismatch)
    ser_fields = ["lake_id", "lake_name", "state", "reason", "also_coordinate_flagged", "provider", "capability_class", "source_id", "station_name", "found_in_wave", "status"]
    with open(os.path.join(args.out, "held_back_series_mismatch.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=ser_fields)
        w.writeheader()
        for rec in held_series:
            v = rec["v2"]
            w.writerow(dict(lake_id=v["lake_id"], lake_name=inp.directory[v["lake_id"]]["name"], state=inp.directory[v["lake_id"]]["state"], reason=HELD_SERIES_REASON,
                            also_coordinate_flagged=rec["point_flag"] or "no", provider=v["provider"], capability_class=v["capability_class"],
                            source_id=f"{v['provider']}: {v['station']}", station_name=inp.full[v["lake_id"]]["stationName"], found_in_wave=v["wave"],
                            status="HELD - series/datum mismatch pending resolution"))
    # population file (ingestion input)
    with open(os.path.join(args.out, "strict_population.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["lake_id", "stratum", "in_sample", "provider", "capability_class", "found_in_wave"])
        for rec in eligible:
            v = rec["v2"]
            w.writerow([v["lake_id"], stratum_of(rec), "yes" if v["lake_id"] in picked else "no", v["provider"], v["capability_class"], v["wave"]])

    recs_s = collections.Counter(r["rec"] for r in sample_rows)
    recs_f = collections.Counter(r["rec"] for r in flagged_rows)
    manifest = dict(
        generatedBy="jobs/lake-brain/review/build_review_pack.py", criteria=CRITERIA, snapshotDate=SNAPSHOT_DATE, seed=args.seed, targetN=args.target,
        sampleSize=n_sample, samplePackId=sample_pack, flaggedPackId=flagged_pack,
        acceptRule=dict(maxErrors=1, sampleSize=n_sample, confidence=0.95, text="accept the batch when <= 1 error in the sample; any stratum with a reject is reviewed in full"),
        counts=dict(v2StrictBeforeExclusions=sum(1 for r in inp.v2 if r["wave"] in STRICT_WAVES and r["binding_status"] in STRICT_STATUSES),
                    excluded=len(excluded), heldBackCoordinateFlags=len(held), heldBackSeriesMismatch=len(held_series),
                    heldBackEither=len({r["v2"]["lake_id"] for r in held} | {r["v2"]["lake_id"] for r in held_series}), eligible=len(eligible), flaggedWave1=len(flagged_rows)),
        excluded=excluded, heldBack=[r["v2"]["lake_id"] for r in held], heldBackSeries=[r["v2"]["lake_id"] for r in held_series], heldSeriesReason=HELD_SERIES_REASON,
        heldByFlag=dict(collections.Counter(r["point_flag"] for r in held)),
        strata={s: dict(size=sizes[s], sampled=alloc[s]) for s in sorted(sizes)},
        recommendations=dict(sample=dict(recs_s), flagged=dict(recs_f)),
        sampleRecommendationByStratum={s: dict(collections.Counter(r["rec"] for r in sample_rows if r["stratum"] == s)) for s in sorted(sizes)},
        inputSha256=inp.hashes(),
        rules="Strict = binding-review-v1; no v1.1 extensions, no R7h/VERIFIED_ENVELOPE, no post-hoc promotions. Nothing is marked REVIEWED by this pack.",
    )
    json.dump(manifest, open(os.path.join(args.out, "pack_manifest.json"), "w"), indent=1)
    write_readme(args.out, manifest, sample_rows, flagged_rows, sizes, alloc, upper_bound)
    print(json.dumps(dict(eligible=len(eligible), held=len(held), excluded=len(excluded), sample=n_sample, rec_sample=dict(recs_s), rec_flagged=dict(recs_f)), indent=1))
    return manifest


def write_readme(out, m, sample_rows, flagged_rows, sizes, alloc, ub):
    c = m["counts"]
    bound = lambda k: f"{100 * ub(m['sampleSize'], k):.1f}%"
    lines = []
    A = lines.append
    A("# START HERE - Lake Brain binding review")
    A("")
    A("**What this is.** The computer has matched each of many lakes to a water-level gauge on the internet. Before the app is allowed to trust those matches, a person has to check them. You do not need to check all of them: you check a random sample, and the math tells you whether you can trust the rest.")
    A("")
    A("**The one question on every card:** *is this gauge really THIS lake's water level?* Not a river below the dam, not a different lake with a similar name, not a nonsense number.")
    A("")
    A("## What to do (about an hour for the sample)")
    A("1. Double-click `binding_review_sample.html` (it opens in Safari or Chrome; nothing is uploaded anywhere).")
    A(f"2. Go through the {m['sampleSize']} cards. For each one, click the gauge link (a real public web page), look at the gauge and the lake name, and press **Accept**, **Reject** or **Unsure**. Add a note if you like.")
    A("   - **Accept** = this gauge is this lake's water level and the number looks right.")
    A("   - **Reject** = wrong gauge, wrong lake, or the level makes no sense. One reject is allowed (that group is then reviewed in full); two or more means the batch is not accepted and every group with a reject is reviewed in full.")
    A("   - **Unsure** = you cannot tell. Unsure rows must be settled one way or the other before the batch can be accepted.")
    A("3. The bar at the top counts your progress and shows the verdict: green once all rows are reviewed with at most 1 reject.")
    A("4. Your answers are saved in your browser as you go; you can close the page and come back (use the same browser and the same file). Press **Download my review (CSV)** at the end and give that file to Claude.")
    A("5. Separately, `binding_review_flagged57.html` has the 57 lakes the computer was least sure about. These are reviewed one by one (no sampling): Accept or Reject each.")
    A("")
    A("## What is in this folder")
    A("| File | What it is |")
    A("|---|---|")
    A(f"| `binding_review_sample.html` | The review tool for the {m['sampleSize']}-row acceptance sample (double-click) |")
    A("| `binding_review_sample.csv` | The same rows as a spreadsheet |")
    A("| `binding_review_flagged57.html` | The review tool for the 57 flagged rows |")
    A("| `binding_review_flagged57.csv` | The same 57 rows as a spreadsheet |")
    A(f"| `held_back_coordinate_flags.csv` | {c['heldBackCoordinateFlags']} otherwise-eligible lakes marked 'HELD - coordinate review pending': the lake's map point in our directory looks wrong. They are NOT in the sample and must not be accepted until the coordinates are reviewed |")
    A(f"| `held_back_series_mismatch.csv` | {c['heldBackSeriesMismatch']} lakes held for a series/datum mismatch (history series differs from the live binding by more than 15 ft). Also NOT in the sample; must not be accepted until resolved |")
    A("| `strict_population.csv` | Every eligible lake, its group, and whether it is in the sample (used by the ingestion script) |")
    A("| `pack_manifest.json` | Counts, groups, random seed, and file fingerprints so the pack can be rebuilt exactly |")
    A("")
    A("## The numbers")
    A(f"- Machine-verified under the pre-registered rules (`{m['criteria']}`, waves w1 + w2-v1): **{c['v2StrictBeforeExclusions']}** rows.")
    A(f"- Excluded: **{c['excluded']}** (Clinton Lake IL relies on a later rule; 5 lakes whose only source is an undocumented operator web page; Red Lake MN, which was FLAGGED in wave 1 and only promoted afterwards).")
    A(f"- Held back for a coordinate problem (directory point flagged off-water or identity-risk): **{c['heldBackCoordinateFlags']}** ({', '.join(f'{k}: {v}' for k, v in sorted(m['heldByFlag'].items()))}).")
    A(f"- Held back for a series/datum mismatch (history series differs from the live binding by more than 15 ft; found by the rules-v2 hold-out QA): **{c['heldBackSeriesMismatch']}** (`held_back_series_mismatch.csv`; {c['heldBackSeriesMismatch'] + c['heldBackCoordinateFlags'] - c['heldBackEither']} of them are also coordinate-flagged).")
    A(f"- **Eligible: {c['eligible']}** (strict {c['v2StrictBeforeExclusions'] - c['excluded']} minus {c['heldBackEither']} held for either reason). Sample drawn: **{m['sampleSize']}** (random seed {m['seed']}).")
    A("")
    A("| Agency feed | Kind of source | Eligible | In sample |")
    A("|---|---|---|---|")
    for s in sorted(sizes):
        prov, cap = s.split(" | ")
        A(f"| {PROVIDER_PLAIN.get(prov, prov)} (`{prov}`) | {CAP_PLAIN.get(cap, cap)} | {sizes[s]} | {alloc[s]} |")
    A("")
    A("## How the verdict works")
    A(f"Accept the batch when **at most 1 row out of {m['sampleSize']}** is rejected. With {m['sampleSize']} rows checked, the statistical 95% upper bound on the true error rate is {bound(0)} with 0 rejects, {bound(1)} with 1, {bound(2)} with 2. If a group has a reject, that whole group is reviewed in full before any of it is accepted.")
    A("")
    A("## What happens after you finish")
    A("Give Claude the downloaded CSV. The script `jobs/lake-brain/review/ingest_review_result.py` checks every id against this pack, counts the rejects, computes the exact error bound and applies the rule above. Only if the rule is met does it propose a batch of lake ids that may become REVIEWED (never the held-back lakes, the flagged 57, or any later-wave promotion). The 57 flagged rows are decided separately and are not part of that batch.")
    A("")
    A("## Computer's own recommendations (a guide, not an answer)")
    rs, rf = m["recommendations"]["sample"], m["recommendations"]["flagged"]
    A(f"- Sample: {rs.get('PASS', 0)} PASS, {rs.get('FLAG', 0)} FLAG. Flagged-57: {rf.get('PASS', 0)} PASS, {rf.get('FLAG', 0)} FLAG.")
    A("- A FLAG means 'look at this one closely' (for example the level is far from the lake's normal full level, the names differ, or only one agency backs it). It does not mean it is wrong. A PASS does not mean you can skip the check.")
    A("")
    A("## Important limits")
    A("- Nothing here is marked REVIEWED. Binding review is not complete until you have finished the sample and the 57 flagged rows and the result has been ingested.")
    A("- Levels are a snapshot from 2026-10-13. The links go to live pages, so numbers you see there will differ slightly; what matters is that the gauge is the right lake and the level is about right.")
    A("- 'Independent second source' means a different agency measuring the same lake. Many lakes have only one agency, which is normal, not a failure.")
    A("- This pack contains only public information (gauge ids, public levels, public web links). No logins or keys.")
    A("")
    A("## Words used")
    A("- **Full pool**: the elevation (feet above sea level) the lake sits at when 'full' or at its normal level. Gauges report the same kind of number.")
    A("- **Tailwater**: the river just below a dam. A tailwater gauge is the wrong gauge for a lake.")
    A("- **Datum**: what 'zero' means for a gauge. We need feet above sea level, not 'feet above the gauge's own zero'.")
    A("- **Outline**: the lake's shape on the map. 'Distance to outline' tells how far the gauge is from the water.")
    A("- **Drawdown**: when a reservoir is held well below full on purpose (flood space, irrigation, drought).")
    open(os.path.join(out, "START HERE - README.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
