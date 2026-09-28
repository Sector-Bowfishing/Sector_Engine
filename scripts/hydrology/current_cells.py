"""Per-cell evidence files for the Current Clarity Engine (Clarity Fusion Stage 4).

The engine answers "how clear is the water HERE, now?" per cell, so it needs
each scene's cells, not just its per-arm summary. It runs on Linux, where a
PNG cannot be decoded, so each scene is also written as a flat file over ONE
fixed index of the lake's water cells.

  regions   the fixed index: every cell of the Water Clarity frame that the
            layer colours (the lake and the 100 m band past its line,
            masks["reach"]), in row-major order, with its hydrologic region
            (0 = main stem, k = arm k of guntersville.arm_cells.json) and its
            Stage 3A zone (-1 = main stem). Band cells take the nearest lake
            cell's. Written as <out>.bin (for the engine's generated Swift)
            and <out>.json (the tables).

  scene     one published Water Clarity product (<date>.png, .measured.png,
            .distance.png, .json) onto the index:
              magic "SCC1" | u32 N | u32 index hash (FNV-1a of the mask RLE)
              | u8[N] value  (0 none, 1..254 log10 FNU on log10 0.5..200)
              | u8[N] code   (0 none, 255 read, 1 unreadable, 2 cloud, 3 grass)
              | u8[N] dist   (0 read or none, 1 + through-water m / 100, 254 = no path)

  product   a Water Clarity product rebuilt from a pass_history --cells file
            (the pass's observed cells) with the production fill
            (fill_lake.fill_clarity, value_grass). For development and the
            historical replay only: it skips build_clarity's grass-under-cloud
            borrowing and grass-to-bank strip, so it is close to, not identical
            with, what the daily job would have published that day.

usage: geo/bin/python current_cells.py regions <out prefix>
       geo/bin/python current_cells.py swift <regions prefix> <out .swift>
       geo/bin/python current_cells.py scene <product dir> <date> <regions prefix> <out.cells.bin>
       geo/bin/python current_cells.py product <cells.npz> <pass time ISO> <out dir> <date>
"""
import os, sys, json, math, zlib, base64, struct, io
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
DATA = os.path.join(ROOT, "docs", "data", "hydrology", "guntersville")
WATERBODY = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox/.fishintel-cache/guntersville/waterbody.geojson")
LO, HI, TOP = math.log10(0.5), math.log10(200.0), 254
DIST_STEP_M = 100.0


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def rle_mask(mask):
    """Row-major runs, alternating out/in, starting with out (possibly 0)."""
    flat = mask.ravel().astype(np.int8)
    change = np.nonzero(np.diff(flat))[0] + 1
    bounds = np.concatenate([[0], change, [flat.size]])
    runs = np.diff(bounds)
    out = bytearray()
    if flat[0]:
        out += varint(0)
    for r in runs:
        out += varint(int(r))
    return bytes(out)


def rle_values(v):
    """(value, run) varint pairs."""
    out = bytearray()
    i, n = 0, len(v)
    while i < n:
        j = i
        while j < n and v[j] == v[i]:
            j += 1
        out += varint(int(v[i])) + varint(j - i)
        i = j
    return bytes(out)


def fnv1a(b):
    h = 0x811C9DC5
    for x in b:
        h ^= x
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def frame_and_masks():
    sys.path.insert(0, os.path.join(ROOT, "jobs", "lake-surface"))
    import derive_water_surface as dws
    from shapely.geometry import shape
    from shapely.ops import unary_union
    lake_g = unary_union([shape(f["geometry"]) for f in json.load(open(WATERBODY))["features"]])
    dws.UTM = "EPSG:32616"
    frame = dws.Frame(lake_g, cell=dws.CLARITY_CELL)
    return dws, frame, dws.lake_masks(lake_g, frame)


def regions(prefix):
    _, frame, masks = frame_and_masks()
    P = np.load(os.path.join(DATA, "stage3a", "arm_positions.npz"))
    Z = json.load(open(os.path.join(DATA, "stage3a", "arm_zones.json")))
    cells = json.load(open(os.path.join(DATA, "guntersville.arm_cells.json")))
    lake, reach = P["lake"], masks["reach"] | P["lake"]
    assert (masks["lake"] == lake).all(), "the lake mask moved: rebuild arm_positions first"
    arm = P["arm"].astype(np.int32)
    zone = P["zone"].astype(np.int32)
    _, (ir, ic) = ndimage.distance_transform_edt(~lake, return_indices=True)
    band = reach & ~lake
    arm[band] = arm[ir[band], ic[band]]
    zone[band] = zone[ir[band], ic[band]]
    mask_rle = rle_mask(reach)
    idx_arm = arm[reach].astype(np.int64)
    idx_zone = zone[reach].astype(np.int64)
    n = int(reach.sum())
    blob = (b"SCR1" + struct.pack("<IIII", frame.width, frame.height, n, fnv1a(mask_rle))
            + struct.pack("<I", len(mask_rle)) + mask_rle)
    ra = rle_values(idx_arm)
    rz = rle_values(idx_zone + 1)
    blob += struct.pack("<I", len(ra)) + ra + struct.pack("<I", len(rz)) + rz
    open(prefix + ".bin", "wb").write(blob)
    names = cells["arms"]
    zmeta = [{"zone": z["zone"], "arm": z["arm"], "name": z["name"], "index": z["index"], "of": z["of"]}
             for z in Z["zones"]]
    meta = {"lakeId": "Guntersville|AL", "schema": "current-clarity-regions-v1",
            "width": frame.width, "height": frame.height, "cells": n, "indexHash": fnv1a(mask_rle),
            "cornersLonLat": Z["frame"]["cornersLonLat"], "cellGroundM": Z["frame"]["cellGroundM"],
            "regions": [{"index": k, "kind": "mainStem" if nm is None else "arm", "id": nm or "_mainStem",
                         "cells": int((idx_arm == k).sum())} for k, nm in enumerate(names)],
            "zones": zmeta,
            "rule": "index = masks['reach'] | lake (the cells the layer colours), row-major; band cells take the nearest lake cell's region and zone"}
    json.dump(meta, open(prefix + ".json", "w"), indent=1)
    print(f"regions: {n:,} cells, blob {len(blob) / 1024:.0f} KB (mask RLE {len(mask_rle) / 1024:.0f} KB, "
          f"region RLE {len(ra) / 1024:.0f} KB, zone RLE {len(rz) / 1024:.0f} KB), hash {fnv1a(mask_rle):08x}")


def load_regions(prefix):
    b = open(prefix + ".bin", "rb").read()
    assert b[:4] == b"SCR1"
    w, h, n, hsh = struct.unpack("<IIII", b[4:20])
    (ml,) = struct.unpack("<I", b[20:24])
    mask_rle = b[24:24 + ml]
    runs, i, val = [], 0, 0
    while i < len(mask_rle):
        shift = out = 0
        while True:
            x = mask_rle[i]; i += 1
            out |= (x & 0x7F) << shift
            if not x & 0x80:
                break
            shift += 7
        runs.append(out)
    flat = np.zeros(w * h, bool)
    p = 0
    for k, r in enumerate(runs):
        if k % 2 == 1:
            flat[p:p + r] = True
        p += r
    mask = flat.reshape(h, w)
    assert int(mask.sum()) == n
    return mask, hsh


def scene(product_dir, date, regions_prefix, out):
    from PIL import Image
    mask, hsh = load_regions(regions_prefix)

    def load(suffix):
        p = f"{product_dir.rstrip('/')}/{date}{suffix}"
        if p.startswith("http"):
            import urllib.request
            return urllib.request.urlopen(p).read()
        return open(p, "rb").read()
    meta = json.loads(load(".json"))
    enc = meta["encoding"]
    assert abs(enc["lo"] - LO) < 1e-9 and abs(enc["hi"] - HI) < 1e-9 and enc["top"] == TOP, enc
    step = meta["measured"].get("distanceStepM", DIST_STEP_M)
    assert step == DIST_STEP_M, step
    val = np.asarray(Image.open(io.BytesIO(load(".png"))), dtype=np.uint8)
    code = np.asarray(Image.open(io.BytesIO(load(".measured.png"))), dtype=np.uint8)
    dist = np.asarray(Image.open(io.BytesIO(load(".distance.png"))), dtype=np.uint8)
    assert val.shape == mask.shape, (val.shape, mask.shape)
    v, c, d = val[mask], code[mask], dist[mask]
    c = np.where(v == 0, 0, c).astype(np.uint8)
    d = np.where((c == 255) | (c == 0), 0, np.maximum(d, 1)).astype(np.uint8)
    n = int(mask.sum())
    blob = b"SCC1" + struct.pack("<II", n, hsh) + v.tobytes() + c.tobytes() + d.tobytes()
    open(out, "wb").write(blob)
    outside = int(((val > 0) & ~mask).sum())
    print(f"{date}: {n:,} cells, read {int((c == 255).sum()):,}, filled {int(np.isin(c, (1, 2)).sum()):,}, "
          f"grass {int((c == 3).sum()):,}, no value {int((c == 0).sum()):,}; product cells outside the index {outside}")


def product(cells_npz, pass_time, out_dir, date):
    """A product triplet from a pass's observed cells, with the production fill."""
    from PIL import Image
    dws, frame, masks = frame_and_masks()
    import fill_lake  # noqa: E402  (on the path frame_and_masks sets)
    x = np.load(cells_npz)
    fnu, cls = x["fnu"], x["cls"]
    logv = np.where(cls == 1, LO + (fnu.astype(np.float64) - 1) / (TOP - 1) * (HI - LO), np.nan)
    grass = cls == 3
    lake = masks["lake"]
    filled, measured, info = fill_lake.fill_clarity(
        logv, lake, grass, cell_ground_m=frame.cell_ground_m(),
        lake_touch=masks["lake_touch"], reach=masks["reach"], value_grass=True)
    q = dws.encode(filled, LO, HI, top=TOP)
    valued = (q > 0) & (q <= TOP)
    src = np.zeros(q.shape, np.uint8)
    src[valued] = 1
    src[valued & lake & ~measured & (cls == 2)] = 2
    band_out = masks["reach"] & ~lake
    _, (ir, ic) = ndimage.distance_transform_edt(~lake, return_indices=True)
    bed = (lake & grass) | (band_out & grass[ir, ic])
    src[valued & bed] = 3
    src[measured] = 255
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, date)
    Image.fromarray(q, mode="L").save(base + ".png", optimize=True)
    Image.fromarray(src, mode="L").save(base + ".measured.png", optimize=True)
    dws.write_distance(base + ".distance.png", info["dist_to_reading_m"], masks, src)
    meta = {"lakeId": "Guntersville|AL", "field": "turbidity", "unit": "FNU",
            "encoding": {"kind": "log10", "lo": LO, "hi": HI, "top": TOP},
            "pass": {"date": date, "time": pass_time, "platform": os.path.basename(cells_npz).split("_")[1].split(".")[0]},
            "measured": {"distanceStepM": DIST_STEP_M},
            "measuredPct": round(100 * float(measured.sum() / lake.sum()), 1),
            "source": f"rebuilt from {os.path.basename(cells_npz)} (pass_history --cells) with fill_lake.fill_clarity; "
                      "no grass-under-cloud borrowing or grass-to-bank strip (development / replay product)"}
    json.dump(meta, open(base + ".json", "w"), indent=1)
    return meta


def swift(prefix, out):
    """The index for the engine: the blob as base64 and the tables as JSON, in
    one generated Swift file (as HydrologyData.swift carries the arm graph)."""
    blob = base64.b64encode(open(prefix + ".bin", "rb").read()).decode()
    meta = json.load(open(prefix + ".json"))
    tables = json.dumps({"lakeId": meta["lakeId"], "width": meta["width"], "height": meta["height"],
                         "cells": meta["cells"], "indexHash": meta["indexHash"], "cornersLonLat": meta["cornersLonLat"],
                         "cellGroundM": meta["cellGroundM"], "regions": [r["id"] for r in meta["regions"]],
                         "zones": meta["zones"]}, separators=(",", ":"))
    q3 = '"' * 3
    head = ("//\n//  CurrentClarityRegionsData.swift\n"
            "//  GENERATED by scripts/hydrology/current_cells.py swift — do not edit by hand.\n//\n"
            "//  Lake Guntersville's fixed index of the cells the Water Clarity layer\n"
            f"//  colours ({meta['cells']:,}), each with its hydrologic region and Stage 3A zone\n"
            "//  (Clarity Fusion Stage 4). Scene cell files are aligned to this index and\n"
            f"//  carry its hash ({meta['indexHash']:08x}).\n//\n\n")
    body = (f'let currentClarityGuntersvilleBlob = "{blob}"\n\n'
            f"let currentClarityGuntersvilleTables = #{q3}\n{tables}\n{q3}#\n")
    open(out, "w").write(head + body)
    print(f"wrote {out} ({os.path.getsize(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "regions":
        regions(sys.argv[2])
    elif cmd == "swift":
        swift(sys.argv[2], sys.argv[3])
    elif cmd == "scene":
        scene(*sys.argv[2:6])
    elif cmd == "product":
        m = product(*sys.argv[2:6])
        print(m["pass"]["date"], m["measuredPct"], "% read")
    else:
        raise SystemExit(__doc__)
