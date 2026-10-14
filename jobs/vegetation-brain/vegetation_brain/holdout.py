"""Sealed ONE-SHOT holdout guard (pre-registration A4/A5: the TEST set is consumed; v0.3 gets exactly one fresh-truth evaluation).

`run_once` refuses (1) any truth set already consumed by an earlier evaluation, (2) any truth set that already has a seal, and writes a seal
(truth id + sha256, observer/contract fingerprint, parameters, timestamp) BEFORE it calls the evaluator, so a crash cannot be retried quietly with
different parameters. It does not score anything itself: the evaluator is supplied by the (future) validation run and must return the gate results."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
# Truth sets that earlier evaluations (notes 04-12) already used. Reusing them is NOT a fresh holdout.
CONSUMED_TRUTH = frozenset({
    "snohomish-wa-2021-2023", "fwc-ltm-point-intercepts-2015-2023", "fwc-ltm-lake-pac-pvi-2015-2023", "epa-nla-2017", "epa-nla-2018-2019-secondary",
    "umn-mn-plants-1999-2018", "sfwmd-okeechobee-littoral-2015-2016", "sfwmd-kissimmee-littoral-2016", "umrs-pool5-2015", "carver-county-biovolume",
})
OBSERVER_FILES = ("observer.py", "shared.py", "contract.py", "validation.py")


class HoldoutError(RuntimeError):
    pass


def observer_fingerprint() -> str:
    h = hashlib.sha256()
    for f in OBSERVER_FILES:
        h.update(f.encode())
        h.update(open(os.path.join(HERE, f), "rb").read())
    return h.hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_once(truth_id: str, truth_sha256: str, seal_dir: str, evaluator, params: dict, *, now: datetime | None = None) -> dict:
    if truth_id in CONSUMED_TRUTH:
        raise HoldoutError(f"truth set {truth_id!r} was already used by an earlier evaluation: it is not a fresh holdout")
    seal = os.path.join(seal_dir, f"{truth_id}.seal.json")
    if os.path.exists(seal):
        raise HoldoutError(f"a seal already exists for {truth_id!r}: the single holdout evaluation was already started")
    os.makedirs(seal_dir, exist_ok=True)
    rec = {"truthId": truth_id, "truthSha256": truth_sha256, "observerFingerprint": observer_fingerprint(), "params": params,
           "sealedAt": (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(), "status": "STARTED"}
    with open(seal, "x") as f:                       # exclusive create: a second process cannot also start
        json.dump(rec, f, indent=1, sort_keys=True)
    result = evaluator(params)
    rec.update({"status": "COMPLETED", "result": result})
    with open(seal, "w") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
    return rec
