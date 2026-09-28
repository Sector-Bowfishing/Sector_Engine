"""Per-cell Sentinel-2 evidence for the Guntersville Water Clarity layer
(Clarity Fusion Stage 1, item 8). The shipped raster is NOT changed: this
reruns its build with taps (cell for cell identical, checked) and writes, for
every cell, what a future fusion needs -- FNU, the canonical visibility range,
observed or filled, the pass date, the through-water distance to a reading,
the specific exclusion or fill reason, and the cell's hydrologic arm.

Derived from the "36% measured" audit script.

Reruns the shipped build (the Sector-mapbox fishintel module, unchanged, the
same waterbody and --until) with taps on its intermediates:

  pixel level  every 10 m Sentinel-2 pixel of the chosen pass gets the FIRST
               gate it fails (a waterfall in the code's own order), counted
               per frame cell from the tile that weighs most in that cell;
  cell level   the lake's cells (the denominator) split into measured,
               read-then-dropped (specks, shadow, tiny patches, pockets),
               grass, and unread, each unread cell labelled by its dominant
               pixel reason;
  fill         the shipped measured.png codes and how far each estimate was
               carried from a reading.

usage: geo/bin/python audit_measured.py <out.json>
"""
import os, sys, json, collections, datetime as dt
FISHINTEL = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox/scripts/fishintel")
sys.path.insert(0, FISHINTEL)
import numpy as np
import pyproj
from PIL import Image
from scipy import ndimage
from shapely.geometry import shape
from shapely.ops import unary_union
import derive_water_surface as dws
import fill_lake

WATERBODY = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox/.fishintel-cache/guntersville/waterbody.geojson")
UNTIL = "2026-09-26"

REASONS = {
    0: "readable",
    1: "no scene data (swath edge / off tile)",
    2: "SCL defective / saturated",
    3: "SCL cloud (medium/high)",
    4: "SCL thin cirrus",
    5: "SCL cloud shadow",
    6: "SCL snow/ice",
    7: "SCL dark area (topographic/cast shadow)",
    8: "SCL vegetation (inside the outline)",
    9: "SCL not vegetated / bare (inside the outline)",
    10: "SCL unclassified",
    11: "within 60 m of SCL cloud/shadow/cirrus",
    12: "within 600 m of a real (>=1 ha) cloud",
    13: "haze at a cloud edge (SWIR16 > 0.012, offshore, <1.5 km from cloud)",
    14: "haze (SWIR16 > 0.02 patch, or > 0.010 within 400 m of one, offshore)",
    15: "within 100 m of bright water (hull / missed cloud)",
    16: "pixel touching an SCL bank pixel",
    17: "within 100 m of a bright non-vegetated structure",
    18: "SWIR16 > 0.0215 (glint / haze / land in the pixel)",
    19: "floating-algae index > 0.005 (plants at the surface)",
    20: "NDVI > 0.10 (plants at or near the surface)",
    21: "red reflectance <= 0 / invalid",
}

CALL = {"n": 0}
TILES = []          # per tile of the chosen pass: reason codes + geometry


def reason_codes(t):
    """The same arrays _s2_native_fields builds, and the first gate each
    pixel fails, in the code's order."""
    h, w = t["red"].shape
    up = lambda x: np.repeat(np.repeat(x, 2, axis=0), 2, axis=1)[:h, :w]
    def rho(dn):
        r = dn.astype("float32") * dws.S2_SCALE + dws.S2_OFFSET
        r[(dn == 0) | (dn == 65535)] = np.nan
        return r
    scl = up(t["scl"])
    r_red = rho(t["red"])
    r_nir, r_sw = up(rho(t["nir08"])), up(rho(t["swir16"]))
    water = scl == dws.SCL_WATER
    with np.errstate(invalid="ignore", divide="ignore"):
        fai = r_nir - (r_red + (r_sw - r_red) * (865 - 665) / (1610 - 665))
        ndvi = (r_nir - r_red) / np.maximum(1e-6, r_nir + r_red)
        bright = np.nan_to_num(r_sw, nan=0) > dws.BRIGHT_SWIR
        veg = ndvi >= dws.GRASS_NDVI_MIN
        haze_px = water & (r_sw > dws.HAZE_SWIR) & ~veg
    structure = bright & (np.nan_to_num(ndvi, nan=1.0) < dws.S2_STRUCTURE_NDVI_MAX) & ~water
    haze = bright & water
    bank = np.isin(scl, dws.S2_SCL_BANK)
    px = dws.S2_NATIVE_PX
    E = dws._edge_dist_px
    to_bank, to_structure = E(bank), E(structure)
    cloudy_classes = [c for c in dws.SCL_CLOUDY if c != 0]
    to_cloud = E(np.isin(scl, cloudy_classes))
    clear = to_cloud >= dws.S2_CLOUD_STANDOFF_M / px
    cl20 = np.isin(t["scl"], cloudy_classes)
    lab, n = ndimage.label(cl20)
    if n:
        sizes = ndimage.sum(cl20, lab, index=np.arange(1, n + 1))
        real20 = np.isin(lab, np.nonzero(sizes >= dws.S2_REAL_CLOUD_MIN_PX20)[0] + 1)
    else:
        real20 = cl20
    to_real = E(up(real20))
    near_cloud = to_real < dws.S2_CLOUD_EDGE_M / px
    under_cloud = to_real < dws.S2_REAL_CLOUD_STANDOFF_M / px
    offshore = ((to_bank >= dws.S2_CLOUD_EDGE_OFFSHORE_M / px)
                & (to_structure >= dws.S2_CLOUD_EDGE_OFFSHORE_M / px))
    with np.errstate(invalid="ignore"):
        cloud_edge = near_cloud & offshore & (r_sw > dws.S2_CLOUD_EDGE_SWIR)
        haze_edge = ((E(haze_px) < dws.HAZE_EDGE_M / px) & offshore & (r_sw > dws.HAZE_EDGE_SWIR))
    beside_bright = E(haze) < dws.S2_HAZE_STANDOFF_M / px
    code = np.zeros((h, w), "uint8")
    todo = np.ones((h, w), bool)
    def take(mask, c):
        m = todo & mask
        code[m] = c
        todo[m] = False
    take(scl == 0, 1)
    take(scl == 1, 2)
    take(np.isin(scl, (8, 9)), 3)
    take(scl == 10, 4)
    take(scl == 3, 5)
    take(scl == 11, 6)
    take(scl == 2, 7)
    take(scl == 4, 8)
    take(scl == 5, 9)
    take(scl == 7, 10)
    take(~clear, 11)
    take(under_cloud, 12)
    take(cloud_edge, 13)
    take(haze_edge, 14)
    take(beside_bright, 15)
    take(to_bank < dws.S2_BANK_STANDOFF_M / px, 16)
    take(to_structure < dws.S2_STRUCTURE_STANDOFF_M / px, 17)
    with np.errstate(invalid="ignore"):
        take(~(r_sw <= dws.SWIR_MAX), 18)
        take(~(fai <= dws.FAI_MAX), 19)
        take(~(ndvi <= dws.NDVI_MAX), 20)
        take(~(r_red > 0), 21)
    # Cross-check: what is left must be exactly the code's own `ok`.
    ok = water & clear & ~under_cloud & ~beside_bright & ~cloud_edge & ~haze_edge
    ok &= to_bank >= dws.S2_BANK_STANDOFF_M / px
    ok &= to_structure >= dws.S2_STRUCTURE_STANDOFF_M / px
    with np.errstate(invalid="ignore"):
        ok &= (r_sw <= dws.SWIR_MAX) & (fai <= dws.FAI_MAX) & (ndvi <= dws.NDVI_MAX) & (r_red > 0)
    assert (todo == ok).all(), "waterfall disagrees with the code's gate"
    near = near_cloud
    return code, near


_orig_fields = dws._s2_native_fields
def tapped_fields(t):
    if CALL["n"] == 1:      # the first s2_pass call is the chosen pass
        code, near = reason_codes(t)
        TILES.append({"code": code, "near": near, "tr10": t["tr10"], "tr20": t["tr20"],
                      "crs": t["crs"], "scl": t["scl"].copy()})
    return _orig_fields(t)
dws._s2_native_fields = tapped_fields

PASS = {}
_orig_pass = dws.s2_pass
def tapped_pass(items, frame, measurable, grass_mask):
    CALL["n"] += 1
    r = _orig_pass(items, frame, measurable, grass_mask)
    if CALL["n"] == 1:
        PASS.update(v=r[0].copy(), grass=r[1].copy(), aux=r[2], ids=[i["id"] for i in items])
    return r
dws.s2_pass = tapped_pass

FILL = {}
_orig_fill = fill_lake.fill_clarity
def tapped_fill(logv, lake, grass, **kw):
    FILL.update(logv=logv.copy(), grass=grass.copy())
    r = _orig_fill(logv, lake, grass, **kw)
    FILL.update(measured=r[1].copy(), dist=r[2]["dist_to_reading_m"].copy())
    return r
fill_lake.fill_clarity = tapped_fill
dws.fill_lake.fill_clarity = tapped_fill


def cell_index(tile, frame):
    """The frame cell (flat index, -1 off the frame) of every 10 m pixel."""
    h, w = tile["code"].shape
    tr = tile["tr10"]
    to_m = pyproj.Transformer.from_crs(tile["crs"], dws.WEB_MERCATOR, always_xy=True)
    cols = tr.c + (np.arange(w) + 0.5) * tr.a
    rows = tr.f + (np.arange(h) + 0.5) * tr.e
    out = np.full((h, w), -1, "int64")
    ft = frame.transform
    for r0 in range(0, h, 512):
        yy, xx = np.meshgrid(rows[r0:r0 + 512], cols, indexing="ij")
        X, Y = to_m.transform(xx, yy)
        fc = np.floor((X - ft.c) / ft.a).astype("int64")
        fr = np.floor((Y - ft.f) / ft.e).astype("int64")
        good = (fc >= 0) & (fc < frame.width) & (fr >= 0) & (fr < frame.height)
        out[r0:r0 + 512] = np.where(good, fr * frame.width + fc, -1)
    return out


def main():
    out_path = sys.argv[1]
    gj = json.load(open(WATERBODY))
    lake_geom = unary_union([shape(f["geometry"]) for f in gj["features"]])
    frame = dws.Frame(lake_geom, cell=dws.CLARITY_CELL)
    masks = dws.lake_masks(lake_geom, frame)
    tmp = os.path.join(os.path.dirname(out_path), "audit_gvl")
    os.makedirs(tmp, exist_ok=True)
    prefix = os.path.join(tmp, "Guntersville.clarity")
    dws.build_clarity(frame, masks, list(lake_geom.bounds), dt.datetime.fromisoformat(UNTIL), prefix)
    meta = json.load(open(prefix + ".json"))
    lake = masks["lake"]
    H, W = lake.shape
    N = int(lake.sum())
    v, pgrass, aux = PASS["v"], PASS["grass"], PASS["aux"]
    measured = FILL["measured"]
    source = np.asarray(Image.open(prefix + ".measured.png"))
    shipped = np.asarray(Image.open(os.path.expanduser(
        "~/Desktop/Development/iOS/Sector-mapbox/Sector/Assets.xcassets/FishIntel/"
        "GuntersvilleClarityMeasured.dataset/Guntersville.clarity.measured.png")))
    rep = {"pass": meta["pass"], "lakeCells": N, "measuredCells": int(measured.sum()),
           "measuredPct": meta["measuredPct"], "openWaterReadPct": meta["openWaterReadPct"],
           "shippedMeasuredCells": int((shipped == 255).sum()),
           "reproducesShipped": bool((shipped == source).all()),
           "cellsDifferingFromShipped": int((shipped != source).sum()),
           "cellGroundM": frame.cell_ground_m()}

    # ---- pixel reasons, per cell, from the tile weighing most in it
    wgts, idxs = [], []
    for t in TILES:
        foot = dws.to_grid(np.where(t["scl"] > 0, 1.0, np.nan).astype("float32"), t["tr20"], t["crs"], frame)
        inside = ~np.isnan(foot)
        wgts.append(np.clip(ndimage.distance_transform_edt(inside) * frame.cell / dws.TILE_FEATHER_M, 0, 1)
                    * inside)
        idxs.append(cell_index(t, frame))
    wstack = np.stack(wgts)
    primary = np.argmax(wstack, axis=0)
    no_tile = wstack.max(axis=0) <= 0
    K = 32
    counts = np.zeros((H * W, K), "int64")
    near_px = np.zeros(H * W, "int64")
    for k, (t, idx) in enumerate(zip(TILES, idxs)):
        use = (idx >= 0)
        use[use] = (primary.ravel()[idx[use]] == k)
        c = np.bincount(idx[use] * K + t["code"][use].astype("int64"), minlength=H * W * K)
        counts += c.reshape(H * W, K)
        near_px += np.bincount(idx[use], weights=t["near"][use].astype("float64"), minlength=H * W).astype("int64")
    counts = counts.reshape(H, W, K)
    lake_px = counts[lake]                               # (N, K)
    rep["pixels"] = {
        "lakePixels10m": int(lake_px.sum()),
        "byFirstFailedGate": {REASONS[r]: int(lake_px[:, r].sum()) for r in REASONS if lake_px[:, r].sum()},
    }

    # ---- cell waterfall
    read_pass = lake & ~np.isnan(v)
    logv0 = np.where(v > 0, np.log10(np.maximum(v, 0.05)), np.nan)
    dropped = read_pass & ~measured
    # the code's own drop steps, re-derived to split `dropped`
    local = dws.smooth_known(logv0.astype("float32"), 14)
    hot = ~np.isnan(logv0) & ((logv0 - local) > dws.SPECK_LOG10)
    lab, n = ndimage.label(hot)
    speck = np.zeros_like(hot)
    if n:
        sz = ndimage.sum(hot, lab, index=np.arange(1, n + 1))
        speck = np.isin(lab, np.nonzero(sz <= dws.SPECK_MAX_CELLS)[0] + 1)
    lv = np.where(speck, np.nan, logv0)
    nearc = np.nan_to_num(aux["near"]) >= 0.5
    dark = ~np.isnan(lv) & nearc & ((lv - local) < -dws.S2_SHADOW_SPECK_LOG10)
    lab, n = ndimage.label(dark)
    shadow = np.zeros_like(dark)
    if n:
        sz = ndimage.sum(dark, lab, index=np.arange(1, n + 1))
        shadow = np.isin(lab, np.nonzero(sz <= dws.SPECK_MAX_CELLS)[0] + 1)
    lv = np.where(shadow, np.nan, lv)
    lab, n = ndimage.label(~np.isnan(lv))
    tiny = np.zeros(lv.shape, bool)
    if n:
        sz = ndimage.sum(~np.isnan(lv), lab, index=np.arange(1, n + 1))
        tiny = np.isin(lab, np.nonzero(sz < dws.S2_MIN_PATCH_CELLS)[0] + 1)
    lv = np.where(tiny, np.nan, lv)
    pocket = dropped & ~speck & ~shadow & ~tiny
    unread = lake & np.isnan(v)
    grass_cls = unread & pgrass
    # unread, not grass: why? the dominant non-readable pixel reason in the cell
    readable_px = counts[..., 0]
    total_px = counts.sum(axis=2)
    other = counts.copy(); other[..., 0] = 0
    dom = np.argmax(other, axis=2)
    partial = unread & ~pgrass & (readable_px > 0)
    rest = unread & ~pgrass
    groups = {
        "no scene coverage": (1, 2),
        "cloud, cloud shadow, cirrus": (3, 4, 5, 6),
        "cloud standoff (60 m of SCL cloud, 600 m of real cloud)": (11, 12),
        "haze (cloud edge, hazy water)": (13, 14),
        "bright water (hulls, missed cloud)": (15,),
        "land/shoreline inside the outline (SCL veg, bare, dark, unclassified)": (7, 8, 9, 10),
        "shoreline pixel touching SCL bank": (16,),
        "structures (bridges, docks, roofs) within 100 m": (17,),
        "SWIR too high (glint, haze, land in pixel)": (18,),
        "vegetation signal on water (FAI / NDVI)": (19, 20),
        "invalid red": (21,),
    }
    code_group = {c: g for g, cs in groups.items() for c in cs}
    unread_by = collections.Counter()
    for c in range(1, 22):
        m = rest & (dom == c) & (total_px > 0)
        if m.any():
            unread_by[code_group[c]] += int(m.sum())
    unread_by["no tile pixel lands in the cell"] += int((rest & (total_px == 0)).sum())
    rep["cells"] = {
        "denominator_lakeCells": N,
        "measured": int(measured.sum()),
        "readThenDropped": {"muddySpeck": int((dropped & speck).sum()),
                            "shadowPatchNearCloud": int((dropped & shadow).sum()),
                            "patchUnder5Cells": int((dropped & tiny).sum()),
                            "muddyPocketBesideGrass": int(pocket.sum())},
        "unreadGrassBed_NDVIge0.3": int(grass_cls.sum()),
        "unreadNotGrass": int(rest.sum()),
        "unreadNotGrass_hadSomeReadablePixelsButUnder25pct": int(partial.sum()),
        "unreadNotGrass_byDominantPixelReason": dict(unread_by.most_common()),
        "cloudHiddenShare_ge0.5_amongUnread": int((unread & (np.nan_to_num(aux["hidden"]) >= 0.5)).sum()),
        "noTileFootprint": int((lake & no_tile).sum()),
        "in40mBankBand": int((lake & ~masks["clarity"]).sum()),
        "measuredIn40mBankBand": int((measured & ~masks["clarity"]).sum()),
    }
    # the partial cells: what share of their pixels was readable
    if partial.any():
        rp = readable_px[partial] / np.maximum(1, total_px[partial])
        rep["cells"]["partialReadableShare_p50"] = float(np.median(rp))

    # ---- fill composition (the shipped PNG codes, inside the lake)
    fc = collections.Counter(source[lake].tolist())
    names = {255: "satellite-derived (read this pass)", 3: "grass bed, carried in from water round it",
             2: "cloud/haze hid it, filled through the water", 1: "unreadable water, filled through the water",
             0: "no value"}
    rep["fill"] = {names.get(k, str(k)): int(c) for k, c in fc.most_common()}
    d = FILL["dist"][lake & ~measured]
    bins = [0, 250, 500, 1000, 2000, 5000, np.inf]
    h, _ = np.histogram(np.where(np.isfinite(d), d, 1e9), bins=bins)
    rep["fill"]["estimatedByThroughWaterDistance_m"] = {
        f"{bins[i]:g}-{bins[i + 1]:g}": int(h[i]) for i in range(len(h))}
    rep["fill"]["heldOutErrorByDistance_ft"] = meta["fill"]["errorByDistance"]
    rep["fill"]["backgroundLevel_FNU"] = round(10 ** meta["fill"]["b0Log10"], 2)
    json.dump(rep, open(out_path, "w"), indent=2)
    print(json.dumps(rep, indent=2))
    # ---- the per-cell evidence
    reason = np.zeros(lake.shape, dtype=np.uint8)          # 0 = observed
    dom_all = dom.copy()
    reason[unread & ~pgrass & (total_px > 0)] = dom_all[unread & ~pgrass & (total_px > 0)].astype(np.uint8)
    reason[unread & ~pgrass & (total_px == 0)] = 22          # no tile pixel in the cell
    reason[unread & pgrass] = 30                             # surface grass (NDVI >= 0.3)
    reason[dropped & speck] = 40; reason[dropped & shadow] = 41
    reason[dropped & tiny] = 42; reason[pocket] = 43
    reason[~lake] = 255
    reason[measured] = 0
    np.save(out_path.replace(".json", ".reason.npy"), reason)
    np.save(out_path.replace(".json", ".lake.npy"), lake)


if __name__ == "__main__":
    main()
