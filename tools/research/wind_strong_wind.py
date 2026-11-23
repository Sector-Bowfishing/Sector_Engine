#!/usr/bin/env python3
"""Wind strong-wind methods: read-only fetcher and scorer for protocol WSW-2026-11-23-R4 (gap WIND-CNF-001).

The protocol (docs/brains/wind-strong-wind/WSW-2026-11-23-R4.protocol.json) was pre-registered and hashed before any
data was fetched; its sha256 is pinned below and the runner refuses any other file (the superseded R3, R2 and R1 too).
It reads public NOAA NBM grib2 and IEM ASOS/AWOS observations and writes local files only. It never writes Firebase or a
bucket, never changes a score, an evidence file, a binding or a schedule, and admits nothing: every output is labelled
INTERNAL_EXPERIMENTAL / NOT_FOR_CUSTOMERS.

Run binding (R4 runBinding): one global run ledger per protocol id in
<Wind research folder>/protocol-runs/WSW-2026-11-23-R4/. The research folder is $SECTOR_RESEARCH_HOME/wind-brain, the folder
Cortex research-path returns; SECTOR_RESEARCH_HOME must be set (no machine-local default here). --out must be inside it.
fit (once), rows and score (once per window) are one-shot across every --out; only run #1 counts.

    verify                          protocol sha256 == the pinned registration; prints the resolved research folder
    plan  --window cal_h1|pw|h2     (init, lead) pairs and the message estimate; no network
    fetch --window cal_h1|pw|h2     synoptic night (init, lead) pairs + IEM days into --out/<window>/store (resumable)
          [--month YYYY-MM] [--min-free-gb N (default 80)] [--fit-sha SHA (pw/h2: must equal the ledger's fit)]
    fit   [--corpus-store DIR]      M-B map from CAL+H1 only (DIR read in place when given, else --out/cal_h1/store)
    rows  --window pw|h2 --fit-sha  write-once input manifest, then rows + accounting
    score --window pw|h2 --fit-sha  inputs re-verified; B0 / M-A / M-B, WI4 credit, gate, bootstrap, decision, run number

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
import signal
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _wsw_run_ledger as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROTOCOL = os.path.join(REPO, "docs", "brains", "wind-strong-wind", "WSW-2026-11-23-R4.protocol.json")
REGISTERED_SHA256 = "c0e86f6afa9de57d33c71d4eb049d4b1c95e403ad4a9c966edd16c7e9aaf77ca"
PROTOCOL_ID = "WSW-2026-11-23-R4"
WIND_RUNTIME = os.path.join(REPO, "brains", "wind", "runtime")
LABELS = ["INTERNAL_EXPERIMENTAL", "NOT_FOR_CUSTOMERS"]
UTC = dt.timezone.utc

MPH = 0.44704
T15 = 15 * MPH                      # 6.7056 m/s, the WI4 / scoreboard dimension-1 event threshold
LEADS = (1, 3, 6, 12, 18)
SYNOPTIC = (0, 6, 12, 18)
STATION_IDS = ("15M", "4A6", "8A1", "9A4", "DCU", "HSV", "MSL", "SNH")
STATIONS_N = len(STATION_IDS)
LAKES_JSON = os.path.join(WIND_RUNTIME, "lakes.json")
LAKES_JSON_SHA256 = "1ded19e9b838b08d659cb9a7572f4569bacab0ff81bccebccbcc546270dede51"
RESEARCH_FOLDER = "wind-brain"
LEVELS = (0.5, 0.9, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999)
MIN_FIT_ROWS = 5000
MIN_EVENTS = 25
MIN_P90_COVERAGE = 0.80
MAX_OBS_MISSING = 0.05            # share of planned rows without an observation (R4)
MAX_OBS_MISSING_STATION = 0.15    # at any one station
BOOT_N, BOOT_SEED = 2000, 20261123
LOWER_PCT = {"pw": 1.25, "h2": 0.625}   # Bonferroni: two candidates on PW; the four-rule H2 family (pW15, prob_recal, M-A, M-B)
SUPPORT_POD, SUPPORT_FAR = 0.25, 0.80
BUDGET_BYTES, BUDGET_SECONDS = 60_000_000_000, 48 * 3600
DEFAULT_MIN_FREE_GB = 80.0
H2_OPEN = dt.datetime(2027, 1, 1, tzinfo=UTC)
WINDOWS = {
    "cal_h1": (dt.datetime(2026, 5, 6, 0, tzinfo=UTC), dt.datetime(2026, 10, 6, 23, tzinfo=UTC)),
    "pw": (dt.datetime(2025, 1, 2, 0, tzinfo=UTC), dt.datetime(2025, 5, 26, 18, tzinfo=UTC)),
    "h2": (dt.datetime(2026, 10, 7, 0, tzinfo=UTC), dt.datetime(2026, 12, 31, 18, tzinfo=UTC)),
}
H2_START = WINDOWS["h2"][0]
H2_EXCLUDED_VALID_DATE = "2026-10-07"   # shared with CAL+H1 (read)
WINDOW_LABEL = {"pw": "NBM pre-v4.3 (v4.2) winter-spring: version-transfer caveat, not a v5.0 measurement",
                "h2": "NBM v5.0 H2 confirmatory (one shot)"}
ALLOWED_HOSTS = {"noaa-nbm-grib2-pds.s3.amazonaws.com", "mesonet.agron.iastate.edu"}
UA = "SectorWind/1.0 (wind research; github.com/Sector-Bowfishing)"
FIT_FILE = "wsw-mb-fit.json"
METHODS = ("B0", "M-A", "M-B")


class Refused(SystemExit):
    """A guard refused the step (exit code 3)."""

    def __init__(self, msg: str):
        super().__init__(3)
        self.msg = msg

    def __str__(self):
        return self.msg


class BudgetExceeded(Refused):
    pass


def _utcnow() -> dt.datetime:
    """The system clock. The H2 seal depends on it; there is no command-line override."""
    return dt.datetime.now(UTC)


# ----------------------------------------------------------------------------------------------------------------- protocol
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def load_protocol(path: str = PROTOCOL) -> tuple[dict, str]:
    """The registered protocol only: its bytes must hash to the pinned sha256 (and agree with the committed sidecar)."""
    raw = open(path, "rb").read()
    got = sha256_bytes(raw)
    if got != REGISTERED_SHA256:
        raise Refused(f"REFUSED: protocol sha256 {got} is not the registered {REGISTERED_SHA256}")
    side = path + ".sha256"
    if os.path.exists(side) and open(side).read().split()[0].strip() != got:
        raise Refused("REFUSED: protocol sidecar disagrees with the registered sha256")
    return json.loads(raw), got


# ------------------------------------------------------------------------------------------------------------------ windows
def is_night(valid: dt.datetime) -> bool:
    """sector_wind.validate._night: valid UTC hour 01..08."""
    return 1 <= valid.hour <= 8


def night_pairs(window: str) -> list[tuple[dt.datetime, int]]:
    """Synoptic (init, lead) pairs of the window whose valid hour is night. CAL+H1 never plans a valid time in H2."""
    start, end = WINDOWS[window]
    out, t = [], start
    while t <= end:
        if t.hour in SYNOPTIC:
            for lead in LEADS:
                vt = t + dt.timedelta(hours=lead)
                if is_night(vt) and not (window == "cal_h1" and vt >= H2_START):
                    out.append((t, lead))
        t += dt.timedelta(hours=1)
    return out


def month_pairs(window: str, month: str | None) -> list[tuple[dt.datetime, int]]:
    pairs = night_pairs(window)
    if month is None:
        return pairs
    sel = [p for p in pairs if f"{p[0]:%Y-%m}" == month]
    if not sel:
        raise Refused(f"REFUSED: month {month} has no init in the {window} window")
    return sel


def obs_days(window: str, pairs) -> list[dt.date]:
    """Observation days for the pairs: the day before the first init to two days after the last, never a day on or after
    the H2 start unless the window is H2."""
    if not pairs:
        return []
    d, last = (pairs[0][0] - dt.timedelta(days=1)).date(), (pairs[-1][0] + dt.timedelta(days=2)).date()
    out = []
    while d <= last:
        if window == "h2" or d < H2_START.date():
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def obs_end(window: str) -> dt.datetime:
    end = WINDOWS[window][1] + dt.timedelta(days=2)
    return end if window == "h2" else min(end, H2_START - dt.timedelta(seconds=1))


def guard_h2(window: str, step: str) -> None:
    if window == "h2" and _utcnow() < H2_OPEN:
        raise Refused(f"REFUSED: H2 (inits 2026-10-07..2026-12-31) is sealed until {H2_OPEN:%Y-%m-%d}; {step} not run")


def guard_fit_rows(rows) -> None:
    lo, hi = WINDOWS["cal_h1"]
    for r in rows:
        t = dt.datetime.strptime(r["init"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        v = dt.datetime.strptime(r["valid"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if not (lo <= t <= hi) or v >= H2_START:
            raise Refused(f"REFUSED: fit row init {r['init']} valid {r['valid']} is outside CAL+H1; M-B is fitted on CAL+H1 only")


def check_host(url: str) -> None:
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        raise Refused(f"REFUSED: host {p.hostname!r} ({p.scheme}) is not in the protocol's public host list")


def guard_free_space(path: str, min_free_gb: float) -> float:
    import shutil
    probe = path
    while not os.path.exists(probe):
        probe = os.path.dirname(probe) or "."
    free = shutil.disk_usage(probe).free / 1e9
    if free < min_free_gb:
        raise Refused(f"REFUSED: {free:.1f} GB free on the output volume (< {min_free_gb:g} GB); stopped before the next download")
    return free


def research_folder() -> str:
    """$SECTOR_RESEARCH_HOME/wind-brain, the folder Cortex research-path returns (it must exist; it is never created here)."""
    root = os.environ.get("SECTOR_RESEARCH_HOME")
    if not root:
        raise Refused("REFUSED: set SECTOR_RESEARCH_HOME to the research home whose wind-brain folder Cortex research-path returns")
    folder = os.path.realpath(os.path.join(os.path.expanduser(root), RESEARCH_FOLDER))
    if not os.path.isdir(folder):
        raise Refused(f"REFUSED: the Wind research folder {folder} does not exist (set SECTOR_RESEARCH_HOME to the research home "
                      "that Cortex research-path uses)")
    return folder


def binding_folder() -> str:
    return os.path.join(research_folder(), "protocol-runs", PROTOCOL_ID)


def guard_out(out: str) -> str:
    """--out must be inside the Wind research folder (on the research SSD), never elsewhere."""
    folder = research_folder()
    real = os.path.realpath(out)
    if os.path.commonpath([folder, real]) != folder:
        raise Refused(f"REFUSED: --out {out} is not inside the Wind research folder {folder}")
    return real


def check_lakes() -> None:
    """R4 pins lakes.json and the 8 frozen stations."""
    got = sha256_file(LAKES_JSON)
    if got != LAKES_JSON_SHA256:
        raise Refused(f"REFUSED: brains/wind/runtime/lakes.json sha256 {got} differs from the registered {LAKES_JSON_SHA256}")
    ids = tuple(sorted(json.load(open(LAKES_JSON))["stations"]))
    if ids != STATION_IDS:
        raise Refused(f"REFUSED: lakes.json stations {ids} differ from the registered {STATION_IDS}")


def ledger(clock=None) -> L.RunLedger:
    return L.RunLedger(binding_folder(), PROTOCOL_ID, REGISTERED_SHA256, clock=clock or _utcnow)


def guard_fit_sha(led: L.RunLedger, out: str, given: str | None, protocol_sha: str) -> tuple[dict, str]:
    """--fit-sha must equal the fit sha recorded in the run ledger at fit time, and the fit file in --out must match it."""
    end = led.completed("fit", "cal_h1")
    if not end:
        raise Refused("REFUSED: the run ledger has no completed fit for this protocol; run `fit` first")
    recorded = end["outputs"]["fitSha256"]
    if not given:
        raise Refused("REFUSED: --fit-sha is required (the fit sha256 posted on Sector_Ops #51)")
    if given.strip().lower() != recorded:
        raise Refused(f"REFUSED: --fit-sha {given} is not the fit recorded in the run ledger ({recorded})")
    fit, fsha = load_fit(os.path.join(out, FIT_FILE), protocol_sha)
    if fsha != recorded:
        raise Refused(f"REFUSED: the fit file in --out ({fsha}) is not the fit recorded in the run ledger ({recorded})")
    return fit, fsha


def note_fit_use(window: str, step: str, fsha: str) -> None:
    """fit-record.json in the binding folder: the ledger's fit and the first use of it per window and step (atomic)."""
    p = os.path.join(binding_folder(), "fit-record.json")
    rec = json.load(open(p)) if os.path.exists(p) else {"fitSha256": fsha, "firstUse": {}}
    if rec["fitSha256"] != fsha:
        raise Refused("REFUSED: fit-record.json names a different fit")
    key = f"{window}:{step}"
    if key not in rec["firstUse"]:
        rec["firstUse"][key] = f"{_utcnow():%Y-%m-%dT%H:%M:%SZ}"
        L.atomic_write_json(p, rec)


def guard_h2_ledger(led: L.RunLedger, step: str) -> None:
    """R4: refuse H2 when an earlier H2 rows/score attempt exists (fetch only before rows), or an H2 line predates unseal."""
    es = led.entries()
    for e in es:
        if e.get("window") == "h2" and e["kind"] != "REFUSED" and e["at"] < f"{H2_OPEN:%Y-%m-%dT%H:%M:%SZ}":
            led.refuse(step, "h2", f"the ledger has an H2 {e['step']} line at {e['at']}, before the unseal date")
    if step == "fetch" and any(a for st in ("rows", "score") for a in led.attempts(st, "h2")):
        led.refuse(step, "h2", "H2 rows or score were already attempted; no further H2 fetch")


def code_identity() -> dict:
    """Runner, ledger module and Wind runtime hashes, and the repository git commit with a dirty flag."""
    import subprocess
    out = {"runnerSha256": sha256_file(os.path.abspath(__file__)), "ledgerModuleSha256": sha256_file(L.__file__),
           "windRuntime": L.tree_hash(os.path.join(WIND_RUNTIME, "sector_wind"))["collectionSha256"]}
    try:
        out["gitCommit"] = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        out["gitDirty"] = bool(subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--", "tools/research", "brains/wind/runtime",
                                               "docs/brains/wind-strong-wind"], capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        out["gitCommit"], out["gitDirty"] = "UNKNOWN (not a git checkout)", None
    return out


def input_manifest(window: str, out: str) -> dict:
    """What rows read: the window store's nbm/ and metar/ trees, lakes.json, and the code that reads them."""
    store_root = os.path.join(out, window, "store")
    return {"schema": "sector-wind-wsw-input-manifest-v1", "protocolId": PROTOCOL_ID, "window": window, "store": store_root,
            "nbm": L.tree_hash(os.path.join(store_root, "nbm")), "metar": L.tree_hash(os.path.join(store_root, "metar")),
            "grids": L.tree_hash(os.path.join(store_root, "grids")), "lakesJsonSha256": sha256_file(LAKES_JSON),
            "code": code_identity()}


# ------------------------------------------------------------------------------------------------------------------- budget
class Budget:
    """Cumulative download bytes and wall clock for one window, kept in <window>/budget.json across runs."""

    def __init__(self, path: str, max_bytes: int = BUDGET_BYTES, max_seconds: float = BUDGET_SECONDS, clock=time.monotonic):
        self.path, self.max_bytes, self.max_seconds, self.clock = path, max_bytes, max_seconds, clock
        prev = json.load(open(path)) if os.path.exists(path) else {}
        self.bytes, self.prior_seconds = prev.get("bytes", 0), prev.get("seconds", 0.0)
        self.attempts = prev.get("attempts", 0)
        self.t0 = clock()

    def seconds(self) -> float:
        return self.prior_seconds + (self.clock() - self.t0)

    def check(self, url: str) -> None:
        check_host(url)
        if self.bytes >= self.max_bytes:
            raise BudgetExceeded(f"STOPPED: download budget reached ({self.bytes} of {self.max_bytes} bytes)")
        if self.seconds() >= self.max_seconds:
            raise BudgetExceeded(f"STOPPED: wall-clock budget reached ({self.seconds() / 3600:.1f} of {self.max_seconds / 3600:g} h)")

    def add(self, n: int) -> None:
        self.bytes += n

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"bytes": self.bytes, "seconds": round(self.seconds(), 1), "attempts": self.attempts,
                       "maxBytes": self.max_bytes, "maxSeconds": self.max_seconds}, fh, indent=1)
        os.replace(tmp, self.path)
        self.prior_seconds, self.t0 = self.seconds(), self.clock()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"redirect refused ({newurl})", headers, fp)


def budgeted_fetch(budget: Budget, error_cls, opener=None, sleep=time.sleep):
    """A drop-in for sector_wind.grib.fetch: every attempt is host-checked and budget-checked before it is sent, every
    byte read is counted (retries and partial reads included), and redirects are refused."""
    opener = opener or urllib.request.build_opener(_NoRedirect)

    def fetch(url: str, rng=None, timeout: int = 120, tries: int = 4) -> bytes:
        headers = {"User-Agent": UA}
        if rng is not None:
            headers["Range"] = f"bytes={rng[0]}-{rng[1]}"
        last = None
        for attempt in range(tries):
            budget.check(url)
            budget.attempts += 1
            try:
                with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                    chunks = []
                    while True:
                        c = r.read(1 << 20)
                        if not c:
                            break
                        budget.add(len(c))
                        chunks.append(c)
                    return b"".join(chunks)
            except BudgetExceeded:
                raise
            except Exception as e:
                last = e
                if getattr(e, "code", None) in (301, 302, 303, 307, 308, 404):
                    break
                sleep(1.5 * (attempt + 1))
        raise error_cls(f"{url}: {last}")
    return fetch


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
    knots: list[list] = []
    for fk, ok in zip(F, O):
        d = ok - fk
        if knots and abs(knots[-1][0] - fk) < 1e-12:
            knots[-1][1].append(d)
        else:
            knots.append([fk, [d]])
    return {"levels": list(LEVELS), "F": [round(x, 6) for x in F], "O": [round(x, 6) for x in O],
            "knots": [[round(k[0], 6), round(sum(k[1]) / len(k[1]), 6)] for k in knots], "n": len(pairs)}


def truth_gap(accounting: dict) -> str | None:
    """R4 accounting.truthSideGaps: a missing observation day, or rows without an observation above 5% overall or 15% at
    any station. Returns the reason, or None."""
    if accounting.get("missingObsDays"):
        return f"{len(accounting['missingObsDays'])} planned observation days have no stored METAR file"
    planned, per = accounting.get("plannedRows") or 0, accounting.get("plannedRowsPerStation") or 0
    if not planned:
        return "no planned rows"
    share = accounting.get("obsMissing", 0) / planned
    if share > MAX_OBS_MISSING:
        return f"{share:.1%} of planned rows have no observation (> {MAX_OBS_MISSING:.0%})"
    for sid, n in sorted((accounting.get("obsMissingByStation") or {}).items()):
        if per and n / per > MAX_OBS_MISSING_STATION:
            return f"{n / per:.1%} of planned rows at {sid} have no observation (> {MAX_OBS_MISSING_STATION:.0%})"
    return None


def fit_pairs(rows: list[dict], accounting: dict) -> list[tuple[float, float]]:
    """CAL+H1 rows -> (deterministic speed, observed speed); refused on any cycle or truth gap or any row outside CAL+H1."""
    gaps = accounting["missingCycles"] + accounting["incompleteCycles"]
    if gaps:
        raise Refused(f"REFUSED: {gaps} planned CAL+H1 cycles missing or incomplete; M-B is not fitted on a gappy CAL+H1")
    why = truth_gap(accounting)
    if why:
        raise Refused(f"REFUSED: CAL+H1 truth gap: {why}; M-B is not fitted")
    use = [r for r in rows if r["lead"] in LEADS and is_night(dt.datetime.strptime(r["valid"], "%Y-%m-%dT%H:%M:%SZ"))]
    guard_fit_rows(use)
    return [(r["b0"], r["obs"]) for r in use if r.get("obs") is not None and r.get("b0") is not None]


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
    """Yes/no per method. A missing value is 'no event forecast' (it cannot hit; it misses an observed event)."""
    b0, p90 = row.get("b0"), row.get("p90")
    return {"B0": b0 is not None and b0 >= T15,
            "M-A": p90 is not None and p90 >= T15,
            "M-B": b0 is not None and apply_qm(fit, b0) >= T15}


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


def _with_rows(by_lead: dict) -> dict:
    """Production leaves out a lead that has no rows (it is absent from the skill's night dict)."""
    return {k: v for k, v in by_lead.items() if v["n"]}


def wi4_credit(by_lead: dict) -> float:
    """wind-specialist-capability-v2 WI4 as the production scorer computes it (wind_measurements._strong)."""
    bl = _with_rows(by_lead)
    if not bl or not sum(t["obsEvents"] for t in bl.values()):
        return 0.0
    pod_c = min(lin(t["pod"], 0.0, 0.5) for t in bl.values())
    far_c = min(1.0 if t["far"] is None else lin(t["far"], 0.8, 0.5) for t in bl.values())
    return round(pod_c * far_c, 4)


def scoreboard_gate(by_lead: dict) -> bool:
    """scoreboard.py dimension 1 strong-wind condition over the leads that have rows."""
    bl = _with_rows(by_lead)
    return bool(bl) and all(t["pod"] is not None and t["pod"] >= 0.5 and (t["far"] is None or t["far"] <= 0.5) for t in bl.values())


def _pct(xs: list, p: float):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return round(quantile(xs, p / 100.0), 4)


def bootstrap(rows: list[dict], fc: dict, lower_pct: float, n: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
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
    out = {"resamples": n, "seed": seed, "blocks": "UTC valid date", "days": len(days), "lowerPercentile": lower_pct, "methods": {}}
    for m in METHODS:
        out["methods"][m] = {k: {"p2_5": _pct(v, 2.5), "p97_5": _pct(v, 97.5)} for k, v in stats[m].items()}
    out["csiDifferenceVsB0"] = {m: {"lowerBound": _pct(v, lower_pct), "median": _pct(v, 50), "p97_5": _pct(v, 97.5)} for m, v in diffs.items()}
    return out


def score(rows: list[dict], fit: dict, accounting: dict, window: str = "pw", boot_n: int = BOOT_N) -> dict:
    """Scored rows = every night row with an observation; a missing method value is 'no event forecast' (R3 accounting)."""
    night = [r for r in rows if r["lead"] in LEADS and is_night(dt.datetime.strptime(r["valid"], "%Y-%m-%dT%H:%M:%SZ"))
             and not (window == "h2" and r["valid"].startswith(H2_EXCLUDED_VALID_DATE))]
    scored = [r for r in night if r.get("obs") is not None]
    for r in scored:
        r["obsEvent"] = r["obs"] >= T15
    fc = {m: [forecasts(r, fit)[m] for r in scored] for m in METHODS}
    acc = dict(accounting)
    acc.update({"rowsNight": len(night), "rowsScored": len(scored),
                "b0MissingScored": sum(r.get("b0") is None for r in scored), "p90MissingScored": sum(r.get("p90") is None for r in scored)})
    planned = acc.get("plannedRows") or 0
    p90_cov = 1 - acc["p90MissingScored"] / len(scored) if scored else 0.0
    obs_missing_share = acc.get("obsMissing", 0) / planned if planned else 1.0
    gap = truth_gap(acc)
    res = {"labels": LABELS, "accounting": acc, "p90Coverage": round(p90_cov, 4), "obsMissingShare": round(obs_missing_share, 4), "methods": {}}
    for m in METHODS:
        by_lead = {str(l): table((fc[m][i], r["obsEvent"]) for i, r in enumerate(scored) if r["lead"] == l) for l in LEADS}
        res["methods"][m] = {"byLead": by_lead, "pooled": table(zip(fc[m], (r["obsEvent"] for r in scored))),
                             "wi4Credit": wi4_credit(by_lead), "scoreboardDim1Gate": scoreboard_gate(by_lead)}
    events = sum(r["obsEvent"] for r in scored)
    res["observedEvents"] = events
    why = []
    if acc.get("missingCycles", 0) or acc.get("incompleteCycles", 0):
        verdict = {m: "INCOMPLETE" for m in ("M-A", "M-B")}
        why.append(f"{acc.get('missingCycles', 0)} missing and {acc.get('incompleteCycles', 0)} incomplete planned cycles")
    elif gap:
        verdict = {m: "INCOMPLETE" for m in ("M-A", "M-B")}
        why.append(gap)
    elif events < MIN_EVENTS:
        verdict = {m: "INSUFFICIENT_EVENTS" for m in ("M-A", "M-B")}
        why.append(f"{events} observed events in the scored rows (< {MIN_EVENTS})")
    else:
        res["bootstrap"] = bootstrap(scored, fc, LOWER_PCT[window], boot_n)
        verdict = {}
        for m in ("M-A", "M-B"):
            if m == "M-A" and p90_cov < MIN_P90_COVERAGE:
                verdict[m] = "NOT_EVALUABLE"
                why.append(f"90% level on {p90_cov:.1%} of scored rows (< {MIN_P90_COVERAGE:.0%}); M-A not evaluable")
                continue
            p = res["methods"][m]["pooled"]
            lb = res["bootstrap"]["csiDifferenceVsB0"][m]["lowerBound"]
            ok = lb is not None and lb > 0 and (p["pod"] or 0) >= SUPPORT_POD and p["far"] is not None and p["far"] <= SUPPORT_FAR
            verdict[m] = "SUPPORTED" if ok else "NOT_SUPPORTED"
    res["why"] = "; ".join(why)
    res["outcome"] = {m: {"outcome": verdict[m], "wi4Credit": res["methods"][m]["wi4Credit"],
                          "scoreboardDim1Gate": res["methods"][m]["scoreboardDim1Gate"]} for m in ("M-A", "M-B")}
    res["outcome"]["B0"] = {"outcome": "REFERENCE", "wi4Credit": res["methods"]["B0"]["wi4Credit"],
                            "scoreboardDim1Gate": res["methods"]["B0"]["scoreboardDim1Gate"]}
    return res


# --------------------------------------------------------------------------------------------------- runtime (lazy imports)
def _runtime():
    if WIND_RUNTIME not in sys.path:
        sys.path.insert(0, WIND_RUNTIME)
    from sector_wind import grib, ingest, interp, store, validate   # numpy + eccodes
    return grib, ingest, interp, store, validate


def _cfg(ingest):
    return ingest.load_config(os.path.join(WIND_RUNTIME, "lakes.json"))


def do_fetch(window: str, out: str, max_pairs: int | None = None, month: str | None = None, budget: Budget | None = None,
             min_free_gb: float = DEFAULT_MIN_FREE_GB, opener=None) -> dict:
    grib, ingest, _, store, _ = _runtime()
    for u in (ingest.NBM_CORE, ingest.NBM_QMD, ingest.IEM):
        check_host(u)
    budget = budget or Budget(os.path.join(binding_folder(), f"budget-{window}.json"))
    real = (grib.fetch, ingest.fetch)
    guarded = budgeted_fetch(budget, grib.FetchError, opener)
    grib.fetch = guarded        # read_idx -> grib.fetch
    ingest.fetch = guarded      # _field and ingest_metar_day -> ingest.fetch

    def _on_signal(signum, frame):
        budget.save()
        raise SystemExit(128 + signum)
    old = {s: signal.signal(s, _on_signal) for s in (signal.SIGTERM, signal.SIGINT)}
    done = failed = days = 0
    try:
        cfg = _cfg(ingest)
        st = store.LocalStore(os.path.join(out, window, "store"))
        pairs = month_pairs(window, month)
        pairs = pairs[:max_pairs] if max_pairs else pairs
        by_init: dict[dt.datetime, list[int]] = {}
        for t, l in pairs:
            by_init.setdefault(t, []).append(l)
        for t, leads in sorted(by_init.items()):
            o = [st.get_json(f"nbm/{lk}/{t:%Y%m%d%H}.json.gz") for lk in cfg["lakes"]]
            if all(x and x.get("status") == "complete" and len(x["steps"]) == len(leads) for x in o):
                continue
            guard_free_space(out, min_free_gb)
            r = ingest.ingest_nbm_cycle(st, cfg, t, leads, True)
            done += 1
            failed += any(v != "complete" for v in r.values())
            budget.save()
        for d in obs_days(window, pairs):
            if not st.exists(f"metar/{d:%Y%m%d}.json.gz"):
                guard_free_space(out, min_free_gb)
                ingest.ingest_metar_day(st, cfg, dt.datetime(d.year, d.month, d.day, tzinfo=UTC))
                days += 1
                budget.save()
        st.flush_ledger()
    finally:
        grib.fetch, ingest.fetch = real
        for s, h in old.items():
            signal.signal(s, h)
        budget.save()
    return {"window": window, "month": month, "cyclesFetched": done, "cyclesNotComplete": failed, "metarDaysFetched": days,
            "budget": {"bytes": budget.bytes, "attempts": budget.attempts, "hours": round(budget.seconds() / 3600, 2)}}


def build_rows(window: str, store_root: str) -> tuple[list[dict], dict]:
    """Rows for the window's planned synoptic night pairs from a store in the corpus layout (read only), with accounting."""
    _, ingest, interp, store, validate = _runtime()
    cfg = _cfg(ingest)
    if not os.path.isdir(store_root):
        raise Refused(f"REFUSED: store folder {store_root} not found")
    st = store.LocalStore(store_root)
    lo = WINDOWS[window][0]
    end = obs_end(window)
    obs = {k: v for k, v in validate.load_obs(st, lo - dt.timedelta(days=1), end).items() if window == "h2" or k[1] < H2_START}
    by_lake: dict[str, list[str]] = {}
    for sid, s in cfg["stations"].items():
        by_lake.setdefault(s["lake"], []).append(sid)
    pairs = night_pairs(window)
    days = obs_days(window, pairs)
    missing_days = [f"{d:%Y-%m-%d}" for d in days if not st.exists(f"metar/{d:%Y%m%d}.json.gz")]
    acc = {"plannedPairs": len(pairs), "plannedRows": len(pairs) * sum(len(v) for v in by_lake.values()),
           "plannedRowsPerStation": len(pairs), "plannedObsDays": len(days), "missingObsDays": missing_days,
           "plannedCycles": 0, "missingCycles": 0, "incompleteCycles": 0, "rowsBuilt": 0,
           "rowsNotBuilt": 0, "obsMissing": 0, "obsMissingByStation": {s: 0 for s in cfg["stations"]},
           "b0Missing": 0, "p90Missing": 0, "missingCycleKeys": [], "incompleteCycleKeys": []}
    wts, rows, seen = {}, [], set()
    for t, lead in pairs:
        for lake in cfg["lakes"]:
            key = f"nbm/{lake}/{t:%Y%m%d%H}.json.gz"
            c = st.get_json(key)
            if key not in seen:
                seen.add(key)
                acc["plannedCycles"] += 1
                if not c:
                    acc["missingCycles"] += 1
                    acc["missingCycleKeys"].append(key)
                elif c.get("status") != "complete":
                    acc["incompleteCycles"] += 1
                    acc["incompleteCycleKeys"].append(key)
            step = next((s for s in c["steps"] if s["leadHours"] == lead), None) if c else None
            if c and not step and key not in acc["incompleteCycleKeys"]:
                acc["incompleteCycles"] += 1
                acc["incompleteCycleKeys"].append(key)
            if not step:
                acc["rowsNotBuilt"] += len(by_lake.get(lake, []))
                continue
            if lake not in wts:
                g = st.get_json(c["grid"])
                ci = interp.CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                wts[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in by_lake[lake]}
            vt = t + dt.timedelta(hours=lead)
            for sid, w in wts[lake].items():
                o = obs.get((sid, vt))
                b0, _ = interp.blend_wind(step["speedMS"], step["dirFromDeg"], w)
                p90 = interp.blend(step["speedP90"], w) if "speedP90" in step else None
                acc["obsMissing"] += o is None
                acc["obsMissingByStation"][sid] += o is None
                acc["b0Missing"] += b0 is None
                acc["p90Missing"] += p90 is None
                rows.append({"station": sid, "lake": lake, "init": f"{t:%Y-%m-%dT%H:%M:%SZ}", "lead": lead,
                             "valid": f"{vt:%Y-%m-%dT%H:%M:%SZ}", "nbmVersion": c.get("modelVersion"),
                             "obs": None if not o else o["speedMS"], "b0": b0, "p90": p90})
    acc["rowsBuilt"] = len(rows)
    return rows, acc


# ---------------------------------------------------------------------------------------------------------------------- CLI
def _write_once(path: str, obj) -> str:
    if os.path.exists(path):
        raise Refused(f"REFUSED: {os.path.basename(path)} is already recorded; it is never overwritten")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    body = json.dumps(obj, indent=1, sort_keys=True).encode()
    with open(path, "xb") as fh:
        fh.write(body)
    return sha256_bytes(body)


def _cmd_fit(a, proto, psha, led) -> int:
    fit_path = os.path.join(a.out, FIT_FILE)
    src = os.path.realpath(a.corpus_store) if a.corpus_store else os.path.join(a.out, "cal_h1", "store")
    inputs = {"source": "corpus-store" if a.corpus_store else "fetched", "storePath": src,
              "nbm": L.tree_hash(os.path.join(src, "nbm")), "metar": L.tree_hash(os.path.join(src, "metar")),
              "lakesJsonSha256": LAKES_JSON_SHA256, "code": code_identity()}
    with led.step("fit", "cal_h1", inputs) as run:
        if os.path.exists(fit_path):
            raise Refused("REFUSED: a fit file already exists in --out")
        rows, acc = build_rows("cal_h1", src)
        fit = fit_qm(fit_pairs(rows, acc))
        fit.update({"schema": "sector-wind-wsw-mb-fit-v1", "protocolId": proto["protocolId"], "protocolSha256": psha,
                    "window": "CAL+H1 inits 2026-05-06T00Z..2026-10-06T23Z, synoptic night pairs valid before 2026-10-07, 8 stations",
                    "source": inputs["source"], "accounting": acc, "runNumber": run.run_number, "ledgerStartLine": run.start_hash,
                    "frozenAt": f"{_utcnow():%Y-%m-%dT%H:%M:%SZ}", "labels": LABELS})
        run.writing()
        fsha = _write_once(fit_path, fit)
        run.outputs = {"fitSha256": fsha, "fitPath": fit_path}
        L.atomic_write_json(os.path.join(binding_folder(), "fit-record.json"), {"fitSha256": fsha, "firstUse": {}})
    print(f"fit written, sha256 {fsha} (run #{run.run_number}, recorded in the run ledger). "
          "Post it on Sector_Ops #51 before any past-window fetch.")
    return 0


def _cmd_fetch(a, psha, led) -> int:
    if a.window != "cal_h1":
        _, fsha = guard_fit_sha(led, a.out, a.fit_sha, psha)
    if a.window == "h2":
        guard_h2_ledger(led, "fetch")
    if any(x["status"] != "ABORTED_NO_RESULT" for x in led.attempts("rows", a.window)):
        led.refuse("fetch", a.window, "rows were already built for this window; the inputs are fixed")
    if a.month:
        month_pairs(a.window, a.month)
    free = guard_free_space(a.out, a.min_free_gb)
    if a.window != "cal_h1":
        note_fit_use(a.window, "fetch", fsha)
    led.log("fetch", a.window, "STARTED", {"month": a.month, "maxPairs": a.max_pairs, "out": a.out})
    try:
        res = do_fetch(a.window, a.out, a.max_pairs, a.month, min_free_gb=a.min_free_gb)
    except BaseException as e:
        led.log("fetch", a.window, "STOPPED", {"month": a.month, "error": f"{type(e).__name__}: {e}"[:300]})
        raise
    res["freeGbBefore"] = round(free, 1)
    led.log("fetch", a.window, "COMPLETED", {"month": a.month, "budget": res["budget"], "cyclesNotComplete": res["cyclesNotComplete"]})
    print(json.dumps(res, indent=1))
    return 0


def _cmd_rows(a, psha, led) -> int:
    _, fsha = guard_fit_sha(led, a.out, a.fit_sha, psha)
    if a.window == "h2":
        guard_h2_ledger(led, "rows")
    rows_path = os.path.join(a.out, a.window, "rows.jsonl")
    acc_path = os.path.join(a.out, a.window, "accounting.json")
    man = input_manifest(a.window, a.out)
    with led.step("rows", a.window, {"fitSha256": fsha, "inputManifest": L.sha256_bytes(L.canonical(man))}) as run:
        if os.path.exists(rows_path) or os.path.exists(acc_path):
            raise Refused("REFUSED: rows are already recorded in --out; they are never overwritten")
        msha = L.write_once_json(os.path.join(binding_folder(), f"input-manifest-{a.window}.json"), man)
        rows, acc = build_rows(a.window, os.path.join(a.out, a.window, "store"))
        run.writing()
        os.makedirs(os.path.dirname(rows_path), exist_ok=True)
        with open(rows_path, "x") as fh:
            fh.writelines(json.dumps(r, sort_keys=True) + "\n" for r in rows)
        asha = _write_once(acc_path, acc)
        run.outputs = {"rowsSha256": sha256_file(rows_path), "accountingSha256": asha, "inputManifestSha256": msha}
        note_fit_use(a.window, "rows", fsha)
    print(json.dumps({**run.outputs, "runNumber": run.run_number, **{k: v for k, v in acc.items() if not k.endswith("Keys")}}, indent=1))
    return 0


def _cmd_score(a, proto, psha, led) -> int:
    fit, fsha = guard_fit_sha(led, a.out, a.fit_sha, psha)
    if a.window == "h2":
        guard_h2_ledger(led, "score")
    rows_end = led.completed("rows", a.window)
    if not rows_end:
        led.refuse("score", a.window, "the run ledger has no completed rows for this window")
    rows_path = os.path.join(a.out, a.window, "rows.jsonl")
    acc_path = os.path.join(a.out, a.window, "accounting.json")
    man_path = os.path.join(binding_folder(), f"input-manifest-{a.window}.json")
    with led.step("score", a.window, {"fitSha256": fsha, "rowsLedgerSeq": rows_end["startSeq"]}) as run:
        recorded = json.load(open(man_path))
        if L.canonical(input_manifest(a.window, a.out)) != L.canonical(recorded):
            raise Refused("REFUSED: the inputs differ from the write-once input manifest recorded before rows")
        for path, key in ((rows_path, "rowsSha256"), (acc_path, "accountingSha256")):
            if not os.path.exists(path) or sha256_file(path) != rows_end["outputs"][key]:
                raise Refused(f"REFUSED: {os.path.basename(path)} differs from the run ledger's rows record")
        rows = [json.loads(l) for l in open(rows_path) if l.strip()]
        res = score(rows, fit, json.load(open(acc_path)), a.window)
        res.update({"schema": "sector-wind-wsw-result-v1", "protocolId": proto["protocolId"], "protocolSha256": psha,
                    "fitSha256": fsha, "rowsSha256": rows_end["outputs"]["rowsSha256"], "accountingSha256": rows_end["outputs"]["accountingSha256"],
                    "inputManifestSha256": sha256_file(man_path), "code": code_identity(), "runNumber": run.run_number,
                    "ledgerStartLine": run.start_hash, "window": a.window, "windowLabel": WINDOW_LABEL[a.window],
                    "scoredAt": f"{_utcnow():%Y-%m-%dT%H:%M:%SZ}",
                    "clockReliance": "the H2 seal reads the system clock; the run ledger and the Sector_Ops #51 record make an early run visible",
                    "admission": "none: evidence only; any WI4/evidence change goes through refresh_wind_score.py (HELD) and Michael"})
        res_path = os.path.join(a.out, a.window, "wsw-result.json")
        run.writing()
        rsha = _write_once(res_path, res)
        run.outputs = {"resultSha256": rsha}
        run.result = res["outcome"]
        note_fit_use(a.window, "score", fsha)
    print(f"result sha256 {rsha} (run #{run.run_number})")
    print(json.dumps({"outcome": res["outcome"], "observedEvents": res["observedEvents"], "why": res["why"]}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("cmd", choices=("verify", "plan", "fit", "fetch", "rows", "score"))
    ap.add_argument("--window", choices=("cal_h1", "pw", "h2"))
    ap.add_argument("--out", help="output folder, inside the Wind research folder on the research SSD")
    ap.add_argument("--corpus-store", help="fit: an existing CAL+H1 corpus store on this machine (read in place)")
    ap.add_argument("--fit-sha", help="pw/h2: the fit sha256 recorded in the run ledger and posted on Sector_Ops #51")
    ap.add_argument("--max-pairs", type=int, help="fetch: smoke-test limit")
    ap.add_argument("--month", help="fetch: one init month YYYY-MM")
    ap.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB, help="fetch: refuse below this free space")
    a = ap.parse_args(argv)
    led = None
    try:
        proto, psha = load_protocol()
        if a.cmd == "verify":
            check_lakes()
            print(f"OK {proto['protocolId']} sha256 {psha}")
            try:
                print(f"run ledger: {binding_folder()}")
            except Refused as e:
                print(e.msg)
            return 0
        if a.cmd == "plan":
            w = a.window or "pw"
            p = night_pairs(w)
            print(json.dumps({"window": w, "initLeadPairs": len(p), "plannedRows": len(p) * STATIONS_N, "nbmMessages": len(p) * 7,
                              "byLead": {l: sum(1 for _, x in p if x == l) for l in LEADS}}, indent=1))
            return 0
        check_lakes()
        if not a.out:
            raise Refused("REFUSED: --out is required")
        a.out = guard_out(a.out)
        led = ledger()
        if a.cmd == "fit":
            return _cmd_fit(a, proto, psha, led)
        if not a.window:
            raise Refused(f"REFUSED: {a.cmd} needs --window")
        if a.window == "h2" and _utcnow() < H2_OPEN:
            led.log(a.cmd, "h2", "REFUSED", {"reason": "sealed until 2027-01-01"})
            guard_h2("h2", a.cmd)
        if a.cmd == "fetch":
            return _cmd_fetch(a, psha, led)
        if a.window == "cal_h1":
            raise Refused("REFUSED: CAL+H1 is used only by fit")
        if a.cmd == "rows":
            return _cmd_rows(a, psha, led)
        return _cmd_score(a, proto, psha, led)
    except L.LedgerRefused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 3
    except Refused as e:
        if led is not None and a.cmd in ("fit", "fetch", "rows", "score"):
            try:                                   # every invocation is recorded, refusals included (best effort)
                led.log(a.cmd, a.window or "cal_h1", "REFUSED", {"reason": e.msg[:300]})
            except Exception:
                pass
        print(e.msg, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
