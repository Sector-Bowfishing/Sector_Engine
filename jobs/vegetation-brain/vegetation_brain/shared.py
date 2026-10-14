"""Consume the SHARED Clarity lake-surface pass evidence instead of reading Sentinel-2 again.

ONE PROVIDER INGESTION PATH, MULTIPLE SPECIALIST CONSUMERS. `jobs/lake-surface` already reads the scenes and writes, per pass, a small
JSON (`<date>.json`, ~4 KB: grassPct, measuredPct, fill.grassToBankPct, pass.sceneIds, ...) and a coded PNG (`<date>.measured.png`:
255 measured water, 3 grass bed, 2 cloud/haze, 1 unreadable, 0 off lake). Vegetation reads those; it opens no new scene, polls nothing and
adds no schedule. Pure functions: callers pass parsed JSON (and, optionally, PNG code counts); nothing here touches the network.

HONESTY: the shared grass class is the PRODUCTION rule (NDVI >= 0.30, cell vote 0.5), which is NOT validated, and it includes the
`bed-to-bank` strip that Clarity paints behind a bed. This module removes that strip (`fill.grassToBankPct`) from the observed share and flags it.
Single passes are never published."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from . import contract as C

CODE_MEASURED, CODE_GRASS, CODE_CLOUD_HAZE, CODE_UNREADABLE, CODE_OFF = 255, 3, 2, 1, 0
PASS_MIN_KNOWN_PCT = C.PASS_MIN_COVERAGE * 100          # 50
PASS_FALLBACK_KNOWN_PCT = C.PASS_FALLBACK_COVERAGE * 100  # 25


@dataclass
class SharedPass:
    when: date
    platform: str | None
    scene_ids: list
    grass_pct: float                      # share of lake cells in the grass class (includes the bed-to-bank strip)
    measured_pct: float | None            # share of lake cells measured as water
    grass_to_bank_pct: float | None       # the painted strip behind beds (not an observation)
    grass_under_cloud_pct: float | None
    code_shares: dict | None = None       # {255,3,2,1} shares of ON-LAKE cells (from the PNG) when available

    @property
    def known_pct(self) -> float:
        """Share of the lake actually looked at: measured water + grass (the satellite saw the plants)."""
        if self.code_shares:
            return 100.0 * (self.code_shares.get(CODE_MEASURED, 0.0) + self.code_shares.get(CODE_GRASS, 0.0))
        return (self.measured_pct or 0.0) + self.grass_pct

    @property
    def observed_grass_pct(self) -> float:
        return max(0.0, self.grass_pct - (self.grass_to_bank_pct or 0.0))


def _d(s) -> date:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date() if "T" in str(s) else date.fromisoformat(str(s))


def pass_from_clarity_json(d: dict, code_counts: dict | None = None) -> SharedPass:
    """d: a full per-pass `<date>.json`. code_counts: {255: n, 3: n, 2: n, 1: n, 0: n} from the measured PNG (optional)."""
    p = d["pass"]
    shares = None
    if code_counts:
        on = sum(v for k, v in code_counts.items() if int(k) != CODE_OFF)
        if on > 0:
            shares = {int(k): v / on for k, v in code_counts.items() if int(k) != CODE_OFF}
    fill = d.get("fill") or {}
    return SharedPass(_d(p["date"]), p.get("platform"), list(p.get("sceneIds") or []), float(d.get("grassPct") or 0.0),
                      d.get("measuredPct"), fill.get("grassToBankPct"), fill.get("grassUnderCloudPct"), shares)


@dataclass
class SharedObservation:
    evidence_kind: str
    persistence: str
    scene_ids: list
    observed_on: date | None
    n_accepted: int
    coverage: float                       # known share / 100
    observed_area_km2: float | None
    observed_share_pct: float | None
    shared_presence: tuple | None
    refusal_shares: dict
    low_coverage_fallback: bool = False
    notes: list = field(default_factory=list)
    source_id: str = C.SHARED_SOURCE_ID
    # duck-typed fields the state builder reads
    plant_cells: int | None = None
    read_cells: int | None = None
    interior_cells: int | None = None
    isolated_dropped: int = 0
    cells = None


def _drop_bursts(accepted: list) -> tuple[list, list]:
    if len(accepted) < 3:
        return accepted, []
    keep, dropped = [], []
    for i, a in enumerate(accepted):
        others = sorted(x.observed_grass_pct for j, x in enumerate(accepted) if j != i)
        med = others[len(others) // 2]
        if a.observed_grass_pct >= C.SHARED_BURST_MIN_PCT and a.observed_grass_pct > C.SHARED_BURST_FACTOR * max(med, 0.5):
            dropped.append(a)
        else:
            keep.append(a)
    return keep, dropped


def _refusals(passes: list) -> dict:
    """Dominant refusal shares from the PNG codes where available (cloud/haze code 2, unreadable code 1), else {}."""
    out: dict = {}
    sh = [p.code_shares for p in passes if p.code_shares]
    if not sh:
        return out
    out["CLOUD_OR_HAZE"] = sum(s.get(CODE_CLOUD_HAZE, 0.0) for s in sh) / len(sh)
    out["UNREADABLE_WATER"] = sum(s.get(CODE_UNREADABLE, 0.0) for s in sh) / len(sh)
    return {k: v for k, v in out.items() if v > 0}


def observe_shared(passes: list, reference: date, lake_area_km2: float | None, *, mode: str = "P") -> SharedObservation:
    """Same rules as the pixel observer, applied to lake-level shared evidence: window +-21 d, acceptance = known share >= 50 %
    (fallback >= 25 %, flagged), burst check, median persistence over >= 3 accepted passes, single un-accepted pass never published."""
    if mode not in ("A", "P"):
        raise ValueError("only accepted-pass (A) and persistence (P) modes exist; max composites are forbidden")
    win = sorted([p for p in passes if abs((p.when - reference).days) <= C.PERSISTENCE_WINDOW_DAYS], key=lambda p: abs((p.when - reference).days))
    if not win:
        return SharedObservation("NONE", "NOT_APPLICABLE", [], None, 0, 0.0, None, None, ("UNKNOWN", "NO_SCENE"), {"NO_SCENE": 1.0})
    acc = [p for p in win if p.known_pct >= PASS_MIN_KNOWN_PCT]
    acc, bursts = _drop_bursts(acc)
    notes = []
    if bursts:
        notes.append(f"excluded implausible burst pass(es): {[b.when.isoformat() for b in bursts]}")
    fallback = False
    if acc:
        use = acc
    else:
        cand = [p for p in win if p.known_pct >= PASS_FALLBACK_KNOWN_PCT]
        if not cand:
            return SharedObservation("NONE", "NOT_APPLICABLE", [], None, 0, 0.0, None, None, ("UNKNOWN", "PASS_NOT_ACCEPTED"),
                                     _refusals(win) or {"PASS_NOT_ACCEPTED": 1.0}, notes=notes)
        use, fallback = [max(cand, key=lambda p: (p.known_pct, -abs((p.when - reference).days)))], True
        notes.append("fallback pass: known share between 25 % and 50 %; presence may be understated")
    if mode == "P" and not fallback and len(use) >= C.PERSISTENCE_MIN_SCENES:
        vals = sorted(p.observed_grass_pct for p in use)
        share = vals[len(vals) // 2]
        kind, pers, ids, when = "SATELLITE_PERSISTENCE", "MEDIAN_OF_ACCEPTED", [i for p in use for i in p.scene_ids], sorted(p.when for p in use)[len(use) // 2]
        known = sum(p.known_pct for p in use) / len(use)
        used = use
    else:
        p0 = use[0]
        share, kind, pers = p0.observed_grass_pct, "SATELLITE_ACCEPTED_PASS", ("INSUFFICIENT" if mode == "P" else "NOT_APPLICABLE")
        ids, when, known, used = list(p0.scene_ids), p0.when, p0.known_pct, [p0]
        if mode == "P":
            notes.append(f"only {len(use)} accepted pass(es); persistence needs {C.PERSISTENCE_MIN_SCENES}")
        if len(use) < 3:
            notes.append("burst check needs >= 3 accepted passes; this pass could not be checked against its neighbours")
    area = None if lake_area_km2 is None else share / 100.0 * lake_area_km2
    if area is not None and area >= C.SHARED_MIN_AREA_KM2:
        pres = ("PRESENT", f"observed grass >= {C.SHARED_MIN_AREA_KM2} km2 after removing the bed-to-bank strip")
    elif known >= PASS_MIN_KNOWN_PCT and not fallback and area is not None:
        pres = ("NOT_OBSERVED", "lake looked at; observed grass below the minimum area")
    else:
        pres = ("UNKNOWN", "too little of the lake was looked at to say none" if area is not None else "lake area unknown")
    notes.append("shared Clarity grass class = production rule (unvalidated); bed-to-bank strip removed from the observed share")
    return SharedObservation(kind, pers, ids, when, len(use), known / 100.0, area, round(share, 2), pres, _refusals(used), fallback, notes)
