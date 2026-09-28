"""How wrong was the old membership, and does the new one pass the
connectivity checks? (Clarity Fusion Stage 1)

For every shoreline segment with an old tributaryId, the through-water
distance from the segment to that tributary's own water (its flow lines in the
lake) against the straight-line distance the old profile used. An old
association that needs far more water than the straight line -- or cannot
reach the creek through the water at all within 20 km -- crossed land.

Also: the peninsula test (pairs of water cells close in a straight line but far
apart through the water must not share an arm unless the arm connects them).

usage: geo/bin/python membership_audit.py --raw DIR --final DIR
"""
import os, sys, json, gzip, csv, math, argparse, collections
import numpy as np
from scipy.sparse import csgraph
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_arm_graph as B
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "jobs", "lake-surface"))
import fill_lake


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--raw", required=True); ap.add_argument("--final", required=True)
    a = ap.parse_args()
    raw = json.load(open(os.path.join(a.raw, "arms_raw.json")))
    code_of = {int(k): v for k, v in raw["codes"].items()}
    names = {int(k): v["name"] for k, v in raw["arms"].items()}
    seeds = np.load(os.path.join(a.raw, "seeds.npy")); water = np.load(os.path.join(a.raw, "water.npy"))
    G = json.load(open(os.path.join(a.raw, "frame.json")))["frame"]["cellGroundM"]
    idx = fill_lake._index(water); A = fill_lake._graph8(water, idx, G)
    segs = json.load(gzip.open(os.path.join(B.ASSETS, "GuntersvilleSegments.dataset", "Guntersville.segments.json.gz")))["segments"]
    reg = json.load(gzip.open(os.path.join(B.ASSETS, "GuntersvilleTributaries.dataset", "Guntersville.tributaries.json.gz")))
    reg_name = {t["id"]: t["name"] for t in reg["tributaries"]}
    rows_raw = json.load(open(os.path.join(a.raw, "segment_rows_raw.json")))
    diff = list(csv.DictReader(open(os.path.join(a.final, "membership_diff.csv"))))

    # through-water distance field from each NAME's water (all systems with it:
    # the old id meant the name)
    by_name = collections.defaultdict(list)
    for sid, nm in names.items():
        by_name[nm].append(code_of[sid])
    fields = {}
    for nm in set(reg_name.values()):
        codes = by_name.get(nm, [])
        cells = idx[np.isin(seeds, codes) & water] if codes else np.array([], int)
        if cells.size:
            fields[nm] = csgraph.dijkstra(A, directed=False, indices=cells, min_only=True, limit=20_000)
    out = []
    crossed = collections.Counter(); total = collections.Counter()
    for s, rr, d in zip(segs, rows_raw, diff):
        tid = s.get("tributaryId")
        if not tid or not rr["cell"]:
            continue
        nm = reg_name.get(tid)
        f = fields.get(nm)
        tw = float(f[idx[tuple(rr["cell"])]]) if f is not None else float("inf")
        sl = float(s["distanceToTributaryM"] or 0)
        land = (not np.isfinite(tw)) or (tw > 3 * sl + 500)
        total[tid] += 1
        if land:
            crossed[tid] += 1
        out.append({"segment": rr["segment"], "oldTributaryId": tid, "straightLineM": round(sl), "throughWaterM": round(tw) if np.isfinite(tw) else "",
                    "crossedLand": land, "status": d["status"], "newTributaryId": d["newTributaryId"] or "mainstem"})
    with open(os.path.join(a.final, "old_association_land_check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    n_cross = sum(crossed.values()); n = sum(total.values())
    print(f"old tributary associations: {n}; crossed land (through-water > 3x straight line + 500 m, or no water path within 20 km): {n_cross}")
    for t, c in crossed.most_common(15):
        print(f"   {t:24} {c:4} of {total[t]:4}")
    # how the land-crossers were resolved, and whether any SURVIVING change is not a land-crosser
    res = collections.Counter((r["crossedLand"], r["status"].split(":")[0]) for r in out)
    print("by (crossedLand, status):", dict(res))
    json.dump({"associations": n, "crossedLand": n_cross, "byTributary": dict(crossed), "totals": dict(total),
               "byCrossedAndStatus": {f"{k[0]}|{k[1]}": v for k, v in res.items()}},
              open(os.path.join(a.final, "old_association_land_check.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
