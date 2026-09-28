"""Summarise the Stage 4 Current Clarity replay (ClarityReplay --current).

Per set (discovery 2025-26, validation 2020-24), by confidence, by evidence
level, and by evidence kind: cells, target passes, mean and median absolute
error in log10 FNU and in feet, the share within 0.1 log10 (about +/-26% in
FNU, +/-16% in feet), and the share of targets inside the estimate's 80% range.
95% intervals by cluster bootstrap over target passes (2,000 draws).
Calibration holds when high < moderate < low in error, with intervals apart.

usage: python3 current_replay_summary.py <out.json> set=<replay.json> [set=<replay.json> ...]
"""
import sys, json, random


def med(h):
    n = sum(h)
    if not n:
        return None
    c = 0
    for i, x in enumerate(h):
        c += x
        if c >= n / 2:
            return (i + 0.5) * 0.01
    return None


def within(h, k=10):
    n = sum(h)
    return sum(h[:k]) / n if n else None


def summarise(d, key_of):
    groups, clusters = d["groups"], d["clusters"]
    out = {}
    for g, a in groups.items():
        k = key_of(g.split("|"))
        if k is None:
            continue
        o = out.setdefault(k, {"n": 0, "absLog": 0.0, "absFt": 0.0, "ranged": 0, "inRange": 0, "hist": [0] * 101, "cl": {}})
        o["n"] += a["n"]; o["absLog"] += a["absLog"]; o["absFt"] += a["absFt"]
        o["ranged"] += a["ranged"]; o["inRange"] += a["inRange"]
        o["hist"] = [x + y for x, y in zip(o["hist"], a["hist"])]
        for t, c in clusters.get(g, {}).items():
            e = o["cl"].setdefault(t, [0, 0.0, 0.0]); e[0] += c[0]; e[1] += c[1]; e[2] += c[2]
    res = {}
    rng = random.Random(4)
    for k, o in out.items():
        cl = list(o["cl"].values())
        boots = []
        for _ in range(2000):
            s = [cl[rng.randrange(len(cl))] for _ in cl]
            n = sum(x[0] for x in s)
            if n:
                boots.append(sum(x[1] for x in s) / n)
        boots.sort()
        res[k] = {"cells": o["n"], "targets": len(cl),
                  "meanAbsLog10": round(o["absLog"] / o["n"], 4) if o["n"] else None,
                  "ci95": [round(boots[int(0.025 * len(boots))], 4), round(boots[int(0.975 * len(boots)) - 1], 4)] if boots else None,
                  "medianAbsLog10": med(o["hist"]), "within0p1Log10": round(within(o["hist"]), 3) if o["n"] else None,
                  "meanAbsFt": round(o["absFt"] / o["n"], 3) if o["n"] else None,
                  "inRange80": round(o["inRange"] / o["ranged"], 3) if o["ranged"] else None}
    return res


def main():
    out_path = sys.argv[1]
    report = {}
    for arg in sys.argv[2:]:
        name, path = arg.split("=", 1)
        d = json.load(open(path))
        # groups: set|level|confidence|key|class|season
        report[name] = {
            "targets": d["targets"],
            "byConfidence": summarise(d, lambda p: p[2] if p[1] not in ("changedHistorical", "none") else None),
            "byLevel": summarise(d, lambda p: p[1]),
            "byConfidenceAndKind": summarise(d, lambda p: f"{p[2]}|{p[3]}" if p[1] not in ("changedHistorical", "none") else None),
            "byLevelAndSeason": summarise(d, lambda p: f"{p[1]}|{p[5]}"),
            "byConfidenceAndClass": summarise(d, lambda p: f"{p[2]}|{p[4]}" if p[1] not in ("changedHistorical", "none") else None),
            "refusedWithoutValue": sum(d.get("refusedWithoutValue", {}).values()),
            "rules": d["rules"],
        }
    json.dump(report, open(out_path, "w"), indent=1)
    for name, r in report.items():
        print(f"== {name}: {r['targets']} target passes")
        for sec in ("byConfidence", "byLevel"):
            print(f"  {sec}")
            for k, v in sorted(r[sec].items(), key=lambda kv: -kv[1]["cells"]):
                print(f"    {k:22s} cells {v['cells']:>9,} targets {v['targets']:>4}  mean|dlog| {v['meanAbsLog10']:.3f} "
                      f"{v['ci95']}  median {v['medianAbsLog10']:.3f}  <=0.1 {v['within0p1Log10']:.2f}  "
                      f"mean|dft| {v['meanAbsFt']:.2f}  in80 {v['inRange80']}")


if __name__ == "__main__":
    main()
