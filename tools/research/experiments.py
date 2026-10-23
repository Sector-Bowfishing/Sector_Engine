#!/usr/bin/env python3
"""Research avenues beyond plain downloading: candidate-rule experiments, alternate-source connectors, dataset search and cross-Brain tests.
Registered in EXPERIMENTS and scheduled by the coordinator from discovery.json `avenues` (campaign.py stage_followup + ledger.py).

Every experiment follows the same contract:
  acquire(ev, home, spec, it, targets, gaps) -> dict   downloads (allowlisted, with provenance) or {} for analysis-only avenues
  analyze(home, spec, mine, allacq, upstream) -> {metrics, findings, weak, limitations, [owner]}   OFFLINE and deterministic: re-run by the
      validate stage from the hashed evidence; a result that does not reproduce is rejected
Findings declare the tier they claim (ledger.TIERS); the validator re-computes the evidence and enforces the tier's requirements. A
candidate change that does not beat its baseline on data NOT used to build it is rejected - and kept as a rejected hypothesis.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import gzip
import io
import json
import math
import os
import re
import statistics as S

import discovery as D

SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA"}
RUNGS = {"season": lambda r: r["season"], "region_season": lambda r: f"{r['region']}|{r['season']}", "class_season": lambda r: f"{r['cls']}|{r['season']}"}


def season_of(month: int) -> str:
    return SEASON.get(month, "SON")


def rmse(v):
    return math.sqrt(sum(x * x for x in v) / len(v)) if v else float("nan")


# ------------------------------------------------------------------------------------------------------------------------------- Water Temp
def _resid(home: str, rel: str) -> list[dict]:
    rows = []
    with gzip.open(os.path.join(home, rel), "rt") as fh:
        for r in csv.DictReader(fh):
            if not r.get("m0") or not r.get("e"):
                continue
            rows.append({"stem": D.safe_key(r["lake"].replace("|", "_").replace("/", "-").replace(" ", "_")), "year": int(r["year"]), "season": r["season"],
                         "region": r["region"], "cls": r["cls"], "e": float(r["e"])})
    return rows


def _fit(rows, keyf, min_cell, shrink):
    g: dict = {}
    for r in rows:
        g.setdefault(keyf(r), []).append(r["e"])
    return {k: S.median(v) * len(v) / (len(v) + shrink) for k, v in g.items() if len(v) >= min_cell}


def _sensor_errors(home: str, cfg: dict, allacq: list[dict]) -> dict:
    """{lake key: {'errs': [(date, M0 - sensor)], 'site': ..}} from the primary connector's evidence (best site per lake)."""
    per = {}
    for a in allacq:
        for key, m in (a.get("matched") or {}).items():
            if "sites" in m:
                per[key] = {**m, "sites": per[key]["sites"] + m["sites"]} if key in per else m
    out = {}
    for key in sorted(per):
        m = per[key]
        forc = D.m0_daily(json.load(open(os.path.join(home, m["forcing"]), encoding="utf-8"))["daily"])
        best = None
        for s in m["sites"]:
            series, _ = D.dv_series(os.path.join(home, s["path"]))
            errs = [(d, v0 - obs) for d, obs in sorted(series.items()) if (v0 := D.m0_for_date(forc, d)) is not None]
            if len(errs) >= cfg.get("minDays", 60) and (best is None or len(errs) > len(best["errs"])):
                best = {"errs": errs, "site": s["site"], "paths": [s["path"], m["forcing"]]}
        if best:
            out[key] = best
    return out


def acquire_none(ev, home, spec, it, targets, gaps):
    return {}


def analyze_wt_bias(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Hypothesis: production M0 has a systematic, correctable bias that depends on `rung` (season / region x season / class x season).
    Build: median residual per cell from fleet grab samples up to `trainThroughYear`. Test (neither used to build it):
      T1 temporal holdout: fleet grab samples after trainThroughYear
      T2 leave-lake-out: independent USGS continuous sensors, offsets fitted WITHOUT that lake
    Pre-declared pass rule (discovery.json): T1 RMSE gain >= holdoutMinDelta, T2 pooled gain >= sensorMinDelta, no more than maxWorseShare of
    the sensor lakes worse by > worseTol, bias not larger. Otherwise the hypothesis is rejected and preserved with its numbers."""
    rung = spec["rung"]
    keyf = RUNGS[rung]
    rows = _resid(home, spec["storedResiduals"])
    train = [r for r in rows if r["year"] <= spec["trainThroughYear"]]
    test = [r for r in rows if r["year"] > spec["trainThroughYear"]]
    off = _fit(train, keyf, spec["minCell"], spec["shrink"])
    base = [r["e"] for r in test]
    cand = [r["e"] - off.get(keyf(r), 0.0) for r in test]
    m = {"rung": rung, "cells": len(off), "holdoutN": len(test), "holdoutRmseBase": round(rmse(base), 4), "holdoutRmseCand": round(rmse(cand), 4),
         "holdoutDeltaRmse": round(rmse(base) - rmse(cand), 4), "holdoutBiasBase": round(S.mean(base), 4), "holdoutBiasCand": round(S.mean(cand), 4),
         "holdoutBiasReduction": round(abs(S.mean(base)) - abs(S.mean(cand)), 4)}
    sensors = _sensor_errors(home, spec, allacq)
    meta = {}
    for r in rows:
        meta.setdefault(r["stem"], (r["region"], r["cls"]))
    lakes, used_paths = {}, set([spec["storedResiduals"]])
    for key, se in sorted(sensors.items()):
        stem = D.safe_key(key)
        if stem not in meta:
            continue                                             # lake not in the fleet residual table: no region/class, cannot be tested
        reg, cls = meta[stem]
        loo = _fit([r for r in rows if r["stem"] != stem], keyf, spec["minCell"], spec["shrink"])
        b, c = [], []
        for d, e in se["errs"]:
            k = keyf({"season": season_of(int(d[5:7])), "region": reg, "cls": cls})
            b.append(e)
            c.append(e - loo.get(k, 0.0))
        lakes[key] = {"n": len(b), "rmseBase": round(rmse(b), 4), "rmseCand": round(rmse(c), 4), "biasBase": round(S.mean(b), 4), "biasCand": round(S.mean(c), 4)}
        used_paths |= set(se["paths"])
    m["sensorLakes"] = len(lakes)
    if lakes:
        pb = math.sqrt(sum(v["rmseBase"] ** 2 for v in lakes.values()) / len(lakes))
        pc = math.sqrt(sum(v["rmseCand"] ** 2 for v in lakes.values()) / len(lakes))
        m.update({"sensorRmseBase": round(pb, 4), "sensorRmseCand": round(pc, 4), "sensorDeltaRmse": round(pb - pc, 4),
                  "lakesWorseShare": round(sum(v["rmseCand"] > v["rmseBase"] + spec["worseTol"] for v in lakes.values()) / len(lakes), 4), "lakes": lakes})
    offs = {k: round(v, 3) for k, v in sorted(off.items())}
    m["offsets"] = offs
    se_cells = {k: v for k, v in offs.items() if k.startswith("Southeast|")}
    m["southeastSeasonOffsetsC"] = se_cells or ({k: v for k, v in offs.items() if "|" not in k} if rung == "season" else {})
    ident = spec["avenueId"]
    g = f"discovery.exp.{ident}"
    tests = [{"metric": f"{g}.holdoutDeltaRmse", "op": ">=", "threshold": spec["holdoutMinDelta"]},
             {"metric": f"{g}.sensorDeltaRmse", "op": ">=", "threshold": spec["sensorMinDelta"]},
             {"metric": f"{g}.lakesWorseShare", "op": "<=", "threshold": spec["maxWorseShare"]},
             {"metric": f"{g}.sensorLakes", "op": ">=", "threshold": spec["minSensorLakes"]},
             {"metric": f"{g}.holdoutBiasReduction", "op": ">=", "threshold": 0.0}]
    change = {"scientificChange": f"Add a {rung.replace('_', ' x ')} additive correction to the fallback/forecast water-temperature model (production M0).",
              "previous": "M0 uses no bias correction (WaterTemperatureService.swift, k=0.09 relaxation toward an energy-balance equilibrium).",
              "proposed": {"correction": "M0' = M0 - offset[cell]", "cell": rung, "offsetsC": offs, "fit": f"median fleet residual per cell, years <= {spec['trainThroughYear']}, shrink {spec['shrink']}, min {spec['minCell']} samples"},
              "evidenceSummary": f"{len(train)} fleet grab-sample residuals for fitting; {len(test)} later ones held out; {len(lakes)} USGS continuous-sensor lakes excluded from the fit one at a time.",
              "validationMethod": "T1 temporal holdout on fleet grab samples; T2 leave-lake-out on independent USGS continuous sensors. Thresholds pre-declared in discovery.json.",
              "validationResults": {k: m.get(k) for k in ("holdoutRmseBase", "holdoutRmseCand", "holdoutDeltaRmse", "sensorRmseBase", "sensorRmseCand", "sensorDeltaRmse", "lakesWorseShare")},
              "practicalEffect": "Spring (MAM) water temperatures run cold and autumn (SON) warm in the production model; the correction moves predicted temperatures toward observed ones, which shifts every temperature-gated species rule (spawn windows, cold-water inactivity) by the same amount.",
              "scoreImpact": "None under water-temp-level-ladder-v1: the frozen score is gate-based (Level-4 protected truth) and is not moved by a lower RMSE. Reported as a measured capability gain only.",
              "limitations": "Offsets are fleet-level medians; grab samples are daytime single-depth values compared with a daily-mean model; deployment needs a Swift change and approval; the protected Stage 3C.3 lakes (incl. Guntersville) were not used."}
    cap = {"kind": "prediction", "name": "production M0 water-temperature RMSE (C)", "direction": "lower_better", "baselineMetric": f"{g}.sensorRmseBase",
           "candidateMetric": f"{g}.sensorRmseCand", "minDelta": spec["sensorMinDelta"], "nMetric": f"{g}.sensorLakes", "minN": spec["minSensorLakes"], "tests": tests}
    f = D.finding(f"WT-BIAS-{rung}", f"A {rung.replace('_', ' x ')} correction reduces production M0 error on data not used to build it.", "PARAMETER", sorted(used_paths), home,
                  "offline refit + temporal holdout + leave-lake-out sensor test", f"{g}.holdoutDeltaRmse", ">=", spec["holdoutMinDelta"],
                  tier="INDEPENDENTLY_VALIDATED", change=change, capability=cap)
    return {"metrics": m, "findings": [f], "weak": [], "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- Fish
def analyze_fish_rules(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Grade the support behind every species rule the Fish Brain would show at the pilot lake. No species is VALIDATED (FISH-VAL-001: no rule
    has been compared with a field outcome); the grade separates what may be shown as EXPERIMENTAL from what must ABSTAIN."""
    base = os.path.join(home, spec["bundle"])
    lake = json.load(open(os.path.join(base, "lakes", spec["lake"] + ".json"), encoding="utf-8"))
    pres = {s["speciesId"]: s.get("presenceState") for s in lake.get("species") or []}
    paths = [os.path.join(spec["bundle"], "lakes", spec["lake"] + ".json")]
    per, abstain, experimental = {}, [], []
    for sid in sorted(pres):
        p = os.path.join(base, "rules", sid + ".json")
        if not os.path.exists(p):
            per[sid] = {"presence": pres[sid], "rules": 0, "directRead": 0, "pilotClass": "ABSTAIN", "why": "no rules in the bundle"}
            abstain.append(sid)
            continue
        paths.append(os.path.join(spec["bundle"], "rules", sid + ".json"))
        rules = json.load(open(p, encoding="utf-8"))["rules"]
        direct = sum(1 for r in rules for e in r.get("evidence") or [] if e.get("counts") and e.get("directness") == "DIRECT" and e.get("readStatus") == "READ-FULL")
        better = sum(1 for r in rules if r.get("confidence") in ("MEDIUM", "HIGH") and r.get("status") == "RECONCILED")
        se = sorted({(r.get("transferability") or {}).get("southeastReservoir", "UNKNOWN") for r in rules})
        present = pres[sid] in ("established", "reported")
        cls = "EXPERIMENTAL_INTERNAL" if (present and direct >= spec["minDirectEvidence"] and better >= 1) else "ABSTAIN"
        why = [] if cls != "ABSTAIN" else (["presence not established or reported at the pilot lake"] if not present else []) + \
            ([f"fewer than {spec['minDirectEvidence']} direct, fully read evidence items"] if direct < spec["minDirectEvidence"] else []) + \
            (["no reconciled MEDIUM/HIGH-confidence rule"] if better < 1 else [])
        per[sid] = {"presence": pres[sid], "rules": len(rules), "directRead": direct, "reconciledMedHigh": better, "southeastReservoirTransfer": se, "pilotClass": cls, "why": why}
        (experimental if cls != "ABSTAIN" else abstain).append(sid)
    m = {"speciesAtPilot": len(per), "experimentalInternal": len(experimental), "abstain": len(abstain), "validatedForField": 0, "perSpecies": per}
    g = f"discovery.exp.{spec['avenueId']}"
    change = {"scientificChange": "Replace 'every species rule is shown' with an evidence-graded refusal boundary for the pilot lake.",
              "previous": "All bundle rules for species recorded at the lake are eligible for display; per-rule confidence labels only.",
              "proposed": {"experimentalInternal": experimental, "abstain": abstain, "criteria": {k: spec[k] for k in ("minDirectEvidence",)},
                           "validatedForField": []},
              "evidenceSummary": f"{sum(v['rules'] for v in per.values())} rules across {len(per)} species graded from their recorded evidence entries.",
              "validationMethod": "deterministic grading of the rule metadata (evidence directness, read status, confidence, status, transferability); reproducible offline",
              "validationResults": {k: m[k] for k in ("speciesAtPilot", "experimentalInternal", "abstain", "validatedForField")},
              "practicalEffect": "A bowfisher is never shown a response band or spawn window for a species whose rules rest on indirect, unread or non-reconciled evidence; the app says 'not enough evidence' instead.",
              "scoreImpact": "None: the Biological-state score is not a field-validation measure; FISH-VAL-001 stays open.",
              "limitations": "This grades the strength of the written evidence, not field accuracy. It validates nothing against catch or observation outcomes."}
    f = D.finding("FISH-RULE-GRADE", "Species rules at the pilot lake can be graded by evidence strength into experimental vs abstain.", "RULE", paths, home,
                  "evidence-strength grading of rule metadata", f"{g}.speciesAtPilot", ">=", 1, tier="CANDIDATE_CHANGE", change=change)
    owner = [{"id": "fish-field-outcomes", "gap": "FISH-VAL-001", "publisher": "state fisheries agency (e.g. Alabama Division of Wildlife and Freshwater Fisheries) and TVA reservoir fish programs; "
              "bowfishing tournament organisers",
              "dataset": "dated catch/observation records with species, water temperature and location (creel surveys, electrofishing with spawning condition, tournament weigh-in logs)",
              "access": "request from the agency or organiser; owner action (no public bulk download verified)", "verified": False,
              "addresses": "FISH-VAL-001 (no species rule compared with a field outcome) - the only way to move any species from EXPERIMENTAL to field-validated"}]
    return {"metrics": m, "findings": [f], "weak": [], "limitations": [{"limitation": "no field outcomes: no species is validated for field use", "kind": "external", "gap": "FISH-VAL-001"}], "owner": owner}


# ------------------------------------------------------------------------------------------------------------------------------- dataset search
def _search_urls(q: str, n: int):
    return [("dryad", "https://datadryad.org/api/v2/search", {"q": q, "per_page": n}),
            ("zenodo", "https://zenodo.org/api/records", {"q": q, "size": n, "type": "dataset"}),
            ("sciencebase", "https://www.sciencebase.gov/catalog/items", {"q": q, "format": "json", "max": n, "fields": "title,summary,webLinks,files,link"})]


def acquire_dataset_search(ev, home, spec, it, targets, gaps):
    got = {}
    for q in spec["params"]["queries"]:
        for src, base, params in _search_urls(q, spec["params"].get("perSource", 8)):
            got[f"{src}:{q}"] = ev.fetch("dataset-search", f"{src}_{D.safe_key(q)[:40]}.json", base, params, purpose=f"dataset leads for: {q}")
    return {"queries": spec["params"]["queries"], "files": got}


def _lead_rows(path: str, src: str) -> list[dict]:
    d = json.load(open(path, encoding="utf-8"))
    out = []
    if src == "zenodo":
        for h in (d.get("hits") or {}).get("hits") or []:
            md = h.get("metadata") or {}
            out.append({"title": md.get("title"), "url": h.get("doi_url") or (h.get("links") or {}).get("self_html"), "license": (md.get("license") or {}).get("id"),
                        "files": [{"name": f.get("key"), "bytes": f.get("size")} for f in h.get("files") or []][:10], "text": md.get("description", "")[:600]})
    elif src == "dryad":
        for h in (d.get("_embedded") or {}).get("stash:datasets") or []:
            out.append({"title": h.get("title"), "url": h.get("sharingLink") or h.get("identifier"), "license": "CC0 (Dryad)", "files": [], "text": (h.get("abstract") or "")[:600]})
    else:
        for h in d.get("items") or []:
            out.append({"title": h.get("title"), "url": (h.get("link") or {}).get("url"), "license": "US Government public domain", "files": [{"name": f.get("name"), "bytes": f.get("size")} for f in h.get("files") or []][:10],
                        "text": (h.get("summary") or "")[:600]})
    return out


def analyze_dataset_search(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    terms = [t.lower() for t in spec["params"]["relevance"]]
    leads, paths = {}, []
    for a in mine:
        for k, rel in (a.get("files") or {}).items():
            if not rel:
                continue
            src = k.split(":")[0]
            paths.append(rel)
            for r in _lead_rows(os.path.join(home, rel), src):
                text = f"{r['title']} {r['text']}".lower()
                score = sum(t in text for t in terms)
                if r["url"] and score >= spec["params"]["minTerms"]:
                    leads[r["url"]] = {**r, "source": src, "relevance": score}
    ranked = sorted(leads.values(), key=lambda x: (-x["relevance"], x["url"]))[:15]
    m = {"leads": len(ranked), "top": [{k: x[k] for k in ("title", "url", "source", "license", "relevance")} for x in ranked[:10]]}
    g = f"discovery.exp.{spec['avenueId']}"
    f = D.finding(f"{spec['avenueId'].upper()}-LEADS", f"{len(ranked)} public datasets match the gap terms; each needs a reviewed adapter or agent analysis before it can support any rule.", "DATASET",
                  sorted(set(paths)), home, "repository search (Dryad, Zenodo, ScienceBase) + term relevance screen", f"{g}.leads", ">=", spec["params"].get("minLeads", 1), tier="EVIDENCE_LEAD") if paths else None
    return {"metrics": m, "findings": [f] if f else [], "weak": [] if ranked else ["no-dataset-leads"], "limitations": [],
            "agentTasks": [{"task": f"read and, if usable, analyse: {x['title']} ({x['url']})", "licence": x["license"]} for x in ranked[:5]]}


# ------------------------------------------------------------------------------------------------------------------------------- Lake (CWMS)
CWMS = "https://cwms-data.usace.army.mil/cwms-data/"
ACC = "application/json;version=2"


def _like(name: str) -> str:
    toks = [t for t in re.split(r"[^A-Za-z]+", name) if len(t) >= 4 and t.lower() not in D.STOP]
    return ".*" + ".*".join(t.title() for t in toks) + ".*Elev.*Inst.*" if toks else ""


def acquire_lake_cwms(ev, home, spec, it, targets, gaps):
    cfg = spec["params"]
    lakes = [l for l in D.fleet(home, cfg) if targets is None or l["key"] in set(targets)]
    matched, rejected = {}, {}
    end = cfg["endDate"]
    start = (dt.date.fromisoformat(end) - dt.timedelta(days=cfg["windowDays"] - 1)).isoformat()
    for l in lakes:
        like = _like(l["name"])
        if not like:
            continue
        rel = ev.fetch("cwms-catalog", f"{l['key']}.json", CWMS + "catalog/TIMESERIES", {"like": like, "page-size": 40}, purpose=f"USACE CWMS pool-elevation series for {l['name']}", accept=ACC)
        if not rel:
            continue
        ents = [e for e in json.load(open(os.path.join(home, rel), encoding="utf-8")).get("entries") or []
                if not re.search(r"tailwater|downstream|forebay", e["name"], re.I)]
        ents.sort(key=lambda e: (0 if re.search(r"rev|best", e["name"], re.I) else 1, e["name"]))
        for e in ents[:3]:
            loc = e["name"].split(".")[0]
            lrel = ev.fetch("cwms-location", f"{l['key']}__{D.safe_key(loc)}.json", CWMS + "locations/" + loc, {"office": e["office"]}, purpose=f"coordinates of CWMS location {loc} (identity check)", accept=ACC)
            ll = json.load(open(os.path.join(home, lrel), encoding="utf-8")) if lrel else {}
            lat, lon = ll.get("latitude"), ll.get("longitude")
            if not isinstance(lat, (int, float)) or abs(lat - l["lat"]) > cfg["radiusDeg"] or abs(lon - l["lon"]) > cfg["radiusDeg"]:
                rejected[l["key"]] = f"{loc}: not within {cfg['radiusDeg']} deg of the lake (a different water body with a similar name)"
                continue
            trel = ev.fetch("cwms-series", f"{l['key']}__{D.safe_key(e['name'])[:80]}.json", CWMS + "timeseries",
                            {"name": e["name"], "office": e["office"], "begin": start + "T00:00:00Z", "end": end + "T23:59:59Z", "unit": "ft"}, purpose=f"{cfg['windowDays']}-day pool elevation, CWMS {e['name']}", accept=ACC)
            if trel:
                matched[l["key"]] = {"lake": l["name"], "office": e["office"], "series": e["name"], "path": trel, "start": start, "end": end}
                rejected.pop(l["key"], None)
                break
    return {"lakesSearched": len(lakes), "lakesMatched": len(matched), "matched": matched, "rejected": rejected}


def analyze_lake_cwms(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    cfg = spec["params"]
    per, rej = {}, {}
    for a in mine:
        per.update(a.get("matched") or {})
        rej.update(a.get("rejected") or {})
    lakes, findings = {}, []
    for k in sorted(per):
        m = per[k]
        d = json.load(open(os.path.join(home, m["path"]), encoding="utf-8"))
        vals = d.get("values") or []
        days = {dt.datetime.fromtimestamp(v[0] / 1000, dt.timezone.utc).date().isoformat() for v in vals if v and v[1] is not None}
        end = dt.date.fromisoformat(m["end"])
        cov = round(len({(end - dt.timedelta(days=i)).isoformat() for i in range(30)} & days) / 30, 4)
        sane = all(0 < v[1] < 15000 for v in vals if v and v[1] is not None)
        lakes[k] = {"series": m["series"], "office": m["office"], "points": len(vals), "coverage30": cov, "sane": int(sane)}
    base = cfg["baselineFreshLakes"]
    fresh = sum(1 for v in lakes.values() if v["coverage30"] >= cfg["coverage30"] and v["sane"])
    metrics = {"lakes": lakes, "newFreshLakes": fresh, "freshLakesBase": base, "freshLakesCand": base + fresh, "rejectedIdentity": len(rej)}
    g = f"discovery.exp.{spec['avenueId']}"
    if fresh:
        change = {"scientificChange": "Bind additional fleet lakes to an independent USACE CWMS pool-elevation series as a verified alternate level source.",
                  "previous": f"{base} fleet lakes have a fresh independent (USGS) daily level series; the rest depend on a single primary feed.",
                  "proposed": {"bindings": {k: {"office": v["office"], "series": v["series"]} for k, v in lakes.items() if v["coverage30"] >= cfg["coverage30"] and v["sane"]}},
                  "evidenceSummary": f"{len(lakes)} CWMS series downloaded; identity verified by location coordinates; {fresh} have >= {cfg['coverage30']:.0%} of the last 30 days and plausible elevations.",
                  "validationMethod": "name search in the CWMS catalog, coordinate check against the lake, 30-day coverage and plausibility check (offline recompute)",
                  "validationResults": {"newFreshLakes": fresh, "rejectedIdentity": len(rej)},
                  "practicalEffect": "More lakes keep a fresh, independent level reading when the primary source fails, so fewer lake states go stale or ABSTAIN.",
                  "scoreImpact": "None in lake-brain-score-v1 (no coverage-of-fresh-sources dimension; the score is capped at 3.0 by profiled share). Measured as a coverage gain only.",
                  "limitations": "Coverage, not accuracy: no cross-check against a second source for these lakes; binding needs Lake Brain review and approval."}
        cap = {"kind": "coverage", "name": "fleet lakes with a fresh independent level series", "direction": "higher_better", "baselineMetric": f"{g}.freshLakesBase",
               "candidateMetric": f"{g}.freshLakesCand", "minDelta": 1, "nMetric": f"{g}.newFreshLakes", "minN": 1,
               "tests": [{"metric": f"{g}.newFreshLakes", "op": ">=", "threshold": 1}]}
        paths = sorted({m["path"] for m in per.values()})
        findings.append(D.finding("LAKE-CWMS-COVERAGE", f"{fresh} more fleet lakes have a verified fresh independent CWMS level series.", "EVIDENCE", paths, home,
                                  "CWMS catalog + location identity + 30-day coverage", f"{g}.newFreshLakes", ">=", 1, tier="CANDIDATE_CHANGE", change=change, capability=cap))
    weak = []
    owner = []
    for k, why in rej.items():
        owner.append({"id": f"lake-level-{k}", "gap": "LAKE-GEN-COVERAGE", "publisher": "operating agency for " + k.replace("_", " "),
                      "dataset": "daily pool/lake elevation", "access": f"CWMS search found only a different water body ({why}); identify the operator and its public data service",
                      "verified": False, "addresses": "lake-level coverage for a fleet lake with no independent fresh level source"})
    return {"metrics": metrics, "findings": findings, "weak": weak, "limitations": [], "owner": owner}


# ------------------------------------------------------------------------------------------------------------------------------- cross-Brain
def analyze_xb_wt_fish(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Producer: Water Temp candidate bias correction. Consumer: Fish temperature-gated spawn-window rules. Effect on a practical prediction at
    the pilot lake: how many days earlier/later each species' spawn temperature threshold is crossed in spring once the correction is applied.
    This is an integration PROPOSAL: it measures the effect size, it does not validate either Brain nor publish anything."""
    wt = (upstream or {}).get("water-temp") or {}
    ch = os.path.join(home, wt.get("path", "-"), "candidate-changes.json")
    if not wt.get("packaged") or not os.path.exists(ch):
        return {"metrics": {"producerCandidate": 0}, "findings": [], "weak": [], "limitations": [{"limitation": "no validated Water Temp candidate change this campaign: nothing to propagate", "kind": "dependency"}]}
    changes = json.load(open(ch, encoding="utf-8"))["changes"]
    best = [c for c in changes if c["measured"]["improved"]]
    if not best:
        return {"metrics": {"producerCandidate": 0}, "findings": [], "weak": [], "limitations": [{"limitation": "Water Temp produced no measured improvement", "kind": "dependency"}]}
    c = best[0]
    offs = c["proposed"]["offsetsC"]
    rung = c["proposed"]["cell"]
    forc = D.m0_daily(json.load(open(os.path.join(home, spec["pilotForcing"]), encoding="utf-8"))["daily"])
    year = spec["year"]
    rules = []
    for p in sorted(glob.glob(os.path.join(home, spec["bundle"], "rules", "*.json"))):
        if p.endswith("manifest.json"):
            continue
        for r in json.load(open(p, encoding="utf-8"))["rules"]:
            t = (r.get("phenology") or {}).get("tempC")
            if r.get("kind") == "PHENOLOGY" and t and (r.get("phenology") or {}).get("event") == "spawn":
                rules.append((r["speciesId"], r["ruleId"], t["min"]))
    days = sorted(d for d in forc if d.startswith(str(year)))
    series = {d: D.m0_for_date(forc, d) for d in days}

    def key(d):
        s = season_of(int(d[5:7]))
        return {"season": s, "region_season": f"{spec['region']}|{s}"}.get(rung)
    base_t = {d: v for d, v in series.items() if v is not None}
    cand_t = {d: v - offs.get(key(d), 0.0) for d, v in base_t.items() if key(d)}
    if not cand_t:
        return {"metrics": {"producerCandidate": 1, "applicable": 0}, "findings": [], "weak": [], "limitations": [{"limitation": f"correction rung {rung} cannot be applied to the pilot lake (class unknown)", "kind": "dependency"}]}

    def first_cross(ts, thr):
        for d in sorted(ts):
            if ts[d] >= thr and int(d[5:7]) >= 2:
                return d
        return None
    shifts = {}
    for sid, rid, thr in rules:
        a, b = first_cross(base_t, thr), first_cross(cand_t, thr)
        if a and b:
            shifts[f"{sid}:{rid}"] = (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
    vals = sorted(shifts.values())
    m = {"producerCandidate": 1, "producerRung": rung, "year": year, "rulesTested": len(shifts), "medianShiftDays": vals[len(vals) // 2] if vals else None,
         "maxAbsShiftDays": max((abs(v) for v in vals), default=None), "shifts": shifts}
    report = {"producer": "water-temp (candidate bias correction " + rung + ")", "consumer": "biological-state (temperature-gated spawn-window rules)",
              "contractCompatibility": "water-temp-state-v1 currentTempF/kind + fish rule applicability tempC: compatible (both degrees; Fish converts F to C); the correction would be applied inside Water Temp before publication, so no contract change is needed",
              "validationRequired": "Water Temp correction independently validated (done above) AND at least one species spawn window compared with field outcomes (FISH-VAL-001, not done)",
              "expectedBenefit": f"Spring spawn-threshold crossing dates move by a median {m['medianShiftDays']} days (max {m['maxAbsShiftDays']}) across {len(shifts)} spawn rules at the pilot lake",
              "status": "PROPOSAL (not published, not validated end to end)"}
    m["integrationProposal"] = report
    g = f"discovery.exp.{spec['avenueId']}"
    f = D.finding("XB-WT-FISH", "The Water Temp candidate correction changes Fish spawn-threshold timing at the pilot lake by a measurable number of days.", "EVIDENCE",
                  [spec["pilotForcing"]], home, "effect-size computation on the pilot lake's forcing: production M0 vs corrected M0 against species spawn thresholds",
                  f"{g}.rulesTested", ">=", 1, tier="SCIENTIFIC_SUPPORT")
    return {"metrics": m, "findings": [f], "weak": [], "limitations": [], "integration": report}


def analyze_owner_actions(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Evidence the system cannot fetch itself: recorded as actionable owner records (publisher, access, what it would address)."""
    acts = spec["params"]["actions"]
    return {"metrics": {"ownerActions": len(acts)}, "findings": [], "weak": [], "limitations": [], "owner": acts}


EXPERIMENTS = {
    "owner-actions": {"acquire": acquire_none, "analyze": analyze_owner_actions},
    "wt-bias": {"acquire": acquire_none, "analyze": analyze_wt_bias},
    "fish-rule-grade": {"acquire": acquire_none, "analyze": analyze_fish_rules},
    "dataset-search": {"acquire": acquire_dataset_search, "analyze": analyze_dataset_search},
    "lake-cwms": {"acquire": acquire_lake_cwms, "analyze": analyze_lake_cwms},
    "xb-wt-fish": {"acquire": acquire_none, "analyze": analyze_xb_wt_fish},
}
