"""Stage 14 cert, step 2 (value-blind): an index of the Stage 1 WQP Secchi pull WITHOUT the secchi_m column, plus the
eligibility counts under candidate rules. secchi_m is deleted from every row as it is read; nothing here sees it.
Writes wqp_blind_index.csv (site, org, lat, lon, date, time, bottom_visible, state) and pool_counts.json."""
import csv, json, math, collections
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
W = f"{S}/q9/wqp"
rows = []
with open(f"{W}/secchi.csv", newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        r.pop("secchi_m", None)
        rows.append(r)
cols = ["site_id", "org", "lat", "lon", "date", "time", "time_zone", "bottom_visible", "state", "site_name"]
with open(f"{S}/stage14/cert/wqp_blind_index.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
F = json.load(open(f"{S}/stage14/cert/dev_footprint.json"))
devids = set(F["site_ids"]); B = F["guntersville_box"]
KM = 5.0
def cell(la, lo): return (int(la / 0.05), int(lo / 0.05))
grid = collections.defaultdict(list)
for la, lo, tag in F["coords"]: grid[cell(la, lo)].append((la, lo, tag))
def near(la, lo, km=KM, tags=("dev", "blind")):
    ci, cj = cell(la, lo); best = None
    for di in range(-2, 3):
        for dj in range(-2, 3):
            for a, b, t in grid.get((ci + di, cj + dj), []):
                if t not in tags: continue
                d = 6371 * math.hypot(math.radians(a - la), math.radians(b - lo) * math.cos(math.radians(la)))
                if d <= km: return t
    return None
last = collections.defaultdict(str)
for r in rows: last[r["site_id"]] = max(last[r["site_id"]], r["date"])
site = {}
for r in rows: site.setdefault(r["site_id"], (float(r["lat"]), float(r["lon"]), r["state"], r["org"]))
reason = {}
for s, (la, lo, st, org) in site.items():
    if s in devids: reason[s] = "site in a development file"
    elif B[0] <= la <= B[2] and B[1] <= lo <= B[3]: reason[s] = "Guntersville box"
    elif last[s] >= "2026-01-01": reason[s] = "has a 2026 record (P2 fresh pool)"
    else:
        t = near(la, lo)
        reason[s] = {"dev": "within 5 km of a development station", "blind": "within 5 km of a Stage 12/13 blind-sample site"}.get(t, "eligible")
c = collections.Counter(reason.values())
el = [r for r in rows if reason[r["site_id"]] == "eligible" and "2018-01-01" <= r["date"] <= "2025-12-31"]
days = {(r["site_id"], r["date"]) for r in el}
cool = sum(1 for s, d in days if int(d[5:7]) in (10, 11, 12, 1, 2, 3, 4))
print(json.dumps({"rows_read": len(rows), "sites": len(site), "site_reasons": dict(c), "eligible_rows": len(el), "eligible_site_days": len(days),
                  "eligible_sites": len({s for s, _ in days}), "cool_site_days": cool,
                  "eligible_by_state_top": collections.Counter(site[s][2] for s, _ in days).most_common(15)}, indent=1))
json.dump({"site_reasons": dict(c), "eligible_site_days": len(days)}, open(f"{S}/stage14/cert/pool_counts.json", "w"))
