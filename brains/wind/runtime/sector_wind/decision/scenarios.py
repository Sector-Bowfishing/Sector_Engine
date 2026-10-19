"""Bowfishing capability scenarios (Layer 3: Learning & Validation). Deterministic acceptance checks of the decision layer.

Every scenario runs the REAL runtime interfaces (`build.build`, `ranking.rank`, `timeline.timeline`, frozen `bowfishing`) on a
REAL lake fetch table. All winds are SYNTHETIC and labelled so; no observed outcome is used or invented. A pass shows the
Brain BEHAVES as a bowfishing wind decision should (MODEL_CAPABILITY); it is never evidence that a real bank looked like this
(OBSERVED_ACCURACY). Scientific Confidence never counts these results as validation.

Banks are chosen from the geometry by rule (not hand-picked), so the same suite runs on any lake:
  exposed / sheltered pair: longest and shortest effective fetch for the scenario direction (audit pair on Guntersville);
  flip pair: open to one direction and sheltered from its reverse, and vice versa.

  python -m sector_wind.decision scenarios --fetch FETCH.json.gz --lake "Guntersville|AL"
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from .. import bowfishing as BF
from ..brain import contract as C
from . import build as B
from . import ranking as R
from . import schema as SC
from . import semantics as S
from . import timeline as T

SUITE_ID = "wind-bowfishing-scenarios-v1"
NOW = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)      # fixed evaluation clock (determinism)
DIR = 225.0
AUDIT_PAIR = {"Guntersville|AL": ("GT-005719", "GT-001172")}
ORDER = ("PROTECTED", "LOW_EXPOSURE", "MODERATE_EXPOSURE", "HIGH_EXPOSURE", "EXTREME_EXPOSURE")
CAPABILITY = {   # scenario -> Bowfishing Intelligence V2 capability item it evidences (rubric: docs/brains/scoring/wind-bowfishing-intelligence-v2.json)
    "S01": "GI3", "S02": "GI3", "S06": "GI3", "S03": "SI3", "S10": "SI3", "S17": "SI3", "S16": "DI2", "S18": "DI2",
    "S11": "DI3", "S05": "TI1", "S04": "TI2", "S14": "TI2", "S07": "UM1", "S08": "UM1", "S09": "UM1", "S15": "UM1",
    "S12": "UM2", "S13": "UM2",
}


def _w(mph, d=DIR, dur=BF.STEADY_H, gust=None):
    return B.synthetic_wind(mph, d, dur, gust, label=f"{mph} mph from {d} deg, {dur} h")


def _ok(L):
    return [i for i, b in enumerate(L["banks"]) if not b.get("belowResolution")]


def pair(L, d=DIR):
    ap = AUDIT_PAIR.get(L["lakeId"])
    ix = {b["id"]: i for i, b in enumerate(L["banks"])}
    if ap and all(a in ix for a in ap):
        return ap
    ok = _ok(L)
    eff = sorted(ok, key=lambda i: BF.nine_ray(L["table"][i], d))
    return L["banks"][eff[-1]]["id"], L["banks"][eff[0]]["id"]


def flip_pair(L, d=DIR):
    """A: most open to d relative to d+180; B: the reverse. Both resolvable."""
    ok = _ok(L)
    r = lambda i, t: BF.nine_ray(L["table"][i], t)
    a = max(ok, key=lambda i: r(i, d) / max(r(i, (d + 180) % 360), 10))
    b = max(ok, key=lambda i: r(i, (d + 180) % 360) / max(r(i, d), 10))
    return L["banks"][a]["id"], L["banks"][b]["id"]


def _bank(dec, bid):
    return next(x for x in dec["shorelines"]["requested"] if x["bankId"] == bid)


def _ex(b):
    return ORDER.index(b["windExposure"]["code"]) if b["windExposure"]["code"] in ORDER else -1


def _check(name, cond, detail):
    return {"check": name, "pass": bool(cond), "detail": detail}


def _hours(seq, start=NOW):
    """seq: [(mph, dir)] -> synthetic hourly trip input."""
    return [{"at": C.iso(start + timedelta(hours=k)), "speedMS": m * BF.MPH, "dirFromDeg": d, "gustMS": None, "kind": "synthetic",
             "leadHours": None} for k, (m, d) in enumerate(seq)]


# ── scenarios ──────────────────────────────────────────────────────────────────────────────────

def s01(L):
    a, b = pair(L)
    d = B.build(L["lakeId"], _w(12), L, NOW, bank_ids=(a, b))
    A, Bk = _bank(d, a), _bank(d, b)
    return [_check("exposed bank ranks more exposed", _ex(A) > _ex(Bk), f"{a} {A['windExposure']['code']} vs {b} {Bk['windExposure']['code']}"),
            _check("exposed bank waves >= 3x sheltered", A["predictedSurface"]["waveHeightIn"] >= 3 * max(Bk["predictedSurface"]["waveHeightIn"], 0.1),
                   f"{A['predictedSurface']['waveHeightIn']} vs {Bk['predictedSurface']['waveHeightIn']} in"),
            _check("sheltered bank is Sheltered/Low", Bk["windExposure"]["code"] in S.SHELTERED, Bk["windExposure"]["code"]),
            _check("both explained", bool(A["explanation"]) and bool(Bk["explanation"]), "explanations present")]


def s02(L):
    a, b = flip_pair(L)
    d1 = B.build(L["lakeId"], _w(12, DIR), L, NOW, bank_ids=(a, b))
    d2 = B.build(L["lakeId"], _w(12, (DIR + 180) % 360), L, NOW, bank_ids=(a, b))
    w1 = _bank(d1, a)["predictedSurface"]["waveHeightIn"] > _bank(d1, b)["predictedSurface"]["waveHeightIn"]
    w2 = _bank(d2, b)["predictedSurface"]["waveHeightIn"] > _bank(d2, a)["predictedSurface"]["waveHeightIn"]
    # QA definition (BWIS v1): ordering-pass rate over pairs with >= 20 % fetch contrast in both reversed directions (deterministic sample)
    ok = _ok(L)[::max(1, len(_ok(L)) // 120)]
    n = good = 0
    for i in ok[:120]:
        for j in ok[1:121]:
            if i == j:
                continue
            f = lambda k, t: BF.nine_ray(L["table"][k], t)
            if f(i, DIR) >= 1.2 * f(j, DIR) and f(j, DIR + 180) >= 1.2 * f(i, DIR + 180):
                n += 1
                h = lambda k, t: BF.cem(12 * BF.MPH, f(k, t), BF.STEADY_H * 3600)
                good += h(i, DIR) >= h(j, DIR) and h(j, DIR + 180) >= h(i, DIR + 180)
            if n >= 400:
                break
        if n >= 400:
            break
    return [_check("bank A exposed to SW, sheltered from NE", w1, f"{a} vs {b} at {DIR:g} deg"),
            _check("bank B exposed to NE, sheltered from SW", w2, f"{b} vs {a} at {(DIR + 180) % 360:g} deg"),
            _check("ordering flips with direction (pair sample)", n > 0 and good == n, f"{good}/{n} contrast pairs ordered correctly")]


def s03(L):
    a, _ = pair(L)
    calm = B.build(L["lakeId"], _w(0.5), L, NOW, bank_ids=(a,))
    strong = B.build(L["lakeId"], _w(20), L, NOW, bank_ids=(a,))
    c, s = _bank(calm, a), _bank(strong, a)
    return [_check("calm: exposed bank still Sheltered and Flat", c["windExposure"]["code"] == "PROTECTED" and c["predictedSurface"]["class"] == 1,
                   f"{c['windExposure']['code']} / {c['predictedSurface']['label']}"),
            _check("calm: no bank highly exposed", calm["lakeSummary"]["exposedPct"] == 0, f"exposed {calm['lakeSummary']['exposedPct']}%"),
            _check("20 mph: exposed bank High/Extreme", s["windExposure"]["code"] in S.EXPOSED, s["windExposure"]["code"]),
            _check("20 mph: fishing impact poor or worse", s["fishingImpact"]["code"] in ("POOR", "VERY_POOR"), s["fishingImpact"]["code"]),
            _check("20 mph: confidence LOW", strong["confidence"]["level"] == "LOW", strong["confidence"]["reasons"][0])]


def s04(L):
    a, b = flip_pair(L)
    trip = _hours([(12, DIR)] * 4 + [(12, (DIR + 180) % 360)] * 4)
    d = B.build(L["lakeId"], _w(12), L, NOW, bank_ids=(a, b), trip_hours=trip, prior_hours=_hours([(12, DIR)] * 6, NOW - timedelta(hours=6)))
    tb = {x["bankId"]: x for x in d["trip"]["banks"]}
    ev = [e for e in d["trip"]["events"] if e["type"] == "DIRECTION_SHIFT"]
    ha, hb = tb[a]["hours"], tb[b]["hours"]
    return [_check("direction shift reported", len(ev) == 1, ev[0]["text"] if ev else "none"),
            _check("bank A calms after the shift", ha[-1]["waveHeightIn"] < ha[0]["waveHeightIn"], f"{ha[0]['waveHeightIn']} -> {ha[-1]['waveHeightIn']} in"),
            _check("bank B roughens after the shift", hb[-1]["waveHeightIn"] > hb[0]["waveHeightIn"], f"{hb[0]['waveHeightIn']} -> {hb[-1]['waveHeightIn']} in"),
            _check("exposure change listed for a flipped bank", bool(tb[a]["changes"] or tb[b]["changes"]), f"{tb[a]['changes']} / {tb[b]['changes']}")]


def s05(L):
    a, _ = pair(L)
    i = {b["id"]: k for k, b in enumerate(L["banks"])}[a]
    hs = [BF.evaluate_bank(L, i, 12 * BF.MPH, DIR, h)["predictedHm0M"] for h in (0.5, 1, 2, 3, 6, 12)]
    trip = _hours([(12, DIR)] * 8)
    d = B.build(L["lakeId"], _w(12), L, NOW, bank_ids=(a,), trip_hours=trip)          # no prior history: waves build from the start
    seq = [x["waveHeightIn"] for x in d["trip"]["banks"][0]["hours"]]
    return [_check("waves never shrink with longer steady wind", all(x <= y + 1e-9 for x, y in zip(hs, hs[1:])), str([round(h / 0.0254, 1) for h in hs])),
            _check("waves saturate at the fetch limit", abs(hs[-1] - hs[-2]) <= 0.01 * hs[-1] + 1e-6, f"6 h {hs[-2] / 0.0254:.1f} in, 12 h {hs[-1] / 0.0254:.1f} in"),
            _check("trip timeline builds then holds", all(x <= y for x, y in zip(seq, seq[1:])) and seq[-1] > seq[0], str(seq)),
            _check("missing prior history disclosed", "UNDER-estimated" in d["trip"]["durationBasis"], d["trip"]["durationBasis"][:60])]


def s06(L):
    d = B.build(L["lakeId"], _w(12), L, NOW, top=10)
    ok = _ok(L)
    eff = sorted(ok, key=lambda i: BF.nine_ray(L["table"][i], DIR))
    k = max(1, len(eff) // 10)
    short = [BF.evaluate_bank(L, i, 12 * BF.MPH, DIR)["exposureRank"] for i in eff[:k]]
    long_ = [BF.evaluate_bank(L, i, 12 * BF.MPH, DIR)["exposureRank"] for i in eff[-k:]]
    sh, ex = d["shorelines"]["sheltered"], d["shorelines"]["exposed"]
    return [_check("shortest-fetch tenth all Sheltered/Low", all(x in S.SHELTERED for x in short), f"{sum(x in S.SHELTERED for x in short)}/{k}"),
            _check("longest-fetch tenth all Moderate or worse", all(ORDER.index(x) >= 2 for x in long_), f"{sum(ORDER.index(x) >= 2 for x in long_)}/{k}"),
            _check("listed sheltered banks have shorter fetch than listed exposed", bool(sh) and bool(ex) and
                   max(b["fetch"]["effectiveM"] for b in sh) < min(b["fetch"]["effectiveM"] for b in ex), f"{len(sh)} sheltered, {len(ex)} exposed listed"),
            _check("bounded output", len(sh) <= 10 and len(ex) <= 10 and "fullRanking" not in d, "top-N only")]


def s07(L):
    g = B.build(L["lakeId"], _w(12), None, NOW)
    u = B.build("Lake St. Clair|MI", _w(12), None, NOW, supported=False)
    return [_check("missing geometry -> GEOMETRY_UNAVAILABLE, no banks", g["status"] == "GEOMETRY_UNAVAILABLE" and g["shorelines"] is None, g["status"]),
            _check("unsupported lake -> UNSUPPORTED_LAKE, no banks", u["status"] == "UNSUPPORTED_LAKE" and u["shorelines"] is None, u["status"]),
            _check("no confidence claimed", g["confidence"]["level"] == u["confidence"]["level"] == "UNKNOWN", "UNKNOWN")]


def s08(L):
    nw = B.build(L["lakeId"], B.synthetic_wind(None, None), L, NOW)
    nd = B.build(L["lakeId"], B.synthetic_wind(10, None), L, NOW)
    unk = [b["id"] for b in L["banks"] if b.get("belowResolution")][:1]
    out = [_check("no wind speed -> WIND_UNAVAILABLE", nw["status"] == "WIND_UNAVAILABLE" and nw["shorelines"] is None, nw["status"]),
           _check("no direction at 10 mph -> DIRECTION_UNKNOWN", nd["status"] == "DIRECTION_UNKNOWN" and nd["shorelines"] is None, nd["status"])]
    if unk:
        d = B.build(L["lakeId"], _w(12), L, NOW, bank_ids=tuple(unk), top=25)
        rb = _bank(d, unk[0])
        out.append(_check("below-resolution bank is UNKNOWN, never sheltered",
                          rb["windExposure"]["code"] == "UNKNOWN" and unk[0] not in [b["bankId"] for b in d["shorelines"]["sheltered"]], rb["windExposure"]["code"]))
    return out


def _state(stale, lead=3, mph=8.0, kind="forecast"):
    """A minimal `sector-brain-wind-state-v1` shaped as brain.state.build_state emits it (SYNTHETIC values)."""
    init = NOW - timedelta(hours=lead)
    return {"stateSchema": C.STATE_SCHEMA, "kind": kind, "sustainedMph": mph, "gustMph": mph + 4, "directionDeg": DIR,
            "hourly": [{"at": C.iso(NOW + timedelta(hours=k)), "mph": mph, "gustMph": mph + 4, "dirDeg": DIR, "leadHours": lead + k} for k in range(4)],
            "forecastGeneratedAt": C.iso(init), "stale": stale, "staleReasons": ["forecastCycleStale:5.0h>3h"] if stale else [],
            "surfaceState": None, "analysis": None,
            "provenance": {"generatedAt": C.iso(NOW), "sources": [{"sourceId": "NOAA:NBM:v5.0 (SYNTHETIC test values)"}]}}


def s09(L):
    st = B.build(L["lakeId"], B.wind_from_state(_state(True)), L, NOW)
    fr = B.build(L["lakeId"], B.wind_from_state(_state(False)), L, NOW)
    return [_check("stale forecast -> INPUT_STALE, no banks", st["status"] == "INPUT_STALE" and st["shorelines"] is None, st["explanation"][:80]),
            _check("fresh forecast -> READY", fr["status"] == "READY", fr["status"]),
            _check("forecast labelled as forecast", fr["wind"]["kind"] == "forecast" and any(x["id"] == "FORECAST_INPUT" for x in fr["limitations"]), fr["wind"]["kind"])]


def s10(L):
    probs, n = [], 0
    for mph in (5, 10, 15, 20):
        for d in (45, 135, 225, 315):
            r = R.rank(L, mph * BF.MPH, d, top=25, bank_ids=tuple(b["id"] for b in L["banks"][:: max(1, len(L["banks"]) // 150)]))
            for b in r["requested"] + r["sheltered"] + r["exposed"]:
                n += 1
                probs += [f"{b['bankId']}@{mph}/{d}: {p}" for p in SC.check_bank(b)]
    bounds = [(h, BF.chop_class(h)) for h in (0.0253, 0.0254, 0.0761, 0.0762, 0.1523, 0.1524, 0.3047, 0.3048)]
    a, b = pair(L)
    d15 = B.build(L["lakeId"], _w(15), L, NOW, bank_ids=(b,))
    sb = _bank(d15, b)
    return [_check("exposure/surface semantics consistent on every shown bank", not probs and n > 0, f"{n} bank results, {len(probs)} problems {probs[:2]}"),
            _check("class bounds exactly 1/3/6/12 in", [c for _, c in bounds] == [1, 2, 2, 3, 3, 4, 4, 5], str(bounds)),
            _check("audit case: sheltered bank with wind texture is explained, not contradictory",
                   sb["windExposure"]["code"] != "PROTECTED" or sb["predictedSurface"]["driver"] == "WIND_TEXTURE" or sb["predictedSurface"]["class"] == 1,
                   f"{sb['windExposure']['label']} / {sb['predictedSurface']['label']} ({sb['predictedSurface']['driver']})"),
            _check("surface label never reuses an exposure word", "Protected" not in S.SURFACE_LABEL.values() and "Sheltered" not in S.SURFACE_LABEL.values(),
                   str(list(S.SURFACE_LABEL.values())))]


def s11(L):
    d = B.build(L["lakeId"], _w(15), L, NOW, top=5)
    ex = d["shorelines"]["exposed"]
    if not ex:
        return [_check("an exposed bank exists at 15 mph", False, "none")]
    top = ex[0]
    alts, near = top.get("lessExposedAlternatives", []), top.get("nearestSheltered", [])
    by = {r["bankId"]: r for r in BF.rank_banks_for_wind(L, 15 * BF.MPH, DIR, top=1)["all"]}
    t = by[top["bankId"]]
    rule = all(by[a["bankId"]]["predictedSurfaceClass"] < t["predictedSurfaceClass"] or
               (by[a["bankId"]]["effectiveFetchM"] <= 0.5 * t["effectiveFetchM"] and by[a["bankId"]]["predictedSurfaceClass"] <= t["predictedSurfaceClass"]) for a in alts)
    return [_check("frozen alternative rule holds", rule and all(a["distanceM"] <= a["searchRadiusM"] for a in alts), f"{len(alts)} alternatives"),
            _check("nearest sheltered are Sheltered/Low, within 10 km, nearest first",
                   bool(near) and all(x["windExposure"]["code"] in S.SHELTERED and x["distanceM"] <= R.SHELTER_RADIUS_M for x in near) and
                   [x["distanceM"] for x in near] == sorted(x["distanceM"] for x in near), f"{[(x['bankId'], x['distanceM']) for x in near]}"),
            _check("access caveat on every alternative", all("not checked for fish, access" in x["note"] for x in alts + near), "caveat present"),
            _check("headline names a real sheltered bank", (near[0]["bankId"] in d["explanation"]) if near else False, d["explanation"][-160:])]


def s12(L):
    s3 = B.build(L["lakeId"], B.wind_from_state(_state(False, lead=3)), L, NOW, bank_ids=pair(L))
    s18 = B.build(L["lakeId"], B.wind_from_state(_state(False, lead=18)), L, NOW, bank_ids=pair(L))
    same = [(x["bankId"], x["predictedSurface"]) for x in s3["shorelines"]["requested"]] == [(x["bankId"], x["predictedSurface"]) for x in s18["shorelines"]["requested"]]
    return [_check("lead 3 h: no long-lead limitation", not any(x["id"] == "LONG_LEAD" for x in s3["limitations"]), s3["confidence"]["level"]),
            _check("lead 18 h: long-lead limitation and LOW confidence", any(x["id"] == "LONG_LEAD" for x in s18["limitations"]) and s18["confidence"]["level"] == "LOW",
                   s18["confidence"]["reasons"][0]),
            _check("lead changes confidence, not physics", same, "same wind -> same banks")]


def s13(L):
    light = B.build(L["lakeId"], B.wind_from_state(_state(False, mph=7.0)), L, NOW)
    strong = B.build(L["lakeId"], B.wind_from_state(_state(False, mph=17.0)), L, NOW)
    has = lambda d, i: any(x["id"] == i for x in d["limitations"])
    return [_check("strong-wind limitation present even on a light forecast", has(light, "STRONG_WIND_UNDERFORECAST"), light["limitations"][0]["id"]),
            _check("strong forecast -> LOW confidence with strong-wind reason",
                   strong["confidence"]["level"] == "LOW" and any("strong-wind" in r for r in strong["confidence"]["reasons"]), str(strong["confidence"]["reasons"])),
            _check("confidence never HIGH", all(d["confidence"]["level"] != "HIGH" for d in (light, strong)), "ceiling MODERATE"),
            _check("probabilistic flag not used to raise confidence", has(strong, "PROBABILISTIC_FLAG_EXPLORATORY"), "EXPLORATORY")]


def s14(L):
    a, _ = pair(L)
    trip = _hours([(18, DIR), (18, DIR), (10, DIR), (6, DIR), (4, DIR), (4, DIR)])
    d = B.build(L["lakeId"], _w(18), L, NOW, bank_ids=(a,), trip_hours=trip, prior_hours=_hours([(18, DIR)] * 6, NOW - timedelta(hours=6)))
    h = d["trip"]["banks"][0]["hours"]
    return [_check("modeled waves fall as wind eases", h[-1]["waveHeightIn"] < h[0]["waveHeightIn"], f"{h[0]['waveHeightIn']} -> {h[-1]['waveHeightIn']} in"),
            _check("easing hours flagged recession-optimistic", any(x.get("recessionOptimistic") for x in h[2:]), str([x.get("recessionOptimistic") for x in h])),
            _check("wind-easing events reported", any(e["type"] == "WIND_EASING" for e in d["trip"]["events"]), str([e["text"] for e in d["trip"]["events"]][:3])),
            _check("no wave memory disclosed", d["trip"]["waveMemory"]["memory"] is False, d["trip"]["waveMemory"]["model"])]


def s15(L):
    u = B.build("Wilson Lake|KS", _w(12), None, NOW, supported=False)
    d = B.build(L["lakeId"], _w(12), L, NOW, bank_ids=("NOT-A-BANK",))
    sub = any(x["id"] == "GEOMETRY_SUBSET" for x in d["limitations"])
    return [_check("lake outside Wind coverage refused", u["status"] == "UNSUPPORTED_LAKE", u["status"]),
            _check("bank outside the geometry reported, not invented", d["shorelines"]["requestedNotFound"] == ["NOT-A-BANK"], str(d["shorelines"]["requestedNotFound"])),
            _check("geometry scope disclosed", sub == bool(L.get("subset")) and d["lakeSummary"]["geometryScope"] == ("subset" if L.get("subset") else "full lake table"),
                   d["lakeSummary"]["geometryScope"])]


def s16(L):
    a, b = pair(L)
    h = lambda: hashlib.sha256(json.dumps(B.build(L["lakeId"], _w(13, 210), L, NOW, bank_ids=(a, b)), sort_keys=True).encode()).hexdigest()
    x, y = h(), h()
    return [_check("identical input -> identical decision", x == y, x[:16])]


def s17(L):
    ok = _ok(L)[:: max(1, len(_ok(L)) // 200)]
    bad = 0
    for i in ok:
        for d in (45, 225):
            seq = [BF.evaluate_bank(L, i, m * BF.MPH, d) for m in (5, 10, 15, 20)]
            bad += any(x["predictedSurfaceClass"] > y["predictedSurfaceClass"] or x["predictedHm0M"] > y["predictedHm0M"] for x, y in zip(seq, seq[1:]))
    return [_check("surface never decreases as wind rises 5 -> 20 mph", bad == 0, f"{bad} violations over {len(ok) * 2} bank-directions")]


def s18(L):
    a, b = pair(L)
    d = B.build(L["lakeId"], _w(12), L, NOW, bank_ids=(a, b))
    req = ("lakeId", "evaluatedAt", "wind", "shorelines", "confidence", "limitations", "provenance", "validation", "knowledgeVersion")
    allb = d["shorelines"]["sheltered"] + d["shorelines"]["exposed"] + d["shorelines"]["requested"]
    return [_check("contract invariants hold", SC.check(d) == [], str(SC.check(d))[:80]),
            _check("every bank explained with its numbers", all(f"{x['predictedSurface']['waveHeightIn']:g} in" in x["explanation"] for x in allb if x["predictedSurface"]), f"{len(allb)} banks"),
            _check("contract fields present", all(k in d for k in req), "ok"),
            _check("marked unvalidated shadow", d["validation"]["validated"] is False and d["validation"]["customerExposure"] == "NOT_AUTHORIZED", str(d["validation"]))]


SCENARIOS = {
    "S01": ("Exposed versus sheltered banks", s01), "S02": ("Opposing wind directions", s02), "S03": ("Calm versus strong wind", s03),
    "S04": ("Changing wind direction over a trip", s04), "S05": ("Sustained wind over several hours", s05), "S06": ("Protected coves versus open water", s06),
    "S07": ("Missing geometry and unsupported lake", s07), "S08": ("Unknown wind inputs and unknown banks", s08), "S09": ("Forecast freshness failure", s09),
    "S10": ("Surface classification boundaries and semantics", s10), "S11": ("Nearby sheltered alternatives", s11), "S12": ("Forecast lead-time differences", s12),
    "S13": ("Strong-wind uncertainty", s13), "S14": ("Rapidly decreasing wind", s14), "S15": ("Geographic coverage limits", s15),
    "S16": ("Deterministic output", s16), "S17": ("Speed monotonicity (BWIS v1 QA definition)", s17), "S18": ("Decision contract and explanations", s18),
}


def run(L: dict, only: tuple = ()) -> dict:
    res = []
    for sid, (title, fn) in SCENARIOS.items():
        if only and sid not in only:
            continue
        try:
            checks = fn(L)
        except Exception as e:     # a crash is a failed scenario, recorded, never hidden
            checks = [_check("scenario ran", False, f"{type(e).__name__}: {e}"[:200])]
        res.append({"id": sid, "title": title, "capability": CAPABILITY.get(sid), "input": "SYNTHETIC wind on real lake geometry",
                    "pass": all(c["pass"] for c in checks), "checks": checks})
    return {"suite": SUITE_ID, "knowledgeVersion": SC.KNOWLEDGE_VERSION, "lakeId": L["lakeId"], "geometryTableSha256": L.get("tableSha256"),
            "geometrySubset": L.get("subset"), "banks": len(L["banks"]), "evaluatedAt": C.iso(NOW),
            "passed": sum(r["pass"] for r in res), "total": len(res), "scenarios": res,
            "evidenceClass": "MODEL_CAPABILITY (synthetic inputs; not observed accuracy)"}
