#!/usr/bin/env python3
"""Consolidated binding review packet (individual acceptance, no extrapolation).

ONE packet, two sections:

  Section A  "easy / high confidence": up to 64 rows from the generated bindings table (jobs/lake-brain/data/bindings.proposed.v1.json), chosen by the
             FIXED rule below. 5 REVIEWED pilots + 58 individually accepted lakes = 63 profiled lakes = the next coverage threshold (10 % of 621).
  Section B  "flagged / ambiguous - later, optional": <= 20 rows (recovered mismatch-14 lakes, wave-1 flagged lakes, coordinate-held lakes), clearly
             marked 'do after Section A'. A Section B ACCEPT only counts when the lake is already in the bindings table; the other rows are recorded as
             'accepted for later table inclusion' and never reach accepted_batch.json.

Nothing here accepts anything. Acceptance state is WAITING FOR MICHAEL. The packet is public-derived data only.

SELECTION RULE (selection-rule id consolidated-selection-v1; fixed before any lake was looked at - the thresholds below are the only knobs and
they are changed here, in code review, never after seeing which lakes pass):

  Universe: the 196 rows of the bindings table.
    1  not one of the 5 REVIEWED pilots (the packet never contains a pilot)
    2  not in a hold list (held_lakes.py snapshot, held_back_coordinate_flags.csv, any hold file given)
    3  the existing pack recommendation is PASS and every rule R1..R9 is PASS or n-a
    4  spatial match: the lake has an outline and the gauge is within THRESH.max_dist_m (150 m, the 'at the outline' tolerance of rule_results) of it
    5  live registry: geometry confidence HIGH and point flag 'ok'
    6  not in the coordinate-review pack (coordinate_review_pack.csv) and not in held_back_coordinate_flags.csv
    7  independent confirmation: an independent second source whose latest level differs <= THRESH.second_diff_ft (1.0 ft), OR an operator-published full
       pool (directory basis fullPool, confidence high, operator known) that the latest level AND the 30-day median match within THRESH.pool_tol_ft (3.0 ft)
    8  lake-name vs station-name similarity >= THRESH.name_sim (0.7; 'all lake-name words appear in the station name' counts as 0.7, as in recommend())
    9  history: >= THRESH.hist_years (15) complete years from a repeatable public series (historyBasis base / history_extension, no 'not a repeatable' note)
   10  latest observation age <= THRESH.obs_age_h (48 h)
   11  no attention warning (every recNotes entry except the two purely informational ones, 'single agency only' and 'all lake-name words appear')
   12  no datum ambiguity: R8 PASS, R7 'strong', zero datum offset on every live source, no history merge/composite caveat
  Lakes of the existing 60-row stratified sample are allowed, but non-sample qualifying rows are taken first; the sample rows used are reported.

  Size: target 64. If >= 64 qualify: take 64. If 60..63 qualify: take all of them and report the shortfall (never padded with weak rows). If fewer
  than 60 qualify: relax ONE criterion at a time, CUMULATIVELY, in the pre-stated order RELAX_ORDER until >= 60 qualify, and report exactly what was
  relaxed and how many rows pass only because of the relaxation.

  Ranking inside the qualifying set (RANK_WEIGHTS, 100 points): provider identity 20, coordinate confidence 15, operator confidence 15, geometry
  confidence 10, duplicate-lake ambiguity 10 (lower ambiguity is better), datum/reference ambiguity 10, independent confirmation 10, production
  usefulness 10 (the bowfishing size/region proxy of coverage_recovery_plan.json). Diversity: greedy selection with a penalty per lake already
  chosen from the same provider, state, source kind and region (DIVERSITY_PENALTY); ties broken by sha256(seed|lake id), so the result is deterministic.

SECTION B RULE: SECTION_B_QUOTA rows per source, ordered by the bowfishing proxy (highest first), then lake id: the recovered mismatch-14 lakes
(bindings.proposed.v1.recovered.json), the mismatch-14 lakes still marked NEEDS HUMAN REVIEW, coordinate-held lakes whose live registry says geometry
HIGH and point 'ok' (the hold may be stale: decide the coordinate pack first), then wave-1 flagged lakes whose recommendation is PASS-near-pool. Only
providers the runner supports (a2w, cwms, usgs, rise, tva, nwps). Spare quota flows to the next source. Section B rows are never in the Section A funnel.
"""
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_review_pack as BRP  # noqa: E402
import consolidated_common as CC  # noqa: E402
import held_lakes  # noqa: E402

SELECTION_RULE_ID = "consolidated-selection-v1"
SEED = 20261014
TARGET_A = 64
MIN_A = 60
MAX_B = 20
SECTION_B_QUOTA = (("recovered", 8), ("mismatch", 5), ("held", 2), ("flagged", 5))      # spare quota flows to the next source
THRESH = dict(max_dist_m=150.0, second_diff_ft=1.0, pool_tol_ft=3.0, name_sim=0.7, hist_years=15, obs_age_h=48.0)
# One criterion at a time, cumulative, only if fewer than MIN_A rows qualify under THRESH.
RELAX_ORDER = (
    ("obs_age_h", {"obs_age_h": 72.0}, "latest observation age 48 h -> 72 h (the R6 live rule's own limit)"),
    ("hist_years", {"hist_years": 10}, "history 15 -> 10 complete years"),
    ("independent_tolerance", {"second_diff_ft": 2.0, "pool_tol_ft": 5.0}, "second-source difference 1 -> 2 ft (the R9 rule) and operator-pool tolerance 3 -> 5 ft"),
    ("name_sim", {"name_sim": 0.6}, "name similarity 0.7 -> 0.6"),
)
INFO_NOTE_PREFIXES = ("single agency only", "the station name contains every word of the lake name")
RANK_WEIGHTS = dict(identity=20, coordinate=15, operator=15, geometry=10, duplicate=10, datum=10, independent=10, usefulness=10)
DIVERSITY_PENALTY = dict(provider=2.0, state=1.5, kind=1.0, region=1.0)
HISTORY_BASES_OK = ("base", "history_extension")
SUPPORTED_PROVIDERS = ("a2w", "cwms", "usgs", "rise", "tva", "nwps")

DEFAULT_REGISTRY = "https://storage.googleapis.com/sector-lake-registry/registry/lakes.v1.json"
HANDOFFS = "/Users/mcather/Desktop/Sector Handoffs/Sector Engine"
DEFAULT_SAMPLE_CSV = f"{HANDOFFS}/Lake Brain Binding Review/binding_review_sample.csv"
DEFAULT_HELD_CSV = f"{HANDOFFS}/Lake Brain Binding Review/held_back_coordinate_flags.csv"
DEFAULT_COORD_PACK = f"{HANDOFFS}/Lake Brain Coordinate Review/coordinate_review_pack.csv"
DEFAULT_OUT = f"{HANDOFFS}/Lake Brain Binding Review Consolidated"
DEFAULT_RECOVERED = os.path.join(CC.DATA_DIR, "bindings.proposed.v1.recovered.json")
DEFAULT_DISPOSITIONS = os.path.normpath(os.path.join(HERE, "..", "bindings", "mismatch14_dispositions.json"))


# ---------------------------------------------------------------------------------------------------------------- context
class Ctx:
    """Everything the selection needs besides the row itself. All plain dicts/sets, so tests build it by hand."""

    def __init__(self, table, pilots, held, coord_pack, sample, registry, bow, dir_names=None):
        self.table = table                  # lakeId -> binding (bindings.proposed.v1.json)
        self.pilots, self.held, self.coord_pack, self.sample = set(pilots), set(held), set(coord_pack), set(sample)
        self.registry = registry            # lakeId -> registry lake record
        self.bow = bow                      # lakeId -> bowfishing proxy score (0..9)
        self.dir_names = dir_names or {}    # normalised lake name -> number of directory lakes carrying it
        self.station_use = collections.Counter((b["provider"], str(b["station"])) for b in table.values())


def norm_name(n):
    return " ".join(BRP.name_tokens(n)) or (n or "").lower()


def load_json_or_url(path_or_url):
    if os.path.exists(path_or_url):
        with open(path_or_url, "rb") as f:
            raw = f.read()
    else:
        req = urllib.request.Request(path_or_url, headers={"User-Agent": "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def read_ids(csv_path, col="lake_id"):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return {r[col] for r in csv.DictReader(f)}


# ---------------------------------------------------------------------------------------------------------------- criteria
def effective_sim(row):
    sim = row["nameMatch"]["sim"]
    if sim < 0.7 and BRP.name_contained(row["nameMatch"]["lake"], row["nameMatch"]["station"]):
        sim = 0.7
    return sim


def attention_warnings(row):
    return [n for n in row["recNotes"] if not n.startswith(INFO_NOTE_PREFIXES)]


def independent_basis(row, thr):
    """('second' | 'pool' | 'second+pool' | None, detail)."""
    s = row["second"]
    sec = s is not None and s.get("diff") is not None and s["diff"] <= thr["second_diff_ft"]
    p = row["pool"]
    pool = (p.get("basis") == "fullPool" and p.get("conf") == "high" and (row.get("operator") or "none") not in ("none", "")
            and p.get("diffNow") is not None and p.get("diff") is not None
            and abs(p["diffNow"]) <= thr["pool_tol_ft"] and abs(p["diff"]) <= thr["pool_tol_ft"])
    kind = "second+pool" if sec and pool else "second" if sec else "pool" if pool else None
    return kind


def datum_ambiguity(row, binding):
    reasons = []
    res = {r["id"]: r["res"] for r in row["rules"]}
    if res.get("R8") != "PASS":
        reasons.append("R8 not PASS")
    if row["r7class"] != "strong":
        reasons.append(f"R7 is '{row['r7class']}'")
    if any(float(l.get("datumOffsetFt") or 0.0) != 0.0 for l in binding.get("live", [])):
        reasons.append("non-zero datum offset")
    if binding.get("historyNotes"):
        reasons.append("history merge/composite caveat")
    return reasons


def history_ok(binding, thr):
    return (int(binding.get("historyCompleteYears") or 0) >= thr["hist_years"] and binding.get("historyBasis") in HISTORY_BASES_OK
            and not any("not a repeatable" in n for n in binding.get("historyNotes", [])))


def evaluate(row, ctx, thr=THRESH):
    """Ordered [(criterion, passed)] for one row. The order is the funnel order; the first False is where the row leaves the funnel."""
    lid = row["id"]
    b = ctx.table[lid]
    reg = ctx.registry.get(lid) or {}
    gc = (reg.get("geometryConfidence") or {}).get("level")
    out = []
    out.append(("not_pilot", lid not in ctx.pilots))
    out.append(("not_held", lid not in ctx.held))
    out.append(("recommendation_pass_rules_clear", row["rec"] == "PASS" and all(r["res"] in ("PASS", "n-a") for r in row["rules"])))
    out.append(("spatial_match", bool(row["dist"]["outline"]) and row["dist"]["m"] <= thr["max_dist_m"]))
    out.append(("registry_geometry_high_point_ok", gc == "HIGH" and reg.get("pointFlag") == "ok"))
    out.append(("not_in_coordinate_review", lid not in ctx.coord_pack))
    out.append(("independent_confirmation", independent_basis(row, thr) is not None))
    out.append(("name_similarity", effective_sim(row) >= thr["name_sim"]))
    out.append(("history", history_ok(b, thr)))
    out.append(("observation_age", row["level"]["ageH"] is not None and row["level"]["ageH"] <= thr["obs_age_h"]))
    out.append(("no_attention_warning", not attention_warnings(row)))
    out.append(("no_datum_ambiguity", not datum_ambiguity(row, b)))
    return out


CRITERIA_ORDER = ("not_pilot", "not_held", "recommendation_pass_rules_clear", "spatial_match", "registry_geometry_high_point_ok", "not_in_coordinate_review",
                  "independent_confirmation", "name_similarity", "history", "observation_age", "no_attention_warning", "no_datum_ambiguity")


def funnel(rows, ctx, thr=THRESH):
    """Exact counts: start, each criterion applied cumulatively in order, the same criterion applied alone, and the qualifying ids."""
    ev = {lid: dict(evaluate(r, ctx, thr)) for lid, r in rows.items()}
    steps, alive = [], set(rows)
    for c in CRITERIA_ORDER:
        before = len(alive)
        alive = {l for l in alive if ev[l][c]}
        steps.append(dict(criterion=c, remaining=len(alive), removed=before - len(alive), failedAlone=sum(1 for l in rows if not ev[l][c])))
    # rows that fail EXACTLY ONE criterion (what a single further relaxation would add; information for the lead, never applied here)
    only = collections.defaultdict(list)
    for l in rows:
        bad = [c for c in CRITERIA_ORDER if not ev[l][c]]
        if len(bad) == 1:
            only[bad[0]].append(l)
    return dict(start=len(rows), steps=steps, qualifying=sorted(alive), thresholds=dict(thr),
                blockedOnlyBy={c: sorted(v) for c, v in sorted(only.items())})


def qualify(rows, ctx):
    """Apply THRESH, then (only if fewer than MIN_A qualify) RELAX_ORDER one criterion at a time. Returns (qualifying ids, funnel of the final
    thresholds, relaxation report)."""
    thr = dict(THRESH)
    f = funnel(rows, ctx, thr)
    relax = dict(applied=[], strictQualifying=len(f["qualifying"]), strictIds=list(f["qualifying"]), strictSteps=[[x["criterion"], x["remaining"]] for x in f["steps"]],
                 strictBlockedOnlyBy={c: len(v) for c, v in f["blockedOnlyBy"].items()})
    for name, change, text in RELAX_ORDER:
        if len(f["qualifying"]) >= MIN_A:
            break
        thr.update(change)
        f = funnel(rows, ctx, thr)
        relax["applied"].append(dict(criterion=name, change=change, text=text, qualifyingAfter=len(f["qualifying"])))
    relax["relaxedOnlyIds"] = sorted(set(f["qualifying"]) - set(relax["strictIds"]))
    return f["qualifying"], f, relax


# ---------------------------------------------------------------------------------------------------------------- ranking / selection
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def rank_components(row, ctx, thr=THRESH):
    lid = row["id"]
    b = ctx.table[lid]
    reg = ctx.registry.get(lid) or {}
    W = RANK_WEIGHTS
    nid = row.get("nid") or {}
    identity = W["identity"] * (0.6 * clamp(effective_sim(row)) + 0.2 * (1.0 if nid.get("linked") and (nid.get("score") or 0) >= 90 else 0.0)
                                + 0.2 * (0.0 if BRP.RIVERISH.search(row.get("stationName") or "") else 1.0))
    coord = W["coordinate"] * (0.55 * (1.0 - clamp(row["dist"]["m"] / thr["max_dist_m"])) + 0.45 * clamp(float((reg.get("geometryConfidence") or {}).get("score") or 0)))
    pool = row["pool"]
    operator = W["operator"] * (0.5 * (1.0 if row["capability"] == "DIRECT_OPERATOR_POOL" else 0.0) + 0.3 * (1.0 if pool.get("conf") == "high" else 0.0)
                                + 0.2 * (0.0 if (row.get("operator") or "none") in ("none", "") else 1.0))
    geometry = W["geometry"] * clamp(float((reg.get("geometryConfidence") or {}).get("score") or 0))
    same_name = max(0, ctx.dir_names.get(norm_name(row["name"]), 1) - 1)
    members = max(0, len(reg.get("memberIds") or [lid]) - 1)
    shared_station = max(0, ctx.station_use[(b["provider"], str(b["station"]))] - 1)
    duplicate = W["duplicate"] * clamp(1.0 - 0.5 * min(1, same_name) - 0.3 * min(1, members) - 0.2 * min(1, shared_station))
    datum = W["datum"] * clamp(1.0 - 0.34 * len(datum_ambiguity(row, b)))
    kind = independent_basis(row, thr)
    sd = row["second"]["diff"] if row["second"] and row["second"].get("diff") is not None else None
    ind = W["independent"] * (1.0 if kind == "second+pool" else (0.6 + 0.4 * (1.0 - clamp((sd or 0.0) / max(thr["second_diff_ft"], 1e-9)))) if kind == "second" else 0.5 if kind == "pool" else 0.0)
    use = W["usefulness"] * clamp(float(ctx.bow.get(lid, 0)) / 9.0)
    comp = dict(identity=identity, coordinate=coord, operator=operator, geometry=geometry, duplicate=duplicate, datum=datum, independent=ind, usefulness=use)
    return {k: round(v, 3) for k, v in comp.items()}


def region_of(ctx, lid):
    return ((ctx.table[lid].get("context") or {}).get("region") or {}).get("value") or "?"


def tiebreak(seed, lid):
    return hashlib.sha256(f"{seed}|{lid}".encode()).hexdigest()


def pick_diverse(candidates, rows, ctx, n, seed, forced=(), thr=THRESH):
    """Greedy: highest (rank score - diversity penalty) first; deterministic. `forced` ids are taken first (and count toward diversity)."""
    comp = {l: rank_components(rows[l], ctx, thr) for l in candidates}
    base = {l: sum(c.values()) for l, c in comp.items()}
    chosen = []
    cnt = {k: collections.Counter() for k in DIVERSITY_PENALTY}

    def take(l):
        chosen.append(l)
        cnt["provider"][rows[l]["provider"]] += 1
        cnt["state"][rows[l]["state"]] += 1
        cnt["kind"][rows[l]["capability"]] += 1
        cnt["region"][region_of(ctx, l)] += 1

    for l in forced:
        take(l)
    rest = [l for l in candidates if l not in set(chosen)]
    while rest and len(chosen) < n:
        def val(l):
            pen = (DIVERSITY_PENALTY["provider"] * cnt["provider"][rows[l]["provider"]] + DIVERSITY_PENALTY["state"] * cnt["state"][rows[l]["state"]]
                   + DIVERSITY_PENALTY["kind"] * cnt["kind"][rows[l]["capability"]] + DIVERSITY_PENALTY["region"] * cnt["region"][region_of(ctx, l)])
            return (-(base[l] - pen), tiebreak(seed, l))
        best = min(rest, key=val)
        take(best)
        rest.remove(best)
    return chosen, comp


def select_section_a(rows, ctx, seed=SEED, target=TARGET_A):
    ids, f, relax = qualify(rows, ctx)
    non_sample = [l for l in ids if l not in ctx.sample]
    in_sample = [l for l in ids if l in ctx.sample]
    thr = dict(THRESH)
    for a in relax["applied"]:
        thr.update(a["change"])
    # non-sample rows first (all of them are forced in when fewer than `target`), then the best sample rows fill the remainder
    if len(non_sample) >= target:
        chosen, comp = pick_diverse(non_sample, rows, ctx, target, seed, thr=thr)
    else:
        chosen, comp = pick_diverse(ids, rows, ctx, target, seed, forced=non_sample, thr=thr)
    chosen = chosen[:target]
    sample_used = [l for l in chosen if l in ctx.sample]
    report = dict(qualifying=len(ids), qualifyingNonSample=len(non_sample), qualifyingSample=len(in_sample), target=target, selected=len(chosen),
                  shortfall=max(0, target - len(chosen)), sampleRowsUsed=len(sample_used), sampleRowIds=sorted(sample_used), relaxation=relax,
                  funnel=f, rankComponents={l: comp[l] for l in chosen}, rankScore={l: round(sum(comp[l].values()), 3) for l in chosen})
    return chosen, report


# ---------------------------------------------------------------------------------------------------------------- section B
def select_section_b(cands, ctx, quota=SECTION_B_QUOTA, cap=MAX_B):
    """cands: {'recovered': {id: row}, 'flagged': {id: row}, 'held': {id: row}}. Returns [(source, id)]."""
    order = {s: sorted(cands.get(s, {}), key=lambda l: (-ctx.bow.get(l, 0), l)) for s, _ in quota}
    picked, spare = [], 0
    for s, q in quota:
        take = order[s][: q + spare]
        spare = q + spare - len(take)
        picked += [(s, l) for l in take]
    return picked[:cap]


# ---------------------------------------------------------------------------------------------------------------- display rows
def clip(text, n):
    """Cut at a word boundary with an ellipsis (never mid-word, never silently)."""
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(",;:") + " ..."


def plain_provider(p):
    return BRP.PROVIDER_PLAIN.get(p, p)


def section_row(row, section, seq, ctx, extra=None):
    """The slim card: only what Michael needs. `extra` carries section-B fields (why flagged, binding implication, source group)."""
    lid = row["id"]
    reg = ctx.registry.get(lid) or {}
    gc = reg.get("geometryConfidence") or {}
    third_w = attention_warnings(row)
    inb = lid in ctx.table
    res = {r["id"]: r["res"] for r in row["rules"]}
    d = dict(
        id=lid, section=section, seq=seq, name=row["name"], state=row["state"], provider=row["provider"], providerPlain=plain_provider(row["provider"]),
        operator=row.get("operator"), kindPlain=row.get("capPlain"), identifier=row["sourceId"], station=row["station"], series=row["series"],
        stationName=row["stationName"], links=row["links"],
        lake=dict(lat=row["lake"]["lat"], lon=row["lake"]["lon"], map=row["lake"]["map"]), gauge=dict(lat=row["gauge"]["lat"], lon=row["gauge"]["lon"], map=row["gauge"]["map"]),
        spatial=dict(text=row["dist"]["text"], m=row["dist"]["m"], outline=row["dist"]["outline"]),
        nameMatch=row["nameMatch"], nameSimEffective=round(effective_sim(row), 3),
        geometry=dict(level=gc.get("level"), score=gc.get("score"), pointFlag=reg.get("pointFlag"), areaKm2=reg.get("areaKm2"),
                      text=(f"outline confidence {gc.get('level')}, map point '{reg.get('pointFlag')}'" if gc else "not in the live registry")),
        warnings=third_w + ([] if row["pointFlag"] in ("none", "ok") else [f"directory coordinate flagged '{row['pointFlag']}'"]),
        level=row["level"], pool=row["pool"], second=row["second"], alsoAgrees=row["alsoAgrees"],
        history=row["history"], recommendation=row["rec"], recReasons=row["recReasons"], recNotes=row["recNotes"],
        rulesSummary=" ".join(f"{k}:{res[k]}" for k in sorted(res)), rules=row["rules"], inBindingsTable=inb, bowScore=ctx.bow.get(lid),
    )
    if inb:
        d["independentBasis"] = independent_basis(row, THRESH)
    if extra:
        d.update(extra)
    core = dict(id=lid, section=section, name=d["name"], state=d["state"], provider=d["provider"], identifier=d["identifier"], station=d["station"],
                series=d["series"], recommendation=d["recommendation"])
    d["digest"] = CC.row_digest(core)
    return d


def overlay_recovered(row, binding, inp):
    """The recovered binding may replace the series the research row carries (Buffalo Bill: RISE 152 -> 146). Show the RECOVERED source."""
    if (row["provider"], str(row["station"])) == (binding["provider"], str(binding["station"])):
        return row, None
    live = binding["live"][0]
    pr = binding["verification"]["probe"]
    r = json.loads(json.dumps(row))
    r["station"], r["series"] = str(binding["station"]), str(binding["series"])
    r["sourceId"] = f"{binding['provider']}: {binding['station']}"
    m = re.search(r"item \d+ \(([^)]*)\)", live.get("note") or "")
    r["stationName"] = m.group(1) if m else f"{binding['provider']} {binding['station']}"
    r["sourceLabel"] = f"{plain_provider(binding['provider'])} - {r['stationName']}"
    r["links"] = BRP.source_links(inp, binding["provider"], str(binding["station"]), str(binding["series"]), "")
    r["level"] = dict(lastFt=pr["lastFt"], medFt=pr["medianFt"], obsUtc=pr["lastObservationAt"], ageH=pr.get("ageHours"), snapshot=BRP.SNAPSHOT_DATE)
    fp = binding["verification"].get("directoryFullPoolFt")
    r["pool"] = dict(r["pool"], ft=fp, diff=binding["verification"]["deltaFullPoolFt"], diffNow=round(pr["lastFt"] - fp, 3) if fp is not None else None)
    r["history"] = dict(r["history"], years=binding["historyCompleteYears"], cls=binding["historyClass"])
    r["second"], r["alsoAgrees"] = None, []
    return r, f"replaces research source {row['sourceId']}: {live.get('note')}"


# ---------------------------------------------------------------------------------------------------------------- html / csv
PACKET_CSV_FIELDS = ["section", "seq", "lake_id", "lake_name", "state", "provider", "provider_identifier", "operator", "station_name", "spatial_match",
                     "distance_to_outline_km", "name_similarity", "geometry_status", "warnings", "current_level_ft", "observed_at_utc", "observation_age_hours",
                     "full_pool_ft", "level_minus_full_pool_ft", "second_source", "second_source_level_ft", "second_source_difference_ft", "history_years",
                     "computer_recommendation", "recommendation_reason", "why_flagged", "counts_if_accepted", "gauge_page", "lake_map_link", "gauge_map_link", "row_digest"]


def packet_csv_row(r):
    s = r.get("second")
    return {
        "section": r["section"], "seq": r["seq"], "lake_id": r["id"], "lake_name": r["name"], "state": r["state"], "provider": r["provider"],
        "provider_identifier": r["identifier"], "operator": r.get("operator") or "", "station_name": r["stationName"], "spatial_match": r["spatial"]["text"],
        "distance_to_outline_km": round(r["spatial"]["m"] / 1000.0, 3), "name_similarity": f"{r['nameMatch']['sim']:.3f}", "geometry_status": r["geometry"]["text"],
        "warnings": " | ".join(r["warnings"]), "current_level_ft": r["level"]["lastFt"], "observed_at_utc": r["level"]["obsUtc"], "observation_age_hours": r["level"]["ageH"],
        "full_pool_ft": r["pool"]["ft"], "level_minus_full_pool_ft": r["pool"]["diffNow"],
        "second_source": f"{s['label']} ({s['name']})" if s else "none (single agency)", "second_source_level_ft": s["lastFt"] if s else "",
        "second_source_difference_ft": round(s["diff"], 3) if s and s.get("diff") is not None else "", "history_years": r["history"]["years"],
        "computer_recommendation": r["recommendation"], "recommendation_reason": " | ".join(r["recReasons"]), "why_flagged": r.get("whyFlagged", ""),
        "counts_if_accepted": r.get("countsIfAccepted", ""), "gauge_page": (r["links"][0]["u"] if r["links"] else ""),
        "lake_map_link": (r["lake"]["map"] or {}).get("u", ""), "gauge_map_link": (r["gauge"]["map"] or {}).get("u", ""), "row_digest": r["digest"],
    }


def render_html(template_path, pack_id, rows, meta):
    tpl = open(template_path, encoding="utf-8").read()
    payload = dict(packId=pack_id, rows=rows, meta=meta)
    return tpl.replace("__PACK_ID__", pack_id).replace("__DATA_JSON__", BRP.json_for_html(payload))


# ---------------------------------------------------------------------------------------------------------------- build
def build(inp, ctx, rows_all, out_dir, registry_sha, seed=SEED, extra_inputs=None, recovered=None, dispositions=None, flagged_rows=None, held_rows=None,
          template=None, write=True, held_kind=None):
    """rows_all: {lakeId: build_row(...)} for every table lake. flagged_rows / held_rows: {lakeId: build_row(...)} for Section B candidates;
    recovered: the recovered-bindings document. held_kind: {lakeId: 'coordinate' | 'series' | 'terms'} (why a held lake is held). Returns (manifest, a_rows, b_rows)."""
    held_kind = held_kind or {}
    chosen, rep = select_section_a(rows_all, ctx, seed)
    # presentation order: provider, state, name
    chosen = sorted(chosen, key=lambda l: (rows_all[l]["provider"], rows_all[l]["state"], rows_all[l]["name"], l))
    a_rows = []
    for i, l in enumerate(chosen, 1):
        r = rows_all[l]
        ib = independent_basis(r, THRESH)
        why = {"second": "an independent second source agrees", "pool": "the operator-published full pool matches the level", "second+pool": "an independent second source AND the operator-published full pool agree"}.get(ib, "")
        extra = dict(whyEasy=why, countsIfAccepted="yes, once accepted (in the bindings table)", rankScore=rep["rankScore"][l], inSample=l in ctx.sample)
        a_rows.append(section_row(r, CC.SECTION_A, i, ctx, extra))
    # section B
    cands = {"recovered": {}, "mismatch": {}, "flagged": {}, "held": {}}
    why_b = {}
    rec_docs = {b["lakeId"]: b for b in (recovered or {}).get("bindings", [])}
    for lid, b in rec_docs.items():
        if lid in (held_rows or {}):
            row, note = overlay_recovered(held_rows[lid], b, inp)
            cands["recovered"][lid] = row
            disp = ((dispositions or {}).get("lakes") or {}).get(lid) or {}
            why_b[lid] = ("Recovered mismatch-14 lake: the history series had differed from the live binding by more than 15 ft (a hold-out QA hold). Disposition FIXED: "
                          + f"{(disp.get('overlap') or {}).get('matchedDays', 'n/a')} days of date-matched agreement. "
                          + (clip(note, 300) + ". " if note else "") + "It is NOT in the bindings table yet.")
    for lid, row in (held_rows or {}).items():
        disp = ((dispositions or {}).get("lakes") or {}).get(lid) or {}
        if lid in rec_docs or held_kind.get(lid) not in ("series", "multiple") or disp.get("disposition") != "NEEDS HUMAN REVIEW" or row["provider"] not in SUPPORTED_PROVIDERS:
            continue
        cands["mismatch"][lid] = row
        why_b[lid] = ("Mismatch-14 lake that still needs a human: " + clip(disp.get("reason") or "history series differs from the live binding by more than 15 ft", 600) + " It is NOT in the bindings table.")
    for lid, row in (flagged_rows or {}).items():
        if row["rec"] == "PASS" and row["provider"] in SUPPORTED_PROVIDERS:
            cands["flagged"][lid] = row
            ph = row.get("postHoc") or {}
            why_b[lid] = ("Wave-1 FLAGGED lake (the level is far from the directory full pool or the full-pool figure is uncertain and one agency backs it). "
                          + (row["recReasons"][0] + ". " if row.get("recReasons") else "") + f"Later research status: {ph.get('outcome', 'n/a')} (post-hoc, not counted). It is NOT in the bindings table.")
    for lid, row in (held_rows or {}).items():
        if lid in rec_docs or held_kind.get(lid) != "coordinate" or row["provider"] not in SUPPORTED_PROVIDERS:
            continue
        reg = ctx.registry.get(lid) or {}
        if (reg.get("geometryConfidence") or {}).get("level") == "HIGH" and reg.get("pointFlag") == "ok":
            cands["held"][lid] = row
            why_b[lid] = ("Held lake: its directory coordinate was flagged in research, but the live registry now shows geometry HIGH and map point 'ok'; the coordinate hold may be stale. "
                          "Decide the coordinate-review pack first. It is NOT in the bindings table.")
    picked = select_section_b(cands, ctx)
    b_rows = []
    for i, (src, lid) in enumerate(picked, 1):
        r = cands[src][lid]
        counts = ("yes (already in the bindings table)" if lid in ctx.table else "no: recorded as 'accepted for later table inclusion' only; it does not count toward 63 and never reaches accepted_batch.json")
        extra = dict(sourceGroup=src, whyFlagged=why_b[lid], countsIfAccepted=counts, doAfterA=True)
        b_rows.append(section_row(r, CC.SECTION_B, i, ctx, extra))
    all_rows = a_rows + b_rows
    pack_id = CC.pack_id_for(all_rows, seed)
    meta = dict(sectionA=len(a_rows), sectionB=len(b_rows), pilots=CC.PILOT_COUNT, threshold=CC.COVERAGE_THRESHOLD, neededAccepts=CC.NEEDED_ACCEPTS,
                snapshot=BRP.SNAPSHOT_DATE, criteria=CC.CRITERIA_VERSION, selectionRule=SELECTION_RULE_ID)
    prov_counts = collections.Counter(r["provider"] for r in a_rows)
    manifest = dict(
        schema=CC.SCHEMA_PACK, packId=pack_id, generatedBy="jobs/lake-brain/review/build_consolidated_pack.py", selectionRule=SELECTION_RULE_ID, seed=seed,
        snapshotDate=BRP.SNAPSHOT_DATE, criteriaVersion=CC.CRITERIA_VERSION, status="WAITING FOR MICHAEL (nothing in this packet is accepted)",
        decisions=list(CC.DECISIONS), pilots=sorted(ctx.pilots), pilotCount=CC.PILOT_COUNT, threshold=CC.COVERAGE_THRESHOLD, neededAccepts=CC.NEEDED_ACCEPTS,
        thresholds=THRESH, relaxOrder=[dict(criterion=n, change=c, text=t) for n, c, t in RELAX_ORDER], rankWeights=RANK_WEIGHTS, diversityPenalty=DIVERSITY_PENALTY,
        sectionBQuota=[list(q) for q in SECTION_B_QUOTA],
        counts=dict(tableLakes=len(ctx.table), sectionA=len(a_rows), sectionB=len(b_rows), sampleRowsUsed=rep["sampleRowsUsed"], shortfall=rep["shortfall"],
                    qualifying=rep["qualifying"], qualifyingNonSample=rep["qualifyingNonSample"], qualifyingSample=rep["qualifyingSample"],
                    sectionAByProvider=dict(sorted(prov_counts.items())), sectionAByState=dict(sorted(collections.Counter(r["state"] for r in a_rows).items())),
                    sectionAByKind=dict(sorted(collections.Counter(r["kindPlain"] for r in a_rows).items())),
                    sectionBBySource=dict(sorted(collections.Counter(r["sourceGroup"] for r in b_rows).items()))),
        funnel=rep["funnel"], relaxation=rep["relaxation"], sampleRowIds=rep["sampleRowIds"],
        held=sorted(ctx.held), coordinatePack=sorted(ctx.coord_pack),
        inputs=dict(bindingsTableSha256=CC.sha256_file(CC.BINDINGS) if os.path.exists(CC.BINDINGS) else None, registrySha256=registry_sha, **(extra_inputs or {})),
        rows=[dict(section=r["section"], id=r["id"], seq=r["seq"], digest=r["digest"], name=r["name"], state=r["state"], provider=r["provider"],
                   identifier=r["identifier"], recommendation=r["recommendation"], inBindingsTable=r["inBindingsTable"],
                   **({"rankScore": r.get("rankScore")} if r["section"] == "A" else {"sourceGroup": r.get("sourceGroup")})) for r in all_rows],
        rankComponents=rep["rankComponents"],
        note="Acceptance is individual: only a lake Michael marks ACCEPT can ever count. Nothing is extrapolated to lakes he did not decide.",
    )
    if write:
        os.makedirs(out_dir, exist_ok=True)
        tpl = template or os.path.join(HERE, "consolidated_template.html")
        with open(os.path.join(out_dir, "binding_review_consolidated.html"), "w", encoding="utf-8") as f:
            f.write(render_html(tpl, pack_id, all_rows, meta))
        with open(os.path.join(out_dir, "binding_review_consolidated.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=PACKET_CSV_FIELDS)
            w.writeheader()
            for r in all_rows:
                w.writerow(packet_csv_row(r))
        with open(os.path.join(out_dir, "pack_manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1)
        write_readme(out_dir, manifest, a_rows, b_rows)
    return manifest, a_rows, b_rows


def write_readme(out, m, a_rows, b_rows):
    c, fn = m["counts"], m["funnel"]
    L = []
    A = L.append
    A("# START HERE - Lake Brain binding review (consolidated packet)")
    A("")
    A("**Status: WAITING FOR MICHAEL.** Nothing in this packet is accepted. No lake becomes REVIEWED until you press ACCEPT on it and the export has been ingested.")
    A("")
    A("## What this is")
    A(f"The computer matched lakes to public water-level gauges. Today **{m['pilotCount']}** lakes are REVIEWED. The next coverage step needs **{m['threshold']}** profiled lakes, "
      f"so **{m['neededAccepts']}** more lakes have to be accepted. Section A has **{c['sectionA']}** lakes the computer is most sure about"
      + (f", so you can reach {m['threshold']} even if you say no to a few." if c['sectionA'] >= m['neededAccepts'] + 6 else " (see the note on size below)."))
    A("")
    A("**Every ACCEPT is you personally accepting that one lake. Nothing is extrapolated: a lake you did not accept does not count, and no lake is accepted because other lakes were.**")
    if c["shortfall"] > 0:
        A("")
        A(f"**Honest note on size.** Only **{c['sectionA']}** lakes meet every hard criterion (target {TARGET_A}; shortfall {c['shortfall']}), and nothing weaker was added to make up the number. "
          f"Section A alone can therefore reach at most {m['pilotCount']} + {c['sectionA']} = {m['pilotCount'] + c['sectionA']} profiled lakes, short of {m['threshold']}. "
          "The rest has to come from Path A below, from a later and wider packet (the manifest lists, per criterion, how many lakes miss only that one criterion), or from the Section B lakes once they are in the bindings table.")
    A("")
    A("## How long")
    A(f"About 20 to 30 minutes for Section A if you trust the computer's evidence on each card and open the gauge link only when something looks odd (about 20 seconds a card). "
      f"Plan an hour if you open every gauge page. Section B ({c['sectionB']} rows) is optional and later: do it after Section A.")
    A("")
    A("## What to do")
    A("1. Double-click `binding_review_consolidated.html` (opens in Safari or Chrome; nothing is uploaded).")
    A("2. Work down **Section A**. Each card shows the lake, the gauge, where the gauge sits against the lake outline, the name match, the current level against the lake's full pool, the independent second source (when there is one), any warning, and the computer's recommendation.")
    A("3. Press **Accept** (this gauge is this lake's water level), **Reject** (wrong gauge, wrong lake or a nonsense level) or **Needs review** (you cannot tell; it is set aside and not counted). Add a note if you like. Press the same button again to undo.")
    A("4. The header counts `Section A: accepted N of {n}` and `N more needed to reach 63 profiled lakes`. Your answers are saved in your browser as you go (same browser, same file).".replace("{n}", str(c["sectionA"])))
    A("5. Press **Download my review (CSV)**. Give that file to Claude. A partial export is fine: only the lakes you accepted count; run it again later with the rest.")
    A("6. **Section B** is a separate short list of flagged or ambiguous lakes (each card says why). Do it after Section A, or not at all.")
    A("")
    A("## What happens next")
    A("Claude runs `jobs/lake-brain/review/ingest_batch_review.py` on your export. First a dry run: it checks the export against `pack_manifest.json` (right packet, every row present once, only ACCEPT / REJECT / NEEDS REVIEW, nothing edited), and prints the accepted lakes and `profiled lakes would be 5 + N = M (threshold 63)`. "
      "With your go-ahead it writes the per-packet result and the cumulative `accepted_batch.json` (every individually accepted lake, sorted, nothing ever removed) plus `binding_review_result.json` with their sha256 fingerprints. "
      "That file set is what the history pre-seed accepts. The lakes still need the usual deployment steps (nothing is deployed by this packet). Rejected and Needs-review lakes are recorded and excluded.")
    A("")
    A("## Two ways to get lakes accepted - you choose")
    A("- **Path A: the 60-row random sample** (`Lake Brain Binding Review/binding_review_sample.html`, ~1 hour). If at most 1 of the 60 is rejected, the whole eligible population (every strict, unheld lake in the bindings table) is accepted at once through the statistical rule. It is the fastest way to a large number of lakes, but you are accepting lakes you never opened on the strength of the sample, and a second reject sends whole groups to full review.")
    A("- **Path B: this packet** (individual). Each accepted lake counts only because you personally accepted it, so nothing rests on extrapolation, but it only grows by the lakes you open. These are chosen to be the easiest ones, so it is also fast per lake.")
    A("The two do not conflict: the cumulative list is the union of both (a lake you reject here is never accepted through the sample). Section A rows overlap the 60-row sample only where noted in the manifest.")
    A("")
    A("## Section A: how the lakes were chosen (fixed before looking)")
    A("From the 196 generated bindings, all of these must hold: not one of the 5 reviewed pilots; not on a hold list; the computer's recommendation PASS with every rule R1 to R9 PASS or n/a; the gauge within 150 m of the lake outline; "
      "the live lake registry says outline confidence HIGH and map point 'ok'; the lake is not in the coordinate-review pack; an independent second source agrees within 1 ft **or** the dam operator's published full pool matches the level (latest and 30-day median) within 3 ft; "
      "lake and station names clearly similar (0.7 or more); at least 15 complete years of history from a repeatable public series; last observation within 48 h; no warning; no datum ambiguity. "
      "From the lakes that pass, the ones to show are picked by a fixed score (identity, coordinate, operator, geometry, duplicate-lake ambiguity, datum, independent confirmation, bowfishing usefulness proxy) with a penalty for repeating a provider, state, source kind or region, so the list is spread across the fleet.")
    A("")
    rx = m["relaxation"]
    strict = dict(rx["strictSteps"])
    A("| Step (cumulative, in this order) | Lakes left, strict criteria | Lakes left, after the relaxations below |")
    A("|---|---|---|")
    A(f"| Bindings table | {fn['start']} | {fn['start']} |")
    for st in fn["steps"]:
        A(f"| after: {st['criterion'].replace('_', ' ')} | {strict[st['criterion']]} | {st['remaining']} |")
    A("")
    A(f"**Criteria relaxed: {'none' if not rx['applied'] else '; '.join(a['text'] + ' (qualifying ' + str(a['qualifyingAfter']) + ')' for a in rx['applied'])}.** Strictly, {rx['strictQualifying']} lakes qualify; {len(rx['relaxedOnlyIds'])} more qualify only because of the relaxations (cumulative, one criterion at a time, in the order shown, only because fewer than {MIN_A} qualified strictly). Qualifying lakes: {c['qualifying']} ({c['qualifyingNonSample']} outside the 60-row sample, {c['qualifyingSample']} inside it). "
      f"Shown in Section A: **{c['sectionA']}** (target {TARGET_A}; shortfall {c['shortfall']}; {c['sampleRowsUsed']} of them are rows of the 60-row sample).")
    A("")
    A("| Provider | Section A lakes |")
    A("|---|---|")
    for p, n in c["sectionAByProvider"].items():
        A(f"| {plain_provider(p)} (`{p}`) | {n} |")
    A("")
    A("## Files in this folder")
    A("| File | What it is |")
    A("|---|---|")
    A("| `binding_review_consolidated.html` | The review form (double-click) |")
    A("| `binding_review_consolidated.csv` | The same rows as a spreadsheet (read-only copy; return the HTML's export, not this) |")
    A("| `pack_manifest.json` | Packet id, selection rule, funnel counts, row fingerprints, input hashes. The ingest checks your export against it |")
    A("")
    A("## Limits")
    A("- Levels are a snapshot from 2026-10-13; the links go to live pages, so numbers differ slightly.")
    A("- Nothing is marked REVIEWED by this packet. Public information only; no logins or keys.")
    A("- A lake in Section B that is not in the bindings table cannot be counted even if accepted: it is recorded as 'accepted for later table inclusion'.")
    with open(os.path.join(out, "START HERE - README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------------------------------------------------------- CLI
def load_bow(repo_root):
    spec = importlib.util.spec_from_file_location("coverage_recovery_plan", os.path.join(repo_root, "jobs", "lake-brain", "bindings", "coverage_recovery_plan.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    u = m.load_universe()["lakes"]
    return {l: v["bowScore"] for l, v in u.items()}, u


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--research-docs", default=BRP.DEFAULT_RESEARCH_DOCS)
    ap.add_argument("--data-dir", default=BRP.DEFAULT_DATA)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--registry", default=DEFAULT_REGISTRY, help="URL or local JSON of the live lake registry")
    ap.add_argument("--sample-csv", default=DEFAULT_SAMPLE_CSV)
    ap.add_argument("--held-csv", default=DEFAULT_HELD_CSV)
    ap.add_argument("--coordinate-pack", default=DEFAULT_COORD_PACK)
    ap.add_argument("--bindings", default=CC.BINDINGS)
    ap.add_argument("--recovered", default=DEFAULT_RECOVERED)
    ap.add_argument("--dispositions", default=DEFAULT_DISPOSITIONS)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--dry-run", action="store_true", help="print the funnel and the chosen rows, write nothing")
    args = ap.parse_args(argv)

    repo = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    inp = BRP.Inputs(args.research_docs, args.data_dir)
    tdoc = json.load(open(args.bindings))
    table = {b["lakeId"]: b for b in tdoc["bindings"]}
    pilots = {p["lakeId"] for p in tdoc["pilotReproduction"]}
    assert len(pilots) == CC.PILOT_COUNT, pilots
    reg_doc, reg_sha = load_json_or_url(args.registry)
    registry = {x["lakeId"]: x for x in reg_doc["lakes"]}
    held = held_lakes.load_snapshot() | read_ids(args.held_csv)
    coord = read_ids(args.coordinate_pack)
    sample = read_ids(args.sample_csv)
    bow, universe = load_bow(repo)
    names = collections.Counter(norm_name(d["name"]) for d in inp.directory.values())
    ctx = Ctx(table, pilots, held, coord, sample, registry, bow, names)
    rows_all = {l: BRP.build_row(inp, dict(lake_id=l), "sample", i) for i, l in enumerate(sorted(table), 1)}
    recovered = json.load(open(args.recovered)) if os.path.exists(args.recovered) else {"bindings": []}
    dispositions = json.load(open(args.dispositions)) if os.path.exists(args.dispositions) else {"lakes": {}}
    flagged_ids = sorted(l for l, r in inp.w1.items() if r["bindingStatus"] == "VERIFIED_FLAG")
    flagged_rows = {l: BRP.build_row(inp, dict(lake_id=l), "flagged", 0) for l in flagged_ids}
    held_strict = {}
    eligible, heldc, excl, hs, ht = BRP.select_strict(inp)
    for rec in heldc + hs + ht:
        l = rec["v2"]["lake_id"]
        if l not in held_strict:
            held_strict[l] = BRP.build_row(inp, rec["v2"], "sample", 0)
    held_kind = {}
    for kind, recs in (("terms", ht), ("series", hs), ("coordinate", heldc)):    # later kinds win; a lake held for several reasons is not 'coordinate only'
        for rec in recs:
            held_kind[rec["v2"]["lake_id"]] = kind if rec["v2"]["lake_id"] not in held_kind else "multiple"
    ctx.held |= set(held_strict)
    extra_inputs = dict(sampleCsvSha256=CC.sha256_file(args.sample_csv), heldCsvSha256=CC.sha256_file(args.held_csv), coordinatePackSha256=CC.sha256_file(args.coordinate_pack),
                        recoveredSha256=CC.sha256_file(args.recovered) if os.path.exists(args.recovered) else None, researchInputSha256=inp.hashes())
    manifest, a_rows, b_rows = build(inp, ctx, rows_all, args.out, reg_sha, args.seed, extra_inputs, recovered, dispositions, flagged_rows, held_strict, write=not args.dry_run, held_kind=held_kind)
    print(json.dumps(dict(packId=manifest["packId"], counts=manifest["counts"], relaxation=[a["text"] for a in manifest["relaxation"]["applied"]],
                          funnel=[(s["criterion"], s["remaining"]) for s in manifest["funnel"]["steps"]]), indent=1))
    return manifest


if __name__ == "__main__":
    main()
