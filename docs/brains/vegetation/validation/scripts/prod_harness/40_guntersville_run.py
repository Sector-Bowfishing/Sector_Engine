"""Pilot, UNVALIDATED: Lake Guntersville AL, central/lower reach, Apr-Oct 2025. The REAL production reader (dws._read_s2_native) and the real
Earth Search query (dws.post / ES_SEARCH, collection sentinel-2-c1-l2a) are used; no stubs except per-scene diagnostics. Lake polygon = production
polygons.geojson.gz clipped to a bbox so the read stays under 1 GB."""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, gzip, datetime as dt, warnings, time, os
warnings.filterwarnings("ignore")
import prod_import as P
from shapely.geometry import shape, box
dws = P.dws
dws._read_s2_native = P.REAL_READ
os.environ.setdefault("AWS_REGION", "us-west-2")
H = "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness"
d = json.load(gzip.open(P.PROD + "/polygons.geojson.gz"))
lake = [shape(f["geometry"]) for f in d["features"] if f["properties"]["id"] == "Guntersville|AL"][0]
BB = (-86.30, 34.40, -86.00, 34.66)
lake = lake.intersection(box(*BB))
dws.UTM = "EPSG:32616"
fr = dws.Frame(lake, cell=50.0); m = dws.lake_masks(lake, fr)
print("frame", fr.width, fr.height, "lake cells", int(m["lake"].sum()), "clarity cells", int(m["clarity"].sum()), "ground cell m", round(fr.cell_ground_m(), 1))
body = {"collections": [dws.S2_COLLECTION], "bbox": list(BB), "datetime": "2025-04-01T00:00:00Z/2025-10-31T23:59:59Z", "limit": 200,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
feats = dws.post(dws.ES_SEARCH, body)["features"]
by = {}
for f in feats: by.setdefault((f["properties"]["datetime"][:10], f["properties"].get("platform", "")), []).append(f)
cands = [(k, v) for k, v in sorted(by.items()) if min(i["properties"].get("eo:cloud_cover", 0) for i in v) <= 30]
print(len(feats), "items,", len(by), "passes,", len(cands), "with cloud<=30")
FIELDS = ["read","grass_prod","gfrac","hidden","near","seen_share","nodata_share","cloudscl_share","gfrac_v1","dark_share","glare_share"]
S = len(cands); out = {f: np.zeros((S, fr.height, fr.width), "float32" if f not in ("read","grass_prod") else bool) for f in FIELDS}
ok = np.zeros(S, bool); rej = [""] * S; ids = []; t0 = time.time()
for i, ((date, plat), items) in enumerate(cands):
    ids.append(items[0]["id"])
    P._DIAG["_cur"] = {}
    try:
        acc, grass, aux = dws.s2_pass(items, fr, m["lake"], m["clarity"])
    except dws.PassRejected as e:
        rej[i] = str(e); print(date, "REJECTED", e); continue
    except Exception as e:
        rej[i] = "ERR " + repr(e)[:150]; print(date, "ERR", e); continue
    p = P._DIAG["_cur"]["pix"]; g = lambda a: dws.to_grid(a, p["tr10"], p["crs"], fr)
    r = {"read": ~np.isnan(acc), "grass_prod": grass, "gfrac": aux["gfrac"], "hidden": aux["hidden"], "near": aux["near"], "seen_share": g(p["seen"]),
         "nodata_share": g(p["nodata"]), "cloudscl_share": g(p["cloudscl"]), "gfrac_v1": g(p["veg_valid"]), "dark_share": g(p["dark"]), "glare_share": g(p["glare"])}
    for f in FIELDS: out[f][i] = r[f]
    ok[i] = True
    print(date, items[0]["properties"].get("eo:cloud_cover"), "grass cells", int(grass.sum()), "%.0fs" % (time.time() - t0), flush=True)
np.savez_compressed(H + "/out/cells50_guntersville_central.npz", **out, ok=ok, rejected=np.array(rej), dates=np.array([k[0] for k, _ in cands]), ids=np.array(ids),
                    lake=m["lake"], clarity=m["clarity"], ground_m=fr.cell_ground_m(), cell=50.0, utm="EPSG:32616", survey="2025-07-15")
