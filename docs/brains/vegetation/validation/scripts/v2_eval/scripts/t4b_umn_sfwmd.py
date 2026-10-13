"""TEST supplementary: UMN points (recall) and SFWMD littoral polygons (cells) from the EXISTING note-09/10 caches, with the FROZEN pair. NOT_RUN where no cache exists.
Scene years are labelled substitutes except UMN tier E (exact year). No network."""
from v2jobs import *
import csv, pickle, collections
install_guard()
fz = load_frozen(); PAIR = (fz["haze_swir"], fz["haze_standoff_px"])
UMN = ADOPT / "umn_sfwmd"
sys.path.insert(0, str(UMN / "scripts"))
from lakes_cfg import FL_CFG, scene_years, shift       # read-only helpers (date arithmetic)
WM = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
def geom(lk):
    g = json.load(open(UMN / f"out/geom/{lk}.geojson")); return shape(g["features"][0]["geometry"] if "features" in g else g.get("geometry", g))
def load_scenes(lk):
    fs = sorted((UMN / "out/s2cache").glob(f"{lk}_20*.npz"))
    groups = collections.defaultdict(list)
    for f in fs:
        z = np.load(f, allow_pickle=True); groups[(str(z["crs"]), tuple(np.round(z["transform"], 3)), z["SCL"].shape)].append(f)
    if not groups: return None
    key = max(groups, key=lambda k: len(groups[k]))
    dropped = sum(len(v) for k, v in groups.items() if k != key)
    z0 = np.load(groups[key][0], allow_pickle=True); crs = rasterio.crs.CRS.from_string(str(z0["crs"])); tr = rasterio.Affine(*z0["transform"]); shp = z0["SCL"].shape
    lake = rasterize_lake(geom(lk), crs, tr, shp)
    scenes = []; diags = []
    for f in groups[key]:
        z = np.load(f, allow_pickle=True); off = float(z["off"]); c = "sentinel-2-c1-l2a" if off != 0.0 else "sentinel-2-l2a"
        sc, dg = make_scene2(f.stem, d2(str(z["date"])), c, z["B04"], z["B8A"], z["B11"], z["SCL"], lake, *PAIR)
        scenes.append(sc); diags.append(dg)
    return dict(scenes=scenes, diags=diags, crs=crs, tr=tr, shape=shp, lake=lake, dropped_other_grid=dropped, coll=sorted({s.collection for s in scenes}))
def rc(S, lon, lat):
    t = pyproj.Transformer.from_crs("EPSG:4326", S["crs"], always_xy=True).transform
    x, y = t(lon, lat); col = (x - S["tr"].c) / 10.0; row = (S["tr"].f - y) / 10.0
    return int(np.floor(row)), int(np.floor(col))
out = dict(pair=PAIR, umn={}, sfwmd={}, notrun=[])
# ---- UMN points ------------------------------------------------------------------------------------------------------------------
pts = list(csv.DictReader(open(UMN / "out/umn_fleet_points.csv")))
LAKES_UMN = ["Lake_Minnetonka_MN", "Mille_Lacs_Lake_MN", "Lake_Winnibigoshish_MN", "Gull_Lake_MN"]
for lk in LAKES_UMN:
    S = load_scenes(lk)
    if S is None: out["notrun"].append(lk); continue
    obs_cache = {}
    res = []
    for p in [p for p in pts if p["lake"] == lk and (p["strict"] == "1" or p["incl"] == "1" or p["noveg"] in ("TRUE", "True", "1"))]:
        r, c = rc(S, float(p["lon"]), float(p["lat"])); y0 = int(p["date"][:4])
        for sy, tier in scene_years(y0):
            ref = d2(shift(p["date"], sy))
            for m in "SAP":
                k = (ref, m)
                if k not in obs_cache: obs_cache[k] = O.observe(S["scenes"], ref, mode=m)
                o = obs_cache[k]
                nr, nc = (o.state.shape if o.state is not None else (S["shape"][0] // 5, S["shape"][1] // 5))
                inside = 0 <= r // 5 < nr and 0 <= c // 5 < nc
                st = int(o.state[r // 5, c // 5]) if (o.state is not None and inside) else None
                itr = bool(o.cells.interior[r // 5, c // 5]) if (o.cells is not None and inside) else False
                res.append(dict(lake=lk, survey=p["survey"], date=p["date"], sy=sy, tier=tier, obs=m, strict=p["strict"], incl=p["incl"], noveg=p["noveg"], state=st, interior=itr, kind=o.evidence_kind, persistence=o.persistence,
                                gap=(abs((o.observed_on - ref).days) if o.observed_on else None), n_acc=o.n_accepted))
    out["umn"][lk] = dict(rows=res, n_scenes=len(S["scenes"]), dropped_other_grid=S["dropped_other_grid"], coll=S["coll"], diags=S["diags"])
# ---- SFWMD polygons --------------------------------------------------------------------------------------------------------------
sys.path.insert(0, str(UMN / "scripts"))
OKE_FLOAT = {'MFF', 'MFFe', 'MFFh', 'MFFli'}; OKE_CAT = {'MFGtD', 'MFGtM', 'MFGtS', 'MFGtDT'}
OKE_HERB = {'MFGe', 'MFH', 'MFG', 'MFGc', 'MFGh', 'MFGhT', 'MFB', 'MFBt', 'MFBp', 'MFBs', 'MFHp', 'MFGr', 'MFGsc', 'MFGs', 'MFGa', 'MFGpa', 'MSGs', 'EpD', 'EpDT', 'EG', 'Eo', 'Eal'}
OKE_WOODY = {'CSs', 'SS', 'SSm', 'SSa', 'SSl', 'SSc', 'SSb', 'SSh', 'Ssam', 'CSsH', 'CSsE', 'FS', 'EsD', 'TV'}
def oke_group(p):
    c = p.get('VEGLABEL1_CODE')
    if c == 'OW': return 'OW'
    if c in OKE_FLOAT: return 'FLOAT'
    if c in OKE_CAT: return 'CATTAIL'
    if c in OKE_HERB: return 'HERB'
    if c in OKE_WOODY: return 'WOODY'
    if c == 'SAV': return 'SAV'
    return 'OTHER'
KC_FLOAT = {'6440', '6442', '6445'}; KC_EMERG = {'6410', '6412', '6414', '6420', '6421', '6423', '6424'}; KC_WOODY = {'6181', '6301', '6417', '1000'}
def kc_group(p):
    c = str(p.get('FLUCCS_CODE')).split('-')[0].strip()
    if c == '5200': return 'OW'
    if c in KC_FLOAT: return 'FLOAT'
    if c == '6412': return 'CATTAIL'
    if c in KC_EMERG: return 'HERB'
    if c in KC_WOODY: return 'WOODY'
    if c == '6450': return 'SAV'
    return 'OTHER'
GROUPS = ['OW', 'FLOAT', 'CATTAIL', 'HERB', 'WOODY', 'SAV', 'OTHER']
CFG = {'Okeechobee_FL': dict(files=['VEG_OKE_2015', 'VEG_OKE_2016'], grp=oke_group), 'Kissimmee_FL': dict(files=['VEG_KCOL_2015'], grp=kc_group), 'Tohopekaliga_Toho_FL': dict(files=['VEG_KCOL_2016'], grp=kc_group)}
import gzip
def sf_path(x):
    for suf in (".geojson", ".geojson.gz"):
        p = UMN / f"out/sfwmd/{x}{suf}"
        if p.exists(): return p
    return None
def sf_load(x):
    p = sf_path(x); b = p.read_bytes()
    return json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)
for lk, cfg in CFG.items():
    S = load_scenes(lk)
    if S is None or not all(sf_path(x) is not None for x in cfg["files"]): out["notrun"].append(lk); continue
    H, W = S["shape"]; tf = pyproj.Transformer.from_crs("EPSG:4326", S["crs"], always_xy=True).transform
    shapes = []
    for fn in cfg["files"]:
        d = sf_load(fn)
        feats = [f for f in d["features"] if (lk != 'Tohopekaliga_Toho_FL' or f["properties"].get('AREA_NAME') == 'LAKE TOHOPEKALIGA')]
        for f in feats:
            g = f["geometry"]
            if not g: continue
            shapes.append((shp_t(tf, shape(g)), 1 + GROUPS.index(cfg["grp"](f["properties"]))))
    lab = rasterize(shapes, out_shape=(H, W), transform=S["tr"], fill=0, dtype="uint8")
    fr = {gn: block_mean((lab == i + 1).astype("float32")) for i, gn in enumerate(GROUPS)}; fr["mapped"] = block_mean((lab > 0).astype("float32"))
    dist = cell_center_dist(dist_to_edge_m(S["lake"]))
    base = S["scenes"][0].cells
    pos = ((fr["FLOAT"] + fr["CATTAIL"] + fr["HERB"]) >= 0.5) & base.eligible
    neg = (fr["OW"] >= 0.9) & base.interior
    ref0 = FL_CFG[lk]["refs"][0]; recs = {}
    for sy in FL_CFG[lk]["years"]:
        ref = d2(shift(ref0, sy))
        for m in "SAP":
            o = O.observe(S["scenes"], ref, mode=m); sel = sel_record(S["scenes"], ref)
            st = o.state
            if st is None: fl = np.zeros(pos.shape, bool); kn = fl
            else: fl = st == O.PLANT; kn = (st != O.UNKNOWN) & (st != O.OUTSIDE)
            it = base.interior
            sub = {"ALL": pos, "FLOAT": (fr["FLOAT"] >= 0.5) & base.eligible, "CATTAIL": (fr["CATTAIL"] >= 0.5) & base.eligible}
            r = dict(kind=o.evidence_kind, persistence=o.persistence, n_acc=o.n_accepted, gap=(abs((o.observed_on - ref).days) if o.observed_on else None), n_inwin=sel["n_inwindow"], n_accepted_scenes=sel["n_accepted"],
                     pos_whole=int(pos.sum()), pos_int=int((pos & it).sum()), tp_int=int((fl & pos & it).sum()), tp_whole=int((fl & pos).sum()), known_pos_int=int((kn & pos & it).sum()),
                     fp=int((fl & neg).sum()), tn=int((~fl & kn & neg).sum()), neg_n=int(neg.sum()), neg_unknown=int((~kn & neg).sum()), shares=o.refusal_shares,
                     sub={k: dict(n_int=int((v & it).sum()), tp_int=int((fl & v & it).sum())) for k, v in sub.items()})
            recs[f"{sy}|{m}"] = r
    out["sfwmd"][lk] = dict(recs=recs, n_scenes=len(S["scenes"]), coll=S["coll"], diags=S["diags"], dropped_other_grid=S["dropped_other_grid"])
out["notrun"].append("UMR_Pool5: no S2 cache from note 09 (scenes were fetched live from STAC; the cache was not kept)")
pickle.dump(out, open(OUT2 / "test_umn_sfwmd.pkl", "wb"))
print({k: list(v) for k, v in out.items() if k != "pair"}, out["notrun"])
