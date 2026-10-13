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
  every id a MACHINE_VERIFIED lake of the bindings table. The ingest writes NO hash of the batch into the result, so a batch edited
  by hand to another subset of the same size cannot be told from a real one by content alone; the run records sha256 of both files
  in its state and manifest, and a write to GCS additionally needs `--confirm-batch-sha` (first 12 hex of the batch file's sha256).

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
