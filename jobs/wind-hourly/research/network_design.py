"""Score Acceleration §31–33: choose exposed/protected bank pairs for autonomous validation from the FROZEN fetch tables
and FROZEN CEM (Python mirror verified identical to wind-cem). Design aid only; no outcome data is used.

  python research/network_design.py OUT.json

For every bank pair on one lake within MAX_SEP metres (one host can service both instruments):
  Hm0 per quadrant (wind FROM 0/90/180/270, 9-ray fetch, U = 6 m/s ≈ 13 mph, 6 h duration) and at U = 4.5 m/s (10 mph)
  contrast_q = |H1 - H2| / max(H1, H2)   (addendum v1 eligibility: >= 20%)
Score: quadrants with contrast >= 20% (need >= 3), ordering flips (exposed bank changes with direction), chop-class
difference, both banks measurable (some quadrant Hm0 >= 1 in) — ranked; top pairs per lake."""
import base64, gzip, json, math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import wave_memory as W

IOS = os.path.expanduser("~/Desktop/Development/iOS/sector-wind/Sector/Assets.xcassets/FishIntel/Wind")
LAKES = {"guntersville": "Guntersville", "wheeler": "Wheeler", "wilson": "Wilson", "pickwick": "Pickwick"}
MAX_SEP = 1500.0
Q = {"N": 0, "E": 90, "S": 180, "W": 270}
U_DESIGN = (6.0, 4.5)


def load(lake):
    d = json.load(gzip.open(os.path.join(IOS, f"{LAKES[lake]}WindFetch.dataset/{lake}.windfetch.json.gz")))
    banks = d["banks"] if isinstance(d["banks"], list) else json.loads(d["banks"].replace("'", '"').replace("False", "false").replace("True", "true"))
    raw = base64.b64decode(d["tableBase64"]); n = len(raw) // 2
    t = np.array(struct.unpack(f"<{n}H", raw), dtype=float).reshape(len(banks), 120) * 10.0
    return banks, t


def km(a, b):
    return 6371000 * 2 * math.asin(math.sqrt(math.sin(math.radians(b[0] - a[0]) / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2))


def main(outp):
    out = {}
    for lake in LAKES:
        banks, T = load(lake)
        ok = [i for i, b in enumerate(banks) if not b.get("belowResolution")]
        H = {u: np.array([[W.cem(u, W.nine_ray(T[i], q), 6 * 3600) for q in Q.values()] for i in range(len(banks))]) for u in U_DESIGN}
        pos = np.array([b["standoff"] or b["anchor"] for b in banks])
        cand = []
        # spatial bucketing for the pair search
        cell = {}
        for i in ok:
            k = (int(pos[i][0] / 0.0135), int(pos[i][1] / 0.0165)); cell.setdefault(k, []).append(i)
        for i in ok:
            k = (int(pos[i][0] / 0.0135), int(pos[i][1] / 0.0165))
            for dk in [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1)]:
                for j in cell.get((k[0] + dk[0], k[1] + dk[1]), []):
                    if j <= i:
                        continue
                    sep = km(pos[i], pos[j])
                    if sep > MAX_SEP or sep < 150:
                        continue
                    h1, h2 = H[6.0][i], H[6.0][j]
                    con = np.abs(h1 - h2) / np.maximum(np.maximum(h1, h2), 1e-6)
                    nq = int((con >= 0.2).sum())
                    if nq < 3:
                        continue
                    flips = int(len({int(np.sign(a - b)) for a, b, c in zip(h1, h2, con) if c >= 0.2}) > 1)
                    cls1 = [W.cls(x) for x in h1]; cls2 = [W.cls(x) for x in h2]
                    classDiff = int(sum(a != b for a, b in zip(cls1, cls2)))
                    measurable = bool(max(h1) >= 0.0254 and max(h2) >= 0.0254)
                    cand.append({"a": banks[i]["id"], "b": banks[j]["id"], "aLatLon": [round(x, 5) for x in banks[i]["anchor"]], "bLatLon": [round(x, 5) for x in banks[j]["anchor"]],
                                 "separationM": round(sep), "quadrantsContrast20": nq, "orderingFlips": flips, "classDiffQuadrants": classDiff,
                                 "measurable": measurable, "hm0In_6ms": {q: [round(h1[k2] / 0.0254, 1), round(h2[k2] / 0.0254, 1)] for k2, q in enumerate(Q)},
                                 "hm0In_4p5ms": {q: [round(H[4.5][i][k2] / 0.0254, 1), round(H[4.5][j][k2] / 0.0254, 1)] for k2, q in enumerate(Q)},
                                 "meanContrast": round(float(con.mean()), 3), "regionA": banks[i].get("region"), "regionB": banks[j].get("region")})
        cand.sort(key=lambda c: (c["measurable"], c["quadrantsContrast20"], c["orderingFlips"], c["classDiffQuadrants"], c["meanContrast"]), reverse=True)
        # de-duplicate: keep pairs whose anchors are >= 1 km from already chosen pairs
        chosen = []
        for c in cand:
            if all(km(c["aLatLon"], x["aLatLon"]) > 1000 for x in chosen):
                chosen.append(c)
            if len(chosen) == 5:
                break
        out[lake] = {"banks": len(banks), "eligiblePairs": len(cand), "fullPairs(4q,flip,measurable)": sum(c["quadrantsContrast20"] == 4 and c["orderingFlips"] and c["measurable"] for c in cand),
                     "top": chosen}
        print(lake, len(banks), "banks;", len(cand), "pairs with >=3 quadrants;", out[lake]["fullPairs(4q,flip,measurable)"], "4q+flip+measurable", flush=True)
    json.dump(out, open(outp, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
