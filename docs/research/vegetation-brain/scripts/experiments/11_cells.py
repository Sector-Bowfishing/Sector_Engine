"""Per-lake Sector-style cell fields for every scene of a stack. Usage: 11_cells.py snoco|fwc [LakeName ...]
Writes out/cell_{tag}_{lake}.npz : G (S,h,w) cell gfrac, H (S,h,w) 'turbidity read' flag, truth fractions per label class, masks."""
import sys, json, glob, numpy as np, rasterio
from pathlib import Path
from shapely.geometry import shape
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import cell_lib as C
tag = sys.argv[1]; only = set(sys.argv[2:])
if tag == "snoco":
    short = {"Lake Serene":"Serene","Blackmans Lake":"Blackmans","Storm Lake":"Storm","Lake Roesiger":"Roesiger","Lake Bosworth":"Bosworth"}
    lakes = {short[f["properties"]["name"]]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/snoco_layer15.geojson"))["features"]}
else:
    ids = {"Orange":"288216","Griffin":"305765","Apopka":"293912","Harris":"294031","Panasoffkee":"294114","Yale":"306620","Cypress":"281219"}
    L = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
    lakes = {k: L[v] for k, v in ids.items()}
caches = {}
for f in glob.glob(str(ROOT/f"out/s2cache/{tag}_*.npz")):
    z = np.load(f, allow_pickle=True); caches.setdefault((z["B04"].shape, str(z["date"].item() if z["date"].shape == () else z["date"])), []).append(f)
for nm, geom in lakes.items():
    if only and nm not in only: continue
    sp = ROOT/f"out/stack_{tag}_{nm}.npz"
    if not sp.exists(): continue
    st = np.load(sp, allow_pickle=True); shp = st["lake"].shape; dates = [str(d) for d in st["dates"]]
    scenes = []
    for d in dates:
        fs = caches.get((shp, d), [])
        if len(fs) != 1:
            # ambiguous (two lakes with same grid shape+date): pick the one whose NDVI_sector matches the stack
            ok = None
            for f in fs:
                z = np.load(f, allow_pickle=True); ndv = (z["B8A"]-z["B04"])/np.maximum(1e-6, z["B8A"]+z["B04"])
                k = list(st["idx"]).index("NDVI_sector"); i = dates.index(d)
                if np.allclose(np.nan_to_num(ndv), np.nan_to_num(st["X"][i, k]), atol=1e-4): ok = f; break
            fs = [ok] if ok else []
        if not fs: print(nm, "no cache for", d); scenes.append(None); continue
        z = np.load(fs[0], allow_pickle=True)
        scenes.append({k: z[k] for k in ["B02","B03","B04","B8A","B11","SCL"]} | {"transform": rasterio.Affine(*z["transform"]), "crs": rasterio.crs.CRS.from_string(str(z["crs"]))})
    ref = next(s for s in scenes if s)
    fr = C.Frame(geom); m = C.lake_masks(geom, fr, ref["crs"])
    S = len(scenes); G = np.full((S, fr.height, fr.width), np.nan, "float32"); Hh = np.zeros((S, fr.height, fr.width), bool)
    for i, s in enumerate(scenes):
        if s is None: continue
        G[i], Hh[i] = C.scene_cells(s, fr, m["lake"])
    # sanity: validate port at pixel level against stack (NDVI_sector) done separately
    truth = {c[4:]: C.to_grid(st[c].astype("float32"), ref["transform"], ref["crs"], fr) for c in st.files if c.startswith("lab_")}
    out = ROOT/f"out/cell_{tag}_{nm}.npz"
    np.savez_compressed(out, G=G, H=Hh, dates=np.array(dates), clear=st["clear"], survey=str(st["survey"]), lake=m["lake"], clarity=m["clarity"],
                        ground_m=fr.ground_m(), **{"truth_"+k: v for k, v in truth.items()})
    print(nm, "frame", fr.width, "x", fr.height, "ground cell %.1f m" % fr.ground_m(), "lake cells", int(m["lake"].sum()), "clarity cells", int(m["clarity"].sum()),
          "scenes", S, "->", out.name, flush=True)
