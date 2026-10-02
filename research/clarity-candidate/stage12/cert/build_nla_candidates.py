"""Certification protocol sections 2-3, NLA part (blind: no Secchi file is read). Builds the NLA 2022 + 2017 index-site
visits, drops visits (a) in lakes whose index site is within 5 km of any development-corpus station or AERONET-OC site,
or Guntersville; (b) duplicated in the Stage 1 WQP pull (a site within 100 m, same date; only the pull's coordinates and
dates are read); (c) dated after 2025-12-31. Writes nla_candidates.csv in the extractor's format."""
import csv, json, math, collections
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
import datetime as _dt
def iso(d):
    d = d.strip()
    for fmt in ("%d-%b-%y", "%m/%d/%Y", "%Y-%m-%d"):
        try: return _dt.datetime.strptime(d, fmt).date().isoformat()
        except ValueError: pass
    for sep in ("/", "-"):
        if sep in d:
            a = d.split(sep)
            if len(a[0]) == 4: return f"{a[0]}-{int(a[1]):02d}-{int(a[2][:2]):02d}"
            return f"{a[2][:4]}-{int(a[0]):02d}-{int(a[1]):02d}"
    return None
vis = []
for r in csv.DictReader(open("nla22_siteinfo.csv", encoding="utf-8-sig", errors="replace")):
    if r.get("SITESAMP") not in ("Y", "YES") or not r.get("INDEX_LAT_DD") or not r.get("DATE_COL"): continue
    vis.append({"src": "NLA22", "site": r["SITE_ID"], "lake": r.get("UNIQUE_ID") or r["SITE_ID"], "visit": r.get("VISIT_NO", "1"),
                "lat": float(r["INDEX_LAT_DD"]), "lon": float(r["INDEX_LON_DD"]), "date": iso(r["DATE_COL"]), "state": r.get("PSTL_CODE", "")})
info17 = {}
for r in csv.DictReader(open("nla17_siteinfo.csv", encoding="utf-8-sig", errors="replace")):
    info17.setdefault(r["SITE_ID"], r)
for r in csv.DictReader(open("nla17_index_visits.csv")):
    if not r.get("INDEX_LAT_DD") or not r.get("DATE_COL"): continue
    try: lat, lon = float(r["INDEX_LAT_DD"]), float(r["INDEX_LON_DD"])
    except ValueError: continue
    i = info17.get(r["SITE_ID"], {})
    vis.append({"src": "NLA17", "site": r["SITE_ID"], "lake": i.get("UNIQUE_ID") or r["SITE_ID"], "visit": r.get("VISIT_NO", "1"),
                "lat": lat, "lon": lon, "date": iso(r["DATE_COL"]), "state": r.get("STATE") or i.get("PSTL_CODE", "")})
n0 = len(vis)
def km(a, b, c, d):
    return 6371 * 2 * math.asin(math.sqrt(math.sin(math.radians(c - a) / 2) ** 2 + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(math.radians(d - b) / 2) ** 2))
dev = [(x["lat"], x["lon"]) for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))]
dev += [(j["lat"], j["lon"]) for j in json.load(open(f"{S}/stage11/ac/jobs_aeronet.json"))]
grid = collections.defaultdict(list)
for a, b in dev: grid[(int(a * 10), int(b * 10))].append((a, b))
def near_dev(a, b):
    ci, cj = int(a * 10), int(b * 10)
    return any(km(a, b, p, q) <= 5 for i in range(ci - 1, ci + 2) for j in range(cj - 1, cj + 2) for p, q in grid[(i, j)])
gunt = lambda a, b: 34.27 <= a <= 35.06 and -86.42 <= b <= -85.60
# WQP pull: coordinates and dates only
wq = collections.defaultdict(list)
with open(f"{S}/q9/wqp/secchi.csv", newline="") as f:
    for r in csv.DictReader(f):
        try: wq[r["date"]].append((float(r["lat"]), float(r["lon"])))
        except (ValueError, KeyError): pass
drop = collections.Counter(); out = []
for v in vis:
    if not v["date"] or v["date"] > "2025-12-31": drop["date"] += 1; continue
    if near_dev(v["lat"], v["lon"]) or gunt(v["lat"], v["lon"]): drop["development lake"] += 1; continue
    if any(abs(p - v["lat"]) < 0.002 and abs(q - v["lon"]) < 0.002 and km(v["lat"], v["lon"], p, q) <= 0.1 for p, q in wq.get(v["date"], [])):
        drop["duplicate of a WQP-pull visit"] += 1; continue
    out.append(v)
# the lake-level development exclusion also applies to every other visit of an excluded lake
bad = {v["lake"] for v in vis if near_dev(v["lat"], v["lon"]) or gunt(v["lat"], v["lon"])}
out = [v for v in out if v["lake"] not in bad]
with open("nla_candidates.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "lat", "lon", "date", "set", "src", "lake", "state"]); w.writeheader()
    for v in out:
        w.writerow({"id": f"{v['src']}:{v['site']}:{v['visit']}", "lat": v["lat"], "lon": v["lon"], "date": v["date"], "set": v["src"],
                    "src": v["src"], "lake": v["lake"], "state": v["state"]})
print("visits", n0, "kept", len(out), dict(drop), "lakes", len({v['lake'] for v in out}), "states", len({v['state'] for v in out}),
      {s: sum(1 for v in out if v['src'] == s) for s in ("NLA22", "NLA17")})
