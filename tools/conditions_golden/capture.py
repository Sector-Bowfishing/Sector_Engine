#!/usr/bin/env python3
"""Golden /conditions responses and the phone-contract check (Sector_Ops #53, Step 0).

Two jobs, standard library only:

  capture   Call GET /conditions for every point in points-v1.json, keep the raw bodies in a PRIVATE folder
            (--raw-dir, outside this public repo), and write REDACTED copies to the fixture folder.
            Redaction replaces free text (reasons, prose, alert text, the spawn species name) with "<redacted>",
            keeping the type, so no per-lake species presence lands in the public repo. Numbers, enums,
            units, dates and key structure are kept: they are what the contract is about.

  check     Validate JSON files (or a live call per point with --live) against
            contracts/phone/conditions-phone-contract-v1.json. Exit 1 on any violation.

Examples:
  python3 tools/conditions_golden/capture.py capture --raw-dir "<Sector Research>/shared/conditions-golden/2026-11-06"
  python3 tools/conditions_golden/capture.py check verification/fixtures/phone-contract/2026-11-06/*.json
  python3 tools/conditions_golden/capture.py check --live
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/phone/conditions-phone-contract-v1.json"
POINTS = ROOT / "verification/fixtures/phone-contract/points-v1.json"
FIXTURES = ROOT / "verification/fixtures/phone-contract"
DEFAULT_BASE = "https://sector-engine-e43utajroa-uc.a.run.app"
USER_AGENT = "sector-engine-golden-capture/1"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")

# Free-text paths (contract path syntax). Everything else is kept as served.
REDACT = {
    "topReasons[]", "closingLine", "spawnSpeciesName",
    "dormantFactors[].label", "dormantFactors[].reason",
    "factors[].label", "factors[].why", "gates[].reason",
    "whereToLook[].title", "whereToLook[].body",
    "weather.conditionDescription",
    "alerts[].headline", "alerts[].details", "alerts[].event", "alerts[].id",
    "tonight.headline",
    "nights[].topReasons[]", "nights[].factors[].detail",
    "clarityGauges[].siteName",
}


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text())["fields"]


def _is_type(v, t: str) -> bool:
    if t == "int":
        return isinstance(v, int) and not isinstance(v, bool) or (isinstance(v, float) and v.is_integer())
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "string":
        return isinstance(v, str)
    if t == "bool":
        return isinstance(v, bool)
    if t == "date":
        return isinstance(v, str) and bool(DATE_RE.match(v))
    if t == "array":
        return isinstance(v, list)
    if t == "object":
        return isinstance(v, dict)
    raise ValueError(f"unknown contract type {t}")


def _children(fields: dict, parent: str) -> list[str]:
    """Direct child keys of `parent` ('' = root): 'a', 'a.b', 'a[]', 'a[].b'."""
    out = []
    for p in fields:
        if parent == "":
            if "." not in p and not p.endswith("[]") and "[]." not in p:
                out.append(p)
        elif p.startswith(parent + ".") and "." not in p[len(parent) + 1:].replace("[]", "\0"):
            rest = p[len(parent) + 1:]
            if "[]" not in rest:
                out.append(p)
    return out


def validate(doc, fields: dict) -> list[str]:
    errors: list[str] = []

    def walk_obj(obj: dict, parent: str, where: str):
        for p in _children(fields, parent):
            key = p.split(".")[-1]
            spec = fields[p]
            v = obj.get(key)
            here = f"{where}.{key}" if where else key
            if v is None:
                if spec["required"]:
                    errors.append(f"{here}: required key missing or null")
                continue
            check_value(v, p, here)

    def check_value(v, p: str, here: str):
        spec = fields[p]
        if not _is_type(v, spec["type"]):
            errors.append(f"{here}: expected {spec['type']}, got {type(v).__name__} {json.dumps(v)[:60]}")
            return
        if spec["type"] == "object":
            walk_obj(v, p, here)
        elif spec["type"] == "array":
            elem = p + "[]"
            if elem in fields:  # array of scalars
                for i, e in enumerate(v):
                    if e is None or not _is_type(e, fields[elem]["type"]):
                        errors.append(f"{here}[{i}]: expected {fields[elem]['type']}")
            else:  # array of objects
                for i, e in enumerate(v):
                    if not isinstance(e, dict):
                        errors.append(f"{here}[{i}]: expected object")
                        continue
                    walk_obj(e, elem, f"{here}[{i}]")

    if not isinstance(doc, dict):
        return ["$: expected object"]
    walk_obj(doc, "", "")
    return errors


def redact(doc, path: str = ""):
    if isinstance(doc, dict):
        return {k: redact(v, f"{path}.{k}" if path else k) for k, v in doc.items()}
    if isinstance(doc, list):
        return [redact(v, path + "[]") for v in doc]
    if isinstance(doc, str) and path in REDACT:
        return "<redacted>"
    return doc


def fetch(base: str, lat: float, lon: float, timeout: float) -> bytes:
    url = f"{base}/conditions?lat={lat:.5f}&lon={lon:.5f}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cmd_capture(a) -> int:
    fields = load_contract()
    points = json.loads(POINTS.read_text())["points"]
    raw_dir = Path(a.raw_dir).expanduser()
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir = FIXTURES / a.date
    out_dir.mkdir(parents=True, exist_ok=True)
    bad = 0
    for pt in points:
        t0 = time.time()
        try:
            body = fetch(a.base, pt["lat"], pt["lon"], a.timeout)
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"FAIL  {pt['slug']}: {e}")
            bad += 1
            continue
        ms = int((time.time() - t0) * 1000)
        (raw_dir / f"{pt['slug']}.json").write_bytes(body)
        doc = json.loads(body)
        errs = validate(doc, fields)
        red = redact(doc)
        (out_dir / f"{pt['slug']}.json").write_text(json.dumps(red, indent=1, sort_keys=True) + "\n")
        print(f"{'OK  ' if not errs else 'BAD '}  {pt['slug']:<28} {ms:>6} ms  score={doc.get('score')}"
              f"  weather={'y' if doc.get('weather') else 'n'} water={'y' if doc.get('water') else 'n'}"
              f" gen={'y' if doc.get('generation') else 'n'} wtm={'y' if doc.get('waterTempModel') else 'n'}")
        for e in errs[:10]:
            print("      ", e)
        bad += bool(errs)
        time.sleep(a.pause)
    return 1 if bad else 0


def cmd_check(a) -> int:
    fields = load_contract()
    bad = 0
    if a.live:
        for pt in json.loads(POINTS.read_text())["points"]:
            try:
                doc = json.loads(fetch(a.base, pt["lat"], pt["lon"], a.timeout))
            except Exception as e:  # noqa: BLE001
                print(f"FAIL  {pt['slug']}: {e}")
                bad += 1
                continue
            errs = validate(doc, fields)
            print(f"{'OK  ' if not errs else 'BAD '}  {pt['slug']}")
            for e in errs[:10]:
                print("      ", e)
            bad += bool(errs)
    for f in a.files:
        errs = validate(json.loads(Path(f).read_text()), fields)
        print(f"{'OK  ' if not errs else 'BAD '}  {f}")
        for e in errs[:10]:
            print("      ", e)
        bad += bool(errs)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--timeout", type=float, default=60)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--raw-dir", required=True, help="private folder for unredacted bodies (never this repo)")
    c.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    c.add_argument("--pause", type=float, default=1.0)
    k = sub.add_parser("check")
    k.add_argument("--live", action="store_true")
    k.add_argument("files", nargs="*")
    a = ap.parse_args()
    if a.cmd == "capture" and ROOT in Path(a.raw_dir).expanduser().resolve().parents:
        ap.error("--raw-dir must be outside the repository")
    return cmd_capture(a) if a.cmd == "capture" else cmd_check(a)


if __name__ == "__main__":
    sys.exit(main())
