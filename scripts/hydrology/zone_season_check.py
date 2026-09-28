"""POST-HOC, EXPLORATORY (not gate evidence): does the 2025-vs-2026
disagreement in zone_events.py follow the season? Cold = Nov-Mar, warm =
Apr-Oct. Storm-lag 0-3 d zone events of the large/medium/small groups against
each position's dry-week noise band and dry share.

usage: python3 zone_season_check.py <zone_events.json> <arm_zones.json>
"""
import sys, json, collections, statistics as st
from math import comb
r = json.load(open(sys.argv[1])); zz = json.load(open(sys.argv[2]))
K = {a: v.get("zones") for a, v in zz["arms"].items()}
NAMED = ("town-creek-marshall", "south-sauty-creek", "browns-creek")
def binp(k, n, p): return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)) if n else 1.0
cells = collections.defaultdict(list)
for e in r["zoneEventDump"]:
    if e["anom"] is None or e["lag"] is None or e["lag"] > 3 or e["arm"] in NAMED: continue
    m = int(e["date"][5:7]); season = "cold (Nov-Mar)" if m in (11, 12, 1, 2, 3) else "warm (Apr-Oct)"
    cells[(e["date"][:4], season)].append(e)
for key in sorted(cells):
    xs = cells[key]
    k = sum(e["anom"] > r["noise"][e["pos"]][1] for e in xs)
    ds = st.mean(r["dryShare"][e["pos"]] for e in xs)
    months = collections.Counter(e["date"][:7] for e in xs)
    print(f"{key[0]} {key[1]:15s} events {len(xs):3d}  murkier {100*k/len(xs):4.0f}%  (dry ~{100*ds:.0f}%)  p={binp(k, len(xs), ds):.4f}"
          f"  median x{10**st.median(e['anom'] for e in xs):.2f}  months {dict(sorted(months.items()))}")
