#!/usr/bin/env python3
"""Coverage recovery plan: recompute, from the repository tables and the cached research data, why each of the 621 directory lakes is or is not an
eligible Lake Brain binding candidate, rank the recovery opportunities and project the effect on the UNMODIFIED rubric lake-brain-score-v1.

    python3 jobs/lake-brain/bindings/coverage_recovery_plan.py [--check]      writes jobs/lake-brain/data/coverage_recovery_plan.json

Nothing here writes a binding, promotes a lifecycle or edits a rubric. Every score is a PROJECTION ONLY: it holds only if the lakes of the tranche
pass human review, and the displayed value stays capped by the validation gate (5.0 while /validation/lake-brain is NOT_VALIDATED).

Inputs (sha256 recorded): bindings.proposed.v1.json / .excluded.json / .recovered.json and mismatch14_dispositions.json (repo); verified_bindings_v2.csv,
plan_flood_evidence.csv, lake_features.csv, history_extension.csv (research checkout); lake_geometry_flags.csv, directory_lakes_2026-10-13.json,
binding2/remaining_unbound.json, binding2/unbound_profile.json and the plan composite history (research data outside Git).

Bowfishing value: the directory has NO popularity or species-presence field. The proxy is the research heuristic of binding2/profile_unbound.py,
applied to all 621 lakes: size class (0-4) + state bowfishing prevalence (1-3) + regulated pool (+1) + warm-water lake (+1); tier A >= 8, B 6-7, C else.
It encodes judgement, not data (documented in LAKE_BRAIN_BINDING_GAPS_RESEARCH.md); it only orders opportunities, it never gates anything.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA_OUT = os.path.join(REPO, "jobs", "lake-brain", "data")
OUT = os.path.join(DATA_OUT, "coverage_recovery_plan.json")
sys.path.insert(0, os.path.join(REPO, "jobs", "brain_platform"))
from sector_brain_platform.scoring import score_lake  # noqa: E402  (the production rubric, unmodified)

_spec = importlib.util.spec_from_file_location("build_bindings_table", os.path.join(HERE, "build_bindings_table.py"))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

NOW = dt.datetime(2026, 10, 13, 12, 0, tzinfo=dt.timezone.utc)
DIRECTORY_TOTAL = 621

# ------------------------------------------------------------------------------------------------------------------------ taxonomy
STATE_W = {s: 3 for s in "AL AR FL GA IL IN IA KS KY LA MI MN MS MO NE NC ND OH OK SC SD TN TX WI VA".split()}
STATE_W.update({s: 2 for s in "CA MD PA NY NJ DE MA WV CO ID WA OR UT NV AZ NM MT WY".split()})
STATE_W.update({s: 1 for s in "AK HI ME NH VT CT RI".split()})
TERMS_WMD = {"sjrwmd", "nhdes"}


def bow_score(area_km2: float | None, state: str, regulated: bool, lake_class: str) -> tuple[int, str]:
    """Research heuristic (binding2/profile_unbound.py) - not data. size class + state prevalence + regulated pool + warm-water."""
    a = 0.5 if area_km2 in (None, 0) else float(area_km2)
    size = 0 if a < 2 else 1 if a < 5 else 2 if a < 15 else 3 if a < 50 else 4
    warm = 0 if (state == "AK" or (lake_class or "").startswith("N1a")) else 1
    s = size + STATE_W.get(state, 2) + (1 if regulated else 0) + warm
    return s, ("A" if s >= 8 else "B" if s >= 6 else "C")


def blockers_for(reason_codes: set[str], provider: str, coord_flag: str, mismatch_disposition: str | None = None) -> set[str]:
    """Map generator reason codes to RECOVERY LEVERS. A lake is recoverable once every lever on it is pulled."""
    out = set()
    for c in reason_codes:
        if c == "history-live-mismatch":
            out.add(f"mismatch:{mismatch_disposition or 'UNCLASSIFIED'}")
        elif c == "coordinate-flag":
            out.add({"off_water": "coord:off_water", "identity_risk": "coord:identity_risk"}.get(coord_flag, "coord:no_polygon"))
        elif c == "post-hoc":
            out.add("posthoc")
        elif c in ("flagged", "flagged-wave1"):
            out.add("flag")
        elif c == "stage-only":
            out.add("stage")
        elif c == "undocumented-provider":
            out.add("terms:sjrwmd_nhdes" if provider in TERMS_WMD else "terms:undocumented")
        elif c == "provider-not-allowed":
            out.add("adapter")
        elif c == "no-adapter-series":
            out.add("adapter")
        else:
            raise ValueError(c)
    return out


# ------------------------------------------------------------------------------------------------------------------------ quality
def composite_years(lb_data: str, lake: str) -> int | None:
    p = os.path.join(lb_data, "plan", "history", "composite", re.sub(r"[^A-Za-z0-9]+", "_", lake).strip("_") + ".csv.gz")
    if not os.path.exists(p):
        return None
    by = collections.Counter()
    with gzip.open(p, "rt") as fh:
        for line in fh:
            y = line.split(",")[0][:4]
            if y.isdigit():
                by[y] += 1
    return sum(1 for y, n in by.items() if n >= 329 and int(y) < 2026)


def research_quality(row: dict, plan_ev: dict, lb_data: str, tva_pilot: bool) -> dict:
    """The research fleet scorer's per-lake classification (fleet_score.classify, overlay mode, strict columns), re-implemented so the plan does not
    import the research branch. Verified against fleet_score_v2.json tier T1 (see verify_t1)."""
    years = int(float(row["complete_years"] or 0))
    hist = row["history_class"]
    if tva_pilot:
        loc = {"Guntersville|AL": "GVDA1", "Wheeler|AL": "WHLA1", "Wilson|AL": "WLSA1", "Pickwick Lake|TN": "PICT1"}.get(row["lake_id"])
        pth = os.path.join(lb_data, "history", "tva_pilots", f"{loc}_daily.csv") if loc else ""
        if pth and os.path.exists(pth):   # the research counts the deep pilot composite (NWS RVDHUN + HADS + CWMS), 16-18 complete years
            by = collections.Counter(r["date"][:4] for r in csv.DictReader(open(pth)))
            years = sum(1 for y, n in by.items() if n >= 329 and int(y) < 2026)
            hist = "SUFFICIENT" if years >= 5 else "LIMITED"
    elif row["provider"] == "tva":
        years, hist = 4, "LIMITED"
    cy = composite_years(lb_data, row["lake_id"])
    if cy is not None and cy > years:
        years, hist = cy, ("SUFFICIENT" if cy >= 5 else ("LIMITED" if cy >= 2 else hist))
    e = plan_ev.get(row["lake_id"])
    plan = flood = False
    if e is not None:
        plan, flood = e.get("planStrict") == "True", e.get("floodStrict") == "True"
    return {"src": row["capability_class"] in ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE"), "plan": plan, "flood": flood,
            "hist": hist == "SUFFICIENT" and years >= 5, "base": hist in ("SUFFICIENT", "LIMITED")}


def table_quality(rec: dict) -> dict:
    p = rec.get("plan") or {}
    return {"src": rec["capability"] in ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE"), "plan": bool(p.get("planStrict")), "flood": bool(p.get("floodStrict")),
            "hist": rec["historyClass"] == "SUFFICIENT", "base": rec["historyClass"] in ("SUFFICIENT", "LIMITED")}


# ------------------------------------------------------------------------------------------------------------------------ rubric projection
def rubric_facts(directory: int, profiled: int, shares: dict, validation: str, health: str = "WARNING") -> dict:
    """Synthetic facts with exactly round(share * N) profiles satisfying each predicate (the method of research_score.py). obs = 1 (every bound
    lake publishes an observed level at probe time, R6)."""
    k = lambda s: round(shares.get(s, 0.0) * profiled)  # noqa: E731
    profiles, states = {}, {}
    for i in range(profiled):
        hist_ok, base_ok = i < k("hist"), i < max(k("base"), k("hist"))
        profiles[f"L{i}"] = {"sourceCapability": {"level": "DIRECT_OPERATOR_POOL" if i < k("src") else "PROXY"},
                             "operatingPools": {"guideCurve": {"available": i < k("plan")}},
                             "historicalCoverage": {"baselineStatus": "SUFFICIENT" if hist_ok else ("LIMITED" if base_ok else "INSUFFICIENT")}}
        states[f"L{i}"] = {"kind": "OBSERVED", "floodPoolState": "IN_CONSERVATION" if i < k("flood") else "UNKNOWN"}
    return {"registry": {"directoryLakeCount": directory, "health": health}, "validation": {"status": validation}, "health": {"status": health},
            "profiles": profiles, "states": states, "directoryLakeCount": directory}


def project(profiled_quality: list[dict], validation: str) -> dict:
    n = len(profiled_quality)
    sh = {k: (sum(1 for q in profiled_quality if q[k]) / n if n else 0.0) for k in ("src", "plan", "hist", "base", "flood")}
    sh["obs"] = 1.0
    s = score_lake(rubric_facts(DIRECTORY_TOTAL, n, sh, validation), NOW)
    return {"displayed": s["value"], "uncapped": s["uncapped"], "gates": [g["gate"] for g in s["scoreBlockers"] if g.get("gate")],
            "coveragePct": round(100 * n / DIRECTORY_TOTAL, 1), "coverageDim": s["scoreBreakdown"]["coverage"]["value"]}


# ------------------------------------------------------------------------------------------------------------------------ universe
def sha(p: str) -> str:
    return B.sha256(p)


def load_universe() -> dict:
    inp = B.Inputs()
    lb = B.DATA
    table = json.load(open(B.OUT))
    excl = json.load(open(B.OUT_EXCLUDED))
    rec = json.load(open(B.OUT_RECOVERED)) if os.path.exists(B.OUT_RECOVERED) else {"bindings": []}
    disp = json.load(open(B.DISPOSITIONS)) if os.path.exists(B.DISPOSITIONS) else {"lakes": {}}
    remaining = {x["lakeId"]: x for x in json.load(open(os.path.join(lb, "binding2", "remaining_unbound.json")))}
    unbound_prof = {x["lakeId"]: x for x in json.load(open(os.path.join(lb, "binding2", "unbound_profile.json")))}
    v2 = {r["lake_id"]: r for r in inp.v2}
    elig = {b["lakeId"]: b for b in table["bindings"]}
    ex = {x["lakeId"]: x for x in excl["excluded"]}
    recovered = {b["lakeId"]: b for b in rec["bindings"]}
    lakes = {}
    for lid, d in inp.directory.items():
        f = inp.features.get(lid, {})
        g = inp.geom.get(lid, {})
        regulated = bool(d.get("hasDam")) or d.get("poolBasis") == "fullPool"
        area = B.num(f.get("area_km2"))
        bs, bt = bow_score(area, d["state"], regulated, f.get("lake_class", ""))
        L = {"lakeId": lid, "state": d["state"], "operator": d.get("operatorName"), "areaKm2": area, "bowScore": bs, "bowTier": bt,
             "coordFlag": g.get("point_flag", ""), "coordConfidence": g.get("confidence", ""), "provider": None, "wave": None, "status": None}
        if lid in v2:
            r = v2[lid]
            L.update(provider=r["provider"], wave=r["wave"], status=r["binding_status"])
        if lid in elig:
            L.update(category="eligible", blockers=[], quality=table_quality(elig[lid]))
        elif lid in ex:
            codes = {x["code"] for x in ex[lid]["reasons"]}
            md = (disp["lakes"].get(lid) or {}).get("disposition")
            L.update(category="held", blockers=sorted(blockers_for(codes, v2[lid]["provider"], g.get("point_flag", ""), md)), reasonCodes=sorted(codes),
                     quality=research_quality(v2[lid], inp.plan, lb, lid in B.PILOTS))
        else:
            r = remaining.get(lid) or {}
            up = unbound_prof.get(lid) or {}
            cls = r.get("cls") or ""
            bl = {"nosource:known_source" if cls in ("source exists but not live/stale", "portal/PDF/login only") or str(up.get("reason", "")).startswith("pending")
                  else "nosource:failed_review" if cls == "live candidate failed review rules" else "nosource:no_data"}
            if g.get("point_flag", "") != "ok":
                bl.add({"off_water": "coord:off_water", "identity_risk": "coord:identity_risk"}.get(g.get("point_flag", ""), "coord:no_polygon"))
            L.update(category="unbound", blockers=sorted(bl), wave1Reason=up.get("reason"), cls=r.get("cls"), bestSource=r.get("bestSource"),
                     unboundStatus=r.get("status"), quality={"src": True, "plan": False, "flood": False, "hist": False, "base": False})
        lakes[lid] = L
    assert len(lakes) == DIRECTORY_TOTAL, len(lakes)
    # mismatch14: the 14 held lakes carry the disposition
    for lid, v in disp["lakes"].items():
        lakes[lid]["mismatch14"] = v["disposition"]
        if v["disposition"] == "FIXED" and lid in recovered:
            lakes[lid]["quality"] = table_quality(recovered[lid])
    inputs = {k: sha(p) for k, p in sorted(inp.files.items())}
    for p in (B.OUT, B.OUT_EXCLUDED, B.OUT_RECOVERED, B.DISPOSITIONS, os.path.join(lb, "binding2", "remaining_unbound.json"),
              os.path.join(lb, "binding2", "unbound_profile.json")):
        if os.path.exists(p):
            inputs[os.path.relpath(p, REPO) if p.startswith(REPO) else os.path.relpath(p, lb)] = sha(p)
    return {"lakes": lakes, "inputs": inputs}


def verify_t1(u: dict, inp_rows: list[dict] | None = None) -> dict:
    """Reproduce the research T1 shares (fleet_score_v2.json: 273 lakes, plan 0.44, flood 0.575, hist 0.934, base 0.989) from research_quality()."""
    inp = B.Inputs()
    rows = [r for r in inp.v2 if r["wave"] in B.STRICT_WAVES and r["binding_status"] in B.STRICT_STATUSES and "v1.1" not in r["checks_passed"]
            and r["provider"] not in {"nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake", "aep", "eccc", "mncsg"}]
    qs = [research_quality(r, inp.plan, B.DATA, r["lake_id"] in B.PILOTS) for r in rows]
    n = len(qs)
    return {"profiled": n, **{k: round(sum(1 for q in qs if q[k]) / n, 3) for k in ("plan", "flood", "hist", "base")}}


# ------------------------------------------------------------------------------------------------------------------------ counts
def category_counts(lakes: dict) -> dict:
    """Every lake exactly once, under (a) the generator's primary reason (as in excluded.json), (b) the brief's recovery taxonomy, (c) any blocker."""
    out = {"directory": len(lakes), "eligible": 0, "heldResearchBound": 0, "unbound": 0}
    prim = collections.Counter()
    tax = collections.Counter()
    anyb = collections.Counter()
    for L in lakes.values():
        out[{"eligible": "eligible", "held": "heldResearchBound", "unbound": "unbound"}[L["category"]]] += 1
        if L["category"] == "eligible":
            continue
        b = set(L["blockers"])
        for x in b:
            anyb[x] += 1
        # taxonomy primary (priority: mismatch > terms > adapter > coordinate > other evidence gap > no source)
        if any(x.startswith("mismatch") for x in b):
            t = "history/live mismatch"
        elif "terms:sjrwmd_nhdes" in b:
            t = "provider terms: sjrwmd / nhdes"
        elif "terms:undocumented" in b:
            t = "provider terms: undocumented operator endpoint"
        elif "adapter" in b:
            t = "provider not on allow-list / no adapter"
        elif any(x.startswith("coord:") for x in b) and L["category"] == "held":
            t = {"coord:identity_risk": "coordinate: identity risk", "coord:off_water": "coordinate: off water", "coord:no_polygon": "coordinate: no polygon"}[
                sorted(x for x in b if x.startswith("coord:"))[0]]
        elif b & {"posthoc", "flag", "stage"}:
            t = "other evidence gap (post-hoc v1.1/R7h, flagged, stage-only)"
        elif any(x.startswith("nosource") for x in b):
            t = "no source (unbound)"
        else:
            raise AssertionError(L["lakeId"])
        tax[t] += 1
    out["byTaxonomy"] = dict(sorted(tax.items()))
    out["byAnyBlocker"] = dict(sorted(anyb.items()))
    ex = json.load(open(B.OUT_EXCLUDED))
    out["generatorPrimaryReason"] = ex["byPrimaryReason"]
    # coordinate flags over the whole directory (brief: 43 identity-risk + 126 off-water)
    out["coordinateFlagsAllLakes"] = dict(collections.Counter(L["coordFlag"] or "no_polygon" for L in lakes.values()))
    cross = collections.defaultdict(collections.Counter)
    for L in lakes.values():
        cross[L["coordFlag"] or "no_polygon"][L["category"]] += 1
    out["coordinateFlagCrossTab"] = {k: dict(v) for k, v in sorted(cross.items())}
    by_prov = {}
    for tok in ("terms:sjrwmd_nhdes", "terms:undocumented", "adapter"):
        c, alone = collections.Counter(), collections.Counter()
        for L in lakes.values():
            if tok in L["blockers"]:
                c[L["provider"]] += 1
                if set(L["blockers"]) <= {tok}:
                    alone[L["provider"]] += 1
        srt = lambda x: dict(sorted(x.items(), key=lambda kv: (-kv[1], str(kv[0]))))   # noqa: E731
        by_prov[tok] = {"lakes": srt(c), "onlyThisBlocker": srt(alone)}
    out["providerGroups"] = by_prov
    out["unboundByResearchClass"] = dict(collections.Counter(L.get("cls") or "?" for L in lakes.values() if L["category"] == "unbound"))
    sig = collections.Counter(tuple(L["blockers"]) for L in lakes.values() if L["category"] != "eligible")
    out["blockerSignatures"] = [{"blockers": list(k), "lakes": v} for k, v in sorted(sig.items(), key=lambda kv: (-kv[1], kv[0]))]
    return out


# ------------------------------------------------------------------------------------------------------------------------ opportunities
# Each opportunity pulls ONE lever (or a named subset) and recovers the lakes whose remaining blockers are then empty. Judgement fields are explicit:
#   confidence H/M/L: H = binding-review-v1 evidence already VERIFIED and the blocker is not evidence; M = post-hoc / partly evidenced; L = evidence or permission absent
#   effort S/M/L: S = data/doc edit by the lead, M = script or adapter work, L = new provider adapter plus review plus an outside party
OPPORTUNITIES = [
    dict(id="R1", name="Mismatch-14 FIXED lakes (Task A)", pulls=["mismatch:FIXED"], confidence="H", effort="S", kind="HUMAN REVIEW",
         waiting="Michael reviews the 8 newly recovered MACHINE_VERIFIED candidates (bindings.proposed.v1.recovered.json); then remove them from held_lakes.SERIES_MISMATCH and regenerate with --include-recovered",
         why="strict binding-review-v1 rows; the hold was a hold-out QA artefact (or one wrong RISE item, Buffalo Bill); 3 years of date-matched agreement proven"),
    dict(id="R2", name="Mismatch-14 NEEDS-REVIEW lakes (Canyon, Detroit, Jackson, Rend, Taneycomo)", pulls=["mismatch:NEEDS HUMAN REVIEW"],
         confidence="M", effort="S", kind="HUMAN REVIEW / DECISION",
         waiting="Per lake: Canyon/Jackson - accept the A2W=CDA tsid identity (or log A2W for 20 days); Detroit - accept a day-key-aligned comparison (a new pre-registered criteria version); Taneycomo - supply the FERC P-2221 operating range; Rend - decide on the unexplained 0.55 ft series offset",
         why="every pre-registered criterion passes except one documented gap each"),
    dict(id="R3", name="Coordinate: off-water pins whose evidence is strict (only blocker)", pulls=["coord:off_water"], confidence="H", effort="M", kind="HUMAN REVIEW + GEOMETRY",
         waiting="Pin repair to the lake polygon (geometry/coordinates thread) and a Michael sign-off of the repaired coordinates; the binding evidence is unchanged",
         why="binding-review-v1 VERIFIED; a polygon exists for every off-water lake (confidence HIGH/MEDIUM for most)"),
    dict(id="R4", name="Coordinate: identity-risk lakes whose evidence is strict (only blocker)", pulls=["coord:identity_risk"], confidence="L", effort="M", kind="HUMAN REVIEW",
         waiting="Per-lake identity decision: is the directory pin the lake the gauge belongs to (name or namesake collision)? Michael's call, lake by lake",
         why="the directory point may be a different water body; a wrong match would put another lake's level on the wrong lake"),
    dict(id="R5", name="Coordinate: no polygon (22 lakes) whose evidence is strict (only blocker)", pulls=["coord:no_polygon"], confidence="M", effort="M", kind="EXTERNAL SOURCE",
         waiting="A polygon source (NHD/OSM/GSW) accepted by the geometry contract, then the usual pin repair",
         why="cannot be assessed until a polygon exists"),
    dict(id="R6", name="Provider terms: St. Johns River WMD and NH DES", pulls=["terms:sjrwmd_nhdes"], confidence="L", effort="M", kind="TERMS",
         waiting="Written confirmation of acceptable use of the SJRWMD / NH DES public endpoints (or a supported feed), then one adapter per provider",
         why="strict rows exist (3 + 1 in T1) but the endpoint terms are unreviewed; two adapters would unlock the group"),
    dict(id="R7", name="Provider terms: other undocumented operator endpoints (Duke, SRP, CNPPID, ...)", pulls=["terms:undocumented"], confidence="L", effort="L", kind="TERMS",
         waiting="Operator permission / terms per endpoint (Duke Energy Lake View is the largest: 8 lakes); one adapter per operator",
         why="each operator needs its own agreement and adapter; reuse is low except Duke"),
    dict(id="R8", name="Post-hoc v1.1 / R7h rows with no other blocker", pulls=["posthoc"], confidence="M", effort="S", kind="DECISION",
         waiting="Michael decides whether labelled binding-review-v1.1 / R7h promotions (rules written after wave-1 failures) may enter review as a separate, clearly labelled list",
         why="evidence exists but the rule was written after seeing failures; the R7h error rate was never measured"),
    dict(id="R9", name="New provider adapters on the post-hoc rows (CO-OPS, USGS-d, CDEC, USBR PN, NWRFC, CWMS-NWDP)", pulls=["adapter", "posthoc"], confidence="M", effort="L",
         kind="DECISION + CODE",
         waiting="The R8 decision AND a Swift adapter per provider (CO-OPS alone is 14 rows)",
         why="two blockers each: no adapter and post-hoc"),
    dict(id="R10", name="Flagged single-origin rows (drawdown / weak level class)", pulls=["flag", "posthoc"], confidence="L", effort="M", kind="EXTERNAL SOURCE",
         waiting="An independent second source per lake (corroboration) or a Michael waiver of the R7 'flag' class",
         why="the flag marks rows whose level class or drawdown could not be confirmed"),
    dict(id="R11", name="Stage-only lakes", pulls=["stage", "posthoc"], confidence="L", effort="L", kind="EXTERNAL SOURCE",
         waiting="A documented gauge datum (USGS site altitude / operator datum record) to turn stage into elevation; never a fitted offset",
         why="no absolute level to test"),
    dict(id="R12", name="Unbound lakes with a known but stale / portal-only / pending source", pulls=["nosource:known_source"], confidence="L", effort="M", kind="EXTERNAL SOURCE",
         waiting="Per lake: a live feed (stale), a machine-readable endpoint (portal/PDF/login only) or the pending corroboration / operator full-pool figure",
         why="the only unbound lakes with a named source at all"),
    dict(id="R13", name="Unbound lakes whose live candidate failed the review rules", pulls=["nosource:failed_review"], confidence="L", effort="L", kind="EXTERNAL SOURCE",
         waiting="Per lake: a different candidate series, or a decision on which failed rule is waivable (each failure was a real check: datum, freshness, identity, plausibility)",
         why="a candidate exists but did not pass R1-R8; padding these would be the poor matches the rule forbids"),
    dict(id="R14", name="Unbound lakes with no public level data found", pulls=["nosource:no_data"], confidence="L", effort="L", kind="EXTERNAL SOURCE",
         waiting="A new public data source or a state / local gauge; research logged per-lake dead ends (no gauge, discontinued, proxy only)",
         why="no candidate at all"),
]
CONF = {"H": 3, "M": 2, "L": 1}
EFF = {"S": 1, "M": 2, "L": 3}


def recoverable(L: dict, unlocked: set[str]) -> bool:
    b = set(L["blockers"])
    return L["category"] != "eligible" and bool(b) and b <= unlocked


def opportunity_sets(lakes: dict) -> dict[str, set[str]]:
    """Lakes each opportunity makes recoverable ON ITS OWN (all blockers within its `pulls`)."""
    return {o["id"]: {lid for lid, L in lakes.items() if recoverable(L, set(o["pulls"]))} for o in OPPORTUNITIES}


def rank(lakes: dict) -> list[dict]:
    sets = opportunity_sets(lakes)
    rows = []
    for o in OPPORTUNITIES:
        s = sets[o["id"]]
        tiers = collections.Counter(lakes[l]["bowTier"] for l in sorted(s))
        provs = collections.Counter((lakes[l]["provider"] or lakes[l]["operator"] or "?") for l in sorted(s))
        reuse = max(provs.values()) if provs else 0
        rows.append({**o, "lakes": len(s), "lakeIds": sorted(s), "bowA": tiers["A"], "bowB": tiers["B"], "bowC": tiers["C"], "bowScoreSum": sum(lakes[l]["bowScore"] for l in s),
                     "providers": dict(sorted(provs.items(), key=lambda kv: (-kv[1], kv[0]))), "reuse": reuse})
    # (1) confidence, (2) effort, (3) bowfishing value (tier-A lakes, proxy), (4) lakes recovered, (5) reuse (most lakes behind one provider/operator);
    # an opportunity that recovers no lake on its own is ranked after every one that does.
    rows.sort(key=lambda r: (r["lakes"] == 0, -CONF[r["confidence"]], EFF[r["effort"]], -r["bowA"], -r["lakes"], -r["reuse"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def shares_of(qs: list[dict]) -> dict:
    n = len(qs)
    return {k: round(sum(1 for q in qs if q[k]) / n, 3) if n else 0.0 for k in ("src", "plan", "hist", "base", "flood")}


def cumulative(lakes: dict, ranked: list[dict]) -> list[dict]:
    """Unlock the levers of each ranked opportunity in order; a lake counts once ALL its blockers are pulled (so a lake needing two opportunities
    lands in the later of the two)."""
    unlocked: set[str] = set()
    profiled = {lid for lid, L in lakes.items() if L["category"] == "eligible"}
    pilots = [lid for lid in B.PILOTS if lid in lakes]

    def step(name, ids, added, extra=None):
        qs = [lakes[l]["quality"] for l in ids]
        d = {"step": name, "added": added, "profiled": len(ids), "coveragePct": round(100 * len(ids) / DIRECTORY_TOTAL, 1), "shares": shares_of(qs),
             "projection": {v: project(qs, v) for v in ("NOT_VALIDATED", "PARTIAL", "VALIDATED")}}
        d.update(extra or {})
        return d

    steps = [step("T-1 today: the 5 reviewed pilot lakes", pilots, len(pilots))]
    steps.append(step("T0 all 196 eligible candidates reviewed", sorted(profiled), len(profiled)))
    for r in ranked:
        unlocked |= set(r["pulls"])
        new = {lid for lid, L in lakes.items() if lid not in profiled and recoverable(L, unlocked)}
        profiled |= new
        steps.append(step(f"+ {r['id']} {r['name']}", sorted(profiled), len(new), {"opportunity": r["id"], "addedIds": sorted(new)}))
    return steps


def build() -> dict:
    u = load_universe()
    lakes = u["lakes"]
    counts = category_counts(lakes)
    ranked = rank(lakes)
    steps = cumulative(lakes, ranked)
    return {"schema": "lake-brain-coverage-recovery-plan/v1", "runDate": "2026-10-13",
            "note": "PROJECTION ONLY: every score assumes the tranche passes human review; the displayed value is capped at 5.0 while validation is NOT_VALIDATED. "
                    "Rubric lake-brain-score-v1 is unmodified (sector_brain_platform.scoring.score_lake).",
            "inputs": u["inputs"], "t1Reproduction": verify_t1(u), "counts": counts,
            "opportunities": [{k: v for k, v in r.items() if k != "lakeIds"} | {"lakeIds": r["lakeIds"]} for r in ranked], "cumulative": steps}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if a.check:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print("coverage plan up to date" if ok else "coverage plan differs from a fresh build")
        return 0 if ok else 1
    open(OUT, "w").write(text)
    c = doc["counts"]
    print(json.dumps({k: c[k] for k in ("directory", "eligible", "heldResearchBound", "unbound")}), json.dumps(c["byTaxonomy"], indent=0))
    print("T1 reproduction:", doc["t1Reproduction"])
    for r in doc["opportunities"]:
        print(f"#{r['rank']:2} {r['id']:4} conf {r['confidence']} eff {r['effort']} lakes {r['lakes']:3} A {r['bowA']:2} B {r['bowB']:2} reuse {r['reuse']:3}  {r['name']}")
    for s in doc["cumulative"]:
        p = s["projection"]
        print(f"{s['profiled']:4} (+{s['added']:3}) {s['step'][:70]:70} NV {p['NOT_VALIDATED']['displayed']}/{p['NOT_VALIDATED']['uncapped']}  PARTIAL {p['PARTIAL']['displayed']}  VALIDATED {p['VALIDATED']['displayed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
