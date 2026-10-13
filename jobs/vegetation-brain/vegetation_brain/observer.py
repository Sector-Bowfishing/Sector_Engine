"""Surface-reaching vegetation observer (OFFLINE; pure numpy; no I/O, no network).

Pipeline (pre-registration section 1):  pixels -> scene fields -> 50 m cells (plant fraction + refusal reason)
-> pass acceptance -> persistence (median of accepted scenes) -> lake observation.

PRINCIPLES (docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md):
  * One noisy pixel never makes a cell vegetation: a cell needs plantFraction >= 0.5 of its SEEN pixels.
  * Unreliable evidence is UNKNOWN with a reason code, never NO_PLANT.
  * Max / second-highest / votes>=2 composites are forbidden (research: precision 0.21-0.40).
  * Submerged vegetation is not observable: nothing here can produce a "submerged" class.

The pixel plant rule is the production rule (jobs/lake-surface/derive_water_surface.py: NDVI(B8A,B4) >= 0.30 on a
non-cloud pixel), plus ONE provisional addition justified by the research (dark open water with red and NIR
both ~0.005 crosses NDVI 0.30 from rounding noise: 6-10 % of open-water pixels): an absolute NIR floor
(NIR_PLANT_MIN). That floor is PROVISIONAL until calibrated on negative-control lakes (see the validation reports).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np

from . import contract as C

# Provisional (see module docstring); calibrated label-free on open-water NIR of negative-control lakes, not on truth lakes.
NIR_PLANT_MIN = 0.03
DARK_ARTIFACT_CELL_SHARE = 0.25        # cell with this share of NDVI-crossing-but-dark pixels is flagged DARK_WATER if borderline
DISTURBED_SWIR = 0.010                 # production HAZE_EDGE_SWIR: the water-at-a-haze-fringe limit, applied when the surface is disturbed
HAZE_STANDOFF_PX = 10                  # 100 m, as production S2_HAZE_STANDOFF_M
MIN_PLANT_CELLS = 3                    # presence needs >= 3 plant cells after dropping isolated singletons
MIN_READ_FRACTION = 0.5                # NOT_OBSERVED needs >= half of the eligible interior cells read

# integer codes for the per-cell state raster
UNKNOWN, NO_PLANT, PLANT = 0, 1, 2
OUTSIDE = -1
REASON_CODES = {name: i + 1 for i, name in enumerate(C.REFUSALS)}
REASON_NAMES = {v: k for k, v in REASON_CODES.items()}


# ------------------------------------------------------------------------------------- reflectance
def reflectance(dn: np.ndarray, collection: str) -> np.ndarray:
    """DN -> surface reflectance with the collection's own convention. Applying the c1 offset to the plain
    `sentinel-2-l2a` collection (already offset-free) doubles the value: that error cost a whole research pass."""
    if collection == "sentinel-2-c1-l2a":
        off = C.S2_OFFSET_C1
    elif collection == "sentinel-2-l2a":
        off = 0.0
    else:
        raise ValueError(f"unknown S2 collection {collection!r}; offset convention not defined")
    r = dn.astype("float32") * C.S2_SCALE + off
    r[(dn == 0) | (dn == 65535)] = np.nan
    return r


def check_offset_convention(swir_dn_over_water_median: float, collection: str) -> None:
    """Open water's SWIR is ~0 reflectance: DN ~1000-1100 on c1 (offset -0.1), ~0-200 on offset-free l2a."""
    if collection == "sentinel-2-c1-l2a" and not (900 <= swir_dn_over_water_median <= 1500):
        raise ValueError(f"SWIR DN over water is {swir_dn_over_water_median:.0f}; expected ~1000-1100 for c1")
    if collection == "sentinel-2-l2a" and swir_dn_over_water_median > 800:
        raise ValueError("SWIR DN over water is high for an offset-free collection; check the offset convention")


# ------------------------------------------------------------------------------------- helpers
def grow(mask: np.ndarray, px: int) -> np.ndarray:
    """Square (Chebyshev) dilation by px pixels, separable, numpy only."""
    if px <= 0 or not mask.any():
        return mask.copy()
    out = mask.copy()
    for axis in (0, 1):
        acc = out.copy()
        for s in range(1, px + 1):
            acc |= np.roll(out, s, axis) & _roll_valid(out.shape, s, axis)
            acc |= np.roll(out, -s, axis) & _roll_valid(out.shape, -s, axis)
        out = acc
    return out


def _roll_valid(shape, s, axis):
    v = np.ones(shape, bool)
    if s > 0:
        (v[:s, :] if axis == 0 else v[:, :s]).fill(False)
    else:
        (v[s:, :] if axis == 0 else v[:, s:]).fill(False)
    return v


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    """Erosion with the array border counted as outside the mask."""
    if px <= 0:
        return mask.copy()
    p = np.pad(mask, px, constant_values=False)
    return (~grow(~p, px))[px:-px, px:-px]


# ------------------------------------------------------------------------------------- scene -> pixel fields
@dataclass
class SceneFields:
    plant: np.ndarray        # bool: plant-spectrum pixel (seen)
    seen: np.ndarray         # bool: inside the lake and usable
    blocked: dict            # reason name -> bool array (pixels blocked for that reason)
    dark_artifact: np.ndarray  # bool: NDVI >= 0.30 but NIR below the floor (rounding noise, NOT plant)
    lake: np.ndarray


def scene_fields(scl: np.ndarray, red: np.ndarray, nir: np.ndarray, swir: np.ndarray, lake_mask: np.ndarray) -> SceneFields:
    """All inputs on one 10 m grid (20 m bands already repeated to 10 m). red/nir/swir are reflectances (NaN = no data)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (nir - red) / np.maximum(1e-6, nir + red)
    finite = np.isfinite(red) & np.isfinite(nir) & np.isfinite(swir)
    valid_scl = scl > 0
    water = scl == C.SCL_WATER
    plant_spec = np.isfinite(ndvi) & (ndvi >= C.PLANT_NDVI_MIN)
    plant_px = plant_spec & (nir >= NIR_PLANT_MIN)
    dark_artifact = plant_spec & (nir < NIR_PLANT_MIN)

    cloud_cls = np.isin(scl, (1, 8, 9, 10))
    shadow_cls = scl == C.SCL_SHADOW
    snow_cls = scl == C.SCL_SNOW
    blocked = {
        "CLOUD": grow(cloud_cls, C.CLOUD_STANDOFF_PX),
        "SHADOW": grow(shadow_cls, C.CLOUD_STANDOFF_PX // 3),
        "ICE_OR_SNOW": grow(snow_cls, C.CLOUD_STANDOFF_PX // 3),
    }
    with np.errstate(invalid="ignore"):
        haze_px = water & (swir > C.HAZE_SWIR) & ~plant_px
    blocked["HAZE"] = grow(haze_px, HAZE_STANDOFF_PX)
    blocked["GLARE"] = np.zeros_like(haze_px)      # reserved: set by `apply_surface_disturbance` from the Wind Brain, never inferred here
    any_block = np.zeros_like(haze_px)
    for m in blocked.values():
        any_block |= m
    seen = lake_mask & valid_scl & finite & ~any_block
    plant = plant_px & seen
    return SceneFields(plant=plant, seen=seen, blocked=blocked, dark_artifact=dark_artifact & seen, lake=lake_mask)


def apply_surface_disturbance(fields: SceneFields, swir: np.ndarray, disturbed: bool, glint_swir: float = DISTURBED_SWIR) -> SceneFields:
    """Wind Brain (or scene geometry) says the surface is disturbed: a stricter SWIR limit than the haze rule applies, and water
    pixels above it that are not plants become GLARE-blocked. Wind science is NOT computed here; only a flag is consumed."""
    if not disturbed:
        return fields
    with np.errstate(invalid="ignore"):
        g = fields.seen & ~fields.plant & (swir > glint_swir)
    fields.blocked["GLARE"] = g
    fields.seen = fields.seen & ~g
    fields.plant = fields.plant & fields.seen
    return fields


# ------------------------------------------------------------------------------------- pixels -> cells
@dataclass
class CellScene:
    plant_fraction: np.ndarray    # float32 NaN = unknown
    state: np.ndarray             # int8 UNKNOWN/NO_PLANT/PLANT/OUTSIDE
    reason: np.ndarray            # int8 0 = none else REASON_CODES
    eligible: np.ndarray          # bool: inside the lake enough to be assessed (>= half of cell pixels in the lake)
    interior: np.ndarray          # bool: eligible and not shore-adjacent
    shape: tuple

    @property
    def read(self) -> np.ndarray:
        return self.interior & (self.state != UNKNOWN)

    def coverage(self) -> float:
        n = int(self.interior.sum())
        return float(self.read.sum()) / n if n else 0.0


def _blocks(a: np.ndarray, k: int) -> np.ndarray:
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return a[:h, :w].reshape(h // k, k, w // k, k)


def to_cells(fields: SceneFields, cell_px: int = C.CELL_PX) -> CellScene:
    lake_b = _blocks(fields.lake, cell_px).sum(axis=(1, 3))
    seen_b = _blocks(fields.seen, cell_px).sum(axis=(1, 3))
    plant_b = _blocks(fields.plant, cell_px).sum(axis=(1, 3))
    dark_b = _blocks(fields.dark_artifact, cell_px).sum(axis=(1, 3))
    edge = fields.lake & ~erode(fields.lake, 1)
    edge_b = _blocks(edge, cell_px).sum(axis=(1, 3))
    n = cell_px * cell_px
    eligible = lake_b >= n / 2
    shore = eligible & (edge_b > 0)
    interior = eligible & ~shore

    blocked_counts = {k: _blocks(v & fields.lake, cell_px).sum(axis=(1, 3)) for k, v in fields.blocked.items()}
    shape = lake_b.shape
    state = np.full(shape, OUTSIDE, "int8")
    reason = np.zeros(shape, "int8")
    pf = np.full(shape, np.nan, "float32")
    state[eligible] = UNKNOWN

    seen_frac = np.where(lake_b > 0, seen_b / np.maximum(lake_b, 1), 0.0)
    enough = eligible & (seen_frac >= C.MIN_SEEN_FRACTION)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(seen_b > 0, plant_b / np.maximum(seen_b, 1), np.nan)
    pf[enough] = frac[enough].astype("float32")
    is_plant = enough & (frac >= C.PLANT_FRACTION_MIN)
    is_none = enough & ~is_plant
    # borderline dark-water artifacts: a cell with many NDVI-crossing dark pixels and some plant evidence is not trusted either way
    dark_share = np.where(lake_b > 0, dark_b / np.maximum(lake_b, 1), 0.0)
    dark_bad = enough & (dark_share >= DARK_ARTIFACT_CELL_SHARE) & (np.nan_to_num(frac) >= 0.2)
    is_plant &= ~dark_bad
    is_none &= ~dark_bad
    state[is_plant] = PLANT
    state[is_none] = NO_PLANT
    reason[dark_bad] = REASON_CODES["DARK_WATER"]
    # why a cell is UNKNOWN: dominant blocking reason, else insufficient valid pixels
    unk = eligible & (state == UNKNOWN) & ~dark_bad
    order = ["ICE_OR_SNOW", "CLOUD", "SHADOW", "HAZE", "GLARE"]
    best = np.zeros(shape, bool)
    for nm in order:
        hit = unk & ~best & (blocked_counts[nm] > 0) & (blocked_counts[nm] >= np.maximum(1, (lake_b - seen_b) * 0.5))
        reason[hit] = REASON_CODES[nm]
        best |= hit
    reason[unk & ~best] = REASON_CODES["INSUFFICIENT_VALID_PIXELS"]
    # shore-adjacent cells are never claimed (prereg section 1): a SHORE_ADJACENT UNKNOWN regardless of the pixels
    state[shore] = UNKNOWN
    reason[shore] = REASON_CODES["SHORE_ADJACENT"]
    pf[shore] = np.nan
    return CellScene(pf, state, reason, eligible, interior, shape)


# ------------------------------------------------------------------------------------- pass acceptance and persistence
@dataclass
class Scene:
    id: str
    when: date
    cells: CellScene
    collection: str = "sentinel-2-c1-l2a"


def accept_pass(scene: Scene) -> bool:
    return scene.cells.coverage() >= C.PASS_MIN_COVERAGE


def select_scenes(scenes: list, reference: date, window_days: int = C.PERSISTENCE_WINDOW_DAYS) -> dict:
    """Scenes inside +-window of the reference date, split into accepted (>=50 % read) and the fallback (best >=25 %)."""
    inwin = sorted([s for s in scenes if abs((s.when - reference).days) <= window_days], key=lambda s: abs((s.when - reference).days))
    accepted = [s for s in inwin if accept_pass(s)]
    fallback = None
    if not accepted:
        cand = [s for s in inwin if s.cells.coverage() >= C.PASS_FALLBACK_COVERAGE]
        if cand:
            fallback = max(cand, key=lambda s: (s.cells.coverage(), -abs((s.when - reference).days)))
    return {"inWindow": inwin, "accepted": accepted, "fallback": fallback}


def _drop_isolated(plant: np.ndarray) -> tuple[np.ndarray, int]:
    nb = np.zeros(plant.shape, int)
    p = plant.astype(int)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            nb += np.roll(np.roll(p, dy, 0), dx, 1) * _shift_valid(plant.shape, dy, dx)
    iso = plant & (nb == 0)
    return plant & ~iso, int(iso.sum())


def _shift_valid(shape, dy, dx):
    v = np.ones(shape, int)
    if dy > 0:
        v[:dy, :] = 0
    if dy < 0:
        v[dy:, :] = 0
    if dx > 0:
        v[:, :dx] = 0
    if dx < 0:
        v[:, dx:] = 0
    return v


@dataclass
class LakeObservation:
    evidence_kind: str                    # SATELLITE_SINGLE_PASS / ACCEPTED_PASS / PERSISTENCE / NONE
    persistence: str                      # MEDIAN_OF_ACCEPTED / INSUFFICIENT / NOT_APPLICABLE
    scene_ids: list
    observed_on: date | None
    cells: CellScene | None
    state: np.ndarray | None
    reason: np.ndarray | None
    n_accepted: int
    coverage: float
    plant_cells: int
    read_cells: int
    interior_cells: int
    isolated_dropped: int
    refusal_shares: dict                  # reason name -> share of ELIGIBLE cells that are UNKNOWN for that reason
    low_coverage_fallback: bool = False
    notes: list = field(default_factory=list)


def observe(scenes: list, reference: date, *, mode: str = "P") -> LakeObservation:
    """mode 'S' single nearest clear scene, 'A' accepted pass, 'P' persistence (median of >=3 accepted scenes; else A).
    No 'max' mode exists on purpose."""
    if mode not in ("S", "A", "P"):
        raise ValueError(f"mode {mode!r} is not allowed; forbidden composites: {C.FORBIDDEN_COMPOSITES}")
    sel = select_scenes(scenes, reference)
    if not sel["inWindow"]:
        return _empty("NO_SCENE")
    if mode == "S":
        clear = [s for s in sel["inWindow"] if s.cells.coverage() >= 0.0 and _seen_share(s) >= 0.75]
        if not clear:
            return _empty("PASS_NOT_ACCEPTED", note="no scene with >= 75 % of lake cells seen")
        s = clear[0]
        return _from_single(s, "SATELLITE_SINGLE_PASS", "NOT_APPLICABLE", 1)
    acc = sel["accepted"]
    if mode == "P" and len(acc) >= C.PERSISTENCE_MIN_SCENES:
        return _from_persistence(acc)
    if acc:
        best = acc[0]
        obs = _from_single(best, "SATELLITE_ACCEPTED_PASS", "INSUFFICIENT" if mode == "P" else "NOT_APPLICABLE", len(acc))
        if mode == "P":
            obs.notes.append(f"only {len(acc)} accepted scene(s); persistence needs {C.PERSISTENCE_MIN_SCENES}")
        return obs
    fb = sel["fallback"]
    if fb is not None:
        obs = _from_single(fb, "SATELLITE_ACCEPTED_PASS", "INSUFFICIENT" if mode == "P" else "NOT_APPLICABLE", 0)
        obs.low_coverage_fallback = True
        obs.notes.append("fallback pass: coverage between 25 % and 50 %; presence may be understated")
        return obs
    return _empty("PASS_NOT_ACCEPTED", note="no scene read >= 25 % of the interior cells")


def _seen_share(s: Scene) -> float:
    c = s.cells
    n = int(c.eligible.sum())
    return float((c.state[c.eligible] != UNKNOWN).sum()) / n if n else 0.0


def _empty(reason: str, note: str | None = None) -> LakeObservation:
    return LakeObservation("NONE", "NOT_APPLICABLE", [], None, None, None, None, 0, 0.0, 0, 0, 0, 0, {reason: 1.0},
                           notes=[note] if note else [])


def _finish(kind, pers, ids, when, cells, state, reason, n_acc, fallback=False) -> LakeObservation:
    plant = state == PLANT
    plant, dropped = _drop_isolated(plant)
    state = state.copy()
    state[(state == PLANT) & ~plant] = NO_PLANT
    interior = cells.interior
    read = interior & (state != UNKNOWN)
    elig = int(cells.eligible.sum())
    shares = {}
    for code, name in REASON_NAMES.items():
        k = int(((reason == code) & (state == UNKNOWN) & cells.eligible).sum())
        if k:
            shares[name] = k / max(elig, 1)
    return LakeObservation(kind, pers, ids, when, cells, state, reason, n_acc,
                           float(read.sum()) / max(int(interior.sum()), 1), int(plant.sum()), int(read.sum()),
                           int(interior.sum()), dropped, shares, fallback)


def _from_single(s: Scene, kind: str, pers: str, n_acc: int) -> LakeObservation:
    return _finish(kind, pers, [s.id], s.when, s.cells, s.cells.state, s.cells.reason, n_acc)


def _from_persistence(acc: list) -> LakeObservation:
    stack = np.stack([a.cells.plant_fraction for a in acc])           # NaN = unknown in that scene
    known = np.isfinite(stack)
    need = max(2, int(np.ceil(len(acc) / 2)))
    nk = known.sum(axis=0)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(np.where(known, stack, np.nan), axis=0)
    base = acc[0].cells
    state = np.full(base.shape, OUTSIDE, "int8")
    state[base.eligible] = UNKNOWN
    reason = np.zeros(base.shape, "int8")
    ok = base.eligible & (nk >= need)
    state[ok & (med >= C.PLANT_FRACTION_MIN)] = PLANT
    state[ok & (med < C.PLANT_FRACTION_MIN)] = NO_PLANT
    # cells with too little repeated evidence inherit the nearest accepted scene's state and reason
    lack = base.eligible & ~ok
    for a in acc:                                                     # nearest-first order
        take = lack & (a.cells.state != UNKNOWN)
        state[take] = a.cells.state[take]
        lack = lack & ~take
    reason_src = np.zeros(base.shape, "int8")
    for a in reversed(acc):
        reason_src = np.where(a.cells.reason > 0, a.cells.reason, reason_src)
    reason[state == UNKNOWN] = reason_src[state == UNKNOWN]
    reason[base.eligible & (state == UNKNOWN) & (reason == 0)] = REASON_CODES["INSUFFICIENT_VALID_PIXELS"]
    shore = base.eligible & ~base.interior
    state[shore] = UNKNOWN
    reason[shore] = REASON_CODES["SHORE_ADJACENT"]
    cells = CellScene(med.astype("float32"), state, reason, base.eligible, base.interior, base.shape)
    when = sorted(a.when for a in acc)[len(acc) // 2]
    return _finish("SATELLITE_PERSISTENCE", "MEDIAN_OF_ACCEPTED", [a.id for a in acc], when, cells, state, reason, len(acc))


# ------------------------------------------------------------------------------------- lake-level presence
def presence(obs: LakeObservation) -> tuple[str, str]:
    """-> (PRESENT | NOT_OBSERVED | UNKNOWN, reason). NOT_OBSERVED requires a genuine look, never a refusal."""
    if obs.evidence_kind == "NONE" or obs.cells is None:
        return "UNKNOWN", next(iter(obs.refusal_shares), "NO_SCENE")
    if obs.plant_cells >= MIN_PLANT_CELLS:
        return "PRESENT", "plant cells >= MIN_PLANT_CELLS"
    if obs.interior_cells and obs.read_cells / obs.interior_cells >= MIN_READ_FRACTION:
        return "NOT_OBSERVED", "interior read; fewer than MIN_PLANT_CELLS plant cells"
    return "UNKNOWN", "too little of the lake was read to say none"
