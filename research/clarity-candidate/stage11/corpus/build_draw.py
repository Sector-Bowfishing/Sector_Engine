"""Stage 11 corpus expansion E (PREREGISTRATION_STAGE11.md section 2.4 + addendum B). Historical only (<= 2025-12-31).
E-AL: every ADEM (21AWIC) lake/reservoir Secchi row in Alabama in the pool. E-TN (addendum B): every TDEC (TDECWR_WQX)
row in Tennessee (TVA publishes nothing to WQP). E-NAT: the national draw, sites in no earlier file and with no Secchi
record dated 2025-01-01 or later (so they cannot enter the P2 fresh national pool), seed 20261111, <= 3 per site,
one per site-month, <= 12% per state, same-day-turbidity rows first, 4,000 station-days. Writes e_draw.csv."""
import csv, json, random, collections, os, datetime as dt
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
W = f"{S}/q9/wqp"
earlier = set()
for f in ("national_sample", "targeted_sample", "targeted_capped", "all_matchups", "targeted_matchups", "national_matchups", "national_matchups_clean"):
    p = f"{S}/q9/{f}.csv"
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            earlier.add(r.get("site_id") or r.get("site") or r.get("group"))
for r in csv.DictReader(open(f"{S}/stage8/fresh_draw.csv")):
    earlier.add(r["site"])
for l in open(f"{S}/stage7/national_sites.txt"):
    earlier.add(l.strip())
earlier.discard(None); earlier.discard("")
sec = list(csv.DictReader(open(f"{W}/secchi.csv")))
last = collections.defaultdict(str)
for r in sec:
    last[r["site_id"]] = max(last[r["site_id"]], r["date"])
turb_days = {(r["site_id"], r["date"]) for r in csv.DictReader(open(f"{W}/turbidity.csv"))}
GUNT_BOX = (34.27, -86.42, 35.06, -85.60)
def in_gunt(r):
    la, lo = float(r["lat"]), float(r["lon"])
    return GUNT_BOX[0] <= la <= GUNT_BOX[2] and GUNT_BOX[1] <= lo <= GUNT_BOX[3]
ok = lambda r: r["date"] <= "2025-12-31" and 0.05 <= float(r["secchi_m"]) <= 25 and r.get("bottom_visible") != "true"
rows = []
eal = [r for r in sec if r["org"] == "21AWIC" and r["state"] == "AL" and ok(r)]
etn = [r for r in sec if r["org"] == "TDECWR_WQX" and r["state"] == "TN" and ok(r)]
for tag, rs in (("E-AL", eal), ("E-TN", etn)):
    seen = set()
    for r in rs:
        k = (r["site_id"], r["date"])
        if k in seen: continue
        seen.add(k); rows.append({**r, "set": tag, "turbSameDay": k in turb_days})
pool = [r for r in sec if ok(r) and r["site_id"] not in earlier and last[r["site_id"]] < "2025-01-01"
        and r["org"] not in ("21AWIC", "TDECWR_WQX") and not in_gunt(r)]
rng = random.Random(20261111)
rng.shuffle(pool)
pool.sort(key=lambda r: 0 if (r["site_id"], r["date"]) in turb_days else 1)      # stable: shuffled within each tier
per_site, per_month, per_state = collections.Counter(), set(), collections.Counter()
nat, N = [], 4000
for r in pool:
    if len(nat) >= N: break
    sm = (r["site_id"], r["date"][:7])
    if per_site[r["site_id"]] >= 3 or sm in per_month or per_state[r["state"]] >= 0.12 * N:
        continue
    per_site[r["site_id"]] += 1; per_month.add(sm); per_state[r["state"]] += 1
    nat.append({**r, "set": "E-NAT", "turbSameDay": (r["site_id"], r["date"]) in turb_days})
rows += nat
out = []
for i, r in enumerate(rows):
    out.append({"id": f"e{i:05d}", "site": r["site_id"], "org": r["org"], "name": r["site_name"], "lat": r["lat"], "lon": r["lon"],
                "date": r["date"], "time": r.get("time", ""), "secchi_m": r["secchi_m"], "secchi_ft": round(float(r["secchi_m"]) * 3.28084, 3),
                "state": r["state"], "set": r["set"], "turbSameDay": r["turbSameDay"]})
with open("e_draw.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
st = {"E-AL": len([o for o in out if o["set"] == "E-AL"]), "E-TN": len([o for o in out if o["set"] == "E-TN"]), "E-NAT": len(nat),
      "E-NAT sites": len({o["site_id"] for o in nat}), "E-NAT with same-day turbidity": sum(o["turbSameDay"] for o in nat),
      "earlier-file sites excluded": len(earlier), "eligible national pool rows": len(pool), "states": dict(per_state.most_common())}
json.dump(st, open("e_draw_stats.json", "w"), indent=1); print(json.dumps(st, indent=1))
