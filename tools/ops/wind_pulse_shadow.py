#!/usr/bin/env python3
"""Wind's 7-day shadow on Pulse (Sector_Ops #49; decision D4, Sector_Ops #51 comment 6889677881). READ-ONLY runner for the pre-registered protocol
docs/architecture/production/WIND_PULSE_SHADOW_PROTOCOL_V1.md (protocol id wind-pulse-shadow-v1).

On Pulse there is no legacy Wind write to compare with, so the shadow checks what CAN be checked, exactly as pre-registered in the cutover plan (#176):
  C1 completeness   >= 95% of the window's hours have a Wind artifact sealed within 20 min of the hour; every miss has a written explanation
  C2 determinism    at least one re-seal per UTC day of the window, and every re-seal's write set equals the original's (normalized hash)
  C3 skill          pooled MAE of the sealed analysis wind at the 4 live lakes vs METAR <= 1.10 x the recorded validation MAE (>= 200 pairs)
  C4 bounds         every write is a path Wind owns (the Publisher's ownership table) and every lake key is on the staged W-H3 list
  C5 Mac mini       no sleep in the window (`pmset -g log`), and the archive holds no raw cutout the retention rule should have pruned

  python tools/ops/wind_pulse_shadow.py reseal --store local:DIR --artifact FILE --out FILE --read-rtdb        # C2: one re-seal record
  python tools/ops/wind_pulse_shadow.py report --artifacts DIR --store local:DIR --start YYYY-MM-DDTHH:00:00Z --reseals DIR
                                               [--explanations FILE] [--pmset-log FILE] [--days 7]               # the verdict (JSON)

Nothing here writes a database, a bucket, the Wind archive or a policy. `reseal` runs Wind's UNCHANGED build through a DryRunWriter over a
copy-on-write view of the archive (every write stays in memory) and writes ONE local record file, create-only. It reads the previous state GET-only
(--read-rtdb, required), exactly as the shadow run did: a seal that took its previous state from the local bookkeeping advanced that file, so it can
never be re-sealed reproducibly. `report` only reads. Exit codes: report 0 PASS, 1 FAIL, 3 INCOMPLETE, 2 refused; reseal 0 equal,
1 different, 2 refused (nothing written).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
WIND_RUNTIME = os.path.join(ROOT, "brains", "wind", "runtime")
for p in (WIND_RUNTIME, os.path.join(ROOT, "jobs", "brain_platform")):
    if p not in sys.path:
        sys.path.insert(0, p)

PROTOCOL_ID = "wind-pulse-shadow-v1"
PROTOCOL_DOC = os.path.join(ROOT, "docs", "architecture", "production", "WIND_PULSE_SHADOW_PROTOCOL_V1.md")
STAGE = os.path.join(HERE, "hybrid-stage", "wind.json")
EVIDENCE = os.path.join(WIND_RUNTIME, "sector_wind", "brain", "validation_evidence.json")
# Pre-registered thresholds (the protocol doc states the same numbers; test_pulse_shadow pins them together).
THRESHOLDS = {"days": 7, "completenessMin": 0.95, "sealWithinMinutes": 20, "skillMaeRatioMax": 1.10, "skillMinPairs": 200, "retentionKeepDays": 30}
VOLATILE_KEYS = frozenset({"durationMs"})        # wall-clock run time: the only field excluded from the C2 write-set hash
RESEAL_SCHEMA = "wind-pulse-reseal-v1"
MPH_PER_MS = 2.2369362920544
PMSET_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4})\s+(Sleep)\b")


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def protocol_sha256() -> str | None:
    return hashlib.sha256(open(PROTOCOL_DOC, "rb").read()).hexdigest() if os.path.exists(PROTOCOL_DOC) else None


# ── artifacts and write sets ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def is_wind_artifact(doc) -> bool:
    return (isinstance(doc, dict) and doc.get("envelope") == "publish-artifact-v2" and isinstance(doc.get("sections"), list)
            and (doc.get("lineage") or {}).get("brainId") == "wind")


def load_artifacts(root: str) -> list[dict]:
    """Every sealed Wind artifact under `root` (recursively), once per artifactId, oldest first."""
    seen = {}
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if not f.endswith(".json"):
                continue
            try:
                doc = _load(os.path.join(dp, f))
            except (OSError, ValueError):
                continue
            if is_wind_artifact(doc):
                seen.setdefault(doc["lineage"].get("artifactId") or hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest(), doc)
    return sorted(seen.values(), key=lambda a: a["lineage"]["generatedAt"])


def mutations(artifact: dict) -> list[dict]:
    return [m for s in artifact["sections"] for m in s["mutations"]]


def _strip(v):
    if isinstance(v, dict):
        return {k: _strip(x) for k, x in v.items() if k not in VOLATILE_KEYS}
    if isinstance(v, list):
        return [_strip(x) for x in v]
    return v


def writeset_sha256(artifact: dict) -> str:
    """sha256 over the sorted (op, path, value) mutations with only the wall-clock `durationMs` removed. Lineage (executionId, generatedAt) is not
    part of the write set."""
    rows = sorted((m["op"], m["path"], json.dumps(_strip(m.get("value")), sort_keys=True, separators=(",", ":"))) for m in mutations(artifact))
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def _diff_paths(a: dict, b: dict, limit: int = 20) -> list[str]:
    ma = {m["path"]: (m["op"], json.dumps(_strip(m.get("value")), sort_keys=True)) for m in mutations(a)}
    mb = {m["path"]: (m["op"], json.dumps(_strip(m.get("value")), sort_keys=True)) for m in mutations(b)}
    return sorted(p for p in set(ma) | set(mb) if ma.get(p) != mb.get(p))[:limit]


# ── C2: the re-seal ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

class CopyOnWriteStore:
    """Reads fall through to the archive; every write stays in memory. The archive on disk is never changed."""

    def __init__(self, inner):
        self._inner, self._w = inner, {}
        self.root = inner.root                       # publish() reads ledger files by path (read only)

    def get_json(self, key):
        return json.loads(json.dumps(self._w[key])) if key in self._w else self._inner.get_json(key)

    def put_json(self, key, obj):
        self._w[key] = json.loads(json.dumps(obj))
        return 0

    def exists(self, key):
        return key in self._w or self._inner.exists(key)

    def list(self, prefix):
        return sorted(set(self._inner.list(prefix)) | {k for k in self._w if k.startswith(prefix)})

    def append_ledger(self, entry):
        pass

    def flush_ledger(self):
        pass

    def read_ledger(self):
        return self._inner.read_ledger()


def newer_runs(store, t: dt.datetime) -> list[str]:
    """Ingest run records written after `t` (the re-seal must happen before the next run, or the archive no longer holds the original inputs)."""
    out = []
    for d in (t, t + dt.timedelta(days=1)):
        for k in store.list(f"runs/{d:%Y%m%d}/"):
            stem = k.rsplit("/", 1)[-1].split(".")[0]
            try:
                if dt.datetime.strptime(f"{d:%Y%m%d}{stem}", "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc) > t:
                    out.append(k)
            except ValueError:
                continue
    return sorted(out)


def reseal(store_spec: str, artifact: dict, *, read_rtdb: bool = True, reader=None, directory=None) -> dict:
    """Re-run Wind's build for the artifact's hour over a copy-on-write view of the archive and compare write sets. Returns the record. The previous
    state is read live (GET only; `reader` stands in for the database in tests)."""
    if not read_rtdb:
        raise ValueError("a re-seal reads the previous state live (--read-rtdb), as the shadow run must: the local bookkeeping is not reproducible")
    import artifact_entry as E
    from sector_wind.ingest import load_config, verified_release
    from sector_wind.store import LocalStore
    lin = artifact["lineage"]
    t = _parse(lin["generatedAt"])
    disk = LocalStore(store_spec.removeprefix("local:"))
    later = newer_runs(disk, t)
    if later:
        raise ValueError(f"the archive already holds {len(later)} later run(s) (first {later[0]}): re-seal before the next run (protocol C2)")
    store = CopyOnWriteStore(disk)
    from sector_wind.brain.live_previous import live_previous
    if reader is None:
        from sector_brain_platform import BRAIN_RTDB_URL, BrainRtdb, TokenProvider
        reader = BrainRtdb(BRAIN_RTDB_URL, TokenProvider())
    previous = live_previous(reader)
    summary = disk.get_json(f"runs/{t:%Y%m%d}/{t:%H%M%S}.json")        # the same ingest summary the original run passed to publish()
    rep, built = E.build(store, load_config(), now=t, run_summary=summary, execution_id=lin["executionId"], code_version=lin["codeVersion"],
                         release=verified_release(), directory=directory, previous=previous)
    if not rep.get("ok") or not built.artifact:
        return {"schema": RESEAL_SCHEMA, "protocol": PROTOCOL_ID, "artifactId": lin.get("artifactId"), "generatedAt": lin["generatedAt"],
                "equal": False, "error": f"re-seal failed: {(rep.get('errors') or ['no artifact'])[:3]}"}
    a, b = writeset_sha256(artifact), writeset_sha256(built.artifact)
    return {"schema": RESEAL_SCHEMA, "protocol": PROTOCOL_ID, "artifactId": lin.get("artifactId"), "generatedAt": lin["generatedAt"],
            "originalWritesetSha256": a, "resealWritesetSha256": b, "equal": a == b,
            "originalOutputFingerprint": lin.get("outputFingerprint"), "resealOutputFingerprint": built.artifact["lineage"].get("outputFingerprint"),
            "differingPaths": [] if a == b else _diff_paths(artifact, built.artifact), "readRtdb": read_rtdb,
            "resealedAt": _iso(dt.datetime.now(dt.timezone.utc).replace(microsecond=0))}


# ── the criteria ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _status(ok: bool | None) -> str:
    return "PASS" if ok is True else ("FAIL" if ok is False else "NOT_EVALUATED")


def c1_completeness(arts: list[dict], start: dt.datetime, days: int, explanations: dict) -> dict:
    hours = [start + dt.timedelta(hours=h) for h in range(24 * days)]
    on_time = set()
    for a in arts:
        g = _parse(a["lineage"]["generatedAt"])
        slot = g.replace(minute=0, second=0)
        if (g - slot) <= dt.timedelta(minutes=THRESHOLDS["sealWithinMinutes"]):
            on_time.add(slot)
    missed = [_iso(h) for h in hours if h not in on_time]
    unexplained = [h for h in missed if not str(explanations.get(h) or "").strip()]
    share = (len(hours) - len(missed)) / len(hours)
    ok = share >= THRESHOLDS["completenessMin"] and not unexplained
    return {"status": _status(ok), "hours": len(hours), "sealedOnTime": len(hours) - len(missed), "share": round(share, 4),
            "missed": missed, "unexplained": unexplained}


def c2_determinism(records: list[dict], start: dt.datetime, days: int) -> dict:
    window = {(start + dt.timedelta(hours=h)).date().isoformat() for h in range(24 * days)}     # every UTC date the window touches
    mine = [r for r in records if r.get("schema") == RESEAL_SCHEMA and r.get("generatedAt") and
            start <= _parse(r["generatedAt"]) < start + dt.timedelta(days=days)]
    by_day = {}
    for r in mine:
        by_day.setdefault(r["generatedAt"][:10], []).append(r)
    missing = sorted(window - set(by_day))
    unequal = [r.get("artifactId") or r["generatedAt"] for r in mine if r.get("equal") is not True]
    return {"status": _status(not missing and not unequal), "records": len(mine), "daysCovered": len(set(by_day) & window),
            "daysMissing": missing, "unequal": unequal}


def c3_skill(arts: list[dict], store, cfg: dict, evidence: dict) -> dict:
    from sector_wind.brain.lakes import WIND_LAKE_IDS
    from sector_wind.validate import load_obs
    if not arts:
        return {"status": "NOT_EVALUATED", "why": "no artifacts"}
    lake_of = {lid: wl for wl, lid in WIND_LAKE_IDS.items()}
    first, last = _parse(arts[0]["lineage"]["generatedAt"]), _parse(arts[-1]["lineage"]["generatedAt"])
    obs = load_obs(store, first - dt.timedelta(days=1), last + dt.timedelta(days=1))
    pairs, per_lake = {}, {}
    for a in arts:
        for m in mutations(a):
            st = m.get("value")
            if m["op"] != "SET" or not m["path"].endswith("/states/wind") or not isinstance(st, dict) or st.get("kind") != "analysis":
                continue
            lid, at = st.get("lakeId"), (st.get("analysis") or {}).get("analysisTime")
            if lid not in lake_of or not at or st.get("sustainedMph") is None:
                continue
            t = _parse(at) if at.endswith("Z") and len(at) == 20 else None
            if t is None or t.minute != 0:
                continue                                                           # METAR truth is taken at the top of the hour
            for sid, s in cfg["stations"].items():
                o = obs.get((sid, t)) if s.get("lake") == lake_of[lid] else None
                if o and o.get("speedMS") is not None:
                    pairs[(lid, at, sid)] = (float(st["sustainedMph"]), float(o["speedMS"]) * MPH_PER_MS)
    for (lid, _, _), (f, o) in pairs.items():
        per_lake.setdefault(lid, []).append(abs(f - o))
    errs = [abs(f - o) for f, o in pairs.values()]
    bar = round(evidence["metrics"]["speedMaeMph"] * THRESHOLDS["skillMaeRatioMax"], 3)
    if len(errs) < THRESHOLDS["skillMinPairs"]:
        return {"status": "NOT_EVALUATED", "pairs": len(errs), "why": f"fewer than {THRESHOLDS['skillMinPairs']} pairs", "barMph": bar}
    mae = sum(errs) / len(errs)
    return {"status": _status(mae <= bar), "pairs": len(errs), "maeMph": round(mae, 3), "barMph": bar,
            "evidenceMaeMph": evidence["metrics"]["speedMaeMph"],
            "perLake": {lid: {"pairs": len(v), "maeMph": round(sum(v) / len(v), 3)} for lid, v in sorted(per_lake.items())}}


def c4_bounds(arts: list[dict], lakes: list[str]) -> dict:
    from sector_brain_platform.cycle_watchdog import LAKE_PATH
    from sector_brain_platform.ownership import path_allowed
    allowed, not_owned, outside = set(lakes), set(), set()
    for a in arts:
        for m in mutations(a):
            if not path_allowed("wind", m["path"].lstrip("/")):
                not_owned.add(m["path"])
            k = LAKE_PATH.match(m["path"])
            if k and k.group(1) not in allowed:
                outside.add(k.group(1))
    return {"status": _status(bool(arts) and not not_owned and not outside) if arts else "NOT_EVALUATED", "artifacts": len(arts),
            "notOwned": sorted(not_owned)[:20], "lakesOutsideList": sorted(outside)[:20], "listSize": len(allowed)}


def c5_mac_mini(pmset_log: str | None, store_keys: list[str], start: dt.datetime, days: int) -> dict:
    from sector_wind.retention import plan
    end = start + dt.timedelta(days=days)
    sleeps = None
    if pmset_log is not None:
        sleeps = []
        for line in pmset_log.splitlines():
            m = PMSET_LINE.match(line.strip())
            if m:
                t = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S %z").astimezone(dt.timezone.utc)
                if start <= t < end:
                    sleeps.append(_iso(t))
    overdue = plan(store_keys, end, THRESHOLDS["retentionKeepDays"])
    sleep_ok = None if sleeps is None else not sleeps
    ok = None if sleep_ok is None else (sleep_ok and not overdue)
    if sleep_ok is None and overdue:
        ok = False
    return {"status": _status(ok), "sleepEvents": sleeps, "retentionOverdue": len(overdue), "retentionOverdueSample": overdue[:5],
            **({"why": "no pmset log given"} if sleeps is None else {})}


def report(arts, records, store, cfg, evidence, lakes, start, days, explanations, pmset_log, store_keys) -> dict:
    crit = {"C1": c1_completeness(arts, start, days, explanations), "C2": c2_determinism(records, start, days),
            "C3": c3_skill([a for a in arts if start <= _parse(a["lineage"]["generatedAt"]) < start + dt.timedelta(days=days)], store, cfg, evidence),
            "C4": c4_bounds(arts, lakes), "C5": c5_mac_mini(pmset_log, store_keys, start, days)}
    st = [c["status"] for c in crit.values()]
    verdict = "FAIL" if "FAIL" in st else ("PASS" if all(s == "PASS" for s in st) else "INCOMPLETE")
    return {"protocol": PROTOCOL_ID, "protocolSha256": protocol_sha256(), "thresholds": THRESHOLDS, "window": {"start": _iso(start), "days": days},
            "verdict": verdict, "criteria": crit}


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reseal")
    r.add_argument("--store", required=True)
    r.add_argument("--artifact", required=True)
    r.add_argument("--out", required=True, help="a NEW local file for the record (never overwritten)")
    r.add_argument("--read-rtdb", action="store_true", help="REQUIRED: read the previous state GET-only, as the shadow run did (BRAIN_ACCESS_TOKEN)")
    p = sub.add_parser("report")
    p.add_argument("--artifacts", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--start", required=True, help="the window's first hour, YYYY-MM-DDTHH:00:00Z")
    p.add_argument("--reseals", required=True, help="the folder of re-seal records")
    p.add_argument("--days", type=int, default=THRESHOLDS["days"])
    p.add_argument("--explanations", default=None, help='JSON {"YYYY-MM-DDTHH:00:00Z": "why this hour has no on-time seal"}')
    p.add_argument("--pmset-log", default=None, help="the Mac mini's `pmset -g log` output saved to a file")
    a = ap.parse_args(argv)
    if not a.store.startswith("local:"):
        print("REFUSED: --store must be local:DIR (the runner's own archive)", file=sys.stderr)
        return 2
    if a.cmd == "reseal":
        if os.path.exists(a.out) or a.out.startswith("gs://"):
            print("REFUSED: --out is a new local file", file=sys.stderr)
            return 2
        try:
            art = _load(a.artifact)
            if not is_wind_artifact(art):
                raise ValueError("not a sealed Wind artifact")
            rec = reseal(a.store, art, read_rtdb=a.read_rtdb)
        except (OSError, ValueError, KeyError) as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 2
        with open(a.out, "x", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, sort_keys=True)
        print(json.dumps({k: rec.get(k) for k in ("generatedAt", "equal", "differingPaths", "error")}, sort_keys=True))
        return 0 if rec.get("equal") else 1
    try:
        start = _parse(a.start)
        if start.minute or start.second:
            raise ValueError("--start must be the top of an hour")
    except ValueError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    from sector_wind.ingest import load_config
    from sector_wind.store import LocalStore
    store = LocalStore(a.store.removeprefix("local:"))
    records = []
    for dp, _, fs in os.walk(a.reseals):
        for f in fs:
            if f.endswith(".json"):
                try:
                    records.append(_load(os.path.join(dp, f)))
                except (OSError, ValueError):
                    continue
    out = report(load_artifacts(a.artifacts), records, store, load_config(), _load(EVIDENCE), _load(STAGE)["watchdog"]["lakes"], start, a.days,
                 _load(a.explanations) if a.explanations else {}, open(a.pmset_log).read() if a.pmset_log else None,
                 [k for pre in ("nbm/", "rtma/", "nbm-points/") for k in store.list(pre)])
    print(json.dumps(out, indent=1, sort_keys=True))
    return {"PASS": 0, "FAIL": 1}.get(out["verdict"], 3)


if __name__ == "__main__":
    sys.exit(main())
