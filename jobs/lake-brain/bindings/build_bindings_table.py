#!/usr/bin/env python3
"""Build the PROPOSED Lake Brain level-source bindings table from the cached research data.

    python3 jobs/lake-brain/bindings/build_bindings_table.py [--check]

Writes (deterministically; no network):
    jobs/lake-brain/data/bindings.proposed.v1.json            one record per ELIGIBLE lake, status MACHINE_VERIFIED
    jobs/lake-brain/data/bindings.proposed.v1.excluded.json   every research-bound lake that was left out, with the exact reasons

NOTHING here is REVIEWED. Michael's review is a separate step: scripts/generate-lake-bindings.py turns this table into
Swift candidates, and only ids listed in jobs/lake-brain/data/accepted_batch.json become REVIEWED.

ELIGIBILITY (Michael's final decisions, 2026-10-13):
  * canonical = STRICT rows only: binding-review-v1 as pre-registered = waves w1 + w2-v1 of verified_bindings_v2.csv with status
    VERIFIED or VERIFIED_CORROBORATED. Never v1.1 extensions, R7h / VERIFIED_ENVELOPE promotions or other post-hoc promotions.
  * Clinton Lake|IL is excluded (its row relies on a v1.1 rule).
  * providers on the allow-list only (tva, cwms, cwms-saw, usgs, a2w, rise, nwps, twdb); lakes whose source provider is
    undocumented / has unclear terms are excluded (nipsco, njwsa, duke, wps-hydro, alliant, srp, cnppid, nppd, utahlake,
    aep, eccc, mncsg, sjrwmd, nhdes). hads / IEM is admitted only as a HISTORY source.
  * lakes whose directory coordinate is flagged (lake_geometry_flags.csv point_flag != ok: off_water / identity_risk / no polygon) are held back.
  * the 57 wave-1 flagged rows (verified_bindings.csv status VERIFIED_FLAG) are excluded, including the one that the wave-2 re-audit
    later re-labelled VERIFIED_CORROBORATED (Red Lake|MN).

INPUTS (paths overridable by env): LAKE_BRAIN_RESEARCH (docs/research/lake-brain/data of the research checkout) and
LB_DATA (Sector_Research_Data/lake-brain; bulk probe data outside Git). Their sha256 are recorded in the output.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESEARCH = os.environ.get("LAKE_BRAIN_RESEARCH",
                          "/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data")
DATA = os.environ.get("LB_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
OUT_DIR = os.path.join(REPO, "jobs", "lake-brain", "data")
OUT = os.path.join(OUT_DIR, "bindings.proposed.v1.json")
OUT_EXCLUDED = os.path.join(OUT_DIR, "bindings.proposed.v1.excluded.json")
OUT_RECOVERED = os.path.join(OUT_DIR, "bindings.proposed.v1.recovered.json")
DISPOSITIONS = os.path.join(HERE, "mismatch14_dispositions.json")
DIRECTORY_SWIFT = os.path.join(REPO, "Sources", "SectorEngine", "Support", "LakeDirectory.swift")

CRITERIA_VERSION = "binding-review-v1"
SCHEMA = "lake-brain-bindings-proposed/v1"
STATUS = "MACHINE_VERIFIED"

STRICT_WAVES = {"w1", "w2-v1"}
STRICT_STATUSES = {"VERIFIED", "VERIFIED_CORROBORATED"}
ALLOW_PROVIDERS = {"tva", "cwms", "cwms-saw", "usgs", "a2w", "rise", "nwps", "twdb"}
UNDOCUMENTED = {"nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake", "aep", "eccc", "mncsg",
                "sjrwmd", "nhdes"}
POST_HOC_STATUSES = {"VERIFIED_ENVELOPE": "post-hoc R7h envelope promotion (not in binding-review-v1)",
                     "VERIFIED_FLAG": "flagged single-origin row (drawdown / weak level class)",
                     "STAGE_ONLY": "stage-only: no absolute level to test"}

# primary reason = the first that applies in this order (a lake can have several; all are listed)
REASON_PRIORITY = ["post-hoc", "flagged", "stage-only", "flagged-wave1", "undocumented-provider", "provider-not-allowed", "coordinate-flag", "history-live-mismatch", "no-adapter-series"]

# Rules-v2 hold-out QA (jobs/lake-brain/validation/results/holdout_v2_results.json, seriesQa.mismatchOver15ft, 2026-10-13): the research
# HISTORY series differs from the LIVE binding by more than 15 ft (series / datum mismatch). A baseline built from a different series than the
# live level would give wrong 'unusual' labels. Held back pending datum resolution; no offset is guessed.
HISTORY_LIVE_MISMATCH = {
    "Bartlett|AZ", "Blue Mesa Reservoir|CO", "Buffalo Bill Reservoir|WY", "Canyon Lake|TX", "Detroit Lake|OR", "Glendo Reservoir|WY",
    "Jackson Lake|WY", "Jordanelle Reservoir|UT", "Lake Koocanusa|MT", "Lake Shelbyville|IL", "Lake Taneycomo|MO", "Navajo Reservoir|NM",
    "Pineview Reservoir|UT", "Rend Lake|IL",
}
HISTORY_MISMATCH_REASON = "history/live series mismatch >15 ft - hold pending datum resolution"
RECOVERED_SCHEMA = "lake-brain-bindings-recovered/v1"

PILOTS = {  # the 5 hand-written bindings; their time zones are kept
    "Guntersville|AL": "America/Chicago", "Wheeler|AL": "America/Chicago", "Wilson|AL": "America/Chicago",
    "Pickwick Lake|TN": "America/Chicago", "Lake Hartwell|SC": "America/New_York",
}

# Providers that have a Swift adapter in LakeLevelFeeds*.swift (live series). Keep in sync with LevelSeriesRef.Provider.
ADAPTER_PROVIDERS = {"tva", "cwms", "usgs", "a2w", "rise", "nwps", "twdb"}

ELEV_USGS_PARAMS = {"62614", "62615", "62616", "00062", "72020", "72022"}   # 00065 gage height is NOT an elevation

# ---------------------------------------------------------------------------------------------------------------- time zones
# Lake-local calendar days drive the history and the baseline. Mapping: the lake id's state (the directory's first state), with a
# longitude / latitude refinement for the states that straddle a zone boundary. County lines are not used, so a lake within about
# 30 miles of a boundary can land on the wrong side; a day that is wrong by one hour of offset moves a daily stamp only when the
# source stamps near midnight, and the history builder keys on the source's own UTC date where it matters (RISE). Documented
# approximation, not a survey.
STATE_TZ = {
    "AL": "America/Chicago", "AR": "America/Chicago", "IL": "America/Chicago", "IA": "America/Chicago", "LA": "America/Chicago",
    "MN": "America/Chicago", "MS": "America/Chicago", "MO": "America/Chicago", "OK": "America/Chicago", "WI": "America/Chicago",
    "TX": "America/Chicago", "KS": "America/Chicago", "NE": "America/Chicago", "ND": "America/Chicago", "SD": "America/Chicago",
    "TN": "America/Chicago", "KY": "America/New_York", "IN": "America/New_York", "MI": "America/Detroit", "OH": "America/New_York",
    "FL": "America/New_York", "GA": "America/New_York", "SC": "America/New_York", "NC": "America/New_York", "VA": "America/New_York",
    "WV": "America/New_York", "MD": "America/New_York", "DE": "America/New_York", "NJ": "America/New_York", "PA": "America/New_York",
    "NY": "America/New_York", "CT": "America/New_York", "RI": "America/New_York", "MA": "America/New_York", "VT": "America/New_York",
    "NH": "America/New_York", "ME": "America/New_York", "DC": "America/New_York",
    "CO": "America/Denver", "MT": "America/Denver", "NM": "America/Denver", "UT": "America/Denver", "WY": "America/Denver",
    "ID": "America/Boise", "AZ": "America/Phoenix", "NV": "America/Los_Angeles", "CA": "America/Los_Angeles",
    "OR": "America/Los_Angeles", "WA": "America/Los_Angeles", "AK": "America/Anchorage", "HI": "Pacific/Honolulu",
}


def timezone_for(state: str, lat: float, lon: float) -> tuple[str, str]:
    """IANA zone for a lake and the rule that produced it."""
    base = STATE_TZ.get(state, "America/Chicago")
    rule = f"state {state}"
    if state == "FL" and lon < -85.0:
        return "America/Chicago", "FL panhandle west of 85.0W"
    if state == "IN" and lon < -86.9:
        return "America/Chicago", "IN lon < -86.9 (NW and SW corners)"
    if state == "KY" and lon < -85.9:
        return "America/Chicago", "KY lon < -85.9 (western KY)"
    if state == "TN" and lon > -85.4:
        return "America/New_York", "TN lon > -85.4 (East Tennessee)"
    if state == "TX" and lon < -104.0:
        return "America/Denver", "TX lon < -104 (El Paso)"
    if state == "NE" and lon < -101.0:
        return "America/Denver", "NE lon < -101 (Panhandle)"
    if state == "KS" and lon < -101.5:
        return "America/Denver", "KS lon < -101.5"
    if state == "SD" and lon < -100.4:
        return "America/Denver", "SD lon < -100.4 (west river)"
    if state == "ND" and lon < -101.0 and lat < 47.5:
        return "America/Denver", "ND SW"
    if state == "OR" and lon > -117.1 and lat < 44.5:
        return "America/Boise", "OR Malheur County"
    if state == "ID" and lat > 45.9:
        return "America/Los_Angeles", "ID panhandle (Pacific)"
    if state == "MI" and lon < -87.5 and lat > 45.4:
        return "America/Chicago", "MI Upper Peninsula west"
    if state == "NV" and lat > 41.5 and lon > -114.9:
        return "America/Denver", "NV Wendover"
    return base, rule


# ---------------------------------------------------------------------------------------------------------------- helpers
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def truthy(v) -> bool:
    return str(v).strip().lower() == "true"


def num(v, digits=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return round(x, digits) if digits is not None else x


def to_int(v):
    x = num(v)
    return int(x) if x is not None else None


def live_cadence(tsid: str) -> int:
    """Live cadence the Brain budgets for: the series interval, never finer than hourly (the classifier works on hourly points)."""
    return max(60, interval_minutes(tsid)) if interval_minutes(tsid) < 1440 else interval_minutes(tsid)


def interval_minutes(tsid: str) -> int:
    """CWMS / A2W tsid -> source cadence in minutes (the 4th dotted part is the interval)."""
    parts = tsid.split(".")
    iv = parts[3] if len(parts) >= 6 else ""
    iv = iv.lstrip("~")
    m = re.match(r"^(\d+)(Minute|Minutes|Hour|Hours|Day|Days)$", iv)
    if not m:
        return 60
    n, u = int(m.group(1)), m.group(2)
    return n * (1 if u.startswith("Minute") else 60 if u.startswith("Hour") else 1440)


# ---------------------------------------------------------------------------------------------------------------- inputs
class Inputs:
    def __init__(self):
        r = RESEARCH
        self.files = {
            "verified_bindings_v2.csv": os.path.join(r, "verified_bindings_v2.csv"),
            "verified_bindings.csv": os.path.join(r, "verified_bindings.csv"),
            "plan_flood_evidence.csv": os.path.join(r, "plan_flood_evidence.csv"),
            "lake_features.csv": os.path.join(r, "lake_features.csv"),
            "history_extension.csv": os.path.join(r, "history_extension.csv"),
            "verified_v2_full.csv": os.path.join(DATA, "binding2", "verified_v2_full.csv"),
            "lake_geometry_flags.csv": os.path.join(DATA, "geometry", "lake_geometry_flags.csv"),
            "directory_lakes_2026-10-13.json": os.path.join(DATA, "directory_lakes_2026-10-13.json"),
            "nid_links.csv": os.path.join(DATA, "binding", "nid_links.csv"),
            "candidates.csv": os.path.join(DATA, "binding", "candidates.csv"),
            "probe_results_v2.json": os.path.join(DATA, "binding2", "probe_results_v2.json"),
            "clarity_index.json": os.path.join(DATA, "context", "clarity_read", "index.json"),
            "shore_dem.json": os.path.join(DATA, "context", "shore_dem.json"),
        }
        for k, p in self.files.items():
            if not os.path.exists(p):
                raise SystemExit(f"missing research input {k}: {p}")
        self.v2 = read_csv(self.files["verified_bindings_v2.csv"])
        self.v1 = {x["lake_id"]: x for x in read_csv(self.files["verified_bindings.csv"])}
        self.full = {x["lakeId"]: x for x in read_csv(self.files["verified_v2_full.csv"])}
        self.plan = {x["lakeId"]: x for x in read_csv(self.files["plan_flood_evidence.csv"])}
        self.features = {x["id"]: x for x in read_csv(self.files["lake_features.csv"])}
        self.hist_ext = {x["lake"]: x for x in read_csv(self.files["history_extension.csv"])}
        self.geom = {x["id"]: x for x in read_csv(self.files["lake_geometry_flags.csv"])}
        self.directory = {x["id"]: x for x in json.load(open(self.files["directory_lakes_2026-10-13.json"]))["lakes"]}
        self.nid = {}
        for x in read_csv(self.files["nid_links.csv"]):
            self.nid[x["lakeId"]] = x
        self.cands: dict[str, list[dict]] = collections.defaultdict(list)
        for x in read_csv(self.files["candidates.csv"]):
            self.cands[x["lakeId"]].append(x)
        self.probes = json.load(open(self.files["probe_results_v2.json"]))
        self.clarity = json.load(open(self.files["clarity_index.json"])).get("lakes", {})
        self.shore = json.load(open(self.files["shore_dem.json"]))
        self._a2w = None
        self._cwms_levels = None
        self._rise_catalog = None

    # ---- Access2Water district listings (research cache of the reporting API; one file per district)
    def a2w(self) -> dict[tuple[str, str], dict]:
        if self._a2w is None:
            out = {}
            for f in glob.glob(os.path.join(DATA, "binding", "raw", "a2w", "locations_*.json")):
                for loc in json.load(open(f)):
                    out[(loc["provider"], loc["code"])] = loc
            self._a2w = out
        return self._a2w

    # ---- CWMS /levels cache (metric; converted to ft)
    def cwms_levels(self) -> dict[tuple[str, str], list[dict]]:
        if self._cwms_levels is None:
            out = collections.defaultdict(list)
            for f in glob.glob(os.path.join(DATA, "history", "cwms_levels", "lv_*.json")):
                office = os.path.basename(f)[3:6]
                try:
                    levels = json.load(open(f)).get("levels", [])
                except Exception:
                    continue
                for lv in levels:
                    lid = lv["location-level-id"]
                    out[(office, lid.split(".")[0])].append(lv)
            self._cwms_levels = out
        return self._cwms_levels

    def rise_catalog(self) -> dict[int, dict]:
        if self._rise_catalog is None:
            items = json.load(open(os.path.join(DATA, "binding", "raw", "rise", "catalog_items_level.json")))
            self._rise_catalog = {x["attributes"]["_id"]: x["attributes"] for x in items}
        return self._rise_catalog


# ---------------------------------------------------------------------------------------------------------------- eligibility
def classify_lakes(inp: Inputs, recovered: frozenset = frozenset()):
    """-> (eligible rows, excluded list). Every research-bound lake (a row in verified_bindings_v2.csv) lands in exactly one.

    `recovered` = lakes whose history/live mismatch hold was lifted by a FIXED disposition (mismatch14_dispositions.json). It is EMPTY unless the
    caller asks for it (--include-recovered), so the default table, the review pack and the Swift generator never see a recovered lake."""
    flag57 = {k for k, r in inp.v1.items() if r["binding_status"] == "VERIFIED_FLAG"}
    eligible, excluded = [], []
    for r in inp.v2:
        lake = r["lake_id"]
        reasons = []
        in_strict = r["wave"] in STRICT_WAVES and r["binding_status"] in STRICT_STATUSES
        if not in_strict:
            if r["wave"] not in STRICT_WAVES:
                reasons.append(("post-hoc", f"wave {r['wave']} is a post-hoc extension (rules written after seeing wave-1 failures), not binding-review-v1 as pre-registered"))
            if r["binding_status"] in POST_HOC_STATUSES:
                code = "post-hoc" if r["binding_status"] == "VERIFIED_ENVELOPE" else ("flagged" if r["binding_status"] == "VERIFIED_FLAG" else "stage-only")
                reasons.append((code, f"status {r['binding_status']}: {POST_HOC_STATUSES[r['binding_status']]}"))
        if "v1.1" in r["checks_passed"]:
            reasons.append(("post-hoc", "row relies on a v1.1 rule (tag in checks_passed)"))
        if lake == "Clinton Lake|IL":
            reasons.append(("post-hoc", "Clinton Lake|IL is excluded by decision (its row relies on a v1.1 rule)"))
        prov = r["provider"]
        if prov in UNDOCUMENTED:
            reasons.append(("undocumented-provider", f"source provider '{prov}' is undocumented / terms unclear (not on the allow-list)"))
        elif prov not in ALLOW_PROVIDERS:
            reasons.append(("provider-not-allowed", f"source provider '{prov}' is not on the allow-list"))
        if lake in flag57:
            reasons.append(("flagged-wave1", "one of the 57 wave-1 flagged rows (verified_bindings.csv VERIFIED_FLAG)"))
        if lake in HISTORY_LIVE_MISMATCH and lake not in recovered:
            reasons.append(("history-live-mismatch", HISTORY_MISMATCH_REASON))
        g = inp.geom.get(lake, {})
        pf = g.get("point_flag", "")
        if pf != "ok":
            reasons.append(("coordinate-flag", f"directory coordinate point_flag={pf or 'missing (no polygon)'}"
                            + (f": {g.get('why')}" if g.get("why") else "")))
        if reasons:
            reasons.sort(key=lambda x: REASON_PRIORITY.index(x[0]))
            excluded.append((r, reasons))
        else:
            eligible.append(r)
    return eligible, excluded


# ---------------------------------------------------------------------------------------------------------------- live series
def a2w_split(station: str) -> tuple[str, str]:
    office, code = station.split(":", 1)
    return office, code


def a2w_resolve_tsid(inp: Inputs, station: str, probe: dict | None) -> tuple[str | None, str]:
    """The pool-elevation tsid of an A2W location. Research probe first (the one that was probed live), else the same catalog rule."""
    if probe and probe.get("tsid"):
        return probe["tsid"], "research probe"
    office, code = a2w_split(station)
    loc = inp.a2w().get((office, code))
    if not loc:
        return None, "location not in the A2W cache"
    ok = []
    for t in loc.get("timeseries") or []:
        p = t["parameter"]
        if not re.match(r"^(Elev|Elev-Pool|Elev-Forebay|Elev-Lake|Elev-Headwater|Elev-Upper|Elev-Reservoir)$", p):
            continue
        if re.search(r"(tail|below|down|dnstr|\btw\b|-tw\b|outlet|outflow|lower)", t["tsid"].split(".")[0], re.I):
            continue
        ok.append(t)
    if len(ok) == 1:
        return ok[0]["tsid"], "catalog rule (unique)"
    return None, f"{len(ok)} candidate tsids"


TWDB_DRYRUN = os.path.join(HERE, "twdb_dryrun.v1.json")


def twdb_catalog() -> dict[str, tuple[str, str]]:
    """TWDB research station key (recent-conditions key, e.g. `CedarCreek`) -> (file slug, datum label the file declares), from the
    committed dry run. Empty when the dry run is absent: a twdb row then has no adapter series and is not built."""
    if not os.path.exists(TWDB_DRYRUN):
        return {}
    return {x["twdbKey"]: (x["slug"], x["datumLabel"]) for x in json.load(open(TWDB_DRYRUN))["lakes"]}


def live_ref_for(inp: Inputs, row: dict, full: dict) -> dict | None:
    """The primary live series of a research row, in the Swift LevelSeriesRef shape."""
    prov, st, ser = row["provider"], row["station"], row["series_or_param"]
    cap = row["capability_class"]
    ref = {"provider": prov, "capability": cap, "station": st, "series": ser, "cadenceMin": 60, "lagMin": 60, "datumOffsetFt": 0.0}
    if prov == "tva":
        ref.update(series=None, cadenceMin=60, lagMin=60, note="observed-data-48-hours ReservoirElevation")
    elif prov in ("cwms", "cwms-saw"):
        office = st.split(":")[0]
        ref.update(provider="cwms", station=office, cadenceMin=live_cadence(ser))
        ref["lagMin"] = 1440 if ref["cadenceMin"] >= 1440 else 120
        ref["note"] = f"USACE CWMS {office} (unit=EN)" + (" [cwms-saw label in research]" if prov == "cwms-saw" else "")
        if prov == "cwms-saw":
            ref["station"] = "SAW"
    elif prov == "usgs":
        if ser not in ELEV_USGS_PARAMS:
            return None
        ref.update(cadenceMin=60, lagMin=60, note=f"USGS {full.get('stationName') or st}")
    elif prov == "a2w":
        probe = inp.probes.get(f"a2w|{st}")
        tsid, how = a2w_resolve_tsid(inp, st, probe)
        if not tsid:
            return None
        ref.update(series=tsid, cadenceMin=live_cadence(tsid), lagMin=120, note=f"USACE Access2Water {st} ({how})")
    elif prov == "rise":
        ref.update(cadenceMin=1440, lagMin=2880, note=f"USBR RISE daily item {ser} ({full.get('stationName', '')}); ~48 h latency, 0.0 placeholders dropped")
    elif prov == "nwps":
        ref.update(cadenceMin=60, lagMin=120, note=f"NWS NWPS gauge {st} observed {ser}")
    elif prov == "twdb":
        hit = twdb_catalog().get(st)
        if not hit:
            return None
        ref.update(station=hit[0], series=f"water_level@{hit[1]}", cadenceMin=1440, lagMin=1440,
                   note="TWDB Water Data for Texas estimated daily average (relay of the lake's gauge; not independent corroboration)")
    else:
        return None
    return ref


def fallback_refs(inp: Inputs, lake: str, primary: dict, primary_row: dict) -> list[dict]:
    """Other independently VERIFIED (binding-review-v1) series of the same lake from the wave-1 candidate evaluation, on adapter-backed
    allow-listed providers. Ordered operator pool first, then match score. Wave-2-only lakes have no candidate table: no fallback."""
    out, seen = [], {(primary["provider"], primary["station"], primary.get("series"))}
    cand = [c for c in inp.cands.get(lake, []) if c["status"] == "VERIFIED" and c["family"] == "elev"
            and c["prov"] in ("cwms", "a2w", "usgs", "rise", "nwps", "tva")]
    cand.sort(key=lambda c: (0 if c["capability"] == "DIRECT_OPERATOR_POOL" else 1, -float(c["matchScore"] or 0)))
    for c in cand:
        prov, st = c["prov"], c["station"]
        probe = inp.probes.get({"cwms": f"cwms|{st}|{c['loc']}", "rise": f"rise|{c['lakeName']}"}.get(prov, f"{prov}|{st}")) or {}
        if prov == "usgs":
            par = probe.get("param") or c["series"]
            if par not in ELEV_USGS_PARAMS:
                continue
            ref = {"provider": "usgs", "capability": c["capability"], "station": st, "series": par, "cadenceMin": 60, "lagMin": 60}
        elif prov == "cwms":
            ref = {"provider": "cwms", "capability": c["capability"], "station": st, "series": probe.get("series") or c["series"],
                   "cadenceMin": live_cadence(probe.get("series") or c["series"]), "lagMin": 120}
            if ref["cadenceMin"] >= 1440:
                ref["lagMin"] = 1440
        elif prov == "a2w":
            tsid, _ = a2w_resolve_tsid(inp, st, probe)
            if not tsid:
                continue
            ref = {"provider": "a2w", "capability": c["capability"], "station": st, "series": tsid, "cadenceMin": live_cadence(tsid), "lagMin": 120}
        elif prov == "rise":
            item = probe.get("item") or c["station"]
            ref = {"provider": "rise", "capability": c["capability"], "station": str(item), "series": str(item), "cadenceMin": 1440, "lagMin": 2880}
        elif prov == "nwps":
            pe = ((probe.get("datumInfo") or {}).get("pedts") or {}).get("observed") or c["series"]
            ref = {"provider": "nwps", "capability": "DIRECT_LAKE_GAUGE", "station": st, "series": pe, "cadenceMin": 60, "lagMin": 120}
        elif prov == "tva":
            ref = {"provider": "tva", "capability": c["capability"], "station": st, "series": None, "cadenceMin": 60, "lagMin": 60}
        else:
            continue
        key = (ref["provider"], ref["station"], ref.get("series"))
        if key in seen:
            continue
        seen.add(key)
        ref["datumOffsetFt"] = 0.0
        ref["note"] = f"fallback: independently VERIFIED candidate (R1-R8) of the same lake; probe {c['lastObs']} age {c['ageH']} h"
        out.append(ref)
        if len(out) == 2:
            break
    return out


# ---------------------------------------------------------------------------------------------------------------- history
USGS_RE = re.compile(r"^usgs:(?P<site>[0-9A-Za-z]+):(?P<param>[0-9]{5})(?P<alt>\+alt)?:dv$")
USGSIV_RE = re.compile(r"^usgsiv:(?P<site>[0-9A-Za-z]+):(?P<param>[0-9]{5})$")


def parse_hist_series(inp: Inputs, hs: str, row: dict, full: dict) -> tuple[dict | None, str | None]:
    """verified_v2_full.histSeries -> a Swift LakeHistorySource-shaped dict, or (None, why)."""
    if not hs:
        return None, None
    prov = hs.split(":")[0]
    if prov == "cwms":
        _, office, tsid = hs.split(":", 2)
        return {"kind": "cwmsDaily", "office": office, "series": tsid}, None
    if prov == "rise":
        return {"kind": "riseDaily", "item": hs.split(":")[1]}, None
    if prov == "twdb":
        hit = twdb_catalog().get(hs.split(":")[1]) or next((v for k, v in twdb_catalog().items() if v[0] == hs.split(":")[1]), None)
        if not hit:
            return None, f"{hs}: no TWDB file slug / datum label in the committed dry run"
        return {"kind": "twdbDaily", "slug": hit[0], "datum": hit[1], "offsetFt": 0.0}, None
    if prov == "hads":
        _, lid, pe = hs.split(":", 2)
        return {"kind": "hadsDaily", "lid": lid, "pe": pe[:2], "offsetFt": 0.0}, None
    if prov == "usgsiv":
        m = USGSIV_RE.match(hs)
        return ({"kind": "usgsDaily", "site": m["site"], "param": m["param"], "stat": "iv", "offsetFt": 0.0}, None) if m else (None, f"unparsed {hs}")
    if prov == "usgs":
        m = USGS_RE.match(hs)
        if not m:
            return None, f"unparsed {hs}"
        if m["alt"]:
            alt = usgs_site_altitude(inp, m["site"])
            if alt is None:
                return None, f"{hs}: gage-height history needs a site altitude that is not in the research cache"
            return {"kind": "usgsDaily", "site": m["site"], "param": m["param"], "stat": "dv", "offsetFt": alt,
                    "note": "gage height + site altitude (datum offset); research history series"}, None
        return {"kind": "usgsDaily", "site": m["site"], "param": m["param"], "stat": "dv", "offsetFt": 0.0}, None
    if prov == "b2":
        name = hs[3:]
        m = re.match(r"^usgs_(?P<site>[0-9A-Za-z]+)_(?P<param>[0-9]{5})\.csv\.gz$", name)
        if m and row["provider"] == "usgs":
            return {"kind": "usgsDaily", "site": m["site"], "param": m["param"], "stat": "dv", "offsetFt": 0.0}, None
        if row["provider"] == "cwms-saw" and name.startswith("cwms-saw_SAW_"):
            # the binding2 history file is the live series itself (location "ROA JHK" is flattened to ROA_JHK in the file name)
            return {"kind": "cwmsDaily", "office": "SAW", "series": row["series_or_param"]}, None
        return None, f"unmapped binding2 history file {name}"
    return None, f"unsupported history source {hs}"


def usgs_site_altitude(inp: Inputs, site: str) -> float | None:
    path = os.path.join(DATA, "binding", "catalog.jsonl")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        for ln in f:
            if f'"station": "{site}"' not in ln:
                continue
            r = json.loads(ln)
            if r["prov"] == "usgs" and r["station"] == site and r["family"] == "stage":
                return num((r.get("extra") or {}).get("alt"))
    return None


HX_USGS = re.compile(r"^usgs:(?P<site>[0-9A-Za-z]+)_(?P<param>[0-9]{5})_(?P<stat>[0-9]{5}|iv)(?:_dv)?(?:\((?P<off>[^)]*)\))?$")
HX_OFFSET = re.compile(r"^\+?(-?[0-9.]+)ft")


def parse_hx_components(sources: str) -> tuple[list[dict], list[str]]:
    """history_extension.csv `sources` -> components (precedence order) and any component we cannot represent."""
    comps, bad = [], []
    for part in [p.strip() for p in sources.split(";") if p.strip()]:
        if part.startswith("hads:"):
            comps.append({"kind": "hadsDaily", "lid": part.split(":")[1].split("(")[0], "pe": "HP", "offsetFt": 0.0})
        elif part.startswith("cwms:"):
            body = part[5:]
            off = 0.0
            m = re.search(r"\(\+(-?[0-9.]+)\)$", body)
            if m:
                off = float(m.group(1)); body = body[:m.start()]
            office, _, tsid = body.partition("_")
            comps.append({"kind": "cwmsDaily", "office": office, "series": tsid, "offsetFt": off})
        elif part.startswith("usgs:"):
            m = HX_USGS.match(part)
            if not m:
                bad.append(part); continue
            off, offtxt = 0.0, m["off"] or ""
            if "UNCALIBRATED" in offtxt:
                bad.append(part); continue
            mo = HX_OFFSET.match(offtxt)
            if mo:
                off = float(mo.group(1))
            elif offtxt:
                m2 = re.search(r"\(?\+?(-?[0-9.]+)ft", offtxt)
                off = float(m2.group(1)) if m2 else 0.0
            stat = m["stat"]
            comps.append({"kind": "usgsDaily", "site": m["site"], "param": m["param"], "stat": stat, "offsetFt": off})
        else:
            bad.append(part)   # rvd:, twdb:, coops: - not admitted as history sources here
    return comps, bad


def build_history(inp: Inputs, row: dict, full: dict, ref: dict) -> dict:
    lake = row["lake_id"]
    hx = inp.hist_ext.get(lake)
    notes = []
    sources: list[dict] = []
    years = int(full.get("completeYears") or row.get("complete_years") or 0)
    cls = full.get("historyClass") or row.get("history_class") or "NONE"
    first_year = to_int(full.get("firstYear") or row.get("period_of_record_start_year"))
    basis = "base"
    if row["provider"] == "tva":
        sources.append({"kind": "tvaOperatingGuide", "locationId": row["station"]})
        notes.append("TVA operating guide (current + previous year); long history is the NWS RVDHUN/HADS composite of the research, not integrated")
        years, cls, first_year = 0, "NONE", None
        if hx and hx["status"] == "PILOT_COMPOSITE":
            notes.append(f"research composite (RVDHUN + HADS) counted {hx['completeYears']} complete years for this pilot: not a repeatable public source")
        return {"sources": sources, "completeYears": years, "historyClass": cls, "firstYear": first_year, "basis": "tva-guide", "notes": notes}
    if hx and hx["status"] == "EXTENDED":
        comps, bad = parse_hx_components(hx["sources"])
        if comps and not bad:
            # Research precedence is "first source wins on a date"; the runner merges in list order with the LAST entry winning,
            # so the composite is emitted lowest-precedence first.
            sources = list(reversed(comps))
            if len(comps) > 1:
                notes.append("composite: listed lowest precedence first (the runner's merge lets the last entry win a date)")
            years, cls, first_year = int(hx["completeYears"]), hx["newClass"], to_int(hx["firstYear"])
            basis = "history_extension"
        else:
            notes.append(f"research extension not representable ({'; '.join(bad)}); base history used instead")
    if not sources:
        src, why = parse_hist_series(inp, full.get("histSeries", ""), row, full)
        if src:
            sources = [src]
        elif why:
            notes.append(why)
            years, cls = 0, "NONE"
            basis = "none"
        else:
            basis = "none"
            years, cls = 0, "NONE"
    return {"sources": sources, "completeYears": years, "historyClass": cls, "firstYear": first_year, "basis": basis, "notes": notes}


# ---------------------------------------------------------------------------------------------------------------- plan evidence
GUIDE_RX = re.compile(r"(guide curve|rule curve)", re.I)
TOP_RX = re.compile(r"^(top of conservation.*|top of normal|top of constant conservation|buford top of conservation.*)$", re.I)
BOT_RX = re.compile(r"^(bottom of normal|bottom of conservation|bottom of constant conservation pool|drought level.*)$", re.I)
FLOOD_RX = re.compile(r"^(top of conservation.*|top of constant conservation|buford top of conservation.*|bottom of flood( control)?)$", re.I)
M2FT = 3.28084


def pick(labels: list[str], rx: re.Pattern, prefer: list[str], search: bool = False) -> str | None:
    hits = [l for l in labels if (rx.search(l) if search else rx.match(l))]
    for p in prefer:
        for h in hits:
            if h.lower() == p:
                return h
    return hits[0] if hits else None


def a2w_levels(inp: Inputs, office: str, code: str) -> list[dict]:
    loc = inp.a2w().get((office, code))
    if not loc:
        return []
    return [x for x in (loc.get("levels") or []) if x.get("base_parameter") == "Elev" and x.get("units") in ("ft", None)]



def cwms_guide_series(inp: Inputs, office: str, loc: str) -> str | None:
    """Daily-readable CWMS 'Elev-Guide Curve' time series of a location (research catalog). Only series whose catalog extent reaches
    today qualify (a guide series that stopped in 2021 would silently give no guide); Rev versions and coarser intervals first."""
    path = os.path.join(DATA, "binding", "raw", "cwms", f"ts_{office}.json")
    if not os.path.exists(path):
        return None
    cache = inp.__dict__.setdefault("_cwms_ts", {})
    if office not in cache:
        cache[office] = [(e["name"], ((e.get("extents") or [{}])[0].get("latest-time") or "")) for e in json.load(open(path)).get("entries", [])
                         if "Elev-Guide Curve" in e["name"]]
    names = [n for n, latest in cache[office] if n.split(".")[0] == loc and latest[:10] >= "2026-10-13"]
    if not names:
        return None
    def rank(n: str):
        parts = n.split(".")
        return (0 if parts[5].startswith("Rev") else 1, interval_minutes(n) * -1, n)
    return sorted(names, key=rank)[0]


def cwms_level_items(inp: Inputs, office: str, code: str) -> list[dict]:
    return inp.cwms_levels().get((office, code), [])


def level_item(role: str, label: str, a2w_hit: dict | None, cwms_hit: dict | None, office: str, code: str) -> dict | None:
    """Compact reference to one operator level."""
    if a2w_hit is not None:
        if a2w_hit.get("type") == "CONSTANT" and a2w_hit.get("latest_value") is not None:
            return {"role": role, "name": label, "kind": "static", "valueFt": round(float(a2w_hit["latest_value"]), 2),
                    "source": f"a2w:{office}:{code}:{a2w_hit['tsid']}", "seasonal": False}
        return {"role": role, "name": label, "kind": "a2w", "office": office, "location": code, "id": a2w_hit["tsid"],
                "source": f"a2w:{office}:{code}:{a2w_hit['tsid']}", "seasonal": True,
                "researchTodayFt": num(a2w_hit.get("latest_value"), 2)}
    if cwms_hit is not None:
        lid = cwms_hit["location-level-id"]
        if "seasonal-values" in cwms_hit:
            vals = [x["value"] * M2FT for x in cwms_hit["seasonal-values"]] if cwms_hit.get("level-units-id") == "m" else [x["value"] for x in cwms_hit["seasonal-values"]]
            return {"role": role, "name": label, "kind": "cwmsLevel", "office": office, "id": lid, "source": f"cwms-level:{office}:{lid}",
                    "seasonal": True, "researchRangeFt": [round(min(vals), 2), round(max(vals), 2)]}
        v = cwms_hit.get("constant-value")
        if v is not None:
            ft = v * M2FT if cwms_hit.get("level-units-id") == "m" else v
            return {"role": role, "name": label, "kind": "static", "valueFt": round(ft, 2), "source": f"cwms-level:{office}:{lid}", "seasonal": False}
    return None


def build_plan(inp: Inputs, lake: str, row: dict) -> dict | None:
    """Verified operator plan / flood evidence under the STRICT columns only (planStrict / floodStrict, verifiedMatch)."""
    pe = inp.plan.get(lake)
    if not pe or not truthy(pe["verifiedMatch"]):
        return None
    plan_strict, flood_strict = truthy(pe["planStrict"]), truthy(pe["floodStrict"])
    if not (plan_strict or flood_strict):
        return None
    labels = [x.strip() for x in pe["levelLabels"].split(";") if x.strip()]
    ev = {"matchedProject": pe["matchedProject"], "matchBasis": pe["matchBasis"], "matchTier": pe["matchTier"] or None,
          "distKm": num(pe["distKm"]), "planSource": pe["planSource"], "verifiedMatch": True,
          "planStrict": plan_strict, "floodStrict": flood_strict, "levels": []}
    if pe["planSource"] == "tva":
        ev["tvaOperatingGuide"] = row["station"]
        ev["levels"] = [{"role": "guideCurve", "name": "TVA GuideCurve", "kind": "tvaGuide", "source": f"tva:operating-guide:{row['station']}", "seasonal": True},
                        {"role": "zoneTop", "name": "TVA TopOpZone", "kind": "tvaGuide", "source": f"tva:operating-guide:{row['station']}", "seasonal": True},
                        {"role": "zoneBottom", "name": "TVA BtmOpZone", "kind": "tvaGuide", "source": f"tva:operating-guide:{row['station']}", "seasonal": True}]
        return ev
    # projects: "SAM:Bankhead | Bankhead Lock and Dam" or "SAM:HNHenry | HNHenry (APC)"
    codes = [c.strip() for c in pe["matchedProject"].split("|")[0].split(";") if ":" in c]
    items: list[dict] = []
    chosen: dict[str, dict] = {}
    for c in codes:
        office, code = c.split(":", 1)
        a2 = a2w_levels(inp, office, code)
        cw = cwms_level_items(inp, office, code)
        by_a2 = {x["label"]: x for x in a2 if x.get("parameter") in ("Elev", "Elev-Pool") or True}
        # label -> first Elev level of that label (Elev-Pool preferred over Elev; tailwater params are not 'Elev' base-only)
        for x in a2:
            if x["parameter"] == "Elev-Pool":
                by_a2[x["label"]] = x
        by_cw = {}
        for lv in cw:
            if lv.get("parameter-id") == "Elev":
                by_cw.setdefault(lv["specified-level-id"], lv)
        avail = sorted(set(by_a2) | set(by_cw))
        want = {
            "guideCurve": pick(avail, GUIDE_RX, [], search=True) if truthy(pe["guide"]) else None,
            "zoneTop": pick(avail, TOP_RX, ["top of normal", "top of conservation", "top of constant conservation"]) if truthy(pe["zone"]) else None,
            "zoneBottom": pick(avail, BOT_RX, ["bottom of normal", "bottom of conservation"]) if truthy(pe["zone"]) else None,
            "floodPoolBottom": pick(avail, FLOOD_RX, ["top of conservation", "top of constant conservation", "bottom of flood control", "bottom of flood"]) if flood_strict else None,
        }
        for role, label in want.items():
            if not label or role in chosen:
                continue
            it = level_item(role, label, by_a2.get(label), by_cw.get(label), office, code)
            if it and role == "guideCurve" and not it["seasonal"]:
                it = None   # a guide curve is a seasonal curve; a constant "guide" level does not count (research rule)
            if it:
                chosen[role] = it
        if truthy(pe["guide"]) and "guideCurve" not in chosen:
            ts = cwms_guide_series(inp, office, code)
            if ts:
                chosen["guideCurve"] = {"role": "guideCurve", "name": "Guide Curve", "kind": "cwmsSeries", "office": office, "id": ts,
                                        "source": f"cwms:{office}:{ts}", "seasonal": True}
    if truthy(pe["guide"]) and "guideCurve" not in chosen:
        ev["unresolved"] = ["guideCurve (seasonal CWMS time-series guide; tsid not in the research cache)"]
    if truthy(pe["zone"]) and not ("zoneTop" in chosen and "zoneBottom" in chosen):
        chosen.pop("zoneTop", None); chosen.pop("zoneBottom", None)
    if plan_strict and "guideCurve" not in chosen and not ("zoneTop" in chosen and "zoneBottom" in chosen):
        ev["planStrict"] = False
    if flood_strict and "floodPoolBottom" not in chosen:
        ev["floodStrict"] = False
    ev["levels"] = [chosen[r] for r in ("guideCurve", "zoneTop", "zoneBottom", "floodPoolBottom") if r in chosen]
    if not ev["levels"]:
        return None
    return ev


# ---------------------------------------------------------------------------------------------------------------- context
def build_context(inp: Inputs, lake: str) -> dict | None:
    f = inp.features.get(lake)
    if not f:
        return None
    src = "research lake_features.csv (2026-10-13)"

    def kv(value, source, quality):
        return None if value is None or value == "" else {"value": value, "source": source, "quality": quality}

    ctx = {
        "lakeClass": kv(f["lake_class"], f"{src}; classes from morphometry + operator family + residence time", "derived"),
        "regime": kv(f["regime"], src, "derived"),
        "region": kv(f["region"], src, "derived"),
        "residenceTimeDays": kv(num(f["res_time_d"], 1), f"{src}: storage / mean inflow ({f['storage_src']} / {f['inflow_src']})", "derived") if f["res_time_d"] else None,
        "chainPosition": {"upLakes": to_int(f["n_up_lakes"]), "downLakes": to_int(f["n_down_lakes"]),
                          "nearestDown": f["nearest_down"] or None, "chainId": f["chain_id"] or None,
                          "source": "NLDI main-stem navigation from the dam coordinate (250 km) intersected with directory polygons", "quality": "derived"}
        if f["n_up_lakes"] or f["n_down_lakes"] or f["chain_id"] else None,
    }
    s = inp.shore.get(lake)
    if s:
        ctx["shorelineSlope"] = {"medianSlopeDeg": round(s["slope_med"], 2), "shareUnder2Deg": round(s["frac_lt2deg"], 3),
                                 "runPerVerticalFtMedian": round(s["run_per_ft_med"], 1),
                                 "source": "USGS 3DEP DEM, shore band 10-60 m (research context_shore_dem.py; pilots only)",
                                 "quality": "proxy (Spearman 0.76 vs CWMS stage-area slope, 33 lakes)"}
    g = inp.clarity.get(lake)
    if g and g.get("grassPct") is not None:
        ctx["grassPct"] = {"value": g["grassPct"], "asOf": g.get("date"), "source": f"Sector Water Clarity {g.get('platform', '')} pass {g.get('date')} (consume-only snapshot)",
                           "quality": "measured, single pass; refresh by regenerating"}
    return {k: v for k, v in ctx.items() if v is not None}


# ---------------------------------------------------------------------------------------------------------------- dam facts
def build_facts(inp: Inputs, lake: str, row: dict) -> dict:
    n = inp.nid.get(lake)
    out = {}
    nid_id = row.get("nid_id") or ""
    if n and (not nid_id or re.sub(r"0+", "", n["nidId"]) == re.sub(r"0+", "", nid_id) or True):
        purposes = n.get("purposes") or ""
        nid_id = nid_id or n["nidId"]
        out = {"nidId": nid_id, "damName": n["nidName"] or None, "operatorName": n["fedOp"] or n["owner"] or None,
               "hydropower": ("Hydroelectric" in purposes) if purposes else None,
               "floodControl": ("Flood Risk Reduction" in purposes) if purposes else None,
               "nidPurposes": purposes or None, "nidMatchScore": num(n.get("nidScore")), "nidDistM": num(n.get("nidDistM")),
               "source": f"NID {nid_id} purposes (nid_links.csv)"}
    elif nid_id:
        out = {"nidId": nid_id}
    return out


# ---------------------------------------------------------------------------------------------------------------- record
def build_record(inp: Inputs, row: dict) -> tuple[dict | None, list[str]]:
    lake = row["lake_id"]
    warnings = []
    full = inp.full[lake]
    d = inp.directory[lake]
    ref = live_ref_for(inp, row, full)
    if ref is None:
        return None, [f"{lake}: no live ref could be built for {row['provider']} {row['station']} {row['series_or_param']}"]
    live = [ref] + fallback_refs(inp, lake, ref, row)
    hist = build_history(inp, row, full, ref)
    tz, tz_rule = (PILOTS[lake], "pilot (hand-written binding keeps its zone)") if lake in PILOTS else timezone_for(d["state"], d["lat"], d["lon"])
    plan = build_plan(inp, lake, row)
    probe = None
    key = {"cwms": f"cwms|{row['station']}|{full.get('loc', '')}", "rise": f"rise|{full.get('stationName', '')}"}.get(row["provider"], f"{row['provider']}|{row['station']}")
    pr = inp.probes.get(key) or inp.probes.get(f"{row['provider']}|{row['station']}")
    if pr and pr.get("stats"):
        st = pr["stats"]
        probe = {"lastObservationAt": st.get("last_t"), "ageHours": st.get("age_h"), "medianFt": st.get("med_ft"), "lastFt": st.get("last_ft"),
                 "minFt30d": st.get("min_ft"), "maxFt30d": st.get("max_ft"), "samples30d": st.get("n")}
    if probe is None:
        probe = {"lastObservationAt": full.get("lastObs"), "ageHours": num(full.get("ageH")), "medianFt": num(full.get("medFt"))}
    full_pool = num(d.get("fullPoolFt"))
    rec = {
        "lakeId": lake,
        "status": STATUS,
        "capability": row["capability_class"],
        "provider": ref["provider"],
        "researchProvider": row["provider"],
        "station": ref["station"],
        "series": ref.get("series"),
        "live": live,
        "history": hist["sources"],
        "historyCompleteYears": hist["completeYears"],
        "historyClass": hist["historyClass"],
        "historyFirstYear": hist["firstYear"],
        "historyBasis": hist["basis"],
        "historyNotes": hist["notes"],
        "plan": plan,
        "timeZone": tz,
        "timeZoneRule": tz_rule,
        "dam": build_facts(inp, lake, row),
        "context": build_context(inp, lake),
        "verification": {
            "criteriaVersion": CRITERIA_VERSION,
            "researchStatus": row["binding_status"],
            "wave": row["wave"],
            "checksPassed": [c for c in row["checks_passed"].replace(";", ",").split(",") if c],
            "corroboratedBy": row["corroborated_by"] or None,
            "probedAt": "2026-10-13",
            "probe": probe,
            "directoryFullPoolFt": full_pool,
            "deltaFullPoolFt": num(full.get("deltaFullPoolFt")),
            "coordinateFlag": inp.geom[lake]["point_flag"],
        },
    }
    if rec["history"] == [] and hist["completeYears"] == 0:
        warnings.append(f"{lake}: no history source (class NONE)")
    return rec, warnings


# ---------------------------------------------------------------------------------------------------------------- recovered (mismatch14)
def load_fixed_dispositions(path: str = DISPOSITIONS) -> dict[str, dict]:
    """lakeId -> FIXED disposition record. Only lakes of the 14-lake hold list can ever be recovered; anything else is a hard error."""
    if not os.path.exists(path):
        return {}
    doc = json.load(open(path))
    out = {}
    for lake, v in doc.get("lakes", {}).items():
        if v.get("disposition") != "FIXED":
            continue
        assert lake in HISTORY_LIVE_MISMATCH, f"{lake}: a FIXED disposition for a lake outside the 14-lake mismatch hold list"
        assert v.get("reviewRequired") is True and v.get("status") == "MACHINE_VERIFIED_CANDIDATE", f"{lake}: a FIXED lake must stay a review-required candidate"
        out[lake] = v
    return out


def apply_recovery(rec: dict, disp: dict) -> dict:
    """Overlay a FIXED disposition on the machine record. Status stays MACHINE_VERIFIED (never REVIEWED); a series correction replaces the live
    primary and the history source with the documented ones. No datum offset is ever introduced (datumOffsetFt stays 0.0)."""
    assert rec["status"] == STATUS
    corr = disp.get("correction")
    if corr:
        old = corr["replaces"]
        new_live = dict(corr["live"])
        rest = [l for l in rec["live"][1:] if not (l["provider"] == old["provider"] and l["station"] == old["station"])]
        rec["live"] = [new_live] + rest
        rec["provider"], rec["researchProvider"], rec["station"], rec["series"] = new_live["provider"], new_live["provider"], new_live["station"], new_live.get("series")
        rec["history"] = [dict(corr["history"])]
        rec["historyCompleteYears"], rec["historyClass"], rec["historyFirstYear"] = corr["historyCompleteYears"], corr["historyClass"], corr["historyFirstYear"]
        rec["historyBasis"], rec["historyNotes"] = "mismatch14-correction", [corr["historyNote"]]
        rec["verification"]["probe"] = dict(corr["probe"])
    for l in rec["live"]:
        assert l.get("datumOffsetFt", 0.0) == 0.0
    rec["recovery"] = {"source": "jobs/lake-brain/bindings/mismatch14_dispositions.json", "disposition": "FIXED", "fixType": disp["fixType"],
                       "criteriaVersion": "mismatch14-v1", "reviewRequired": True,
                       "overlap": disp["overlap"], "operatorFullPoolFt": disp["operator"]["fullPoolFt"], "datumOffsetFt": 0.0,
                       "correction": (corr or {}).get("evidence")}
    return rec


def build_recovered(inp: Inputs, fixed: dict[str, dict]) -> dict[str, dict]:
    """MACHINE_VERIFIED candidate records for the FIXED lakes. Every other gate (strict wave/status, provider allow-list, no v1.1, coordinate ok)
    is still enforced here: a lake that fails one is not recovered."""
    rows = {r["lake_id"]: r for r in inp.v2}
    out = {}
    for lake, disp in sorted(fixed.items()):
        r = rows[lake]
        assert r["wave"] in STRICT_WAVES and r["binding_status"] in STRICT_STATUSES and "v1.1" not in r["checks_passed"], lake
        assert r["provider"] in ALLOW_PROVIDERS and r["provider"] not in UNDOCUMENTED, lake
        assert inp.geom[lake]["point_flag"] == "ok", lake
        rec, _ = build_record(inp, r)
        assert rec is not None, lake
        out[lake] = apply_recovery(rec, disp)
    return out


# ---------------------------------------------------------------------------------------------------------------- pilots
def pilot_reproduction(records: dict[str, dict]) -> list[dict]:
    """Assert that the 5 hand-written bindings are reproduced by the machine table (key fields). Mirrors LakeSourceBindings.swift."""
    expected = {
        "Guntersville|AL": {"provider": "tva", "station": "GVDA1", "series": None, "capability": "DIRECT_OPERATOR_POOL", "tz": "America/Chicago",
                            "history": [{"kind": "tvaOperatingGuide", "locationId": "GVDA1"}]},
        "Wheeler|AL": {"provider": "tva", "station": "WHLA1", "series": None, "capability": "DIRECT_OPERATOR_POOL", "tz": "America/Chicago",
                       "history": [{"kind": "tvaOperatingGuide", "locationId": "WHLA1"}]},
        "Wilson|AL": {"provider": "tva", "station": "WLSA1", "series": None, "capability": "DIRECT_OPERATOR_POOL", "tz": "America/Chicago",
                      "history": [{"kind": "tvaOperatingGuide", "locationId": "WLSA1"}]},
        "Pickwick Lake|TN": {"provider": "tva", "station": "PICT1", "series": None, "capability": "DIRECT_OPERATOR_POOL", "tz": "America/Chicago",
                             "history": [{"kind": "tvaOperatingGuide", "locationId": "PICT1"}]},
        # Hartwell: the hand-written binding has CWMS SAS pool as primary and USGS 02187010/00062 as the reviewed fallback; the machine
        # probe found the CWMS pool feed silent (R6) and chose the USGS gauge. Same station + parameter, same CWMS daily history.
        "Lake Hartwell|SC": {"provider": "usgs", "station": "02187010", "series": "00062", "capability": "DIRECT_LAKE_GAUGE", "tz": "America/New_York",
                             "history": [{"kind": "cwmsDaily", "office": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS"}]},
    }
    out = []
    for lake, e in expected.items():
        r = records.get(lake)
        assert r is not None, f"pilot {lake} is not in the machine table"
        got = {"provider": r["provider"], "station": r["station"], "series": r.get("series"), "capability": r["capability"], "tz": r["timeZone"]}
        for k in got:
            assert got[k] == e[k], f"pilot {lake}: {k} machine={got[k]!r} hand-written={e[k]!r}"
        hist = [dict(h) for h in r["history"]]
        for h in e["history"]:
            assert h in hist, f"pilot {lake}: history {h} missing from machine history {hist}"
        out.append({"lakeId": lake, "matches": True, **got})
    return out


# ---------------------------------------------------------------------------------------------------------------- main
def swift_directory_ids() -> set[str]:
    if not os.path.exists(DIRECTORY_SWIFT):
        return set()
    txt = open(DIRECTORY_SWIFT).read()
    return set(re.findall(r'id: "([^"]+\|[A-Z]{2})"', txt)) | set(re.findall(r'"id": "([^"]+\|[A-Z]{2})"', txt))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="build in memory and fail if the committed files differ")
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--include-recovered", action="store_true",
                    help="ALSO put the FIXED mismatch14 lakes (mismatch14_dispositions.json) into the main table as MACHINE_VERIFIED candidates. "
                         "Off by default: the committed table, the review pack and the Swift generator stay at the 196-lake population until a human accepts the recovered list.")
    args = ap.parse_args(argv)

    inp = Inputs()
    fixed = load_fixed_dispositions()
    recovered_records = build_recovered(inp, fixed) if fixed else {}
    eligible, excluded_rows = classify_lakes(inp, frozenset(recovered_records) if args.include_recovered else frozenset())
    records, warnings, dropped = {}, [], []
    for row in eligible:
        rec, w = build_record(inp, row)
        warnings += w
        if rec is None:
            dropped.append((row, [("no-adapter-series", w[0])]))
            continue
        if args.include_recovered and row["lake_id"] in recovered_records:
            rec = recovered_records[row["lake_id"]]
        records[row["lake_id"]] = rec

    # Pilots are asserted on the machine records computed BEFORE eligibility (a pilot held back for a coordinate flag still has a record).
    pilot_rows = [r for r in inp.v2 if r["lake_id"] in PILOTS]
    pilot_records = {}
    for r in pilot_rows:
        rec, _ = build_record(inp, r)
        if rec:
            pilot_records[r["lake_id"]] = rec
    reproduction = pilot_reproduction(pilot_records)

    ids = swift_directory_ids()
    if ids:
        missing = [k for k in records if k not in ids]
        assert not missing, f"lake ids not in LakeDirectory.swift: {missing}"

    ordered = [records[k] for k in sorted(records)]
    by_provider = collections.Counter(r["provider"] for r in ordered)
    ex_list = []
    for row, reasons in excluded_rows + dropped:
        d = inp.directory.get(row["lake_id"], {})
        ex_list.append({"lakeId": row["lake_id"], "researchProvider": row["provider"], "researchStatus": row["binding_status"], "wave": row["wave"],
                        "primaryReason": reasons[0][0], "reasons": [{"code": c, "detail": t} for c, t in reasons],
                        "coordinateFlag": inp.geom.get(row["lake_id"], {}).get("point_flag", "")})
    ex_list.sort(key=lambda x: x["lakeId"])
    ex_primary = collections.Counter(x["primaryReason"] for x in ex_list)
    ex_any = collections.Counter(r["code"] for x in ex_list for r in x["reasons"])
    plan_counts = collections.Counter()
    for r in ordered:
        p = r["plan"]
        if p:
            plan_counts["withEvidence"] += 1
            plan_counts["planStrict"] += bool(p["planStrict"])
            plan_counts["floodStrict"] += bool(p["floodStrict"])
    hist_counts = collections.Counter(r["historyClass"] for r in ordered)

    doc = {
        "schema": SCHEMA, "bindingStatus": STATUS, "criteriaVersion": CRITERIA_VERSION,
        "note": "MACHINE_VERIFIED, NOT REVIEWED. Generated by jobs/lake-brain/bindings/build_bindings_table.py from the cached research data. "
                "A binding becomes REVIEWED only by listing its lakeId in jobs/lake-brain/data/accepted_batch.json after Michael's review.",
        "researchDate": "2026-10-13",
        "inputs": {k: {"sha256": sha256(p)} for k, p in sorted(inp.files.items())},
        "counts": {"eligible": len(ordered), "byProvider": dict(sorted(by_provider.items())), "history": dict(sorted(hist_counts.items())),
                   "plan": dict(plan_counts), "excludedResearchBound": len(ex_list), "excludedByPrimaryReason": dict(sorted(ex_primary.items())),
                   "excludedByAnyReason": dict(sorted(ex_any.items()))},
        "pilotReproduction": reproduction,
        "bindings": ordered,
    }
    ex_doc = {"schema": "lake-brain-bindings-excluded/v1", "criteriaVersion": CRITERIA_VERSION, "count": len(ex_list),
              "byPrimaryReason": dict(sorted(ex_primary.items())), "byAnyReason": dict(sorted(ex_any.items())),
              "note": "Every lake with a research binding row (verified_bindings_v2.csv) that is NOT in bindings.proposed.v1.json. Unbound lakes are not listed.",
              "excluded": ex_list}

    text = json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n"
    ex_text = json.dumps(ex_doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n"
    rec_text = None
    if fixed:
        rec_doc = {"schema": RECOVERED_SCHEMA, "bindingStatus": STATUS, "criteriaVersion": CRITERIA_VERSION,
                   "note": "NEWLY RECOVERED, NOT REVIEWED. MACHINE_VERIFIED candidates whose history/live mismatch hold was lifted by a FIXED disposition "
                           "(jobs/lake-brain/bindings/mismatch14_dispositions.json). They are NOT in bindings.proposed.v1.json, NOT in any review sample or pack, and "
                           "cannot be accepted until Michael reviews this list, removes the lakes from held_lakes.SERIES_MISMATCH and regenerates with --include-recovered.",
                   "dispositions": {"sha256": sha256(DISPOSITIONS)}, "count": len(recovered_records),
                   "bindings": [recovered_records[k] for k in sorted(recovered_records)]}
        rec_text = json.dumps(rec_doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n"
    if args.stdout:
        sys.stdout.write(text)
        return 0
    if args.check:
        ok = os.path.exists(OUT) and open(OUT).read() == text and os.path.exists(OUT_EXCLUDED) and open(OUT_EXCLUDED).read() == ex_text
        if rec_text is not None:
            ok = ok and os.path.exists(OUT_RECOVERED) and open(OUT_RECOVERED).read() == rec_text
        print("bindings tables up to date" if ok else "bindings tables differ from a fresh build")
        return 0 if ok else 1
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        f.write(text)
    with open(OUT_EXCLUDED, "w") as f:
        f.write(ex_text)
    if rec_text is not None:
        with open(OUT_RECOVERED, "w") as f:
            f.write(rec_text)
        print(f"recovered (FIXED, review required) {len(recovered_records)} -> {os.path.relpath(OUT_RECOVERED, REPO)}")
    print(f"eligible {len(ordered)} -> {os.path.relpath(OUT, REPO)}")
    print("  by provider:", dict(sorted(by_provider.items())))
    print("  history:", dict(sorted(hist_counts.items())), " plan:", dict(plan_counts))
    print(f"excluded {len(ex_list)} research-bound lakes -> {os.path.relpath(OUT_EXCLUDED, REPO)}")
    print("  primary reason:", dict(sorted(ex_primary.items())))
    print("  any reason:    ", dict(sorted(ex_any.items())))
    for w in warnings:
        print("  warn:", w)
    print("pilot reproduction:", ", ".join(x["lakeId"] for x in reproduction))
    return 0


if __name__ == "__main__":
    sys.exit(main())
