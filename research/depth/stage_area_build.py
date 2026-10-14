"""Build jobs/depth-brain/depth_brain/data/stage_area_curves.json: operator elevation-area ratings (USACE CWMS `Elev;Area`) for lakes whose CWMS level SERIES sits at the
same CWMS location as the rating. Read-only GETs (cached outside git). Rules are frozen in docs/brains/depth/DEPTH_STAGE_AREA_RATING_RULES.md (RATING-ZONE-RULES-1)
BEFORE this script's output was inspected: it records accepted and rejected lakes with the reason, it does not tune thresholds."""
import json, os, re, urllib.parse
import numpy as np
from datum_pair_common import get_json, CWMS

HERE = os.path.dirname(os.path.abspath(__file__))
INV = os.path.join(HERE, "../../docs/brains/depth/data/stage_area_inventory.json")
PAIRS = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum2/cwms_pairs.json")
CANDS = os.path.join(HERE, "../../jobs/depth-brain/depth_brain/data/candidates.json")
OUT = os.path.join(HERE, "../../jobs/depth-brain/depth_brain/data/stage_area_curves.json")
EDGES = (3.0, 6.0, 10.0)
WINDOW_ABOVE = 6.0                               # points stored: the whole rating up to pool+6 ft (drawdowns can be large, so nothing is cut below the pool)


def tok(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def rating(office, rid):
    r = get_json(f"{CWMS}/ratings/{urllib.parse.quote(rid, safe='')}", {"office": office}, headers={"Accept": "application/json;version=2"}, retries=1)
    return (r or {}).get("data"), (r or {}).get("_url")


def parse(d):
    sr = d["simple-rating"]; sr = sr if isinstance(sr, list) else [sr]
    best = max(sr, key=lambda x: x["effective-date"])
    pts = best["rating-points"]["point"]; pts = pts if isinstance(pts, list) else [pts]
    e = np.array([float(p["ind"]) for p in pts]); a = np.array([float(p["dep"]) for p in pts])
    o = np.argsort(e, kind="stable")
    return e[o], a[o], best["effective-date"], (best.get("vertical-datum-info") or {}).get("native-datum"), best.get("units-id"), [x["effective-date"][:10] for x in sr]


D5 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5")
TSC_LAKES = {   # lake -> (table file, survey year, public URL): lakes whose RISE elevation passed the storage-consistency fit and whose pool is in the table's frame (datum_pairings_5.json)
    "Bighorn Lake|WY": ("BighornReservoirAreaCapacityTables2017_Final508.pdf", 2017, "BighornReservoirAreaCapacityTables2017_Final508.pdf"),
    "El Vado Lake|NM": ("ElVado2018_tables.pdf", 2018, "ElVadoReservoir2018AreaAndCapacityTables_Final(508).pdf"),
    "Elephant Butte Reservoir|NM": ("Elephant_Butte_Reservoir_2017_&_2019_Area_and_Capacity_Tables.pdf", 2019, "Elephant Butte Reservoir 2017 & 2019 Area and Capacity Tables.pdf"),
    "Heron Lake|NM": ("Heron_Reservoir_2010_Capacity_Tables.pdf", 2010, "Heron Reservoir 2010 Capacity Tables.pdf"),
    "Navajo Reservoir|NM": ("NavajoReservoir2019AreaCapacityTables_final508VI.pdf", 2019, "NavajoReservoir2019AreaCapacityTables_final508VI.pdf"),
    "Swanson Reservoir|NE": ("Swanson_Reservoir_2011_Capacity_Tables.pdf", 2011, "Swanson Reservoir 2011 Capacity Tables.pdf"),
    "Patterson Lake|ND": ("Edward_Arthur_Patterson_CapacityTable_2013.pdf", 2013, "Edward_Arthur_Patterson CapacityTable 2013.pdf"),
    "Lake Tschida|ND": ("Lake_Tschida_2013_Capacity_Tables.pdf", 2013, "Lake Tschida 2013 Capacity Tables.pdf"),
    "Calamus Reservoir|NE": ("Calamus_2012_Area-Capacity_table_final.pdf", 2012, "Calamus 2012 Area-Capacity table_final.pdf"),
    "Cheney Reservoir|KS": None,        # keeps its CWMS rating
}


def tsc_curve(pdf, tabs, eqs, pool):
    """Area-versus-elevation from a Reclamation TSC table (survey-derived, project vertical datum): ACAP equations (area = A2 + 2*A3*x) or the printed 1-ft area table."""
    if pdf in eqs:
        rows = eqs[pdf]["rows"]
        bases = np.array([r[1] for r in rows])
        grid = np.arange(bases[0], bases[-1] + 1.0, 0.25)
        idx = np.clip(np.searchsorted(bases, grid, side="right") - 1, 0, len(rows) - 1)
        x = grid - bases[idx]
        a2, a3 = (np.array([r[k] for r in rows])[idx] for k in (4, 5))
        return grid, a2 + 2 * a3 * x, "ACAP equations"
    t = tabs[pdf]["area"]
    e = np.array(sorted(float(k) for k in t))
    return e, np.array([t[str(int(k))] for k in e]), "1-ft area table"


def main():
    inv = json.load(open(INV))["ratings"]
    pairs = json.load(open(PAIRS))
    cands = {c["lakeId"]: c for c in json.load(open(CANDS))["candidates"]}
    lakes, rejected = {}, {}
    jobs = []
    for lid, v in pairs.items():                                   # pass 1: the CWMS level SERIES sits at the rating's location
        s = v.get("series") or {}
        jobs.append((lid, s.get("cwmsOffice"), (s.get("tsid") or "").split(".")[0], "series-location"))
    seen = {j[0] for j in jobs}
    for lid, c in cands.items():                                   # pass 2: the verified reference POOL is a CWMS level at the rating's location
        src = (c["reference"].get("source") or "")
        m = re.match(r"CWMS ([^. ]+(?: Lake)?(?:_[A-Za-z0-9_]+)?)", src)
        if lid in seen or not m or not c["reference"].get("datumVerified"):
            continue
        jobs.append((lid, c.get("cwmsOffice"), m.group(1), "pool-location"))
    for lid, off, loc, by in jobs:
        if lid not in cands:
            continue
        offs = [off] + (["NWDM"] if off in ("NWK", "NWO", "NWP", "NWS", "NWW") else [])
        hits, off = next((([i for i in inv[o] if tok(i.split(".Elev")[0].split("-")[0]) == tok(loc.split("-")[0])], o) for o in offs if o in inv and any(tok(i.split(".Elev")[0].split("-")[0]) == tok(loc.split("-")[0]) for i in inv[o])), ([], None))
        if not hits:
            continue
        c = cands[lid]; P = c["reference"]["poolFt"]
        tried = []
        for rid in hits:
            d, url = rating(off, rid)
            if not d:
                tried.append((rid, "fetch failed")); continue
            e, a, eff, vd, units, versions = parse(d)
            tried.append((rid, eff[:10], units, vd, float(e.min()), float(e.max()), url, e, a, versions))
        ok = [t for t in tried if len(t) > 3]
        if not ok:
            rejected[lid] = "rating fetch failed"; continue
        rdn = re.sub(r"[- ]", "", str(c["reference"].get("datum") or "")).upper() or None
        compat = [t for t in ok if not t[3] or not rdn or re.sub(r"[- ]", "", str(t[3])).upper() == rdn]
        t = max(compat or ok, key=lambda t: (t[1], t[5] - t[4]))        # prefer a rating in the pool's datum; then latest effective date, then widest elevation span
        rid, eff, units, vd, emin, emax, url, e, a, versions = t
        why = None
        u = (units or "").lower().replace(" ", "")
        if u not in ("ft;ac", "ft;acre", "ft;acres"):                # ft;ft2 (Alamo) was tried and rejected: converted values (0.1 acre at pool) show the unit label is unreliable
            why = f"units {units}"
        elif P is None or not (emin <= P - EDGES[0] and P <= emax):
            why = f"pool {P} not inside rating {emin:.1f}-{emax:.1f} with 3 ft below it"
        else:
            top = int(np.searchsorted(e, P + WINDOW_ABOVE, side="right")) + 1        # one bracketing point above the window
            if np.any(np.diff(a[:top]) < -0.01 * max(a[:top].max(), 1.0)):
                why = "area decreases with elevation (below pool + 6 ft)"
            elif float(np.interp(P, e, a)) <= 0:
                why = "area at pool is not positive"
        if why:
            rejected[lid] = why; continue
        top = int(np.searchsorted(e, P + WINDOW_ABOVE, side="right")) + 1        # one bracketing point above the window
        keep_e, keep_a = e[:top], a[:top]
        step = None
        if len(keep_e) > 400 and float(np.median(np.diff(keep_e))) < 0.1:         # very fine ratings (0.01 ft): resample on a 0.1 ft grid (linear between points, so the area error is negligible) to keep the repo file small
            grid = np.arange(np.ceil(keep_e[0] * 10) / 10, keep_e[-1], 0.1)
            keep_e, keep_a, step = np.concatenate([[e[0]], grid, [keep_e[-1]]]), np.concatenate([[a[0]], np.interp(grid, keep_e, keep_a), [keep_a[-1]]]), 0.1
        lakes[lid] = {"office": off, "ratingId": rid, "effectiveDate": eff[:10], "versions": versions, "ratingNativeDatum": vd, "seriesLocation": loc, "matchedBy": by, "url": url,
                      "elevMinFt": round(emin, 2), "elevMaxFt": round(emax, 2), "nPointsTotal": int(len(e)), "poolFt": P,
                      "resampledStepFt": step, "elevFt": [round(float(x), 3) for x in keep_e], "areaAc": [round(float(x), 2) for x in keep_a]}
    tabs, eqs = json.load(open(D5 + "/tsc_tables.json")), json.load(open(D5 + "/tsc_equations.json"))
    for lid, spec in TSC_LAKES.items():
        if not spec or lid in lakes:
            continue
        pdf, year, fname = spec
        c = cands[lid]; P = c["reference"]["poolFt"]
        e, a, form = tsc_curve(pdf, tabs, eqs, P)
        if not (e[0] <= P - EDGES[0] and P <= e[-1]) or np.any(np.diff(a) < -0.01 * max(a.max(), 1.0)) or float(np.interp(P, e, a)) <= 0:
            rejected[lid] = "TSC table does not cover the pool / not monotone"; continue
        top = int(np.searchsorted(e, P + WINDOW_ABOVE, side="right")) + 1
        e, a = e[:top], a[:top]
        lakes[lid] = {"office": "USBR-TSC", "ratingId": f"TSC {pdf.rsplit('.', 1)[0]} ({form})", "effectiveDate": f"{year}-01-01", "versions": [str(year)], "ratingNativeDatum": None, "seriesLocation": None, "matchedBy": "tsc-table",
                      "url": "https://www.usbr.gov/tsc/techreferences/reservoir/" + urllib.parse.quote(fname), "elevMinFt": round(float(e[0]), 2), "elevMaxFt": round(float(e[-1]), 2), "nPointsTotal": int(len(e)),
                      "poolFt": P, "resampledStepFt": None, "elevFt": [round(float(x), 3) for x in e], "areaAc": [round(float(x), 2) for x in a]}
    json.dump({"schema": "depth-stage-area-curves-v1", "rules": "RATING-ZONE-RULES-1", "lakes": lakes, "rejected": rejected}, open(OUT, "w"), separators=(",", ":"))
    print(len(lakes), "accepted;", len(rejected), "rejected", rejected)


main()
