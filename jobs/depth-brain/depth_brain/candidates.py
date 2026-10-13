"""Offline builder of the Depth candidate manifest (Phase 6). Never run by the shadow job.

Inputs (all read-only, all small):
  directory   canonical lake directory (GET /lakes; snapshot JSON)
  bindings    Lake Brain research-verified bindings (verified_bindings_v2.csv): which lakes COULD get a live direct level
  reviewed    lake ids with a REVIEWED Lake Brain binding in Sources/SectorEngine/LakeBrain/LakeSourceBindings.swift (live today)
  full_pool   docs/data/full_pool.csv (reference-pool source strings)
  providers   data/datum_providers.json (datum audit)
  matrix      research fleet evidence matrix; contour_truth for zones; operating_range for history; licences if present
Output: data/candidates.json (+ a CSV for docs). Everything unknown stays unknown."""
from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter

from . import contract as C
from . import zones as Z
from .datum import DATA_DIR, DatumAssessment, assess, load_provider_table, normalize_datum, provider_level_datum
from . import proposals
from .evidence import depth_tier_from_research

USGS_PARAM_DATUM = {"62614": "NGVD29", "62615": "NAVD88"}       # USGS parameter definitions: surface elevation above NGVD 1929 / NAVD 1988


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def reviewed_lake_ids(swift_path: str) -> list[str]:
    txt = open(swift_path).read()
    ids = set(re.findall(r'lakeId:\s*"([^"]+)"', txt))
    ids |= set(re.findall(r'tvaPilot\(\s*"([^"]+)"', txt))
    return sorted(i for i in ids if "|" in i)


def cwms_project(s: str | None) -> str | None:
    """'Bankhead.Elev.Inst.15Minutes.0.Raw-USGS' or 'CWMS Abiquiu.Elev.Inst.0.Top of Conservation (max)' -> project token."""
    if not s:
        return None
    m = re.search(r"(?:CWMS\s+)?([A-Za-z0-9_\- ]+?)\.Elev", s)
    return m.group(1).strip().lower() if m else None


def reference_datum_for(source: str | None, table: dict) -> tuple[str | None, bool, str | None]:
    """Datum of the reference-pool figure, from the audited source-pattern table. -> (datum, verified, matchedPattern)."""
    if not source:
        return None, False, None
    low = source.lower()
    for pat, rec in (table.get("referencePoolSources") or {}).items():
        if pat.lower() in low:
            d = normalize_datum(rec.get("datum"))
            return d, bool(d and rec.get("basis") in ("verified_doc", "verified_data")), pat
    return None, False, None


def level_datum_for(binding: dict, table: dict) -> tuple[str | None, bool, str]:
    prov = (binding.get("provider") or "").lower()
    if prov in ("usgs", "usgs-d"):
        p = (binding.get("series_or_param") or "").split("+")[0]
        d = USGS_PARAM_DATUM.get(p)
        if d:
            return d, True, f"USGS parameter {p} is defined against {d}"
    d, verified, raw = provider_level_datum(table, prov)
    return d, verified, f"provider table: {raw}" if raw else "provider not in datum audit"


def licence_for(sources: list, lic: dict) -> dict:
    """Most restrictive wins; `unknown`/missing counts as NOT allowed. Only sources that actually carry depth evidence matter."""
    if not sources:
        return {"classes": [], "customerDerivedMetricsAllowed": "n/a"}
    classes, allowed = [], True
    for sk in sources:
        r = lic.get(sk)
        classes.append(r["classification"] if r else "UNREVIEWED")
        if not r or str(r.get("customerDerivedMetricsAllowed")).lower() != "true":
            allowed = False
    return {"classes": classes, "sources": list(sources), "customerDerivedMetricsAllowed": "true" if allowed else "false"}


def assess_candidate(lid, lk, b, src_str, table, cwms_locs, overrides, a2w=None):
    """Datum relationship for one lake -> (assessment, level_datum, level_verified, level_note, ref_datum, ref_verified, ref_rule, blocked_extra).
    Order: per-lake reviewed override > operator rules (TVA system, CWMS same location) > both-datums-stated > UNKNOWN."""
    prov = ((b or {}).get("provider") or "").lower()
    ld, ld_ver, ld_note = level_datum_for(b, table) if b else (None, False, "no binding")
    rd, rd_ver, rd_pat = reference_datum_for(src_str, table)
    loc = cwms_locs.get(lid) or {}
    if normalize_datum(loc.get("datum")):
        rd, rd_ver, rd_pat = normalize_datum(loc["datum"]), True, f"CWMS API vertical-datum {loc.get('office')}/{loc.get('location')}"
    if prov == "a2w" and (a2w or {}).get(lid, {}).get("verticalDatum"):
        d = normalize_datum(a2w[lid]["verticalDatum"])
        if d in ("NGVD29", "NAVD88"):                                  # LOCAL project tags are unresolved, never trusted as equal
            ld, ld_ver, ld_note = d, True, f"A2W project vertical_datum {a2w[lid]['verticalDatum']} ({a2w[lid]['office']}:{a2w[lid]['code']})"
    blocked = []
    if prov == "duke":
        blocked.append("DUKE_LOCAL_SCALE_NOT_ENABLED")      # series is a 100-based local scale; shift = scale - 100 (unverified, API now 403)
    same_src = bool(b and prov.startswith("cwms") and src_str and cwms_project(src_str) and cwms_project(src_str) == cwms_project(b.get("series_or_param")))
    same_sys = bool(prov == "tva" and (src_str or "").startswith("TVA"))
    ov = overrides.get(lid)
    if ov:
        a = DatumAssessment(ov["status"], float(ov["sigmaFt"]), 0.0, ["reviewed per-lake datum override (evidence in datum_lake_overrides.json)"])
        return a, normalize_datum(ov.get("levelDatum")) or ld, True, "reviewed override", normalize_datum(ov.get("referenceDatum")) or rd, True, "override", blocked
    a = assess(ld, rd, same_source=same_src, same_operator_system=same_sys, level_datum_verified=ld_ver, reference_datum_verified=rd_ver)
    return a, ld, ld_ver, ld_note, rd, rd_ver, rd_pat, blocked


def range_class(p05_p95: float | None) -> str | None:
    if p05_p95 is None:
        return None
    return "GE4FT" if p05_p95 >= 4 else ("1P5TO4FT" if p05_p95 >= 1.5 else "LT1P5FT")


def build(paths: dict, manifest_version: str) -> dict:
    table = load_provider_table(paths.get("providers"))
    directory = json.load(open(paths["directory"]))["lakes"]
    bind = {r["lake_id"]: r for r in read_csv(paths["bindings"])}
    pool = {r["id"]: r for r in read_csv(paths["full_pool"])}
    reviewed = set(reviewed_lake_ids(paths["reviewed_swift"]))
    matrix = {r["lakeId"]: r for r in read_csv(paths["matrix"])}
    truth = {r["lakeId"]: r for r in read_csv(paths["contour_truth"])}
    oprange = {r["lake"]: r for r in read_csv(paths["operating_range"])}
    lic = {r["sourceKey"]: r for r in read_csv(paths["licences"])} if paths.get("licences") and os.path.exists(paths["licences"]) else {}
    cwms_locs = json.load(open(paths["cwms_locations"]))["lakes"] if paths.get("cwms_locations") and os.path.exists(paths["cwms_locations"]) else {}
    a2w = json.load(open(paths["a2w_datums"]))["lakes"] if paths.get("a2w_datums") and os.path.exists(paths["a2w_datums"]) else {}
    overrides = json.load(open(paths["overrides"])) if paths.get("overrides") and os.path.exists(paths["overrides"]) else {}
    twdb_ver = proposals.twdb_updates(paths.get("twdb_reference_pools")) if paths.get("twdb_reference_pools") else {}
    twdb_all = (proposals.load(paths["twdb_reference_pools"]) or {}).get("lakes", {}) if paths.get("twdb_reference_pools") else {}
    conv = {r["id"]: float(r["shift_ft_ngvd29_to_navd88"]) for r in read_csv(paths["datum_shift"]) if r.get("shift_ft_ngvd29_to_navd88")}
    out = []
    for lk in directory:
        lid = lk["id"]
        b = bind.get(lid)
        p = pool.get(lid)
        m = matrix.get(lid, {})
        ref_conf = lk.get("poolConfidence")
        src_str = p["source"] if p else None
        blocked: list[str] = []
        # level side
        if lid in reviewed:
            lstat = "LIVE_REVIEWED"
        elif b and b.get("binding_status") in ("VERIFIED", "VERIFIED_CORROBORATED"):
            lstat = "RESEARCH_VERIFIED"
        elif b and b.get("binding_status") in ("VERIFIED_ENVELOPE", "VERIFIED_FLAG"):
            lstat = "RESEARCH_VERIFIED_LABELLED"          # verified under the labelled v1.1 rules: usable, never HIGH_CONFIDENCE
        else:
            lstat = "NONE"
        cap = b.get("capability_class") if b else None
        if lk.get("poolBasis") != "fullPool":
            blocked.append("REFERENCE_NOT_A_POOL_ELEVATION")
        if ref_conf not in C.REFERENCE_CONF_ALLOWED:
            blocked.append("REFERENCE_POOL_CONFIDENCE_LOW")
        if lk.get("fullPoolFt") is None:
            blocked.append("MISSING_REFERENCE_POOL")
        if lstat == "NONE":
            blocked.append("NO_VERIFIED_LEVEL_BINDING")
        elif cap not in C.ALLOWED_LEVEL_CAPABILITIES and lstat != "LIVE_REVIEWED":
            blocked.append("LEVEL_SOURCE_NOT_DIRECT")
        conv_ft = conv.get(lid)
        a, ld, ld_ver, ld_note, rd, rd_ver, rd_pat, extra = assess_candidate(lid, lk, b, src_str, table, cwms_locs, overrides, a2w)   # conversion NOT enabled
        blocked.extend(extra)
        if lstat != "NONE" and not a.usable and not extra:
            blocked.append("DATUM_UNKNOWN" if a.status == "UNKNOWN" else ("DATUM_CONVERSION_NOT_ENABLED" if (ld and rd and {ld, rd} == {"NGVD29", "NAVD88"}) else "DATUM_INCOMPATIBLE"))
        shift_possible = not blocked
        # history
        hr = oprange.get(lid)
        hyears = int(float(hr["full_years"])) if hr and hr.get("full_years") else (int(b["complete_years"]) if b and b.get("complete_years") else None)
        rclass = range_class(float(hr["p05_p95_range_ft"])) if hr and hr.get("p05_p95_range_ft") else None
        # rollout
        if shift_possible and lstat == "LIVE_REVIEWED":
            rollout = "PILOT_VERIFIED"
        elif shift_possible and lstat == "RESEARCH_VERIFIED" and ref_conf == "high" and a.status in ("SAME_SOURCE", "SAME_OPERATOR_SYSTEM", "SAME_DATUM") and (hyears or 0) >= 10 and cap in C.ALLOWED_LEVEL_CAPABILITIES:
            rollout = "HIGH_CONFIDENCE"
        elif shift_possible:
            rollout = "MEDIUM_CONFIDENCE"
        else:
            rollout = "BLOCKED"
        # evidence + zones
        rt = m.get("evidenceTier", "U")
        tier = depth_tier_from_research(rt)
        # evidence kind is about DEPTH: contours (incl. partial / the single IENC contour) are `contour`; stage-area hypsometry says nothing about depth -> `unknown`
        kind = "contour" if rt in ("A", "B", "B-partial", "B-binary") else ("proxy" if tier == "D" else "unknown")
        ev = {"tier": tier, "researchTier": rt, "kind": kind, "hypsometryOnly": rt == "C",
              # D/UNKNOWN evidence is never named as a depth source
              "bestSource": (m.get("bestDepthSource") if tier in ("A", "B", "C") else None),
              "contourSources": [s for s in (m.get("contourSources") or "").split(";") if s]}
        t = truth.get(lid)
        zr = None
        if t and tier in ("A", "B"):
            itv = float(t["interval_ft"]) if t.get("interval_ft") else (twdb_all.get(lid) or {}).get("contourIntervalFt")   # TWDB rows: interval from the verified survey facts
            sh = {"lt3": float(t["shr_0_3"]), "lt6": float(t["shr_0_3"]) + float(t["shr_3_6"]), "lt10": float(t["shr_0_3"]) + float(t["shr_3_6"]) + float(t["shr_6_10"])} \
                if all(t.get(k) not in (None, "") for k in ("shr_0_3", "shr_3_6", "shr_6_10")) else {}
            cov = float(t["cov_raster"]) if t.get("cov_raster") else None
            z = Z.reference_zones_from_shares(sh, itv, cov, tier, t.get("src", "?"))
            if z:
                zr = {"cumulative": {str(k): v for k, v in z.cumulative.items()}, "intervalFt": itv, "coverage": cov, "source": t.get("src"),
                      "referenceStatus": "UNVERIFIED", "referencePoolFt": None,
                      "note": "survey reference pool not verified for this lake: effective zones are withheld until it is"}
                ev.update({"coverage": cov, "intervalFt": itv})
        tw = twdb_ver.get(lid)
        if zr and tw:                                                  # survey reference pool verified AND preregistered validation passed
            zr.update({"referenceStatus": "VERIFIED", "referencePoolFt": tw["referencePoolFt"], "referencePoolDatum": tw["referencePoolDatum"],
                       "surveyYear": tw.get("surveyYear"), "note": "survey reference pool verified (docs/brains/depth/DEPTH_TWDB_REFERENCE_POOL_VERIFICATION.md)"})
            ev["surveyYear"] = tw.get("surveyYear")
        licence = licence_for(ev["contourSources"], lic)
        rec = {
            "lakeId": lid, "lakeName": lk.get("name"), "state": lk.get("state"), "operator": lk.get("operatorName"), "cwmsOffice": lk.get("cwmsOffice"),
            "reference": {"poolFt": lk.get("fullPoolFt"), "basis": lk.get("poolBasis"), "confidence": ref_conf, "source": src_str or "engine-directory:fullPoolFt",
                          "datum": rd, "datumVerified": rd_ver, "datumRule": rd_pat, "winterPoolFt": (float(p["winterPoolFt"]) if p and p.get("winterPoolFt") else None)},
            "levelSource": {"status": lstat, "provider": b.get("provider") if b else None, "series": b.get("series_or_param") if b else None,
                            "capability": cap, "datum": ld, "datumVerified": ld_ver, "datumNote": ld_note},
            "datum": {**a.as_dict(), "navd88MinusNgvd29Ft": conv_ft},
            "history": {"completeYears": hyears, "rangeClass": rclass, "p05p95RangeFt": float(hr["p05_p95_range_ft"]) if hr and hr.get("p05_p95_range_ft") else None},
            "shiftPossible": shift_possible, "blockedReasons": blocked, "rollout": rollout, "evidence": ev, "licence": licence,
        }
        if zr:
            rec["referenceZones"] = zr
        out.append(rec)
    summary = {
        "lakes": len(out), "shiftPossible": sum(r["shiftPossible"] for r in out),
        "rollout": dict(Counter(r["rollout"] for r in out)),
        "levelSourceStatus": dict(Counter(r["levelSource"]["status"] for r in out)),
        "datumStatus": dict(Counter(r["datum"]["status"] for r in out)),
        "blockedReasons": dict(Counter(x for r in out for x in r["blockedReasons"])),
        "tier": dict(Counter(r["evidence"]["tier"] for r in out)),
        "researchTier": dict(Counter(r["evidence"]["researchTier"] for r in out)),
        "zonesAvailableForReference": sum(1 for r in out if "referenceZones" in r),
        "providerTableProviders": sorted((table.get("providers") or {}).keys()),
    }
    return {"schema": "depth-candidates-v1", "manifestVersion": manifest_version, "summary": summary, "candidates": out}
