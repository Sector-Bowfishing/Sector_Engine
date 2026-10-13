"""Contour-derived depth zones, and how a level shift moves them. Only what the contours support.

Reference shares come from real contours (research data/contour_truth_lakes.csv): cumulative share of the SURVEYED surface
at depth < 3, < 6, < 10 ft at the survey reference pool. An edge is *supported* only if it is a multiple of the contour
interval, or the interval is <= 3 ft (measured interpolation RMS 0.28 ft at 1-2 ft intervals; 1.3 ft at 5 ft; 2.8 ft at 10 ft).
We never interpolate a fine edge out of a coarse interval: an unsupported edge is omitted, and a shifted edge that falls
between supported edges yields a BOUND (lo, hi), not a point.

Effective-zone arithmetic (reference pool surface, shift s = level - referencePool, s <= 0 means lower):
  a point with reference depth d now has depth d + s.
  dry            = S(-s)                      share of the reference surface now exposed (s < 0)
  wet and < X    = S(X - s) - S(-s);  wet in [a,b) = S(b - s) - S(a - s)
S is the cumulative share function. s > 0 (rising) never creates a point answer for the flooded margin: water that was
shore at the reference pool is not in the survey; that part is reported as `floodedMarginUnquantified`."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import contract as C
from .evidence import assert_allowed_use


@dataclass
class ReferenceZones:
    cumulative: dict                       # {edge_ft: share_of_surveyed_surface} for SUPPORTED edges only; edge 0 -> 0.0 implied
    interval_ft: float | None
    coverage: float | None                 # share of the lake surface the survey covers (0..1)
    tier: str                              # A | B | C
    source: str
    survey_year: int | None = None
    reference_pool_ft: float | None = None          # pool elevation the contour depths are measured from
    reference_pool_datum: str | None = None
    reference_status: str = "UNVERIFIED"            # VERIFIED | UNVERIFIED (is the survey reference pool known and datum-compatible?)
    flags: list = field(default_factory=list)


def supported_edges(interval_ft: float | None, edges=C.EDGES_FT) -> list[float]:
    """Edges (ft) the contour interval can resolve."""
    if not interval_ft or interval_ft <= 0:
        return []
    out = []
    for e in edges:
        if interval_ft <= C.MAX_INTERVAL_FOR_ARBITRARY_EDGE_FT or abs(e / interval_ft - round(e / interval_ft)) < 1e-9:
            out.append(float(e))
    return out


def reference_zones_from_shares(shares: dict, interval_ft, coverage, tier, source, *, survey_year=None, flags=None,
                                reference_pool_ft=None, reference_pool_datum=None, reference_verified=False) -> ReferenceZones | None:
    """shares: {'lt3': s03, 'lt6': ..., 'lt10': ...} cumulative shares of the surveyed surface. Unsupported edges are dropped."""
    sup = supported_edges(interval_ft)
    cum = {}
    for e in sup:
        key = f"lt{int(e)}"
        v = shares.get(key)
        if v is not None and 0.0 <= float(v) <= 1.0 + 1e-6:
            cum[e] = min(1.0, float(v))
    if not cum:
        return None
    last = None
    for e in sorted(cum):                        # cumulative must be non-decreasing; a violation means bad input -> refuse
        if last is not None and cum[e] + 1e-6 < last:
            return None
        last = cum[e]
    return ReferenceZones(cum, interval_ft, coverage, tier, source, survey_year, reference_pool_ft, reference_pool_datum,
                          "VERIFIED" if reference_verified else "UNVERIFIED", list(flags or []))


def _bounds(cum: dict, x: float) -> tuple[float, float]:
    """Bounds on S(x) given S at supported edges (monotone). x <= 0 -> (0,0). Beyond the last edge: [S(last), 1]."""
    if x <= 0:
        return 0.0, 0.0
    pts = [(0.0, 0.0)] + sorted(cum.items())
    lo = 0.0
    hi = 1.0
    for e, s in pts:
        if e <= x + 1e-9:
            lo = max(lo, s)
        if e >= x - 1e-9:
            hi = min(hi, s)
            break
    return lo, hi


def reference_state(z: ReferenceZones) -> dict:
    """Reference-condition shares, only for supported bands. Fields omitted when the interval cannot resolve the edge."""
    c = z.cumulative
    out = {}
    if 3.0 in c:
        out["shareUnder3Ft"] = round(c[3.0], 3)
    if 6.0 in c:
        out["shareUnder6Ft"] = round(c[6.0], 3)
    if 10.0 in c:
        out["shareUnder10Ft"] = round(c[10.0], 3)
        out["shareDeeper"] = round(max(0.0, 1.0 - c[10.0]), 3)
    if 3.0 in c and 6.0 in c:
        out["share3To6Ft"] = round(c[6.0] - c[3.0], 3)
    if 6.0 in c and 10.0 in c:
        out["share6To10Ft"] = round(c[10.0] - c[6.0], 3)
    return out


def effective_zones(z: ReferenceZones, shift_ft: float, sigma_ft: float) -> dict:
    """Shares of the REFERENCE surface now dry / in each band, as (lo, hi) bounds across shift +- sigma.

    Refuses (returns {'available': False, reason}) unless the survey reference pool is verified and datum-compatible."""
    if z.reference_status != "VERIFIED":
        return {"available": False, "reason": "SURVEY_REFERENCE_POOL_UNVERIFIED"}
    c = z.cumulative
    grid = [shift_ft + sigma_ft * (i / 4.0) for i in range(-4, 5)]
    edges = [e for e in C.EDGES_FT]
    bands = [("under3", 0.0, 3.0), ("threeToSix", 3.0, 6.0), ("sixToTen", 6.0, 10.0)]
    agg: dict = {}

    def upd(key, lo, hi):
        lo = max(0.0, lo); hi = min(1.0, max(lo, hi))
        cur = agg.get(key)
        agg[key] = (lo, hi) if cur is None else (min(cur[0], lo), max(cur[1], hi))

    for s in grid:
        dry_lo, dry_hi = _bounds(c, -s) if s < 0 else (0.0, 0.0)
        upd("dry", dry_lo, dry_hi)
        for name, a, b in bands:                 # wet share with effective depth in [a, b): S(b - s) - S(a - s); the dry part cancels
            a_lo, a_hi = _bounds(c, a - s)
            b_lo, b_hi = _bounds(c, b - s)
            upd(name, b_lo - a_hi, b_hi - a_lo)
        lo10, hi10 = _bounds(c, 10.0 - s)
        d_lo, d_hi = (1.0 - hi10, 1.0 - lo10)
        upd("deeper", d_lo, d_hi)
    out = {"available": True, "basis": "share of the reference-pool surveyed surface", "shiftFt": round(shift_ft, 1),
           "shares": {k: {"lo": round(v[0], 3), "hi": round(v[1], 3)} for k, v in agg.items()},
           "resolution": "bounds: the shifted edge falls between supported contour levels" if any(
               round(v[1] - v[0], 3) > 0.02 for v in agg.values()) else "point-like"}
    if shift_ft > 0:
        out["floodedMarginUnquantified"] = True
    return out


def forbid_modeled_zones(source_kind: str) -> None:
    """Called wherever a zone/share is about to be built from a non-contour source."""
    assert_allowed_use(source_kind, "zone_shares")
