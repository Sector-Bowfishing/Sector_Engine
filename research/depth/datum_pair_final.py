#!/usr/bin/env python3
"""Step 5: assemble the proposals file from decisions_cwms.json (groups 1-3), usgs_lakes.json (group 4) and the fetched evidence.
Writes jobs/depth-brain/depth_brain/data/proposals/datum_pairings.json and docs/brains/depth/data/datum_pairings_usgs.csv
Run after datum_pair_build.py: venv python -I research/depth/datum_pair_final.py"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datum_pair_common import ROOT

REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption")
DEC = json.load(open(f"{ROOT}/decisions_cwms.json"))
UL = json.load(open(f"{ROOT}/usgs_lakes.json"))
A2WS = json.load(open(f"{ROOT}/a2w_series.json"))
PAIRS = json.load(open(f"{ROOT}/cwms_pairs.json"))
CAND = {c["lakeId"]: c for c in json.load(open(f"{REPO}/jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]}
A2W_BASE = "https://water.usace.army.mil/cda/reporting/providers"
CWMS_BASE = "https://cwms-data.usace.army.mil/cwms-data"
ALT = {"Anderson Ranch Reservoir|ID": "CWMS AND Top of Normal = 4194.0 ft (NGVD29)", "Palisades Reservoir|ID": "CWMS PAL Top of Normal = 5619.0 ft (NGVD29)", "Jackson Lake|WY": "CWMS JCK Top of Normal = 6768.0 ft (NGVD29)",
       "Seminole|GA": "CWMS JimWoodruff Top of Normal = 78.0 ft, Bottom of Normal = 76.0 ft (NGVD29)", "Red Lake|MN": "CWMS RedLake_Dam Top of Normal = 1174.5 ft (series location stamped LOCAL; MSL1912 in the series version name)",
       "Percy Priest Lake|TN": "CWMS JPHT1 Top of Power 483.0/490.5 ft (NGVD29)", "Okeechobee|FL": "CWMS Okeechobee Top of Flood = 17.25 ft (not a pool)"}
PARAM_DATUM = {"62614": "NGVD29", "72020": "NGVD29", "62615": "NAVD88"}
STAT_KEYS = ("n", "meanFt", "sdFt", "minFt", "maxFt", "window")


def stats_block(st, extra=None):
    if not st:
        return {"n": 0, "meanFt": None, "sdFt": None, "minFt": None, "maxFt": None, "window": None}
    b = {k: st.get(k) for k in STAT_KEYS}
    b.update({"medianFt": st.get("medianFt"), "firstHalfMeanFt": st.get("firstHalfMeanFt"), "secondHalfMeanFt": st.get("secondHalfMeanFt"), "quarterMeanRangeFt": st.get("quarterMeanRangeFt")})
    if extra:
        b.update(extra)
    return b


def cwms_record(lid, d):
    v = PAIRS[lid]; s = v["series"]
    ev = []
    a2 = A2WS.get(lid, {})
    if a2.get("a2wUrl"):
        ev.append({"url": a2["a2wUrl"], "says": f"Access2Water location {a2['station']}: project vertical_datum '{v.get('a2wProjectDatum')}', series {s.get('tsid')} latest {s.get('a2wLatestValue')} ft"})
    if s.get("cwmsUrl"):
        ev.append({"url": s["cwmsUrl"], "says": f"CWMS data API returns the same series (same-instant difference to A2W {s.get('sameInstantDiffFt')} ft); vertical-datum-info {json.dumps(s.get('verticalDatumInfo') and s['verticalDatumInfo'].get('native-datum'))}"})
    sl = v.get("seriesLocation") or {}
    if sl.get("url"):
        ev.append({"url": sl["url"], "says": f"CWMS location {v.get('seriesLocationName')} ({sl.get('kind')}) vertical-datum {sl.get('verticalDatum')}"})
    if d.get("poolLevelUrl"):
        ev.append({"url": d["poolLevelUrl"], "says": f"CWMS level {d.get('poolLevelId')} ({d.get('poolLevelSpecified')}) values {d.get('poolLevelValues')} ft; pool figure {d['poolFt']}"})
    for h in v.get("poolLevelHits", []):
        if h["levelId"] == d.get("poolLevelId") and (h.get("locationRecord") or {}).get("url"):
            ev.append({"url": h["locationRecord"]["url"], "says": f"pool-level location {h['location']} vertical-datum {h['locationRecord'].get('verticalDatum')}"}); break
    bp = d.get("bestPair")
    if not bp and d.get("pairings"):
        bp = d["pairings"][0]
    if bp and bp.get("usgsUrl"):
        ev.append({"url": bp["usgsUrl"], "says": f"USGS {bp['site']} parameter {bp['param']} ({bp.get('paramDatum') or 'datum not defined'}): {bp['cls']} - {bp['detail']}"})
    return ev, bp


def main():
    lakes = {}
    for lid, d in DEC.items():
        v = PAIRS[lid]; dec = d["decision"]
        ev, bp = cwms_record(lid, d)
        doc_pool = d["poolSourceKind"] in ("doc", "tva-zone", "none")
        usable_bp = bp if (bp and bp["stats"].get("n", 0) >= 100 and (bp["stats"].get("sdFt") or 0) <= 0.5 and bp["cls"] not in ("NOT_SAME_POOL_OR_MISALIGNED", "OFFSET_UNEXPLAINED", "TOO_FEW")) else None
        rec = {"decision": dec, "group": d["group"], "levelDatum": d.get("levelDatum"), "referenceDatum": d.get("referenceDatum"), "method": "cwms-location", "evidence": ev}
        if dec in ("SAME_SOURCE", "SAME_DATUM"):
            rec["sigmaFt"] = d["sigma"]
            if d.get("viaPairing"):
                rec["method"] = "hartwell-pairing"
            ofs = stats_block(usable_bp["stats"], {"usgsSite": usable_bp["site"], "usgsParam": usable_bp["param"], "usgsParamDatum": usable_bp["paramDatum"], "pairClass": usable_bp["cls"], "circularFeed": usable_bp["circular"], "offsetDefinition": "USGS minus CWMS series, same UTC instants"}) if usable_bp else stats_block(None)
            rec["offsetStats"] = ofs
            if dec == "SAME_SOURCE":
                rec["levelDatum"] = d.get("levelDatum"); rec["referenceDatum"] = d.get("referenceDatum")
                if d.get("seriesLocationDatum") in ("LOCAL",):
                    rec["levelDatum"] = "LOCAL (CWMS location datum unnamed; vertical-datum-info OTHER)"; rec["referenceDatum"] = "LOCAL (same CWMS location)"
            bits = []
            if dec == "SAME_SOURCE":
                bits.append(f"CWMS series {d['tsid']} and pool level {d['poolLevelId']} share location {d['poolLevelLocation']}")
            else:
                bits.append(f"series location {d['seriesLocation']} and pool-level location {d['poolLevelLocation']} are both stamped {d.get('referenceDatum')} in CWMS" if not d.get("viaPairing") else d["reason"])
            if d.get("sameLocation") is False and d.get("poolSourceKind") != "none":
                pass
            rec["summary"] = "; ".join(bits) + f"; pool figure {d['poolFt']} equals the level value."
            cav = []
            if doc_pool:
                cav.append(f"Pool figure came from a document ({d['poolSourceKind']}), not from CWMS; it equals the CWMS level exactly, so the recommended reference is the CWMS level itself (re-bind).")
            if any(len(h) and abs(x - d['poolFt']) > 0.06 for h in [d.get("poolLevelValues") or []] for x in h):
                cav.append(f"The CWMS level is seasonal ({d['poolLevelValues']}); the shift is relative to {d['poolFt']} only in the season that value applies.")
            if d.get("seriesLocationDatum") in ("LOCAL",) and dec == "SAME_DATUM":
                cav.append("The CWMS series location is LOCAL; the NGVD29 claim rests on the USGS 62614 pairing (mean offset in offsetStats) plus the NGVD29-stamped pool level at a sibling location; the CWMS same-location pool level is LOCAL.")
            if d.get("seriesLocationDatum") in ("LOCAL",) and dec == "SAME_SOURCE":
                cav.append("Datum is an unnamed CWMS LOCAL datum: the shift is exact because pool and level share one location, but the level must NOT be treated as NGVD29/NAVD88 elevation.")
                # supporting evidence only
                sib = [h for h in v.get("poolLevelHits", []) if (h.get("locationRecord") or {}).get("verticalDatum") == "NGVD29"]
                if sib and usable_bp and usable_bp["cls"] == "NUMERICALLY_EQUAL_NGVD29":
                    cav.append(f"Supporting only: the same value is also stored at {sib[0]['location']} (stamped NGVD29) and USGS {usable_bp['param']} (NGVD29) equals the series (mean {usable_bp['stats']['meanFt']} ft).")
            if d.get("seriesLocationDatum") in (None,) and dec == "SAME_SOURCE":
                cav.append("CWMS location carries no vertical-datum stamp; absolute datum not stated by CWMS.")
            if usable_bp and usable_bp["circular"]:
                cav.append("The USGS pairing is circular (CWMS series is the USGS feed): it fixes the datum of the numbers, it does not independently confirm the CWMS tag.")
            if not usable_bp:
                cav.append("No independent USGS elevation series within 3 km usable for pairing; decision rests on CWMS metadata.")
            rec["caveat"] = " ".join(cav)
            strong = (d["poolSourceKind"] in ("cwms-level", "cwms-url")) and not (dec == "SAME_DATUM" and not (usable_bp and not usable_bp["circular"] and usable_bp["cls"].startswith(("CONSISTENT", "NUMERICALLY"))) and not (d.get("seriesVdi")))
            if dec == "SAME_SOURCE":
                rec["confidence"] = "high" if (strong and d.get("seriesLocationDatum") is not None) else "medium"
            else:
                rec["confidence"] = "high" if (strong and d.get("seriesVdi") and usable_bp and not usable_bp["circular"]) else "medium"
            if d.get("viaPairing"):
                rec["confidence"] = "medium"
        else:
            rec["summary"] = d.get("reason")
            rec["reason"] = d.get("reason")
            rec["offsetStats"] = stats_block(None)
            if lid in ALT:
                rec["alternativeReference"] = ALT[lid]
            rec["caveat"] = "Unresolved; resolver: " + ("operator document stating the vertical datum of the pool figure (or a pool-like CWMS level); " if "not equal" in (d.get("reason") or "") else "district confirmation that the project-level CWMS location carries the same datum as the series location; ")
            rec["confidence"] = "low"
        lakes[lid] = rec

    # ---------------- group 4 (USGS-served)
    rows = []
    for lid, r in UL.items():
        param = r["param"]; src = r.get("poolSource") or ""
        site_url = f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={r['site']}&parameterCd={param}"
        base = {"group": "G4", "method": "hartwell-pairing", "evidence": [{"url": (r["series"].get(param) or {}).get("url") or site_url, "says": f"USGS {r['site']} parameter {param}: {r['series'].get(param,{}).get('n')} instantaneous values in the last 365 days"}]}
        so = r.get("siblingOffsets", {})
        cp = r.get("cwmsPartner") or {}
        dec = None
        if lid in ("Clarks Hill / J.S. Thurmond|GA", "Lake Strom Thurmond (Clarks Hill)|SC"):
            st = cp["offset_usgs_minus_cwms"]
            dec = {"decision": "SAME_DATUM", "levelDatum": "NGVD29 (00062 series; numerically equal to CWMS NGVD29 pool series)", "referenceDatum": "NGVD29", "sigmaFt": round(max(0.15, abs(st["meanFt"]), min(2 * st["sdFt"], 1.0)), 3),
                   "offsetStats": stats_block(st, {"cwmsTsid": cp["tsid"], "circularFeed": False, "offsetDefinition": "USGS 00062 minus CWMS Thurmond Elev-Pool (Raw-SHEF_SAS), same UTC instants"}),
                   "summary": "USGS 02193900 00062 minus the CWMS SHEF pool series (location Thurmond, NGVD29) is +0.18 ft mean, 0.08 ft SD, stable by quarter (0.13 to 0.20); NAVD88 would be about -0.66 ft (NCAT) so the 00062 series is NGVD29-valued; pool 330 ft is the CWMS Thurmond Top of Conservation (NGVD29).",
                   "caveat": "Offset is +0.18 ft (larger than Hartwell's -0.12); sigma carries it. CWMS Top of Conservation is seasonal (326/330 ft); 330 is the summer value. USGS 00062 itself carries no datum label: the datum rests on the CWMS pairing.",
                   "confidence": "medium"}
            dec["evidence"] = base["evidence"] + [{"url": cp["locationUrl"], "says": "CWMS location Thurmond vertical-datum NGVD29"}, {"url": cp["urls"][0], "says": "CWMS Thurmond.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS (Corps SHEF feed, independent of the USGS gauge), 365 days"},
                                                  {"url": f"{CWMS_BASE}/levels?office=SAS&level-id-mask=Thurmond*&unit=EN", "says": "CWMS Thurmond.Elev.Inst.0.Top of Conservation seasonal values 326/330 ft"}]
        elif lid in ("Walter F. George / Eufaula|GA", "Eufaula / W.F. George|AL"):
            a = r.get("anchor") or {}
            ast = a.get("offset_anchor_minus_bound")
            ev = base["evidence"] + [{"url": cp["locationUrl"], "says": "CWMS location WalterFGeorge vertical-datum NGVD29; series vertical-datum-info native NGVD-29 with NAVD-88 offset -0.2591 (estimate)"},
                                      {"url": f"{CWMS_BASE}/levels?office=SAM&level-id-mask=WalterFGeorge*&unit=EN", "says": "CWMS WalterFGeorge.Elev.Inst.0.Top of Conservation seasonal 188/190 ft; 190 ft is the summer value"}]
            if lid.endswith("|GA"):
                dec = {"decision": "SAME_DATUM", "levelDatum": "NGVD29 (00062 series; numerically equal to independent USGS 62614 gauge on the same pool)", "referenceDatum": "NGVD29",
                       "sigmaFt": round(max(0.15, abs(ast["meanFt"]), min(2 * ast["sdFt"], 1.0)), 3),
                       "offsetStats": stats_block(ast, {"usgsSite": a["site"], "usgsParam": "62614", "usgsParamDatum": "NGVD29", "offsetDefinition": "USGS 0234296910 62614 (NGVD29) minus USGS 02343240 00062, same UTC instants, two gauges ~25 km apart on one pool"}),
                       "summary": "USGS 02343240 00062 equals the NGVD29-defined USGS 0234296910 62614 gauge on the same pool (mean +0.04, SD 0.07 ft) and the CWMS WalterFGeorge series (NGVD29, a USGS feed); pool 190 ft equals the CWMS Top of Conservation (NGVD29).",
                       "caveat": "The CWMS series is the USGS feed (Raw-USGS), so only the 62614 gauge is independent. NAVD88 would be about -0.26 ft, so the 0.04 ft agreement discriminates only weakly. Pool is seasonal (188/190 ft). Two directory entries (GA/AL) are the same lake.",
                       "confidence": "medium", "evidence": ev + [{"url": a["url"], "says": "USGS 0234296910 62614 (above NGVD 1929) iv"}]}
            else:
                dec = {"decision": "SAME_DATUM", "levelDatum": "NGVD29 (USGS 62614 by parameter definition)", "referenceDatum": "NGVD29", "sigmaFt": round(max(0.15, abs(r["cwmsPartner"]["offset_usgs_minus_cwms"]["meanFt"]), min(2 * r["cwmsPartner"]["offset_usgs_minus_cwms"]["sdFt"], 1.0)), 3),
                       "offsetStats": stats_block(cp["offset_usgs_minus_cwms"], {"cwmsTsid": cp["tsid"], "circularFeed": True, "offsetDefinition": "USGS 62614 minus CWMS WalterFGeorge series"}),
                       "summary": "Level is USGS 62614 (above NGVD 1929); pool 190 ft equals the CWMS WalterFGeorge Top of Conservation (location stamped NGVD29, native NGVD-29); the 62614 gauge agrees with the CWMS series (+0.04 ft mean, 0.07 SD).",
                       "caveat": "Pool document (wfg-pert.htm) not itself fetched; the pool is re-bound to the CWMS level. Seasonal 188/190 ft. The CWMS series is a USGS feed, so the agreement is not independent.", "confidence": "high", "evidence": ev}
        if dec is None:
            reason = None; resolver = None
            if param == "00065":
                reason = "level is 00065 gage height (+ alt_va); not an elevation unless the gauge datum conversion is established, and the pool datum is also undocumented"; resolver = "USGS gage-datum record plus operator document for the pool"
            elif param == "00062":
                if so.get("62615"):
                    s = so["62615"]
                    reason = f"USGS 00062 is {-s['meanFt']:+.2f} ft relative to the site's own 62615 (NAVD88) series (n={s['n']}, SD {s['sdFt']}): the 00062 scale is a per-site datum, not NAVD88. Pool source '{src[:70]}' states no datum"
                    resolver = "operator document naming the datum of the pool figure and of the gauge scale (e.g. Santee Cooper/Dominion/FERC exhibit)"
                else:
                    reason = f"USGS 00062 with no 62614/62615 sibling and no CWMS/operator series to pair; pool source '{src[:70]}' states no datum"; resolver = "an independent datum-labelled series on the same pool (USBR RISE series datum or operator table) plus pool datum document"
            else:
                pd = PARAM_DATUM.get(param)
                reason = f"level datum is {pd} by parameter definition; pool source '{src[:80] or 'none'}' states no datum, and no CWMS pool-like level exists for this lake"
                resolver = "operator or state document stating the datum of the pool figure" if src else "a published pool figure with a stated datum (none in manifest)"
                if lid in ("Kerr Reservoir (Buggs Island)|VA",):
                    reason += "; the CWMS ROA JHK series is NGVD29-stamped (vdi offset to NAVD88 -1.018 ft) and equals the USGS gauge, but CWMS has no pool level for the project"
                    resolver = "Kerr Water Control Plan (KERRWCP.pdf, SAW) datum statement, or a CWMS ROA JHK Top of Conservation level"
                if lid in ("Lake D'Arbonne|LA", "Lake Bistineau|LA"):
                    pass
            dec = {"decision": "UNKNOWN", "levelDatum": PARAM_DATUM.get(param), "referenceDatum": None, "sigmaFt": None, "offsetStats": stats_block(None), "summary": reason, "reason": reason, "caveat": "Unresolved; resolver: " + resolver, "confidence": "low", "evidence": base["evidence"]}
            if lid == "Deep Creek Lake|MD":
                dec["caveat"] += ". Measured: 62615 minus 00062 = +1.82 ft constant (SD 0.0), consistent with the Historical Spillway Datum 2462 note (project note, not re-fetched)"
        dec.update({"group": "G4", "method": dec.get("method", "hartwell-pairing") if dec["decision"] != "UNKNOWN" else "operator-doc"})
        lakes[lid] = dec
        rows.append([lid, param, r["site"], dec["decision"], json.dumps({p: (v["meanFt"], v["sdFt"], v["n"]) for p, v in so.items()}), (cp.get("offset_usgs_minus_cwms") or {}).get("meanFt"), ((r.get("anchor") or {}).get("offset_anchor_minus_bound") or {}).get("meanFt"), dec.get("sigmaFt"), dec["summary"][:200]])
    with open(f"{REPO}/docs/brains/depth/data/datum_pairings_usgs.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["lake", "param", "site", "decision", "sibling_minus_bound(mean,sd,n)", "usgs_minus_cwms_mean", "anchor_minus_bound_mean", "sigmaFt", "summary"]); w.writerows(rows)
    out = {"schema": "depth-datum-proposals-v1", "generatedAt": "2026-10-14", "sigmaRule": "SAME_SOURCE (one CWMS location): 0.0. SAME_DATUM: max(0.15 ft, |mean offset|, min(2*SD, 1.0 ft)) from the independent datum-labelled series; 0.15 ft when only CWMS metadata supports it.",
           "lakes": dict(sorted(lakes.items()))}
    p = f"{REPO}/jobs/depth-brain/depth_brain/data/proposals/datum_pairings.json"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, "w"), indent=1, default=str)
    from collections import Counter
    print(Counter((l["group"], l["decision"]) for l in lakes.values()), len(lakes))
    print(Counter(l["confidence"] for l in lakes.values() if l["decision"].startswith("SAME")))


if __name__ == "__main__":
    main()
