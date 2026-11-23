#!/usr/bin/env python3
"""Wind strong-wind methods: read-only fetcher and scorer for protocol WSW-2026-11-23 (gap WIND-CNF-001).

The protocol (docs/brains/wind-strong-wind/WSW-2026-11-23.protocol.json) was pre-registered and hashed before any
past-window or H2 value was fetched. This runner reads public NOAA NBM grib2 and IEM ASOS/AWOS observations and writes
local files under --out only. It never writes Firebase or a bucket, never changes a score, an evidence file, a binding
or a schedule, and admits nothing: every output is labelled INTERNAL_EXPERIMENTAL / NOT_FOR_CUSTOMERS.

    verify                     protocol sha256 == committed sidecar
    plan  --window pw|h2       (init, lead) pairs and the message estimate; no network
    fit   --corpus-store DIR   M-B quantile map from CAL+H1 night rows only (reads the existing corpus store in place)
    fetch --window pw|h2       NBM synoptic night (init, lead) pairs + IEM days into --out/<window>/store
                               (pw: refused until the fit file exists; h2: refused before 2027-01-01)
    rows  --window pw|h2       station rows (obs, B0 speed, P90 speed) -> --out/<window>/rows.jsonl
    score --window pw|h2       B0 / M-A / M-B per lead + pooled, WI4 credit, scoreboard gate, bootstrap, decision
                               (h2: refused before 2027-01-01 and refused a second time in the same folder)

Scoring and fitting maths are standard library only (tested offline on synthetic fixtures). fetch/rows/fit import the
Wind runtime (numpy, eccodes) lazily, so the same decoder, row-scan fix and self-check as the corpus are used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import random
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROTOCOL = os.path.join(REPO, "docs", "brains", "wind-strong-wind", "WSW-2026-11-23.protocol.json")
WIND_RUNTIME = os.path.join(REPO, "brains", "wind", "runtime")
LABELS = ["INTERNAL_EXPERIMENTAL", "NOT_FOR_CUSTOMERS"]
UTC = dt.timezone.utc

MPH = 0.44704
T15 = 15 * MPH                      # 6.7056 m/s, the WI4 / scoreboard dimension-1 event threshold
LEADS = (1, 3, 6, 12, 18)
SYNOPTIC = (0, 6, 12, 18)
LEVELS = (0.5, 0.9, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999)
MIN_FIT_ROWS = 10000
MIN_EVENTS = 25
MIN_P90_COVERAGE = 0.80
BOOT_N, BOOT_SEED = 2000, 20261123
LOWER_PCT = 1.25                    # Bonferroni over two methods, one-sided 2.5%
SUPPORT_POD, SUPPORT_FAR = 0.25, 0.80
H2_OPEN = dt.datetime(2027, 1, 1, tzinfo=UTC)
WINDOWS = {
    "cal_h1": (dt.datetime(2026, 5, 6, 0, tzinfo=UTC), dt.datetime(2026, 10, 6, 23, tzinfo=UTC)),
    "pw": (dt.datetime(2025, 11, 1, 0, tzinfo=UTC), dt.datetime(2026, 4, 30, 18, tzinfo=UTC)),
    "h2": (dt.datetime(2026, 10, 7, 0, tzinfo=UTC), dt.datetime(2026, 12, 31, 18, tzinfo=UTC)),
}
ALLOWED_HOSTS = {"noaa-nbm-grib2-pds.s3.amazonaws.com", "mesonet.agron.iastate.edu"}
FIT_FILE = "wsw-mb-fit.json"
METHODS = ("B0", "M-A", "M-B")


class Refused(SystemExit):
    """A guard refused the step (exit code 3)."""

    def __init__(self, msg: str):
        super().__init__(3)
        self.msg = msg

    def __str__(self):
        return self.msg


# ----------------------------------------------------------------------------------------------------------------- protocol
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def load_protocol(path: str = PROTOCOL) -> tuple[dict, str]:
    """The protocol, refused unless its sha256 equals the committed sidecar (pre-registration is immutable)."""
    side = path + ".sha256"
    if not os.path.exists(side):
        raise Refused(f"REFUSED: no sha256 sidecar for {os.path.basename(path)}")
    want = open(side).read().split()[0].strip()
    got = sha256_file(path)
    if got != want:
        raise Refused(f"REFUSED: protocol sha256 {got} != sidecar {want}; the pre-registered protocol was changed")
    return json.load(open(path)), got


# ------------------------------------------------------------------------------------------------------------------ windows
def is_night(valid: dt.datetime) -> bool:
    """sector_wind.validate._night: valid UTC hour 01..08."""
    return 1 <= valid.hour <= 8


def night_pairs(window: str) -> list[tuple[dt.datetime, int]]:
    """Synoptic (init, lead) pairs of the window whose valid hour is night."""
    start, end = WINDOWS[window]
    out, t = [], start
    while t <= end:
        if t.hour in SYNOPTIC:
            for lead in LEADS:
                if is_night(t + dt.timedelta(hours=lead)):
                    out.append((t, lead))
        t += dt.timedelta(hours=1)
    return out


def guard_window(window: str, now: dt.datetime, step: str) -> None:
    if window not in ("pw", "h2"):
        raise Refused(f"REFUSED: {step} takes --window pw or h2 (CAL+H1 is used only by fit)")
    if window == "h2" and now < H2_OPEN:
        raise Refused(f"REFUSED: H2 (inits 2026-10-07..2026-12-31) is sealed until {H2_OPEN:%Y-%m-%d}; {step} not run")


def guard_fit_window(inits) -> None:
    lo, hi = WINDOWS["cal_h1"]
    bad = [t for t in inits if not (lo <= t <= hi)]
    if bad:
        raise Refused(f"REFUSED: fit rows outside CAL+H1 (first {min(bad):%Y-%m-%dT%HZ}); M-B is fitted on CAL+H1 only")


def check_hosts(urls) -> None:
    for u in urls:
        h = urlparse(u).hostname
        if urlparse(u).scheme != "https" or h not in ALLOWED_HOSTS:
            raise Refused(f"REFUSED: host {h!r} is not in the protocol's public host list")


# -------------------------------------------------------------------------------------------------------------- M-B (fit)
def quantile(sorted_x: list[float], q: float) -> float:
    """Type 7 (linear between order statistics)."""
    n = len(sorted_x)
    h = (n - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, n - 1)
    return sorted_x[lo] + (h - lo) * (sorted_x[hi] - sorted_x[lo])


def fit_qm(pairs: list[tuple[float, float]]) -> dict:
    """Protocol M-B: knots (F_k, D_k = O_k - F_k) at the pre-registered levels; ties in F merged with mean D."""
    if len(pairs) < MIN_FIT_ROWS:
        raise Refused(f"REFUSED: {len(pairs)} CAL+H1 night rows < {MIN_FIT_ROWS}; M-B not fitted")
    f = sorted(p[0] for p in pairs)
    o = sorted(p[1] for p in pairs)
    F = [quantile(f, q) for q in LEVELS]
    O = [quantile(o, q) for q in LEVELS]
    knots: list[list[float]] = []
    for fk, ok in zip(F, O):
        d = ok - fk
        if knots and abs(knots[-1][0] - fk) < 1e-12:
            knots[-1][1].append(d)
        else:
            knots.append([fk, [d]])
    return {"levels": list(LEVELS), "F": [round(x, 6) for x in F], "O": [round(x, 6) for x in O],
            "knots": [[round(k[0], 6), round(sum(k[1]) / len(k[1]), 6)] for k in knots], "n": len(pairs)}


def apply_qm(fit: dict, f: float) -> float:
    k = fit["knots"]
    if f <= k[0][0]:
        return f + k[0][1]
    if f >= k[-1][0]:
        return f + k[-1][1]
    for (x0, d0), (x1, d1) in zip(k, k[1:]):
        if x0 <= f <= x1:
            return f + (d0 + (d1 - d0) * (f - x0) / (x1 - x0) if x1 > x0 else d1)
    return f + k[-1][1]


def load_fit(path: str, protocol_sha: str) -> tuple[dict, str]:
    if not os.path.exists(path):
        raise Refused(f"REFUSED: fit file {os.path.basename(path)} missing; run `fit` on CAL+H1 first")
    raw = open(path, "rb").read()
    fit = json.loads(raw)
    if fit.get("protocolSha256") != protocol_sha:
        raise Refused("REFUSED: fit file was made under a different protocol")
    return fit, sha256_bytes(raw)


# ----------------------------------------------------------------------------------------------------------------- scoring
def forecasts(row: dict, fit: dict) -> dict:
    b0 = row.get("b0")
    p90 = row.get("p90")
    return {"B0": None if b0 is None else b0 >= T15,
            "M-A": None if p90 is None else p90 >= T15,
            "M-B": None if b0 is None else apply_qm(fit, b0) >= T15}


def table(pairs) -> dict:
    """pairs: iterable of (forecast_bool, observed_bool)."""
    h = m = fa = n = 0
    for fc, ob in pairs:
        n += 1
        h += fc and ob
        m += (not fc) and ob
        fa += fc and not ob
    return {"n": n, "hits": h, "misses": m, "falseAlarms": fa, "obsEvents": h + m, "fcEvents": h + fa,
            "pod": h / (h + m) if h + m else None, "far": fa / (h + fa) if h + fa else None,
            "csi": h / (h + m + fa) if h + m + fa else None}


def lin(x, zero, full):
    if x is None:
        return 0.0
    if full > zero:
        return max(0.0, min(1.0, (x - zero) / (full - zero)))
    return max(0.0, min(1.0, (zero - x) / (zero - full)))


def wi4_credit(by_lead: dict) -> float:
    """wind-specialist-capability-v2 WI4, as written."""
    if not sum(t["obsEvents"] for t in by_lead.values()):
        return 0.0
    pod_c = min(lin(by_lead[l]["pod"], 0.0, 0.5) if by_lead[l]["obsEvents"] else 0.0 for l in by_lead)
    far_c = min(1.0 if by_lead[l]["far"] is None else lin(by_lead[l]["far"], 0.8, 0.5) for l in by_lead)
    return round(pod_c * far_c, 4)


def scoreboard_gate(by_lead: dict) -> bool:
    """scoreboard.py dimension 1 strong-wind condition: POD >= 0.5 and FAR <= 0.5 (or none forecast) at every lead."""
    return all(t["pod"] is not None and t["pod"] >= 0.5 and (t["far"] is None or t["far"] <= 0.5) for t in by_lead.values())


def _pct(xs: list[float], p: float):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return round(quantile(xs, p / 100.0), 4)


def bootstrap(rows: list[dict], fc: dict, n: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """Block bootstrap over UTC valid dates; pooled POD/FAR/CSI per method and paired CSI(method) - CSI(B0)."""
    by_day: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        by_day.setdefault(r["valid"][:10], []).append(i)
    days = sorted(by_day)
    rng = random.Random(seed)
    stats = {m: {"pod": [], "far": [], "csi": []} for m in METHODS}
    diffs = {m: [] for m in METHODS if m != "B0"}
    for _ in range(n):
        idx = [i for d in (rng.choice(days) for _ in days) for i in by_day[d]]
        csi = {}
        for m in METHODS:
            t = table((fc[m][i], rows[i]["obsEvent"]) for i in idx)
            for k in ("pod", "far", "csi"):
                stats[m][k].append(t[k])
            csi[m] = t["csi"] or 0.0
        for m in diffs:
            diffs[m].append(csi[m] - csi["B0"])
    out = {"resamples": n, "seed": seed, "blocks": "UTC valid date", "days": len(days), "methods": {}}
    for m in METHODS:
        out["methods"][m] = {k: {"p2_5": _pct(v, 2.5), "p97_5": _pct(v, 97.5)} for k, v in stats[m].items()}
    out["csiDifferenceVsB0"] = {m: {"lower1_25": _pct(v, LOWER_PCT), "median": _pct(v, 50), "p97_5": _pct(v, 97.5)} for m, v in diffs.items()}
    return out


def score(rows: list[dict], fit: dict, boot_n: int = BOOT_N) -> dict:
    """Common-row scoring and the pre-registered decision. rows: {station, lead, valid, obs, b0, p90}."""
    night = [r for r in rows if r.get("obs") is not None and r.get("b0") is not None and r["lead"] in LEADS
             and is_night(dt.datetime.strptime(r["valid"], "%Y-%m-%dT%H:%M:%SZ"))]
    for r in night:
        r["obsEvent"] = r["obs"] >= T15
    own = {}
    for m in METHODS:
        avail = [(forecasts(r, fit)[m], r["obsEvent"]) for r in night if forecasts(r, fit)[m] is not None]
        own[m] = table(avail)
    common = [r for r in night if r.get("p90") is not None]
    coverage = len(common) / len(night) if night else 0.0
    fc = {m: [forecasts(r, fit)[m] for r in common] for m in METHODS}
    res = {"labels": LABELS, "rowsNight": len(night), "rowsCommon": len(common), "p90Coverage": round(coverage, 4),
           "ownRows": own, "methods": {}}
    for m in METHODS:
        by_lead = {str(l): table((fc[m][i], r["obsEvent"]) for i, r in enumerate(common) if r["lead"] == l) for l in LEADS}
        res["methods"][m] = {"byLead": by_lead, "pooled": table(zip(fc[m], (r["obsEvent"] for r in common))),
                             "wi4Credit": wi4_credit(by_lead), "scoreboardDim1Gate": scoreboard_gate(by_lead)}
    events = sum(r["obsEvent"] for r in common)
    res["observedEventsCommon"] = events
    if not night or coverage < MIN_P90_COVERAGE:
        outcome = {m: "NOT_EVALUABLE" for m in ("M-A", "M-B")}
        res["why"] = f"speedP90 on {coverage:.1%} of rows (< {MIN_P90_COVERAGE:.0%})"
    elif events < MIN_EVENTS:
        outcome = {m: "INSUFFICIENT_EVENTS" for m in ("M-A", "M-B")}
        res["why"] = f"{events} observed events in the common rows (< {MIN_EVENTS})"
    else:
        res["bootstrap"] = bootstrap(common, fc, boot_n)
        outcome = {}
        for m in ("M-A", "M-B"):
            p = res["methods"][m]["pooled"]
            lb = res["bootstrap"]["csiDifferenceVsB0"][m]["lower1_25"]
            ok = lb is not None and lb > 0 and (p["pod"] or 0) >= SUPPORT_POD and p["far"] is not None and p["far"] <= SUPPORT_FAR
            outcome[m] = "SUPPORTED" if ok else "NOT_SUPPORTED"
    res["outcome"] = outcome
    return res


# --------------------------------------------------------------------------------------------------- runtime (lazy imports)
def _runtime():
    if WIND_RUNTIME not in sys.path:
        sys.path.insert(0, WIND_RUNTIME)
    from sector_wind import ingest, interp, store, validate   # numpy + eccodes
    return ingest, interp, store, validate


def _cfg(ingest):
    return ingest.load_config(os.path.join(WIND_RUNTIME, "lakes.json"))


def collect_fit_pairs(corpus_store: str) -> list[tuple[float, float]]:
    """CAL+H1 night rows of validate.collect over the existing corpus store (read in place, never written)."""
    ingest, _, store, validate = _runtime()
    if corpus_store.startswith(("gs:", "gs://", "s3:", "http")):
        raise Refused("REFUSED: --corpus-store must be a local folder (read-only use)")
    lo, hi = WINDOWS["cal_h1"]
    st = store.LocalStore(corpus_store)
    recs = validate.collect(st, _cfg(ingest), lo, hi, LEADS)
    guard_fit_window(r["init"] for r in recs)
    return [(r["rec"][0], r["rec"][3]) for r in recs if validate._night(r["validTime"])]


def do_fetch(window: str, out: str, max_pairs: int | None = None) -> dict:
    ingest, _, store, _ = _runtime()
    check_hosts([ingest.NBM_CORE, ingest.NBM_QMD, ingest.IEM])
    cfg = _cfg(ingest)
    st = store.LocalStore(os.path.join(out, window, "store"))
    pairs = night_pairs(window)[:max_pairs] if max_pairs else night_pairs(window)
    by_init: dict[dt.datetime, list[int]] = {}
    for t, l in pairs:
        by_init.setdefault(t, []).append(l)
    done = failed = 0
    for t, leads in sorted(by_init.items()):
        o = [st.get_json(f"nbm/{lk}/{t:%Y%m%d%H}.json.gz") for lk in cfg["lakes"]]
        if all(x and x.get("status") == "complete" and len(x["steps"]) == len(leads) for x in o):
            continue
        r = ingest.ingest_nbm_cycle(st, cfg, t, leads, True)
        done += 1
        failed += any(v != "complete" for v in r.values())
    first, last = (pairs[0][0], pairs[-1][0]) if pairs else WINDOWS[window]
    days, d = 0, first.replace(hour=0) - dt.timedelta(days=1)
    while d <= last + dt.timedelta(days=2):
        if not st.exists(f"metar/{d:%Y%m%d}.json.gz"):
            ingest.ingest_metar_day(st, cfg, d)
            days += 1
        d += dt.timedelta(days=1)
    st.flush_ledger()
    return {"window": window, "cyclesFetched": done, "cyclesNotComplete": failed, "metarDaysFetched": days}


def build_rows(window: str, out: str) -> list[dict]:
    ingest, interp, store, validate = _runtime()
    cfg = _cfg(ingest)
    st = store.LocalStore(os.path.join(out, window, "store"))
    lo, hi = WINDOWS[window]
    obs = validate.load_obs(st, lo - dt.timedelta(days=1), hi + dt.timedelta(days=2))
    by_lake: dict[str, list[str]] = {}
    for sid, s in cfg["stations"].items():
        by_lake.setdefault(s["lake"], []).append(sid)
    wts, rows = {}, []
    for t, lead in night_pairs(window):
        for lake in cfg["lakes"]:
            c = st.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
            if not c:
                continue
            if lake not in wts:
                g = st.get_json(c["grid"])
                ci = interp.CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                wts[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in by_lake[lake]}
            step = next((s for s in c["steps"] if s["leadHours"] == lead), None)
            if not step:
                continue
            vt = t + dt.timedelta(hours=lead)
            for sid, w in wts[lake].items():
                o = obs.get((sid, vt))
                b0, _ = interp.blend_wind(step["speedMS"], step["dirFromDeg"], w)
                rows.append({"station": sid, "lake": lake, "init": f"{t:%Y-%m-%dT%H:%M:%SZ}", "lead": lead,
                             "valid": f"{vt:%Y-%m-%dT%H:%M:%SZ}", "nbmVersion": c.get("modelVersion"),
                             "obs": None if not o else o["speedMS"], "b0": b0,
                             "p90": interp.blend(step["speedP90"], w) if "speedP90" in step else None})
    return rows


# ---------------------------------------------------------------------------------------------------------------------- CLI
def _now(a) -> dt.datetime:
    return dt.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else dt.datetime.now(UTC)


def _write(path: str, obj) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    body = json.dumps(obj, indent=1, sort_keys=True).encode()
    with open(path, "wb") as fh:
        fh.write(body)
    return sha256_bytes(body)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("verify", "plan", "fit", "fetch", "rows", "score"))
    ap.add_argument("--window", choices=("pw", "h2"))
    ap.add_argument("--out", help="output folder (the Wind research folder)")
    ap.add_argument("--corpus-store", help="fit: the existing CAL+H1 corpus store (local folder, read only)")
    ap.add_argument("--fit", help="path to wsw-mb-fit.json (default <out>/wsw-mb-fit.json)")
    ap.add_argument("--rows", help="score: rows.jsonl (default <out>/<window>/rows.jsonl)")
    ap.add_argument("--max-pairs", type=int, help="fetch: smoke-test limit")
    ap.add_argument("--boot", type=int, default=BOOT_N, help=argparse.SUPPRESS)
    ap.add_argument("--now", help=argparse.SUPPRESS)
    ap.add_argument("--protocol", default=PROTOCOL, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    try:
        proto, psha = load_protocol(a.protocol)
        if a.cmd == "verify":
            print(f"OK {proto['protocolId']} sha256 {psha}")
            return 0
        if a.cmd == "plan":
            guard = a.window or "pw"
            p = night_pairs(guard)
            print(json.dumps({"window": guard, "initLeadPairs": len(p), "nbmMessages": len(p) * 7,
                              "byLead": {l: sum(1 for _, x in p if x == l) for l in LEADS}}, indent=1))
            return 0
        if not a.out:
            raise Refused("REFUSED: --out is required")
        fit_path = a.fit or os.path.join(a.out, FIT_FILE)
        if a.cmd == "fit":
            if not a.corpus_store:
                raise Refused("REFUSED: fit needs --corpus-store (the existing CAL+H1 corpus)")
            if os.path.exists(fit_path):
                raise Refused("REFUSED: a fit file already exists; the fit is frozen once")
            fit = fit_qm(collect_fit_pairs(a.corpus_store))
            fit.update({"schema": "sector-wind-wsw-mb-fit-v1", "protocolId": proto["protocolId"], "protocolSha256": psha,
                        "window": "CAL+H1 inits 2026-05-06T00Z..2026-10-06T23Z, night 01-08Z, leads 1/3/6/12/18",
                        "frozenAt": f"{_now(a):%Y-%m-%dT%H:%M:%SZ}", "labels": LABELS})
            print(f"fit written, sha256 {_write(fit_path, fit)} (post this on Sector_Ops #51)")
            return 0
        guard_window(a.window, _now(a), a.cmd)
        fit, fsha = load_fit(fit_path, psha)
        if a.cmd == "fetch":
            print(json.dumps(do_fetch(a.window, a.out, a.max_pairs), indent=1))
            return 0
        rows_path = a.rows or os.path.join(a.out, a.window, "rows.jsonl")
        if a.cmd == "rows":
            rows = build_rows(a.window, a.out)
            os.makedirs(os.path.dirname(rows_path), exist_ok=True)
            with open(rows_path, "w") as fh:
                fh.writelines(json.dumps(r, sort_keys=True) + "\n" for r in rows)
            print(f"{len(rows)} rows, sha256 {sha256_file(rows_path)}")
            return 0
        res_path = os.path.join(a.out, a.window, "wsw-result.json")
        if a.window == "h2" and os.path.exists(res_path):
            raise Refused("REFUSED: H2 has already been scored once in this folder (one shot)")
        rows = [json.loads(l) for l in open(rows_path) if l.strip()]
        res = score(rows, fit, a.boot)
        res.update({"schema": "sector-wind-wsw-result-v1", "protocolId": proto["protocolId"], "protocolSha256": psha,
                    "fitSha256": fsha, "rowsSha256": sha256_file(rows_path), "window": a.window,
                    "windowLabel": ("NBM v4.3 cool season (version-transfer caveat: not a v5.0 measurement)" if a.window == "pw"
                                    else "NBM v5.0 H2 confirmatory (one shot)"),
                    "scoredAt": f"{_now(a):%Y-%m-%dT%H:%M:%SZ}",
                    "admission": "none: evidence only; any WI4/evidence change goes through refresh_wind_score.py (HELD) and Michael"})
        print(f"result sha256 {_write(res_path, res)}")
        print(json.dumps({"outcome": res["outcome"], "observedEventsCommon": res["observedEventsCommon"],
                          "wi4Credit": {m: res["methods"][m]["wi4Credit"] for m in METHODS}}, indent=1))
        return 0
    except Refused as e:
        print(e.msg, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
