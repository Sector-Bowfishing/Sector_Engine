"""Water Temp TVA discharge archiver — hourly, append-only, idempotent.

TVA's public RestApi keeps only today's hours (observed-data) and a 3-day
outlook (predicted-data); anything older is gone. This job keeps it, for the
Water Temp cascade work (Guntersville → Wheeler → Wilson → Pickwick), entirely
separate from Clarity's hydrology-hourly job.

Layout under <prefix> (default "water-temp/tva"):
  raw/<DAM>/<observed|predicted>/<YYYY-MM-DDTHH>Z.json   exact response bytes, one per fetch hour (UTC)
  <DAM>/<YYYY-MM-DD>.json                                 daily record (local TVA date):
      observed[<ISO local hour>] = {raw, parsed, firstSeenAt, source}
      revisions[]               = later fetches whose values differ (never overwritten)
      predicted[<fetch hour Z>] = {fetchedAt, raw rows}

Rules: never overwrite an observed hour, never fill a gap, raise on any schema
change or empty response, exit non-zero if any dam failed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from typing import Callable, Optional

import requests

BASE = "https://www.tva.com/RestApi"
DAMS = ["NKJT1", "GVDA1", "WHLA1", "WLSA1", "PICT1"]
OBSERVED_KEYS = {"Day", "Time", "ReservoirElevation", "TailwaterElevation", "AverageHourlyDischarge"}
PREDICTED_KEYS = {"Day", "AverageInflow", "MidnightElevation", "AverageOutflow"}
TZ_OFFSETS = {"CDT": -5, "CST": -6, "EDT": -4, "EST": -5}
TIME_RE = re.compile(r"^(\d{1,2}) (AM|PM) (CDT|CST|EDT|EST)$")
SCHEMA_VERSION = 1


class SchemaError(Exception):
    pass


# ---------- parsing ----------

def number(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.replace(",", "").strip()
        if re.fullmatch(r"-?\d+(\.\d+)?", s):
            return float(s)
    raise SchemaError(f"not a number: {v!r}")


def local_hour(day: str, tm: str) -> dt.datetime:
    m = TIME_RE.match(tm.strip())
    if not m:
        raise SchemaError(f"unexpected Time format: {tm!r}")
    hour = int(m.group(1)) % 12 + (12 if m.group(2) == "PM" else 0)
    d = dt.datetime.strptime(day, "%m/%d/%Y")
    tz = dt.timezone(dt.timedelta(hours=TZ_OFFSETS[m.group(3)]))
    return d.replace(hour=hour, tzinfo=tz)


def check_rows(rows, keys: set, kind: str):
    if not isinstance(rows, list) or not rows:
        raise SchemaError(f"{kind}: expected a non-empty JSON list, got {type(rows).__name__} len={len(rows) if isinstance(rows, list) else '-'}")
    for r in rows:
        if not isinstance(r, dict) or set(r) != keys:
            raise SchemaError(f"{kind}: keys changed: {sorted(r) if isinstance(r, dict) else r!r}")


def parse_observed(rows):
    check_rows(rows, OBSERVED_KEYS, "observed")
    out = []
    for r in rows:
        t = local_hour(r["Day"], r["Time"])
        out.append((t.isoformat(), {
            "localTime": t.isoformat(),
            "utcTime": t.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "reservoirElevationFt": number(r["ReservoirElevation"]),
            "tailwaterElevationFt": number(r["TailwaterElevation"]),
            "avgHourlyDischargeCfs": number(r["AverageHourlyDischarge"]),
        }, r))
    return out


def parse_predicted(rows):
    check_rows(rows, PREDICTED_KEYS, "predicted")
    for r in rows:
        dt.datetime.strptime(r["Day"], "%m/%d/%Y")
        number(r["AverageInflow"]); number(r["MidnightElevation"]); number(r["AverageOutflow"])
    return rows


# ---------- storage ----------

class LocalStore:
    """Filesystem store (tests, dry runs). Same semantics as GCSStore."""

    def __init__(self, root: str):
        self.root = root

    def _p(self, key):
        return os.path.join(self.root, key)

    def read(self, key):
        try:
            with open(self._p(key), "rb") as f:
                return f.read(), 1
        except FileNotFoundError:
            return None, 0

    def write(self, key, data: bytes, generation: int) -> bool:
        p = self._p(key)
        exists = os.path.exists(p)
        if (generation == 0 and exists) or (generation != 0 and not exists):
            return False
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        return True


class GCSStore:
    """Cloud Storage with generation preconditions (no lost updates, no clobbering)."""

    def __init__(self, bucket: str):
        from google.cloud import storage  # imported lazily so tests need no GCP libs
        self.bucket = storage.Client().bucket(bucket)
        from google.api_core.exceptions import PreconditionFailed
        self._pf = PreconditionFailed

    def read(self, key):
        b = self.bucket.get_blob(key)
        if b is None:
            return None, 0
        return b.download_as_bytes(if_generation_match=b.generation), b.generation

    def write(self, key, data: bytes, generation: int) -> bool:
        try:
            self.bucket.blob(key).upload_from_string(
                data, content_type="application/json", if_generation_match=generation)
            return True
        except self._pf:
            return False


# ---------- archive logic ----------

def put_once(store, key: str, data: bytes) -> bool:
    """Create-only write. True if written, False if it already existed."""
    return store.write(key, data, generation=0)


def merge_day(store, key: str, dam: str, date: str, updater: Callable[[dict], bool], tries=5):
    for _ in range(tries):
        raw, gen = store.read(key)
        doc = json.loads(raw) if raw else {"schemaVersion": SCHEMA_VERSION, "dam": dam, "localDate": date,
                                           "source": BASE, "observed": {}, "revisions": [], "predicted": {}}
        if not updater(doc):
            return False  # nothing new
        data = json.dumps(doc, indent=1, sort_keys=True).encode()
        if store.write(key, data, gen):
            return True
    raise RuntimeError(f"could not update {key}: concurrent writers")


def archive_dam(store, prefix: str, dam: str, fetch: Callable[[str], bytes], now: dt.datetime) -> dict:
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H") + "Z"
    fetched_at = now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    summary = {"dam": dam, "newObservedHours": 0, "revisions": 0, "predictedStored": False}

    obs_bytes = fetch(f"{BASE}/observed-data/{dam}.json")
    pred_bytes = fetch(f"{BASE}/predicted-data/{dam}.json")
    obs = parse_observed(json.loads(obs_bytes))          # raises SchemaError before anything is written
    pred = parse_predicted(json.loads(pred_bytes))

    put_once(store, f"{prefix}/raw/{dam}/observed/{stamp}.json", obs_bytes)
    put_once(store, f"{prefix}/raw/{dam}/predicted/{stamp}.json", pred_bytes)

    by_date: dict = {}
    for iso, parsed, raw in obs:
        by_date.setdefault(iso[:10], []).append((iso, parsed, raw))
    for date, items in by_date.items():
        def upd(doc, items=items):
            changed = False
            for iso, parsed, raw in items:
                cur = doc["observed"].get(iso)
                if cur is None:
                    doc["observed"][iso] = {"raw": raw, "parsed": parsed, "firstSeenAt": fetched_at}
                    summary["newObservedHours"] += 1
                    changed = True
                elif cur["raw"] != raw and not any(r["hour"] == iso and r["raw"] == raw for r in doc["revisions"]):
                    doc["revisions"].append({"hour": iso, "raw": raw, "parsed": parsed, "seenAt": fetched_at})
                    summary["revisions"] += 1
                    changed = True
            return changed
        merge_day(store, f"{prefix}/{dam}/{date}.json", dam, date, upd)

    fetch_date = now.astimezone(dt.timezone(dt.timedelta(hours=-6))).strftime("%Y-%m-%d")

    def upd_pred(doc):
        if stamp in doc["predicted"]:
            return False
        doc["predicted"][stamp] = {"fetchedAt": fetched_at, "rows": pred}
        summary["predictedStored"] = True
        return True
    merge_day(store, f"{prefix}/{dam}/{fetch_date}.json", dam, fetch_date, upd_pred)
    return summary


def http_fetch(url: str, tries=3) -> bytes:
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
            if r.status_code == 200:
                return r.content
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"fetch failed {url}: {last}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default=os.environ.get("WT_ARCHIVE_BUCKET"))
    ap.add_argument("--prefix", default=os.environ.get("WT_ARCHIVE_PREFIX", "water-temp/tva"))
    ap.add_argument("--local-dir", help="write to a local folder instead of Cloud Storage")
    ap.add_argument("--dams", default=",".join(DAMS))
    a = ap.parse_args(argv)
    if not a.local_dir and not a.bucket:
        ap.error("--bucket (or WT_ARCHIVE_BUCKET) or --local-dir is required")
    store = LocalStore(a.local_dir) if a.local_dir else GCSStore(a.bucket)
    now = dt.datetime.now(dt.timezone.utc)
    failed = []
    for dam in a.dams.split(","):
        try:
            print(json.dumps(archive_dam(store, a.prefix, dam, http_fetch, now)))
        except Exception as e:  # keep going for other dams, but fail the run loudly
            failed.append(dam)
            print(json.dumps({"dam": dam, "error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
