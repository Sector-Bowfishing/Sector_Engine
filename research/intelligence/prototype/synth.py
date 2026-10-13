"""Research prototype: deterministic, species-first, confidence-aware bowfishing synthesis.

RESEARCH ONLY. Not production code, not imported by anything. Stdlib only.

What it is: the smallest rule set that can answer WHERE / WHEN / WHAT / WHY / HOW SURE from specialist
Brain states without inventing any input. Intelligence owns the *combination*; it owns no water-temperature,
clarity, wind, depth or vegetation science. Every factor arrives as a record carrying its source Brain, kind,
age and spatial support; this module only maps a restated value into an ordinal state with a species response
band and then combines ordinal states.

Species response bands are Biological-Brain-owned inputs. The STUB profiles at the bottom exist ONLY to exercise
the logic in tests; their numbers are NOT evidence and make no biological claim.

Rules (each is tested in tests/test_synth.py):
  R1  UNKNOWN never improves a rating (property, exhaustive).
  R2  Safety/legal gates are species-independent and override everything.
  R3  A BLOCKING critical factor makes the zone POOR for that species; no other factor can offset it.
  R4  Top class (START_HERE) requires every critical factor KNOWN and none LIMITING.
  R5  Confidence is the weakest critical factor (min), never a sum or mean. Agreement adds nothing.
  R6  Stale evidence lowers a factor one level; lake-wide support for an area decision caps it at MEDIUM.
  R7  Beyond a specialist's forecast horizon a factor is UNKNOWN. No persistence is passed off as forecast.
  R9  The top class also needs confidence >= MEDIUM; otherwise it is shown as WORTH_A_LOOK with the reason.
  R8  Every explanation line is a template over a factor record; nothing is free text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

# ----------------------------------------------------------------------------- vocabularies
STATES = ("BLOCKING", "LIMITING", "WORKABLE", "FAVORABLE")          # ordinal low -> high; UNKNOWN handled apart
KINDS = ("MEASURED", "OBSERVED", "MODELED", "PROXY", "FORECAST", "NONE")
CONF = ("INSUFFICIENT", "LOW", "MEDIUM", "HIGH")                     # ordinal low -> high
RATINGS = ("NOT_TONIGHT", "POOR", "UNRANKED", "LOW_PRIORITY", "WORTH_A_LOOK", "START_HERE")
SUPPORT = ("BANK_AREA", "LAKE", "POINT", "NONE")
BASE_CONF_BY_KIND = {"MEASURED": 3, "OBSERVED": 3, "MODELED": 2, "FORECAST": 2, "PROXY": 1, "NONE": 0}


@dataclass(frozen=True)
class Factor:
    """One specialist Brain's restated value for one zone. Built from a published Brain state, never computed here."""
    fid: str                      # 'waterTemp', 'clarity', 'wind', 'depth', 'vegetation', 'lake'
    source: str                   # 'water-temp@wt-1.2' (brain@version) for traceability
    value: Optional[float]        # restated value, None when the Brain does not know
    unit: str = ""
    kind: str = "NONE"
    support: str = "NONE"
    age_h: Optional[float] = None
    stale_after_h: Optional[float] = None
    lead_h: float = 0.0           # how far ahead this value is being used
    horizon_h: Optional[float] = None   # the Brain's own forecast horizon (None = current-state only)
    brain_confidence: Optional[str] = None   # the Brain's own label if it publishes one (cap, never raise)

    @property
    def stale(self) -> bool:
        return self.stale_after_h is not None and self.age_h is not None and self.age_h > self.stale_after_h

    @property
    def known(self) -> bool:
        if self.value is None or self.kind == "NONE":
            return False
        if self.lead_h > 0 and (self.horizon_h is None or self.lead_h > self.horizon_h):
            return False                                                      # R7
        return True


@dataclass(frozen=True)
class Gate:
    gid: str
    reason: str
    source: str


@dataclass
class SpeciesProfile:
    species: str
    critical: tuple                                   # factor ids that decide where this species is
    supporting: tuple
    bands: dict                                       # fid -> fn(value)->state
    stub: bool = True


@dataclass
class ZoneResult:
    zone: str
    species: str
    rating: str
    confidence: str
    states: dict
    best: list
    limiting: list
    unknown: list
    freshness: list
    explanation: list
    caveats: list = field(default_factory=list)


def effective_conf(f: Factor, area_decision: bool = True) -> int:
    """R5/R6: confidence level index for one factor. Never raised by anything else."""
    if not f.known:
        return 0
    c = BASE_CONF_BY_KIND[f.kind]
    if f.stale:
        c -= 1
    if area_decision and f.support in ("LAKE", "POINT"):
        c = min(c, 2)
    if f.lead_h > 0:
        c = min(c, 2)
    if f.brain_confidence in CONF:
        c = min(c, CONF.index(f.brain_confidence))
    return max(c, 0)


def rate(profile: SpeciesProfile, factors: dict, gates: list) -> tuple[str, dict]:
    """Return (rating, per-factor state). UNKNOWN is stored as None."""
    states = {}
    for fid in profile.critical + profile.supporting:
        f = factors.get(fid)
        band = profile.bands.get(fid)
        states[fid] = band(f.value) if (f is not None and f.known and band) else None
    if gates:
        return "NOT_TONIGHT", states                                           # R2
    crit = [states[x] for x in profile.critical]
    if any(s == "BLOCKING" for s in crit):
        return "POOR", states                                                   # R3
    unk = sum(1 for s in crit if s is None)
    if unk == len(crit) or (unk >= 2 and unk * 2 >= len(crit)):
        return "UNRANKED", states               # too little is known to say anything; shown as such, never as 'poor'
    # R1: for the rating an unknown deciding factor counts as LIMITING (pessimistic bound), and is flagged unconfirmed
    lim = sum(1 for s in crit if s == "LIMITING") + unk
    fav = sum(1 for s in crit if s == "FAVORABLE")
    sup = [states[x] for x in profile.supporting if states[x] is not None]
    sup_bad = any(s in ("BLOCKING", "LIMITING") for s in sup)
    if lim >= 2:
        return "LOW_PRIORITY", states
    if lim == 1:
        return ("WORTH_A_LOOK" if (fav >= 1 and not sup_bad) else "LOW_PRIORITY"), states
    if fav == len(crit) and not sup_bad:
        return "START_HERE", states                                             # R4 (unk==0 implied since lim==0)
    return "WORTH_A_LOOK", states


def confidence(profile: SpeciesProfile, factors: dict) -> tuple[str, dict]:
    per = {x: effective_conf(factors[x]) if x in factors else 0 for x in profile.critical}
    lo = min(per.values()) if per else 0                                        # R5: weakest link
    return CONF[lo], per


def _fmt(f: Factor) -> str:
    return f"{f.value:g}{(' ' + f.unit) if f.unit else ''}"


def evaluate_zone(zone: str, profile: SpeciesProfile, factors: dict, gates: list | None = None) -> ZoneResult:
    gates = gates or []
    rating, states = rate(profile, factors, gates)
    conf, per = confidence(profile, factors)
    capped = False
    if rating == "START_HERE" and CONF.index(conf) < CONF.index("MEDIUM"):
        rating, capped = "WORTH_A_LOOK", True                                    # R9
    best, limiting, unknown, fresh, caveats = [], [], [], [], []
    for fid in profile.critical + profile.supporting:
        f = factors.get(fid)
        st = states.get(fid)
        if f is None or not f.known:
            why = "beyond forecast horizon" if (f is not None and f.value is not None and f.lead_h > 0) else "not published"
            unknown.append({"factor": fid, "text": f"{fid}: unknown ({why})", "source": f.source if f else None})
            continue
        line = {"factor": fid, "text": f"{fid} {_fmt(f)} ({f.kind.lower()}, {f.support.lower()})", "source": f.source}
        if st in ("FAVORABLE", "WORKABLE"):
            if st == "FAVORABLE":
                best.append(line)
        else:
            limiting.append(line)
        if f.age_h is not None:
            fresh.append({"factor": fid, "text": f"{fid} {f.age_h:g} h old" + (" — STALE" if f.stale else ""), "source": f.source})
        if f.support in ("LAKE", "POINT"):
            caveats.append(f"{fid} is {f.support.lower()}-level, not specific to this zone")
    for g in gates:
        limiting.insert(0, {"factor": g.gid, "text": g.reason, "source": g.source})
    if capped:
        caveats.append("would rate START_HERE but the weakest deciding factor is too uncertain to say so")
    if any(x["factor"] in profile.critical for x in unknown) and rating == "WORTH_A_LOOK":
        caveats.append("promising but unconfirmed: a deciding factor is unknown")
    expl = []                                                                    # R8: templates only
    expl += [f"BEST: {b['text']} [{b['source']}]" for b in best]
    expl += [f"LIMITING: {l['text']} [{l['source']}]" for l in limiting]
    expl += [f"UNKNOWN: {u['text']}" for u in unknown]
    expl += [f"FRESHNESS: {x['text']}" for x in fresh]
    expl.append(f"CONFIDENCE: {conf} (weakest deciding factor: " +
                (min(per, key=per.get) if per else "none") + ")")
    return ZoneResult(zone, profile.species, rating, conf, states, best, limiting, unknown, fresh, expl, caveats)


def rank_zones(profile: SpeciesProfile, zones: dict, gates: list | None = None) -> list:
    """zones: {name: {fid: Factor}}. Ordinal sort by rating, then confidence, then more FAVORABLE. No blended number."""
    out = [evaluate_zone(z, profile, f, gates) for z, f in zones.items()]
    def key(r):
        fav = sum(1 for s in r.states.values() if s == "FAVORABLE")
        return (RATINGS.index(r.rating), CONF.index(r.confidence), fav)
    return sorted(out, key=key, reverse=True)


def species_first(profiles: list, present: set, zones: dict, gates: list | None = None) -> dict:
    """Run only for species present on the lake AND with a profile; others are reported as NOT_ASSESSED, never guessed."""
    res, not_assessed = {}, []
    have = {p.species: p for p in profiles}
    for sp in sorted(present):
        if sp in have:
            res[sp] = rank_zones(have[sp], zones, gates)
        else:
            not_assessed.append(sp)
    return {"ranked": res, "notAssessed": not_assessed}


def trend(ratings_by_checkpoint: list) -> str:
    """IMPROVING / STEADY / WORSENING from >=2 checkpoints whose critical factors were all known; else UNKNOWN."""
    r = [x for x in ratings_by_checkpoint if x is not None]
    if len(r) < 2:
        return "UNKNOWN"
    d = RATINGS.index(r[-1]) - RATINGS.index(r[0])
    return "IMPROVING" if d > 0 else ("WORSENING" if d < 0 else "STEADY")


# ----------------------------------------------------------------------------- TEST STUB profiles (not evidence)
def _band(cuts: list[tuple[float, str]], top: str) -> Callable[[float], str]:
    def f(v: float) -> str:
        for ub, s in cuts:
            if v < ub:
                return s
        return top
    return f

STUB_SHALLOW_VEG_FEEDER = SpeciesProfile(
    species="stub_shallow_veg_feeder", critical=("waterTemp", "depth", "vegetation", "wind"), supporting=("clarity",),
    bands={"waterTemp": _band([(50, "BLOCKING"), (60, "LIMITING"), (66, "WORKABLE"), (84, "FAVORABLE")], "WORKABLE"),
           "depth": _band([(1.0, "FAVORABLE"), (3.0, "WORKABLE"), (6.0, "LIMITING")], "BLOCKING"),     # effective depth ft
           "vegetation": _band([(0.1, "LIMITING"), (0.3, "WORKABLE")], "FAVORABLE"),
           "wind": _band([(3, "FAVORABLE"), (8, "WORKABLE"), (14, "LIMITING")], "BLOCKING"),          # exposure-adjusted mph
           "clarity": _band([(1.0, "BLOCKING"), (2.0, "LIMITING"), (3.0, "WORKABLE")], "FAVORABLE")})

STUB_OPEN_WATER_EDGE = SpeciesProfile(
    species="stub_open_water_edge", critical=("waterTemp", "clarity", "wind"), supporting=("depth",),
    bands={"waterTemp": _band([(60, "BLOCKING"), (64, "LIMITING"), (70, "WORKABLE")], "FAVORABLE"),
           "clarity": _band([(1.5, "BLOCKING"), (2.5, "LIMITING"), (4.0, "WORKABLE")], "FAVORABLE"),
           "wind": _band([(4, "FAVORABLE"), (10, "WORKABLE"), (16, "LIMITING")], "BLOCKING"),
           "depth": _band([(2.0, "LIMITING"), (10.0, "FAVORABLE")], "WORKABLE")})
