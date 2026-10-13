"""Adapter for the SHIPPED observer v0.2 (imported, not re-implemented). OFFLINE: socket guard makes any connection raise.
Reuses the v1_eval adapter (v1lib) for: cached reflectance -> DN, lake masks, distance to edge, cell geometry. Adds haze_swir / haze_standoff_px threading.
The adaptive NIR floor is computed by the module itself; nir_floor is NEVER passed."""
import sys, os
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
V1S = "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/v1_eval/scripts"
sys.path.insert(0, V1S)
from v1lib import *                       # noqa  (imports observer as O, contract as C, numpy, rasterio, pyproj, shapely, ndimage ...)
import pandas as pd

HERE2 = Path(__file__).resolve().parents[1]           # .../adoption/v2_eval
OUT2 = HERE2 / "out"
ADOPT = HERE2.parent
EXP = ADOPT.parent
NLA = ADOPT / "nla"
SEAS = ADOPT / "seasonal"
GRID_HS = [0.02, 0.03, 0.04, 0.06, 0.10]
GRID_HP = [0, 2, 5, 10]
DEFAULT = (0.02, 10)

def install_guard():
    net_guard()
    assert O.NIR_PLANT_MIN == 0.03 and hasattr(O, "scene_nir_floor")      # unmodified v0.2 module state

def make_scene2(sid, when, coll, dn_red, dn_nir, dn_swir, scl, lake, hs, hp):
    """-> (Scene, diag). scene_fields gets haze_swir/haze_standoff_px; the adaptive floor is the module's own (no nir_floor)."""
    red = O.reflectance(dn_red, coll); nir = O.reflectance(dn_nir, coll); swir = O.reflectance(dn_swir, coll)
    f = O.scene_fields(scl, red, nir, swir, lake, haze_swir=hs, haze_standoff_px=hp)
    cells = O.to_cells(f)
    el = cells.eligible
    unk = {}
    for code, nm in O.REASON_NAMES.items():
        k = int(((cells.reason == code) & (cells.state == O.UNKNOWN) & el).sum())
        if k: unk[nm] = k
    diag = dict(id=sid, when=str(when), floor=f.nir_floor, tail=f.floor_diag.get("tail"), n_open=f.floor_diag.get("openWaterPixels"),
                ambiguous=bool(f.blocked["BLOOM_AMBIGUOUS"].any()), cov=cells.coverage(), unknown=unk, eligible=int(el.sum()), interior=int(cells.interior.sum()))
    return O.Scene(sid, when, cells, coll), diag

def obs_record(o, keep_state=True):
    pres = O.presence(o)
    return dict(kind=o.evidence_kind, persistence=o.persistence, n_accepted=o.n_accepted, plant_cells=o.plant_cells, read_cells=o.read_cells, interior=o.interior_cells,
                coverage=o.coverage, isolated_dropped=o.isolated_dropped, shares=o.refusal_shares, notes=o.notes, presence=pres, fallback=o.low_coverage_fallback,
                scene_ids=o.scene_ids, observed_on=str(o.observed_on), state=(None if (o.state is None or not keep_state) else o.state.copy()))

def sel_record(scenes, ref):
    sel = O.select_scenes(scenes, ref)
    gs = {}
    for s in sel["inWindow"]:
        c = s.cells
        for code, nm in O.REASON_NAMES.items():
            k = int(((c.reason == code) & (c.state == O.UNKNOWN) & c.eligible).sum())
            if k: gs[nm] = gs.get(nm, 0) + k
    return dict(n_inwindow=len(sel["inWindow"]), n_accepted=len(sel["accepted"]), bursts=sel["bursts"], cov=[round(s.cells.coverage(), 3) for s in sel["inWindow"]],
                gaps=[abs((s.when - ref).days) for s in sel["inWindow"]], scene_unknown_cells=gs,
                scene_eligible_cells_total=int(sum(s.cells.eligible.sum() for s in sel["inWindow"])),
                inwindow_ids=[s.id for s in sel["inWindow"]])

def pair_key(hs, hp): return f"{hs:.2f}|{hp}"

def load_frozen():
    p = OUT2 / "chosen_params.frozen.json"
    return json.load(open(p))

def append_manifest(paths, kind="v2_eval", note="note 12 v0.2 dev/test evaluation (cache-only; 0 S2 network bytes)"):
    import hashlib
    man = EXP.parent / "MANIFEST.jsonl"
    with open(man, "a") as fh:
        for p in paths:
            p = Path(p); b = p.read_bytes()
            fh.write(json.dumps(dict(kind=kind, path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), source_url="local", retention="keep", note=note)) + "\n")
