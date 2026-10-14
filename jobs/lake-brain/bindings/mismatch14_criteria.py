"""PRE-REGISTERED acceptance criteria for the 14 history/live mismatch lakes (Task A, fleet-bindings campaign).

Written and committed BEFORE any date-matched live-vs-history comparison was computed (the only numbers known at the time were the
rules-v2 hold-out QA medians in jobs/lake-brain/validation/results/holdout_v2_results.json, which compare a multi-year MEDIAN of the history
with a 30-day median of the live series and therefore cannot separate a seasonal drawdown from a datum error). Never edited after a result.

A lake is FIXED only if the history source that the bindings generator would emit (or one corrected series chosen by SEMANTIC identity -
same location, pool/forebay elevation parameter - never by fit) satisfies ALL of:

  O1  window      : at least MIN_MATCHED_DAYS matched calendar days inside the WINDOW_DAYS days that end at the history's last day (capped at
                    the run date), both series fetched / read for the SAME calendar dates (lake-local day = the history's own date key).
  O2  centre      : median |live - history| over the matched days <= MEDIAN_ABS_FT.
  O3  tail        : 95th percentile |live - history| <= P95_ABS_FT (a datum / unit / series error shows in the tail even when the median is small).
  O4  recency     : the history series has a value within HISTORY_MAX_STALE_DAYS of the run date (a baseline that stopped years ago is not 'the live series').
  P1  operator    : an operator-published pool elevation (normal / full / top of conservation pool) is documented with a source, and the
                    directory fullPoolFt differs from it by <= POOL_TOL_FT.
  P2  plausible   : the live series' values in the window lie inside [operator minimum pool - POOL_TOL_FT, operator top-of-dam / max pool + POOL_TOL_FT].
  D1  datum       : the datum relationship is either IDENTICAL BY CONSTRUCTION (same provider, location, parameter; only interval/version differs)
                    or documented by the operator / USGS site record. A constant offset may ONLY be one that is documented; offsets are never fitted.
                    Where the datum is documented and equal, datumOffsetFt = 0.0.
  S1  short feeds : a live provider that serves only a short recent window (NWPS ~30 days, Access2Water latest value only) cannot meet O1 itself.
                    Then (a) the live series is tied to a RECORD-HOLDING read of the same series (CWMS CDA for an A2W tsid; IEM/HADS for an NWPS
                    lid with the same PE) by value agreement on every day both exist: >= SHORT_MIN_DAYS matched days, median |diff| <= SHORT_MEDIAN_FT
                    and max |diff| <= SHORT_MAX_FT; and (b) O1-O3 are evaluated between that record-holding read, freshly fetched, and the history
                    source over the WINDOW. If (a) cannot be established the lake cannot be FIXED (NEEDS HUMAN REVIEW), never FIXED on a short overlap.
                    (When the history source IS the record-holding series, (b) tests file integrity and the day-key convention only; the
                    semantic proof then rests on P1/P2 and D1.)

CORRECTLY HELD     : the mismatch is real - the live and the best semantically-correct history series differ by a documented physical reason that
                     a constant documented offset cannot remove (different water body, tailwater vs pool, different gauge datum with no record).
NO DEFENSIBLE MATCH: no history candidate of the same water body and parameter exists in the research cache or the provider catalogs.
NEEDS HUMAN REVIEW : evidence is incomplete or contradictory (operator reference missing, series ambiguous, record stale, S1 not satisfiable).
"""
MIN_MATCHED_DAYS = 365
WINDOW_DAYS = 1095
MEDIAN_ABS_FT = 0.5
P95_ABS_FT = 2.0
HISTORY_MAX_STALE_DAYS = 45
POOL_TOL_FT = 1.0
SHORT_MIN_DAYS = 20
SHORT_MEDIAN_FT = 0.1
SHORT_MAX_FT = 0.5
RUN_DATE = "2026-10-13"
CRITERIA_VERSION = "mismatch14-v1"
