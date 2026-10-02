"""Where an observation is on Guntersville: main stem or which arm, and which Stage 3A zone.
Reads the engine's own arm grid (docs/data/hydrology/guntersville/stage3a), a Web-Mercator frame of
2468 x 2886 cells (29.6 m ground). A point off the lake cells takes the nearest lake cell within 60 m."""
import json, math, os
import numpy as np
from scipy import ndimage

G = os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/docs/data/hydrology/guntersville")
_P = np.load(os.path.join(G, "stage3a", "arm_positions.npz"))
_Z = json.load(open(os.path.join(G, "stage3a", "arm_zones.json")))
NAMES = json.load(open(os.path.join(G, "guntersville.arm_cells.json")))["arms"]
LAKE, ARM, ZONE = _P["lake"], _P["arm"].astype(int), _P["zone"].astype(int)
H, W = LAKE.shape
(_W, _N), (_E, _), (_, _S), _ = _Z["frame"]["cornersLonLat"]
CELL_M = _Z["frame"]["cellGroundM"]
_mx = lambda lon: math.radians(lon)
_my = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
_dist, (_ir, _ic) = ndimage.distance_transform_edt(~LAKE, return_indices=True)
ZMETA = {z["zone"]: z for z in _Z["zones"]}


def cell(lat, lon):
    c = (_mx(lon) - _mx(_W)) / (_mx(_E) - _mx(_W)) * W
    r = (_my(_N) - _my(lat)) / (_my(_N) - _my(_S)) * H
    return int(r), int(c)


def where(lat, lon, snap_m=60.0):
    """-> dict(kind mainStem|arm|offLake, arm, zone, zoneName) for a lat/lon."""
    r, c = cell(lat, lon)
    if not (0 <= r < H and 0 <= c < W):
        return {"kind": "offLake", "arm": None, "zone": None, "zoneName": None}
    if not LAKE[r, c]:
        if _dist[r, c] * CELL_M > snap_m:
            return {"kind": "offLake", "arm": None, "zone": None, "zoneName": None}
        r, c = _ir[r, c], _ic[r, c]
    a, z = ARM[r, c], ZONE[r, c]
    name = NAMES[a] if 0 <= a < len(NAMES) else None
    zm = ZMETA.get(int(z)) if z >= 0 else None
    return {"kind": "mainStem" if name is None else "arm", "arm": name, "zone": int(z) if z >= 0 else None,
            "zoneName": (f"{zm['arm']} {zm['name']}" if zm else None)}


def center(r, c):
    """lat/lon of a cell centre."""
    x = _mx(_W) + (c + 0.5) / W * (_mx(_E) - _mx(_W))
    y = _my(_N) - (r + 0.5) / H * (_my(_N) - _my(_S))
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2), math.degrees(x)
