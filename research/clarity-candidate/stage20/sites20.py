"""Stage 20 sites (value-blind): one open-water point per directory lake (its pole of inaccessibility on a 30 m grid, from
the lake-surface outlines, kept when >= 600 m from shore so a 60 m disk is clean), plus the Stage 11 large global water
bodies (their given open-water coordinates). No clarity value, Secchi or model output is used. Writes sites20.json."""
import gzip, json, sys, os, importlib.util
S = os.environ["CLARITY_RESEARCH_ROOT"]
spec = importlib.util.spec_from_file_location("bp", sys.argv[2]); bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
from shapely.geometry import shape
feats = json.load(gzip.open(sys.argv[1]))["features"]
sites = []
for f in feats:
    try:
        pts, pole = bp.outline_points(shape(f["geometry"]))
    except Exception:
        continue
    if pole and pole >= 600: sites.append({"site": "L:" + f["properties"]["id"], "lat": pts[0][0], "lon": pts[0][1], "shore_m": round(pole)})
G = {}
src = open(f"{S}/../../../../iOS/Sector/.claude/none").read() if False else None
exec(open(sys.argv[3]).read().split("def post")[0], G)          # Stage 11 PTS dict
for name, (la, lo) in G["PTS"].items(): sites.append({"site": "G:" + name, "lat": la, "lon": lo, "shore_m": None})
json.dump(sites, open(f"{S}/stage20/sites20.json", "w"), indent=0)
print(len(sites), "sites;", sum(1 for s in sites if s["site"].startswith("L:")), "directory lakes")
