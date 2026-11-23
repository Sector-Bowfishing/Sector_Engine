#!/usr/bin/env python3
"""Wind strong-wind methods: read-only fetcher and scorer for protocol WSW-2026-11-23-R5 (gap WIND-CNF-001).

The protocol (docs/brains/wind-strong-wind/WSW-2026-11-23-R5.protocol.json) was pre-registered and hashed before any
data was fetched; its sha256 is pinned below and the runner refuses any other file (the superseded R4..R1 too). It reads
public NOAA NBM grib2 and IEM ASOS/AWOS observations and writes local files only. It never writes Firebase or a bucket,
never changes a score, an evidence file, a binding or a schedule, and admits nothing: every output is labelled
INTERNAL_EXPERIMENTAL / NOT_FOR_CUSTOMERS.

Run binding (R5 runBinding): the shared tools/research/protocol_run_ledger.py. One ledger per protocol id at
<research-path root for wind>/_ledgers/WSW-2026-11-23-R5.jsonl (CORTEX_HOME must be set), anchored on Sector_Ops #51 before
any step. Result steps fit, rows and score post a 'Run start:' and a 'Run result:' comment: the runner writes each text to
a pending file next to the ledger and waits; the Mac mini session posts it once (never reposts) and the runner confirms it.

    verify                              protocol sha256 == the pinned registration
    anchor                              open the ledger and write the 'Run anchor:' text to post on #51 (before any step)
    plan    --window cal_h1|pw|h2       (init, lead) pairs and the message estimate; no network
    fetch   --window W --month M|smoke  key fetch:<W>:<M>; resumable inside a key; --min-free-gb (default 80);
                                        pw/h2 need --fit-sha (the counted fit's output); h2 refused before 2027-01-01
    fit     --out O [--corpus-store D]  key fit:cal_h1 (result step)
    rows    --window pw|h2 --fit-sha    key rows:<W> (result step); inputs bound in the ledger first
    score   --window pw|h2 --fit-sha    key score:<W> (result step); inputs re-checked
    confirm-result --step S --window W  retry confirming a posted 'Run result:' comment
    audit                               the ledger summary, checked against #51

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
import protocol_run_ledger as PRL  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROTOCOL = os.path.join(REPO, "docs", "brains", "wind-strong-wind", "WSW-2026-11-23-R5.protocol.json")
REGISTERED_SHA256 = "a3578415c6b9f8d6a678e567234e1775512a3db9ea53ede1451f476128d0b565"
PROTOCOL_ID = "WSW-2026-11-23-R5"
RESULT_STEPS = frozenset({"fit", "rows", "score"})
FETCH_MONTHS = {"cal_h1": ("2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"),
                "pw": ("smoke", "2025-01", "2025-02", "2025-03", "2025-04", "2025-05"), "h2": ("2026-10", "2026-11", "2026-12")}
SMOKE_PAIRS = 6
WAIT_SECONDS, WAIT_LIMIT_SECONDS = 30, 6 * 3600
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


def ledger_keys() -> dict:
    """Every (step, key) the protocol fixes (R5 runBinding.keys)."""
    return {"fit": ["fit:cal_h1"],
            "fetch": [f"fetch:{w}:{m}" for w in ("cal_h1", "pw", "h2") for m in FETCH_MONTHS[w]],
            "rows": ["rows:pw", "rows:h2"], "score": ["score:pw", "score:h2"]}


def key_for(step: str, window: str, month: str | None = None) -> str:
    key = f"{step}:{window}" + (f":{month}" if step == "fetch" else "")
    if key not in ledger_keys().get(step, []):
        raise Refused(f"REFUSED: {step} key {key} is not one of the protocol's fixed keys")
    return key


def _open_ledger(forbid_under=()) -> "PRL.Ledger":
    """The protocol's run ledger: root from Cortex research-path for wind (CORTEX_HOME), --out folders forbidden as roots."""
    return PRL.Ledger.for_brain("wind", PROTOCOL_ID, REGISTERED_SHA256, repo=REPO, forbid_under=forbid_under, result_steps=RESULT_STEPS)


def guard_out(out: str, led) -> str:
    """--out must be inside the research-path folder (the research SSD) and must not contain it."""
    real = os.path.realpath(out)
    root = str(led.root)
    if os.path.commonpath([root, real]) != root or real == root:
        raise Refused(f"REFUSED: --out {out} is not a folder inside the Wind research folder {root}")
    return real


def check_lakes() -> None:
    """R4/R5 pin lakes.json and the 8 frozen stations."""
    got = sha256_file(LAKES_JSON)
    if got != LAKES_JSON_SHA256:
        raise Refused(f"REFUSED: brains/wind/runtime/lakes.json sha256 {got} differs from the registered {LAKES_JSON_SHA256}")
    ids = tuple(sorted(json.load(open(LAKES_JSON))["stations"]))
    if ids != STATION_IDS:
        raise Refused(f"REFUSED: lakes.json stations {ids} differ from the registered {STATION_IDS}")


def _utc_of(entry) -> dt.datetime:
    return dt.datetime.fromisoformat(entry["utc"].replace("Z", "+00:00"))


def guard_clock(led, window: str | None) -> None:
    """R5 runBinding.clock: no step with a clock earlier than the newest ledger entry; no H2 when the ledger has an H2 entry
    dated before the unseal date."""
    es = led.entries()
    now = _utcnow()
    if es and now < _utc_of(es[-1]):
        raise Refused(f"REFUSED: the system clock {now:%Y-%m-%dT%H:%M:%SZ} is earlier than the newest ledger entry {es[-1]['utc']}")
    if window == "h2":
        early = [e for e in es if (e.get("key") or "").split(":")[1:2] == ["h2"] and _utc_of(e) < H2_OPEN]
        if early:
            raise Refused(f"REFUSED: the ledger has an H2 entry dated {early[0]['utc']}, before the unseal date")


def began(led, step: str, key: str) -> bool:
    return any(e["step"] == step and e["key"] == key and e["status"] == PRL.STARTED for e in led.entries())


def guard_fit_sha(led, out: str, given: str | None, protocol_sha: str) -> tuple[dict, str]:
    """--fit-sha must equal the 'fit' output of the counted fit:cal_h1 entry, and the fit file in --out must match it."""
    try:
        recorded = led.require("fit", "fit:cal_h1")["outputs"]["fit"]
    except PRL.LedgerRefusal as e:
        raise Refused(f"REFUSED: no counted fit in the run ledger ({e})")
    if not given:
        raise Refused("REFUSED: --fit-sha is required (the counted fit's sha256, also posted on Sector_Ops #51)")
    if given.strip().lower() != recorded:
        raise Refused(f"REFUSED: --fit-sha {given} is not the counted fit in the run ledger ({recorded})")
    fit, fsha = load_fit(os.path.join(out, FIT_FILE), protocol_sha)
    if fsha != recorded:
        raise Refused(f"REFUSED: the fit file in --out ({fsha}) is not the counted fit ({recorded})")
    return fit, fsha


def code_identity() -> dict:
    """Runner and ledger-module sha256, the Wind runtime tree hash, and the repository git commit with a dirty flag."""
    import subprocess
    out = {"runnerSha256": sha256_file(os.path.abspath(__file__)), "ledgerModuleSha256": sha256_file(PRL.__file__),
           "windRuntime": PRL.sha256_tree(os.path.join(WIND_RUNTIME, "sector_wind"))}
    try:
        out["gitCommit"] = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        out["gitDirty"] = bool(subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--", "tools/research", "brains/wind/runtime",
                                               "docs/brains/wind-strong-wind"], capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        out["gitCommit"], out["gitDirty"] = "UNKNOWN (not a git checkout)", None
    return out


def input_files(window: str, store_root: str) -> dict:
    """What rows (and score, re-checked) read; fit uses the nbm/ and metar/ entries of its own store."""
    from pathlib import Path
    return {"nbm": Path(store_root, "nbm"), "metar": Path(store_root, "metar"), "grids": Path(store_root, "grids"),
            "lakes.json": Path(LAKES_JSON), "runner": Path(os.path.abspath(__file__)), "ledgerModule": Path(PRL.__file__),
            "windRuntime": Path(WIND_RUNTIME, "sector_wind")}


# ------------------------------------------------------------------------------------------------------------- #51 records
_sleep = time.sleep


def pending_path(led, key: str, kind: str) -> str:
    d = os.path.join(str(led.dir), f"{PROTOCOL_ID}.pending")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{key.replace(':', '_')}.{kind}.md")


def publish(led, key: str, kind: str, text: str) -> str:
    """Write the comment text for the Mac mini session to post on Sector_Ops #51, exactly once."""
    p = pending_path(led, key, kind)
    if os.path.exists(p) and open(p).read() != text:
        raise Refused(f"REFUSED: a different pending {kind} text for {key} already exists ({p})")
    with open(p, "w") as fh:
        fh.write(text)
    print(f"POST ONCE on {PRL.ANCHOR_REPO}#{PRL.ANCHOR_ISSUE} (research record; never edit or repost): {p}", flush=True)
    print(f"  gh api repos/{PRL.ANCHOR_REPO}/issues/{PRL.ANCHOR_ISSUE}/comments -F body=@'{p}'", flush=True)
    return p


def await_listed(confirm, what: str, limit: float = WAIT_LIMIT_SECONDS) -> dict:
    """Retry confirm() while #51 does not list the comment yet ('wait and retry; never repost')."""
    waited = 0.0
    while True:
        try:
            return confirm()
        except PRL.RepeatDetected:
            raise
        except PRL.LedgerRefusal as e:
            if "not listed yet" not in str(e) or waited >= limit:
                raise
        _sleep(WAIT_SECONDS)
        waited += WAIT_SECONDS


def result_step(led, step: str, key: str, args: dict, inputs: dict, compute):
    """begin -> 'Run start:' posted and confirmed -> compute (writes outputs) -> complete -> 'Run result:' posted and confirmed.
    compute(run) returns (outputs {name: Path}, result summary). Errors before any output abort the attempt; a confirmed
    start is public, so a retry of the key is then a REPEAT (it does not count)."""
    run = led.begin(step, key, args, inputs)
    try:
        publish(led, key, "start", led.start_text(step, key))
        await_listed(lambda: led.confirm_started(step, key), f"Run start {key}")
        outputs, result = compute(run)
    except BaseException as e:
        try:
            led.abort_before_result(step, key, f"{type(e).__name__}: {e}"[:300])
        except PRL.LedgerRefusal:
            pass
        raise
    entry = led.complete(step, key, outputs, result)
    publish(led, key, "result", led.result_text(step, key))
    try:
        await_listed(lambda: led.confirm_result(step, key), f"Run result {key}")
    except PRL.LedgerRefusal as e:
        print(f"Run result for {key} not confirmed yet ({e}); post it once, then run confirm-result", file=sys.stderr)
    return entry, run


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


def do_fetch(window: str, out: str, max_pairs: int | None = None, month: str | None = None, budget: "Budget | None" = None,
             min_free_gb: float = DEFAULT_MIN_FREE_GB, opener=None) -> dict:
    grib, ingest, _, store, _ = _runtime()
    for u in (ingest.NBM_CORE, ingest.NBM_QMD, ingest.IEM):
        check_host(u)
    if budget is None:
        raise Refused("REFUSED: do_fetch needs the window's budget (next to the run ledger)")
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


def _budget(led, window: str) -> Budget:
    return Budget(os.path.join(str(led.dir), f"{PROTOCOL_ID}.budget-{window}.json"))


def _cmd_fit(a, proto, psha, led) -> int:
    from pathlib import Path
    fit_path = os.path.join(a.out, FIT_FILE)
    src = os.path.realpath(a.corpus_store) if a.corpus_store else os.path.join(a.out, "cal_h1", "store")
    files = {"nbm": Path(src, "nbm"), "metar": Path(src, "metar")}
    led.bind_inputs("fit", "fit:cal_h1", files)

    def compute(run):
        if os.path.exists(fit_path):
            raise Refused("REFUSED: a fit file already exists in --out")
        rows, acc = build_rows("cal_h1", src)
        fit = fit_qm(fit_pairs(rows, acc))
        fit.update({"schema": "sector-wind-wsw-mb-fit-v1", "protocolId": proto["protocolId"], "protocolSha256": psha,
                    "window": "CAL+H1 inits 2026-05-06T00Z..2026-10-06T23Z, synoptic night pairs valid before 2026-10-07, 8 stations",
                    "source": "corpus-store" if a.corpus_store else "fetched", "accounting": acc, "runNumber": run,
                    "frozenAt": f"{_utcnow():%Y-%m-%dT%H:%M:%SZ}", "labels": LABELS})
        _write_once(fit_path, fit)
        return {"fit": Path(fit_path)}, {"n": fit["n"], "topKnot": fit["knots"][-1], "runNumber": run}
    entry, run = result_step(led, "fit", "fit:cal_h1", {"source": "corpus-store" if a.corpus_store else "fetched", "storePath": src},
                             files, compute)
    print(f"fit sha256 {entry['outputs']['fit']} (run {run}, counted {entry['counted']}). "
          "Post it on Sector_Ops #51 before any past-window fetch.")
    return 0


def _cmd_fetch(a, psha, led) -> int:
    if not a.month:
        raise Refused("REFUSED: fetch needs --month (one of the protocol's fixed keys, or 'smoke' for the past window)")
    key = key_for("fetch", a.window, a.month)
    if a.window != "cal_h1":
        guard_fit_sha(led, a.out, a.fit_sha, psha)
    if began(led, "rows", f"rows:{a.window}") if a.window != "cal_h1" else began(led, "fit", "fit:cal_h1"):
        raise Refused("REFUSED: the inputs of this window are fixed (rows or fit has begun); no further fetch")
    smoke = a.month == "smoke"
    month = "2025-01" if smoke else a.month
    month_pairs(a.window, month)
    free = guard_free_space(a.out, a.min_free_gb)
    led.begin("fetch", key, {"window": a.window, "month": a.month, "maxPairs": SMOKE_PAIRS if smoke else None})
    try:
        res = do_fetch(a.window, a.out, SMOKE_PAIRS if smoke else None, month, budget=_budget(led, a.window), min_free_gb=a.min_free_gb)
    except BaseException as e:
        led.abort_before_result("fetch", key, f"{type(e).__name__}: {e}"[:300])
        raise
    led.complete("fetch", key)
    res["freeGbBefore"], res["key"] = round(free, 1), key
    print(json.dumps(res, indent=1))
    return 0


def _cmd_rows(a, psha, led) -> int:
    from pathlib import Path
    _, fsha = guard_fit_sha(led, a.out, a.fit_sha, psha)
    key = key_for("rows", a.window)
    store_root = os.path.join(a.out, a.window, "store")
    rows_path = os.path.join(a.out, a.window, "rows.jsonl")
    acc_path = os.path.join(a.out, a.window, "accounting.json")
    files = input_files(a.window, store_root)
    led.bind_inputs("rows", key, files)

    def compute(run):
        if os.path.exists(rows_path) or os.path.exists(acc_path):
            raise Refused("REFUSED: rows are already recorded in --out; they are never overwritten")
        rows, acc = build_rows(a.window, store_root)
        os.makedirs(os.path.dirname(rows_path), exist_ok=True)
        with open(rows_path, "x") as fh:
            fh.writelines(json.dumps(r, sort_keys=True) + "\n" for r in rows)
        _write_once(acc_path, acc)
        summary = {k: v for k, v in acc.items() if not k.endswith("Keys") and k not in ("obsMissingByStation", "missingObsDays")}
        summary.update({"missingObsDays": len(acc["missingObsDays"]), "runNumber": run})
        return {"rows": Path(rows_path), "accounting": Path(acc_path)}, summary
    entry, run = result_step(led, "rows", key, {"fitSha256": fsha, "window": a.window}, files, compute)
    print(json.dumps({"key": key, "run": run, "counted": entry["counted"], **entry["outputs"]}, indent=1))
    return 0


def _cmd_score(a, proto, psha, led) -> int:
    from pathlib import Path
    fit, fsha = guard_fit_sha(led, a.out, a.fit_sha, psha)
    rkey, key = key_for("rows", a.window), key_for("score", a.window)
    try:
        rows_entry = led.require("rows", rkey)
    except PRL.LedgerRefusal as e:
        raise Refused(f"REFUSED: no counted rows for this window ({e})")
    store_root = os.path.join(a.out, a.window, "store")
    ihash = led.check_inputs("rows", rkey, input_files(a.window, store_root))
    rows_path = os.path.join(a.out, a.window, "rows.jsonl")
    acc_path = os.path.join(a.out, a.window, "accounting.json")
    for path, name in ((rows_path, "rows"), (acc_path, "accounting")):
        if not os.path.exists(path) or sha256_file(path) != rows_entry["outputs"][name]:
            raise Refused(f"REFUSED: {os.path.basename(path)} differs from the counted rows entry")
    res_path = os.path.join(a.out, a.window, "wsw-result.json")
    inputs = {"fit": fsha, "rows": rows_entry["outputs"]["rows"], "accounting": rows_entry["outputs"]["accounting"]}

    def compute(run):
        if os.path.exists(res_path):
            raise Refused("REFUSED: a result is already recorded in --out")
        rows = [json.loads(l) for l in open(rows_path) if l.strip()]
        res = score(rows, fit, json.load(open(acc_path)), a.window)
        res.update({"schema": "sector-wind-wsw-result-v1", "protocolId": proto["protocolId"], "protocolSha256": psha,
                    "fitSha256": fsha, "rowsSha256": inputs["rows"], "accountingSha256": inputs["accounting"],
                    "inputHashes": ihash, "ledgerAnchor": led.anchor(), "code": code_identity(), "runNumber": run,
                    "countedBy": "the ledger's COMPLETED entry for this key (see the 'Run result:' comment on #51)",
                    "window": a.window, "windowLabel": WINDOW_LABEL[a.window], "scoredAt": f"{_utcnow():%Y-%m-%dT%H:%M:%SZ}",
                    "clockReliance": "the H2 seal reads the system clock; the run ledger and the Sector_Ops #51 record make an early run visible",
                    "admission": "none: evidence only; any WI4/evidence change goes through refresh_wind_score.py (HELD) and Michael"})
        _write_once(res_path, res)
        return {"result": Path(res_path)}, {"outcome": res["outcome"], "observedEvents": res["observedEvents"], "runNumber": run}
    entry, run = result_step(led, "score", key, {"fitSha256": fsha, "window": a.window}, inputs, compute)
    print(json.dumps({"key": key, "run": run, "counted": entry["counted"], "result": entry["result"]}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("cmd", choices=("verify", "anchor", "plan", "fit", "fetch", "rows", "score", "confirm-result", "audit"))
    ap.add_argument("--window", choices=("cal_h1", "pw", "h2"))
    ap.add_argument("--step", choices=("fit", "rows", "score"), help="confirm-result: the result step")
    ap.add_argument("--out", help="output folder, inside the Wind research folder on the research SSD")
    ap.add_argument("--corpus-store", help="fit: an existing CAL+H1 corpus store (read in place; may be outside the research root)")
    ap.add_argument("--fit-sha", help="pw/h2: the counted fit's sha256 (ledger), also posted on Sector_Ops #51")
    ap.add_argument("--month", help="fetch: YYYY-MM of the window, or 'smoke' (past window only)")
    ap.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB, help="fetch: refuse below this free space")
    a = ap.parse_args(argv)
    try:
        proto, psha = load_protocol()
        if a.cmd == "verify":
            check_lakes()
            print(f"OK {proto['protocolId']} sha256 {psha}")
            return 0
        if a.cmd == "plan":
            w = a.window or "pw"
            p = night_pairs(w)
            print(json.dumps({"window": w, "initLeadPairs": len(p), "plannedRows": len(p) * STATIONS_N, "nbmMessages": len(p) * 7,
                              "byLead": {l: sum(1 for _, x in p if x == l) for l in LEADS}}, indent=1))
            return 0
        check_lakes()
        if a.cmd in ("anchor", "audit", "confirm-result"):
            led = _open_ledger()
            if a.cmd == "anchor":
                publish(led, "anchor", "anchor", led.post_anchor_text())
                return 0
            if a.cmd == "audit":
                print(json.dumps(led.audit(check_external=True), indent=1, default=str))
                return 0
            if not (a.step and a.window):
                raise Refused("REFUSED: confirm-result needs --step and --window")
            print(json.dumps(await_listed(lambda: led.confirm_result(a.step, key_for(a.step, a.window)), "Run result"), indent=1, default=str))
            return 0
        if not a.out:
            raise Refused("REFUSED: --out is required")
        led = _open_ledger(forbid_under=[a.out])
        a.out = guard_out(a.out, led)
        if a.cmd == "fit":
            guard_clock(led, "cal_h1")
            return _cmd_fit(a, proto, psha, led)
        if not a.window:
            raise Refused(f"REFUSED: {a.cmd} needs --window")
        guard_h2(a.window, a.cmd)
        guard_clock(led, a.window)
        if a.cmd == "fetch":
            return _cmd_fetch(a, psha, led)
        if a.window == "cal_h1":
            raise Refused("REFUSED: CAL+H1 is used only by fit")
        if a.cmd == "rows":
            return _cmd_rows(a, psha, led)
        return _cmd_score(a, proto, psha, led)
    except PRL.LedgerRefusal as e:
        print(f"REFUSED by the run ledger: {e}", file=sys.stderr)
        return 3
    except Refused as e:
        print(e.msg, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
