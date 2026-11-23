#!/usr/bin/env python3
"""Wind archive continuity (decision D5, Sector_Ops #51 comment 6889677881): is the runner's LOCAL Wind archive a faithful continuation of the
cloud candidate archive (gs://sector-wind-candidate/wind/v1)? READ-ONLY: it reads the local folder and a saved object listing of the bucket; it
never writes either, and makes no network call itself.

  gcloud storage objects list "gs://sector-wind-candidate/wind/v1/**" --format=json > remote.json          # the listing (owner's read access)
  gcloud storage cat gs://sector-wind-candidate/wind/v1/brain/wind/last_publish.json > remote_last.json      # optional, for the dates
  python tools/ops/wind_archive_continuity.py --local DIR --remote-listing remote.json [--remote-last-publish remote_last.json]

What it checks
  REQUIRED for continuity (Wind cannot profile or interpolate without them): fetch/national/MANIFEST.json, every fetch/national/* table,
    every fetch/dev/* table and every grids/* file in the bucket must be present locally with the SAME MD5.
  W-H2 profile digests: for each national manifest entry Wind profiles (PASS/FLAGGED with a table), the local table's own tableSha256 must equal
    the manifest's. Read-live change detection (D2) compares the live profile's geometry.tableSha256 with the manifest's; a mismatch would re-send
    that profile every hour.
  W-H3: the nationally profiled lakes (D3) are all on the staged watchdog list.
  INFO (never a failure): Wind's previous-state bookkeeping brain/wind/last_publish.json (a cache only under D2), profile_cache/, and the date
    range of each raw series (nbm/, rtma/, nbm-points/, metar/, runs/) in the bucket and locally.

Verdict: CONTINUOUS (exit 0), DIVERGED (a required object differs, or a profile digest mismatches; exit 1), SEED_NEEDED (a required object is
missing locally; exit 3), UNVERIFIED (otherwise fine, but a required bucket object has no MD5, e.g. a composite upload, so equality is not proven;
exit 4). Exit 2: refused (bad input).
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
WIND_RUNTIME = os.path.join(ROOT, "brains", "wind", "runtime")
for p in (WIND_RUNTIME, os.path.join(ROOT, "jobs", "brain_platform"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

REMOTE = "gs://sector-wind-candidate/wind/v1"
BOOKKEEPING = "brain/wind/last_publish.json"
MANIFEST = "fetch/national/MANIFEST.json"
REQUIRED_PREFIXES = ("fetch/national/", "fetch/dev/", "grids/")
SERIES_DATE = (
    ("nbm/", re.compile(r"/(\d{10})\.json\.gz$"), 10),
    ("rtma/", re.compile(r"/(\d{8})/(\d{4})\.json\.gz$"), 8),
    ("nbm-points/", re.compile(r"/(\d{10})\.json\.gz$"), 10),
    ("metar/", re.compile(r"(\d{8})\.json\.gz$"), 8),
    ("runs/", re.compile(r"^runs/(\d{8})/"), 8),
)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def md5_b64(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def parse_listing(doc, prefix: str = "wind/v1/") -> dict[str, dict]:
    """{key relative to the archive root: {md5, size}} from `gcloud storage objects list --format=json` (snake or camel case field names)."""
    rows = doc if isinstance(doc, list) else (doc.get("items") or [])
    out = {}
    for r in rows:
        name = r.get("name") or (r.get("storage_url") or r.get("url") or "").split("/", 3)[-1]
        if not name or name.endswith("/"):
            continue
        if not name.startswith(prefix):
            continue
        out[name[len(prefix):]] = {"md5": r.get("md5_hash") or r.get("md5Hash"), "size": int(r.get("size") or 0)}
    return out


def local_keys(root: str) -> list[str]:
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if not f.endswith(".tmp"):
                out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    return sorted(out)


def _read_json(path: str):
    raw = open(path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def series_range(keys) -> dict:
    out = {}
    for pre, rx, n in SERIES_DATE:
        stamps = sorted(m.group(1) + (m.group(2) if m.lastindex and m.lastindex > 1 else "") for k in keys if k.startswith(pre)
                        for m in [rx.search(k)] if m)
        if stamps:
            out[pre.rstrip("/")] = {"count": len(stamps), "oldest": stamps[0], "newest": stamps[-1]}
    return out


def profile_digests(local_root: str, manifest: dict | None) -> dict:
    """Each profiled manifest entry's tableSha256 vs the local table's own tableSha256."""
    if not manifest:
        return {"status": "NOT_EVALUATED", "why": "no local manifest"}
    checked, mismatched, missing = 0, [], []
    for m in manifest.get("lakes", []):
        if m.get("status") not in ("PASS", "FLAGGED") or not m.get("tableSha256"):
            continue
        p = os.path.join(local_root, "fetch", "national", f"{m['slug']}.windfetch.json.gz")
        lid = f"{m['name']}|{m['state']}"
        if not os.path.exists(p):
            missing.append(lid)
            continue
        checked += 1
        if _read_json(p).get("tableSha256") != m["tableSha256"]:
            mismatched.append(lid)
    return {"status": "PASS" if not mismatched and not missing else "FAIL", "checked": checked, "mismatched": mismatched[:20],
            "missing": missing[:20], "mismatchedCount": len(mismatched), "missingCount": len(missing)}


def watchdog_scope(manifest: dict | None) -> dict:
    import wind_watchdog_lakes as WL
    if not manifest:
        return {"status": "NOT_EVALUATED", "why": "no local manifest"}
    directory = WL.load_directory(WL.GOLDEN)
    d3 = WL.d3_lakes(manifest, directory)
    pinned = set(_load(WL.STAGE)["watchdog"]["lakes"])
    off = sorted(set(d3) - pinned)
    return {"status": "PASS" if not off else "FAIL", "d3Lakes": len(d3), "notOnPinnedList": off[:20]}


def compare(local_root: str, remote: dict[str, dict], remote_last_publish: dict | None = None) -> dict:
    lkeys = local_keys(local_root)
    lset = set(lkeys)
    required = sorted(k for k in remote if k.startswith(REQUIRED_PREFIXES))
    missing = [k for k in required if k not in lset]
    unverified = [k for k in required if k in lset and not remote[k]["md5"]]      # composite objects carry no MD5: present, but not proven equal
    differ = [k for k in required if k in lset and remote[k]["md5"] and md5_b64(os.path.join(local_root, k)) != remote[k]["md5"]]
    local_only_required = sorted(k for k in lkeys if k.startswith(REQUIRED_PREFIXES) and k not in remote)
    manifest = _read_json(os.path.join(local_root, MANIFEST)) if MANIFEST in lset else None
    book_local = _read_json(os.path.join(local_root, BOOKKEEPING)) if BOOKKEEPING in lset else None
    book = {"remote": BOOKKEEPING in remote, "local": book_local is not None,
            "sameBytes": (BOOKKEEPING in remote and book_local is not None and md5_b64(os.path.join(local_root, BOOKKEEPING)) == remote[BOOKKEEPING]["md5"]),
            "localAt": (book_local or {}).get("at"), "remoteAt": (remote_last_publish or {}).get("at"),
            "localProfileShas": len((book_local or {}).get("profileShas") or {}),
            "note": "a cache only: under W-H2 (D2) a hand-off reads its previous state from the live database"}
    digests = profile_digests(local_root, manifest)
    scope = watchdog_scope(manifest)
    verdict = ("SEED_NEEDED" if missing else "DIVERGED" if differ or digests["status"] == "FAIL" or scope["status"] == "FAIL"
               else "UNVERIFIED" if unverified else "CONTINUOUS")
    return {"verdict": verdict, "remote": REMOTE,
            "required": {"remoteObjects": len(required), "missingLocally": len(missing), "differ": len(differ), "unverifiedNoMd5": len(unverified),
                         "unverifiedSample": unverified[:10], "localOnly": len(local_only_required),
                         "missingSample": missing[:10], "differSample": differ[:10], "localOnlySample": local_only_required[:10]},
            "profileDigests": digests, "watchdogScope": scope, "bookkeeping": book,
            "profileCache": {"remote": sum(k.startswith("brain/wind/profile_cache/") for k in remote),
                             "local": sum(k.startswith("brain/wind/profile_cache/") for k in lkeys)},
            "series": {"remote": series_range(remote), "local": series_range(lkeys)}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", required=True, help="the runner's local Wind archive folder")
    ap.add_argument("--remote-listing", required=True, help="`gcloud storage objects list ... --format=json` output for the candidate archive")
    ap.add_argument("--remote-prefix", default="wind/v1/")
    ap.add_argument("--remote-last-publish", default=None, help="optional: the bucket's brain/wind/last_publish.json, saved locally")
    a = ap.parse_args(argv)
    if a.local.startswith("gs://") or not os.path.isdir(a.local):
        print("REFUSED: --local is an existing local folder", file=sys.stderr)
        return 2
    try:
        remote = parse_listing(_load(a.remote_listing), a.remote_prefix)
        if not remote:
            raise ValueError(f"the listing has no objects under {a.remote_prefix}")
        out = compare(a.local, remote, _load(a.remote_last_publish) if a.remote_last_publish else None)
    except (OSError, ValueError, KeyError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, sort_keys=True))
    return {"CONTINUOUS": 0, "DIVERGED": 1, "SEED_NEEDED": 3, "UNVERIFIED": 4}[out["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
