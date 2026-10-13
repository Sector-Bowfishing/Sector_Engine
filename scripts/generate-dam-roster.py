#!/usr/bin/env python3
"""Generate Sources/SectorEngine/Engine/Region/DamRoster.swift.

WHY: WaterContext needs to know, for any scored point, whether it sits on the
water a dam releases into. Distance cones guessed wrong (Guntersville town on
the lake side, the Bull Shoals W-then-S bend), so every roster dam carries the
real NHDPlus downstream-main reach from USGS NLDI plus the USGS sites NLDI
lists on it. That geometry is build-time data, not a runtime fetch.

Pipeline (see docs in the Swift header this script emits):
  1. Seed dams parsed from the engine's own rosters:
       TailwaterRegistry.dams, SWPAGenerationService.projects,
       AlabamaPowerGenerationService.registry.
  2. Every LakeDirectory hasDam lake not covered by a name-matched seed within
     12 mi is anchored from USGS site metadata:
       (a) USACE NID CSV -- NOT USED (not downloaded); lakes it would anchor are
           reported UNANCHORED,
       (b) midpoint of a name-matched pool site and a tailrace/below-dam site
           within 3 mi of it,
       (c) the position of a 'BELOW|BL <name> DAM' gauge.
  3. Every active USGS surface site named BELOW/BL/BLW..DAM or TAILRACE/
     TAILWATER/TW with no roster dam within 3 mi becomes a gauge-named dam.
  Overrides (scripts/data/dam-roster-overrides.json) rename, re-anchor, add or
  drop dams and supply impoundments / rivers / normal pools.
  4. Per dam, NLDI: position -> comid -> 60 km DM flowlines + nwissite. The
     chained flowline is trimmed at the dam's projection (searched over the
     snapped comid plus 3 mi), Douglas-Peucker simplified at 30 m and polyline5
     encoded.
  5. normalPoolFt: 30-day median of a name-matched USGS 00062/62614 site within
     15 mi; else the NWPS table fullPoolFt; else overrides; else nil.

Network: sequential, >= 0.5 s between calls, every response cached by URL hash
so reruns are offline. The cache layout (sha1(url).json) matches the gauge
prototype's nldi/ folder, which can be passed with --extra-cache (read-only).

Usage:
  python3 scripts/generate-dam-roster.py \
      --cache-dir /path/to/cache [--extra-cache DIR ...] [--report FILE] [--offline]
"""
import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "Sources", "SectorEngine")
OUT_SWIFT = os.path.join(SRC, "Engine", "Region", "DamRoster.swift")
OVERRIDES = os.path.join(REPO, "scripts", "data", "dam-roster-overrides.json")

NLDI = "https://api.water.usgs.gov/nldi/linked-data"
NWIS = "https://waterservices.usgs.gov/nwis"

# ----------------------------------------------------------------------------- tunables
SEED_COVER_MILES = 12.0        # a seed name-matched to a hasDam lake within this covers it
POOL_SITE_MILES = 15.0         # pool site search radius around a directory lake point
PAIR_MILES = 3.0               # pool site <-> tailrace site
BELOW_GAUGE_MILES = 15.0       # 'BL <name> DAM' gauge search radius around a directory lake point
GAUGE_DAM_DEDUP_MILES = 3.0    # step 3: no roster dam within this
REACH_KM = 60                  # NLDI DM distance
TRIM_SEARCH_MILES = 3.0        # dam projection search along the chained flowline
SIMPLIFY_M = 30.0              # Douglas-Peucker tolerance
SNAP_FLAG_MILES = 0.25         # coverage report flag
BEHIND_DAM_TOLERANCE_MILES = 0.05
DAM_NOISE_MILES = 0.15         # WaterContext.damNoiseMiles: sites this close are kept regardless
NORMAL_POOL_SITE_MILES = 15.0
MIN_CALL_GAP_S = 0.5

# Tailwaters the gauge-selection rule was validated on (WaterContextTests.
# testGeneratedRosterCoversKnownTailwaters). The report checks each is present
# with a reach and snapMiles <= 0.25.
KNOWN_TAILWATERS = [
    "Buford", "Bull Shoals", "Table Rock", "Beaver", "Norfork", "Greers Ferry", "Allatoona", "Carters",
    "West Point", "Philpott", "Saluda", "Pinopolis", "Bagnell", "Keystone", "Denison", "Tenkiller Ferry",
    "Broken Bow", "Walter F. George", "Livingston", "Hartwell", "J. Strom Thurmond", "Wolf Creek", "Kinzua",
    "Holter", "Folsom", "Gathright", "Beltzville",
]

US_STATES = ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "IA", "ID", "IL", "IN", "KS",
             "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM",
             "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI",
             "WV", "WY"]


# ============================================================================= fetch
class Fetcher:
    def __init__(self, cache_dir, extra_caches, offline):
        self.cache_dir = cache_dir
        self.extra = extra_caches
        self.offline = offline
        self.last_call = 0.0
        self.network_calls = 0
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, d, url, ext):
        return os.path.join(d, hashlib.sha1(url.encode()).hexdigest() + ext)

    def get(self, url, kind="json"):
        ext = ".json" if kind == "json" else ".txt"
        for d in [self.cache_dir] + self.extra:
            p = self._path(d, url, ext)
            if os.path.exists(p):
                with open(p) as f:
                    return json.load(f) if kind == "json" else f.read()
        if self.offline:
            print("offline: missing " + url, file=sys.stderr)
            return None
        for attempt in range(4):
            gap = time.time() - self.last_call
            if gap < MIN_CALL_GAP_S:
                time.sleep(MIN_CALL_GAP_S - gap)
            self.last_call = time.time()
            self.network_calls += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "sector-engine-dam-roster-generator"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    body = r.read().decode("utf-8", "replace")
                payload = json.loads(body) if kind == "json" else body
                p = self._path(self.cache_dir, url, ext)
                with open(p, "w") as f:
                    f.write(body)
                with open(p + ".url", "w") as f:
                    f.write(url)
                return payload
            except urllib.error.HTTPError as e:
                if e.code in (400, 404):
                    # Deterministic "nothing here" -- cache it so reruns stay offline.
                    body = "null" if kind == "json" else ""
                    p = self._path(self.cache_dir, url, ext)
                    with open(p, "w") as f:
                        f.write(body)
                    with open(p + ".url", "w") as f:
                        f.write(url)
                    return None
                print("retry %s: %s" % (url, e), file=sys.stderr)
            except Exception as e:  # noqa: BLE001 - transient network errors are retried
                print("retry %s: %s" % (url, e), file=sys.stderr)
            time.sleep(3 + 4 * attempt)
        return None


# ============================================================================= geometry
def miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p = math.radians
    a = math.sin(p(lat2 - lat1) / 2) ** 2 + math.cos(p(lat1)) * math.cos(p(lat2)) * math.sin(p(lon2 - lon1) / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def xy(lat0, lon0, lat, lon):
    k = 69.0
    return ((lon - lon0) * k * math.cos(math.radians(lat0)), (lat - lat0) * k)


def assemble(first_comid, flowlines):
    """Chain NLDI DM flowlines end->start from the snapped comid. Returns [(lat, lon)]."""
    feats = {str(c): pts for c, pts in flowlines}
    starts = {}
    for c, pts in flowlines:
        starts.setdefault((round(pts[0][0], 5), round(pts[0][1], 5)), str(c))
    first = str(first_comid)
    if first not in feats:
        return []
    line, used = list(feats[first]), {first}
    while True:
        end = line[-1]
        nxt = starts.get((round(end[0], 5), round(end[1], 5)))
        if nxt is None or nxt in used:
            best = None
            for c, pts in flowlines:
                c = str(c)
                if c in used:
                    continue
                dd = miles(end[1], end[0], pts[0][1], pts[0][0])
                if dd < 0.04 and (best is None or dd < best[0]):
                    best = (dd, c)
            if not best:
                break
            nxt = best[1]
        used.add(nxt)
        line += feats[nxt][1:]
    return [(lat, lon) for lon, lat in line]


def project(line, lat, lon, search_miles=None):
    """Nearest location on the polyline -> (miles off, segment index, t, along miles)."""
    best, acc = None, 0.0
    for i in range(len(line) - 1):
        a, b = line[i], line[i + 1]
        bx, by = xy(a[0], a[1], b[0], b[1])
        px, py = xy(a[0], a[1], lat, lon)
        seg = math.hypot(bx, by)
        l2 = seg * seg or 1e-12
        t = max(0.0, min(1.0, (px * bx + py * by) / l2))
        dd = math.hypot(px - t * bx, py - t * by)
        if best is None or dd < best[0]:
            best = (dd, i, t, acc + t * seg)
        acc += seg
        if search_miles is not None and acc > search_miles:
            break
    return best


def trim_at(line, lat, lon, first_miles=0.0):
    """Cut the chained flowline at the dam's projection. The search covers the snapped
    comid itself plus TRIM_SEARCH_MILES: a reservoir's artificial path can run 4+ mi
    above the dam (Hartwell, Saluda), and the dam is on that comid by construction."""
    dd, i, t, along = project(line, lat, lon, first_miles + TRIM_SEARCH_MILES)
    a, b = line[i], line[i + 1]
    q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    rest = line[i + 1:]
    if rest and miles(q[0], q[1], rest[0][0], rest[0][1]) < 1e-4:
        rest = rest[1:]
    return [q] + rest, dd, along


def simplify(points, tol_m):
    """Douglas-Peucker in a local equirectangular frame (metres)."""
    if len(points) < 3:
        return list(points)
    lat0, lon0 = points[0]
    m_per_mile = 1609.344
    pts = [tuple(v * m_per_mile for v in xy(lat0, lon0, la, lo)) for la, lo in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        s, e = stack.pop()
        ax, ay = pts[s]
        bx, by = pts[e]
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        worst, wi = -1.0, None
        for k in range(s + 1, e):
            px, py = pts[k]
            if l2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
                d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
            if d > worst:
                worst, wi = d, k
        if wi is not None and worst > tol_m:
            keep[wi] = True
            stack.append((s, wi))
            stack.append((wi, e))
    return [p for p, k in zip(points, keep) if k]


def encode_polyline(points, precision=5):
    """Google encoded polyline, (lat, lon) order."""
    factor = 10 ** precision
    out, plat, plon = [], 0, 0
    for lat, lon in points:
        ilat, ilon = int(round(lat * factor)), int(round(lon * factor))
        for delta in (ilat - plat, ilon - plon):
            v = ~(delta << 1) if delta < 0 else (delta << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


def decode_polyline(s, precision=5):
    factor = 10 ** precision
    idx, lat, lon, out = 0, 0, 0, []
    while idx < len(s):
        vals = []
        for _ in range(2):
            shift, result = 0, 0
            while True:
                b = ord(s[idx]) - 63
                idx += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            vals.append(~(result >> 1) if result & 1 else result >> 1)
        lat += vals[0]
        lon += vals[1]
        out.append((lat / factor, lon / factor))
    return out


# ============================================================================= names
# Port of the GaugeClassifier name-key rules (spec rule A, "Name key").
GENERIC = {"LAKE", "LAKES", "LK", "L", "RESERVOIR", "RES", "RESV", "POND", "THE", "OF", "POOL", "IMPOUNDMENT",
           "DAM", "RIVER", "R", "RIV", "RV", "AND", "LCRA"}
LOCATORS = {"AT", "NR", "NEAR", "BL", "BLW", "BELOW", "ABV", "ABOVE", "AB", "IN", "ON", "US", "DS", "UPSTREAM",
            "DOWNSTREAM", "@", "OFF", "BTWN", "BETWEEN", "BY"}
COMPASS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
BELOW = {"BELOW", "BL", "BLW", "BLO"}
TAIL = {"TAILRACE", "TAILWATER", "TW"}
DAMW = {"DAM", "L&D", "LOCK", "POWERHOUSE", "SPILLWAY"}
LAKEW = {"LAKE", "LAKES", "LK", "RESERVOIR", "RES", "RESV", "POND", "IMPOUNDMENT", "FOREBAY", "HEADWATER", "POOL"}
RIVERW = {"RIVER", "R", "RIV", "RV", "WW", "WATERWAY"}
TRIBW = {"CREEK", "CR", "CK", "CRK", "BROOK", "BR", "BRANCH", "RUN", "BAYOU", "SLOUGH", "TRIBUTARY", "TRIB",
         "DITCH", "DRAIN", "SWAMP", "CANAL", "SPRING", "SPRINGS", "SPGS", "SPG", "GULCH", "WASH", "HOLLOW", "HOLW"}
ROAD = {"RD", "ROAD", "HWY", "HIGHWAY", "BRIDGE", "AVE", "PIKE", "LANE", "LN", "DR", "DRIVE", "ST", "STREET"}
SURFACE_TYPES = {"ST", "ST-CA", "ST-DCH", "ST-TS", "LK", "ES", "WE", "OC-CO"}
KEY_NORM = {"CK": "CREEK", "CR": "CREEK", "CRK": "CREEK", "MT": "MOUNT", "ST": "SAINT", "FT": "FORT"}


def tokens(s):
    s = re.sub(r"&(apos|#39);|['’`]", " ", s)
    s = re.sub(r"&amp;", "&", s).upper()
    s = re.sub(r"L\s*&\s*D", " L&D ", s)
    s = re.sub(r"[^A-Z0-9&]+", " ", s)
    return [t for t in s.split() if t]


def waterbody_phrase(tks):
    out = []
    for i, t in enumerate(tks):
        nxt = tks[i + 1] if i + 1 < len(tks) else ""
        if out and (t in LOCATORS or re.search(r"\d", t) or (t in COMPASS and nxt == "OF")):
            break
        out.append(t)
    return out


def ordered_key(phrase):
    merged, i = [], 0
    while i < len(phrase):
        t = phrase[i]
        if t == "C" and i + 1 < len(phrase) and phrase[i + 1] in LAKEW:
            merged.append("CREEK")
            i += 1
            continue
        if len(t) == 1 and i + 1 < len(phrase) and phrase[i + 1] not in GENERIC:
            merged.append(t + phrase[i + 1])
            i += 2
            continue
        merged.append(t)
        i += 1
    return tuple(KEY_NORM.get(t, t) for t in merged
                 if t not in GENERIC and len(t) > 1 and not re.fullmatch(r"[A-Z]{2}", t))


def lake_aliases(name):
    base = re.sub(r"\(.*?\)", " ", name)
    al = [ordered_key(tokens(base))]
    for part in base.split("/"):
        k = ordered_key(tokens(part))
        if k and k not in al:
            al.append(k)
    for inner in re.findall(r"\((.*?)\)", name):
        if not re.fullmatch(r"[A-Za-z]{2}", inner.strip()):
            k = ordered_key(tokens(inner))
            if k and k not in al:
                al.append(k)
    return [a for a in al if a]


def keys_match(key, aliases):
    if not key:
        return False
    for a in aliases:
        if a and (key[-len(a):] == a or a[-len(key):] == key):
            return True
    return False


def dam_key(name):
    """Distinctive words of a dam name: 'Walter F. George Dam' -> ('WALTERFGEORGE'...)."""
    return ordered_key([t for t in tokens(name) if t not in DAMW and t not in {"AND", "NO"}])


def classify_role(name, site_type):
    """Coarse role (enough for anchoring): pool / damRelease / river / tributary / other."""
    st = (site_type or "").upper()
    tks = tokens(name)
    dam_hit = any(t in DAMW and not (i + 1 < len(tks) and tks[i + 1] in ROAD) for i, t in enumerate(tks))
    wb = waterbody_phrase(tks)
    wbset, allset = set(wb), set(tks)
    if st and st not in SURFACE_TYPES:
        return "nonSurface"
    if (allset & TAIL) or ((allset & BELOW) and (dam_hit or (allset & LAKEW))) or \
            (dam_hit and (wbset & RIVERW) and not (wbset & LAKEW)):
        return "damRelease"
    if st == "LK" and not ((wbset & RIVERW) and not (wbset & LAKEW)):
        return "pool"
    if wbset & LAKEW:
        return "pool"
    for t in wb:
        if t in RIVERW:
            return "river"
        if t in TRIBW:
            return "tributary"
    return "other"


NAME_EXPAND = {"C": "CREEK", "CK": "CREEK", "CR": "CREEK", "CYN": "CANYON", "DIV": "DIVERSION", "MTN": "MOUNTAIN",
               "MT": "MOUNT", "LWR": "LOWER", "UPR": "UPPER", "PP": "POWERPLANT", "RVR": "RIVER", "RIV": "RIVER",
               "RV": "RIVER", "R": "RIVER", "FK": "FORK", "BR": "BRANCH"}
NAME_NOISE = {"HW", "NO", "UNIT", "OUTLET", "U", "(TW)", "LOW", "FLOW", "STATION"}
PLACE_STOP = {"AT", "NR", "NEAR"}
ABOVE = {"AB", "ABV", "ABOVE", "US", "UPSTREAM"}


def name_words(tks):
    """Display words for a name fragment: initials kept ('R B RUSSELL' -> R. B. Russell),
    abbreviations expanded where they are not initials ('PROSSER C' -> Prosser Creek)."""
    out = []
    for i, t in enumerate(tks):
        nxt = tks[i + 1] if i + 1 < len(tks) else None
        prv = tks[i - 1] if i > 0 else None
        if len(t) == 1 and t.isalpha() and nxt and len(nxt) == 1 and nxt.isalpha():
            out.append(t + ".")
        elif len(t) == 1 and t.isalpha() and prv and len(prv) == 1 and prv.isalpha() and nxt and nxt not in LOCATORS:
            out.append(t + ".")
        elif t in NAME_NOISE or t == "&":
            continue
        elif t in NAME_EXPAND and i > 0:
            out.append(NAME_EXPAND[t])
        else:
            out.append(t)
    return out


def titlecase(words):
    small = {"OF", "AND", "THE"}
    out = []
    for i, w in enumerate(words):
        if w.endswith(".") or w == "L&D":
            out.append(w)
        elif w in small and i > 0:
            out.append(w.lower())
        else:
            out.append(w[0] + w[1:].lower())
    return " ".join(out)


def place_of(tks):
    """'... NEAR KENT CLIFFS NY' -> 'Kent Cliffs'. NR/NEAR beats AT ('AT LK MARION TAILRACE NR PINEVILLE')."""
    order = [i for i, t in enumerate(tks) if t in {"NR", "NEAR"} and i > 0] + \
            [i for i, t in enumerate(tks) if t == "AT" and i > 0]
    for i in order:
        if True:
            words = []
            for w in tks[i + 1:]:
                if w in LOCATORS or re.search(r"\d", w) or (len(w) == 2 and w in US_STATES):
                    break
                words.append(w)
            if words:
                return titlecase(name_words(words))
    return None


def dam_mentions(tks):
    """Indices of DAM tokens that are dams, not roads ('SUWANEE DAM ROAD')."""
    return [i for i, t in enumerate(tks) if t == "DAM" and not (i + 1 < len(tks) and tks[i + 1] in ROAD)]


def below_dam(tks):
    """A BELOW word followed by a dam with no other locator between: 'BL TABLE ROCK DAM'.
    Not 'BLW TANGLE CREEK, ABV HORSESHOE DAM' -- that gauge is above Horseshoe."""
    for i, t in enumerate(tks):
        if t not in BELOW:
            continue
        for j in dam_mentions(tks):
            if j > i and not any(x in LOCATORS for x in tks[i + 1:j]):
                return True
    return False


def at_dam(tks):
    """'ARKANSAS RIVER AT MURRAY DAM' / 'CHATTAHOOCHEE RIVER BUFORD DAM' -- at the dam, not above it."""
    for j in dam_mentions(tks):
        before = tks[:j]
        if any(x in ABOVE for x in before):
            return False
        return True
    return False


def release_gauge(site):
    """A gauge on the water leaving a dam, for pair anchoring: TAILRACE/TW, below a dam, or at a dam."""
    tks = tokens(site["name"])
    return site["role"] == "damRelease" and (bool(set(tks) & TAIL) or below_dam(tks) or at_dam(tks))


def named_dam(name):
    """'WHITE RIVER BL TABLE ROCK DAM NR BRANSON' -> 'Table Rock Dam'. None when the name gives no dam words."""
    tks = tokens(name)
    for i in dam_mentions(tks):
        words, j = [], i - 1
        while j >= 0:
            w = tks[j]
            initial = len(w) == 1 and w.isalpha() and j + 1 < i and len(tks[j + 1]) == 1
            if not initial and (w in LOCATORS or w in TAIL or re.search(r"\d", w)
                                or (w in RIVERW and not (j + 1 < i and len(tks[j + 1]) == 1))):
                break
            words.insert(0, w)
            j -= 1
        if words and words[-1] == "&" and words[-2:-1] == ["LOCK"]:
            words = words[:-2]
        if "LOCK" in tks[max(0, i - 2):i]:
            num = next((t for t in tks[i + 1:i + 2] if t.isdigit()), "")
            river = river_of(name)
            return ("%s Lock and Dam %s" % (river or "", num)).strip().replace("  ", " ")
        words = [w for w in words if w not in GENERIC or w in {"LAKE"}]
        words = name_words(words)
        if words and not all(w in GENERIC for w in words):
            return titlecase(words) + " Dam"
    return None


def river_of(site_name):
    """River name from a gauge name's water-body phrase: 'WHITE RIVER AT CALICO ROCK' -> 'White'."""
    wb = waterbody_phrase(tokens(site_name))
    for i, t in enumerate(wb):
        if t in RIVERW and i > 0 and not (i + 1 < len(wb) and len(wb[i + 1]) == 1):
            words = [w for w in wb[:i] if w not in GENERIC]
            if words:
                return titlecase(name_words(words))
    return None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ============================================================================= sources
def read(path):
    with open(os.path.join(SRC, path)) as f:
        return f.read()


def parse_directory():
    src = read("Support/LakeDirectory.swift")
    out = []
    for m in re.finditer(r'DirectoryLake\(name: "([^"]+)", state: "(\w+)", states: \[([^\]]*)\], '
                         r'lat: ([-\d.]+), lon: ([-\d.]+), hasDam: (\w+)', src):
        out.append(dict(name=m.group(1), state=m.group(2), states=re.findall(r'"(\w+)"', m.group(3)),
                        lat=float(m.group(4)), lon=float(m.group(5)), hasDam=m.group(6) == "true",
                        id="%s|%s" % (m.group(1), m.group(2)), aliases=lake_aliases(m.group(1))))
    return out


def parse_seeds():
    seeds = []
    src = read("Engine/Region/TailwaterRegistry.swift")
    for m in re.finditer(r'Dam\("([^"]+)", ([-\d.]+), ([-\d.]+), downstream: ([\d.]+)\)', src):
        seeds.append(dict(name=m.group(1), lat=float(m.group(2)), lon=float(m.group(3)), river=None,
                          lake=None, source="TailwaterRegistry", scoresTailwater=True))
    src = read("Engine/Adapters/SWPAGenerationService.swift")
    for m in re.finditer(r'Project\(abbr: "(\w+)", name: "([^"]+)",\s*lake: "([^"]+)",\s*river: "([^"]+)",'
                         r'\s*latitude: ([-\d.]+), longitude: ([-\d.]+)', src):
        seeds.append(dict(name=m.group(2), lat=float(m.group(5)), lon=float(m.group(6)), river=m.group(4),
                          lake=m.group(3), source="SWPA", scoresTailwater=False))
    src = read("Engine/Adapters/AlabamaPowerGenerationService.swift")
    for m in re.finditer(r'name: "([^"]+)",\s*river: "([^"]+)",\s*lat: ([-\d.]+), lon: ([-\d.]+)', src):
        seeds.append(dict(name=m.group(1) + " Dam", lat=float(m.group(3)), lon=float(m.group(4)),
                          river=m.group(2), lake=m.group(1), source="APC", scoresTailwater=False))
    # One entry per name, first source wins (TailwaterRegistry, then SWPA, then APC).
    seen, out = set(), []
    for s in seeds:
        if s["name"] not in seen:
            seen.add(s["name"])
            out.append(s)
    return out


def parse_nwps_pools():
    src = read("Fetchers/WaterLevelService.swift")
    return {m.group(1): float(m.group(2))
            for m in re.finditer(r'ReservoirGauge\(name: "([^"]+)",\s*lid: "\w+", fullPoolFt: ([\d.]+)', src)}


def parse_rdb(text):
    rows, header = [], None
    for line in (text or "").splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if header is None:
            header = cols
            continue
        if cols and re.fullmatch(r"\d+[sdn]", cols[0]):
            continue
        rows.append(dict(zip(header, cols)))
    return rows


def _site_rows(text, state):
    out = {}
    for r in parse_rdb(text):
        try:
            lat, lon = float(r["dec_lat_va"]), float(r["dec_long_va"])
        except (KeyError, ValueError):
            continue
        try:
            alt = float(r.get("alt_va") or "nan")
        except ValueError:
            alt = float("nan")
        s = dict(site=r["site_no"], name=r["station_nm"], type=r["site_tp_cd"], lat=lat, lon=lon,
                 alt=None if math.isnan(alt) else alt, state=state)
        s["role"] = classify_role(s["name"], s["type"])
        s["okey"] = ordered_key(waterbody_phrase(tokens(s["name"])))
        s["tokens"] = set(tokens(s["name"]))
        out[s["site"]] = s
    return out


def load_sites(fetcher):
    """-> (active, anchors, pool_code_sites).

    active: real-time surface sites (step 3 and the normal-pool lookup).
    anchors: active plus every discontinued ST/LK gauging station with an IV or DV
      record. Sites don't move when they stop reporting, and USACE Savannah
      District's dams (Hartwell, Thurmond) only have discontinued USGS pool/
      tailrace pairs -- the active list alone leaves them unanchored.
    pool_code_sites: active sites publishing 00062/62614/62615 in IV.
    """
    active, anchors, pool_code_sites = {}, {}, set()
    for st in US_STATES:
        url = "%s/site/?format=rdb&stateCd=%s&siteStatus=active&siteType=ST,LK&hasDataTypeCd=iv" % (NWIS, st)
        active.update(_site_rows(fetcher.get(url, kind="text"), st))
        url = "%s/site/?format=rdb&stateCd=%s&siteStatus=all&siteType=ST,LK&hasDataTypeCd=iv,dv" % (NWIS, st)
        anchors.update(_site_rows(fetcher.get(url, kind="text"), st))
        url = ("%s/site/?format=rdb&stateCd=%s&siteStatus=active&hasDataTypeCd=iv"
               "&parameterCd=00062,62614,62615" % (NWIS, st))
        for r in parse_rdb(fetcher.get(url, kind="text")):
            pool_code_sites.add(r["site_no"])
    for k, v in active.items():
        anchors.setdefault(k, v)
    return active, anchors, pool_code_sites


# ============================================================================= roster assembly
def load_overrides():
    with open(OVERRIDES) as f:
        return json.load(f)


def related(site, aliases):
    """The gauge's own name (before 'NEAR <town>') carries every word of one of the lake's aliases."""
    tks = tokens(site["name"])
    cut = next((i for i, t in enumerate(tks) if t in {"NR", "NEAR"} and i > 0), len(tks))
    own = set(tks[:cut])
    return any(a and set(a) <= own for a in aliases)


def lake_base_dam_name(lake_name):
    base = re.sub(r"\(.*?\)", " ", lake_name).split("/")[0]
    words = [w for w in re.split(r"\s+", base.strip())
             if w and w.upper().strip(".") not in {"LAKE", "RESERVOIR", "RES", "POND"}]
    return (" ".join(words) or base.strip()) + " Dam"


def site_named_dam(site):
    """Dam name a tailrace/below-dam gauge implies.

    '<words> DAM' names it outright. '<lake> TAILRACE' names the lake ('LAKE GREENWOOD
    TAILRACE' -> Greenwood Dam). A river tailwater or an unnamed 'BELOW DAM' only
    says which river and town ('FOX RIVER (TAILWATER) NEAR MCHENRY' -> Fox River Dam
    near Mchenry): four Fox River dams must not all be 'Fox Dam'.
    """
    n = named_dam(site["name"])
    if n:
        return n
    tks = tokens(site["name"])
    stop = next((i for i, t in enumerate(tks) if t in TAIL or t == "DAM"), None)
    if stop is None:
        return None
    phrase = waterbody_phrase(tks[:stop]) if stop else []
    phrase = [w for w in phrase if w not in BELOW]
    if any(w in RIVERW for w in phrase) or "DAM" in tks[stop:stop + 1]:
        river = river_of(site["name"]) or titlecase(name_words([w for w in phrase if w not in GENERIC] or ["UNNAMED"]))
        place = place_of(tks)
        return "%s River Dam%s" % (river, (" near " + place) if place else "")
    words = name_words([w for w in phrase if w not in GENERIC])
    return (titlecase(words) + " Dam") if words else None


def new_dam(name, lat, lon, source, **kw):
    d = dict(name=name, lat=lat, lon=lon, source=source, river=None, lakeName=None, lakeID=None,
             scoresTailwater=False, anchor=None, state=None)
    d.update(kw)
    return d


def nearest_dam(dams, lat, lon):
    best = None
    for d in dams:
        m = miles(d["lat"], d["lon"], lat, lon)
        if best is None or m < best[0]:
            best = (m, d)
    return best


def assign_impoundment(dam, directory, radius):
    """Nearest hasDam directory lake whose name matches the dam's lake (or the dam's own name words)."""
    keys = lake_aliases(dam["lakeName"]) if dam["lakeName"] else [dam_key(dam["name"])]
    best = None
    for lake in directory:
        if not lake["hasDam"]:
            continue
        m = miles(dam["lat"], dam["lon"], lake["lat"], lake["lon"])
        if m > radius:
            continue
        if any(keys_match(a, keys) for a in lake["aliases"]) and (best is None or m < best[0]):
            best = (m, lake)
    return best


def build_roster(fetcher, overrides, report):
    directory = parse_directory()
    by_lake_id = {l["id"]: l for l in directory}
    active, anchors, pool_code_sites = load_sites(fetcher)
    dam_over = overrides.get("dams", {})
    lake_over = overrides.get("lakes", {})
    dropped = set(overrides.get("drop", []))

    def site_coord(codes):
        pts = [anchors[c] for c in codes if c in anchors]
        if len(pts) != len(codes):
            raise SystemExit("override anchor site missing from USGS site lists: %s" % codes)
        return (sum(p["lat"] for p in pts) / len(pts), sum(p["lon"] for p in pts) / len(pts))

    def apply_coordinate_override(d):
        o = dam_over.get(d["name"], {})
        if "anchorSites" in o:
            d["lat"], d["lon"] = (round(v, 5) for v in site_coord(o["anchorSites"]))
            d["source"], d["anchor"] = "override", "override: USGS site(s) %s" % "/".join(o["anchorSites"])
        elif "lat" in o:
            d["lat"], d["lon"], d["source"] = o["lat"], o["lon"], "override"
            d["anchor"] = "override: " + o.get("note", "")

    # ---- 1. seeds
    dams = []
    for s in parse_seeds():
        dams.append(new_dam(s["name"], s["lat"], s["lon"], s["source"], river=s["river"], lakeName=s["lake"],
                            scoresTailwater=s["scoresTailwater"]))
    for d in dams:
        # Before anything measures distance from a seed: a corrected coordinate must
        # drive coverage and the step-3 3-mile dedupe too.
        apply_coordinate_override(d)
        o = dam_over.get(d["name"], {})
        if "impoundmentLakeID" in o:
            d["lakeID"] = o["impoundmentLakeID"]
            d["lakeName"] = by_lake_id[o["impoundmentLakeID"]]["name"] if o["impoundmentLakeID"] else None
        else:
            hit = assign_impoundment(d, directory, 30.0)
            if hit:
                d["lakeID"], d["lakeName"] = hit[1]["id"], hit[1]["name"]
        if "impoundmentName" in o:
            d["lakeName"] = o["impoundmentName"]

    # ---- 2. LakeDirectory hasDam lakes
    def covered(lake):
        for d in dams:
            if d["lakeID"] == lake["id"]:
                return "impounded by %s" % d["name"]
        for d in dams:
            keys = lake_aliases(d["lakeName"]) if d["lakeName"] else [dam_key(d["name"])]
            m = miles(d["lat"], d["lon"], lake["lat"], lake["lon"])
            if any(keys_match(a, keys) for a in lake["aliases"]):
                if d["source"] in ("TailwaterRegistry", "SWPA", "APC") and m <= SEED_COVER_MILES:
                    return "name-matched seed %s (%.1f mi)" % (d["name"], m)
                if m <= 60 and d["lakeID"] and d["lakeID"] != lake["id"]:
                    return "same-name directory row, impounded by %s (%.1f mi)" % (d["name"], m)
        return None

    for lake in sorted((l for l in directory if l["hasDam"]), key=lambda l: l["id"]):
        why = covered(lake)
        if why:
            report["covered"].append((lake["id"], why))
            continue
        lo = lake_over.get(lake["id"], {})
        anchor = None
        if "anchorSites" in lo:
            lat, lon = site_coord(lo["anchorSites"])
            anchor = dict(lat=lat, lon=lon, source="override",
                          how="override: USGS site(s) %s" % "/".join(lo["anchorSites"]),
                          name=lo.get("damName"), sites=[anchors[c] for c in lo["anchorSites"]])
        elif "lat" in lo:
            anchor = dict(lat=lo["lat"], lon=lo["lon"], source="override", how="override: " + lo.get("note", ""),
                          name=lo.get("damName"), sites=[])
        if anchor is None:
            # (b) pool site + tailrace/below-dam site within 3 mi.
            pairs = []
            for p in anchors.values():
                if p["role"] != "pool" or not keys_match(p["okey"], lake["aliases"]):
                    continue
                if miles(lake["lat"], lake["lon"], p["lat"], p["lon"]) > POOL_SITE_MILES:
                    continue
                for t in anchors.values():
                    if not release_gauge(t):
                        continue
                    sep = miles(p["lat"], p["lon"], t["lat"], t["lon"])
                    if sep > PAIR_MILES:
                        continue
                    rel = related(t, lake["aliases"])
                    if not rel and sep > 1.5:
                        continue   # an unrelated release gauge that far off is another dam (Cheat Lake vs L&D 8)
                    pairs.append((0 if rel else 1, sep, p["site"], t["site"], p, t))
            if pairs:
                _, sep, _, _, p, t = min(pairs, key=lambda x: x[:4])
                lat, lon, how = (p["lat"] + t["lat"]) / 2, (p["lon"] + t["lon"]) / 2, "midpoint"
                ttks = tokens(t["name"])
                if sep > 1.0 and ((set(ttks) & TAIL) or (at_dam(ttks) and not below_dam(ttks))):
                    # Far apart, and the release gauge says it is AT the dam: the midpoint
                    # would sit a mile out on the lake (Lake Ouachita vs Blakely Mtn Dam).
                    lat, lon, how = t["lat"], t["lon"], "release gauge (at the dam)"
                anchor = dict(lat=lat, lon=lon, source="USGS pair",
                              how="USGS pair %s/%s (%.2f mi apart, %s)" % (p["site"], t["site"], sep, how),
                              name=lo.get("damName") or site_named_dam(t) or named_dam(p["name"]), sites=[p, t],
                              state=lake["state"])
        if anchor is None:
            # (c) 'BELOW|BL <name> DAM' gauge.
            cands = []
            for t in anchors.values():
                nd = named_dam(t["name"])
                if t["role"] != "damRelease" or not nd or not below_dam(tokens(t["name"])):
                    continue
                if not any(keys_match(dam_key(nd), [a]) for a in lake["aliases"]):
                    continue
                m = miles(lake["lat"], lake["lon"], t["lat"], t["lon"])
                if m <= BELOW_GAUGE_MILES:
                    cands.append((m, t["site"], t, nd))
            if cands:
                m, _, t, nd = min(cands, key=lambda x: x[:2])
                anchor = dict(lat=t["lat"], lon=t["lon"], source="USGS below-dam gauge",
                              how="USGS below-dam gauge %s" % t["site"], name=lo.get("damName") or nd, sites=[t])
        if anchor is None:
            report["unanchored"].append((lake["id"], "no NID (not used), no USGS pool/tailrace pair, "
                                                     "no 'BELOW <name> DAM' gauge"))
            continue
        near = nearest_dam(dams, anchor["lat"], anchor["lon"])
        if near and near[0] <= 1.0:
            if not near[1]["lakeID"]:
                near[1]["lakeID"], near[1]["lakeName"] = lake["id"], lake["name"]
            report["covered"].append((lake["id"], "anchor %.2f mi from roster dam %s" % (near[0], near[1]["name"])))
            continue
        name = anchor["name"] or lake_base_dam_name(lake["name"])
        river = None
        for s in anchor["sites"]:
            river = river or river_of(s["name"])
        dams.append(new_dam(name, round(anchor["lat"], 5), round(anchor["lon"], 5), anchor["source"],
                            lakeID=lake["id"], lakeName=lake["name"], river=river, anchor=anchor["how"],
                            state=lake["state"]))

    # ---- overrides: extra dams
    for extra in overrides.get("add", []):
        if "anchorSites" in extra:
            lat, lon = site_coord(extra["anchorSites"])
            how = "override: USGS site(s) %s" % "/".join(extra["anchorSites"])
        else:
            lat, lon, how = extra["lat"], extra["lon"], "override: " + extra.get("note", "")
        dams.append(new_dam(extra["name"], round(lat, 5), round(lon, 5), "override", river=extra.get("river"),
                            lakeID=extra.get("impoundmentLakeID"),
                            lakeName=extra.get("impoundmentName") or (
                                by_lake_id[extra["impoundmentLakeID"]]["name"] if extra.get("impoundmentLakeID") else None),
                            anchor=how))

    # ---- 3. gauge-named dams (active sites only)
    for s in sorted(active.values(), key=lambda x: (len(x["site"]) != 8, x["site"])):
        if s["role"] == "nonSurface":
            continue
        tks = tokens(s["name"])
        if not (below_dam(tks) or (s["tokens"] & TAIL)):
            continue
        if set(waterbody_phrase(tks)) & {"CANAL", "DITCH", "DRAIN"}:
            # A diversion canal below a dam is not the river the dam releases into.
            report["gaugeSkipped"].append((s["site"], s["name"], "canal/ditch"))
            continue
        name = site_named_dam(s)
        if not name:
            report["gaugeUnnamed"].append((s["site"], s["name"]))
            continue
        near = nearest_dam(dams, s["lat"], s["lon"])
        if near and near[0] <= GAUGE_DAM_DEDUP_MILES:
            continue
        d = new_dam(name, s["lat"], s["lon"], "USGS below-dam gauge", river=river_of(s["name"]),
                    anchor="USGS gauge-named dam %s '%s'" % (s["site"], s["name"]), state=s["state"])
        hit = assign_impoundment(dict(d, lakeName=None), directory, 15.0)
        if hit and not any(x["lakeID"] == hit[1]["id"] for x in dams):
            d["lakeID"], d["lakeName"] = hit[1]["id"], hit[1]["name"]
        dams.append(d)

    # ---- unique names: the operator rosters keep theirs; a later namesake gets its state
    # ("Wilson Dam" is TVA's; the Kansas one becomes "Wilson Dam (KS)").
    taken = set()
    for d in dams:
        if d["name"] in taken:
            d["name"] = "%s (%s)" % (d["name"], d.get("state") or "%.2f,%.2f" % (d["lat"], d["lon"]))
        n, k = d["name"], 2
        while d["name"] in taken:
            d["name"] = "%s #%d" % (n, k)
            k += 1
        taken.add(d["name"])

    # ---- per-dam overrides (rename / coordinate / river / impoundment), drops
    out = []
    for d in dams:
        if d["name"] in dropped:
            report["dropped"].append(d["name"])
            continue
        if d["source"] != "override":
            apply_coordinate_override(d)
        o = dam_over.get(d["name"], {})
        if "river" in o:
            d["river"] = o["river"]
        if "rename" in o:
            d["name"] = o["rename"]
        out.append(d)
    return out, directory, active, pool_code_sites


# ============================================================================= reach + pool
def nldi_reach(fetcher, dam):
    pos = fetcher.get("%s/comid/position?f=json&coords=POINT(%.5f%%20%.5f)" % (NLDI, dam["lon"], dam["lat"]))
    if not pos or not pos.get("features"):
        return None, "NLDI position returned no comid"
    comid = pos["features"][0]["properties"]["comid"]
    fl = fetcher.get("%s/comid/%s/navigation/DM/flowlines?f=json&distance=%d" % (NLDI, comid, REACH_KM))
    st = fetcher.get("%s/comid/%s/navigation/DM/nwissite?f=json&distance=%d" % (NLDI, comid, REACH_KM))
    flowlines = [(f["properties"]["nhdplus_comid"], f["geometry"]["coordinates"])
                 for f in (fl or {}).get("features", []) if f.get("geometry")]
    line = assemble(comid, flowlines)
    if len(line) < 2:
        return None, "NLDI flowlines empty for comid %s" % comid
    first = next((pts for c, pts in flowlines if str(c) == str(comid)), [])
    first_miles = sum(miles(a[1], a[0], b[1], b[0]) for a, b in zip(first, first[1:]))
    reach, snap, dam_along = trim_at(line, dam["lat"], dam["lon"], first_miles)
    simplified = simplify(reach, SIMPLIFY_M)
    sites, behind = set(), []
    for f in (st or {}).get("features", []):
        code = f["properties"]["identifier"].replace("USGS-", "")
        lon, lat = f["geometry"]["coordinates"][:2]
        _, _, _, along = project(line, lat, lon)
        # NLDI lists sites on the whole first catchment, which starts in the pool
        # above the dam. A forebay gauge is not on the downstream reach. Within
        # DAM_NOISE_MILES of the dam the projection is noise for a release gauge
        # (Holter's sits 0.05 mi from the dam), but a pool-named site there at or
        # above the dam's projection is still the forebay (Lanier 02334400).
        # A gauge whose name says it measures the release ('TAILWATER', 'BELOW
        # DALE HOLLOW DAM') is never dropped: a 2-decimal dam coordinate can sit
        # below its own tailrace gauge.
        site_name = f["properties"].get("name") or ""
        role = classify_role(site_name, None)
        if role == "damRelease" and release_gauge(dict(role=role, name=site_name)):
            sites.add(code)
            continue
        near_dam = miles(lat, lon, dam["lat"], dam["lon"]) <= DAM_NOISE_MILES
        if (along < dam_along - BEHIND_DAM_TOLERANCE_MILES and not near_dam) or \
                (role == "pool" and near_dam and along <= dam_along + BEHIND_DAM_TOLERANCE_MILES):
            behind.append(code)
            continue
        sites.add(code)
    names = [f["properties"].get("name") or "" for f in (st or {}).get("features", [])]
    return dict(comid=comid, reach=simplified, rawVertices=len(reach), snapMiles=snap, sites=sites,
                behind=behind, siteNames=names), None


def median_pool(fetcher, site, alt):
    """30-day median of the site's pool elevation series; None when the series is local-datum or missing."""
    def series_values(payload):
        best = None
        for ts in ((payload or {}).get("value") or {}).get("timeSeries", []):
            code = ts["variable"]["variableCode"][0]["value"]
            for block in ts.get("values", []):
                method = " ".join((m.get("methodDescription") or "") for m in block.get("method", [])).upper()
                if "TAIL" in method or "LOWER" in method:
                    continue
                vals = []
                for v in block.get("value", []):
                    try:
                        x = float(v["value"])
                    except (TypeError, ValueError):
                        continue
                    if x > -999:
                        vals.append(x)
                if not vals:
                    continue
                rank = {"62614": 0, "00062": 1, "62615": 2}.get(code, 9)
                if best is None or (rank, -len(vals)) < best[0]:
                    best = ((rank, -len(vals)), code, vals)
        return best
    url = "%s/dv/?format=json&sites=%s&parameterCd=00062,62614,62615&period=P30D&siteStatus=all" % (NWIS, site)
    best = series_values(fetcher.get(url))
    if best is None:
        url = "%s/iv/?format=json&sites=%s&parameterCd=00062,62614,62615&period=P30D&siteStatus=all" % (NWIS, site)
        best = series_values(fetcher.get(url))
    if best is None:
        return None, None
    med = statistics.median(best[2])
    if alt is not None and alt > 50 and med < alt * 0.5:
        return None, "local datum (%s median %.2f vs gauge datum %.1f)" % (best[1], med, alt)
    return round(med, 2), best[1]


def normal_pool(fetcher, dam, active, pool_code_sites, nwps, overrides):
    if dam["lakeName"]:
        aliases = lake_aliases(dam["lakeName"])
        cands = []
        for s in active.values():
            if s["site"] not in pool_code_sites or s["role"] != "pool" or not keys_match(s["okey"], aliases):
                continue
            m = miles(dam["lat"], dam["lon"], s["lat"], s["lon"])
            if m <= NORMAL_POOL_SITE_MILES:
                cands.append((m, s["site"], s))
        for m, _, s in sorted(cands, key=lambda x: x[:2]):
            med, code = median_pool(fetcher, s["site"], s["alt"])
            if med is not None:
                return med, "USGS %s %s 30-day median" % (s["site"], code)
        for name, ft in nwps.items():
            if keys_match(ordered_key(tokens(name)), aliases):
                return ft, "NWPS table %s" % name
    o = overrides.get("dams", {}).get(dam["name"], {})
    if "normalPoolFt" in o:
        return float(o["normalPoolFt"]), "override"
    return None, None


# ============================================================================= emit
def swift_str(s):
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def swift_opt_str(s):
    return "nil" if s is None else swift_str(s)


def emit_swift(dams, counts):
    lines = []
    for d in dams:
        pool = "nil" if d["normalPoolFt"] is None else ("%.2f" % d["normalPoolFt"]).rstrip("0").rstrip(".")
        if pool != "nil" and "." not in pool:
            pool += ".0"
        codes = ", ".join(swift_str(c) for c in sorted(d["sites"]))
        lines.append(
            "        RosterDam(id: %s, name: %s, latitude: %.5f, longitude: %.5f, coordinateSource: %s, "
            "river: %s, impoundmentLakeID: %s, impoundmentName: %s, normalPoolFt: %s, "
            "encodedReach: #\"%s\"#, reachSiteCodes: [%s], snapMiles: %.3f, scoresTailwater: %s),"
            % (swift_str(d["id"]), swift_str(d["name"]), d["lat"], d["lon"], swift_str(d["source"]),
               swift_str(d["river"] or ""), swift_opt_str(d["lakeID"]), swift_opt_str(d["lakeName"]), pool,
               d["encoded"], codes, d["snapMiles"], "true" if d["scoresTailwater"] else "false"))
    return SWIFT_HEADER % counts + SWIFT_TYPES + "\n".join(lines) + "\n" + SWIFT_FOOTER


SWIFT_HEADER = '''//
//  DamRoster.swift
//  Sector — dam roster with NHDPlus tailwater reaches (GENERATED — do not hand-edit)
//
//  Regenerate with: python3 scripts/generate-dam-roster.py --cache-dir <dir>
//  Hand corrections go in scripts/data/dam-roster-overrides.json, never here.
//
//  WaterContext decides "is this point on the lake, below a dam, or neither"
//  from this data. Distance cones got it wrong where rivers bend (Bull Shoals
//  runs W then S) and where a town sits on the lake side of the dam, so every
//  dam carries its real downstream-main reach: the USGS NLDI NHDPlus flowline
//  from the dam's projection %(reach_km)d km downstream, Douglas-Peucker simplified at
//  %(simplify_m)d m and polyline5 encoded, plus the USGS sites NLDI lists on it.
//
//  Dam coordinates, in priority order:
//    TailwaterRegistry / SWPA / APC — the engine's own operator rosters;
//    USGS pair — midpoint of a lake's pool gauge and its tailrace gauge;
//    USGS below-dam gauge — a 'BELOW <name> DAM' / TAILRACE gauge position;
//    override — scripts/data/dam-roster-overrides.json, verified from USGS sites.
//  The USACE NID was not used; lakes only it could anchor are listed UNANCHORED
//  in the generator's coverage report.
//
//  snapMiles is the distance from the dam coordinate to the NHDPlus flowline.
//  Above 0.25 mi the 1-mile face logic in WaterContext is unreliable for that
//  dam; the report flags those for coordinate review.
//
//  %(dams)d dams, %(tailwater)d from TailwaterRegistry. scoresTailwater mirrors
//  TailwaterRegistry membership for diagnostics only — TailwaterRegistry.isTailwater
//  stays the scoring authority.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

'''

SWIFT_TYPES = r'''/// One dam and the river it releases into. Provenance is in the file header.
struct RosterDam: Equatable, Identifiable, Sendable {
    let id: String
    let name: String
    let latitude: Double
    let longitude: Double
    /// "TailwaterRegistry" | "SWPA" | "APC" | "USGS pair" | "USGS below-dam gauge" | "override".
    let coordinateSource: String
    /// River leaving the dam, from the operator roster or the reach's USGS gauge
    /// names. Empty when neither names one. Informational.
    let river: String
    /// `DirectoryLake.id` of the reservoir behind the dam, when LakeDirectory lists it.
    let impoundmentLakeID: String?
    let impoundmentName: String?
    /// Pool elevation (ft) to compare ground and gauge elevations against when no
    /// live generation pool matches: a name-matched USGS pool gauge's 30-day
    /// median, else NWPS full pool, else a hand value. A typical level, not a
    /// datum — good to a few feet, which is all the 3 ft / 50 ft tests need.
    let normalPoolFt: Double?
    /// Google polyline (precision 5, lat/lon order). The first vertex is the dam's
    /// projection onto the NHDPlus flowline; the reach runs downstream from there.
    let encodedReach: String
    /// USGS site codes NLDI lists on the reach, minus forebay sites behind the dam.
    /// Incomplete by nature (NLDI omitted Keystone's 07164480), which is why
    /// GaugeSelector also tests geometry.
    let reachSiteCodes: Set<String>
    /// Dam coordinate to flowline distance. Above 0.25 mi the coordinate needs review.
    let snapMiles: Double
    /// True only for TailwaterRegistry dams. Diagnostics only; scoring still asks
    /// TailwaterRegistry.isTailwater.
    let scoresTailwater: Bool
    /// `encodedReach`, decoded when the value is built. `DamRoster.all` is a lazily
    /// initialised static, so the roster decodes once on first use and the hot
    /// path (every render's WaterContext.resolve) never parses a string.
    let reach: [(lat: Double, lon: Double)]

    var coordinate: CLLocationCoordinate2D { .init(latitude: latitude, longitude: longitude) }

    init(id: String, name: String, latitude: Double, longitude: Double, coordinateSource: String,
         river: String, impoundmentLakeID: String?, impoundmentName: String?, normalPoolFt: Double?,
         encodedReach: String, reachSiteCodes: Set<String>, snapMiles: Double, scoresTailwater: Bool) {
        self.id = id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.coordinateSource = coordinateSource
        self.river = river
        self.impoundmentLakeID = impoundmentLakeID
        self.impoundmentName = impoundmentName
        self.normalPoolFt = normalPoolFt
        self.encodedReach = encodedReach
        self.reachSiteCodes = reachSiteCodes
        self.snapMiles = snapMiles
        self.scoresTailwater = scoresTailwater
        self.reach = Self.decodePolyline(encodedReach)
    }

    /// Fixture initialiser: tests describe a reach by its vertices, not an encoded
    /// string. Vertices round to 1e-5° (about a metre) through the encoding, the
    /// same precision the generated roster carries.
    init(id: String, name: String, latitude: Double, longitude: Double, coordinateSource: String = "fixture",
         river: String = "", impoundmentLakeID: String? = nil, impoundmentName: String? = nil,
         normalPoolFt: Double? = nil, reach: [(lat: Double, lon: Double)], reachSiteCodes: Set<String> = [],
         snapMiles: Double = 0, scoresTailwater: Bool = false) {
        self.init(id: id, name: name, latitude: latitude, longitude: longitude, coordinateSource: coordinateSource,
                  river: river, impoundmentLakeID: impoundmentLakeID, impoundmentName: impoundmentName,
                  normalPoolFt: normalPoolFt, encodedReach: Self.encodePolyline(reach),
                  reachSiteCodes: reachSiteCodes, snapMiles: snapMiles, scoresTailwater: scoresTailwater)
    }

    /// `reach` is derived from `encodedReach`, and tuples aren't Equatable.
    static func == (a: RosterDam, b: RosterDam) -> Bool {
        a.id == b.id && a.name == b.name && a.latitude == b.latitude && a.longitude == b.longitude
            && a.coordinateSource == b.coordinateSource && a.river == b.river
            && a.impoundmentLakeID == b.impoundmentLakeID && a.impoundmentName == b.impoundmentName
            && a.normalPoolFt == b.normalPoolFt && a.encodedReach == b.encodedReach
            && a.reachSiteCodes == b.reachSiteCodes && a.snapMiles == b.snapMiles
            && a.scoresTailwater == b.scoresTailwater
    }

    // MARK: Polyline5

    /// Decodes a Google encoded polyline. Malformed input stops at the last whole
    /// vertex rather than trapping — generated data is trusted, fixtures aren't.
    static func decodePolyline(_ encoded: String) -> [(lat: Double, lon: Double)] {
        let bytes = Array(encoded.utf8)
        var out: [(lat: Double, lon: Double)] = []
        out.reserveCapacity(bytes.count / 4)
        var index = 0, lat = 0, lon = 0
        func next() -> Int? {
            var result = 0, shift = 0
            while index < bytes.count {
                let b = Int(bytes[index]) - 63
                index += 1
                guard b >= 0, shift < 60 else { return nil }
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20 { return (result & 1) != 0 ? ~(result >> 1) : result >> 1 }
            }
            return nil
        }
        while index < bytes.count {
            guard let dLat = next(), let dLon = next() else { break }
            lat += dLat
            lon += dLon
            out.append((lat: Double(lat) / 1e5, lon: Double(lon) / 1e5))
        }
        return out
    }

    static func encodePolyline(_ vertices: [(lat: Double, lon: Double)]) -> String {
        var scalars: [UInt8] = []
        var prevLat = 0, prevLon = 0
        func append(_ delta: Int) {
            var v = delta < 0 ? ~(delta << 1) : (delta << 1)
            while v >= 0x20 {
                scalars.append(UInt8((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            }
            scalars.append(UInt8(v + 63))
        }
        for vertex in vertices {
            let lat = Int((vertex.lat * 1e5).rounded()), lon = Int((vertex.lon * 1e5).rounded())
            append(lat - prevLat)
            append(lon - prevLon)
            prevLat = lat
            prevLon = lon
        }
        return String(decoding: scalars, as: UTF8.self)
    }
}

enum DamRoster {

    /// Roster dams within `miles` of `coordinate`, nearest first, with their
    /// distance in miles. A haversine prefilter: callers do polyline math only on
    /// what survives, so a render touches a handful of reaches, not the roster.
    /// `roster` exists for fixtures.
    static func dams(within miles: Double, of coordinate: CLLocationCoordinate2D,
                     in roster: [RosterDam] = DamRoster.all) -> [(RosterDam, Double)] {
        // A degree of latitude is ~69 mi everywhere; skip the trig for the obvious misses.
        let latSlack = miles / 69.0 + 0.01
        var hits: [(RosterDam, Double)] = []
        for dam in roster where abs(dam.latitude - coordinate.latitude) <= latSlack {
            let d = TailwaterRegistry.haversineMiles(lat1: coordinate.latitude, lon1: coordinate.longitude,
                                                     lat2: dam.latitude, lon2: dam.longitude)
            if d <= miles { hits.append((dam, d)) }
        }
        return hits.sorted { $0.1 < $1.1 }
    }

    static let all: [RosterDam] = [
'''

SWIFT_FOOTER = "    ]\n}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-dir", default=os.path.join(REPO, ".build", "dam-roster-cache"))
    ap.add_argument("--extra-cache", action="append", default=[], help="read-only response cache (sha1(url).json)")
    ap.add_argument("--report", help="write the coverage report here too")
    ap.add_argument("--offline", action="store_true", help="never touch the network; missing responses are skipped")
    ap.add_argument("--out", default=OUT_SWIFT)
    args = ap.parse_args()

    fetcher = Fetcher(args.cache_dir, args.extra_cache, args.offline)
    overrides = load_overrides()
    report = dict(covered=[], unanchored=[], dropped=[], gaugeUnnamed=[], gaugeSkipped=[], noReach=[])
    dams, directory, active, pool_code_sites = build_roster(fetcher, overrides, report)
    nwps = parse_nwps_pools()

    built = []
    for i, d in enumerate(dams):
        r, err = nldi_reach(fetcher, d)
        if r is None:
            report["noReach"].append((d["name"], d["source"], err))
            continue
        d.update(encoded=encode_polyline(r["reach"]), vertices=len(r["reach"]), rawVertices=r["rawVertices"],
                 snapMiles=round(r["snapMiles"], 3), sites=r["sites"], behind=r["behind"])
        if not d["river"]:
            for n in r["siteNames"]:
                d["river"] = river_of(n)
                if d["river"]:
                    break
        d["normalPoolFt"], d["poolSource"] = normal_pool(fetcher, d, active, pool_code_sites, nwps, overrides)
        built.append(d)
        if (i + 1) % 50 == 0:
            print("  %d/%d dams (%d network calls)" % (i + 1, len(dams), fetcher.network_calls), file=sys.stderr)

    # Stable order and ids.
    built.sort(key=lambda d: (d["name"], d["lat"], d["lon"]))
    seen = {}
    for d in built:
        base = slug(d["name"])
        seen[base] = seen.get(base, 0) + 1
        d["id"] = base if seen[base] == 1 else "%s-%d" % (base, seen[base])

    counts = dict(reach_km=REACH_KM, simplify_m=int(SIMPLIFY_M), dams=len(built),
                  tailwater=sum(1 for d in built if d["scoresTailwater"]))
    with open(args.out, "w") as f:
        f.write(emit_swift(built, counts))

    # ---- report
    lines = ["Dam roster coverage report", "=" * 26, ""]
    lines.append("Dams emitted: %d (TailwaterRegistry %d, SWPA %d, APC %d, USGS pair %d, USGS below-dam gauge %d, "
                 "override %d)" % (len(built), *[sum(1 for d in built if d["source"] == s) for s in
                                                   ("TailwaterRegistry", "SWPA", "APC", "USGS pair",
                                                    "USGS below-dam gauge", "override")]))
    verts = [d["vertices"] for d in built]
    raw = [d["rawVertices"] for d in built]
    lines.append("Reach vertices: mean %.0f simplified (mean %.0f raw), total %d; encoded bytes %d"
                 % (statistics.mean(verts), statistics.mean(raw), sum(verts), sum(len(d["encoded"]) for d in built)))
    lines.append("Network calls this run: %d" % fetcher.network_calls)
    lines.append("")
    by_name = {d["name"]: d for d in built}
    problems = []
    for k in KNOWN_TAILWATERS:
        d = by_name.get(k + " Dam")
        if d is None:
            problems.append("%s Dam: MISSING" % k)
        elif d["snapMiles"] > SNAP_FLAG_MILES:
            problems.append("%s Dam: snapMiles %.2f" % (k, d["snapMiles"]))
    lines.append("Known tailwaters (spec list, %d): %s" % (len(KNOWN_TAILWATERS),
                                                          "all present, snapMiles <= 0.25" if not problems
                                                          else "; ".join(problems)))
    lines.append("")
    flagged = [d for d in built if d["snapMiles"] > SNAP_FLAG_MILES]
    lines.append("snapMiles > %.2f (coordinate review): %d" % (SNAP_FLAG_MILES, len(flagged)))
    for d in sorted(flagged, key=lambda d: -d["snapMiles"]):
        lines.append("  %-34s %5.2f mi  [%s] %s" % (d["name"], d["snapMiles"], d["source"], d["anchor"] or ""))
    lines.append("")
    apc = [d for d in built if d["source"] == "APC"]
    lines.append("APC seeds still on AlabamaPowerGenerationService's impoundment reference points "
                 "(no USGS gauge names the dam; the reach may start in the lake -- needs NID): %d" % len(apc))
    for d in apc:
        lines.append("  %-34s snap %.2f" % (d["name"], d["snapMiles"]))
    lines.append("")
    lines.append("UNANCHORED hasDam lakes (NID would be the next source; not used): %d" % len(report["unanchored"]))
    for lid, why in report["unanchored"]:
        lines.append("  " + lid)
    lines.append("")
    lines.append("Dams without an NLDI reach (not emitted): %d" % len(report["noReach"]))
    for n, s, e in report["noReach"]:
        lines.append("  %s [%s]: %s" % (n, s, e))
    lines.append("")
    lines.append("Dropped by override: %s" % (", ".join(report["dropped"]) or "none"))
    lines.append("Gauge-named sites with no derivable dam name: %d" % len(report["gaugeUnnamed"]))
    for code, n in report["gaugeUnnamed"]:
        lines.append("  %s %s" % (code, n))
    lines.append("")
    lines.append("hasDam lakes covered without a new dam: %d" % len(report["covered"]))
    for lid, why in report["covered"]:
        lines.append("  %-45s %s" % (lid, why))
    lines.append("")
    lines.append("All dams:")
    for d in built:
        lines.append("  %-34s %9.5f %10.5f snap %.2f  verts %3d  sites %2d (behind dam %d)  pool %s (%s)  lake %s  [%s]%s"
                     % (d["name"], d["lat"], d["lon"], d["snapMiles"], d["vertices"], len(d["sites"]),
                        len(d["behind"]), d["normalPoolFt"], d["poolSource"], d["lakeID"], d["source"],
                        (" " + d["anchor"]) if d["anchor"] else ""))
    text = "\n".join(lines) + "\n"
    print(text)
    if args.report:
        with open(args.report, "w") as f:
            f.write(text)


if __name__ == "__main__":
    main()
