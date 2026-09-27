#!/usr/bin/env python3
"""Regenerate Sources/SectorEngine/Support/LakeDirectory.swift from the research sheet.

    python3 scripts/generate-lake-directory.py

THE ENGINE OWNS THE LAKE LIST (2026-09-26). It serves it at `GET /lakes`, and the
iOS and Android apps download it, cache it and search it; a lake added here
reaches both on their next launch. After regenerating, deploy, then refresh the
apps' bundled fallback (a first launch with no network) from the response:

    curl -s <engine>/lakes > <app>/lake_directory.json

The sheet (docs/data/Sector_Lakes_APIs_2.xlsx) is a PER-STATE inventory, so a
reservoir on a state line appears once per state it touches. Pickwick is listed
three times — AL "Pickwick", MS "Pickwick Lake", TN "Pickwick Lake" — and the
app faithfully rendered all three in search. One lake, one row.

Merging on name alone would be wrong: 19 name collisions in this sheet are
genuinely DIFFERENT lakes hundreds of miles apart (several states have a "Long
Lake"). So rows merge only when the normalized name matches AND the coordinates
are within MERGE_RADIUS_MI of each other, via single-linkage clustering.

Name normalization mirrors LakeDirectorySearch.normalize exactly — if the two
drift, search stops finding merged entries.
"""

import html
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "docs/data/Sector_Lakes_APIs_2.xlsx"
OUT = ROOT / "Sources/SectorEngine/Support/LakeDirectory.swift"

# Same water split across a state line sits well inside this. The nearest pair
# of genuinely-different same-named lakes in the sheet is far outside it.
MERGE_RADIUS_MI = 25.0

# Must match LakeDirectorySearch.normalize.
STOP = {"lake", "lakes", "reservoir", "res", "pond", "the", "of"}


def normalize(s: str) -> str:
    cleaned = "".join(c if c.isalnum() else " " for c in s.lower())
    return " ".join(t for t in cleaned.split() if t not in STOP)


def miles(a, b):
    (lat1, lon1), (lat2, lon2) = a, b
    r = 3958.8
    dla, dlo = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = (math.sin(dla / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlo / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


# The columns the directory reads, BY HEADER. They were read by letter, and
# the 2026-08-06 edit inserted three pool columns after "Coord Conf": every
# later column shifted, and a regenerate read operators, gages and water-temp
# sources out of the wrong cells.
COLUMNS = {
    "state": "State", "lake": "Lake", "lat": "Latitude", "lon": "Longitude",
    "conf": "Coord Conf", "dam": "Dam?", "operator": "Managing Operator",
    "api": "API Level", "gage": "USGS Gage", "temp": "Water Temp — Best Source",
    "pool": "Full Pool (ft)", "poolBasis": "Pool Basis",
}


def read_rows():
    """The sheet's data rows, each keyed by the COLUMNS keys."""
    z = zipfile.ZipFile(SHEET)
    shared = re.findall(r"<si>(.*?)</si>",
                        z.read("xl/sharedStrings.xml").decode("utf-8", "replace"), re.S)
    # Cell text is XML: "Coeur d&apos;Alene" has to reach the app as "Coeur d'Alene".
    shared = [html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", s, re.S))) for s in shared]
    xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    out = []
    for raw in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
        cells = {}
        for ref, attrs, body in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', raw, re.S):
            v = re.search(r"<v>(.*?)</v>", body, re.S)
            if not v:
                continue
            cells[ref] = shared[int(v.group(1))] if 't="s"' in attrs else v.group(1)
        out.append(cells)
    header = {html.unescape(v).strip(): ref for ref, v in out[0].items()}
    missing = [h for h in COLUMNS.values() if h not in header]
    if missing:
        sys.exit(f"sheet has no column {missing}; headers are {sorted(header)}")
    return [{key: row.get(header[h]) for key, h in COLUMNS.items()} for row in out[1:]]


CONF_RANK = {"high": 0, "med": 1, "medium": 1, "low": 2}

# USACE district -> CWMS office code. The sheet names the district in prose
# ("USACE Little Rock", "USACE Louisville (LRL)"), and CWMS is partitioned by
# these codes — so this column IS the routing table for observed data. Codes in
# parentheses win; otherwise the district name is matched.
DISTRICT_TO_OFFICE = {
    "little rock": "SWL", "tulsa": "SWT", "fort worth": "SWF", "galveston": "SWG",
    "nashville": "LRN", "louisville": "LRL", "huntington": "LRH", "pittsburgh": "LRP",
    "buffalo": "LRB", "chicago": "LRC", "detroit": "LRE",
    "st. louis": "MVS", "st louis": "MVS", "rock island": "MVR", "vicksburg": "MVK",
    "memphis": "MVM", "new orleans": "MVN", "st. paul": "MVP", "st paul": "MVP",
    "kansas city": "NWK", "omaha": "NWO", "walla walla": "NWW", "portland": "NWP",
    "seattle": "NWS",
    "mobile": "SAM", "savannah": "SAS", "wilmington": "SAW", "charleston": "SAC",
    "jacksonville": "SAJ",
    "baltimore": "NAB", "philadelphia": "NAP", "new york": "NAN", "norfolk": "NAO",
    "new england": "NAE",
    "albuquerque": "SPA", "los angeles": "SPL", "sacramento": "SPK",
}

# Verified CWMS office corrections, keyed by COORDINATE (not name — there is an
# AL "Jordan" and an NC "Jordan Lake"; only the location tells them apart). Each
# entry was confirmed against the live CWMS Data API to return a fresh pool,
# tailwater, or outflow reading at the stated office — the sheet either left the
# office blank or named the wrong district. A cluster within OVERRIDE_RADIUS_MI
# of one of these points takes the listed office.
#   (lake, lat, lon, office)
OFFICE_OVERRIDES = [
    # Sheet had the WRONG district — these lakes have data under another office.
    ("Mississinewa Lake", 40.72, -85.96, "LRC"),
    ("Kanopolis Lake",    38.62, -98.00, "SWT"),
    ("Cave Run Lake",     38.13, -83.53, "LRL"),
    ("Broken Bow Lake",   34.14, -94.68, "SWL"),
    ("Laurel River Lake", 36.83, -84.24, "LRN"),
    # Sheet left the office BLANK, but the lake name-matches a live CWMS project.
    ("Bankhead",          33.46, -87.36, "SAM"),
    ("Jordan",            32.62, -86.26, "SAM"),
    ("Lake Martin",       32.82, -85.92, "SAM"),
    ("Logan Martin",      33.43, -86.34, "SAM"),
    ("Lewis Smith Lake",  34.05, -87.11, "SAM"),
    ("Weiss",             34.17, -85.55, "SAM"),
    ("Bartlett",          33.82, -111.63, "SPL"),
    ("Havasu",            34.30, -114.14, "SPL"),
    ("Roosevelt",         33.67, -111.16, "SPL"),
    ("Don Pedro",         37.70, -120.42, "SPK"),
    ("Folsom",            38.71, -121.16, "SPK"),
    ("Oroville",          39.54, -121.49, "SPK"),
    ("Shasta",            40.72, -122.42, "SPK"),
    ("Pueblo Reservoir",  38.26, -104.72, "SPA"),
    ("Cheney Reservoir",  37.72, -97.79, "SWT"),
    ("Cross Lake",        32.53, -93.90, "MVK"),
    ("Lake Bistineau",    32.42, -93.42, "MVK"),
    ("Ross Barnett Reservoir", 32.43, -89.94, "MVK"),
    ("Lake Darling",      48.55, -101.52, "MVP"),
    ("Caballo Lake",      32.90, -107.30, "SPA"),
    ("El Vado Lake",      36.58, -106.73, "SPA"),
    ("Heron Lake",        36.68, -106.68, "SPA"),
    ("Sumner Lake",       34.61, -104.38, "SPA"),
    ("Lake Milton",       41.10, -80.96, "LRP"),
    ("Lake Hudson",       36.21, -95.16, "SWT"),
    ("Pymatuning Reservoir", 41.63, -80.47, "LRP"),
    ("Lake Jocassee",     34.95, -82.93, "SAS"),
    ("Lake Keowee",       34.79, -82.90, "SAS"),
    ("Pineview Reservoir", 41.25, -111.85, "SPK"),
    ("Claytor Lake",      37.05, -80.62, "LRH"),
    ("Cheat Lake",        39.72, -79.86, "LRP"),
]
OVERRIDE_RADIUS_MI = 12.0


def override_office(lat, lon):
    """The verified office for a cluster at (lat, lon), or None."""
    for _, olat, olon, office in OFFICE_OVERRIDES:
        if miles((lat, lon), (olat, olon)) <= OVERRIDE_RADIUS_MI:
            return office
    return None

# Ranked best-first, so a merged cluster keeps its richest routing.
API_LEVELS = ["dedicated", "usgsOnly", "none"]
GAGE_LEVELS = ["yes", "likely", "no"]
TEMP_SOURCES = ["buoy", "inSitu", "satellite", "limited"]


def parse_api_level(v):
    v = (v or "").strip().lower()
    if v.startswith("dedicated"): return "dedicated"
    if v.startswith("usgs"): return "usgsOnly"
    return "none"


def parse_gage(v):
    v = (v or "").strip().lower()
    return {"yes": "yes", "likely": "likely"}.get(v, "no")


def parse_temp_source(v):
    v = (v or "").strip().lower()
    if "buoy" in v: return "buoy"
    if "in-situ" in v or "in situ" in v: return "inSitu"
    if "satellite" in v: return "satellite"
    return "limited"


def parse_office(op):
    """CWMS office for a USACE-run project, else None."""
    o = (op or "").strip()
    if "usace" not in o.lower():
        return None
    code = re.search(r"\(([A-Z]{3})\)", o)          # explicit "(LRL)"
    if code:
        return code.group(1)
    low = o.lower()
    for name, office in DISTRICT_TO_OFFICE.items():
        if name in low:
            return office
    return None


# Lakes verified to belong in the directory but MISSING from the research sheet.
# Same shape as a parsed sheet row; added to `rows` so they cluster + dedup like
# everything else (conf=1 so their coordinate wins any merge). Add here when a
# real, coverable lake never shows up in search because the sheet skipped it.
# Verified full pool per lake, keyed by directory id ("Name|ST"). The sheet's
# "Full Pool (ft)" column was checked against the operators' own data (TVA's
# operating guide, USACE CWMS location levels) and researched per lake for the
# rest: about 1 in 8 of its "High" values was top of gates, top of dam or a
# flood pool. Where TVA or CWMS publishes the level, the CSV takes THEIR
# number, in the same datum as the live pool reading the engine compares it
# with. A lake missing from the CSV falls back to the sheet's column, as low;
# a CSV row with no number means the research found none, and nothing is kept.
FULL_POOL_CSV = ROOT / "docs/data/full_pool.csv"
TEMP_SENSORS_CSV = ROOT / "docs/data/temp_sensors.csv"
POOL_BASES = {"fullPool", "naturalSurface"}
POOL_CONFS = {"high", "med", "low"}


def read_full_pools():
    import csv
    out = {}
    with open(FULL_POOL_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if not row["fullPoolFt"].strip():
                out[row["id"].strip()] = None
                continue
            basis, conf = row["basis"].strip(), row["conf"].strip()
            if basis not in POOL_BASES or conf not in POOL_CONFS:
                sys.exit(f"full_pool.csv: bad basis/conf for {row['id']}: {basis!r} {conf!r}")
            out[row["id"].strip()] = (float(row["fullPoolFt"]), basis, conf)
    return out


def read_temp_sensors():
    """Lake id -> its own surface temperature sensor ("usgs:<site>" or
    "cwms:<office>:<time-series id>"): a sensor inside the lake's outline,
    reporting within the last 30 days when the table was built."""
    import csv
    if not TEMP_SENSORS_CSV.exists():
        return {}
    with open(TEMP_SENSORS_CSV, newline="") as f:
        return {r["id"].strip(): r["sensor"].strip() for r in csv.DictReader(f) if r["sensor"].strip()}


def sheet_pool(c):
    """The sheet's own full-pool columns, as (ft, basis, conf) or None."""
    try:
        ft = float(c["pool"])
    except (TypeError, ValueError):
        return None
    basis = "naturalSurface" if "natural" in (c["poolBasis"] or "").lower() else "fullPool"
    return ft, basis, "low"


MANUAL_ADDITIONS = [
    # Nickajack Reservoir — TVA, Tennessee River between Chickamauga and
    # Guntersville. It's in TVA's generation feed and the app's reservoir-gauge
    # table, but the sheet omitted it, so lake search couldn't find it at all.
    {"name": "Nickajack Lake", "state": "TN", "lat": 35.03, "lon": -85.53,
     "conf": 1, "dam": True, "operator": "TVA", "api": "dedicated",
     "gage": "yes", "temp": "inSitu", "office": None, "pool": None},
]


def main():
    rows = []
    for c in read_rows():
        name, state = (c["lake"] or "").strip(), (c["state"] or "").strip()
        try:
            lat, lon = float(c["lat"]), float(c["lon"])
        except (TypeError, ValueError):
            continue
        if not name or not state:
            continue
        rows.append({
            "name": name, "state": state, "lat": lat, "lon": lon,
            "conf": CONF_RANK.get((c["conf"] or "").strip().lower(), 3),
            "dam": (c["dam"] or "").strip().lower() == "yes",
            "operator": (c["operator"] or "").strip(),
            "api": parse_api_level(c["api"]),
            "gage": parse_gage(c["gage"]),
            "temp": parse_temp_source(c["temp"]),
            "office": parse_office(c["operator"]),
            "pool": sheet_pool(c),
        })

    # Curated lakes the sheet missed (see MANUAL_ADDITIONS).
    rows.extend(MANUAL_ADDITIONS)

    # Group by normalized name, then split each group into proximity clusters.
    groups = defaultdict(list)
    for r in rows:
        groups[normalize(r["name"])].append(r)

    clusters, merged_count = [], 0
    for _, members in groups.items():
        pending, buckets = list(members), []
        while pending:
            seed = pending.pop()
            bucket = [seed]
            changed = True
            while changed:                      # single-linkage
                changed = False
                for cand in list(pending):
                    if any(miles((cand["lat"], cand["lon"]), (m["lat"], m["lon"])) <= MERGE_RADIUS_MI
                           for m in bucket):
                        bucket.append(cand)
                        pending.remove(cand)
                        changed = True
            buckets.append(bucket)
        for b in buckets:
            if len(b) > 1:
                merged_count += 1
            clusters.append(b)

    entries = []
    for b in clusters:
        # Canonical name: most common spelling, ties broken toward the longer
        # one so "Pickwick Lake" wins over "Pickwick".
        counts = Counter(m["name"] for m in b)
        top = max(counts.values())
        name = sorted([n for n, c in counts.items() if c == top], key=lambda n: (-len(n), n))[0]
        # Best coordinate = highest stated confidence.
        best = sorted(b, key=lambda m: m["conf"])[0]
        states = [best["state"]] + sorted({m["state"] for m in b} - {best["state"]})
        def best_of(field, order):
            vals = [m[field] for m in b]
            return sorted(vals, key=lambda v: order.index(v) if v in order else len(order))[0]
        entries.append({
            "name": name, "state": best["state"], "states": states,
            "lat": best["lat"], "lon": best["lon"],
            "dam": any(m["dam"] for m in b),
            # A merged cluster keeps its RICHEST routing: if any state's row
            # knows the lake has a dedicated API or a real gage, the lake does.
            "operator": best["operator"] or next((m["operator"] for m in b if m["operator"]), ""),
            "api": best_of("api", API_LEVELS),
            "gage": best_of("gage", GAGE_LEVELS),
            "temp": best_of("temp", TEMP_SOURCES),
            # Verified coordinate override wins over the sheet's district when one
            # applies; otherwise keep the richest office any member row carried.
            "office": override_office(best["lat"], best["lon"])
                      or next((m["office"] for m in b if m["office"]), None),
        })

    full_pools = read_full_pools()
    for e, b in zip(entries, clusters):
        key = f'{e["name"]}|{e["state"]}'
        e["pool"] = full_pools[key] if key in full_pools \
            else next((m["pool"] for m in sorted(b, key=lambda m: m["conf"]) if m["pool"]), None)
    unused = set(full_pools) - {f'{e["name"]}|{e["state"]}' for e in entries}
    if unused:
        sys.exit(f"full_pool.csv lists lakes the directory doesn't have: {sorted(unused)}")
    sensors = read_temp_sensors()
    unused = set(sensors) - {f'{e["name"]}|{e["state"]}' for e in entries}
    if unused:
        sys.exit(f"temp_sensors.csv lists lakes the directory doesn't have: {sorted(unused)}")
    for e in entries:
        e["tempSensor"] = sensors.get(f'{e["name"]}|{e["state"]}')

    entries.sort(key=lambda e: (e["states"][0], e["name"]))

    def swift_str(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = [
        "//",
        "//  LakeDirectory.swift",
        "//  Sector — curated US lake registry (GENERATED — do not hand-edit)",
        "//",
        "//  Source: docs/data/Sector_Lakes_APIs_2.xlsx (Michael's research).",
        "//  Regenerate with: python3 scripts/generate-lake-directory.py",
        "//",
        "//  The free-text MapKit lake search was unreliable (\"Wheeler\" -> a",
        "//  Wisconsin lake, a town, a cemetery). This is the authoritative set of",
        "//  named lakes + verified coordinates, so search returns REAL lakes first",
        "//  and MapKit is only the long-tail fallback.",
        "//",
        "//  The sheet is a PER-STATE inventory, so a reservoir on a state line is",
        "//  listed once per state — Pickwick appeared three times (AL/MS/TN). The",
        "//  generator merges rows whose normalized name matches AND whose",
        f"//  coordinates are within {MERGE_RADIUS_MI:.0f} mi, and `states` carries every state the",
        "//  water touches. Name alone would be wrong: this sheet has 19 name",
        "//  collisions that are genuinely different lakes hundreds of miles apart.",
        "//",
        "",
        "import Foundation",
        "#if canImport(CoreLocation)",
        "import CoreLocation",
        "#endif",
        "",
        "/// How much live data a lake can offer, straight from the sheet's",
        "/// `API Level` column. Routing, not decoration: `.dedicated` means an",
        "/// operator feed exists (TVA, SWPA, CWMS); `.usgsOnly` means fall to a",
        "/// gage; `.none` means expect nothing and say so rather than spin.",
        "enum LakeAPILevel: String, Equatable, Codable { case dedicated, usgsOnly, none }",
        "",
        "/// Sheet's `USGS Gage` column. `.likely` is the researcher's hedge — try",
        "/// the gage, but a miss isn't a bug.",
        "enum LakeGage: String, Equatable, Codable { case yes, likely, no }",
        "",
        "/// Sheet's `Water Temp — Best Source`. Decides whether a measured temp is",
        "/// worth fetching or the modeled estimate is the honest answer.",
        "enum LakeTempSource: String, Equatable, Codable { case buoy, inSitu, satellite, limited }",
        "",
        "/// What `fullPoolFt` is. `.fullPool` is a managed reservoir's normal full",
        "/// (summer) pool — the level its operator fills to, so a live pool above it",
        "/// is water into the flood pool and below it is a drawdown. `.naturalSurface`",
        "/// is an unregulated lake's usual surface: a reference, not a level anyone holds.",
        "enum LakePoolBasis: String, Equatable, Codable { case fullPool, naturalSurface }",
        "",
        "/// How `fullPoolFt` is sourced: `.high` = the operator's own figure (TVA,",
        "/// USACE CWMS, USBR, the utility); `.med` = a secondary source; `.low` = unverified.",
        "enum LakePoolConfidence: String, Equatable, Codable { case high, med, low }",
        "",
        "struct DirectoryLake: Identifiable, Equatable, Codable {",
        "    let name: String",
        "    /// Primary state — the one whose coordinate the sheet rated most confident.",
        "    let state: String",
        "    /// Every state this water touches, primary first. One element for most.",
        "    let states: [String]",
        "    let lat: Double",
        "    let lon: Double",
        "    let hasDam: Bool",
        "    /// Who runs it, verbatim from the sheet — shown in diagnostics.",
        "    let operatorName: String",
        "    let apiLevel: LakeAPILevel",
        "    let usgsGage: LakeGage",
        "    let tempSource: LakeTempSource",
        "    /// CWMS office code for USACE projects, parsed from the district the",
        "    /// sheet names (\"USACE Little Rock\" -> SWL). nil for everyone else.",
        "    /// CWMS is partitioned by office, so this is the key that makes an",
        "    /// observed-data lookup possible without hardcoding districts.",
        "    let cwmsOffice: String?",
        "    /// Normal full pool, ft — see `poolBasis`. In the datum the operator's own",
        "    /// lake level reads in: for TVA and CWMS lakes, the same system as the live",
        "    /// pool reading; for a utility on a local datum (Ameren, NIPSCO, Yadkin),",
        "    /// that datum. nil = unknown. Source: docs/data/full_pool.csv.",
        "    let fullPoolFt: Double?",
        "    let poolBasis: LakePoolBasis?",
        "    let poolConfidence: LakePoolConfidence?",
        "    /// The lake's own surface temperature sensor, read live when the spot is on",
        "    /// this lake: \"usgs:<site>\" or \"cwms:<office>:<time-series id>\". nil = none;",
        "    /// the model stands. Source: docs/data/temp_sensors.csv.",
        "    let tempSensor: String?",
        "    var id: String { \"\\(name)|\\(state)\" }",
        "    var coordinate: CLLocationCoordinate2D { .init(latitude: lat, longitude: lon) }",
        "}",
        "",
        "enum LakeDirectory {",
        "    /// Every lake, decoded once from the JSON below. As 621 Swift initializer",
        "    /// calls this file needed 9 GB to compile in release (2026-09-27) — more",
        "    /// than a Cloud Build worker has — and every field added made it worse.",
        "    /// One string literal compiles in no time.",
        "    static let all: [DirectoryLake] = {",
        "        do {",
        "            return try JSONDecoder().decode([DirectoryLake].self, from: Data(lakesJSON.utf8))",
        "        } catch {",
        "            fatalError(\"LakeDirectory.swift: the lake JSON does not decode — regenerate it: \\(error)\")",
        "        }",
        "    }()",
        "}",
        "",
    ]
    rows_out = []
    for e in entries:
        pool = e["pool"]
        rows_out.append({
            "name": e["name"], "state": e["state"], "states": e["states"],
            "lat": e["lat"], "lon": e["lon"], "hasDam": e["dam"],
            "operatorName": e["operator"], "apiLevel": e["api"], "usgsGage": e["gage"],
            "tempSource": e["temp"], "cwmsOffice": e["office"],
            "fullPoolFt": pool[0] if pool else None,
            "poolBasis": pool[1] if pool else None,
            "poolConfidence": pool[2] if pool else None,
            "tempSensor": e.get("tempSensor"),
        })
    # One lake per line keeps the diff of a single edit to a single line.
    body = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows_out)
    assert '"""#' not in body
    lines += ['private let lakesJSON = #"""', "[", body, "]", '"""#', ""]
    OUT.write_text("\n".join(lines))

    print(f"sheet rows:      {len(rows)}")
    print(f"entries written: {len(entries)}")
    print(f"merged clusters: {merged_count}")
    from collections import Counter as _C
    print("  api level:  ", dict(_C(e["api"] for e in entries)))
    print("  usgs gage:  ", dict(_C(e["gage"] for e in entries)))
    print("  temp source:", dict(_C(e["temp"] for e in entries)))
    print(f"  cwms office resolved: {sum(1 for e in entries if e['office'])}"
          f"  across {len({e['office'] for e in entries if e['office']})} districts")
    print("  full pool:  ", dict(_C((e["pool"][1], e["pool"][2]) if e["pool"] else None for e in entries)))
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
