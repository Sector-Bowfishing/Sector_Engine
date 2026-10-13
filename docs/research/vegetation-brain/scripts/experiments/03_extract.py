"""Build per-lake pixel stacks: S2 index stack for all clear scenes within +-WIN days of the survey,
plus ground-truth label rasters on the same 10 m grid. Usage: 03_extract.py snoco|fwc"""
import sys, json, datetime as dt, numpy as np, rasterio, collections
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import s2lib
from rasterio.features import rasterize
from shapely.geometry import shape, Point, box, mapping
from shapely.ops import unary_union
from scipy.ndimage import distance_transform_edt
ROOT = s2lib.ROOT; WIN = 45

def build(name, lake_ll, survey_date, classes_ll, tag, max_clouds=0.25, extra=None, touched=False, outside=False, pad_ll=None):
    """classes_ll: {class: [shapely geoms in lon/lat]}. returns saved path"""
    b = (pad_ll or lake_ll).bounds; m = 0.002
    bbox = (b[0]-m, b[1]-m, b[2]+m, b[3]+m)
    d0 = (survey_date - dt.timedelta(days=WIN)).isoformat(); d1 = (survey_date + dt.timedelta(days=WIN)).isoformat()
    items = s2lib.dedupe_by_date(s2lib.search(bbox, d0, d1, 70))
    scenes = []
    for it in items:
        try: scenes.append(s2lib.read_scene(it, bbox, tag))
        except Exception as e: print("  read fail", it.id, e)
    if not scenes: print("no scenes", name); return None
    tr, crs = scenes[0]["transform"], scenes[0]["crs"]
    shp = scenes[0]["B04"].shape
    # all scenes in one UTM tile? (different tiles/orbits can differ) -> keep only those matching grid
    scenes = [s for s in scenes if s["transform"] == tr and s["B04"].shape == shp]
    proj = s2lib.grid_helpers(tr, crs, shp)
    lake = proj(lake_ll).buffer(-10)
    ras = lambda geoms: rasterize([(g, 1) for g in geoms if not g.is_empty], out_shape=shp, transform=tr, fill=0, dtype="uint8", all_touched=touched).astype(bool) if geoms else np.zeros(shp, bool)
    lake_m = ras([lake])
    labels = {c: ras([proj(g) for g in gs]) & (True if outside else lake_m) for c, gs in classes_ll.items()}
    anyveg = np.zeros(shp, bool)
    for v in labels.values(): anyveg |= v
    # dilated "surveyed polygon" exclusion zone handled in analysis; distance to shore (m)
    inside = rasterize([(proj(lake_ll), 1)], out_shape=shp, transform=tr, fill=0, dtype="uint8").astype(bool)
    dist = distance_transform_edt(inside) * 10.0
    dlab = distance_transform_edt(~anyveg) * 10.0 if anyveg.any() else np.full(shp, 9999.0)
    X, V = s2lib.stack_scenes(scenes)
    # clear fraction inside lake
    lake_pix = lake_m.sum()
    clear = np.array([(V[i] & lake_m).sum() / max(1, lake_pix) for i in range(len(scenes))])
    dates = np.array([s["date"] for s in scenes])
    out = ROOT / "out" / f"stack_{tag}_{name.replace(' ','_')}.npz"
    np.savez_compressed(out, X=X, V=V, dates=dates, clear=clear, lake=lake_m, dist=dist.astype("float32"), dlab=dlab.astype("float32"),
                        survey=survey_date.isoformat(), idx=np.array(s2lib.IDX_ORDER),
                        **{"lab_"+c: v for c, v in labels.items()}, **(extra or {}))
    print(name, "scenes", len(scenes), "lake px", lake_pix, {c: int(v.sum()) for c, v in labels.items()}, "clear>", (clear >= (1-max_clouds)).sum(), "->", out.name, flush=True)
    return out

def fwc():
    import lifeform
    sys.path.insert(0, str(ROOT/"scripts"))
    pts = json.load(open(ROOT/"data/fwc_ltm_point_intercepts.json"))
    lk = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
    def pdate(s):
        try: return dt.datetime.strptime(s.split()[0], "%m/%d/%Y").date()
        except Exception: return None
    targets = [("288216","Orange",2022),("305765","Griffin",2019),("293912","Apopka",2021),("294031","Harris",2018),
               ("294114","Panasoffkee",2022),("306620","Yale",2023),("281219","Cypress",2022)]
    for lid, nm, yr in targets:
        P = [x for x in pts if x["Lake_Id"] == lid and pdate(x["Date"] or "") and pdate(x["Date"]).year == yr and x["Latitude"]]
        if not P or lid not in lk: print("skip", nm); continue
        ds = sorted(pdate(x["Date"]) for x in P); med = ds[len(ds)//2]
        cl = collections.defaultdict(list)
        for x in P:
            cl[lifeform.point_class(x["Species"])].append(Point(x["Longitude"], x["Latitude"]).buffer(0.00003))
        allpts = unary_union([Point(x["Longitude"], x["Latitude"]) for x in P])
        pad = unary_union([lk[lid], allpts.convex_hull])
        build(nm, lk[lid], med, cl, "fwc", touched=True, outside=True, pad_ll=pad, extra={"n_points": len(P), "survey_min": ds[0].isoformat(), "survey_max": ds[-1].isoformat()})

def snoco():
    L = lambda i: json.load(open(ROOT/f"data/snoco_layer{i}.geojson"))["features"]
    lakes = {f["properties"]["name"]: shape(f["geometry"]) for f in L(15)}
    short = {"Lake Serene":"Serene","Blackmans Lake":"Blackmans","Storm Lake":"Storm","Lake Roesiger":"Roesiger","Lake Bosworth":"Bosworth"}
    classes = {"floating_leaf":[6,7,8], "submerged_assemblage":[9,10,11,12,13], "arrowhead":[14]}
    for full, geom in lakes.items():
        sn = short[full]
        cl = collections.defaultdict(list); dates = []
        for c, layers in classes.items():
            for i in layers:
                for f in L(i):
                    if f["properties"].get("lake_name") == sn and f["geometry"]:
                        cl[c].append(shape(f["geometry"]).buffer(0))
                        if f["properties"].get("date_surveyed"): dates.append(f["properties"]["date_surveyed"])
        for f in L(0):  # milfoil points -> 10 m buffered, submerged
            if f["properties"].get("lake_name") == sn and f["geometry"]:
                cl["submerged_assemblage"].append(shape(f["geometry"]).buffer(0.0001))
        if not dates: continue
        d = dt.datetime.fromtimestamp(float(np.median(dates))/1000).date()
        build(sn, geom, d, cl, "snoco")

if __name__ == "__main__":
    {"snoco": snoco, "fwc": fwc}[sys.argv[1]]()
