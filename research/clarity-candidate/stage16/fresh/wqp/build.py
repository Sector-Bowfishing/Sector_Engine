#!/opt/homebrew/bin/python3.13
"""Build secchi.csv / turbidity.csv from the raw WQP downloads in raw/.

Run download.py first. Re-runnable; reads only raw/ and writes:
  secchi.csv, secchi_censored.csv, turbidity.csv, build_stats.json, flag_review.tsv
"""
import collections
import csv
import datetime as dt
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
TODAY = dt.date.today()
START = dt.date(2018, 1, 1)

from download import STATES  # noqa: E402  (same folder)

ABBR = {f: a for f, a in STATES}

SECCHI_CHAR = "Depth, Secchi disk depth"
TURB_CHAR = "Turbidity"

LEN_TO_M = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "ft": 0.3048, "feet": 0.3048, "foot": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "cm": 0.01, "mm": 0.001, "yd": 0.9144,
}

# Activity types that are not a measurement of the lake water itself.
NON_ENV_QC = re.compile(r"blank|spike|reference|standard|calibration|lab control|matrix|surrogate|measurement precision", re.I)

# ---------------------------------------------------------------- helpers

def read_csv(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        yield from csv.DictReader(f)


def job_files(name):
    """CSV paths for a download job, following year splits. None if the job failed."""
    mp = os.path.join(RAW, name + ".meta.json")
    if not os.path.exists(mp):
        return None
    with open(mp) as f:
        meta = json.load(f)
    if not meta.get("ok"):
        return None
    if meta.get("split_by_year"):
        return [os.path.join(RAW, p + ".csv") for p in meta["parts"]]
    return [os.path.join(RAW, name + ".csv")]


def to_float(s):
    try:
        x = float(s)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def length_m(value, unit):
    x = to_float(value)
    if x is None:
        return None
    k = LEN_TO_M.get((unit or "").strip().lower().rstrip("."))
    return None if k is None else x * k


def hhmm(t):
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", t or "")
    if not m:
        return ""
    h, mi = int(m.group(1)), int(m.group(2))
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else ""


def parse_date(s):
    try:
        return dt.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def fmt_value(v, x):
    """Keep the reported digits for plain decimals ('.53' -> '0.53'); normalise the rest."""
    if re.fullmatch(r"\d+(\.\d*)?|\.\d+", v):
        whole, _, frac = v.partition(".")
        whole = whole.lstrip("0") or "0"
        return whole + ("." + frac if frac else "")
    return repr(x)


def fmt(x, nd):
    return repr(round(x, nd)) if x is not None else ""


def valid_coord(lat, lon, state):
    if lat is None or lon is None or lat == 0 or lon == 0:
        return False
    if not (17.5 <= lat <= 72.0):
        return False
    if -180.0 <= lon <= -64.0:
        return True
    return state == "AK" and 170.0 <= lon <= 180.0  # western Aleutians


# Approximate state extents (lat_min, lat_max, lon_min, lon_max), used with a 0.3 deg pad.
STATE_BOX = {
    "AL": (30.1, 35.1, -88.5, -84.9), "AK": (51.2, 71.5, -180.0, -129.9), "AZ": (31.3, 37.0, -114.9, -109.0),
    "AR": (33.0, 36.5, -94.7, -89.6), "CA": (32.5, 42.1, -124.5, -114.1), "CO": (36.9, 41.1, -109.1, -102.0),
    "CT": (40.9, 42.1, -73.8, -71.8), "DE": (38.4, 39.9, -75.8, -75.0), "DC": (38.8, 39.0, -77.2, -76.9),
    "FL": (24.4, 31.0, -87.7, -80.0), "GA": (30.3, 35.0, -85.7, -80.8), "HI": (18.9, 22.3, -160.3, -154.8),
    "ID": (41.9, 49.0, -117.3, -111.0), "IL": (36.9, 42.5, -91.6, -87.0), "IN": (37.7, 41.8, -88.1, -84.8),
    "IA": (40.3, 43.6, -96.7, -90.1), "KS": (36.9, 40.0, -102.1, -94.6), "KY": (36.4, 39.2, -89.6, -81.9),
    "LA": (28.9, 33.1, -94.1, -88.8), "ME": (43.0, 47.5, -71.1, -66.9), "MD": (37.9, 39.8, -79.5, -75.0),
    "MA": (41.2, 42.9, -73.5, -69.9), "MI": (41.6, 48.3, -90.5, -82.1), "MN": (43.4, 49.4, -97.3, -89.5),
    "MS": (30.1, 35.0, -91.7, -88.1), "MO": (35.9, 40.7, -95.8, -89.1), "MT": (44.3, 49.0, -116.1, -104.0),
    "NE": (39.9, 43.1, -104.1, -95.3), "NV": (35.0, 42.0, -120.1, -114.0), "NH": (42.6, 45.4, -72.6, -70.6),
    "NJ": (38.9, 41.4, -75.6, -73.9), "NM": (31.3, 37.0, -109.1, -103.0), "NY": (40.4, 45.1, -79.8, -71.8),
    "NC": (33.8, 36.6, -84.4, -75.4), "ND": (45.9, 49.0, -104.1, -96.5), "OH": (38.4, 42.3, -84.9, -80.5),
    "OK": (33.6, 37.0, -103.1, -94.4), "OR": (41.9, 46.3, -124.6, -116.4), "PA": (39.7, 42.3, -80.6, -74.7),
    "RI": (41.1, 42.1, -71.9, -71.1), "SC": (32.0, 35.3, -83.4, -78.5), "SD": (42.4, 46.0, -104.1, -96.4),
    "TN": (34.9, 36.7, -90.4, -81.6), "TX": (25.8, 36.5, -106.7, -93.5), "UT": (36.9, 42.0, -114.1, -109.0),
    "VT": (42.7, 45.1, -73.5, -71.4), "VA": (36.5, 39.5, -83.7, -75.2), "WA": (45.5, 49.0, -124.8, -116.9),
    "WV": (37.2, 40.7, -82.7, -77.7), "WI": (42.4, 47.1, -92.9, -86.2), "WY": (41.0, 45.0, -111.1, -104.0),
}


def in_state_box(lat, lon, state, pad=0.3):
    b = STATE_BOX.get(state)
    if b is None:
        return True
    if state == "AK" and lon > 0:
        return b[0] - pad <= lat <= b[1] + pad
    return b[0] - pad <= lat <= b[1] + pad and b[2] - pad <= lon <= b[3] + pad


def haversine_m(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(min(1.0, h)))


# ---------------------------------------------------- bottom-visible text rules
# Applied to ResultCommentText (specific to the Secchi result) and to
# ActivityCommentText (shared by every result of the visit, so it only counts
# when it names the disk). Outcomes: 'true' = reading censored high (disk on /
# visible at the bottom, reported as greater-than, or view blocked by plants),
# 'false' = explicitly not on the bottom, 'less' = censored low, '' = no info.
SECCHI_WORD = r"(?:\bsecchi|\bdisks?\b|\bdiscs?\b|\bsd\b|\bsdd\b)"
NEG_TEXT = [
    re.compile(r"seen on bottom:\s*no\b", re.I),
    re.compile(r"bottom\?\s*:?\s*(?:no|n)\b", re.I),
    re.compile(r"\bnot\s+(?:seen\s+|visible\s+)?(?:on|at|to|touching|hit\w*|reach\w*)\s+(?:the\s+)?bottom", re.I),
    re.compile(r"\b(?:did\s*n[o']?t|does\s*n[o']?t|never|could\s*n[o']?t)\s+(?:hit|reach|touch|see)\s+(?:the\s+)?bottom", re.I),
    re.compile(r"bottom\s+(?:was\s+)?not\s+(?:visible|seen|reached)", re.I),
    re.compile(r"\bbottom visible:\s*no\b", re.I),
]
POS_TEXT = [
    re.compile(r"seen on bottom:\s*yes\b", re.I),
    re.compile(r"bottom\?\s*:?\s*(?:yes|y)\b", re.I),
    re.compile(r"^\s*(?:disk\s+|disc\s+|secchi\s+)?(?:is\s+|was\s+)?on\s+(?:the\s+)?bottom\b", re.I),
    re.compile(r"\bbottom visible:\s*yes\b", re.I),
    re.compile(SECCHI_WORD + r"[^.;|\n]{0,40}?\b(?:on|at|to|hit|hits|hitting|touch\w*|rest\w*|reach\w*|sitting|lying|laying|sat)\s+(?:on\s+|at\s+)?(?:the\s+)?(?:lake\s+|pond\s+)?bottom", re.I),
    re.compile(SECCHI_WORD + r"\s*(?:=|\bis\b|\bwas\b|\bequals?\b)\s*(?:the\s+)?(?:lake\s+)?bottom", re.I),
    re.compile(r"\b(?:clear|visible|visable|seen|visibility)\s+(?:all\s+the\s+way\s+)?(?:to|on|at)\s+(?:the\s+)?bottom", re.I),
    re.compile(r"\bbottom\s+(?:was\s+|is\s+)?(?:clearly\s+)?(?:visible|visable|seen)\b", re.I),
    re.compile(r"\b(?:saw|see|could see|can see)\s+(?:the\s+)?bottom\b", re.I),
    re.compile(r"\bhit\s+(?:the\s+)?bottom\b", re.I),
    re.compile(r"\btouch\w*\s+(?:the\s+)?bottom\b", re.I),
    re.compile(r"\bon\s+bottom\b", re.I),
    re.compile(r"\bto\s+bottom\b", re.I),
    re.compile(r"\bobscured\s+by\s+(?:the\s+)?bottom", re.I),
    re.compile(r"\bbottomed\s+out\b", re.I),
    re.compile(r"\b(?:vob|sob|v\.o\.b\.)\b", re.I),
    re.compile(r"^\s*bottom\b(?!\s*(?:depth|temp|sample|reading|oxygen|do\b|mud|substrate|of\b|is\s+at|was\s+at))", re.I),
]
GT_TEXT = [
    re.compile(r"^\s*(?:>=?|greater\s+than|more\s+than|deeper\s+than|at\s+least)\s*\d", re.I),
    re.compile(r"(?:secchi|\bsd\b|\bsdd\b|reading|transparency)\s*(?:depth\s+)?(?:is\s+|was\s+)?(?:>|greater\s+than|deeper\s+than|more\s+than)", re.I),
    re.compile(r"qualifier:\s*\(?\s*>", re.I),
]
LT_TEXT = [re.compile(r"qualifier:\s*\(?\s*<", re.I), re.compile(r"^\s*(?:<=?|less\s+than)\s*\d", re.I)]
VEG = r"(?:vegetation|veg\b|weeds?|plants?|macrophytes?|grass(?:es)?|sav\b|hydrilla|milfoil|lily|lilies|pondweed|algae\s+mat)"
OBSTRUCTED = [
    re.compile(r"(?:obstruct\w*|obscur\w*|limited|blocked|hidden|impeded|lost\s+(?:visual|sight|view))\s+(?:\w+\s+){0,3}?(?:by|due\s+to|because\s+of)\s+(?:\w+\s+){0,2}?" + VEG, re.I),
    re.compile(VEG + r"\s+(?:\w+\s+){0,2}?(?:obstruct\w*|obscur\w*|block\w*|impair\w*|interfer\w*|limit\w*|prevent\w*)", re.I),
    re.compile(r"(?:lost|disappear\w*|hidden|went)\s+(?:in|into|behind|among)\s+(?:the\s+)?(?:\w+\s+)?" + VEG, re.I),
    re.compile(SECCHI_WORD + r"\s+(?:disk\s+|disc\s+)?(?:\w+\s+)?in\s+(?:the\s+)?" + VEG, re.I),
    re.compile(r"(?:could\s*n[o']?t|unable\s+to|can\s*n[o']?t|cannot)\s+see\s+(?:any\s+)?(?:farther|further|deeper)", re.I),
    re.compile(r"(?:secchi|depth|reading|clarity)[^.;]{0,40}\bdue\s+to\s+(?:\w+\s+){0,2}?" + VEG, re.I),
    re.compile(r"^\s*(?:in\s+)?weeds?\s*\.?\s*$", re.I),   # FL LAKEWATCH: disk disappeared into weeds
    re.compile(VEG + r"\s+(?:\w+\s+){0,3}?(?:impact\w*|affect\w*|hinder\w*|impair\w*)\b[^.;]{0,30}" + SECCHI_WORD, re.I),
    re.compile(VEG + r"\s+(?:covered|covering|hid|hides|hiding|hide)\s+(?:the\s+)?" + SECCHI_WORD, re.I),
]
# Visit comments saying the Secchi reading itself was bad.
BAD_SECCHI_COMMENT = re.compile(r"bad[_\s]+secchi|secchi[^.;]{0,25}\b(?:invalid|unreliable|questionable|suspect|erroneous|not\s+valid)\b", re.I)
# Comments that mention the bottom but not the Secchi disk reaching it.
BOTTOM_NOT_SECCHI = re.compile(
    r"bottom\s+(?:temp|oxygen|do\b|sample|water|depth|reading|diffus|substrate)|"
    r"sonde|probe|ysi|anchor|\btube\b|sampler|(?:weeds?|vegetation|plants?|algae|debris|mud|sediment|periphyton)\s+(?:on|at|covering)\s+(?:the\s+)?bottom|growing\s+from\s+bottom|"
    r"(?:muddy|sandy|rocky|mucky|shallow|hard)\s+bottom", re.I)
# Florida DEP data-qualifier codes carried in comments as **X** (FAC 62-160):
# S = Secchi disk visible to bottom, L = off-scale high (> value), K = off-scale low.
FL_CODE = re.compile(r"\*\*([A-Za-z!?*]{1,6})\*\*")


def text_flag(text, activity_level):
    """Return (outcome, reason) for one comment string; outcome in true/false/less/''."""
    if not text:
        return "", ""
    t = " ".join(text.split())
    if not activity_level:
        codes = "".join(FL_CODE.findall(t)).upper()
        if "S" in codes:
            return "true", "comment:FL qualifier S (visible on bottom)"
        if "L" in codes:
            return "true", "comment:FL qualifier L (greater than)"
        if "K" in codes:
            return "less", "comment:FL qualifier K (less than)"
    structured = re.search(r"seen on bottom:|bottom visible:|bottom\?\s*:", t, re.I)
    names_disk = re.search(SECCHI_WORD, t, re.I)
    if activity_level and not (names_disk or structured):
        return "", ""  # activity comments cover every result (DO, temp, bottom samples...)
    for rx in NEG_TEXT:
        if rx.search(t):
            return "false", "comment:not on bottom"
    if not activity_level:
        for rx in LT_TEXT:
            if rx.search(t):
                return "less", "comment:less than"
    for rx in GT_TEXT:
        if rx.search(t):
            return "true", "comment:greater than"
    for rx in POS_TEXT:
        if not rx.search(t):
            continue
        if not names_disk and not structured and BOTTOM_NOT_SECCHI.search(t):
            return "", ""  # e.g. 'sonde touching bottom', 'weeds on bottom'
        if re.search(r"\bmay\b|\bmight\b|\bpossibl|\bprobabl|\blikely\b", t, re.I):
            return "true", "comment:bottom visible (uncertain)"
        return "true", "comment:bottom visible"
    if any(rx.search(t) for rx in OBSTRUCTED):
        return "true", "comment:view obstructed by vegetation"
    return "", ""


# ---------------------------------------------------------------- stations

# Stations whose stored coordinates are known to be wrong and cannot be repaired.
BAD_SITE_COORDS = {
    "IDEQ_WQX-BPL3": "stored lon +116.565: flipping the sign lands ~40 km west of Payette Lake "
                     "(sister sites BPL1/BPL4 sit at -116.06..-116.11), so a digit is also wrong",
}


def load_stations(stats):
    sites = {}
    failed = []
    for kind in ("secchi", "turb"):
        for fips, ab in STATES:
            files = job_files(f"{kind}_station_{ab}")
            if files is None:
                failed.append(f"{kind}_station_{ab}")
                continue
            for p in files:
                for r in read_csv(p):
                    sid = r["MonitoringLocationIdentifier"]
                    if sid not in sites:
                        r["_state"] = ab
                        sites[sid] = r
    stats["station_jobs_failed"] = failed
    # Longitude/latitude sign slips (e.g. Payette Lake, ID stored at +116.06):
    # flip the sign only if the flipped point falls inside the state's box.
    fixed = []
    for sid, s in sites.items():
        lat, lon = to_float(s["LatitudeMeasure"]), to_float(s["LongitudeMeasure"])
        if lat is None or lon is None or valid_coord(lat, lon, s["_state"]) or sid in BAD_SITE_COORDS:
            continue
        for flat, flon in ((lat, -lon), (-lat, lon), (-lat, -lon)):
            if valid_coord(flat, flon, s["_state"]) and in_state_box(flat, flon, s["_state"]):
                s["LatitudeMeasure"], s["LongitudeMeasure"] = repr(flat), repr(flon)
                fixed.append(f"{sid} ({lat},{lon} -> {flat},{flon})")
                break
    stats["station_coordinate_sign_fixed"] = fixed
    for sid, why in BAD_SITE_COORDS.items():
        if sid in sites:
            sites[sid]["LatitudeMeasure"] = sites[sid]["LongitudeMeasure"] = ""
    stats["station_coordinates_rejected"] = BAD_SITE_COORDS
    return sites


# ---------------------------------------------------------- companion flags

def minutes(t):
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", t or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


class Companion:
    """Evidence recorded as separate results: joined on ActivityIdentifier, else
    on (site, date) when the times are within 90 minutes (or either is missing)."""

    def __init__(self):
        self.by_act = collections.defaultdict(list)
        self.by_day = collections.defaultdict(list)

    def add(self, r, item):
        self.by_act[r["ActivityIdentifier"]].append(item)
        self.by_day[(r["MonitoringLocationIdentifier"], r["ActivityStartDate"])].append((minutes(r["ActivityStartTime/Time"]), item))

    def get(self, r):
        hit = self.by_act.get(r["ActivityIdentifier"])
        if hit:
            return hit, "same visit"
        t = minutes(r["ActivityStartTime/Time"])
        out = [it for tt, it in self.by_day.get((r["MonitoringLocationIdentifier"], r["ActivityStartDate"]), [])
               if t is None or tt is None or abs(t - tt) <= 90]
        return out, "same site+day"


def load_companions(stats):
    """Bottom-visible evidence recorded as separate results, plus bottom depths (m)."""
    flags = Companion()
    counts = collections.Counter()

    def add(name, fn):
        files = job_files(name)
        if files is None:
            stats.setdefault("companion_jobs_failed", []).append(name)
            return
        for p in files:
            for r in read_csv(p):
                f = fn(r["ResultMeasureValue"].strip())
                if f:
                    flags.add(r, (f, name))
                    counts[(name, f)] += 1

    def yn(v):
        u = v.upper()
        return "true" if u in ("Y", "YES") else "false" if u in ("N", "NO") else ""

    add("comp_secchi_bottom_yn", yn)
    add("comp_secchi_choice", lambda v: "true" if "BOTTOM" in v.upper() and "NOT" not in v.upper() else "")
    add("comp_secchi_condition", lambda v: "true" if "BOTTOM" in v.upper() and "NOT" not in v.upper() else "")
    add("comp_lake_clear_bottom", lambda v: "true" if v.lower().startswith(("yes", "clear to bottom")) else "false" if v.lower() in ("no", "n") else "")

    bottom = Companion()
    files = job_files("comp_depth_bottom")
    if files is None:
        stats.setdefault("companion_jobs_failed", []).append("comp_depth_bottom")
    else:
        for p in files:
            for r in read_csv(p):
                d = length_m(r["ResultMeasureValue"], r["ResultMeasure/MeasureUnitCode"])
                if d is not None and 0 < d < 400:
                    bottom.add(r, d)
    stats["companion_flag_counts"] = {f"{k[0]}={k[1]}": v for k, v in sorted(counts.items())}
    return flags, bottom


# ------------------------------------------------------------------- secchi

SECCHI_COLS = ["site_id", "site_name", "org", "lat", "lon", "date", "time", "time_zone", "secchi_m", "bottom_visible", "state"]
# depth_m (sample depth) is an extra trailing column: many lake turbidity rows are profile samples.
TURB_COLS = ["site_id", "site_name", "org", "lat", "lon", "date", "time", "value", "unit", "state", "depth_m"]
NWIS_SECCHI_PCODE_RANK = {"00078": 0, "49701": 1, "00077": 2}   # m, ft, in
UNIT_RANK = {"m": 0, "meters": 0, "cm": 1, "mm": 1, "in": 2, "ft": 3, "feet": 3}
# WQX qualifier codes that mean the value should not be used.
REJECT_Q = {"R", "SUS", "FQC", "FPC", "LAC", "SCF"}
LESS_Q = {"U", "<"}
GREATER_Q = {"GT", ">", "LL"}   # LL: 'true value assumed greater than reported' (MNPCA Secchi-on-bottom)
REJECT_COMMENT = re.compile(r"\bto\s+rejected\b|\binvalid(?:ated)?\b", re.I)
TURB_UNITS = {"NTU", "FNU", "NTRU", "FTU", "JTU", "NTMU", "FNRU", "FAU", "FNMU", "AU"}
CENSOR_DET = {"Not Detected", "Present Below Quantification Limit", "Below Reporting Limit", "Below Method Detection Limit",
              "Below Detection Limit", "Below Daily Detection Limit", "Below Sample-specific Detect Limit",
              "Below System Detection Limit", "Detected Not Quantified", "Not Detected at Detection Limit",
              "Not Detected at Reporting Limit", "Present Above Quantification Limit", "Above Operating Range",
              "Not Reported", "Unable to Measure", "Not Present", "Trace"}


def site_coords(r, sites, state, stats_key, drops):
    """Station coordinates; the activity's own coordinates only if the station has none."""
    sid = r["MonitoringLocationIdentifier"]
    s = sites.get(sid)
    lat = lon = None
    src = ""
    if s:
        lat, lon = to_float(s["LatitudeMeasure"]), to_float(s["LongitudeMeasure"])
        src = "station"
    if not valid_coord(lat, lon, state):
        alat, alon = to_float(r.get("ActivityLocation/LatitudeMeasure")), to_float(r.get("ActivityLocation/LongitudeMeasure"))
        if sid not in BAD_SITE_COORDS and valid_coord(alat, alon, state) and in_state_box(alat, alon, state):
            lat, lon, src = alat, alon, "activity"
        else:
            drops[f"no_valid_coordinates" + ("" if s else "(no station record)")] += 1
            return None
    return lat, lon, src, s


def parse_secchi_value(raw_v, unit):
    """-> (metres or None, censor) where censor is '', '>' or '<'."""
    v = raw_v.strip().lstrip("=").strip()        # NH DES exports values as '=3.5'
    censor = ""
    if v.startswith(">"):
        censor, v = ">", v.lstrip(">=").strip()
    elif v.startswith("<"):
        censor, v = "<", v.lstrip("<=").strip()
    elif v.endswith("+") and to_float(v[:-1]) is not None:   # '3.5+'
        censor, v = ">", v[:-1].strip()
    m = re.fullmatch(r"(\d*\.?\d+)\s*(m|ft|cm|in)\.?", v, re.I)   # unit written into the value ('>2m')
    if m:
        v, unit = m.group(1), m.group(2)
    x = to_float(v)
    if x is None:
        return None, censor, "no_value" if v == "" else "non_numeric_value"
    mm = length_m(v, unit)
    if mm is None:
        return None, censor, f"unknown_unit({unit or 'blank'})"
    return mm, censor, ""


def build_secchi(sites, comp_flags, bottom, stats, review):
    drops = collections.Counter()
    flag_src = collections.Counter()
    units = collections.Counter()
    qual = collections.Counter()
    tz = collections.Counter()
    coord_src = collections.Counter()
    far_actloc = collections.Counter()
    flag_orgs = collections.Counter()
    flag_conflicts = collections.Counter()
    stat_min_orgs = collections.Counter()
    rows = []
    failed_states = []
    text_seen = {}
    for fips, ab in STATES:
        files = job_files(f"secchi_result_{ab}")
        if files is None:
            failed_states.append(ab)
            continue
        for p in files:
            for r in read_csv(p):
                org = r["OrganizationIdentifier"]
                if r["CharacteristicName"] != SECCHI_CHAR:
                    drops["other_characteristic"] += 1
                    continue
                if r["ResultStatusIdentifier"].strip().lower() == "rejected":
                    drops["status_rejected"] += 1
                    continue
                if NON_ENV_QC.search(r["ActivityTypeCode"]):
                    drops["qc_blank_or_spike_activity"] += 1
                    continue
                if r["ActivityMediaName"] not in ("Water", "Habitat", "Other", ""):
                    drops[f"media_{r['ActivityMediaName']}"] += 1
                    continue
                d = parse_date(r["ActivityStartDate"])
                if d is None or d < START or d > TODAY:
                    drops["date_out_of_range"] += 1
                    continue
                q = {c.upper() for c in re.split(r"[;,\s]+", r["MeasureQualifierCode"].strip()) if c}
                for c in q:
                    qual[f"{c} ({org})"] += 1
                if q & REJECT_Q:
                    drops["qualifier_rejected_or_failed_qc(" + "/".join(sorted(q & REJECT_Q)) + ")"] += 1
                    continue
                if REJECT_COMMENT.search(r["ResultCommentText"]):
                    drops["comment_says_rejected_or_invalid"] += 1
                    continue
                if BAD_SECCHI_COMMENT.search(r["ResultCommentText"]) or BAD_SECCHI_COMMENT.search(r["ActivityCommentText"]):
                    drops["comment_says_secchi_reading_bad"] += 1
                    continue
                unit = r["ResultMeasure/MeasureUnitCode"].strip()
                m, censor, why = parse_secchi_value(r["ResultMeasureValue"], unit)
                if censor == "<" or q & LESS_Q:
                    drops["less_than_censored"] += 1
                    continue
                if m is None:
                    det = r["ResultDetectionConditionText"].strip()
                    drops[why + (f"({det})" if det and why == "no_value" else "")] += 1
                    continue
                units[unit] += 1
                # ---- censoring / bottom-visible evidence
                flags = []  # (true|false, source)
                if censor == ">":
                    flags.append(("true", "value written as '>' or '+'"))
                if q & GREATER_Q:
                    flags.append(("true", "qualifier:" + "/".join(sorted(q & GREATER_Q))))
                if r["StatisticalBaseCode"].strip().lower() == "minimum":
                    flags.append(("true", "StatisticalBaseCode=Minimum"))
                    stat_min_orgs[org] += 1
                det = r["ResultDetectionConditionText"].strip()
                if det in ("Present Above Quantification Limit", "Above Operating Range"):
                    flags.append(("true", f"detection:{det}"))
                less = False
                for col, act in (("ResultCommentText", False), ("ActivityCommentText", True)):
                    t = r[col]
                    if not t:
                        continue
                    f, why = text_flag(t, act)
                    key = (col, " ".join(t.split())[:300])
                    if key not in text_seen:
                        text_seen[key] = [f, why, 0, org]
                    text_seen[key][2] += 1
                    if f == "less":
                        less = True
                    elif f:
                        flags.append((f, why))
                if less and not any(f == "true" for f, _ in flags):
                    drops["less_than_censored"] += 1
                    continue
                items, how = comp_flags.get(r)
                for f, srcname in items:
                    flags.append((f, f"{srcname} ({how})"))
                bds, how = bottom.get(r)
                if bds:
                    bd = max(bds)
                    if m >= bd - 0.05:
                        flags.append(("true", f"secchi >= 'Depth, bottom' ({how})"))
                    else:
                        flags.append(("false", f"secchi < 'Depth, bottom' ({how})"))
                # Any evidence of a censored reading wins over evidence against it.
                bv = "true" if any(f == "true" for f, _ in flags) else "false" if any(f == "false" for f, _ in flags) else ""
                # ---- junk
                if m <= 0:
                    drops["junk_le_0m"] += 1
                    continue
                if m > 30:
                    drops["junk_gt_30m"] += 1
                    continue
                c = site_coords(r, sites, ab, "secchi", drops)
                if c is None:
                    continue
                lat, lon, csrc, s = c
                coord_src[csrc] += 1
                for f, src_ in set(flags):
                    flag_src[f"{f}: {src_}"] += 1
                if bv:
                    flag_orgs[f"{bv}: {org}"] += 1
                if bv == "true" and any(f == "false" for f, _ in flags):
                    flag_conflicts[" + ".join(sorted({s_ for _, s_ in flags}))] += 1
                alat, alon = to_float(r.get("ActivityLocation/LatitudeMeasure")), to_float(r.get("ActivityLocation/LongitudeMeasure"))
                actdist = None
                if csrc == "station" and alat is not None and alon is not None and valid_coord(alat, alon, ab):
                    actdist = haversine_m(lat, lon, alat, alon)
                tz[r["ActivityStartTime/TimeZoneCode"].strip()] += 1
                rows.append({
                    "site_id": r["MonitoringLocationIdentifier"],
                    "site_name": " ".join(((s or {}).get("MonitoringLocationName") or r.get("MonitoringLocationName", "")).split()),
                    "org": org,
                    "lat": fmt(lat, 6), "lon": fmt(lon, 6),
                    "date": d.isoformat(),
                    "time": hhmm(r["ActivityStartTime/Time"]),
                    "time_zone": r["ActivityStartTime/TimeZoneCode"].strip(),
                    "secchi_m": fmt(m, 3),
                    "bottom_visible": bv,
                    "state": ab,
                    "_m": m, "_unit": unit.lower(), "_prov": r["ProviderName"], "_act": r["ActivityIdentifier"],
                    "_pcode": r["USGSPCode"], "_method": r["ResultAnalyticalMethod/MethodIdentifier"].strip().upper(),
                    "_flags": sorted({s_ for f_, s_ in flags if f_ == "true"}),
                    "_actdist": actdist,
                })
    rows, dd = dedupe_secchi(rows)
    for r in rows:   # visit coordinates (ActivityLocation) that disagree with the station's
        d_ = r["_actdist"]
        if d_ is not None and d_ > 100:
            far_actloc[(r["org"], ">5 km" if d_ > 5000 else "1-5 km" if d_ > 1000 else "100 m-1 km")] += 1
    kept = [r for r in rows if r["bottom_visible"] != "true"]
    cens = [dict(r, flag_source="; ".join(r["_flags"])) for r in rows if r["bottom_visible"] == "true"]
    stats["secchi"] = dict(
        failed_states=failed_states, drops=dict(drops.most_common()), dedupe=dd,
        units_seen=dict(units.most_common()), qualifier_codes=dict(qual.most_common()),
        flag_sources=dict(flag_src.most_common()), flag_by_org=dict(flag_orgs.most_common()),
        flag_conflicts_resolved_true=dict(flag_conflicts.most_common()),
        statistical_base_minimum_orgs=dict(stat_min_orgs),
        time_zones=dict(tz.most_common()), coord_source=dict(coord_src),
        visit_coords_over_100m_from_station={f"{o} {b}": n for (o, b), n in far_actloc.most_common()},
        rows_by_org_final=dict(collections.Counter(r["org"] for r in rows).most_common()),
    )
    for (col, t), (f, why, n, org) in text_seen.items():
        review.append((col, f, why, n, org, t))
    return kept, cens


def dedupe_secchi(rows):
    """Collapse repeats of one reading. Distinct replicate readings are kept."""
    counts = collections.Counter()
    by_act = collections.defaultdict(list)
    for r in rows:
        by_act[(r["site_id"], r["_act"])].append(r)
    out = []
    for key, grp in by_act.items():
        if len(grp) > 1 and grp[0]["_prov"] == "NWIS":
            # NWIS: one Secchi reading per sample, reported under several pcodes/units.
            grp.sort(key=lambda r: NWIS_SECCHI_PCODE_RANK.get(r["_pcode"], 9))
            counts["nwis_same_reading_other_pcode"] += len(grp) - 1
            grp = grp[:1]
        if len(grp) > 1 and {r["_method"] for r in grp} >= {"SECCHI", "SECCHI-SCOPE"}:
            # NH DES VLAP: reading with a viewscope next to the standard reading; keep the standard one.
            n = len(grp)
            grp = [r for r in grp if r["_method"] != "SECCHI-SCOPE"]
            counts["nh_viewscope_reading_with_standard_reading"] += n - len(grp)
        if len(grp) > 1:
            # A censored copy makes every copy of the same value censored.
            cens = [r for r in grp if r["bottom_visible"] == "true"]
            for r in grp:
                if r["bottom_visible"] != "true" and any(abs(r["_m"] - c["_m"]) <= max(0.05, 0.03 * c["_m"]) for c in cens):
                    r["bottom_visible"] = "true"
                    r["_flags"] = sorted(set(r["_flags"]) | {"same value flagged in another result of the visit"})
                    counts["uncensored_copy_of_censored_reading_moved"] += 1
            # Same reading in two units (e.g. 25 in + 2.1 ft): keep the metric one.
            grp.sort(key=lambda r: UNIT_RANK.get(r["_unit"], 5))
            keep = []
            for r in grp:
                dup = None
                for k in keep:
                    if r["secchi_m"] == k["secchi_m"]:
                        dup = "same_visit_same_value"
                        break
                    if r["_unit"] != k["_unit"] and abs(r["_m"] - k["_m"]) <= max(0.05, 0.03 * k["_m"]):
                        dup = "same_visit_same_reading_other_unit"
                        break
                if dup:
                    counts[dup] += 1
                else:
                    keep.append(r)
            grp = keep
        out.extend(grp)
    # Re-submissions under another activity id: same site, day, time and value.
    seen = {}
    final = []
    for r in out:
        k = (r["site_id"], r["date"], r["time"], r["secchi_m"])
        if k in seen:
            counts["same_site_day_time_value_other_visit_id"] += 1
            kept = seen[k]
            if r["bottom_visible"] == "true" and kept["bottom_visible"] != "true":
                kept["bottom_visible"] = "true"
                kept["_flags"] = sorted(set(kept["_flags"]) | set(r["_flags"]) | {"flagged in a re-submitted copy"})
                counts["uncensored_copy_of_censored_reading_moved"] += 1
            continue
        seen[k] = r
        final.append(r)
    final, n, moved = dedupe_across_sites(final, ("date", "time", "secchi_m"), censor_key="bottom_visible")
    counts["same_place_day_time_value_other_site_id(other org copy)"] = n
    counts["uncensored_copy_of_censored_reading_moved"] += moved
    return final, dict(counts)


def dedupe_across_sites(rows, keys, censor_key=None):
    """One reading submitted twice under different site ids (e.g. WI_MMSD rows
    re-published by WIDNR, CBA rows re-published by FL LAKEWATCH): same position
    to ~10 m and identical keys. Keeps the copy from the organisation with more
    rows; a censored copy makes the kept copy censored."""
    org_n = collections.Counter(r["org"] for r in rows)
    grp = collections.defaultdict(list)
    for r in rows:
        grp[(round(float(r["lat"]), 4), round(float(r["lon"]), 4)) + tuple(r[k] for k in keys)].append(r)
    out, removed, moved = [], 0, 0
    for g in grp.values():
        if len(g) == 1 or len({r["site_id"] for r in g}) == 1:
            out.extend(g)
            continue
        g.sort(key=lambda r: (-org_n[r["org"]], r["site_id"]))
        keep = g[0]
        if censor_key and keep[censor_key] != "true" and any(r[censor_key] == "true" for r in g):
            src = next(r for r in g if r[censor_key] == "true")
            keep[censor_key] = "true"
            keep["_flags"] = sorted(set(keep["_flags"]) | set(src["_flags"]) | {"flagged in another organisation's copy"})
            moved += 1
        # the other copies are dropped
        out.append(keep)
        removed += len(g) - 1
    return out, removed, moved


def build_turbidity(sites, stats):
    drops = collections.Counter()
    units = collections.Counter()
    atype = collections.Counter()
    kept = []
    failed_states = []
    for fips, ab in STATES:
        files = job_files(f"turb_result_{ab}")
        if files is None:
            failed_states.append(ab)
            continue
        for p in files:
            for r in read_csv(p):
                if r["CharacteristicName"] != TURB_CHAR:
                    drops["other_characteristic"] += 1
                    continue
                if r["ResultStatusIdentifier"].strip().lower() == "rejected":
                    drops["status_rejected"] += 1
                    continue
                if NON_ENV_QC.search(r["ActivityTypeCode"]):
                    drops["qc_blank_or_spike_activity"] += 1
                    continue
                if r["ActivityMediaName"] not in ("Water", "Other", ""):
                    drops[f"media_{r['ActivityMediaName']}"] += 1
                    continue
                d = parse_date(r["ActivityStartDate"])
                if d is None or d < START or d > TODAY:
                    drops["date_out_of_range"] += 1
                    continue
                if r["ResultTimeBasisText"].strip() or r["StatisticalBaseCode"].strip().lower() in ("minimum", "maximum", "delta", "range"):
                    drops["daily_or_logger_statistic(min/max/delta or 1-day basis)"] += 1
                    continue
                q = {c.upper() for c in re.split(r"[;,\s]+", r["MeasureQualifierCode"].strip()) if c}
                if q & REJECT_Q:
                    drops["qualifier_rejected_or_failed_qc(" + "/".join(sorted(q & REJECT_Q)) + ")"] += 1
                    continue
                if REJECT_COMMENT.search(r["ResultCommentText"]):
                    drops["comment_says_rejected_or_invalid"] += 1
                    continue
                det = r["ResultDetectionConditionText"].strip()
                v = r["ResultMeasureValue"].strip().lstrip("=").strip()
                if v.startswith(("<", ">")) or q & LESS_Q or det in CENSOR_DET:
                    drops["censored_or_not_reported" + (f"({det})" if det else "")] += 1
                    continue
                if v == "":
                    drops["no_value"] += 1
                    continue
                x = to_float(v)
                if x is None:
                    drops["non_numeric_value"] += 1
                    continue
                if x < 0:
                    drops["negative_value"] += 1
                    continue
                if x > 4000:   # beyond the range of field turbidimeters/sondes
                    drops["junk_gt_4000"] += 1
                    continue
                unit = r["ResultMeasure/MeasureUnitCode"].strip()
                if unit.upper() not in TURB_UNITS:
                    drops[f"non_turbidity_unit({unit or 'blank'})"] += 1
                    continue
                c = site_coords(r, sites, ab, "turbidity", drops)
                if c is None:
                    continue
                lat, lon, csrc, s = c
                # Sample depth below the surface: activity depth, else result depth, else the
                # top of a reported depth interval; 0 for samples labelled 'Surface'.
                depth = length_m(r["ActivityDepthHeightMeasure/MeasureValue"], r["ActivityDepthHeightMeasure/MeasureUnitCode"])
                if depth is None:
                    depth = length_m(r["ResultDepthHeightMeasure/MeasureValue"], r["ResultDepthHeightMeasure/MeasureUnitCode"])
                if depth is None:
                    depth = length_m(r["ActivityTopDepthHeightMeasure/MeasureValue"], r["ActivityTopDepthHeightMeasure/MeasureUnitCode"])
                if depth is None and r["ActivityRelativeDepthName"].strip().lower() == "surface":
                    depth = 0.0
                units[unit] += 1
                atype[r["ActivityTypeCode"]] += 1
                kept.append({
                    "site_id": r["MonitoringLocationIdentifier"],
                    "site_name": " ".join(((s or {}).get("MonitoringLocationName") or r.get("MonitoringLocationName", "")).split()),
                    "org": r["OrganizationIdentifier"],
                    "lat": fmt(lat, 6), "lon": fmt(lon, 6),
                    "date": d.isoformat(),
                    "time": hhmm(r["ActivityStartTime/Time"]),
                    "value": fmt_value(v, x),
                    "unit": unit,
                    "state": ab,
                    "depth_m": fmt(abs(depth), 3) if depth is not None else "",
                })
    seen = set()
    out = []
    for row in kept:
        k = (row["site_id"], row["date"], row["time"], row["depth_m"], row["value"], row["unit"])
        if k in seen:
            continue
        seen.add(k)
        out.append(row)
    exact = len(kept) - len(out)
    out, cross, _ = dedupe_across_sites(out, ("date", "time", "depth_m", "value", "unit"))
    stats["turbidity"] = dict(failed_states=failed_states, drops=dict(drops.most_common()),
                              units_kept=dict(units.most_common()), activity_types_kept=dict(atype.most_common()),
                              exact_duplicates_removed=exact, same_place_other_site_id_duplicates_removed=cross)
    return out


def write(path, cols, rows):
    rows.sort(key=lambda r: (r["state"], r["site_id"], r["date"], r["time"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


SITE_COLS = ["site_id", "site_name", "org", "lat", "lon", "state", "site_type", "datum", "horizontal_method",
             "huc8", "n_secchi", "n_secchi_censored", "n_turbidity"]


def write_sites(path, sites, secchi, cens, turb):
    """One row per site used in any output file, with the station metadata that
    the per-measurement files leave out (site type, coordinate datum, ...)."""
    n = {k: collections.Counter(r["site_id"] for r in rows) for k, rows in
         (("n_secchi", secchi), ("n_secchi_censored", cens), ("n_turbidity", turb))}
    first = {}
    for rows in (secchi, cens, turb):
        for r in rows:
            first.setdefault(r["site_id"], r)
    out = []
    for sid, r in first.items():
        s = sites.get(sid, {})
        out.append({
            "site_id": sid, "site_name": r["site_name"], "org": r["org"], "lat": r["lat"], "lon": r["lon"],
            "state": r["state"], "site_type": s.get("MonitoringLocationTypeName", ""),
            "datum": s.get("HorizontalCoordinateReferenceSystemDatumName", ""),
            "horizontal_method": s.get("HorizontalCollectionMethodName", ""), "huc8": s.get("HUCEightDigitCode", ""),
            **{k: n[k].get(sid, 0) for k in n},
        })
    out.sort(key=lambda r: (r["state"], r["site_id"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SITE_COLS)
        w.writeheader()
        w.writerows(out)


def main():
    stats = {"built": dt.datetime.now().isoformat(timespec="seconds")}
    sites = load_stations(stats)
    comp_flags, bottom = load_companions(stats)
    review = []
    secchi, cens = build_secchi(sites, comp_flags, bottom, stats, review)
    turb = build_turbidity(sites, stats)
    write(os.path.join(HERE, "secchi.csv"), SECCHI_COLS, secchi)
    write(os.path.join(HERE, "secchi_censored.csv"), SECCHI_COLS + ["flag_source"], cens)
    write(os.path.join(HERE, "turbidity.csv"), TURB_COLS, turb)
    write_sites(os.path.join(HERE, "sites.csv"), sites, secchi, cens, turb)
    review.sort(key=lambda x: (-x[3]))
    with open(os.path.join(HERE, "flag_review.tsv"), "w", encoding="utf-8") as f:
        f.write("column\tflag\treason\tn_rows\texample_org\ttext\n")
        for col, fl, why, n, org, t in review:
            f.write(f"{col}\t{fl}\t{why}\t{n}\t{org}\t{t}\n")
    with open(os.path.join(HERE, "build_stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(f"secchi rows {len(secchi)}, censored {len(cens)}, turbidity rows {len(turb)}")


if __name__ == "__main__":
    main()
