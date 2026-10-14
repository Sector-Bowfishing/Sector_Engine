"""Duke Energy lake-level frame + datum proposals from Duke's own public lake-levels JSON (the endpoint behind duke-energy.com/lakes; read-only GET).
Each row pairs the live level (`Actual`, relative scale with 100.00 = full pond for Catawba-Wateree and Keowee-Toxaway lakes; absolute feet for Lake Robinson)
with the full-pond elevation and its datum in the `Elevation` field ("1200.0 ft (AMSL, NGVD 29 datum)"). Writes the small evidence snapshot and datum_pairings_4.json."""
import json, os, re, sys, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
URL = "https://api.hydro-derived.duke-energy.app/lakes/current-level"
CANDS = os.path.join(ROOT, "jobs/depth-brain/depth_brain/data/candidates.json")
OUT_SNAP = os.path.join(ROOT, "docs/brains/depth/data/duke_api_2026-10-14.json")
OUT_PROP = os.path.join(ROOT, "jobs/depth-brain/depth_brain/data/proposals/datum_pairings_4.json")
LAKES = {"Lake Hickory|NC": "Lake Hickory", "Lake James|NC": "Lake James", "Lake Norman|NC": "Lake Norman", "Lake Wylie|SC": "Lake Wylie", "Lake Wateree|SC": "Lake Wateree",
         "Lake Jocassee|SC": "Lake Jocassee", "Lake Keowee|SC": "Lake Keowee", "Lake Robinson|SC": "Lake Robinson"}
LIP = "https://files.nc.gov/ncdeq/Water%20Resources/files/ibt/Concord/09Final_Environmental_Impact_Statement_May_2006/FEIS_Appendices/Appendix-D_%20Low_Inflow_Protocol_Catawba.pdf"


def main():
    rows = {r["LakeDisplayName"]: r for r in json.loads(urllib.request.urlopen(URL, timeout=60).read())}
    cands = {c["lakeId"]: c for c in json.load(open(CANDS))["candidates"]}
    snap, props = {}, {}
    for lid, name in LAKES.items():
        r = rows[name]
        m = re.match(r"\s*([0-9.]+)\s*ft\s*\(AMSL,\s*(NGVD\s?29|NAVD\s?88)\s*datum", r["Elevation"])
        if not m:
            print("NO DATUM", name, r["Elevation"]); continue
        fp, datum = float(m.group(1)), m.group(2).replace(" ", "")
        snap[lid] = {k: r[k] for k in ("LakeDisplayName", "Actual", "Target", "Min", "Max", "Date", "Elevation", "LocationId")}
        pool = cands[lid]["reference"]["poolFt"]
        if abs(pool - fp) > 0.05:
            print("POOL MISMATCH", lid, pool, fp); continue
        relative = abs(float(r["Max"]) - 100.0) < 1.0 and float(r["Actual"]) < 120
        sc = {"kind": "DUKE_RELATIVE_100", "fullPondScaleValue": 100.0} if relative else {"kind": "ABSOLUTE_FT"}
        props[lid] = {
            "decision": "SAME_SOURCE", "group": "DUKE", "levelDatum": datum, "referenceDatum": datum, "method": "operator-doc", "confidence": "high", "sigmaFt": 0.1, "levelScale": sc,
            "summary": (f"Duke's own lake-levels row carries the live level (Actual {r['Actual']}, Max {r['Max']}: 100-based scale, 100.00 = full pond) and the full-pond elevation with its datum ({r['Elevation']}); "
                        f"directory pool {pool} equals it. shift = Actual - 100.") if relative else
                       (f"Duke's own lake-levels row carries the live level in absolute feet (Actual {r['Actual']}, Max {r['Max']}) and the full-pond elevation with its datum ({r['Elevation']}); directory pool {pool} equals it."),
            "evidence": [{"url": URL, "says": f"row {name}: Actual {r['Actual']}, Target {r['Target']}, Min {r['Min']}, Max {r['Max']}, Elevation '{r['Elevation']}', observed {r['Date']} (fetched {dt.date.today()})"}] +
                        ([{"url": LIP, "says": "Catawba-Wateree Low Inflow Protocol: licensee refers to the full pond elevation of all its reservoirs as 100.0 ft relative; tabulates full pond in ft above mean sea level"}] if lid.split("|")[0] in ("Lake Hickory", "Lake James", "Lake Norman", "Lake Wylie", "Lake Wateree") else []),
            "caveat": "The endpoint is the public JSON behind Duke's lake-levels web page, not a documented API contract; an earlier probe of a different path returned 403/Missing Authentication Token."}
    json.dump(snap, open(OUT_SNAP, "w"), indent=1)
    json.dump({"schema": "depth-datum-proposals-v1", "generatedAt": str(dt.date.today()), "sigmaRule": "SAME_SOURCE 0.1 (provider rule precedent)", "lakes": props}, open(OUT_PROP, "w"), indent=1)
    print(len(props), "proposals", [(k, v["levelScale"]["kind"]) for k, v in props.items()])


main()
