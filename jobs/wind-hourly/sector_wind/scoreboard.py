"""Wind Candidate scoreboard, derived by code from the FROZEN rubric v1 (pre-registration §1) and evidence.

  python -m sector_wind.scoreboard --store local:$MIRROR --evidence-dir <docs/intelligence/wind/stage3a/evidence> \
      [--log docs/intelligence/wind/WIND_SCORE_CHANGE_LOG.jsonl] [--json out.json]

Nobody types a score. Each dimension states its evidence source, sample size, date range and why it
passes or fails. Derivation rules (the same strict reading that produced the Stage 2 measured dimensions):
  - credit is linear between the rubric's zero and full thresholds;
  - with several conditions, credit is the minimum across them;
  - a condition with no numeric zero threshold is pass/fail;
  - a condition that was not measured (e.g. no observed events) earns 0. Unmeasured is not passed.
Dimensions 1-4 use the most recent completed evidence window: the Stage 2 archived backfill until
Milestone A completes, then the live milestone evaluation. Dimension 8 counts only the live shadow.
The hard caps are applied last. The score log is append-only: a new line is written only when the
official score changes, with the old and new score, the dimensions that moved and why."""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from datetime import datetime, timedelta, timezone

from . import monitor
from .sample import iso

RUBRIC = "frozen rubric v1 (WIND_STAGE2_PREREGISTRATION.md §1)"
CANDIDATE = "wind-candidate-2026.10.stage2-baseline"
WEIGHTS = {1: 12, 2: 8, 3: 5, 4: 5, 5: 10, 6: 20, 7: 20, 8: 8, 9: 4, 10: 8}
NAMES = {1: "Wind speed", 2: "Direction", 3: "Gust", 4: "Lead time", 5: "Fetch method", 6: "Exposure (field)",
         7: "Surface (field)", 8: "Freshness/reliability", 9: "Coverage", 10: "Provenance/Unknown"}
LIVE_START = datetime(2026, 10, 8, tzinfo=timezone.utc)
LEADS = ("1", "3", "6", "12", "18")


def lin(x, zero, full):
    """Linear credit; works whichever way the scale runs."""
    if x is None:
        return 0.0
    if full > zero:
        return max(0.0, min(1.0, (x - zero) / (full - zero)))
    return max(0.0, min(1.0, (zero - x) / (zero - full)))


def pooled(part: dict, keys=LEADS):
    """n-weighted pooling over leads for MAE, bias; pooled counts for direction and gust."""
    rows = [part[k] for k in keys if k in part and part[k].get("n")]
    n = sum(r["n"] for r in rows)
    if not n:
        return {}
    out = {"n": n, "mae": sum(r["mae"] * r["n"] for r in rows) / n, "bias": sum(r["bias"] * r["n"] for r in rows) / n}
    dn = sum(r.get("dir_n", 0) for r in rows)
    if dn:
        out.update({"dir_n": dn, "dir_within22_5": sum(r["dir_within22_5"] * r["dir_n"] for r in rows if r.get("dir_n")) / dn,
                    "dir_mean": sum(r["dir_mean"] * r["dir_n"] for r in rows if r.get("dir_n")) / dn})
    gn = sum(r.get("gust_n", 0) for r in rows)
    if gn:
        out.update({"gust_n": gn, "gust_bias": sum(r["gust_bias_conditional"] * r["gust_n"] for r in rows if r.get("gust_n")) / gn})
    return out


def dims_1_to_4(ev: dict, label: str) -> dict:
    nbm = ev["nbm"]; night, allh = nbm["night"], nbm["allHours"]
    pn, pa = pooled(night), pooled(allh)
    win = f"{nbm['window'][0][:10]} -> {nbm['window'][1][:10]}"
    out = {}
    # 1 speed (night): MAE 1.6 -> 1.0 linear; |bias| <= 0.3 pass/fail; >=15 mph POD >= 0.5 & FAR <= 0.5 pass/fail; unmeasured = 0
    obs15 = sum(night[k].get("n_obs_15mph", 0) for k in LEADS if k in night)
    pod15 = [night[k].get("pod_15mph") for k in LEADS if k in night]
    far15 = [night[k].get("far_15mph") for k in LEADS if k in night]
    if obs15 == 0:
        ev15, why15 = 0.0, "no observed >= 15 mph night events: unmeasured -> 0 (strict)"
    else:
        ok = all(p is not None and p >= 0.5 for p in pod15) and all(f is None or f <= 0.5 for f in far15)
        ev15, why15 = (1.0 if ok else 0.0), f"{obs15} observed events; POD {pod15} FAR {far15}"
    c = {"MAE": lin(pn.get("mae"), 1.6, 1.0), "|bias|<=0.3": 1.0 if abs(pn.get("bias", 9)) <= 0.3 else 0.0, ">=15mph POD/FAR": ev15}
    out[1] = {"credit": min(c.values()), "conditions": c, "source": label, "window": win, "n": pn.get("n"),
              "why": f"night pooled MAE {pn.get('mae', float('nan')):.3f}, bias {pn.get('bias', float('nan')):+.3f}; {why15}"}
    # 2 direction (all hours, both >= 2.6 m/s): within 22.5 0.65 -> 0.85 linear; circular MAE <= 20 pass/fail
    c = {"within22.5": lin(pa.get("dir_within22_5"), 0.65, 0.85), "circMAE<=20": 1.0 if (pa.get("dir_mean") or 99) <= 20 else 0.0}
    out[2] = {"credit": min(c.values()), "conditions": c, "source": label, "window": win, "n": pa.get("dir_n"),
              "why": f"within 22.5° {pa.get('dir_within22_5', float('nan')):.3f}, circular MAE {pa.get('dir_mean', float('nan')):.1f}°"}
    # 3 gust (all hours): |conditional bias| 3 -> 1 linear; >= 20 kt POD >= 0.6 & FAR <= 0.6 pass/fail; unmeasured = 0
    pods = [allh[k].get("gust20_pod") for k in LEADS if k in allh]
    fars = [allh[k].get("gust20_far") for k in LEADS if k in allh]
    if all(p is None for p in pods):
        ge, gwhy = 0.0, "no observed >= 20 kt gust events: unmeasured -> 0 (strict)"
    else:
        ge = 1.0 if all(p is not None and p >= 0.6 for p in pods) and all(f is None or f <= 0.6 for f in fars) else 0.0
        gwhy = f">= 20 kt POD {pods} FAR {fars}"
    c = {"|cond. bias|": lin(abs(pa.get("gust_bias", 9)), 3.0, 1.0), ">=20kt POD/FAR": ge}
    out[3] = {"credit": min(c.values()), "conditions": c, "source": label, "window": win, "n": pa.get("gust_n"),
              "why": f"conditional gust bias {pa.get('gust_bias', float('nan')):+.2f} m/s; {gwhy}"}
    # 4 lead (night): +18 h MAE degradation vs +1 h, 50% -> 15% linear; beats persistence at >= +3 h pass/fail
    m1, m18 = night.get("1", {}).get("mae"), night.get("18", {}).get("mae")
    deg = (m18 / m1 - 1) if m1 and m18 else None
    pers = nbm.get("persistenceNight", {})
    beats = [k for k in ("3", "6", "12", "18") if k in night and k in pers and night[k].get("mae") is not None and pers[k].get("mae")]
    ok = bool(beats) and all(night[k]["mae"] < pers[k]["mae"] for k in beats)
    c = {"+18h vs +1h": lin(deg, 0.50, 0.15) if deg is not None else 0.0, "beats persistence >= +3h": 1.0 if ok else 0.0}
    out[4] = {"credit": min(c.values()), "conditions": c, "source": label, "window": win, "n": night.get("18", {}).get("n"),
              "why": f"+18 h MAE {'%+.1f%%' % (100 * deg) if deg is not None else 'unmeasured'} vs +1 h; persistence compared at {beats}"}
    return out


def dim5(fetch_ev: dict) -> dict:
    f = fetch_ev
    c = {"SPM84/CEM method": 1.0 if f.get("method") == "SPM84/CEM 9-ray ±12° mean" else 0.0,
         "independent median <= 5%": 1.0 if (f.get("independentMedianRel") or 1) <= 0.05 else 0.0,
         "six frozen cases": 1.0 if f.get("sixCasesPass") else 0.0, "resolution flags": 1.0 if f.get("resolutionFlags") else 0.0}
    return {"credit": min(c.values()), "conditions": c, "source": f.get("source"), "window": f.get("date"), "n": f.get("rays"),
            "why": f"independent exact-geometry median relative difference {f.get('independentMedianRel')}"}


def dims_6_7(ledger_paths) -> dict:
    """Only a one-time holdout certification counts. Before it exists both are 0 ('no field data').
    The rubric gives no numeric zero threshold for 6 and 7, so each condition is pass/fail here; a
    partial-credit rule must be set by Michael/ChatGPT before certification (the 8/10 gate needs >= 70%)."""
    entries = []
    for p in ledger_paths:
        for path in glob.glob(p):
            entries += [json.loads(l) for l in open(path) if l.strip()]
    if not entries:
        z = {"credit": 0.0, "conditions": {"holdout certification": 0.0}, "source": "none", "window": None, "n": 0,
             "why": "no field data: 0 real observations; holdout sealed; no certification run"}
        return {6: dict(z), 7: dict(z)}
    e = entries[-1]
    ex, sf = e.get("exposure", {}), e.get("surface", {})
    if not e.get("sufficient"):
        z = lambda w: {"credit": 0.0, "conditions": {"sufficient holdout": 0.0}, "source": "certification ledger", "window": None, "n": w,
                       "why": "holdout below the frozen minimum (>= 24 pairs, >= 36 observations): insufficient, not pass/fail"}
        return {6: z(ex.get("n")), 7: z(sf.get("n"))}
    c6 = {"concordance >= 0.80": 1.0 if (ex.get("concordance") or 0) >= 0.80 else 0.0, ">= 40 pairs": 1.0 if ex.get("n", 0) >= 40 else 0.0}
    c7 = {"exact >= 0.60": 1.0 if sf.get("exact", 0) >= 0.6 else 0.0, "within1 >= 0.90": 1.0 if sf.get("within1", 0) >= 0.9 else 0.0,
          "severe <= 0.05": 1.0 if sf.get("severe", 1) <= 0.05 else 0.0, ">= 60 obs": 1.0 if sf.get("n", 0) >= 60 else 0.0}
    return {6: {"credit": min(c6.values()), "conditions": c6, "source": "certification ledger", "window": None, "n": ex.get("n"), "why": json.dumps(ex)},
            7: {"credit": min(c7.values()), "conditions": c7, "source": "certification ledger", "window": None, "n": sf.get("n"), "why": json.dumps(sf)}}


def dim8(store, cfg, now) -> dict:
    """Live shadow only (backfill shows decoding, not reliability). Completeness over the full UTC days
    since 2026-10-08 (30-day target), median availability age <= 90 min, fallbacks exercised."""
    end_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = max(0, min(30, (end_day - LIVE_START).days))
    if days == 0:
        return {"credit": 0.0, "conditions": {"30-day completeness": 0.0, "median age <= 90": 0.0, "fallbacks exercised": 0.0},
                "source": "live shadow archive", "window": f"{LIVE_START:%Y-%m-%d} -> (no complete day yet)", "n": 0,
                "why": "no complete live UTC day yet (clock started 2026-10-07 04:59Z; Milestone windows start 2026-10-08)"}
    m = monitor.milestone(store, cfg, LIVE_START, LIVE_START + timedelta(days=days) - timedelta(hours=1))
    worst = min(min(v["nbmShare"], v["rtmaShare"]) for v in m["lakes"].values())
    med = m["nbmAvailabilityAgeMin"]["median"]
    c = {"30-day completeness": (days / 30) * min(1.0, worst / 0.99), "median age <= 90": 1.0 if med is not None and med <= 90 else 0.0,
         "fallbacks exercised": 1.0 if m["runsUsingCatchup"] > 0 else 0.0}
    return {"credit": min(c.values()), "conditions": c, "source": "live shadow archive", "window": m["window"][0][:10] + " -> " + m["window"][1][:10],
            "n": m["hours"], "why": f"{days}/30 complete days, worst completeness {worst:.4f}, median age {med} min, catch-up runs {m['runsUsingCatchup']}"}


def dim9(cov: dict) -> dict:
    dev = cov.get("developmentLakesComplete", 0); n = cov.get("directoryLakesPassed", 0)
    c = {"development lakes (1 -> 4)": lin(dev, 1, 4), "directory lakes (0 -> 50)": lin(n, 0, 50)}
    return {"credit": min(c.values()), "conditions": c, "source": cov.get("source"), "window": cov.get("date"), "n": dev + n,
            "why": f"{dev}/4 development lakes, {n} directory lakes passing national QA"}


def dim10(prov: dict) -> dict:
    keys = ("kindEverywhere", "unknownIsGrey", "explanationOnEveryResult")
    c = {k: 1.0 if prov.get(k) else 0.0 for k in keys}
    return {"credit": min(c.values()), "conditions": c, "source": prov.get("source"), "window": prov.get("date"), "n": None,
            "why": "; ".join(f"{k}={prov.get(k)}" for k in keys)}


def caps(field_dims, overwater: dict) -> list:
    out = []
    if field_dims[6]["credit"] == 0 and field_dims[7]["credit"] == 0:
        out.append({"cap": 6.0, "rule": "Exposure or surface never field-validated"})
    if not overwater.get("measuredStationComparisons"):
        out.append({"cap": 7.0, "rule": "Land-only wind validation, no over-water reference"})
    return out


def compute(store, cfg, evidence_dir, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    E = lambda name: json.load(open(os.path.join(evidence_dir, name)))
    w = E("wind_skill_source.json")      # which skill evidence is current (Stage 2 backfill until Milestone A)
    skill = json.load(open(os.path.join(evidence_dir, w["file"])))
    d = dims_1_to_4(skill, w["label"])
    d[5] = dim5(E("fetch_method.json"))
    d.update(dims_6_7([os.path.join(evidence_dir, "certification*.jsonl")]))
    d[8] = dim8(store, cfg, now)
    d[9] = dim9(E("coverage.json"))
    d[10] = dim10(E("provenance.json"))
    ow = E("overwater.json")
    pts = {k: WEIGHTS[k] * d[k]["credit"] for k in d}
    raw = round(sum(pts.values()) / 10, 2)
    cp = caps(d, ow)
    official = round(min([raw] + [c["cap"] for c in cp]), 1)
    return {"candidate": CANDIDATE, "rubric": RUBRIC, "computedAt": iso(now),
            "dimensions": {k: {"name": NAMES[k], "weight": WEIGHTS[k], "points": round(pts[k], 2), **d[k]} for k in sorted(d)},
            "rawPoints": round(sum(pts.values()), 2), "raw": raw, "caps": cp, "official": official}


def render(s) -> str:
    L = [f"WIND CANDIDATE  {s['candidate']}  ({s['rubric']})", f"computed {s['computedAt']}", ""]
    for k, d in s["dimensions"].items():
        L.append(f"{k:>2} {d['name']:<22} {d['points']:5.1f} / {d['weight']:<3} credit {d['credit']:.2f}")
        L.append(f"     source: {d['source']} | window: {d['window']} | n: {d['n']}")
        L.append(f"     {d['why']}")
        L.append("     " + ", ".join(f"{c}={v:.2f}" for c, v in d["conditions"].items()))
    L += ["", f"RAW SCORE: {s['rawPoints']:.1f} / 100 -> {s['raw']:.2f} / 10", "ACTIVE CAPS:"]
    L += [f"  {c['cap']:.1f} — {c['rule']}" for c in s["caps"]] or ["  none"]
    L.append(f"OFFICIAL SCORE: {s['official']:.1f} / 10")
    return "\n".join(L)


def append_log(log_path, s, reason) -> dict | None:
    prev = None
    if os.path.exists(log_path):
        lines = [json.loads(l) for l in open(log_path) if l.strip()]
        prev = lines[-1] if lines else None
    if prev and prev["newScore"] == s["official"] and prev.get("dimensionPoints") == {str(k): v["points"] for k, v in s["dimensions"].items()}:
        return None
    moved = []
    if prev and prev.get("dimensionPoints"):
        moved = [k for k, v in s["dimensions"].items() if abs(prev["dimensionPoints"].get(str(k), -1) - v["points"]) > 1e-6]
    e = {"timestamp": s["computedAt"], "oldScore": prev["newScore"] if prev else None, "newScore": s["official"],
         "dimensionsChanged": [f"{k} {s['dimensions'][k]['name']}" for k in moved],
         "newEvidence": {str(k): s["dimensions"][k]["why"] for k in moved}, "reason": reason,
         "dimensionPoints": {str(k): v["points"] for k, v in s["dimensions"].items()}, "raw": s["raw"], "caps": [c["cap"] for c in s["caps"]]}
    with open(log_path, "a") as f:
        f.write(json.dumps(e) + "\n")
    return e


def main(argv=None):
    from .store import open_store
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True); ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--log", default=None); ap.add_argument("--reason", default="scoreboard recompute")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lakes.json")))
    s = compute(open_store(a.store), cfg, a.evidence_dir)
    print(render(s))
    if a.log:
        e = append_log(a.log, s, a.reason)
        print("\nscore log: " + ("appended" if e else "unchanged (no new line)"))
    if a.json:
        json.dump(s, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
