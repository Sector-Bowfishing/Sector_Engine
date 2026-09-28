"""Clarity Fusion Stage 5: the preregistered confidence-tier decision.

Reads two ClarityReplay --current outputs (validation 2020-24, discovery
2025-26) run with the stricter High rule, and applies the decision rule in
docs/clarity/stage5/CONFIDENCE_TIERS_PREREGISTRATION.md exactly:

  1. validation: High has >= 20 target passes and >= 10,000 cells
  2. validation: 95% paired cluster bootstrap of (Moderate - High) mean |log10|
     lies entirely above 0 (target passes resampled jointly, 2,000 draws, seed 5)
  3. validation: High mean |log10| <= 0.80 x Moderate's
  4. validation: High mean |ft| < Moderate's
  5. discovery:  High mean |log10| < Moderate's

Only cells that showed a number count (E and F are left out, as in Stage 4).

usage: python3 confidence_tiers.py validation.json discovery.json out.json
"""
import sys, json, random

TIERS = ("high", "moderate", "low")


def per_target(d):
    """target -> tier -> [cells, sum |log10|, sum |ft|]"""
    out = {}
    for g, cl in d["clusters"].items():
        _, level, conf, *_ = g.split("|")
        if level in ("changedHistorical", "none") or conf not in TIERS:
            continue
        for t, (n, a, f) in cl.items():
            e = out.setdefault(t, {k: [0, 0.0, 0.0] for k in TIERS})[conf]
            e[0] += n; e[1] += a; e[2] += f
    return out


def means(rows):
    tot = {k: [0, 0.0, 0.0] for k in TIERS}
    for r in rows:
        for k in TIERS:
            for j in range(3):
                tot[k][j] += r[k][j]
    return {k: {"cells": v[0], "meanAbsLog10": v[1] / v[0] if v[0] else None,
                "meanAbsFt": v[2] / v[0] if v[0] else None} for k, v in tot.items()}


def main():
    val, disc, out_path = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
    pv, pd = per_target(val), per_target(disc)
    mv, md = means(pv.values()), means(pd.values())
    high_targets = sum(1 for r in pv.values() if r["high"][0] > 0)

    rows = list(pv.values())
    rng = random.Random(5)
    diffs = []
    for _ in range(2000):
        s = [rows[rng.randrange(len(rows))] for _ in rows]
        m = means(s)
        if m["high"]["meanAbsLog10"] is not None and m["moderate"]["meanAbsLog10"] is not None:
            diffs.append(m["moderate"]["meanAbsLog10"] - m["high"]["meanAbsLog10"])
    diffs.sort()
    ci = [diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]] if diffs else None

    h, m = mv["high"], mv["moderate"]
    checks = {
        "1_sample": {"pass": high_targets >= 20 and h["cells"] >= 10_000,
                     "highTargets": high_targets, "highCells": h["cells"]},
        "2_separation": {"pass": bool(ci) and ci[0] > 0, "moderateMinusHighCI95": ci,
                         "point": (m["meanAbsLog10"] - h["meanAbsLog10"]) if h["meanAbsLog10"] is not None else None},
        "3_size": {"pass": h["meanAbsLog10"] is not None and h["meanAbsLog10"] <= 0.80 * m["meanAbsLog10"],
                   "ratioHighToModerate": (h["meanAbsLog10"] / m["meanAbsLog10"]) if h["meanAbsLog10"] is not None else None},
        "4_feet": {"pass": h["meanAbsFt"] is not None and h["meanAbsFt"] < m["meanAbsFt"],
                   "highFt": h["meanAbsFt"], "moderateFt": m["meanAbsFt"]},
        "5_replicates": {"pass": md["high"]["meanAbsLog10"] is not None
                         and md["high"]["meanAbsLog10"] < md["moderate"]["meanAbsLog10"],
                         "discoveryHigh": md["high"]["meanAbsLog10"], "discoveryModerate": md["moderate"]["meanAbsLog10"]},
    }
    keep = all(c["pass"] for c in checks.values())
    report = {"decision": "keep High / Moderate / Low" if keep else "collapse to Moderate / Low (user-facing)",
              "checks": checks, "validation": mv, "discovery": md,
              "targets": {"validation": val["targets"], "discovery": disc["targets"]}}
    json.dump(report, open(out_path, "w"), indent=1)
    for k, c in checks.items():
        print(f"{k:14s} {'PASS' if c['pass'] else 'FAIL'}  " + ", ".join(f"{a}={b}" for a, b in c.items() if a != "pass"))
    for name, mm in (("validation", mv), ("discovery", md)):
        print(name, {k: (v["cells"], round(v["meanAbsLog10"], 4) if v["meanAbsLog10"] else None,
                         round(v["meanAbsFt"], 3) if v["meanAbsFt"] else None) for k, v in mm.items()})
    print("DECISION:", report["decision"])


if __name__ == "__main__":
    main()
