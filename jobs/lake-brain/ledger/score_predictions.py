#!/usr/bin/env python3
"""Lake Brain prospective prediction ledger: monthly scorer.

Reads one month of prediction objects (predictions/{yyyy}/{MM}/*.jsonl, written by the Lake Brain job), joins them to the realised daily levels
in each lake's history (history/{lakeKey}/daily.csv), and writes predictions_scores/{YYYY-MM}.json: COUNTS AND RATES ONLY.

  * No pass/fail verdicts. No status changes. The header repeats that Lake Brain validation remains NOT_VALIDATED.
  * A prediction whose target date has not arrived (target >= as-of date) is counted as PENDING and is NEVER scored, even if a row exists.
  * A target date that has arrived but has no row in the history is counted as MISSING (never imputed), after a grace period for late data.
  * Several predictions for one lake on one lake-local day are the same claim repeated (a stable lake publishes about every 2 h). The headline
    figures use ONE record per lake per base date (the earliest generatedAt); `allRecords` pools every record and is NOT independent data.
  * Deterministic: the same inputs and the same --as-of give byte-identical output. The month file is re-scored (overwritten) as targets arrive.

usage:
  score_predictions.py [--month YYYY-MM] [--predictions SRC] [--history SRC] [--out DIR|gs://BUCKET/PATH] [--as-of YYYY-MM-DD] [--grace-days N]
  SRC is a local directory or gs://BUCKET (read with `gcloud storage cat`); default gs://sector-lake-brain. --out default ./ledger-scores.
Python 3, standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

SCORER_VERSION = "lake-prediction-scorer-v1"
LEDGER_VERSION = "lake-prediction-ledger-v1"
RAPID_FLOOR_FT = 0.25
NOTICE = ("Counts and rates only. No pass/fail verdict, no status change. Lake Brain validation remains NOT_VALIDATED; this file existing does not "
          "make it PARTIAL. Predictions on the same lake-day are not independent, and neighbouring days and lakes on one river are correlated: "
          "do not read these rates as having sampling error bars. Judging them against the pre-registered criteria is a separate, explicit step.")
DEFAULT_SOURCE = "gs://sector-lake-brain"
TREND_LABELS = ["RISING_RAPIDLY", "RISING", "STABLE", "FALLING", "FALLING_RAPIDLY"]
DIRECTION = {"RISING_RAPIDLY": "RISING", "RISING": "RISING", "STABLE": "STABLE", "FALLING": "FALLING", "FALLING_RAPIDLY": "FALLING"}


# ----------------------------------------------------------------------------- sources

def lake_key(lake_id: str) -> str:
    """BrainPlatform.lakeKey: every run of non-[A-Za-z0-9] becomes one underscore."""
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id)


class LocalSource:
    def __init__(self, root: str):
        self.root = root

    def list(self, prefix: str) -> list[str]:
        base = os.path.join(self.root, prefix)
        out = []
        for d, _, files in os.walk(base):
            for f in files:
                if f.endswith(".jsonl"):
                    out.append(os.path.relpath(os.path.join(d, f), self.root))
        return sorted(out)

    def read(self, path: str) -> bytes | None:
        try:
            with open(os.path.join(self.root, path), "rb") as fh:
                return fh.read()
        except FileNotFoundError:
            return None


class GcsSource:
    """Read-only, via the gcloud CLI. `run` is injectable for tests: run(args) -> (returncode, stdout bytes, stderr str)."""

    def __init__(self, uri: str, run=None):
        self.uri = uri.rstrip("/")
        self.run = run or self._run

    @staticmethod
    def _run(args):
        p = subprocess.run(args, capture_output=True)
        return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")

    def list(self, prefix: str) -> list[str]:
        rc, out, err = self.run(["gcloud", "storage", "ls", f"{self.uri}/{prefix}**"])
        if rc != 0:
            if "matched no objects" in err or "One or more URLs matched no objects" in err or "No URLs matched" in err:
                return []
            raise RuntimeError(f"gcloud storage ls failed: {err.strip()}")
        names = [l.strip()[len(self.uri) + 1:] for l in out.decode().splitlines() if l.strip().startswith(self.uri + "/") and l.strip().endswith(".jsonl")]
        return sorted(names)

    def read(self, path: str) -> bytes | None:
        rc, out, err = self.run(["gcloud", "storage", "cat", f"{self.uri}/{path}"])
        if rc != 0:
            if "matched no objects" in err or "No URLs matched" in err or "404" in err or "not found" in err.lower():
                return None
            raise RuntimeError(f"gcloud storage cat failed for {path}: {err.strip()}")
        return out


def open_source(spec: str):
    return GcsSource(spec) if spec.startswith("gs://") else LocalSource(spec)


# ----------------------------------------------------------------------------- history

def parse_daily_csv(data: bytes) -> dict[str, float]:
    """history/{k}/daily.csv: `date,elevationFt,sourceId`, one row per lake-local day (the LakeDailyHistory encoder)."""
    out: dict[str, float] = {}
    for i, line in enumerate(data.decode("utf-8", "replace").splitlines()):
        if i == 0 and line.startswith("date,"):
            continue
        p = line.split(",", 2)
        if len(p) != 3:
            continue
        try:
            dt.date.fromisoformat(p[0])
            out[p[0]] = float(p[1])
        except ValueError:
            continue
    return out


class History:
    def __init__(self, source):
        self.source = source
        self.cache: dict[str, dict[str, float] | None] = {}

    def get(self, lake_id: str) -> dict[str, float] | None:
        if lake_id not in self.cache:
            d = self.source.read(f"history/{lake_key(lake_id)}/daily.csv")
            self.cache[lake_id] = None if d is None else parse_daily_csv(d)
        return self.cache[lake_id]


# ----------------------------------------------------------------------------- records

def load_records(source, month: str):
    """-> (records, info). Month = the UTC month in the object path. Malformed lines and other ledger versions are counted, not scored."""
    y, m = month.split("-")
    objects = source.list(f"predictions/{y}/{m}/")
    info = {"objects": len(objects), "lines": 0, "malformedLines": 0, "otherLedgerVersion": 0}
    records, h = [], hashlib.sha256()
    for name in objects:
        data = source.read(name)
        if data is None:
            continue
        for line in data.decode("utf-8", "replace").splitlines():
            if not line.strip():
                continue
            info["lines"] += 1
            h.update(line.encode()); h.update(b"\n")
            try:
                r = json.loads(line)
                lake, base = r["lakeId"], r["baseDate"]
                dt.date.fromisoformat(base)
                r["horizons"], r["labels"], r["generatedAt"]
            except (ValueError, KeyError, TypeError):
                info["malformedLines"] += 1
                continue
            if r.get("ledgerVersion") != LEDGER_VERSION:
                info["otherLedgerVersion"] += 1
                continue
            records.append(r)
    info["inputsSha256"] = h.hexdigest()
    return records, info


def primary_records(records):
    """One record per lake per base date: the earliest generatedAt (ties: runId)."""
    best: dict[tuple, dict] = {}
    for r in records:
        k = (r["lakeId"], r["baseDate"])
        if k not in best or (r["generatedAt"], r["runId"]) < (best[k]["generatedAt"], best[k]["runId"]):
            best[k] = r
    return sorted(best.values(), key=lambda r: (r["lakeId"], r["baseDate"]))


# ----------------------------------------------------------------------------- scoring one record

def status_of(day: dt.date, series: dict[str, float] | None, as_of: dt.date, grace: int) -> str:
    """pending: the target date has not arrived (never scored), or arrived within the grace period with no row yet.
    scored: it has arrived and the history has a row. missing: arrived, grace over, no row."""
    if day >= as_of:
        return "pending"
    if series is not None and day.isoformat() in series:
        return "scored"
    return "pending" if day >= as_of - dt.timedelta(days=grace) else "missing"


def evaluate(r: dict, series: dict[str, float] | None, as_of: dt.date, grace: int) -> dict:
    ev: dict = {"horizons": {}, "trend": None}
    kind = r.get("kind")
    rapid_stored = r.get("rapidThresholdFt")
    for h in r["horizons"]:
        t = dt.date.fromisoformat(h["targetDate"])
        st = status_of(t, series, as_of, grace)
        o: dict = {"status": st}
        if st == "scored":
            v = series[t.isoformat()]
            b = h.get("band")
            if b:
                o["in_p10_p90"] = b["p10"] <= v <= b["p90"]
                o["in_p02_p98"] = b["p02"] <= v <= b["p98"]
                o["tail_low"] = v < b["p02"]
                o["tail_high"] = v > b["p98"]
            prev = series.get((t - dt.timedelta(days=1)).isoformat())
            if prev is not None:
                change = round(abs(v - prev), 6)      # levels are 0.01 ft; strip float fuzz so a change exactly at a threshold is not 'over'
                if rapid_stored is not None:
                    o["rapid_stored"] = change > rapid_stored
                if kind == "OBSERVED":
                    thr = max(h["rateP95"], RAPID_FLOOR_FT) if h.get("rateP95") is not None else RAPID_FLOOR_FT
                    o["rapid_target"] = change > thr
        ev["horizons"][h["days"]] = o

    label = r["labels"].get("trendState")
    if label in DIRECTION:
        base = dt.date.fromisoformat(r["baseDate"])
        floor = r.get("stableFloorFt")
        t: dict = {"label": label}
        b0 = series.get(base.isoformat()) if series is not None else None
        d1, d3 = base + dt.timedelta(days=1), base + dt.timedelta(days=3)
        s1, s3 = status_of(d1, series, as_of, grace), status_of(d3, series, as_of, grace)
        if b0 is None:
            # No row for the base day itself: the forward change cannot be formed (never imputed).
            t["s1"] = "pending" if s1 == "pending" else "missing"
            t["s3"] = "pending" if s3 == "pending" else "missing"
        else:
            t["s1"], t["s3"] = s1, s3
            if s1 == "scored":
                a = round(abs(series[d1.isoformat()] - b0), 6)
                t["abs24"] = a
                if floor is not None:
                    t["le_floor"] = a <= floor
                if rapid_stored is not None:
                    t["rapid_stored"] = a > rapid_stored
            if s3 == "scored" and floor is not None:
                d = round(series[d3.isoformat()] - b0, 6)       # 3-day change; mean rate = d / 3, so compare d with 3 x floor
                t["realised"] = "STABLE" if abs(d) <= round(3 * floor, 6) else ("RISING" if d > 0 else "FALLING")
        ev["trend"] = t
    return ev


# ----------------------------------------------------------------------------- aggregation

def rate(n: int, d: int):
    return None if d == 0 else round(n / d, 6)


class Group:
    def __init__(self):
        self.records = 0
        self.h: dict[int, dict] = {}
        self.t: dict[str, dict] = {}
        self.unknown_trend = 0

    def add(self, ev: dict):
        self.records += 1
        for days, o in ev["horizons"].items():
            a = self.h.setdefault(days, {"predictions": 0, "pending": 0, "missingRealised": 0, "scored": 0, "withBand": 0, "inP10P90": 0,
                                         "inP02P98": 0, "tailLow": 0, "tailHigh": 0, "rapidStoredN": 0, "rapidStoredExceed": 0,
                                         "rapidTargetN": 0, "rapidTargetExceed": 0})
            a["predictions"] += 1
            if o["status"] == "pending":
                a["pending"] += 1
            elif o["status"] == "missing":
                a["missingRealised"] += 1
            else:
                a["scored"] += 1
                if "in_p10_p90" in o:
                    a["withBand"] += 1
                    a["inP10P90"] += o["in_p10_p90"]
                    a["inP02P98"] += o["in_p02_p98"]
                    a["tailLow"] += o["tail_low"]
                    a["tailHigh"] += o["tail_high"]
                if "rapid_stored" in o:
                    a["rapidStoredN"] += 1
                    a["rapidStoredExceed"] += o["rapid_stored"]
                if "rapid_target" in o:
                    a["rapidTargetN"] += 1
                    a["rapidTargetExceed"] += o["rapid_target"]
        t = ev["trend"]
        if t is None:
            self.unknown_trend += 1
            return
        a = self.t.setdefault(t["label"], {"predictions": 0, "next24h": {"pending": 0, "missing": 0, "scored": 0, "sumAbsChangeFt": 0.0,
                                                                          "withinStableFloor": 0, "floorN": 0, "exceedStoredRapid": 0, "rapidN": 0},
                                           "next72h": {"pending": 0, "missing": 0, "scored": 0, "realised": {"RISING": 0, "STABLE": 0, "FALLING": 0},
                                                       "samePersisted": 0}})
        a["predictions"] += 1
        n24, n72 = a["next24h"], a["next72h"]
        n24[t["s1"]] += 1
        if t["s1"] == "scored":
            n24["sumAbsChangeFt"] += t["abs24"]
            if "le_floor" in t:
                n24["floorN"] += 1; n24["withinStableFloor"] += t["le_floor"]
            if "rapid_stored" in t:
                n24["rapidN"] += 1; n24["exceedStoredRapid"] += t["rapid_stored"]
        n72[t["s3"]] += 1
        if t["s3"] == "scored" and "realised" in t:
            n72["realised"][t["realised"]] += 1
            n72["samePersisted"] += DIRECTION[t["label"]] == t["realised"]

    def out(self) -> dict:
        hz = {}
        for days in sorted(self.h):
            a = self.h[days]
            hz[str(days)] = {
                "predictions": a["predictions"], "pending": a["pending"], "missingRealised": a["missingRealised"], "scored": a["scored"],
                "bandPredictionsScored": a["withBand"],
                "coverageP10P90": {"n": a["withBand"], "inside": a["inP10P90"], "rate": rate(a["inP10P90"], a["withBand"])},
                "coverageP02P98": {"n": a["withBand"], "inside": a["inP02P98"], "rate": rate(a["inP02P98"], a["withBand"])},
                "tailOutsideP02P98": {"n": a["withBand"], "outside": a["tailLow"] + a["tailHigh"], "below": a["tailLow"], "above": a["tailHigh"],
                                      "rate": rate(a["tailLow"] + a["tailHigh"], a["withBand"])},
                "rapidExceedanceVsStoredThreshold": {"n": a["rapidStoredN"], "exceeded": a["rapidStoredExceed"],
                                                     "rate": rate(a["rapidStoredExceed"], a["rapidStoredN"])},
                "rapidExceedanceVsTargetDayThreshold": {"n": a["rapidTargetN"], "exceeded": a["rapidTargetExceed"],
                                                        "rate": rate(a["rapidTargetExceed"], a["rapidTargetN"])},
            }
        tr = {}
        for label in TREND_LABELS:
            if label not in self.t:
                continue
            a = self.t[label]; n24 = a["next24h"]; n72 = a["next72h"]
            tr[label] = {
                "predictions": a["predictions"],
                "next24h": {"scored": n24["scored"], "pending": n24["pending"], "missingRealised": n24["missing"],
                            "meanAbsChangeFt": None if n24["scored"] == 0 else round(n24["sumAbsChangeFt"] / n24["scored"], 4),
                            "withinStableFloor": {"n": n24["floorN"], "count": n24["withinStableFloor"], "rate": rate(n24["withinStableFloor"], n24["floorN"])},
                            "exceededStoredRapidThreshold": {"n": n24["rapidN"], "count": n24["exceedStoredRapid"],
                                                             "rate": rate(n24["exceedStoredRapid"], n24["rapidN"])}},
                "next72h": {"scored": n72["scored"], "pending": n72["pending"], "missingRealised": n72["missing"],
                            "realisedMeanRateClass": dict(n72["realised"]),
                            "sameDirectionAsLabel": {"n": sum(n72["realised"].values()), "count": n72["samePersisted"],
                                                     "rate": rate(n72["samePersisted"], sum(n72["realised"].values()))}},
            }
        return {"records": self.records, "horizons": hz, "labelPersistence": tr, "unknownTrendRecords": self.unknown_trend}


DIMENSIONS = ["provider", "poolBasis", "historicalTier", "kind", "rulesVersion"]


def summarise(records, history: History, as_of: dt.date, grace: int) -> dict:
    """overall / byClass / byLake for one set of records."""
    overall = Group()
    by_class: dict[str, dict[str, Group]] = {d: {} for d in DIMENSIONS}
    by_lake: dict[str, Group] = {}
    for r in records:
        ev = evaluate(r, history.get(r["lakeId"]), as_of, grace)
        overall.add(ev)
        by_lake.setdefault(r["lakeId"], Group()).add(ev)
        for d in DIMENSIONS:
            by_class[d].setdefault(str(r.get(d) or "unknown"), Group()).add(ev)
    return {"overall": overall.out(),
            "byClass": {d: {k: g.out() for k, g in sorted(by_class[d].items())} for d in DIMENSIONS},
            "byLake": {k: g.out() for k, g in sorted(by_lake.items())}}


def score_month(predictions, history, month: str, as_of: dt.date, grace: int = 3) -> dict:
    records, info = load_records(predictions, month)
    hist = History(history)
    prim = primary_records(records)
    lakes = sorted({r["lakeId"] for r in records})
    no_history = [l for l in lakes if hist.get(l) is None]
    return {
        "scorerVersion": SCORER_VERSION,
        "ledgerVersion": LEDGER_VERSION,
        "validationStatus": "NOT_VALIDATED",
        "notice": NOTICE,
        "month": month,
        "asOf": as_of.isoformat(),
        "graceDays": grace,
        "rules": {
            "pending": "target date >= asOf, or arrived within graceDays with no history row yet: counted, never scored",
            "missingRealised": "target date arrived, grace over, no history row: counted, never imputed",
            "headline": "primary = one record per lake per base date (earliest generatedAt); allRecords pools every record (not independent)",
            "coverage": "inside [p10,p90] / [p02,p98] inclusive, band from the prediction record (no recomputation); tail = outside [p02,p98]",
            "rapidExceedance": "realised |level(t) - level(t-1 d)| on the target day > stored rapidThresholdFt / > max(target-day p95, 0.25 ft)",
            "labelPersistence": "forward windows from the base day: next 24 h change vs the stored STABLE floor and RAPID threshold; next 72 h mean rate class "
                                "(STABLE if |mean| <= floor) against the predicted label's direction",
        },
        "inputs": dict(info, records=len(records), primaryRecords=len(prim), lakes=len(lakes), lakesWithoutHistory=no_history),
        "primary": summarise(prim, hist, as_of, grace),
        "allRecords": summarise(records, hist, as_of, grace),
    }


# ----------------------------------------------------------------------------- output

def to_json(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def write_out(out: str, month: str, text: str, run=None) -> str:
    rel = f"predictions_scores/{month}.json"
    if out.startswith("gs://"):
        dest = f"{out.rstrip('/')}/{rel}"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            tmp = fh.name
        try:
            rc, _, err = (run or GcsSource._run)(["gcloud", "storage", "cp", tmp, dest])
        finally:
            os.unlink(tmp)
        if rc != 0:
            raise RuntimeError(f"gcloud storage cp failed: {err.strip()}")
        return dest
    path = os.path.join(out, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def previous_month(today: dt.date) -> str:
    last = today.replace(day=1) - dt.timedelta(days=1)
    return f"{last.year:04d}-{last.month:02d}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score a month of Lake Brain predictions against realised daily levels (counts and rates only).")
    ap.add_argument("--month", help="YYYY-MM (default: the month before --as-of)")
    ap.add_argument("--predictions", default=DEFAULT_SOURCE, help="local directory or gs://BUCKET holding predictions/ (default %(default)s)")
    ap.add_argument("--history", help="local directory or gs://BUCKET holding history/ (default: --predictions)")
    ap.add_argument("--out", default="./ledger-scores", help="directory or gs://BUCKET/PATH; writes predictions_scores/{YYYY-MM}.json under it")
    ap.add_argument("--as-of", help="YYYY-MM-DD, the scoring date (default: today, UTC)")
    ap.add_argument("--grace-days", type=int, default=3)
    a = ap.parse_args(argv)
    as_of = dt.date.fromisoformat(a.as_of) if a.as_of else dt.datetime.now(dt.timezone.utc).date()
    month = a.month or previous_month(as_of)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        ap.error("--month must be YYYY-MM")
    doc = score_month(open_source(a.predictions), open_source(a.history or a.predictions), month, as_of, a.grace_days)
    dest = write_out(a.out, month, to_json(doc))
    i = doc["inputs"]
    print(f"{month}: {i['objects']} objects, {i['records']} records ({i['primaryRecords']} primary), {i['lakes']} lakes, "
          f"{i['malformedLines']} malformed -> {dest}  [NOT_VALIDATED; counts and rates only]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
