"""Stage 21 (value-blind): tasks re-running every S2C scene the validation and the consensus re-run need, through the
identical frozen ACOLITE path, raw (K0) and with the frozen top-of-atmosphere offsets (K1), from Google Cloud (nominal
N0511/N0512 operational L1C). Crops are the scene's ORIGINAL crops (centre and lake elevation as recorded in its earlier
result file); points carry the original keys, coordinates from the source tables.
  dev   S2C development anchors (rows12; crops from stage12/corpus/res)
  cert  S2C certification rows (Stage 14 sample; crops from stage14/cert/res_ns, res_wqp)
  fresh S2C Stage 16 fresh rows (crops from stage16/fresh/res_fresh)
  nb    S2C prior passes of the Stage 19 neighbour sets (crops from stage17/scenes/res_nb, stage18p/res_nb18, stage19/res_nb19)
Writes tasks21_s2c.json (one K0 + one K1 run per L1C) and s2c21_index.json (key -> pool). No Secchi value is read."""
import json, os, glob, csv, collections
S = os.environ["CLARITY_RESEARCH_ROOT"]
need = collections.defaultdict(dict)          # l1c -> {(lat, lon, elev): {key: (plat, plon)}}
pool = {}


def add(resfiles, coords, poolname, want=None):
    for f in resfiles:
        r = json.load(open(f)); l1c = r.get("l1c") or ""
        if not l1c.startswith("S2C_"): continue
        for c in r.get("crops", []):
            pts = (c.get("points") or (c.get("raw") or {}).get("points") or {})
            for k in pts:
                if want is not None and k not in want: continue
                if k not in coords: continue
                ck = (c["lat"], c["lon"], c.get("elevation_m"))
                need[l1c].setdefault(ck, {})[k] = coords[k]; pool[k] = poolname


rows12 = {x["id"]: x for x in json.load(open(f"{S}/stage12/analysis/rows12.json"))}
add(glob.glob(f"{S}/stage12/corpus/res/*.json"), {k: (x["lat"], x["lon"]) for k, x in rows12.items() if x["platform"] == "sentinel-2c"}, "dev")
smp = list(csv.DictReader(open(f"{S}/stage13/cert/blind_sample13.csv"))) + list(csv.DictReader(open(f"{S}/stage14/cert/wqp_sample.csv")))
add(glob.glob(f"{S}/stage14/cert/res_ns/*.json") + glob.glob(f"{S}/stage14/cert/res_wqp/*.json"), {r["id"]: (float(r["lat"]), float(r["lon"])) for r in smp}, "cert")
fs = list(csv.DictReader(open(f"{S}/stage16/fresh/fresh_sample.csv")))
add(glob.glob(f"{S}/stage16/fresh/res_fresh/*.json"), {r["id"]: (float(r["lat"]), float(r["lon"])) for r in fs}, "fresh")
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
sel = json.load(open(f"{S}/stage19/neighbors19.json"))
nbk = {f"{cid}#{n['item']}": (corp[cid]["lat"], corp[cid]["lon"]) for cid, v in sel.items() for n in v if n["platform"] == "sentinel-2c"}
add(glob.glob(f"{S}/stage17/scenes/res_nb/*.json") + glob.glob(f"{S}/stage18p/res_nb18/*.json") + glob.glob(f"{S}/stage19/res_nb19/*.json"), nbk, "nb")
T = []
for l1c, cr in sorted(need.items()):
    crops = [{"lat": la, "lon": lo, "elev": el, "points": [[p[0], p[1], k] for k, p in pts.items()]} for (la, lo, el), pts in cr.items()]
    T += [{"run": f"K0_{l1c}", "l1c": l1c, "crops": crops}, {"run": f"K1_{l1c}", "l1c": l1c, "crops": crops, "toa_sub": True}]
json.dump(T, open(f"{S}/stage21/tasks21_s2c.json", "w")); json.dump(pool, open(f"{S}/stage21/s2c21_index.json", "w"))
c = collections.Counter(pool.values())
print("S2C L1C", len(need), "runs", len(T), "points by pool", dict(c), "baselines", collections.Counter(l.split("_")[3] for l in need))
