"""Offline builder of the Depth candidate manifest (Phase 6). Never run by the shadow job.

Inputs (all read-only, all small):
  directory   canonical lake directory (GET /lakes; snapshot JSON)
  bindings    Lake Brain research-verified bindings (verified_bindings_v2.csv): which lakes COULD get a live direct level
  reviewed    lake ids with a REVIEWED Lake Brain binding: Lake's contract brains/lake/contracts/reviewed-lake-bindings-v1.json
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

from depth_brain import contract as C
from depth_brain import zones as Z
from depth_brain.datum import DatumAssessment, assess, normalize_datum, provider_level_datum
from depth_brain import rating as R
from depth_brain.evidence import depth_tier_from_research

from . import proposals
from .paths import LAKE_BINDINGS, LAKE_PROPOSED_BINDINGS, RESEARCH_RECORDS, research_data

GREAT_LAKES_LWD = os.path.join(RESEARCH_RECORDS, "great_lakes_lwd.json")


def load_lwd(path: str = GREAT_LAKES_LWD) -> dict:
    """Great Lakes Low Water Datum record (depth-great-lakes-lwd-v1): lakeId -> {lwdFt, lake}. Absent file -> {} (no LWD references)."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    if d.get("schema") != "depth-great-lakes-lwd-v1" or normalize_datum(d.get("datum")) != "IGLD85":
        raise ValueError(f"{path}: not a depth-great-lakes-lwd-v1 IGLD 1985 record")
    urls = [e["url"] for e in d.get("evidence") or [] if str(e.get("url", "")).startswith("http")][:2]
    return {lid: {"lake": k, "lwdFt": float(d["lakes"][k]["lwdFt"]), "evidenceUrls": urls} for lid, k in (d.get("lakeIds") or {}).items()}


def load_provider_table(path: str | None = None) -> dict:
    """The provider datum document audit (research dataset). Absent -> an empty table (every provider datum stays unknown)."""
    p = path or research_data("datum_providers.json", required=False)
    if not p or not os.path.exists(p):
        return {"schema": "depth-datum-providers-v1", "providers": {}, "referencePoolSources": {}}
    with open(p) as f:
        return json.load(f)

USGS_PARAM_DATUM = {"62614": "NGVD29", "62615": "NAVD88"}       # USGS parameter definitions: surface elevation above NGVD 1929 / NAVD 1988


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def reviewed_lake_ids(contract_path: str = LAKE_BINDINGS) -> list[str]:
    """Lakes with a REVIEWED Lake Brain level binding, from Lake's published contract (brains/lake/contracts/reviewed-lake-bindings-v1.json,
    drift-checked against the compiled table). Depth never parses Lake's Swift source."""
    with open(contract_path, encoding="utf-8") as fh:
        d = json.load(fh)
    if d.get("schema") != "reviewed-lake-bindings-v1":
        raise ValueError(f"{contract_path}: not a reviewed-lake-bindings-v1 contract")
    return sorted(r["lakeId"] for r in d["reviewed"] if "|" in r["lakeId"])


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
    if prov == "coops" and "IGLD85" in (binding.get("series_or_param") or "").upper():
        return "IGLD85", True, "NOAA CO-OPS series water_level_IGLD85 (requested in IGLD 1985)"
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


VERIFICATION_RECORDS = os.path.join(RESEARCH_RECORDS, "datum_verification.json")
VERIFY_OFFSET_TOL_FT = 0.10          # plan section 3.2: source offset vs NOAA VDatum at the gauge
VERIFY_CONFLICT_FT = 0.25            # plan section 3.4: offsets further apart than this are a CONFLICT
VERIFY_MAX_PASSES = 2                # BRAIN_SPEC stop rule


def load_datum_verification(path: str | None = None) -> dict:
    """Per-lake datum verification records (records/datum_verification.json, schema depth-datum-verification-v1). Absent -> {}."""
    p = path or VERIFICATION_RECORDS
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    if d.get("schema") != "depth-datum-verification-v1":
        raise ValueError(f"{p}: not a depth-datum-verification-v1 file")
    return d.get("lakes") or {}


def _http_evidence(side: dict) -> list[dict]:
    """Evidence a reader can open, excluding carried-forward citations (`notEvidence: true`, e.g. a pointer back to candidates.json)."""
    return [e for e in (side or {}).get("evidence") or [] if str(e.get("url", "")).startswith("http") and not e.get("notEvidence")]


def _roots(side: dict) -> set[str]:
    """Independent roots of a side's evidence: `derivedFrom` (the upstream record a publisher re-serves, e.g. USGS-08025350) or the publisher itself."""
    return {str(e.get("derivedFrom") or str(e.get("publisher", "")).split(" (")[0]) for e in _http_evidence(side)}


def _side_verified(side: dict) -> bool:
    """VERIFIED needs two distinct ROOTS naming the datum (two publishers re-serving one gauge count once), or the series' own parameter
    definition plus a passed empirical check."""
    if (side or {}).get("status") != "VERIFIED" or normalize_datum(side.get("datum")) not in ("NGVD29", "NAVD88"):
        return False
    return len(_roots(side)) >= 2 or (side.get("basis") == "parameter-definition+empirical" and bool(_http_evidence(side)))


def _source_navd_minus_ngvd(side: dict) -> float | None:
    """A side's own NAVD88 - NGVD29 offset (CDA `offsets`), whichever direction it was published in."""
    if isinstance(side.get("offsetToNAVD88Ft"), (int, float)):
        return float(side["offsetToNAVD88Ft"])
    if isinstance(side.get("offsetToNGVD29Ft"), (int, float)):
        return -float(side["offsetToNGVD29Ft"])
    return None


def verification_problems(lid: str, rec: dict) -> list[str]:
    """Rule violations of one record (empty list = consistent with the plan's verification rule). Used by tests and by verified_conversion."""
    p = []
    status = rec.get("status")
    if status not in ("VERIFIED", "SAME_SOURCE", "SINGLE_SOURCE", "CONFLICT", "NONE"):
        p.append(f"unknown status {status!r}")
    if not 1 <= int(rec.get("passes") or 0) <= VERIFY_MAX_PASSES:
        p.append("passes must be 1..2")
    sides = rec.get("sides") or {}
    rel = rec.get("relationship") or {}
    for s in ("level", "reference"):
        side = sides.get(s) or {}
        if side.get("status") in ("VERIFIED", "SINGLE_SOURCE", "CONFLICT") and not _http_evidence(side):
            p.append(f"{s} side is {side['status']} without an http evidence item")
        off, vd = _source_navd_minus_ngvd(side), side.get("vdatumCheckFt")
        if off is not None and isinstance(vd, (int, float)) and abs(off - vd) > VERIFY_CONFLICT_FT + 1e-9:
            if not rec.get("offsetConflict"):
                p.append(f"{s} offset {off:+.3f} vs VDatum {vd:+.3f} differ by more than {VERIFY_CONFLICT_FT} ft: record it as offsetConflict")
            if status == "VERIFIED":
                p.append(f"{s} offset conflicts with VDatum: cannot be VERIFIED")
    if status != "NONE" and not any(_http_evidence(sides.get(s)) for s in ("level", "reference")):
        p.append("a record above NONE needs at least one http evidence item")
    if status == "VERIFIED":
        for s in ("level", "reference"):
            if not _side_verified(sides.get(s)):
                p.append(f"{s} side not verified by two independent roots")
            elif (sides.get(s) or {}).get("basis") == "parameter-definition+empirical" and (rel.get("empirical") or {}).get("passed") is not True:
                p.append(f"{s} side rests on its parameter definition but no empirical cross-gauge check passed")
        if rel.get("status") == "CONVERTED":
            off, vd = rel.get("navd88MinusNgvd29Ft"), rel.get("vdatumCheckFt")
            if not isinstance(off, (int, float)) or not isinstance(vd, (int, float)):
                p.append("conversion needs a source offset and a VDatum check")
            elif abs(off - vd) > VERIFY_OFFSET_TOL_FT + 1e-9:
                p.append(f"offset {off} vs VDatum {vd} differ by more than {VERIFY_OFFSET_TOL_FT} ft")
            emp = rel.get("empirical")
            if emp is not None and emp.get("passed") is not True:
                p.append("empirical check did not pass")
            lv, rf = (normalize_datum((sides.get(k) or {}).get("datum")) for k in ("level", "reference"))
            if {lv, rf} != {"NGVD29", "NAVD88"} or lv != normalize_datum(rel.get("levelDatum")) or rf != normalize_datum(rel.get("referenceDatum")):
                p.append("conversion datums do not match the verified sides")
    elif status == "SAME_SOURCE":
        sr = rec.get("sameRecord") or {}
        loc = sr.get("location") or "\0"
        if rel.get("status") != "SAME_SOURCE":
            p.append("SAME_SOURCE record needs relationship SAME_SOURCE")
        if not isinstance(sr.get("referencePoolFt"), (int, float)) or not sr.get("ownerDecision") or not sr.get("office"):
            p.append("SAME_SOURCE needs office, referencePoolFt and the owner's decision")
        if not (loc in str(sr.get("levelSeries", "")) and str(sr.get("referenceLevelId", "")).startswith(loc + ".")):
            p.append("level series and reference level are not on the same CWMS location")
        if normalize_datum(sr.get("referenceDatum")) not in ("NGVD29", "NAVD88"):
            p.append("SAME_SOURCE location datum must be NGVD29 or NAVD88")
        if not sr.get("liveSourceIds"):
            p.append("SAME_SOURCE must pin the reviewed live binding (liveSourceIds)")
        if sr.get("lakeBrainPoolFt") is not None and not isinstance(sr["lakeBrainPoolFt"], (int, float)):
            p.append("lakeBrainPoolFt must be a number")
    elif status == "CONFLICT":
        if not rec.get("conflict"):
            p.append("CONFLICT needs a stated conflict")
    if status not in ("VERIFIED", "SAME_SOURCE") and rel.get("status"):
        p.append("only a VERIFIED or SAME_SOURCE record may carry a relationship")
    return p


def verified_conversion(rec: dict | None) -> tuple[float, str, str] | None:
    """(navd88_minus_ngvd29_ft, level_datum, reference_datum) for a fully verified CONVERTED record, else None. Never an estimate."""
    if not rec or rec.get("status") != "VERIFIED" or (rec.get("relationship") or {}).get("status") != "CONVERTED" or verification_problems("", rec):
        return None
    r = rec["relationship"]
    return float(r["navd88MinusNgvd29Ft"]), normalize_datum(r["levelDatum"]), normalize_datum(r["referenceDatum"])


def reviewed_live_sources(contract_path: str = LAKE_BINDINGS) -> dict[str, list[str]]:
    """lakeId -> liveSourceIds of Lake's reviewed binding contract (reviewed-lake-bindings-v1)."""
    with open(contract_path, encoding="utf-8") as fh:
        d = json.load(fh)
    if d.get("schema") != "reviewed-lake-bindings-v1":
        raise ValueError(f"{contract_path}: not a reviewed-lake-bindings-v1 contract")
    return {r["lakeId"]: list(r.get("liveSourceIds") or []) for r in d["reviewed"]}


def live_source_location(source_id: str) -> tuple[str, str | None, str]:
    """'a2w:LRN:JPHT1:JPHT1-J_PERCY_PRIEST.Elev-Pool...' -> ('a2w', 'LRN', 'JPHT1'); 'cwms:LRN:JPHT1-J_PERCY_PRIEST.Elev...' -> ('cwms', 'LRN', 'JPHT1');
    'tva:JPHT1' -> ('tva', None, 'JPHT1'). The base location is the CWMS location id before its first '-' sub-location suffix."""
    parts = source_id.split(":")
    prov = parts[0].lower()
    if prov == "a2w" and len(parts) >= 4:
        office, loc = parts[1], parts[3].split(".")[0]
    elif prov == "cwms" and len(parts) >= 3:
        office, loc = parts[1], parts[2].split(".")[0]
    else:
        office, loc = None, (parts[1] if len(parts) > 1 else "").split(".")[0]
    return prov, office, loc.split("-")[0]


def same_source_binding_problems(sr: dict, live_ids: list[str] | None) -> list[str]:
    """SAME_SOURCE holds only while the live level binding is exactly the binding the record was decided on: same ids, and every id on the
    record's base location (and office, where the id carries one). A changed provider or location refuses the relationship."""
    if not live_ids:
        return ["lake has no reviewed live binding"]
    p = []
    if sorted(live_ids) != sorted(sr.get("liveSourceIds") or []):
        p.append(f"live binding changed: {sorted(live_ids)} != recorded {sorted(sr.get('liveSourceIds') or [])}")
    for sid in live_ids:
        prov, office, base = live_source_location(sid)
        if base != sr.get("location") or (office is not None and office != sr.get("office")):
            p.append(f"{sid}: base location {office}/{base} is not {sr.get('office')}/{sr.get('location')}")
    return p


def verified_same_source(rec: dict | None, live_ids: list[str] | None = None) -> dict | None:
    """The `sameRecord` block of a valid SAME_SOURCE record whose pinned live binding still matches Lake's reviewed contract, else None."""
    if not rec or rec.get("status") != "SAME_SOURCE" or verification_problems("", rec):
        return None
    if same_source_binding_problems(rec["sameRecord"], live_ids):
        return None
    return rec["sameRecord"]


def assess_candidate(lid, lk, b, src_str, table, cwms_locs, overrides, a2w=None, verification=None, live_sources=None):
    """Datum relationship for one lake -> (assessment, level_datum, level_verified, level_note, ref_datum, ref_verified, ref_rule, blocked_extra).
    Order: per-lake reviewed override > operator rules (TVA system, CWMS same location) > both-datums-stated > UNKNOWN.
    A NGVD29/NAVD88 pair is converted only when `verification` holds a fully VERIFIED CONVERTED record for this lake whose datums match."""
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
    if prov == "duke" and not (overrides.get(lid) or {}).get("levelScale"):
        blocked.append("DUKE_LOCAL_SCALE_NOT_ENABLED")      # series is a 100-based local scale (shift = scale - 100) until a reviewed override documents the frame
    same_src = bool(b and prov.startswith("cwms") and src_str and cwms_project(src_str) and cwms_project(src_str) == cwms_project(b.get("series_or_param")))
    same_sys = bool(prov == "tva" and (src_str or "").startswith("TVA"))
    ov = overrides.get(lid)
    if ov:
        a = DatumAssessment(ov["status"], float(ov["sigmaFt"]), 0.0, ["reviewed per-lake datum override (evidence in datum_lake_overrides.json)"], ov.get("confidence"),
                            f"reviewed-override:{ov.get('method') or 'manual'}:{ov.get('promotedFrom') or 'datum_lake_overrides.json'}",
                            [e["url"] for e in (ov.get("evidence") or []) if isinstance(e, dict) and str(e.get("url", "")).startswith("http")][:2])
        return a, normalize_datum(ov.get("levelDatum")) or ld, True, "reviewed override", normalize_datum(ov.get("referenceDatum")) or rd, True, "override", blocked
    vrec = (verification or {}).get(lid)
    sr = verified_same_source(vrec, (live_sources or {}).get(lid))
    if sr:
        a = DatumAssessment("SAME_SOURCE", C.SIGMA_DATUM["SAME_SOURCE"], 0.0, [f"reference and level share CWMS location {sr['office']}/{sr['location']}"], None,
                            "datum-verification:same-cwms-location:records/datum_verification.json",
                            [f"https://cwms-data.usace.army.mil/cwms-data/locations/{sr['location']}?office={sr['office']}"])
        rd = normalize_datum(sr["referenceDatum"])
        return a, ld, ld_ver, ld_note, rd, True, f"CWMS level {sr['office']}/{sr['referenceLevelId']}", blocked
    vc = verified_conversion(vrec)
    conv_ft = vc[0] if vc and ld_ver and rd_ver and (ld, rd) == (vc[1], vc[2]) else None
    a = assess(ld, rd, same_source=same_src, same_operator_system=same_sys, level_datum_verified=ld_ver, reference_datum_verified=rd_ver,
               navd88_minus_ngvd29_ft=conv_ft)
    if a.status == "CONVERTED":
        a.basis = "datum-verification:records/datum_verification.json"
        a.evidence_urls = [e["url"] for s in ("level", "reference") for e in (vrec["sides"][s].get("evidence") or [])
                           if str(e.get("url", "")).startswith("http")][:2]
        return a, ld, ld_ver, ld_note, rd, rd_ver, rd_pat, blocked
    if a.usable:
        a.basis = ("cwms-location-same-record" if same_src else "tva-operator-system" if same_sys else
                   f"stated-datums:level[{ld_note[:60]}]+reference[{(rd_pat or 'cwms-location-api')[:60]}]")
        if same_sys:
            a.evidence_urls = ["docs/brains/depth/DEPTH_TVA_DATUM_CONFIRMATION.md"]
        elif not same_src and not loc.get("datum"):
            a.evidence_urls = ["docs/brains/depth/DEPTH_DATUM_AUDIT.md"]
        if same_src or loc.get("datum"):
            a.evidence_urls = [f"https://cwms-data.usace.army.mil/cwms-data/locations/{loc.get('location') or ''}?office={loc.get('office') or ''}"] if loc.get("location") else []
    if a.usable and not a.evidence_urls:
        a.evidence_urls = ["docs/brains/depth/DEPTH_DATUM_AUDIT.md"]                  # always give a reader somewhere to check
    return a, ld, ld_ver, ld_note, rd, rd_ver, rd_pat, blocked


# Lake's five hand-written pilots (Lake's LakeSourceBindings `handWritten` rows), restated as data: Depth never parses
# Lake's Swift. live[0] and history in the bindings.proposed.v1.json shape. Keep in step with that file.
LAKE_PILOT_BINDINGS = {
    **{lid: {"live": [{"provider": "tva", "station": loc, "series": None}],
             "history": [{"kind": "sharedTVAArchive", "locationId": loc}, {"kind": "tvaOperatingGuide", "locationId": loc}]}
       for lid, loc in (("Guntersville|AL", "GVDA1"), ("Wheeler|AL", "WHLA1"), ("Wilson|AL", "WLSA1"), ("Pickwick Lake|TN", "PICT1"))},
    "Lake Hartwell|SC": {"live": [{"provider": "cwms", "station": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS"}],
                         "history": [{"kind": "cwmsDaily", "office": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS"}]},
}


def load_lake_bindings(path: str = LAKE_PROPOSED_BINDINGS) -> dict:
    """lakeId -> Lake binding {live, history}: the hand-written pilots first, then bindings.proposed.v1.json. Absent file -> pilots only."""
    out = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            out = {r["lakeId"]: r for r in json.load(fh).get("bindings") or []}
    out.update(LAKE_PILOT_BINDINGS)
    return out


def _cwms_location(series: str | None) -> str | None:
    return series.split(".", 1)[0].strip().lower() if series and "." in series else None


def _cwms_parameter(series: str | None) -> str | None:
    """'Hartwell.Elev-Pool.Inst.1Hour.0.Raw' -> 'elev-pool' (the CWMS parameter: Elev-Pool and Elev-GC are different series)."""
    parts = (series or "").split(".")
    return parts[1].strip().lower() if len(parts) > 1 and parts[1].strip() else None


def history_is_live_series(binding: dict | None) -> bool:
    """True only when Lake's ONE history source is the same series as its primary live source, with the same offset:
    usgs = same site and param; nwps/hads = same lid, HP pe; cwms/a2w = same office, CWMS location (before the first '.') and parameter (second segment, e.g. Elev vs Elev-Pool vs Elev-GC)."""
    if not binding or len(binding.get("history") or []) != 1 or not binding.get("live"):
        return False
    lv, h = binding["live"][0], binding["history"][0]
    prov, kind = (lv.get("provider") or "").lower(), h.get("kind")
    if float(h.get("offsetFt") or 0.0) != float(lv.get("datumOffsetFt") or 0.0):
        return False
    if prov == "usgs" and kind == "usgsDaily":
        return bool(lv.get("station")) and lv.get("station") == h.get("site") and lv.get("series") == h.get("param")
    if prov in ("nwps", "hads") and kind == "hadsDaily":
        return (bool(lv.get("station")) and lv.get("station").upper() == (h.get("lid") or "").upper()
                and str(lv.get("series") or "").upper().startswith("HP") and str(h.get("pe") or "").upper().startswith("HP"))
    if prov in ("cwms", "a2w") and kind == "cwmsDaily":
        office = (lv.get("station") or "").split(":", 1)[0].upper()
        loc = _cwms_location(lv.get("series"))
        param = _cwms_parameter(lv.get("series"))
        return (bool(office and loc and param) and office == (h.get("office") or "").upper() and loc == _cwms_location(h.get("series"))
                and param == _cwms_parameter(h.get("series")))
    return False


def alternative_reference(lid: str, blocked: list, level_datum: str | None, level_datum_verified: bool, history_years: int | None, lwd: dict,
                          lake_binding: dict | None = None, directory_basis: str | None = None):
    """The owner-approved references for lakes whose fullPool route is blocked ONLY on the reference side (contract.SERIES_REFERENCE_ELIGIBLE).
    -> (basis or None, DatumAssessment or None, blocked reasons). A lake with no blocked reason is never touched: its fullPool route stands.
    Order: Great Lakes Low Water Datum (IGLD 1985 level on both sides) > the gauge's own seasonal median > unchanged. The median needs
    enough history (SERIES_HISTORY_TOO_SHORT), Lake's history to be its live series (SERIES_HISTORY_NOT_LIVE_SERIES), and, for a lake whose
    directory basis is fullPool, the scope switch C.SERIES_MEDIAN_ALLOW_FULL_POOL_RESERVOIRS (SERIES_MEDIAN_FULL_POOL_RESERVOIR_OFF)."""
    if not blocked or any(r not in C.SERIES_REFERENCE_ELIGIBLE for r in blocked):
        return None, None, list(blocked)                    # level-side failures, known-datum conflicts, Duke scale: no substitute reference
    g = lwd.get(lid)
    if g and level_datum == "IGLD85" and level_datum_verified:
        a = assess("IGLD85", "IGLD85")
        a.basis, a.evidence_urls = f"great-lakes-lwd:{g['lake']}", list(g.get("evidenceUrls") or [])[:2]
        return "lowWaterDatum", a, []
    if (history_years or 0) < C.SERIES_MEDIAN_MIN_YEARS:
        return None, None, list(blocked) + ["SERIES_HISTORY_TOO_SHORT"]
    if not history_is_live_series(lake_binding):
        return None, None, list(blocked) + ["SERIES_HISTORY_NOT_LIVE_SERIES"]
    if directory_basis == "fullPool" and not C.SERIES_MEDIAN_ALLOW_FULL_POOL_RESERVOIRS:
        return None, None, list(blocked) + ["SERIES_MEDIAN_FULL_POOL_RESERVOIR_OFF"]
    a = assess(None, None, same_series=True)
    a.basis, a.evidence_urls = "same-series:lake-brain-seasonal-median", ["brains/depth/BRAIN_SPEC.md"]
    return "seriesMedian", a, []


def range_class(p05_p95: float | None) -> str | None:
    if p05_p95 is None:
        return None
    return "GE4FT" if p05_p95 >= 4 else ("1P5TO4FT" if p05_p95 >= 1.5 else "LT1P5FT")


def build(paths: dict, manifest_version: str) -> dict:
    table = load_provider_table(paths.get("providers"))
    directory = json.load(open(paths["directory"]))["lakes"]
    bind = {r["lake_id"]: r for r in read_csv(paths["bindings"])}
    pool = {r["id"]: r for r in read_csv(paths["full_pool"])}
    reviewed = set(reviewed_lake_ids(paths.get("reviewed_bindings") or LAKE_BINDINGS))
    matrix = {r["lakeId"]: r for r in read_csv(paths["matrix"])}
    truth = {r["lakeId"]: r for r in read_csv(paths["contour_truth"])}
    oprange = {r["lake"]: r for r in read_csv(paths["operating_range"])}
    lic = {r["sourceKey"]: r for r in read_csv(paths["licences"])} if paths.get("licences") and os.path.exists(paths["licences"]) else {}
    cwms_locs = json.load(open(paths["cwms_locations"]))["lakes"] if paths.get("cwms_locations") and os.path.exists(paths["cwms_locations"]) else {}
    a2w = json.load(open(paths["a2w_datums"]))["lakes"] if paths.get("a2w_datums") and os.path.exists(paths["a2w_datums"]) else {}
    overrides = json.load(open(paths["overrides"])) if paths.get("overrides") and os.path.exists(paths["overrides"]) else {}
    equiv_all = (json.load(open(paths["local_equivalence"])) if paths.get("local_equivalence") and os.path.exists(paths["local_equivalence"]) else {}).get("lakes", {})
    curves = R.load_curves(paths["stage_area"]) if paths.get("stage_area") and os.path.exists(paths["stage_area"]) else {}
    twdb_ver = proposals.twdb_updates(paths.get("twdb_reference_pools")) if paths.get("twdb_reference_pools") else {}
    twdb_all = (proposals.load(paths["twdb_reference_pools"]) or {}).get("lakes", {}) if paths.get("twdb_reference_pools") else {}
    verification = load_datum_verification(paths.get("datum_verification"))
    live_sources = reviewed_live_sources(paths.get("reviewed_bindings") or LAKE_BINDINGS)
    conv = {r["id"]: float(r["shift_ft_ngvd29_to_navd88"]) for r in read_csv(paths["datum_shift"]) if r.get("shift_ft_ngvd29_to_navd88")}
    lwd = load_lwd(paths.get("great_lakes_lwd") or GREAT_LAKES_LWD)
    lake_bindings = load_lake_bindings(paths.get("lake_proposed_bindings") or LAKE_PROPOSED_BINDINGS)
    out = []
    for lk in directory:
        lid = lk["id"]
        b = bind.get(lid)
        p = pool.get(lid)
        sr = verified_same_source(verification.get(lid), live_sources.get(lid))
        pool_ft = float(sr["referencePoolFt"]) if sr else lk.get("fullPoolFt")      # owner-decided same-record reference replaces the directory pool
        m = matrix.get(lid, {})
        ref_conf = C.norm_pool_conf(lk.get("poolConfidence"))
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
        if pool_ft is None:
            blocked.append("MISSING_REFERENCE_POOL")
        if lstat == "NONE":
            blocked.append("NO_VERIFIED_LEVEL_BINDING")
        elif cap not in C.ALLOWED_LEVEL_CAPABILITIES and lstat != "LIVE_REVIEWED":
            blocked.append("LEVEL_SOURCE_NOT_DIRECT")
        conv_ft = conv.get(lid)
        a, ld, ld_ver, ld_note, rd, rd_ver, rd_pat, extra = assess_candidate(lid, lk, b, src_str, table, cwms_locs, overrides, a2w, verification, live_sources)  # converts only on a VERIFIED record
        blocked.extend(extra)
        if lstat != "NONE" and not a.usable and not extra:
            blocked.append("DATUM_UNKNOWN" if a.status == "UNKNOWN" else ("DATUM_CONVERSION_NOT_ENABLED" if (ld and rd and {ld, rd} == {"NGVD29", "NAVD88"}) else "DATUM_INCOMPATIBLE"))
        # history
        hr = oprange.get(lid)
        hyears = int(float(hr["full_years"])) if hr and hr.get("full_years") else (int(b["complete_years"]) if b and b.get("complete_years") else None)
        rclass = range_class(float(hr["p05_p95_range_ft"])) if hr and hr.get("p05_p95_range_ft") else None
        alt_basis, alt_a, blocked = alternative_reference(lid, blocked, ld, ld_ver, hyears, lwd, lake_bindings.get(lid), lk.get("poolBasis"))
        if alt_basis:
            a = alt_a
        shift_possible = not blocked
        # rollout
        if shift_possible and alt_basis:
            rollout = "MEDIUM_CONFIDENCE"                       # new reference bases: never HIGH_CONFIDENCE until field-validated
        elif shift_possible and lstat == "LIVE_REVIEWED":
            rollout = "PILOT_VERIFIED"
        elif shift_possible and lstat == "RESEARCH_VERIFIED" and ref_conf == "high" and a.status in ("SAME_SOURCE", "SAME_OPERATOR_SYSTEM", "SAME_DATUM") and a.evidence_confidence != "medium" and (hyears or 0) >= 10 and cap in C.ALLOWED_LEVEL_CAPABILITIES:
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
        rating_withheld = None
        if lid in curves and alt_basis:
            rating_withheld = "REFERENCE_NOT_FULL_POOL"                               # a rating is read at full pool: not used with a median or the LWD
        elif lid in curves and not (zr and zr.get("referenceStatus") == "VERIFIED"):                     # a validated contour reference (TWDB) keeps priority
            rz, why_r = R.rating_reference_zones(curves[lid], pool_ft, rd, rd_ver, a.status, {float(k): v for k, v in (zr or {}).get("cumulative", {}).items()} or None, equiv_all.get(lid))
            if rz:
                zr = rz
                ev["contourSources"] = list(ev["contourSources"]) + ["USBR_TSC" if curves[lid].get("office") == "USBR-TSC" else "USACE_CWMS"]
                if ev["kind"] in ("unknown", "proxy"):                                  # no measured contours: the rating is the depth-share evidence, at tier C (shares only)
                    tier, ev["tier"], ev["kind"] = "C", "C", "stage-area-rating"
                    ev["bestSource"] = "USACE CWMS elevation-area rating (shares only)"
                    ev["hypsometryOnly"] = False
            else:
                rating_withheld = why_r
        zones_withheld = None
        if alt_basis and zr:                                         # contour zones are read at the survey (full) pool: never shifted from a median or the LWD
            zones_withheld, zr = "REFERENCE_NOT_FULL_POOL", None
        licence = licence_for(ev["contourSources"], lic)
        rec = {
            "lakeId": lid, "lakeName": lk.get("name"), "state": lk.get("state"), "operator": lk.get("operatorName"), "cwmsOffice": lk.get("cwmsOffice"),
            "reference": {"poolFt": pool_ft, "basis": lk.get("poolBasis"), "confidence": ref_conf,
                          "source": (f"CWMS {sr['office']}/{sr['referenceLevelId']} ({sr['referencePoolFt']} ft)" if sr else src_str or "engine-directory:fullPoolFt"),
                          **({"lakeBrainPoolFt": float(sr["lakeBrainPoolFt"])} if sr and sr.get("lakeBrainPoolFt") is not None else {}),
                          "datum": rd, "datumVerified": rd_ver, "datumRule": rd_pat, "winterPoolFt": (float(p["winterPoolFt"]) if p and p.get("winterPoolFt") else None),
                          **({"relativeScalePoolFt": float(sc["fullPondScaleValue"])} if (sc := ((overrides.get(lid) or {}).get("levelScale") or {})).get("kind") == "DUKE_RELATIVE_100" else {})},
            "levelSource": {"status": lstat, "provider": b.get("provider") if b else None, "series": b.get("series_or_param") if b else None,
                            "capability": cap, "datum": ld, "datumVerified": ld_ver, "datumNote": ld_note,
                            **({"scale": sc["kind"]} if sc.get("kind") else {})},
            "datum": {**a.as_dict(), "navd88MinusNgvd29Ft": conv_ft},
            "history": {"completeYears": hyears, "rangeClass": rclass, "p05p95RangeFt": float(hr["p05_p95_range_ft"]) if hr and hr.get("p05_p95_range_ft") else None},
            "shiftPossible": shift_possible, "blockedReasons": blocked, "rollout": rollout, "evidence": ev, "licence": licence,
        }
        if alt_basis:
            directory_ref = {k: rec["reference"][k] for k in ("poolFt", "basis", "confidence", "source", "datum", "datumVerified", "datumRule")}
            if alt_basis == "lowWaterDatum":
                rec["reference"].update({"poolFt": lwd[lid]["lwdFt"], "basis": "lowWaterDatum", "confidence": "high", "datum": "IGLD85", "datumVerified": True,
                                         "datumRule": "research/tools/depth_research/records/great_lakes_lwd.json",
                                         "source": f"Great Lakes Low Water Datum ({lwd[lid]['lake']}), IGLD 1985: NOAA CO-OPS and CHS"})
            else:
                rec["reference"].update({"poolFt": None, "basis": "seriesMedian", "confidence": None, "datum": None, "datumVerified": False, "datumRule": None,
                                         "source": "lake-brain states/lake seasonalBand.p50 (this gauge's own history)",
                                         "seriesMedian": {"statistic": "p50", "windowDays": C.SERIES_MEDIAN_WINDOW_DAYS, "minBasisYears": C.SERIES_MEDIAN_MIN_YEARS,
                                                          "minSampleCount": C.SERIES_MEDIAN_MIN_SAMPLES, "manifestHistoryYears": hyears}})
            rec["reference"]["directory"] = directory_ref
            rec["reference"]["decision"] = "owner decision 2026-11-22, Sector_Ops #51 comment 7075545102"
        if zones_withheld:
            rec["referenceZonesWithheld"] = zones_withheld
        if zr:
            rec["referenceZones"] = zr
        if rating_withheld:
            rec["ratingZoneWithheld"] = rating_withheld
        out.append(rec)
    summary = {
        "lakes": len(out), "shiftPossible": sum(r["shiftPossible"] for r in out),
        "rollout": dict(Counter(r["rollout"] for r in out)),
        "levelSourceStatus": dict(Counter(r["levelSource"]["status"] for r in out)),
        "datumStatus": dict(Counter(r["datum"]["status"] for r in out)),
        "referenceBasis": dict(Counter(r["reference"]["basis"] for r in out if r["shiftPossible"])),
        "blockedReasons": dict(Counter(x for r in out for x in r["blockedReasons"])),
        "tier": dict(Counter(r["evidence"]["tier"] for r in out)),
        "researchTier": dict(Counter(r["evidence"]["researchTier"] for r in out)),
        "zonesAvailableForReference": sum(1 for r in out if "referenceZones" in r),
        "providerTableProviders": sorted((table.get("providers") or {}).keys()),
    }
    return {"schema": "depth-candidates-v1", "manifestVersion": manifest_version, "summary": summary, "candidates": out}
