"""Stage 10: pick the Guntersville survey targets from the frozen models' disagreements (imagery only).
Persistence: a block must be read on >= 3 of the 5 recent passes, and a category must hold on >= 2 of them.
Every target is >= 60 m from shore, >= 1.5 km from any other target, and >= 1 km from either dam.
Outputs: targets.csv / .gpx / .kml, targets_map.png, boat_card.md. The boat card carries NO model numbers
(so the reader is not anchored); the analyst table does."""
import csv, json, math, os, sys, collections, hashlib
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont

S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage10/frozen")
import regions
D = f"{S}/stage10/survey"
DATES = ["2026-09-13", "2026-09-15", "2026-09-17", "2026-09-20", "2026-09-28"]
PLAT = {"2026-09-13": "S2B", "2026-09-15": "S2C", "2026-09-17": "S2A", "2026-09-20": "S2B", "2026-09-28": "S2C"}
DAMS = [(34.4236, -86.3931, "Guntersville Dam"), (35.0036, -85.6197, "Nickajack Dam")]
num = lambda x: None if x in ("", "None", None) else float(x)
cl = lambda ft: None if ft is None else (0 if ft >= 6 else 1 if ft >= 3 else 2 if ft >= 2 else 3)


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return 6371 * 2 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


blocks = collections.defaultdict(list)
for d in DATES:
    for r in csv.DictReader(open(f"{D}/blocks_{d}.csv")):
        blocks[(int(r["br"]), int(r["bc"]))].append({**r, "date": d})
interior = ndimage.distance_transform_edt(regions.LAKE) * regions.CELL_M
P = np.load(os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/docs/data/hydrology/guntersville/stage3a/arm_positions.npz"))
dhead = P["dHeadM"]

agg = []
for (br, bc), rs in blocks.items():
    if len(rs) < 3:
        continue
    r0, c0 = br * 3 + 1, bc * 3 + 1
    if interior[r0, c0] < 60:
        continue
    lat, lon = float(rs[0]["lat"]), float(rs[0]["lon"])
    if any(km((lat, lon), (a, b)) < 1.0 for a, b, _ in DAMS):
        continue
    p1 = [num(r["P1"]) for r in rs]; c3 = [num(r["C3"]) for r in rs]; ch = [num(r["C0"]) for r in rs]; nd = [num(r["ndci"]) for r in rs]
    pairs = [(a, b) for a, b in zip(p1, c3) if a is not None and b is not None]
    x = {"br": br, "bc": bc, "lat": lat, "lon": lon, "kind": rs[0]["kind"], "arm": rs[0]["arm"] or None, "zoneName": rs[0]["zoneName"] or None,
         "nScenes": len(rs), "interiorM": float(interior[r0, c0]), "dHeadM": float(dhead[r0, c0]),
         "P1med": float(np.median([a for a in p1 if a is not None])) if any(a is not None for a in p1) else None,
         "C3med": float(np.median([b for b in c3 if b is not None])) if any(b is not None for b in c3) else None,
         "C0med": float(np.median([v for v in ch if v is not None])) if any(v is not None for v in ch) else None,
         "ndciMed": float(np.median(nd)), "ndciLatest": num(next((r["ndci"] for r in rs if r["date"] == "2026-09-28"), None)),
         "algalN": sum(v > 0.03 for v in nd),
         "p1stained_c3normal": sum(1 for a, b in pairs if 2 <= a < 3 and b >= 3.5),
         "c3clear_p1murky": sum(1 for a, b in pairs if b >= 6 and a < 4),
         "agreeN": sum(1 for a, b in pairs if cl(a) == cl(b)),
         "limitedN": sum(1 for a, v in zip(p1, ch) if (a is not None and a < 2) or (v is not None and v < 2)),
         "paths": dict(collections.Counter(r["P2path"] for r in rs)),
         "byPlatform": {PLAT[r["date"]]: r["P2path"] for r in rs}}
    agg.append(x)
print("candidate blocks", len(agg))

picked = []


def far(x, gap=1.5):
    return all(km((x["lat"], x["lon"]), (p["lat"], p["lon"])) >= gap for p in picked)


def take(cat, cands, n, score, why, priority):
    got = 0
    for x in sorted(cands, key=score, reverse=True):
        if got >= n:
            break
        if far(x):
            picked.append({**x, "category": cat, "why": why(x), "priority": priority}); got += 1
    print(cat, got, "of", n, "from", len(cands))


# fixed: the historical agency stations (continuity with the ADEM/TVA record)
STATIONS = {"GUNM-8 (Short Creek)": (34.364539, -86.216931, "stained arm"), "GUNM-10 (Browns Creek)": (34.34464, -86.33057, "stained arm"),
            "Browns Creek (AWW)": (34.33208, -86.3445, "stained arm"), "GUNM-7 (Town Creek)": (34.405817, -86.183175, "stained arm"),
            "GUNM-7B (Town Creek, upper)": (34.43286, -86.15564, "stained arm"), "GUNM-9 (Big Spring Creek)": (34.3452, -86.29182, "stained arm"),
            "South Sauty Creek (AWW)": (34.46567, -86.09133, "stained arm"), "GUNM-4 (Dry Creek / Roseberry)": (34.63231, -86.01811, "stained arm"),
            "TENR-375 (main channel, mid-lake)": (34.552306, -86.121611, "clear main channel"),
            "TENR-399 (main channel, upper lake)": (34.7872, -85.84777, "clear main channel"),
            "TENR-406 (main channel, upper lake)": (34.86186, -85.7708, "clear main channel"),
            "TENR-417 (main channel, below Nickajack)": (35.00422, -85.69738, "clear main channel")}
for name, (la, lo, cat) in STATIONS.items():
    w = regions.where(la, lo)
    picked.append({"lat": la, "lon": lo, "kind": w["kind"], "arm": w["arm"], "zoneName": w["zoneName"], "category": ("known stained arm (agency station)" if cat == "stained arm" else "clear main channel (agency station)"),
                   "why": "historical agency station: " + name, "priority": "A", "station": name})

take("P1 says stained, C3 says normal/clear", [x for x in agg if x["p1stained_c3normal"] >= 2], 6,
     lambda x: x["p1stained_c3normal"] * (x["C3med"] - x["P1med"]), lambda x: f"{x['p1stained_c3normal']} of {x['nScenes']} passes", "A")
take("C3 says clear, P1 says murky", [x for x in agg if x["c3clear_p1murky"] >= 2], 5,
     lambda x: x["c3clear_p1murky"] * (x["C3med"] - x["P1med"]), lambda x: f"{x['c3clear_p1murky']} of {x['nScenes']} passes", "A")
take("active algal warning (NDCI > 0.03)", [x for x in agg if x["algalN"] >= 2 and (x["ndciLatest"] or 0) > 0.03], 4,
     lambda x: x["ndciMed"], lambda x: f"NDCI > 0.03 on {x['algalN']} of {x['nScenes']} passes", "A")
take("likely under 2 ft", [x for x in agg if x["limitedN"] >= 2], 4,
     lambda x: -min(v for v in (x["P1med"], x["C0med"]) if v is not None), lambda x: f"a model reads < 2 ft on {x['limitedN']} of {x['nScenes']} passes", "A")
take("clear main channel (open water)", [x for x in agg if x["kind"] == "mainStem" and (x["C3med"] or 0) >= 6 and x["interiorM"] >= 250], 3,
     lambda x: x["C3med"], lambda x: "open main channel", "B")
# sediment after runoff: one block near the head of each of the largest arms (conditional on rain)
arm_size = collections.Counter(regions.NAMES[a] for a in regions.ARM[regions.LAKE] if a > 0)
big = [a for a, _ in arm_size.most_common(12)]
heads = []
for a in big:
    c = [x for x in agg if x["arm"] == a and x["dHeadM"] <= 1500 and x["interiorM"] >= 60]
    if c:
        heads.append(min(c, key=lambda x: x["dHeadM"]))
take("sediment after runoff (conditional)", heads, 5, lambda x: arm_size[x["arm"]], lambda x: "creek head of a large arm; only after >= 1 in of rain in 48 h", "B")
take("agreement / control", [x for x in agg if x["agreeN"] >= 2 and x["kind"] == "arm"], 2, lambda x: x["agreeN"], lambda x: f"P1 and C3 give the same class on {x['agreeN']} passes", "C")
take("agreement / control", [x for x in agg if x["agreeN"] >= 2 and x["kind"] == "mainStem"], 2, lambda x: x["agreeN"], lambda x: f"P1 and C3 give the same class on {x['agreeN']} passes", "C")

def pretty(arm):
    if not arm:
        return ""
    for county in ("jackson", "marshall"):
        if f"-{county}" in arm:
            base, rest = arm.split(f"-{county}", 1)
            tail = rest.strip("-").replace("into-", "into ").replace("-", " ")
            return base.replace("-", " ").title() + f" ({county.title()} Co." + (f", {tail}" if tail.startswith("into") else "") + ")"
    return arm.replace("-", " ").title()


# order down the lake (south-west to north-east) and number
ax = lambda p: (p["lat"] - 34.33) * 1.0 + (p["lon"] + 86.39) * 0.8
picked.sort(key=ax)
for i, p in enumerate(picked, 1):
    p["id"] = f"G{i:02d}"
    p["section"] = "Lower lake (dam to Honeycomb/Town Creek)" if ax(p) < 0.33 else "Middle lake (Town Creek to Scottsboro)" if ax(p) < 0.85 else "Upper lake (Scottsboro to Nickajack)"
    p["name"] = p.get("station") or (pretty(p["arm"]) + (f", {p['zoneName'].split(' ', 1)[1]}" if p.get("zoneName") and ' ' in p["zoneName"] else "") if p["kind"] == "arm" else "Main channel")
    p["maps"] = f"https://maps.apple.com/?ll={p['lat']:.5f},{p['lon']:.5f}&q={p['id']}"
cols = ["id", "section", "priority", "category", "name", "lat", "lon", "kind", "arm", "why", "P1med", "C3med", "C0med", "ndciMed", "nScenes", "byPlatform", "maps"]
with open(f"{D}/targets_analyst.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
    for p in picked:
        w.writerow({**p, **{k: (round(p[k], 2) if isinstance(p.get(k), float) else p.get(k)) for k in ("P1med", "C3med", "C0med", "ndciMed")},
                    "lat": f"{p['lat']:.5f}", "lon": f"{p['lon']:.5f}"})
boat_cols = ["id", "section", "priority", "category", "name", "lat", "lon", "maps"]
with open(f"{D}/targets_boat.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=boat_cols, extrasaction="ignore"); w.writeheader()
    for p in picked:
        w.writerow({**p, "lat": f"{p['lat']:.5f}", "lon": f"{p['lon']:.5f}"})
esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
with open(f"{D}/guntersville_clarity_targets.gpx", "w") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Sector Current Clarity survey" xmlns="http://www.topografix.com/GPX/1/1">\n')
    for p in picked:
        fh.write(f'  <wpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}"><name>{p["id"]}</name><desc>{esc(p["category"] + " — " + p["name"])}</desc></wpt>\n')
    fh.write("</gpx>\n")
with open(f"{D}/guntersville_clarity_targets.kml", "w") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Guntersville Clarity Survey</name>\n')
    for p in picked:
        fh.write(f'<Placemark><name>{p["id"]}</name><description>{esc(p["category"] + " — " + p["name"] + " — priority " + p["priority"])}</description>'
                 f'<Point><coordinates>{p["lon"]:.6f},{p["lat"]:.6f},0</coordinates></Point></Placemark>\n')
    fh.write("</Document></kml>\n")
# map: lake mask downsampled, numbered dots
f = 2
lake = regions.LAKE[::f, ::f]
img = Image.new("RGB", (lake.shape[1], lake.shape[0]), (245, 244, 240))
px = np.array(img); px[lake] = (120, 170, 210); img = Image.fromarray(px)
dr = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 13)
except Exception:
    font = ImageFont.load_default()
colour = {"A": (200, 40, 40), "B": (230, 140, 20), "C": (40, 130, 60)}
xy = []
for p in picked:
    r, c = regions.cell(p["lat"], p["lon"]); xy.append((c / f, r / f))
for i, (p, (x, y)) in enumerate(zip(picked, xy)):
    dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=colour[p["priority"]], outline=(20, 20, 20))
    crowded = any(j < i and abs(x - x2) < 40 and abs(y - y2) < 16 for j, (x2, y2) in enumerate(xy))
    dr.text((x - 36, y - 8) if crowded else (x + 7, y - 8), p["id"], fill=(20, 20, 20), font=font)
for la, lo, nm in DAMS:
    r, c = regions.cell(la, lo); dr.rectangle([c / f - 4, r / f - 4, c / f + 4, r / f + 4], fill=(40, 40, 40))
    dr.text((c / f - 8, r / f + 8) if "Guntersville" in nm else (c / f - 90, r / f + 8), nm, fill=(40, 40, 40), font=font)
leg = [("A  first priority", "A"), ("B  second priority / conditional", "B"), ("C  control", "C")]
dr.text((20, 20), "Guntersville Clarity Survey targets (north up)", fill=(20, 20, 20), font=font)
for k, (t, pr) in enumerate(leg):
    dr.ellipse([20, 44 + 20 * k, 30, 54 + 20 * k], fill=colour[pr], outline=(20, 20, 20)); dr.text((38, 42 + 20 * k), t, fill=(20, 20, 20), font=font)
img.save(f"{D}/targets_map.png")
json.dump(picked, open(f"{D}/targets.json", "w"), indent=1, default=str)
h = hashlib.sha256(open(f"{D}/targets_boat.csv", "rb").read()).hexdigest()
print("targets", len(picked), collections.Counter(p["category"] for p in picked), "sha256", h)
