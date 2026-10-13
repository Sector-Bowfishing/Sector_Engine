"""Generate the datum unlock queue (CSV + markdown) from the candidate manifest. Deterministic; re-run after every evidence cycle.
Usage: python research/depth/unlock_queue.py"""
import csv, json, os, collections, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAN = json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/candidates.json"))
FEAT = {r["id"]: r for r in csv.DictReader(open("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv"))}


def group(c):
    br, ls, rf = set(c["blockedReasons"]), c["levelSource"], c["reference"]
    prov, ld, src = (ls["provider"] or "").lower(), ls["datum"], (c["reference"]["source"] or "")
    if c["shiftPossible"]:
        return None
    if "DUKE_LOCAL_SCALE_NOT_ENABLED" in br:
        return ("duke-local-scale", "Duke confirmation that level = 100 + (elevation - full pond) and the full-pond table datum", "Duke Energy Lake Services / FERC licence file", "high", 8)
    if "DATUM_CONVERSION_NOT_ENABLED" in br:
        return ("conversion-disabled", "verified NGVD29<->NAVD88 conversion convention for this lake", "CWMS vertical-datum-info / operator offset", "medium", 4)
    if "DATUM_UNKNOWN" in br:
        if prov == "rise" or prov == "usbr-pnhm":
            return ("rise-usbr", "Reclamation statement of the vertical datum of the RISE/Hydromet elevation series and the pool figure", "USBR regional office / RISE API docs", "medium", 9)
        if prov == "nwps":
            return ("nwps", "stated pool-elevation product (HP) with gauge datum, or a paired CWMS/USGS series", "NWS NWPS gauge metadata + paired operator series", "medium", 8)
        if prov == "a2w":
            if ld in ("NGVD29", "NAVD88"):
                return ("a2w-pool-datum-unstated", "datum of the pool figure (non-CWMS source) so it can be compared with the A2W project datum", "operator document / CWMS level for the same location", "high", 9)
            return ("a2w-local-or-blank", "relationship of the LOCAL/blank A2W project stage to elevation", "USACE district datum document or paired USGS gauge (Hartwell method)", "medium", 9)
        if prov in ("cwms", "cwms-saw", "cwms-nwdp"):
            return ("cwms-pool-datum-unstated", "datum of the pool figure (URL/document value) vs the CWMS series location datum", "operator document or CWMS level at the same location", "high", 10)
        if prov in ("usgs", "usgs-d"):
            return ("usgs-pairing", "pair the USGS series with a CWMS/operator series or a stated pool datum (00062 per-site; never 00065 as elevation)", "CWMS location datum + overlap statistics", "high", 10)
        return ("other-operator", "operator document stating the datum of series and pool figure", f"{prov or 'operator'} documentation", "medium", 5)
    if "NO_VERIFIED_LEVEL_BINDING" in br:
        return ("lake-binding", "a reviewed Lake Brain level binding (Lake owns level)", "Lake Brain binding review", "high", 3)
    if "REFERENCE_POOL_CONFIDENCE_LOW" in br or "REFERENCE_NOT_A_POOL_ELEVATION" in br or "MISSING_REFERENCE_POOL" in br:
        return ("reference-pool", "an operator-published pool elevation with its datum (natural lakes have none by design)", "operator / state agency / NID", "medium", 2)
    return ("other", "review", "lead", "low", 1)


rows = []
for c in MAN["candidates"]:
    g = group(c)
    if not g:
        continue
    key, missing, resolver, conf, base = g
    f = FEAT.get(c["lakeId"], {})
    area = float(f.get("area_km2") or 0)
    plausible = c["reference"]["basis"] == "fullPool" and c["reference"]["confidence"] in ("high", "medium") and c["levelSource"]["status"] != "NONE"
    tier = c["evidence"]["tier"]
    pr = base + (3 if plausible else 0) + (2 if tier in ("A", "B") else 0) + min(3, area / 100.0) + (1 if c["history"].get("rangeClass") == "GE4FT" else 0)
    rows.append({"lakeId": c["lakeId"], "lake": c["lakeName"], "state": c["state"], "operator": c["operator"], "group": key, "plausible": plausible,
                 "referencePoolSource": (c["reference"]["source"] or "")[:90], "referencePoolFt": c["reference"]["poolFt"], "referenceConfidence": c["reference"]["confidence"],
                 "levelSource": f"{c['levelSource']['status']} {c['levelSource']['provider']} {c['levelSource']['series'] or ''}"[:70],
                 "levelDatum": c["levelSource"]["datum"], "datumState": c["datum"]["status"], "blockedReasons": ";".join(c["blockedReasons"]),
                 "missingEvidence": missing, "possibleResolver": resolver, "expectedConfidenceIfResolved": conf, "depthTier": tier,
                 "customerDerivedLicence": c["licence"].get("customerDerivedMetricsAllowed"), "areaKm2": round(area, 1), "priorityScore": round(pr, 2)})
rows.sort(key=lambda r: -r["priorityScore"])
for i, r in enumerate(rows, 1):
    r["priorityRank"] = i
out = f"{ROOT}/docs/brains/depth/data/depth_datum_unlock_queue.csv"
with open(out, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
grp = collections.OrderedDict()
for r in rows:
    d = grp.setdefault(r["group"], {"n": 0, "plausible": 0, "missing": r["missingEvidence"], "resolver": r["possibleResolver"], "conf": r["expectedConfidenceIfResolved"], "score": 0, "ex": []})
    d["n"] += 1; d["plausible"] += r["plausible"]; d["score"] += r["priorityScore"]
    if len(d["ex"]) < 4 and r["plausible"]: d["ex"].append(r["lake"])
summary = {"blocked": len(rows), "plausibleBlocked": sum(r["plausible"] for r in rows),
           "groups": {k: {"n": v["n"], "plausible": v["plausible"]} for k, v in grp.items()}}
json.dump(summary, open(f"{ROOT}/docs/brains/depth/data/depth_datum_unlock_summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))

# ── markdown ─────────────────────────────────────────────────────────────────────────────────────────────────
md = ["# Depth datum unlock queue", "",
      f"Generated by `research/depth/unlock_queue.py` from `candidates.json` (manifest `{MAN.get('manifestVersion')}`). Full per-lake table: `docs/brains/depth/data/depth_datum_unlock_queue.csv` "
      f"({len(rows)} blocked lakes; {summary['plausibleBlocked']} are 'plausible', i.e. acceptable pool + verified level binding, blocked only by datum/other rules). "
      "Fields per lake: lakeId, lake, operator, referencePoolSource, levelSource, datumState, missingEvidence, possibleResolver, expectedConfidenceIfResolved, customer/licence status, priority.", "",
      "Rules that stay on: no guessed conversions, LOCAL stage never treated as elevation, USGS 00065 never treated as elevation, no 'close enough' pairing (hard statistical gate in `proposals.py`).", "",
      "## Groups ranked by unlock potential (plausible lakes, then summed priority)", "",
      "| # | Group | Blocked | Plausible | Missing evidence | Possible resolver | Confidence if resolved | Examples |", "|---|---|---|---|---|---|---|---|"]
for i, (k, v) in enumerate(sorted(grp.items(), key=lambda kv: (-kv[1]["plausible"], -kv[1]["score"])), 1):
    md.append(f"| {i} | `{k}` | {v['n']} | {v['plausible']} | {v['missing']} | {v['resolver']} | {v['conf']} | {', '.join(v['ex'])} |")
md += ["", "## Top 40 lakes by priority", "", "| Rank | Lake | Operator | Group | Reference pool source | Level source | Datum state | Tier | Licence | Priority |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in rows[:40]:
    md.append(f"| {r['priorityRank']} | {r['lake']} ({r['state']}) | {r['operator']} | `{r['group']}` | {r['referencePoolSource'][:50]} | {r['levelSource'][:40]} | {r['datumState']} | {r['depthTier']} | {r['customerDerivedLicence']} | {r['priorityScore']} |")
md += ["", "Priority = group base + 3 if plausible + 2 if tier A/B contours + min(3, area km2 / 100) + 1 if >= 4 ft operating range. It ranks work, it never changes eligibility."]
open(f"{ROOT}/docs/brains/depth/DEPTH_DATUM_UNLOCK_QUEUE.md", "w").write("\n".join(md) + "\n")
