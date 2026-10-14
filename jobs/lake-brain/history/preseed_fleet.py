#!/usr/bin/env python3
"""Lake Brain: offline fleet history PRE-SEED (daily.csv for the accepted bindings), provider-aware, resumable, deterministic.

PRE-REGISTRATION (committed BEFORE any test or run of this script; never edited after a result is seen)
  C1  live/history overlap check. The live series named by the binding is read for the last ~30 days, reduced to one value per lake-local
      day (median of the day's readings, plus the live ref's datumOffsetFt) and compared with the history rows of the same dates.
        >= 1 overlapping day:  d = median over the overlapping days of (live - history)
            |d| >  2.0 ft   ->  REJECT_DATUM   (the history is on another datum / is another series; the lake is NOT written)
            |d| <= 2.0 ft   ->  PASS_OVERLAP
      A single overlapping day is allowed to decide: a false reject (a flood day moving more than 2 ft inside one day) costs only a
      held lake and a manual look; a false accept would seed the wrong baseline. The check fails closed.
  C2  no overlapping day (history ends before the live window: RISE/HADS/A2W latency). Coarse check, the same 15 ft as the runtime's
      historyLiveMismatch: reference = median of the LAST 30 history rows (needs >= 10 rows, else DEFER_NO_EVIDENCE);
            |median(live) - reference| > 15.0 ft  ->  REJECT_DATUM
            otherwise                              ->  PASS_COARSE (written, but flagged `continuity=PASS_COARSE` in the manifest)
      PASS_COARSE can NOT see a datum offset between 2 and 15 ft; the manifest lists every lake that only passed coarsely.
  C3  no history rows at all -> REJECT_EMPTY; no usable live reading -> DEFER_NO_LIVE (not written, retried on the next run).
  Constants are DATUM_REJECT_MEDIAN_FT / COARSE_REJECT_FT / COARSE_REF_ROWS / COARSE_MIN_ROWS below. Warnings that do NOT change a
  verdict: tail older than STALE_TAIL_WARN_DAYS (14 d), complete-year recount more than 2 years below the binding's historyCompleteYears.

WHAT IT DOES
  Input: an `accepted_batch.json` exactly as jobs/lake-brain/review/ingest_review_result.py writes it (a sorted JSON list of lake ids) plus
  its sibling `binding_review_result.json` and the bindings table (jobs/lake-brain/data/bindings.proposed.v1.json). For every lake it pulls
  the daily history named by the binding's `history` list (cwmsDaily / usgsDaily / riseDaily / hadsDaily / tvaOperatingGuide), with the SAME
  reductions as the Swift job (Sources/SectorEngine/LakeBrain/LakeLevelFeeds*.swift): same source ids, lake-local days, per-chunk daily
  medians, 0.0 RISE placeholders dropped, USGS sentinels dropped, '%.2f', LF, ascending dates, later source wins a date. It then runs the
  continuity check C1/C2 against the live series and only then stages `history/<lakeKey>/daily.csv`.

REFUSES to run on anything that is not a legitimately formed accepted batch (see validate_batch): sorted unique id list; result file with
  criteriaVersion binding-review-v1, ruleMet true, verdict ACCEPT_BATCH, rejected <= acceptRule.maxErrors, reviewed == sampleSize,
  unsure == pending == 0, acceptedBatchCount == len(batch), 64-hex reviewCsvSha256, packId LBR-SAMPLE-*; no id of the result's
  heldBackLakes / rejectedIds / flagged57 / the repository hold lists (held_lakes.py); no id in a stratum listed in fullReviewStrata;
  every id a MACHINE_VERIFIED lake of the bindings table. When the result carries acceptedBatchSha256 (ingest_review_result.py and
  ingest_batch_review.py both write it) it must match the batch file; the run records sha256 of both files in its state and manifest,
  and a write to GCS additionally needs `--confirm-batch-sha` (first 12 hex of the batch file's sha256).

  SECOND LEGITIMATE FORM (individually reviewed, jobs/lake-brain/review/ingest_batch_review.py): a result with reviewKind
  'individual-cumulative', verdict ACCEPTED_INDIVIDUALLY and a MANDATORY acceptedBatchSha256. The batch is then the cumulative union of
  per-packet results under review_batches/ next to the batch file: every component file must exist with its recorded sha256, and
  the batch must equal exactly  (individually accepted ids) UNION (sample accepted batch MINUS lakes individually rejected / NEEDS REVIEW).
  An id that is in no component result, an edited batch, a wrong sha or a changed component file is refused. The held-lake, rejected-id,
  bindings-table and MACHINE_VERIFIED checks apply to both forms; the sample-only checks (acceptRule, sampleSize, strata) apply to the first.

SAFETY
  * Default = dry run: nothing but the work dir (state, step cache, staged files, logs) is written. `--write-dir DIR` additionally
    publishes the passed lakes' files locally (atomic rename). `--gcs-prefix gs://bucket/history` uploads the staged files with
    `--if-generation-match=0` (create only; an existing object is never replaced unless --overwrite-existing, which first copies the
    live generation to history_backup/). The flag requires --write-dir and --confirm-batch-sha and is never used by the tests.
  * No promotion to REVIEWED, no change to bindings, no RTDB, no Cloud Run. Read-only GETs against public data endpoints only.
  * Fixture batches (packId / bindings schema containing FIXTURE) run only with --allow-fixture and never with --gcs-prefix.

RATE LIMITS (per host, enforced by one process-wide gate per host; minimum seconds between two requests)
  hads (mesonet.agron.iastate.edu) 15  (IEM asks for <= ~1 request per 15-20 s; HTTP 429 backs off 60 s, doubling, 4 attempts)
  cwms (cwms-data.usace.army.mil) 1, usgs (waterservices.usgs.gov) 1, rise (data.usbr.gov) 1, nwps (api.water.noaa.gov) 1,
  a2w (water.usace.army.mil) 2, tva (www.tva.com) 2.  Hosts other than HADS publish no numeric limit; these are politeness gaps.
  Hosts are independent, so one worker per host runs concurrently (--no-parallel for one-at-a-time).

RESUME / CHECKPOINTS
  <work-dir>/state.json (atomic: tmp + fsync + os.replace) holds the per-lake status; <work-dir>/steps/<lakeKey>/*.json caches every
  fetched step (a CWMS window, a HADS 3-year chunk, a RISE page, a USGS year...) with a content hash. A killed run restarts with the same
  command: finished lakes are skipped, cached steps are re-used without a network call, corrupt cache files are re-fetched. A
  work dir is bound to one (batch sha256, bindings sha256, --now) triple; a different input needs a new work dir.

EXIT CODES  0 all lakes decided (PASS or deliberate REJECT_*), 2 refused input, 3 some lake FAILED/DEFERRED (re-run to retry).

USAGE
  preseed_fleet.py --batch jobs/lake-brain/data/accepted_batch.json --work-dir /path/work                       # dry run
  preseed_fleet.py --batch ... --work-dir W --write-dir /path/out                                                # local files
  preseed_fleet.py --batch ... --work-dir W --lakes "Lake Hartwell|SC" --record DIR                              # record responses
  preseed_fleet.py --batch ... --work-dir W --replay DIR --now 2026-10-13T12:00:00Z                              # canned responses
Contact for the User-Agent comes from env SECTOR_CONTACT (optional; none by default).
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import math
import os
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW_DIR = os.path.normpath(os.path.join(HERE, "..", "review"))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
SCRIPT_VERSION = "preseed-fleet-v1"

# ---------------------------------------------------------------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS (see the header). Do not change after seeing any result.
# ---------------------------------------------------------------------------------------------------------------------------------
DATUM_REJECT_MEDIAN_FT = 2.0
COARSE_REJECT_FT = 15.0
COARSE_REF_ROWS = 30
COARSE_MIN_ROWS = 10
STALE_TAIL_WARN_DAYS = 14
SHORTFALL_WARN_YEARS = 2
COMPLETE_YEAR_DAYS = 329                     # LakeLevelBaseline: a complete year has >= 329 daily rows


def _median(xs):
    return statistics.median(xs)


def continuity_check(live_daily, history_daily):
    """Pre-registered C1/C2/C3. `live_daily` and `history_daily`: dict 'YYYY-MM-DD' -> ft (live already on the binding's datum).

    Returns a dict with `verdict` in {PASS_OVERLAP, PASS_COARSE, REJECT_DATUM, REJECT_EMPTY, DEFER_NO_LIVE, DEFER_NO_EVIDENCE}."""
    if not history_daily:
        return dict(verdict="REJECT_EMPTY", mode="none", detail="no history rows")
    if not live_daily:
        return dict(verdict="DEFER_NO_LIVE", mode="none", detail="no usable live reading")
    overlap = sorted(set(live_daily) & set(history_daily))
    if overlap:
        diffs = [live_daily[d] - history_daily[d] for d in overlap]
        med = _median(diffs)
        verdict = "REJECT_DATUM" if abs(med) > DATUM_REJECT_MEDIAN_FT else "PASS_OVERLAP"
        return dict(verdict=verdict, mode="overlap", overlapDays=len(overlap), medianDiffFt=round(med, 3),
                    maxAbsDiffFt=round(max(abs(x) for x in diffs), 3), thresholdFt=DATUM_REJECT_MEDIAN_FT,
                    firstOverlap=overlap[0], lastOverlap=overlap[-1])
    rows = sorted(history_daily)[-COARSE_REF_ROWS:]
    if len(rows) < COARSE_MIN_ROWS:
        return dict(verdict="DEFER_NO_EVIDENCE", mode="coarse", detail=f"only {len(rows)} history rows, need {COARSE_MIN_ROWS}")
    ref = _median([history_daily[d] for d in rows])
    live_med = _median(list(live_daily.values()))
    diff = live_med - ref
    verdict = "REJECT_DATUM" if abs(diff) > COARSE_REJECT_FT else "PASS_COARSE"
    return dict(verdict=verdict, mode="coarse", overlapDays=0, medianDiffFt=round(diff, 3), thresholdFt=COARSE_REJECT_FT,
                referenceRows=len(rows), referenceFrom=rows[0], referenceTo=rows[-1])


# ---------------------------------------------------------------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------------------------------------------------------------
sys.path.insert(0, REVIEW_DIR)
import held_lakes  # noqa: E402  (repository hold lists: a held lake can never be pre-seeded)

EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
UTC = dt.timezone.utc
USER_AGENT_BASE = "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)"
BINDINGS_SCHEMA = "lake-brain-bindings-proposed/v1"
FIXTURE_MARK = "FIXTURE"
CLOSED = ("PASS", "REJECT_DATUM", "REJECT_EMPTY", "SKIP_NO_SOURCE")     # a decided lake is never re-run on resume
HOST_GAP_SECONDS = {"hads": 15.0, "cwms": 1.0, "usgs": 1.0, "rise": 1.0, "nwps": 1.0, "a2w": 2.0, "tva": 2.0}
HOST_BASE = {
    "hads": "https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py",
    "cwms": "https://cwms-data.usace.army.mil/cwms-data",
    "usgs": "https://waterservices.usgs.gov/nwis",
    "rise": "https://data.usbr.gov/rise/api",
    "nwps": "https://api.water.noaa.gov/nwps/v1",
    "a2w": "https://water.usace.army.mil/cda/reporting",
    "tva": "https://www.tva.com/RestApi",
}
LIVE_DAYS = 30
USGS_ELEVATION_PARAMS = {"00062", "62614", "62615", "62616", "72020", "72022"}
USGS_STAT_ORDER = ["00003", "32400", "30800", "00001", "00002"]
FEET_PER_METRE = 3.280839895


class PreseedError(Exception):
    """Refused input or an unrecoverable condition (exit code 2)."""


class FetchError(Exception):
    """A provider step failed; the lake is marked FAILED and retried on the next run. `permanent` = retrying cannot help."""

    def __init__(self, msg, permanent=False):
        super().__init__(msg)
        self.permanent = permanent


def lake_key(lake_id):
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id)          # BrainPlatform.lakeKey


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def md5_b64(b):
    return base64.b64encode(hashlib.md5(b).digest()).decode()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def atomic_write(path, data):
    """tmp file in the same directory + fsync + os.replace: a kill at any instant leaves the old file or the new one, never half."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def clean_tmp(root):
    n = 0
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if ".tmp." in fn:
                try:
                    os.remove(os.path.join(dp, fn))
                    n += 1
                except OSError:
                    pass
    return n


def utc_iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    """Tolerant ISO-8601 (Z, offsets, optional fraction) -> aware UTC datetime, or None."""
    if not isinstance(s, str):
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        return None
    return t.astimezone(UTC)


def from_epoch_ms(ms):
    return EPOCH + dt.timedelta(milliseconds=ms)


def local_day(t, tz):
    return t.astimezone(tz).strftime("%Y-%m-%d")


# ---- mirrors of Swift LakeDailyHistory / LakeLevelCalendar (same as backfill_tva_deep.py) -----------------------------------------
def _ints(day):
    out = []
    for s in day.split("-"):
        if s == "":
            continue
        try:
            out.append(int(s))
        except ValueError:
            pass
    return out


def doy365(day):
    p = _ints(day)
    if len(p) != 3 or not (1 <= p[1] <= 12) or not (1 <= p[2] <= 31):
        return None
    cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    d = 28 if (p[1] == 2 and p[2] == 29) else p[2]
    return cum[p[1] - 1] + d


def is_day_string(s):
    return len(s) == 10 and doy365(s) is not None


def dedupe(rows):
    """LakeDailyHistory.dedupe: one value per date, the LATER entry wins; ascending by date."""
    by = {}
    for r in rows:
        by[r[0]] = r
    return [by[d] for d in sorted(by)]


def encode(rows):
    s = "date,elevationFt,sourceId\n"
    for d, ft, src in dedupe(rows):
        s += "%s,%.2f,%s\n" % (d, ft, src)
    return s.encode("utf-8")


def decode(data):
    lines = [l for l in data.decode("utf-8", errors="replace").split("\n") if l != ""]
    out = []
    for line in lines[1:]:
        parts = line.split(",", 2)
        if len(parts) != 3:
            continue
        try:
            ft = float(parts[1])
        except ValueError:
            continue
        if not is_day_string(parts[0]):
            continue
        out.append((parts[0], ft, parts[2]))
    return out


def complete_years(rows, today_year):
    per = {}
    for d, _, _ in rows:
        y = int(d[:4])
        per[y] = per.get(y, 0) + 1
    return sorted(y for y, n in per.items() if y < today_year and n >= COMPLETE_YEAR_DAYS)


# ---------------------------------------------------------------------------------------------------------------------------------
# Structured log
# ---------------------------------------------------------------------------------------------------------------------------------
class Log:
    """One JSON object per line in <work-dir>/preseed.log.jsonl (append, flushed) and a short human line on stderr."""

    def __init__(self, path=None, echo=True, clock=time.time):
        self.path, self.echo, self.clock = path, echo, clock
        self.lock = threading.Lock()

    def emit(self, level, event, **kw):
        rec = dict(ts=round(self.clock(), 3), level=level, event=event)
        rec.update(kw)
        line = json.dumps(rec, sort_keys=True, default=str)
        with self.lock:
            if self.path:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "a") as f:
                    f.write(line + "\n")
            if self.echo:
                print("[%s] %s %s" % (level, event, " ".join(f"{k}={v}" for k, v in kw.items() if k in ("lake", "step", "status", "verdict", "error", "calls", "rows"))),
                      file=sys.stderr)

    def info(self, event, **kw):
        self.emit("INFO", event, **kw)

    def warn(self, event, **kw):
        self.emit("WARN", event, **kw)

    def error(self, event, **kw):
        self.emit("ERROR", event, **kw)


# ---------------------------------------------------------------------------------------------------------------------------------
# HTTP: transports (live / replay / recording), per-host gate, retry
# ---------------------------------------------------------------------------------------------------------------------------------
class Response:
    def __init__(self, status, body=b""):
        self.status, self.body = status, body

    @property
    def ok(self):
        return 200 <= self.status < 300


def url_key(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


class LiveTransport:
    def __init__(self, contact=None):
        ua = USER_AGENT_BASE + (f"; contact {contact}" if contact else "")
        self.user_agent = ua

    def get(self, url, accept="application/json", timeout=60):
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": accept, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return Response(r.status, r.read())
        except urllib.error.HTTPError as e:
            return Response(e.code, e.read() if hasattr(e, "read") else b"")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            raise FetchError(f"network error: {e}")


class ReplayMiss(FetchError):
    def __init__(self, url):
        super().__init__(f"replay has no recorded response for {url}", permanent=True)


class ReplayTransport:
    """Canned/recorded responses: <dir>/<sha256(url)[:20]>.json = {"url", "status", "body_b64"} or {"url", "responses": [{status, body_b64}, ...]}
    (a list is consumed in order, the last entry repeats)."""

    def __init__(self, directory, fault_exit_after_calls=None):
        self.dir = directory
        self.counts = {}
        self.calls = 0
        self.fault = fault_exit_after_calls
        self.lock = threading.Lock()

    def get(self, url, accept="application/json", timeout=60):
        with self.lock:
            self.calls += 1
            n = self.calls
        if self.fault is not None and n > self.fault:
            os._exit(137)          # test-only hard kill (no cleanup), active only with --replay and an explicit env var
        p = os.path.join(self.dir, url_key(url) + ".json")
        if not os.path.exists(p):
            raise ReplayMiss(url)
        rec = json.load(open(p))
        if "responses" in rec:
            with self.lock:
                i = self.counts.get(url, 0)
                self.counts[url] = i + 1
            r = rec["responses"][min(i, len(rec["responses"]) - 1)]
        else:
            r = rec
        return Response(int(r["status"]), base64.b64decode(r.get("body_b64", "")))


class RecordingTransport:
    def __init__(self, inner, directory):
        self.inner, self.dir = inner, directory

    def get(self, url, accept="application/json", timeout=60):
        r = self.inner.get(url, accept=accept, timeout=timeout)
        atomic_write(os.path.join(self.dir, url_key(url) + ".json"),
                     json.dumps(dict(url=url, status=r.status, body_b64=base64.b64encode(r.body).decode()), sort_keys=True))
        return r


class Meter:
    """Per-lake accounting of the HTTP work (calls, bytes, seconds in the network call, seconds slept for the gate / backoff)."""

    def __init__(self):
        self.calls = 0
        self.bytes = 0
        self.net_s = 0.0
        self.sleep_s = 0.0
        self.steps = 0
        self.cached_steps = 0
        self.by_host = {}

    def add_call(self, host, nbytes, net_s):
        self.calls += 1
        self.bytes += nbytes
        self.net_s += net_s
        h = self.by_host.setdefault(host, dict(calls=0, bytes=0, net_s=0.0))
        h["calls"] += 1
        h["bytes"] += nbytes
        h["net_s"] += net_s

    def as_dict(self):
        return dict(calls=self.calls, bytes=self.bytes, netSeconds=round(self.net_s, 3), sleepSeconds=round(self.sleep_s, 3),
                    steps=self.steps, cachedSteps=self.cached_steps,
                    byHost={k: dict(calls=v["calls"], bytes=v["bytes"], netSeconds=round(v["net_s"], 3)) for k, v in sorted(self.by_host.items())})


class Http:
    """Per-host gate (minimum seconds between two request starts, one gate per host for the whole process) + retry/backoff.
    429: sleep 60 s, doubling, up to 4 attempts (the IEM rule). 5xx / network error: 3 attempts, 2 s and 4 s apart."""

    def __init__(self, transport, log, clock=time.monotonic, sleep=time.sleep, gaps=None):
        self.transport, self.log, self.clock, self.sleep = transport, log, clock, sleep
        self.gaps = dict(HOST_GAP_SECONDS if gaps is None else gaps)
        self._last = {}
        self._locks = {h: threading.Lock() for h in HOST_BASE}

    def _gate(self, host, meter):
        with self._locks[host]:
            last = self._last.get(host)
            if last is not None:
                wake = last + self.gaps.get(host, 1.0)
                now = self.clock()
                if wake > now:
                    self.sleep(wake - now)
                    meter.sleep_s += wake - now
            self._last[host] = self.clock()

    def get(self, host, url, meter, accept="application/json", timeout=60):
        wait429, attempt = 60.0, 0
        while True:
            attempt += 1
            self._gate(host, meter)
            t0 = self.clock()
            try:
                r = self.transport.get(url, accept=accept, timeout=timeout)
            except ReplayMiss:
                raise
            except FetchError as e:
                meter.add_call(host, 0, self.clock() - t0)
                if attempt >= 3:
                    raise FetchError(f"{host}: {e} (after {attempt} attempts)")
                back = 2.0 * (2 ** (attempt - 1))
                self.log.warn("http_retry", host=host, error=str(e), attempt=attempt, backoffSeconds=back)
                self.sleep(back)
                meter.sleep_s += back
                continue
            meter.add_call(host, len(r.body), self.clock() - t0)
            if r.status == 429:
                if attempt >= 4:
                    raise FetchError(f"{host}: HTTP 429 after {attempt} attempts")
                self.log.warn("http_429_backoff", host=host, attempt=attempt, backoffSeconds=wait429)
                self.sleep(wait429)
                meter.sleep_s += wait429
                wait429 *= 2
                continue
            if r.status >= 500:
                if attempt >= 3:
                    raise FetchError(f"{host}: HTTP {r.status} after {attempt} attempts")
                back = 2.0 * (2 ** (attempt - 1))
                self.log.warn("http_retry", host=host, status=r.status, attempt=attempt, backoffSeconds=back)
                self.sleep(back)
                meter.sleep_s += back
                continue
            return r


# ---------------------------------------------------------------------------------------------------------------------------------
# Step cache (resume): every fetched step is stored atomically with a content hash
# ---------------------------------------------------------------------------------------------------------------------------------
class StepCache:
    def __init__(self, root, log):
        self.root, self.log = root, log

    def path(self, key, step):
        return os.path.join(self.root, "steps", key, re.sub(r"[^A-Za-z0-9._-]+", "_", step) + ".json")

    def run(self, key, step, meter, fn, lake=None):
        p = self.path(key, step)
        if os.path.exists(p):
            try:
                rec = json.load(open(p))
                if rec["sha256"] == sha256_bytes(canonical(rec["payload"]).encode()):
                    meter.cached_steps += 1
                    self.log.info("step_cached", lake=lake, step=step)
                    return rec["payload"]
                self.log.warn("step_cache_corrupt", lake=lake, step=step)
            except (ValueError, KeyError, OSError):
                self.log.warn("step_cache_corrupt", lake=lake, step=step)
        payload = fn()
        atomic_write(p, json.dumps(dict(step=step, sha256=sha256_bytes(canonical(payload).encode()), payload=payload), sort_keys=True))
        meter.steps += 1
        self.log.info("step_fetched", lake=lake, step=step)
        return payload


# ---------------------------------------------------------------------------------------------------------------------------------
# Provider history fetchers (mirrors of LakeLevelFeeds.swift / LakeLevelFeedsFleet.swift; each returns [(date, ft, sourceId)])
# ---------------------------------------------------------------------------------------------------------------------------------
class Ctx:
    """Everything a fetcher needs for one lake."""

    def __init__(self, lake_id, binding, http, steps, now, log, meter, a2w_cache):
        self.lake_id, self.binding, self.http, self.steps, self.now, self.log, self.meter = lake_id, binding, http, steps, now, log, meter
        self.key = lake_key(lake_id)
        self.tz = ZoneInfo(binding["timeZone"])
        self.today = local_day(now, self.tz)
        self.a2w_cache = a2w_cache

    def step(self, name, fn):
        return self.steps.run(self.key, name, self.meter, fn, lake=self.lake_id)

    def get(self, host, url, accept="application/json", timeout=60):
        return self.http.get(host, url, self.meter, accept=accept, timeout=timeout)


def daily_medians(obs, tz, src, offset=0.0):
    """obs: [(utc datetime, ft)] -> [(lake-local date, median + offset, src)] ascending (Swift dailyMedians)."""
    by = {}
    for t, ft in obs:
        by.setdefault(local_day(t, tz), []).append(ft)
    out = []
    for d in sorted(by):
        out.append((d, _median(sorted(by[d])) + offset, src))
    return out


def dedupe_obs(obs):
    """LakeLevelSeries.merge: sorted by time, one value per timestamp (last wins)."""
    by = {}
    for t, ft in obs:
        by[t] = ft
    return [(t, by[t]) for t in sorted(by)]


def _num(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)) and math.isfinite(x):
        return float(x)
    return None


# ---- CWMS ----------------------------------------------------------------------------------------------------------------------
def cwms_window_seconds(series):
    parts = series.split(".")
    minutes = 1440
    if len(parts) >= 6:
        iv = parts[3].strip("~")
        m = re.match(r"^\d+", iv)
        if m:
            n = int(m.group(0))
            if "Minute" in iv:
                minutes = n
            elif "Hour" in iv:
                minutes = n * 60
            else:
                minutes = n * 1440
    years = max(0.25, min(5.0, 60000.0 / (525960.0 / max(1, minutes))))
    return years * 365.25 * 86400


def _q(params):
    from urllib.parse import quote
    return "&".join(f"{quote(str(k), safe='')}={quote(str(v), safe=':~')}" for k, v in params)


def _iso_floor(epoch_s):
    return EPOCH.__add__(dt.timedelta(seconds=math.floor(epoch_s))).strftime("%Y-%m-%dT%H:%M:%SZ")


def cwms_fetch(ctx, office, name, begin_s, end_s):
    """All pages of one CWMS window -> [(utc datetime, ft)] (merged by timestamp). Raises FetchError on any failed page or the page limit."""
    out, page = [], None
    for attempt in range(20):
        params = [("office", office), ("name", name), ("unit", "EN"), ("begin", _iso_floor(begin_s)), ("end", _iso_floor(end_s)), ("page-size", "5000")]
        if page:
            params.append(("page", page))
        r = ctx.get("cwms", f"{HOST_BASE['cwms']}/timeseries?{_q(params)}", accept="application/json;version=2")
        if r.status == 404:
            ctx.log.warn("http_404_as_empty", lake=ctx.lake_id, host="cwms", series=name)
            break
        if not r.ok:
            raise FetchError(f"CWMS {office} {name}: HTTP {r.status}")
        try:
            raw = json.loads(r.body)
        except ValueError:
            raise FetchError(f"CWMS {name}: unreadable JSON")
        k = FEET_PER_METRE if str(raw.get("units", "ft")).lower() == "m" else 1.0
        for row in raw.get("values") or []:
            if isinstance(row, list) and len(row) >= 2 and _num(row[0]) is not None and _num(row[1]) is not None:
                out.append((from_epoch_ms(row[0]), row[1] * k))
        page = raw.get("next-page")
        if not page:
            break
        if attempt == 19:
            raise FetchError(f"CWMS {name}: page limit reached (series too dense for the window)")
    return dedupe_obs(out)


def fetch_cwms_daily(ctx, h):
    office, series = h["office"], h["series"]
    src = f"cwms:{office}:{series}"
    window = cwms_window_seconds(series)
    start = (dt.datetime(1950, 1, 1, tzinfo=UTC) - EPOCH).total_seconds()
    now_s = (ctx.now - EPOCH).total_seconds()
    rows, i = [], 0
    while start < now_s:
        end = min(start + window, now_s + 86400)
        b, e = start, end

        def go(b=b, e=e):
            obs = cwms_fetch(ctx, office, series, b, e)
            return dict(nobs=len(obs), rows=[[d, v] for d, v, _ in daily_medians(obs, ctx.tz, src)])
        p = ctx.step(f"cwms.{i:03d}.{_iso_floor(b)[:10]}", go)
        rows += [(d, v, src) for d, v in p["rows"]]
        start = end
        i += 1
    return dedupe(rows)


# ---- USGS ----------------------------------------------------------------------------------------------------------------------
def parse_usgs_dv(body, offset, src):
    try:
        obj = json.loads(body)
        series = obj["value"]["timeSeries"]
    except (ValueError, KeyError, TypeError):
        return None
    by_stat = {}
    for s in series:
        variable = s.get("variable") or {}
        nodata = _num(variable.get("noDataValue"))
        nodata = -999999.0 if nodata is None else nodata
        opts = ((variable.get("options") or {}).get("option") or [{}])
        stat = (opts[0] or {}).get("optionCode", "?")
        for block in s.get("values") or []:
            for v in block.get("value") or []:
                t = v.get("dateTime")
                try:
                    x = float(v.get("value"))
                except (TypeError, ValueError):
                    continue
                if not isinstance(t, str) or len(t) < 10 or x == nodata or x <= -990000:
                    continue
                by_stat.setdefault(stat, {})[t[:10]] = x
    merged = {}
    for stat in USGS_STAT_ORDER + sorted(k for k in by_stat if k not in USGS_STAT_ORDER):
        for d, x in (by_stat.get(stat) or {}).items():
            merged.setdefault(d, x)
    return dedupe([(d, x + offset, src) for d, x in merged.items()])


def parse_usgs_iv(body):
    try:
        obj = json.loads(body)
        series = obj["value"]["timeSeries"]
    except (ValueError, KeyError, TypeError):
        return None
    out = []
    for s in series:
        for block in s.get("values") or []:
            for v in block.get("value") or []:
                t = parse_iso(v.get("dateTime"))
                try:
                    x = float(v.get("value"))
                except (TypeError, ValueError):
                    continue
                if t is not None and x > -990000:
                    out.append((t, x))
    return out


def fetch_usgs_daily(ctx, h):
    site, param, stat, offset = h["site"], h["param"], h["stat"], float(h.get("offsetFt", 0.0))
    if param not in USGS_ELEVATION_PARAMS and offset == 0:
        raise FetchError(f"USGS {site}: parameter {param} is a gage height; refused without a datum offset", permanent=True)
    src = f"usgs:{site}:{param}:{stat}"
    base = HOST_BASE["usgs"]
    if stat != "iv":
        url = f"{base}/dv/?format=json&sites={site}&parameterCd={param}&startDT=1900-01-01&endDT={ctx.today}&siteStatus=all"
        if stat != "dv":
            url += f"&statCd={stat}"

        def go():
            r = ctx.get("usgs", url, timeout=120)
            if r.status == 404:
                return dict(rows=[])
            if not r.ok:
                raise FetchError(f"USGS dv {site}: HTTP {r.status}")
            rows = parse_usgs_dv(r.body, offset, src)
            if rows is None:
                raise FetchError(f"USGS dv {site}: unreadable JSON")
            return dict(rows=[[d, v] for d, v, _ in rows])
        return dedupe([(d, v, src) for d, v in ctx.step("usgs.dv", go)["rows"]])
    out, year, empty = [], int(ctx.today[:4]), 0
    this_year = year
    while year >= 1990 and empty < 2:
        start = f"{year}-01-01"
        end = ctx.today if year == this_year else f"{year}-12-31"
        url = f"{base}/iv/?format=json&sites={site}&parameterCd={param}&startDT={start}&endDT={end}&siteStatus=all"

        def go(url=url):
            r = ctx.get("usgs", url, timeout=120)
            if r.status == 404:
                return dict(nobs=0, rows=[])
            if not r.ok:
                raise FetchError(f"USGS iv {site} {start}: HTTP {r.status}")
            obs = parse_usgs_iv(r.body)
            if obs is None:
                raise FetchError(f"USGS iv {site} {start}: unreadable JSON")
            return dict(nobs=len(obs), rows=[[d, v] for d, v, _ in daily_medians(obs, ctx.tz, src, offset)])
        p = ctx.step(f"usgs.iv.{year}", go)
        empty = empty + 1 if p["nobs"] == 0 else 0
        out += [(d, v, src) for d, v in p["rows"]]
        year -= 1
    return dedupe(out)


# ---- RISE ----------------------------------------------------------------------------------------------------------------------
def parse_rise(body):
    try:
        obj = json.loads(body)
    except ValueError:
        return [], False
    nxt = ((obj.get("links") or {}).get("next"))
    has_next = bool(nxt) if isinstance(nxt, str) else False
    out = []
    for it in obj.get("data") or []:
        a = it.get("attributes") or {}
        t = parse_iso(a.get("dateTime"))
        v = _num(a.get("result"))
        if t is None or v is None or v <= 0:
            continue
        ra = a.get("resultAttributes")
        if isinstance(ra, dict) and isinstance(ra.get("resultType"), str) and ra["resultType"] != "observed":
            continue
        out.append((t, v))
    return out, has_next


def fetch_rise_daily(ctx, h, max_pages=60):
    item = str(h["item"])
    src = f"rise:{item}"
    obs, page = [], 1
    while page <= max_pages:
        url = f"{HOST_BASE['rise']}/result?itemId={item}&dateTime%5Bafter%5D=1900-01-01&itemsPerPage=2000&page={page}"

        def go(url=url):
            r = ctx.get("rise", url, accept="application/vnd.api+json", timeout=90)
            if not r.ok:
                raise FetchError(f"RISE item {item} page {page}: HTTP {r.status}")
            o, nxt = parse_rise(r.body)
            return dict(hasNext=nxt, obs=[[int((t - EPOCH).total_seconds()), v] for t, v in o])
        p = ctx.step(f"rise.p{page:04d}", go)
        obs += [(EPOCH + dt.timedelta(seconds=s), v) for s, v in p["obs"]]
        if not p["hasNext"]:
            break
        page += 1
    else:
        raise FetchError(f"RISE item {item}: page limit {max_pages} reached")
    return dedupe([(t.strftime("%Y-%m-%d"), v, src) for t, v in dedupe_obs(obs)])


# ---- HADS ----------------------------------------------------------------------------------------------------------------------
def parse_hads(body, prefix):
    text = body.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return []
    cols = lines[0].split(",")
    if "utc_valid" not in cols:
        return []
    ti = cols.index("utc_valid")
    vidx = [i for i, c in enumerate(cols) if c.startswith(prefix)]
    if not vidx:
        return []
    out = []
    for line in lines[1:]:
        c = line.split(",")
        if len(c) <= ti:
            continue
        t = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                t = dt.datetime.strptime(c[ti], fmt).replace(tzinfo=UTC)
                break
            except ValueError:
                pass
        if t is None:
            continue
        for i in vidx:
            if i < len(c):
                try:
                    v = float(c[i])
                except ValueError:
                    continue
                if v > -990:
                    out.append((t, v))
                    break
    return out


def fetch_hads_daily(ctx, h):
    lid, pe, offset = h["lid"], h["pe"].upper(), float(h.get("offsetFt", 0.0))
    prefix, src = pe + "IR", f"hads:{lid}:{pe}"
    this_year = int(ctx.today[:4])
    floor_year = 2009
    out, hi = [], this_year
    while hi >= floor_year:
        lo = max(floor_year, hi - 2)
        ets = ctx.now.strftime("%Y-%m-%dT%H:%MZ") if hi == this_year else f"{hi + 1}-01-01T00:00Z"
        url = f"{HOST_BASE['hads']}?stations={lid}&sts={lo}-01-01T00:00Z&ets={ets}&what=txt&delim=comma"

        def go(url=url):
            r = ctx.get("hads", url, accept="text/plain", timeout=300)        # 429 backoff lives in Http.get
            if not r.ok:
                raise FetchError(f"HADS {lid} {lo}-{hi}: HTTP {r.status}")
            obs = parse_hads(r.body, prefix)
            return dict(nobs=len(obs), rows=[[d, v] for d, v, _ in daily_medians(obs, ctx.tz, src, offset)])
        p = ctx.step(f"hads.{lo}-{hi}", go)
        if p["nobs"] == 0:
            break                          # the archive starts about 2010-12: nothing earlier (Swift: stop at the first empty chunk)
        out += [(d, v, src) for d, v in p["rows"]]
        hi = lo - 1
    return dedupe(out)


# ---- TVA operating guide -------------------------------------------------------------------------------------------------------
def _tva_num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        x = float(v)
    elif isinstance(v, str):
        try:
            x = float(v.replace(",", ""))
        except ValueError:
            return None
    else:
        return None
    return x if x > 0 else None


def parse_tva_guide(body):
    try:
        items = json.loads(body)["items"]
    except (ValueError, KeyError, TypeError):
        return None
    rows = []
    for it in items:
        day = it.get("Day")
        if not isinstance(day, str):
            continue
        p = day.split("/")
        if len(p) != 3:
            continue
        try:
            m, d = int(p[0]), int(p[1])
        except ValueError:
            continue
        rows.append(dict(md="%02d-%02d" % (m, d), cur=_tva_num(it.get("CurYrElev")), prev=_tva_num(it.get("PrevYrElev"))))
    return rows


def fetch_tva_daily(ctx, h):
    loc = h["locationId"]
    src = f"tva:operating-guide:{loc}"

    def go():
        r = ctx.get("tva", f"{HOST_BASE['tva']}/operating-guide/{loc}")
        if not r.ok:
            raise FetchError(f"TVA operating-guide/{loc}: HTTP {r.status}")
        rows = parse_tva_guide(r.body)
        if not rows:
            raise FetchError(f"TVA operating-guide/{loc}: no rows (HTML or changed schema)")
        return dict(rows=rows)
    rows = ctx.step("tva.guide", go)["rows"]
    year = int(ctx.today[:4])
    out = []
    for r in rows:
        if r["prev"] is not None:
            out.append((f"{year - 1}-{r['md']}", r["prev"], src))
        cur = f"{year}-{r['md']}"
        if r["cur"] is not None and cur <= ctx.today:
            out.append((cur, r["cur"], src))
    return dedupe(out)


HISTORY_FETCHERS = {"cwmsDaily": fetch_cwms_daily, "usgsDaily": fetch_usgs_daily, "riseDaily": fetch_rise_daily,
                    "hadsDaily": fetch_hads_daily, "tvaOperatingGuide": fetch_tva_daily}
HISTORY_HOST = {"cwmsDaily": "cwms", "usgsDaily": "usgs", "riseDaily": "rise", "hadsDaily": "hads", "tvaOperatingGuide": "tva"}


def fetch_history(ctx):
    """binding.history in order (lowest precedence first; the later entry wins a date), exactly the runtime's `fresh`."""
    rows = []
    for h in ctx.binding["history"]:
        fn = HISTORY_FETCHERS.get(h["kind"])
        if fn is None:
            raise FetchError(f"history kind {h['kind']} is not supported by the pre-seed", permanent=True)
        rows += fn(ctx, h)
    return dedupe(rows)


# ---------------------------------------------------------------------------------------------------------------------------------
# Live series (continuity check only; never written)
# ---------------------------------------------------------------------------------------------------------------------------------
def parse_tva_time(day, time_text):
    t = time_text.strip()
    up = t.upper()
    zone = None
    for abbr, z in (("EDT", "America/New_York"), ("EST", "America/New_York"), ("CDT", "America/Chicago"), ("CST", "America/Chicago")):
        if up.endswith(abbr):
            zone, t = ZoneInfo(z), t[:-3].strip()
            break
    if zone is None:
        return None
    if t.upper() == "MIDNIGHT":
        hour = 24
    elif t.upper() == "NOON":
        hour = 12
    else:
        m = re.match(r"^(\d{1,2}) (AM|PM)$", t.upper())
        if not m or not 1 <= int(m.group(1)) <= 12:
            return None
        n = int(m.group(1))
        hour = (0 if n == 12 else n) if m.group(2) == "AM" else (12 if n == 12 else n + 12)
    p = day.split("/")
    try:
        mm, dd, yy = int(p[0]), int(p[1]), int(p[2])
    except (ValueError, IndexError):
        return None
    midnight = dt.datetime(yy, mm, dd, tzinfo=zone).astimezone(UTC)
    return midnight + dt.timedelta(hours=hour)       # absolute hours from local midnight (Calendar.byAdding .hour)


def live_observations(ctx, ref):
    """Recent readings of one live ref -> [(utc datetime, ft)] (no datum offset yet). Raises FetchError."""
    prov, st, series = ref["provider"], ref["station"], ref.get("series")
    now = ctx.now
    if prov == "tva":
        r = ctx.get("tva", f"{HOST_BASE['tva']}/observed-data-48-hours/{st}")
        if not r.ok:
            raise FetchError(f"TVA observed {st}: HTTP {r.status}")
        try:
            rows = json.loads(r.body)
        except ValueError:
            raise FetchError(f"TVA observed {st}: unreadable JSON")
        out = []
        for x in rows if isinstance(rows, list) else []:
            ft = _tva_num(x.get("ReservoirElevation"))
            t = parse_tva_time(x.get("Day", ""), x.get("Time", "")) if isinstance(x.get("Day"), str) and isinstance(x.get("Time"), str) else None
            if ft and t:
                out.append((t, ft))
        return dedupe_obs(out)
    if prov == "cwms":
        b = (now - dt.timedelta(days=LIVE_DAYS) - EPOCH).total_seconds()
        e = (now + dt.timedelta(hours=1) - EPOCH).total_seconds()
        return cwms_fetch(ctx, st, series, b, e)
    if prov == "usgs":
        if series not in USGS_ELEVATION_PARAMS:
            raise FetchError(f"USGS {series} is not a lake elevation parameter", permanent=True)
        r = ctx.get("usgs", f"{HOST_BASE['usgs']}/iv/?format=json&sites={st}&parameterCd={series}&period=PT{LIVE_DAYS * 24}H")
        if not r.ok:
            raise FetchError(f"USGS iv {st}: HTTP {r.status}")
        obs = parse_usgs_iv(r.body)
        if obs is None:
            raise FetchError(f"USGS iv {st}: unreadable JSON")
        return dedupe_obs(obs)
    if prov == "rise":
        after = (now - dt.timedelta(days=LIVE_DAYS)).strftime("%Y-%m-%d")
        out = []
        for page in range(1, 4):
            r = ctx.get("rise", f"{HOST_BASE['rise']}/result?itemId={st}&dateTime%5Bafter%5D={after}&itemsPerPage=2000&page={page}", accept="application/vnd.api+json", timeout=90)
            if not r.ok:
                raise FetchError(f"RISE live {st}: HTTP {r.status}")
            o, nxt = parse_rise(r.body)
            out += o
            if not nxt:
                break
        return dedupe_obs(out)
    if prov == "nwps":
        r = ctx.get("nwps", f"{HOST_BASE['nwps']}/gauges/{st}/stageflow/observed", timeout=30)
        if not r.ok:
            raise FetchError(f"NWPS {st}: HTTP {r.status}")
        try:
            obj = json.loads(r.body)
        except ValueError:
            raise FetchError(f"NWPS {st}: unreadable JSON")
        want = (series or "")[:2]
        if want and isinstance(obj.get("pedts"), str) and not obj["pedts"].startswith(want):
            raise FetchError(f"NWPS {st}: gauge reports {obj['pedts']}, binding expects {want} (stage is not pool elevation)", permanent=True)
        if isinstance(obj.get("primaryUnits"), str) and obj["primaryUnits"].lower() != "ft":
            raise FetchError(f"NWPS {st}: primary unit {obj['primaryUnits']} is not feet", permanent=True)
        since = now - dt.timedelta(days=LIVE_DAYS)
        out = []
        for row in obj.get("data") or []:
            t, v = parse_iso(row.get("validTime")), _num(row.get("primary"))
            if t is not None and t >= since and v is not None and v > -990:
                out.append((t, v))
        return dedupe_obs(out)
    if prov == "a2w":
        district, _, code = st.partition(":")
        locs = ctx.a2w_cache.district(district.lower(), ctx)
        loc = locs.get(code)
        if loc is None:
            raise FetchError(f"Access2Water {st}: location not in the {district} listing")
        s = next((x for x in loc.get("timeseries") or [] if x.get("tsid") == series), None)
        if s is None:
            raise FetchError(f"Access2Water {st}: series {series} not listed")
        if str(s.get("unit", "ft")).lower() != "ft":
            raise FetchError(f"Access2Water {series}: unit {s.get('unit')} is not feet", permanent=True)
        t, v = parse_iso(s.get("latest_time")), _num(s.get("latest_value"))
        if t is None or v is None:
            raise FetchError(f"Access2Water {series}: no latest value")
        out = [(t, v)]
        d24 = _num(s.get("delta24hr"))
        if d24 is not None:
            out.insert(0, (t - dt.timedelta(days=1), v - d24))
        return out
    raise FetchError(f"live provider {prov} unsupported", permanent=True)


class A2WCache:
    """One GET per district for the whole run (the listing is large and shared by every lake of the district)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}

    def district(self, slug, ctx):
        with self.lock:
            if slug in self.data:
                return self.data[slug]
            r = ctx.get("a2w", f"{HOST_BASE['a2w']}/providers/{slug}/locations", timeout=90)
            if not r.ok:
                raise FetchError(f"Access2Water {slug} listing: HTTP {r.status}")
            try:
                locs = json.loads(r.body)
                d = {x["code"]: x for x in locs}
            except (ValueError, KeyError, TypeError):
                raise FetchError(f"Access2Water {slug} listing: unreadable")
            self.data[slug] = d
            return d


def fetch_live_daily(ctx):
    """Live series of the binding as {lake-local date: ft on the binding's datum}. Tries `live` refs in order; the ref used is returned."""
    errors = []
    for i, ref in enumerate(ctx.binding["live"]):
        def go(ref=ref):
            obs = live_observations(ctx, ref)
            off = float(ref.get("datumOffsetFt", 0.0) or 0.0)
            rows = daily_medians(obs, ctx.tz, "live", off)
            return dict(nobs=len(obs), daily={d: v for d, v, _ in rows}, last=(utc_iso(obs[-1][0]) if obs else None))
        try:
            p = ctx.step(f"live.{i}.{ref['provider']}", go)
        except FetchError as e:
            errors.append(f"{ref['provider']}:{ref['station']}: {e}")
            if e.permanent:
                continue
            continue
        if p["daily"]:
            return p["daily"], dict(refIndex=i, provider=ref["provider"], station=ref["station"], nobs=p["nobs"], lastObservation=p["last"])
        errors.append(f"{ref['provider']}:{ref['station']}: no readings")
    return {}, dict(refIndex=None, errors=errors)


# ---------------------------------------------------------------------------------------------------------------------------------
# Input validation: a legitimately formed accepted batch
# ---------------------------------------------------------------------------------------------------------------------------------
DEFAULT_BINDINGS = os.path.join(DATA_DIR, "bindings.proposed.v1.json")
REQUIRED_RESULT_FIELDS = ("criteriaVersion", "packId", "reviewCsvSha256", "sampleSize", "reviewed", "accepted", "rejected", "unsure", "pending",
                          "acceptRule", "ruleMet", "verdict", "rejectedIds", "fullReviewStrata", "acceptedBatchCount", "acceptedBatchFile",
                          "heldBackLakes")


def stratum_of(binding):
    # build_review_pack.py: stratum = "<research provider> | <capability>" (one real lake has researchProvider cwms-saw, provider cwms)
    return f"{binding.get('researchProvider') or binding['provider']} | {binding['capability']}"


def load_json(path, what):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise PreseedError(f"{what} unreadable: {path}: {e}")


def load_bindings(path):
    d = load_json(path, "bindings table")
    if not isinstance(d, dict) or not isinstance(d.get("bindings"), list):
        raise PreseedError("bindings table is not a lake-brain-bindings-proposed document")
    schema = str(d.get("schema", ""))
    if not (schema == BINDINGS_SCHEMA or (FIXTURE_MARK in schema.upper() and schema.startswith("lake-brain-bindings-proposed"))):
        raise PreseedError(f"bindings table schema {schema!r} is not {BINDINGS_SCHEMA}")
    rows = {}
    for b in d["bindings"]:
        if b.get("lakeId") in rows:
            raise PreseedError(f"bindings table lists {b.get('lakeId')} twice")
        rows[b["lakeId"]] = b
    return d, rows


def sample_form_problems(batch, batch_path, res):
    """The checks of the sample-based result (ingest_review_result.py)."""
    missing = [k for k in REQUIRED_RESULT_FIELDS if k not in res]
    if missing:
        raise PreseedError(f"binding_review_result.json lacks field(s) written by the ingest: {missing}")
    problems = []
    if res["criteriaVersion"] != "binding-review-v1":
        problems.append(f"criteriaVersion {res['criteriaVersion']!r} != 'binding-review-v1'")
    if res["ruleMet"] is not True or res["verdict"] != "ACCEPT_BATCH":
        problems.append(f"review verdict is {res['verdict']!r} (ruleMet={res['ruleMet']}), not an accepted batch")
    mx = (res["acceptRule"] or {}).get("maxErrors")
    if not isinstance(mx, int) or not isinstance(res["rejected"], int) or res["rejected"] > mx:
        problems.append(f"rejected {res['rejected']} exceeds acceptRule.maxErrors {mx}")
    if res["unsure"] != 0 or res["pending"] != 0:
        problems.append(f"unsure={res['unsure']} pending={res['pending']} (every row must be decided)")
    if not (isinstance(res["sampleSize"], int) and res["reviewed"] == res["sampleSize"] == res["accepted"] + res["rejected"]):
        problems.append("reviewed / sampleSize / accepted+rejected disagree")
    if res["acceptedBatchCount"] != len(batch):
        problems.append(f"acceptedBatchCount {res['acceptedBatchCount']} != {len(batch)} ids in the batch file")
    if res["acceptedBatchFile"] != "accepted_batch.json" or os.path.basename(batch_path) != "accepted_batch.json":
        problems.append("acceptedBatchFile / file name is not accepted_batch.json")
    if not re.fullmatch(r"[0-9a-f]{64}", str(res["reviewCsvSha256"])):
        problems.append("reviewCsvSha256 is not a sha256")
    if not str(res["packId"]).startswith("LBR-SAMPLE-"):
        problems.append(f"packId {res['packId']!r} is not an LBR-SAMPLE pack")
    if "acceptedBatchSha256" in res and res["acceptedBatchSha256"] != sha256_file(batch_path):
        problems.append("acceptedBatchSha256 in the result does not match the batch file")
    return problems


INDIVIDUAL_KIND = "individual-cumulative"
INDIVIDUAL_PACK_PREFIX = "LBR-CONSOLIDATED-"
INDIVIDUAL_RESULT_SCHEMA = "lake-brain-individual-review-result/v1"


def _component_file(base_dir, rel, what):
    """A component file must live under <batch dir>/review_batches/ (no path games) and exist."""
    norm = os.path.normpath(rel)
    if os.path.isabs(norm) or norm.startswith("..") or os.path.dirname(norm) != "review_batches":
        raise PreseedError(f"{what}: component path {rel!r} is not review_batches/<file>")
    path = os.path.join(base_dir, norm)
    if not os.path.isfile(path):
        raise PreseedError(f"{what}: component file not found: {path}")
    return path


def individual_cumulative_problems(batch, batch_path, res):
    """The individually reviewed form (ingest_batch_review.py): batch == individually accepted UNION (sample batch MINUS individually
    rejected / NEEDS REVIEW), every component file present with its recorded sha256, acceptedBatchSha256 mandatory."""
    need = ("criteriaVersion", "verdict", "acceptedBatchCount", "acceptedBatchFile", "acceptedBatchSha256", "components", "rejectedIds", "heldBackLakes")
    missing = [k for k in need if k not in res]
    if missing:
        raise PreseedError(f"binding_review_result.json (individual-cumulative) lacks field(s): {missing}")
    problems = []
    if res["criteriaVersion"] != "binding-review-v1":
        problems.append(f"criteriaVersion {res['criteriaVersion']!r} != 'binding-review-v1'")
    if res["verdict"] != "ACCEPTED_INDIVIDUALLY":
        problems.append(f"review verdict is {res['verdict']!r}, not ACCEPTED_INDIVIDUALLY")
    if res["acceptedBatchCount"] != len(batch):
        problems.append(f"acceptedBatchCount {res['acceptedBatchCount']} != {len(batch)} ids in the batch file")
    if res["acceptedBatchFile"] != "accepted_batch.json" or os.path.basename(batch_path) != "accepted_batch.json":
        problems.append("acceptedBatchFile / file name is not accepted_batch.json")
    if not re.fullmatch(r"[0-9a-f]{64}", str(res["acceptedBatchSha256"])):
        problems.append("acceptedBatchSha256 is missing or not a sha256 (mandatory for an individually reviewed batch)")
    elif res["acceptedBatchSha256"] != sha256_file(batch_path):
        problems.append("acceptedBatchSha256 in the result does not match the batch file (the batch was edited)")
    comps = res["components"]
    if not isinstance(comps, list) or not comps:
        raise PreseedError("individual-cumulative result has no components")
    base = os.path.dirname(os.path.abspath(batch_path))
    indiv, nonaccept, sample_ids, sample_rejected = set(), set(), set(), set()
    n_indiv = 0
    for c in comps:
        kind = c.get("kind")
        if kind == "individual":
            n_indiv += 1
            f = _component_file(base, c.get("resultFile", ""), "individual component")
            if sha256_file(f) != c.get("resultSha256"):
                problems.append(f"{c['resultFile']}: sha256 differs from the recorded one (the batch result file was changed)")
                continue
            d = load_json(f, "individual batch result")
            if d.get("schema") != INDIVIDUAL_RESULT_SCHEMA or d.get("reviewKind") != "individual" or d.get("criteriaVersion") != "binding-review-v1":
                problems.append(f"{c['resultFile']}: not an individual batch result of binding-review-v1")
            if not str(d.get("packId", "")).startswith(INDIVIDUAL_PACK_PREFIX) or d.get("packId") != c.get("packId"):
                problems.append(f"{c['resultFile']}: packId {d.get('packId')!r} is not the component's {INDIVIDUAL_PACK_PREFIX}* pack")
            if not re.fullmatch(r"[0-9a-f]{64}", str(d.get("reviewCsvSha256"))):
                problems.append(f"{c['resultFile']}: reviewCsvSha256 is not a sha256")
            ids = d.get("acceptedIds")
            if not isinstance(ids, list) or ids != sorted(set(ids)) or ids != c.get("acceptedIds"):
                problems.append(f"{c['resultFile']}: acceptedIds are not a sorted unique list equal to the component's")
                continue
            indiv |= set(ids)
            nonaccept |= set(d.get("rejectedIds") or []) | set(d.get("needsReviewIds") or [])
        elif kind == "sample":
            rf = _component_file(base, c.get("resultFile", ""), "sample component")
            bf = _component_file(base, c.get("batchFile", ""), "sample component")
            if sha256_file(rf) != c.get("resultSha256") or sha256_file(bf) != c.get("batchSha256"):
                problems.append("sample component: a file differs from its recorded sha256")
                continue
            sr, sb = load_json(rf, "sample review result"), load_json(bf, "sample accepted batch")
            mx = (sr.get("acceptRule") or {}).get("maxErrors")
            if sr.get("verdict") != "ACCEPT_BATCH" or sr.get("ruleMet") is not True or sr.get("criteriaVersion") != "binding-review-v1":
                problems.append("sample component is not an accepted binding-review-v1 sample batch")
            if not isinstance(mx, int) or not isinstance(sr.get("rejected"), int) or sr["rejected"] > mx or sr.get("unsure") != 0 or sr.get("pending") != 0:
                problems.append("sample component: rejects exceed the rule or rows are undecided")
            if not str(sr.get("packId", "")).startswith("LBR-SAMPLE-"):
                problems.append("sample component: packId is not an LBR-SAMPLE pack")
            if not isinstance(sb, list) or sb != sorted(set(sb)) or sb != c.get("ids"):
                problems.append("sample component: accepted batch is not a sorted unique list equal to the component's ids")
                continue
            sample_ids |= set(sb)
            sample_rejected |= set(sr.get("rejectedIds") or [])
        else:
            problems.append(f"unknown component kind {kind!r}")
    if n_indiv == 0:
        problems.append("no individual component (this form exists for individually reviewed lakes)")
    if indiv & nonaccept:
        problems.append(f"lake(s) both accepted and rejected / needs-review in the component results: {sorted(indiv & nonaccept)[:5]}")
    if indiv & sample_rejected:
        problems.append(f"lake(s) individually accepted but rejected in the sample: {sorted(indiv & sample_rejected)[:5]}")
    expected = indiv | (sample_ids - nonaccept)
    stray = sorted(set(batch) - expected)
    if stray:
        problems.append(f"{len(stray)} id(s) are in no batch result (not individually accepted, not an accepted sample lake): {stray[:5]}")
    lost = sorted(expected - set(batch))
    if lost:
        problems.append(f"{len(lost)} id(s) accepted in the batch results are missing from the batch file: {lost[:5]}")
    return problems


def validate_batch(batch_path, result_path, bindings_path, allow_fixture=False, gcs=False):
    """Refuse anything that is not a batch as ingest_review_result.py writes it. Returns a dict describing the validated inputs."""
    if not os.path.isfile(batch_path):
        raise PreseedError(f"accepted batch not found: {batch_path}")
    batch = load_json(batch_path, "accepted batch")
    if not isinstance(batch, list) or not batch or not all(isinstance(x, str) and x.strip() and x == x.strip() for x in batch):
        raise PreseedError("accepted batch must be a non-empty JSON list of lake id strings (ingest_review_result.py writes exactly that)")
    if len(set(batch)) != len(batch):
        raise PreseedError("accepted batch contains duplicate lake ids")
    if batch != sorted(batch):
        raise PreseedError("accepted batch is not sorted (ingest writes sorted(...)); it was edited or is not the ingest's output")
    result_path = result_path or os.path.join(os.path.dirname(os.path.abspath(batch_path)), "binding_review_result.json")
    if not os.path.isfile(result_path):
        raise PreseedError(f"binding_review_result.json not found next to the batch: {result_path}")
    res = load_json(result_path, "binding review result")
    if not isinstance(res, dict):
        raise PreseedError("binding_review_result.json is not an object")
    individual = res.get("reviewKind") == INDIVIDUAL_KIND
    if individual:
        problems = individual_cumulative_problems(batch, batch_path, res)
    else:
        problems = sample_form_problems(batch, batch_path, res)
    fixture = any(FIXTURE_MARK in str(x).upper() for x in [res.get("packId", "")] + [c.get("packId", "") for c in res.get("components", []) if isinstance(c, dict)])
    bdoc, brows = load_bindings(bindings_path)
    fixture = fixture or FIXTURE_MARK in str(bdoc.get("schema", "")).upper()
    if fixture and (not allow_fixture or gcs or os.path.abspath(bindings_path) == os.path.abspath(DEFAULT_BINDINGS)):
        raise PreseedError("fixture batch/bindings are only accepted with --allow-fixture, never with --gcs-prefix and never with the real bindings table")
    if not fixture and allow_fixture:
        pass                                  # --allow-fixture is permissive only; a real batch still has to pass every check
    held = set(res["heldBackLakes"]) | held_lakes.load_snapshot()
    f57 = res.get("flagged57") or {}
    flagged = set()
    for k in ("acceptedIds", "rejectedIds", "unsureIds", "pendingIds"):
        flagged |= set(f57.get(k) or [])
    bad = lambda s: sorted(set(batch) & set(s))
    if bad(held):
        problems.append(f"{len(bad(held))} id(s) are held back lakes: {bad(held)[:5]}")
    if bad(res["rejectedIds"]):
        problems.append(f"rejected ids in the batch: {bad(res['rejectedIds'])[:5]}")
    if bad(flagged):
        problems.append(f"flagged-57 ids in the batch: {bad(flagged)[:5]}")
    notb = sorted(set(batch) - set(brows))
    if notb:
        problems.append(f"{len(notb)} id(s) are not in the bindings table: {notb[:5]}")
    not_mv = sorted(l for l in batch if l in brows and brows[l].get("status") != "MACHINE_VERIFIED")
    if not_mv:
        problems.append(f"{len(not_mv)} id(s) are not MACHINE_VERIFIED in the bindings table: {not_mv[:5]}")
    bad_strata = set(res.get("fullReviewStrata") or [])
    in_bad = sorted(l for l in batch if l in brows and stratum_of(brows[l]) in bad_strata)
    if in_bad:
        problems.append(f"{len(in_bad)} id(s) are in a stratum that needs full review: {in_bad[:5]}")
    if problems:
        raise PreseedError("not a legitimately formed accepted batch: " + "; ".join(problems))
    return dict(batch=batch, result=res, bindings=brows, bindingsDoc=bdoc, fixture=fixture, batchSha256=sha256_file(batch_path),
                resultSha256=sha256_file(result_path), bindingsSha256=sha256_file(bindings_path))


# ---------------------------------------------------------------------------------------------------------------------------------
# Call/time plan (no network): what a lake costs, per host
# ---------------------------------------------------------------------------------------------------------------------------------
def cwms_series_minutes(series):
    parts = series.split(".")
    if len(parts) >= 6:
        iv = parts[3].strip("~")
        m = re.match(r"^\d+", iv)
        if m:
            n = int(m.group(0))
            return max(1, n if "Minute" in iv else n * 60 if "Hour" in iv else n * 1440)
    return 1440


def load_cwms_catalog(path):
    """Research catalog (jsonl, Sector_Research_Data/lake-brain/binding/catalog_usgs_cwms.jsonl): sid -> first year of the CWMS series."""
    out = {}
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("prov") == "cwms" and isinstance(d.get("begin"), str) and d.get("sid") and d["begin"][:4].isdigit():
                out[d["sid"]] = int(d["begin"][:4])
    return out


def cwms_series_interval_token(series):
    parts = series.split(".")
    if len(parts) >= 6:
        m = re.match(r"^\d+", parts[3].strip("~"))
        if m:
            return int(m.group(0))
    return None


def plan_lake(binding, now, cwms_first_years=None):
    """Expected HTTP calls per host for one lake (history + one live read). A model, compared with the measured smoke in the rollout doc.
    `cwms_first_years` (sid -> first year, from the research catalog) replaces the binding's historyFirstYear for CWMS series: the binding's
    value is the research window (2018 for many sub-daily series) and can be 20-30 years later than the series really starts."""
    calls = {}
    year_now = now.year
    first = binding.get("historyFirstYear")
    if cwms_first_years:
        for h in binding.get("history", []):
            if h["kind"] == "cwmsDaily":
                y = cwms_first_years.get(f"cwms:{h['office']}:{h['series']}")
                if y:
                    first = min(first, y) if first else y
    span_years = max(1, year_now - first + 1) if first else 1
    def add(h, n):
        calls[h] = calls.get(h, 0) + n
    for h in binding.get("history", []):
        k = h["kind"]
        if k == "cwmsDaily":
            window = cwms_window_seconds(h["series"])
            chunks = math.ceil(((now - dt.datetime(1950, 1, 1, tzinfo=UTC)).total_seconds()) / window)
            minutes = cwms_series_minutes(h["series"])
            irregular = cwms_series_interval_token(h["series"]) == 0          # "...Inst.0.0.x": Swift window = 0.25 y; readings per window unknown, 1 page assumed
            pts_per_year = 0 if irregular else 525960 / minutes
            data_chunks = max(1, math.ceil(span_years * 365.25 * 86400 / window))
            pages = 1 if irregular else max(1, math.ceil(min(window / (365.25 * 86400), span_years) * pts_per_year / 5000))
            add("cwms", (chunks - data_chunks) + data_chunks * pages)
        elif k == "usgsDaily":
            add("usgs", 1 if h["stat"] != "iv" else min(span_years, year_now - 1990 + 1) + 2)
        elif k == "riseDaily":
            add("rise", max(1, math.ceil(span_years * 365.25 / 2000)))
        elif k == "hadsDaily":
            add("hads", math.ceil(min(span_years, year_now - 2008) / 3) + 1)
        elif k == "tvaOperatingGuide":
            add("tva", 1)
    live = (binding.get("live") or [{}])[0].get("provider")
    if live:
        add(live if live in HOST_BASE else "cwms", 1 + (1 if live == "rise" else 0))
    return calls


# ---------------------------------------------------------------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------------------------------------------------------------
class State:
    def __init__(self, path, init):
        self.path, self.lock = path, threading.RLock()
        if os.path.exists(path):
            self.d = load_json(path, "state file")
            for k in ("batchSha256", "bindingsSha256", "now", "scriptVersion"):
                if self.d.get(k) != init.get(k):
                    raise PreseedError(f"work dir state belongs to a different input ({k}: {self.d.get(k)!r} != {init.get(k)!r}); use a new --work-dir")
            self.resumed = True
        else:
            self.d = dict(init, schema="lake-brain-preseed-state/v1", lakes={})
            self.resumed = False
            self.save()

    def save(self):
        with self.lock:
            self.d["updatedUtc"] = utc_iso(dt.datetime.now(UTC))
            atomic_write(self.path, json.dumps(self.d, sort_keys=True, indent=1))

    def lake(self, lake_id):
        with self.lock:
            return self.d["lakes"].setdefault(lake_id, dict(status="PENDING", attempts=0))

    def update(self, lake_id, **kw):
        with self.lock:
            self.lake(lake_id).update(kw)
            self.save()


class WorkLock:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    pid = int(open(self.path).read().strip() or 0)
                    os.kill(pid, 0)
                    raise PreseedError(f"another pre-seed (pid {pid}) is running on this work dir")
                except (ValueError, ProcessLookupError, PermissionError) as e:
                    if isinstance(e, PermissionError):
                        raise PreseedError("another pre-seed holds the work dir lock")
                    os.remove(self.path)           # stale lock of a killed run
        raise PreseedError("could not take the work dir lock")

    def __exit__(self, *a):
        try:
            os.remove(self.path)
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------------------------------------------
# GCS publisher (only with --gcs-prefix; the tests exercise it through a fake command runner, never through the CLI flag)
# ---------------------------------------------------------------------------------------------------------------------------------
GCS_PREFIX_RE = re.compile(r"^gs://([a-z0-9][a-z0-9._-]*)/(history[A-Za-z0-9_./-]*?)/?$")


class GcsPublisher:
    """Create-only upload of staged files. An existing object is never replaced unless overwrite=True, in which case its exact generation is
    copied to gs://<bucket>/history_backup/<key>/daily.<ts>.csv first and the upload is `--if-generation-match=<generation>`."""

    def __init__(self, prefix, runner, overwrite=False, log=None, now=None):
        m = GCS_PREFIX_RE.match(prefix)
        if not m:
            raise PreseedError(f"--gcs-prefix must look like gs://<bucket>/history[...] (got {prefix!r})")
        self.bucket, self.path = m.group(1), m.group(2)
        self.run, self.overwrite, self.log = runner, overwrite, log
        self.now = now or dt.datetime.now(UTC)

    def uri(self, key):
        return f"gs://{self.bucket}/{self.path}/{key}/daily.csv"

    def _sh(self, cmd):
        return self.run(cmd)

    def publish(self, key, staged_path, data):
        uri = self.uri(key)
        r = self._sh(["gcloud", "storage", "objects", "describe", uri, "--format=json"])
        gen = None
        if r.returncode == 0:
            meta = json.loads(r.stdout)
            gen = str(meta["generation"])
            if not self.overwrite:
                return dict(status="SKIPPED_EXISTS", object=uri, generation=gen)
            ts = self.now.strftime("%Y%m%dT%H%M%SZ")
            backup = f"gs://{self.bucket}/history_backup/{key}/daily.{ts}.csv"
            c = self._sh(["gcloud", "storage", "cp", f"{uri}#{gen}", backup])
            if c.returncode != 0:
                raise FetchError(f"backup of {uri}#{gen} failed: {c.stderr[-300:]}")
        elif not any(s in (r.stderr or "") for s in ("404", "not found", "No URLs matched", "NotFound")):
            raise FetchError(f"describe {uri} failed: {(r.stderr or '')[-300:]}")
        cond = f"--if-generation-match={gen if gen else 0}"
        c = self._sh(["gcloud", "storage", "cp", staged_path, uri, "--content-type=text/csv", cond])
        if c.returncode != 0:
            raise FetchError(f"upload to {uri} failed: {(c.stderr or '')[-300:]}")
        d = self._sh(["gcloud", "storage", "objects", "describe", uri, "--format=json"])
        meta = json.loads(d.stdout)
        ok = meta.get("md5_hash") == md5_b64(data)
        if not ok:
            raise FetchError(f"read-back md5 of {uri} does not match the staged file")
        return dict(status="WRITTEN", object=uri, generationBefore=gen, generationAfter=str(meta["generation"]), md5Verified=True)


def default_runner(cmd):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------------------------------------------------------------
class Runner:
    def __init__(self, args, info, transport, clock=time.monotonic, sleep=time.sleep, gcs_runner=None):
        self.args, self.info = args, info
        self.work = os.path.abspath(args.work_dir)
        self.log = Log(os.path.join(self.work, "preseed.log.jsonl"), echo=not args.quiet)
        self.http = Http(transport, self.log, clock=clock, sleep=sleep, gaps=getattr(args, "gaps", None))
        self.steps = StepCache(self.work, self.log)
        self.clock = clock
        self.a2w = A2WCache()
        self.now = args.now_dt
        self.state = State(os.path.join(self.work, "state.json"), dict(
            scriptVersion=SCRIPT_VERSION, mode=info["mode"], batchSha256=info.get("batchSha256"), resultSha256=info.get("resultSha256"),
            bindingsSha256=info["bindingsSha256"], now=utc_iso(self.now), fixture=info.get("fixture", False)))
        self.meters = {}
        self.gcs = GcsPublisher(args.gcs_prefix, gcs_runner or default_runner, overwrite=args.overwrite_existing, log=self.log, now=self.now) if args.gcs_prefix else None
        self.existing_dir = args.existing_dir

    # ---- one lake ----------------------------------------------------------------------------------------------------------
    def process_lake(self, lake_id):
        binding = self.info["bindings"][lake_id]
        st = self.state.lake(lake_id)
        self.state.update(lake_id, status="RUNNING", attempts=st.get("attempts", 0) + 1, error=None)
        meter = Meter()
        self.meters[lake_id] = meter
        t0 = self.clock()
        self.log.info("lake_start", lake=lake_id, attempt=st["attempts"])
        try:
            ctx = Ctx(lake_id, binding, self.http, self.steps, self.now, self.log, meter, self.a2w)
            if not binding.get("history"):
                return self._finish(lake_id, "SKIP_NO_SOURCE", meter, t0, note="binding names no history source; the job accumulates history from live")
            rows = fetch_history(ctx)
            if self.existing_dir:
                p = os.path.join(self.existing_dir, "history", lake_key(lake_id), "daily.csv")
                if os.path.exists(p):
                    rows = dedupe(decode(open(p, "rb").read()) + rows)     # runtime merge: existing U fresh, fresh wins
            hist = {d: ft for d, ft, _ in rows}
            live, live_info = fetch_live_daily(ctx)
            cont = continuity_check(live, hist)
            cont["live"] = live_info
            warnings = []
            if rows:
                tail = dt.date.fromisoformat(rows[-1][0].replace("-02-29", "-02-28")) if rows else None
                if tail and (dt.date.fromisoformat(ctx.today) - tail).days > STALE_TAIL_WARN_DAYS:
                    warnings.append(f"STALE_TAIL:{rows[-1][0]}")
                exp = binding.get("historyCompleteYears")
                cy = len(complete_years(rows, int(ctx.today[:4])))
                if isinstance(exp, int) and cy < exp - SHORTFALL_WARN_YEARS:
                    warnings.append(f"HISTORY_SHORTFALL:{cy}<{exp}")
            if cont["verdict"] == "PASS_COARSE":
                warnings.append("CONTINUITY_COARSE_ONLY")
            data = encode(rows) if rows else b""
            common = dict(continuity=cont, warnings=sorted(warnings))
            if rows:
                common.update(rows=len(rows), first=rows[0][0], last=rows[-1][0], sha256=sha256_bytes(data), md5=md5_b64(data),
                              sourceIds=sorted({r[2] for r in rows}), bytes=len(data), completeYears=len(complete_years(rows, int(ctx.today[:4]))),
                              expectedCompleteYears=binding.get("historyCompleteYears"))
            v = cont["verdict"]
            if v in ("PASS_OVERLAP", "PASS_COARSE"):
                atomic_write(os.path.join(self.work, "staged", "history", ctx.key, "daily.csv"), data)
                return self._finish(lake_id, "PASS", meter, t0, **common)
            if v in ("REJECT_DATUM", "REJECT_EMPTY"):
                return self._finish(lake_id, v, meter, t0, **common)
            return self._finish(lake_id, "FAILED", meter, t0, error=f"{v}: {cont.get('detail', '')}", deferred=v, **common)
        except FetchError as e:
            self.log.error("lake_failed", lake=lake_id, error=str(e), permanent=e.permanent)
            return self._finish(lake_id, "FAILED", meter, t0, error=str(e), permanentError=e.permanent)
        except Exception as e:                          # a bug must not take the other lakes down; it is recorded and the exit code is 3
            import traceback
            self.log.error("lake_exception", lake=lake_id, error=repr(e), trace=traceback.format_exc()[-800:])
            return self._finish(lake_id, "FAILED", meter, t0, error=f"unexpected: {e!r}")

    def _finish(self, lake_id, status, meter, t0, **kw):
        wall = self.clock() - t0
        m = meter.as_dict()
        m["wallSeconds"] = round(wall, 3)
        self.state.update(lake_id, status=status, metrics=m, **kw)
        self.log.info("lake_done", lake=lake_id, status=status, calls=meter.calls, rows=kw.get("rows"), verdict=(kw.get("continuity") or {}).get("verdict"))
        return status

    # ---- publication -------------------------------------------------------------------------------------------------------
    def publish_lake(self, lake_id):
        st = self.state.lake(lake_id)
        if st.get("status") != "PASS":
            return
        key = lake_key(lake_id)
        staged = os.path.join(self.work, "staged", "history", key, "daily.csv")
        data = open(staged, "rb").read()
        if sha256_bytes(data) != st["sha256"]:
            raise PreseedError(f"staged file of {lake_id} does not match its recorded sha256; refusing to publish")
        pub = dict(st.get("published") or {})
        if self.args.write_dir and not pub.get("local"):
            atomic_write(os.path.join(self.args.write_dir, "history", key, "daily.csv"), data)
            pub["local"] = True
            self.log.info("published_local", lake=lake_id, rows=st["rows"])
        if self.gcs and not (pub.get("gcs") or {}).get("status") in ("WRITTEN", "SKIPPED_EXISTS"):
            try:
                pub["gcs"] = self.gcs.publish(key, staged, data)
                self.log.info("published_gcs", lake=lake_id, status=pub["gcs"]["status"])
            except FetchError as e:
                pub["gcs"] = dict(status="FAILED", error=str(e))
                self.log.error("publish_gcs_failed", lake=lake_id, error=str(e))
        self.state.update(lake_id, published=pub)

    # ---- the fleet ---------------------------------------------------------------------------------------------------------
    def todo(self, lakes):
        out = []
        for l in lakes:
            s = self.state.lake(l)
            if s["status"] not in CLOSED:
                out.append(l)
        return out

    def run(self, lakes):
        pending = self.todo(lakes)
        self.log.info("run_start", lakes=len(lakes), pending=len(pending), resumed=self.state.resumed, work=self.work, mode=self.info["mode"],
                      now=utc_iso(self.now))
        groups = {}
        for l in sorted(pending):
            hs = self.info["bindings"][l].get("history") or []
            groups.setdefault(HISTORY_HOST.get(hs[0]["kind"], "none") if hs else "none", []).append(l)
        t0 = self.clock()
        if self.args.no_parallel or len(groups) <= 1:
            for g in sorted(groups):
                for l in groups[g]:
                    self.process_lake(l)
        else:
            from concurrent.futures import ThreadPoolExecutor

            def work(g):
                for l in groups[g]:
                    self.process_lake(l)
            with ThreadPoolExecutor(max_workers=len(groups)) as ex:
                for f in [ex.submit(work, g) for g in sorted(groups)]:
                    f.result()
        for l in sorted(lakes):
            if self.args.write_dir or self.gcs:
                self.publish_lake(l)
        wall = self.clock() - t0
        self.write_reports(lakes, wall)
        return wall

    # ---- reports -----------------------------------------------------------------------------------------------------------
    def manifest(self, lakes):
        out = {}
        for l in sorted(lakes):
            s = dict(self.state.lake(l))
            keep = {k: s[k] for k in ("status", "rows", "first", "last", "sha256", "md5", "sourceIds", "bytes", "continuity", "warnings", "error",
                                      "completeYears", "expectedCompleteYears", "note") if k in s}
            keep["provider"] = self.info["bindings"][l]["provider"]
            keep["historyKinds"] = [h["kind"] for h in self.info["bindings"][l].get("history", [])]
            out[l] = keep
        counts = {}
        for v in out.values():
            counts[v["status"]] = counts.get(v["status"], 0) + 1
        return dict(schema="lake-brain-preseed-manifest/v1", scriptVersion=SCRIPT_VERSION, mode=self.info["mode"], fixture=self.info.get("fixture", False),
                    batchSha256=self.info.get("batchSha256"), resultSha256=self.info.get("resultSha256"), bindingsSha256=self.info["bindingsSha256"],
                    now=utc_iso(self.now),
                    preRegistered=dict(datumRejectMedianFt=DATUM_REJECT_MEDIAN_FT, coarseRejectFt=COARSE_REJECT_FT, coarseRefRows=COARSE_REF_ROWS,
                                       coarseMinRows=COARSE_MIN_ROWS),
                    counts=dict(sorted(counts.items())), lakes=out)

    def write_reports(self, lakes, wall):
        man = self.manifest(lakes)
        text = json.dumps(man, sort_keys=True, indent=1)
        atomic_write(os.path.join(self.work, "preseed_manifest.json"), text)
        if self.args.write_dir:
            atomic_write(os.path.join(self.args.write_dir, "preseed_manifest.json"), text)
        per = {}
        for l in lakes:
            s = self.state.lake(l)
            m = s.get("metrics")
            if not m:
                continue
            hs = self.info["bindings"][l].get("history") or []
            for host, hm in (m.get("byHost") or {}).items():
                p = per.setdefault(host, dict(calls=0, bytes=0, netSeconds=0.0, lakes=0))
                p["calls"] += hm["calls"]
                p["bytes"] += hm["bytes"]
                p["netSeconds"] += hm["netSeconds"]
            if hs:
                host = HISTORY_HOST.get(hs[0]["kind"], "none")
                p = per.setdefault(host, dict(calls=0, bytes=0, netSeconds=0.0, lakes=0))
                p["lakes"] += 1
                p.setdefault("lakeYears", 0.0)
                p.setdefault("sleepSeconds", 0.0)
                p.setdefault("wallSeconds", 0.0)
                p["sleepSeconds"] += m["sleepSeconds"]
                p["wallSeconds"] += m["wallSeconds"]
                if s.get("first") and s.get("last"):
                    p["lakeYears"] += (dt.date.fromisoformat(s["last"][:10].replace("-02-29", "-02-28")) - dt.date.fromisoformat(s["first"][:10].replace("-02-29", "-02-28"))).days / 365.25
        for p in per.values():
            for k in ("netSeconds", "sleepSeconds", "wallSeconds", "lakeYears"):
                if k in p:
                    p[k] = round(p[k], 3)
            if p.get("lakeYears"):
                p["callsPerLakeYear"] = round(p["calls"] / p["lakeYears"], 3)
                p["wallSecondsPerLakeYear"] = round(p["wallSeconds"] / p["lakeYears"], 3)
        rep = dict(schema="lake-brain-preseed-run-report/v1", generatedUtc=utc_iso(dt.datetime.now(UTC)), runWallSeconds=round(wall, 3),
                   counts=man["counts"], byHostGroup=dict(sorted(per.items())))
        atomic_write(os.path.join(self.work, "run_report.json"), json.dumps(rep, sort_keys=True, indent=1))
        self.log.info("run_done", counts=man["counts"], wallSeconds=round(wall, 3))
        return man, rep


# ---------------------------------------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", help="accepted_batch.json written by ingest_review_result.py (its sibling binding_review_result.json is read too)")
    ap.add_argument("--result", help="binding_review_result.json (default: next to --batch)")
    ap.add_argument("--bindings", default=DEFAULT_BINDINGS, help="bindings table the batch ids are looked up in")
    ap.add_argument("--work-dir", help="state, step cache, staged files, logs (the only thing a dry run writes)")
    ap.add_argument("--write-dir", help="also publish the passed lakes' history/<key>/daily.csv here (local files only)")
    ap.add_argument("--gcs-prefix", help="gs://<bucket>/history : upload staged files (create-only). Needs --write-dir and --confirm-batch-sha")
    ap.add_argument("--confirm-batch-sha", help="first 12 hex of sha256(accepted_batch.json); required with --gcs-prefix")
    ap.add_argument("--overwrite-existing", action="store_true", help="with --gcs-prefix: replace an existing object after backing up its generation")
    ap.add_argument("--existing-dir", help="directory with history/<key>/daily.csv to merge under the fresh rows (the runtime merge); optional")
    ap.add_argument("--lakes", help="comma list (subset of the batch)")
    ap.add_argument("--limit", type=int, help="first N lakes (sorted by id) after the filters")
    ap.add_argument("--only-hosts", help="comma list of the first history host of a lake: cwms,usgs,rise,hads,tva")
    ap.add_argument("--exclude-hosts", help="comma list of first-history hosts to leave for a later batch")
    ap.add_argument("--smoke", help="comma list of already-REVIEWED pilot lake ids (bindings pilotReproduction): read-only live smoke, no batch needed, no publication")
    ap.add_argument("--measure", help="comma list of any bindings-table lake ids: read-only THROUGHPUT MEASUREMENT (mode=measure), local work dir only, "
                    "never publishable, needs no batch. It is not a pre-seed and its output must not be copied into the history bucket")
    ap.add_argument("--plan", action="store_true", help="print the expected HTTP calls per host and exit (no network, no work dir writes)")
    ap.add_argument("--catalog", help="with --plan: research CWMS catalog jsonl for the real first year of each CWMS series")
    ap.add_argument("--allow-fixture", action="store_true", help="accept a FIXTURE batch (tests only; never with --gcs-prefix or the real bindings)")
    ap.add_argument("--replay", help="directory of recorded/canned responses instead of the network")
    ap.add_argument("--record", help="directory to record every live response into (for building fixtures)")
    ap.add_argument("--now", help="freeze 'now' (UTC ISO). Default: the state's value when resuming, else the clock")
    ap.add_argument("--no-parallel", action="store_true", help="one lake at a time (default: one worker per history host)")
    ap.add_argument("--quiet", action="store_true", help="no stderr log lines (the JSONL log is always written)")
    ap.add_argument("--dry-run", action="store_true", help="explicit dry run (the default); rejected together with --write-dir/--gcs-prefix")
    return ap


def select_lakes(args, info):
    lakes = list(info["batch"])
    if args.lakes:
        want = [x.strip() for x in args.lakes.split(",") if x.strip()]
        unknown = sorted(set(want) - set(lakes))
        if unknown:
            raise PreseedError(f"--lakes not in the accepted batch: {unknown}")
        lakes = [l for l in lakes if l in want]
    def host_of(l):
        hs = info["bindings"][l].get("history") or []
        return HISTORY_HOST.get(hs[0]["kind"], "none") if hs else "none"
    if args.only_hosts:
        keep = {x.strip() for x in args.only_hosts.split(",")}
        lakes = [l for l in lakes if host_of(l) in keep]
    if args.exclude_hosts:
        drop = {x.strip() for x in args.exclude_hosts.split(",")}
        lakes = [l for l in lakes if host_of(l) not in drop]
    pilots = {p["lakeId"] for p in info["bindingsDoc"].get("pilotReproduction", [])}
    skipped = [l for l in lakes if l in pilots]
    lakes = [l for l in lakes if l not in pilots]           # REVIEWED pilots keep their deep history; the pre-seed never touches them
    if args.limit:
        lakes = lakes[: args.limit]
    return lakes, skipped


def main(argv=None, transport=None, clock=time.monotonic, sleep=time.sleep, gcs_runner=None):
    args = build_parser().parse_args(argv)
    try:
        return _main(args, transport, clock, sleep, gcs_runner)
    except PreseedError as e:
        print("REFUSED:", e, file=sys.stderr)
        return 2


def _main(args, transport, clock, sleep, gcs_runner):
    if args.dry_run and (args.write_dir or args.gcs_prefix):
        raise PreseedError("--dry-run cannot be combined with --write-dir / --gcs-prefix")
    if args.gcs_prefix:
        if not args.write_dir:
            raise PreseedError("--gcs-prefix requires --write-dir (files are staged and verified locally first)")
        if args.smoke or args.measure:
            raise PreseedError("--smoke / --measure never publish")
        GcsPublisher(args.gcs_prefix, None)                       # validates the prefix shape
    # ---- inputs
    if args.measure:
        if args.write_dir or args.gcs_prefix or args.batch or args.smoke:
            raise PreseedError("--measure is read-only and takes no --batch / --write-dir / --gcs-prefix / --smoke")
        bdoc, brows = load_bindings(args.bindings)
        want = [x.strip() for x in args.measure.split(",") if x.strip()]
        bad = [w for w in want if w not in brows]
        if bad:
            raise PreseedError(f"--measure lakes not in the bindings table: {bad}")
        info = dict(mode="measure", batch=want, bindings=brows, bindingsDoc=dict(bdoc, pilotReproduction=[]), bindingsSha256=sha256_file(args.bindings),
                    fixture=False)
        lakes, skipped = want, []
    elif args.smoke:
        if args.write_dir or args.gcs_prefix or args.batch:
            raise PreseedError("--smoke is read-only and takes no --batch / --write-dir / --gcs-prefix")
        bdoc, brows = load_bindings(args.bindings)
        pilots = {p["lakeId"] for p in bdoc.get("pilotReproduction", [])}
        want = [x.strip() for x in args.smoke.split(",") if x.strip()]
        bad = [w for w in want if w not in pilots or w not in brows]
        if bad:
            raise PreseedError(f"--smoke lakes must be REVIEWED pilots of the bindings table (pilotReproduction): not pilots: {bad}")
        info = dict(mode="smoke", batch=want, bindings=brows, bindingsDoc=bdoc, bindingsSha256=sha256_file(args.bindings), fixture=False)
        lakes, skipped = want, []
    elif args.plan and not args.batch:
        bdoc, brows = load_bindings(args.bindings)
        info = dict(mode="plan", batch=sorted(brows), bindings=brows, bindingsDoc=bdoc, bindingsSha256=sha256_file(args.bindings), fixture=False)
        lakes, skipped = select_lakes(args, info)
    else:
        if not args.batch:
            raise PreseedError("--batch is required (the accepted_batch.json written by ingest_review_result.py)")
        v = validate_batch(args.batch, args.result, args.bindings, allow_fixture=args.allow_fixture, gcs=bool(args.gcs_prefix))
        if args.gcs_prefix and (args.confirm_batch_sha or "") != v["batchSha256"][:12]:
            raise PreseedError("--gcs-prefix needs --confirm-batch-sha " + v["batchSha256"][:12] + " (first 12 hex of the batch file's sha256)")
        info = dict(v, mode="plan" if args.plan else "batch")
        lakes, skipped = select_lakes(args, info)
    if args.plan:
        now = parse_iso(args.now) if args.now else dt.datetime.now(UTC)
        tot, per = {}, {}
        cat = load_cwms_catalog(args.catalog) if args.catalog else None
        for l in lakes:
            c = plan_lake(info["bindings"][l], now, cat)
            per[l] = c
            for h, n in c.items():
                tot[h] = tot.get(h, 0) + n
        print(json.dumps(dict(lakes=len(lakes), callsByHost=dict(sorted(tot.items())),
                              minSecondsByHostFromGap={h: n * HOST_GAP_SECONDS[h] for h, n in sorted(tot.items())}), indent=1))
        return 0
    if not args.work_dir:
        raise PreseedError("--work-dir is required")
    # ---- now
    state_path = os.path.join(args.work_dir, "state.json")
    if args.now:
        args.now_dt = parse_iso(args.now)
        if args.now_dt is None:
            raise PreseedError("--now must be an ISO-8601 UTC timestamp")
    elif os.path.exists(state_path):
        args.now_dt = parse_iso(load_json(state_path, "state file")["now"])
    else:
        args.now_dt = dt.datetime.now(UTC).replace(microsecond=0)
    # ---- transport
    if transport is None:
        if args.replay:
            fault = os.environ.get("SECTOR_PRESEED_FAULT_EXIT_AFTER_CALLS")          # test-only hard-kill hook, replay mode only
            transport = ReplayTransport(args.replay, int(fault) if fault else None)
        else:
            transport = LiveTransport(contact=os.environ.get("SECTOR_CONTACT"))
            if args.record:
                transport = RecordingTransport(transport, args.record)
    os.makedirs(args.work_dir, exist_ok=True)
    with WorkLock(os.path.join(args.work_dir, ".preseed.lock")):
        removed = clean_tmp(args.work_dir)
        r = Runner(args, info, transport, clock=clock, sleep=sleep, gcs_runner=gcs_runner)
        if removed:
            r.log.warn("removed_partial_tmp_files", count=removed)
        if skipped:
            r.log.info("pilots_skipped", lakes=skipped)
        r.run(lakes)
        st = [r.state.lake(l)["status"] for l in lakes]
        pub_fail = [l for l in lakes if ((r.state.lake(l).get("published") or {}).get("gcs") or {}).get("status") == "FAILED"]
        counts = {s: st.count(s) for s in sorted(set(st))}
        print(json.dumps(dict(lakes=len(lakes), counts=counts, work=r.work, manifest=os.path.join(r.work, "preseed_manifest.json")), indent=1))
        return 3 if any(s not in CLOSED for s in st) or pub_fail else 0


if __name__ == "__main__":
    sys.exit(main())
