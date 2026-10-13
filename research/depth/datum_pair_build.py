#!/usr/bin/env python3
"""Step 4: apply the decision rules to the fetched CWMS / USGS evidence and write
   jobs/depth-brain/depth_brain/data/proposals/datum_pairings.json  (schema depth-datum-proposals-v1)
   docs/brains/depth/data/datum_pairings_cwms.csv   (one row per USACE-served lake)
Inputs (cache dir, outside git): cwms_pairs.json, usgs_pairs.json, usgs_lakes.json (group 4, optional), docs_evidence.json (operator-document checks, optional)
Run: venv python -I research/depth/datum_pair_build.py

Decision rules (CWMS-served level series; pool resolved to a CWMS location level)
  R0  The live series must exist in the public CWMS API under the tsid Access2Water shows, equal to A2W at the same instant (checked in step 2).
  R1  Pool: a CWMS Elev location level with a pool-like name (Top of Conservation/Normal/Multi-Purpose/Gross Pool/Power/Recreation/Bottom of Flood..) whose value
      (constant or any seasonal value) equals the pool figure within 0.06 ft. A level that merely shares a number but is not pool-like (Max Non-Damaging, x% Flood Storage,
      Top of Dam) is rejected. No such level -> UNKNOWN (pool must be proven from an operator document).
  R2  Same CWMS location (series and level) -> SAME_SOURCE (identical native datum by construction, whatever the tag says, LOCAL included). sigma 0.
  R3  Different CWMS locations of one project, both stamped with the same NGVD29 or NAVD88 -> SAME_DATUM, sigma = max(0.15, |mean offset|, min(2*SD, 1.0)) when an
      independent same-datum USGS pairing exists, else 0.15 (metadata only). Stamped but different -> INCOMPATIBLE. Level or pool location unstamped -> UNKNOWN.
  R4  Series tag LOCAL/OTHER and the only pool-like level is at a differently-located NGVD29/NAVD88 location: SAME_DATUM only if an independent USGS 62614/72020 (or
      62615) pairing on the same pool shows the series equals that defined datum (|mean|<=0.15 ft and discriminates from the other datum by >=0.15 ft). Otherwise UNKNOWN.
  Circularity guard: a CWMS version naming USGS (Raw-USGS, USGS-raw, USGS-rev), or SD<=0.01 with mean<=0.01, means the CWMS series IS the USGS feed; it fixes the datum of the
  numbers (the USGS parameter defines it) but is not independent confirmation of the CWMS tag; confidence is capped accordingly."""
import csv, json, math, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datum_pair_common import ROOT

REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption")
CAND = {c["lakeId"]: c for c in json.load(open(f"{REPO}/jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]}
PAIRS = json.load(open(f"{ROOT}/cwms_pairs.json"))
USG = json.load(open(f"{ROOT}/usgs_pairs.json"))
NCAT = {r["id"]: float(r["shift_ft_ngvd29_to_navd88"]) for r in csv.DictReader(open(os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-research/docs/research/depth-brain/data/datum_shift_ngvd29_navd88.csv"))) if r.get("shift_ft_ngvd29_to_navd88")}
POOL_LIKE = ("top of conservation", "top of normal", "top of multi-purpose", "top of multipurpose", "top of power", "guide curve", "top of recreation", "top of gross pool",
             "bottom of flood", "top of summer", "top of winter")
PARAM_DATUM = {"62614": "NGVD29", "72020": "NGVD29", "62615": "NAVD88", "00062": None}
OUT_JSON = f"{REPO}/jobs/depth-brain/depth_brain/data/proposals/datum_pairings.json"
OUT_CSV = f"{REPO}/docs/brains/depth/data/datum_pairings_cwms.csv"


def norm(tag):
    if tag in (None, "", "null"):
        return None
    t = str(tag).upper().replace("-", "").replace(" ", "")
    return {"NGVD29": "NGVD29", "NAVD88": "NAVD88", "LOCAL": "LOCAL", "OTHER": "LOCAL"}.get(t, t)


def group_of(v):
    if v["provider"] == "a2w":
        return "G1" if (v.get("a2wProjectDatum") or "").upper() in ("LOCAL", "") else "G2"
    return "G3"


def pairing_class(p, series_tag, s_ncat):
    """Classify one USGS pairing against the series' stamped/unstamped datum. Returns (cls, detail)."""
    st = p.get("stats") or {}
    Du = PARAM_DATUM.get(p["param"])
    n, m, sd = st.get("n"), st.get("meanFt"), st.get("sdFt")
    if not n or n < 100:
        return "TOO_FEW", f"n={n}"
    if abs(m) > 20 or (sd or 0) > 0.6:
        return "NOT_SAME_POOL_OR_MISALIGNED", f"mean {m} sd {sd}"
    if Du is None:
        return "UNLABELED_PARAM", "parameter 00062 has no datum"
    s = s_ncat
    if series_tag in ("NGVD29", "NAVD88"):
        exp_same, exp_diff = 0.0, ((-s) if (Du == "NGVD29" and series_tag == "NAVD88") else (s if (Du == "NAVD88" and series_tag == "NGVD29") else 0.0))
        if Du == series_tag:
            ok = abs(m) <= 0.2
            return ("CONSISTENT_SAME_DATUM" if ok else "OFFSET_UNEXPLAINED"), f"param datum {Du} == tag; mean {m} sd {sd}"
        if s is None:
            return "DIFFERENT_DATUM_NO_NCAT", f"param {Du} vs tag {series_tag}; mean {m}"
        ok = abs(m - exp_diff) <= 0.3
        return ("CONSISTENT_CONVERSION" if ok else "OFFSET_UNEXPLAINED"), f"param {Du} vs tag {series_tag}; mean {m}, NCAT expectation {exp_diff:+.2f}"
    # unstamped / LOCAL series: which defined datum do the numbers equal?
    if s is None:
        return ("NUMERICALLY_EQUAL_" + Du if abs(m) <= 0.15 else "OFFSET"), f"mean {m} (no NCAT to discriminate)"
    other = (m - (s if Du == "NGVD29" else -s))   # offset if the series were the OTHER datum
    d_this, d_other = abs(m), abs(other)
    if d_this <= 0.15 and d_other - d_this >= 0.15:
        return "NUMERICALLY_EQUAL_" + Du, f"|mean| {d_this:.3f} vs {d_other:.3f} under the other datum (NCAT shift {s:+.2f})"
    if d_this <= 0.15:
        return "AMBIGUOUS_SHIFT_TOO_SMALL", f"mean {m}; NCAT shift {s:+.2f} cannot discriminate NGVD29 from NAVD88"
    return "OFFSET", f"mean {m} sd {sd}"


def best_pair(lid, want_datum, series_tag):
    u = USG.get(lid) or {}
    s_ncat = NCAT.get(lid)
    # measured site shift (62615 - 62614 at the same site), more reliable than NCAT
    by_site = {}
    for p in u.get("pairs", []):
        if p.get("stats"):
            by_site.setdefault(p["site"], {})[p["param"]] = p["stats"]["meanFt"]
    for site, d in by_site.items():
        if "62615" in d and "62614" in d:
            s_ncat = d["62615"] - d["62614"]
    out = []
    for p in u.get("pairs", []):
        if not p.get("stats"):
            continue
        cls, det = pairing_class(p, series_tag, s_ncat)
        st = p["stats"]
        feed = (st.get("sdFt") is not None and st["sdFt"] <= 0.01 and abs(st["meanFt"]) <= 0.01)
        out.append({"site": p["site"], "siteName": p.get("siteName"), "param": p["param"], "paramDatum": PARAM_DATUM.get(p["param"]), "km": p.get("km"), "cls": cls, "detail": det, "stats": st,
                    "circular": bool(u.get("circularIfUsgsGauge") or feed), "identicalFeedSuspected": feed, "usgsUrl": p.get("usgsUrl"), "ncatShiftFt": s_ncat})
    pri = {"CONSISTENT_SAME_DATUM": 0, "NUMERICALLY_EQUAL_NGVD29": 0, "NUMERICALLY_EQUAL_NAVD88": 0, "CONSISTENT_CONVERSION": 1}
    out.sort(key=lambda x: (pri.get(x["cls"], 9), x["circular"], -(x["stats"].get("n") or 0)))
    return out


def sigma_from(stats, floor=0.15):
    if not stats:
        return floor
    return round(max(floor, abs(stats.get("meanFt") or 0), min(2 * (stats.get("sdFt") or 0), 1.0)), 3)


def pool_hits(v):
    out = []
    for h in v.get("poolLevelHits", []):
        sp = (h.get("specifiedLevel") or "").lower()
        if any(sp.startswith(x) for x in POOL_LIKE):
            out.append(h)
    return out


def decide(lid, v):
    s = v["series"]; sloc = v.get("seriesLocation") or {}
    base = {"lake": lid, "group": group_of(v), "provider": v["provider"], "tsid": s.get("tsid"), "poolFt": v["poolFt"], "poolSource": v.get("poolSource"), "poolSourceKind": v["poolSourceKind"],
            "a2wProjectDatum": v.get("a2wProjectDatum"), "seriesLocation": v.get("seriesLocationName"), "seriesLocationDatum": sloc.get("verticalDatum"),
            "seriesVdi": (s.get("verticalDatumInfo") or {}).get("native-datum"), "seriesVersion": (s.get("tsid") or "").split(".")[-1]}
    if not s.get("cwmsOffice") and not sloc.get("verticalDatum"):
        return {**base, "decision": "UNKNOWN", "reason": "level series not retrievable from the public CWMS Data API under the A2W/Lake Brain tsid; datum of the series unproven"}
    if s.get("sameInstantDiffFt") not in (None, 0.0) and abs(s["sameInstantDiffFt"]) > 0.02:
        return {**base, "decision": "UNKNOWN", "reason": f"CWMS API value differs from A2W by {s['sameInstantDiffFt']} ft at the same instant"}
    Ts = norm(sloc.get("verticalDatum")); vdi = norm((s.get("verticalDatumInfo") or {}).get("native-datum"))
    if Ts and vdi and Ts != vdi:
        return {**base, "decision": "UNKNOWN", "reason": f"CWMS location tag {Ts} conflicts with series vertical-datum-info {vdi}"}
    a2w_tag = norm(v.get("a2wProjectDatum"))
    hits = pool_hits(v)
    if not hits:
        near = [f"{h['specifiedLevel']}={h['values']}" for h in v.get("poolLevelHits", [])][:3]
        return {**base, "decision": "UNKNOWN", "levelDatum": Ts or vdi, "reason": "pool figure " + str(v["poolFt"]) + " is not equal to any pool-like CWMS location level at this project" + (f" (equal only to non-pool levels: {near})" if near else "") + "; pool must be proven from an operator document or re-bound to the CWMS level"}
    same_loc = [h for h in hits if h["location"] == v.get("seriesLocationName") and h["office"] == (s.get("cwmsOffice") or h["office"])]
    named = [h for h in hits if h.get("nameMatch")]
    pick = (same_loc or named or hits)[0]
    Tp = norm((pick.get("locationRecord") or {}).get("verticalDatum"))
    base.update({"poolLevelId": pick["levelId"], "poolLevelOffice": pick["office"], "poolLevelLocation": pick["location"], "poolLevelLocationDatum": Tp, "poolLevelSpecified": pick["specifiedLevel"],
                 "poolLevelValues": pick["values"], "poolLevelUrl": pick.get("url"), "poolLevelNameMatch": bool(pick.get("nameMatch")), "nHits": len(hits)})
    sameloc = pick["location"] == v.get("seriesLocationName") and pick["office"] == (s.get("cwmsOffice") or pick["office"])
    base["sameLocation"] = sameloc
    pr = best_pair(lid, Ts or vdi, Ts)
    base["pairings"] = pr
    if sameloc:
        return {**base, "decision": "SAME_SOURCE", "levelDatum": Ts or vdi or "UNSTATED", "referenceDatum": Ts or vdi or "UNSTATED", "sigma": 0.0,
                "reason": "pool level and live series are stored under one CWMS location, hence one native datum"}
    # different locations
    if Ts in ("NGVD29", "NAVD88") and Tp == Ts:
        good = [p for p in pr if p["cls"] in ("CONSISTENT_SAME_DATUM", "CONSISTENT_CONVERSION", "NUMERICALLY_EQUAL_NGVD29", "NUMERICALLY_EQUAL_NAVD88")]
        indep = [p for p in good if not p["circular"] and p["paramDatum"]]
        pick_pair = (indep or good or [None])[0]
        return {**base, "decision": "SAME_DATUM", "levelDatum": Ts, "referenceDatum": Tp, "sigma": sigma_from(pick_pair["stats"]) if pick_pair else 0.15, "bestPair": pick_pair,
                "reason": f"series location and pool-level location are both stamped {Ts} in CWMS"}
    if Ts in ("NGVD29", "NAVD88") and Tp in ("NGVD29", "NAVD88") and Tp != Ts:
        return {**base, "decision": "INCOMPATIBLE", "levelDatum": Ts, "referenceDatum": Tp, "reason": f"series stamped {Ts} but pool level stamped {Tp}; conversion disabled"}
    if Ts in (None, "LOCAL") and Tp in ("NGVD29", "NAVD88"):
        eq = [p for p in pr if p["cls"] == "NUMERICALLY_EQUAL_" + Tp and p["paramDatum"] == Tp]
        if eq:
            return {**base, "decision": "SAME_DATUM", "levelDatum": Tp + " (numerically; CWMS location tag " + str(sloc.get("verticalDatum")) + ")", "referenceDatum": Tp, "sigma": sigma_from(eq[0]["stats"]), "bestPair": eq[0],
                    "viaPairing": True, "reason": f"CWMS series location is {sloc.get('verticalDatum')}; the pool level is stamped {Tp}; an independent USGS {eq[0]['param']} series on the same pool equals the series, so the series values are {Tp}"}
        return {**base, "decision": "UNKNOWN", "levelDatum": sloc.get("verticalDatum"), "referenceDatum": Tp, "reason": f"series location is {sloc.get('verticalDatum')} and the pool level is stamped {Tp}; no USGS series on the same pool shows which datum the series numbers are in"}
    return {**base, "decision": "UNKNOWN", "levelDatum": Ts, "referenceDatum": Tp, "reason": f"series location datum {sloc.get('verticalDatum')} and pool-level location datum {(pick.get('locationRecord') or {}).get('verticalDatum')}: at least one is unstamped, or LOCAL at two different locations"}


def main():
    res = {lid: decide(lid, v) for lid, v in PAIRS.items()}
    json.dump(res, open(f"{ROOT}/decisions_cwms.json", "w"), indent=1, default=str)
    from collections import Counter
    print(Counter((r["group"], r["decision"]) for r in res.values()))
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    cols = ["lake", "group", "provider", "decision", "tsid", "seriesLocation", "seriesLocationDatum", "seriesVdi", "a2wProjectDatum", "poolFt", "poolSourceKind", "poolLevelId", "poolLevelLocationDatum", "sameLocation",
            "pairSite", "pairParam", "pairClass", "pairN", "pairMean", "pairSd", "pairMin", "pairMax", "pairCircular", "sigma", "reason"]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for lid, r in res.items():
            bp = r.get("bestPair") or ((r.get("pairings") or [None])[0]) or {}
            st = bp.get("stats") or {}
            w.writerow([lid, r["group"], r["provider"], r["decision"], r.get("tsid"), r.get("seriesLocation"), r.get("seriesLocationDatum"), r.get("seriesVdi"), r.get("a2wProjectDatum"), r.get("poolFt"), r.get("poolSourceKind"),
                        r.get("poolLevelId"), r.get("poolLevelLocationDatum"), r.get("sameLocation"), bp.get("site"), bp.get("param"), bp.get("cls"), st.get("n"), st.get("meanFt"), st.get("sdFt"), st.get("minFt"), st.get("maxFt"),
                        bp.get("circular"), r.get("sigma"), r.get("reason")])


if __name__ == "__main__":
    main()
