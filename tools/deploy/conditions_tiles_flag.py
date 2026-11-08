#!/usr/bin/env python3
"""Set the Remote Config parameter `conditions_tiles_v1` to a reviewed preset (Sector_Ops #53; DEPLOY_WORKFLOWS_V1.md §3).

Run by .github/workflows/set-conditions-tiles.yml. Standard library only.

  python3 tools/deploy/conditions_tiles_flag.py plan  --preset weather-shadow          # offline: print what would be written
  python3 tools/deploy/conditions_tiles_flag.py apply --preset weather-shadow --project <id>   # token in env RC_ACCESS_TOKEN

Presets (the only values this tool writes):
  off             delete the parameter: every tile `off` (TileFlags: absent -> allOff)
  weather-shadow  the five weather tiles in `shadow`, every other tile `off`

Safety:
  * Read-modify-write of the WHOLE template with its ETag (If-Match): a concurrent edit makes the write fail, never lost.
  * Only `conditions_tiles_v1` changes. The template is read back after the write and every other parameter, group and condition is
    compared with what was read before the write; any difference fails the run.
  * Nothing containing `serve` is ever written: a serve flip is customer-visible and the owner approves it separately.
    `weather-shadow` is also refused when the CURRENT value contains `serve` (that change is customer-visible too); `off` is always allowed
    (it is the rollback).
  * The value is validated with TileFlags semantics (a Python mirror of Sources/SectorEngine/Conditions/TileFlags.swift `parse`) before the
    write and again on the read-back.
  * The Engine reads only TOP-LEVEL `parameters.<name>.defaultValue.value` (RemoteConfigREST.defaults). A `conditions_tiles_v1` inside a
    parameter group, or one with conditional values, is refused: the owner resolves it in the console first.
  * The template version before and after is printed: rollback = this tool with `off`, or a Remote Config version rollback to "before".
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request

PARAM = "conditions_tiles_v1"
API = "https://firebaseremoteconfig.googleapis.com/v1/projects/{project}/remoteConfig"

# TileFlags.swift TileKey / TileMode raw values (binding).
TILE_KEYS = ("humidity", "pressure", "temperature", "sky", "wind", "windOutlookModel", "waterLevel", "clarity", "waterTemp", "generation")
TILE_MODES = ("off", "shadow", "serve")
WEATHER_TILES = ("humidity", "pressure", "temperature", "sky", "wind")

# The exact string written for weather-shadow (owner-specified; Sector_Ops #53). Compact, this key order.
WEATHER_SHADOW = ('{"version":1,"tiles":{"humidity":{"mode":"shadow"},"pressure":{"mode":"shadow"},'
                  '"temperature":{"mode":"shadow"},"sky":{"mode":"shadow"},"wind":{"mode":"shadow"}}}')
PRESETS = {"off": None, "weather-shadow": WEATHER_SHADOW}
# The effective mode of every tile each preset must produce (TileFlags.mode(for:lakeId:) with any lake).
EXPECTED = {
    "off": {k: "off" for k in TILE_KEYS},
    "weather-shadow": {k: ("shadow" if k in WEATHER_TILES else "off") for k in TILE_KEYS},
}


class Refused(Exception):
    """A safety rule refused the change. Nothing was written."""


# ── TileFlags semantics (mirror of TileFlags.parse / mode(for:lakeId:)) ───────────────────────────────────────────────
def parse_tile_flags(raw: str | None) -> dict:
    """-> {"version": int|None, "tiles": {key: {"mode": str, "lakes": list|None}}}. Same fail-safe rules as TileFlags.parse:
    nil/empty/invalid JSON or no `tiles` object -> all off; unknown keys ignored; a missing/unknown mode or malformed entry is skipped (off);
    a `lakes` that is not a list of strings makes that tile off."""
    if raw is None:
        return {"version": None, "tiles": {}}
    try:
        root = json.loads(raw)
    except (ValueError, TypeError):
        return {"version": None, "tiles": {}}
    if not isinstance(root, dict) or not isinstance(root.get("tiles"), dict):
        return {"version": None, "tiles": {}}
    v = root.get("version")
    version = int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    tiles = {}
    for key, entry in root["tiles"].items():
        if key not in TILE_KEYS or not isinstance(entry, dict):
            continue
        mode = entry.get("mode")
        if mode not in TILE_MODES:
            continue
        lakes = None
        if "lakes" in entry:
            if not (isinstance(entry["lakes"], list) and all(isinstance(x, str) for x in entry["lakes"])):
                continue
            lakes = list(entry["lakes"])
        tiles[key] = {"mode": mode, "lakes": lakes}
    return {"version": version, "tiles": tiles}


def effective_modes(raw: str | None) -> dict:
    """Every tile's mode for an unrestricted request (TileFlags.mode with a lake the document does not restrict away)."""
    flags = parse_tile_flags(raw)
    out = {}
    for k in TILE_KEYS:
        t = flags["tiles"].get(k)
        out[k] = "off" if t is None or t["mode"] == "off" else t["mode"]
    return out


def validate_preset(preset: str, raw: str | None) -> list[str]:
    """Problems with `raw` as the value of `preset` (empty = valid). Stricter than the parser: unknown keys, lake restrictions and a
    version other than 1 are errors here, because the parser would silently ignore them."""
    errs = []
    if preset not in PRESETS:
        return [f"unknown preset {preset!r} (allowed: {', '.join(PRESETS)})"]
    if raw is not None and "serve" in raw:
        errs.append("value contains 'serve': a serve flip is customer-visible and approved separately by the owner")
    if preset == "off":
        if raw is not None:
            errs.append("preset off deletes the parameter: the value must be absent")
        return errs
    try:
        root = json.loads(raw) if raw is not None else None
    except ValueError as e:
        return errs + [f"not JSON: {e}"]
    if not isinstance(root, dict) or set(root) != {"version", "tiles"} or root.get("version") != 1 or not isinstance(root.get("tiles"), dict):
        errs.append("document must be exactly {version: 1, tiles: {...}}")
        return errs
    for k, e in root["tiles"].items():
        if k not in TILE_KEYS:
            errs.append(f"unknown tile key {k!r}")
        if not isinstance(e, dict) or set(e) != {"mode"} or e.get("mode") not in TILE_MODES:
            errs.append(f"tile {k!r}: entry must be exactly {{mode: off|shadow|serve}}")
    got = effective_modes(raw)
    if got != EXPECTED[preset]:
        diff = {k: (got[k], EXPECTED[preset][k]) for k in TILE_KEYS if got[k] != EXPECTED[preset][k]}
        errs.append(f"TileFlags effective modes differ from the preset (got, want): {diff}")
    return errs


# ── Template edit (pure) ──────────────────────────────────────────────────────────────────────────────────────────────
def current_value(template: dict) -> str | None:
    p = (template.get("parameters") or {}).get(PARAM)
    if not isinstance(p, dict):
        return None
    dv = p.get("defaultValue")
    return dv.get("value") if isinstance(dv, dict) else None


def preflight(template: dict, preset: str) -> list[str]:
    """Refusals that depend on the current template."""
    errs = []
    for g, group in (template.get("parameterGroups") or {}).items():
        if PARAM in ((group or {}).get("parameters") or {}):
            errs.append(f"{PARAM} is inside parameter group {g!r}: the Engine reads only top-level parameters; resolve it in the console first")
    p = (template.get("parameters") or {}).get(PARAM)
    if isinstance(p, dict) and p.get("conditionalValues"):
        errs.append(f"{PARAM} has conditional values ({', '.join(sorted(p['conditionalValues']))}): the Engine ignores them; resolve them in the console first")
    if isinstance(p, dict) and not isinstance(p.get("defaultValue"), dict):
        errs.append(f"{PARAM} exists without a plain defaultValue: resolve it in the console first")
    cur = json.dumps(p) if p is not None else ""
    if preset != "off" and "serve" in cur:
        errs.append(f"the CURRENT {PARAM} contains 'serve': changing it is customer-visible; the owner does that separately (preset off is allowed)")
    return errs


def apply_preset(template: dict, preset: str) -> dict:
    """The template to PUT: a deep copy with ONLY `parameters.conditions_tiles_v1` changed, and the server-owned `version` removed."""
    out = copy.deepcopy(template)
    out.pop("version", None)
    params = out.setdefault("parameters", {})
    value = PRESETS[preset]
    if value is None:
        params.pop(PARAM, None)
        if not params:
            out.pop("parameters")
    else:
        old = params.get(PARAM) or {}
        new = {"defaultValue": {"value": value}, "valueType": "JSON"}
        if old.get("description"):
            new["description"] = old["description"]
        params[PARAM] = new
    return out


def without_param(template: dict) -> dict:
    """The template minus the target parameter and the version metadata: what must be identical before and after."""
    t = copy.deepcopy(template)
    t.pop("version", None)
    (t.get("parameters") or {}).pop(PARAM, None)
    if "parameters" in t and not t["parameters"]:
        t.pop("parameters")
    return t


def verify_readback(before: dict, after: dict, preset: str) -> list[str]:
    errs = []
    if without_param(before) != without_param(after):
        errs.append("the template changed outside conditions_tiles_v1 (or a concurrent edit landed): inspect the version history")
    got = current_value(after)
    want = PRESETS[preset]
    if want is None:
        if PARAM in (after.get("parameters") or {}):
            errs.append(f"{PARAM} still present after preset off")
    else:
        if got is None:
            errs.append(f"{PARAM} missing after the write")
        elif json.loads(got) != json.loads(want):
            errs.append(f"read-back value differs: {got!r}")
        elif got != want:
            print(f"  note: read-back string is formatted differently but parses equal: {got!r}")
    errs += validate_preset(preset, got if want is not None else None)
    return errs


def version_of(template: dict) -> str:
    v = template.get("version") or {}
    return f"{v.get('versionNumber', '?')} ({v.get('updateTime', '?')}, by {((v.get('updateUser') or {}).get('email') and 'a user') or '?'})"


# ── REST ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _request(method: str, url: str, token: str, body: dict | None = None, etag: str | None = None):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json; UTF-8"
    if etag is not None:
        headers["If-Match"] = etag
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}"), r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        detail = e.read()[:500].decode(errors="replace")
        raise RuntimeError(f"{method} remoteConfig -> HTTP {e.code}: {detail}") from None


def cmd_plan(a) -> int:
    value = PRESETS[a.preset]
    errs = validate_preset(a.preset, value)
    print(f"preset {a.preset}: " + ("delete the parameter" if value is None else value))
    print("effective modes:", json.dumps(effective_modes(value), sort_keys=True))
    for e in errs:
        print("REFUSED:", e)
    return 1 if errs else 0


def cmd_apply(a) -> int:
    token = os.environ.get("RC_ACCESS_TOKEN", "")
    if not token:
        print("RC_ACCESS_TOKEN is not set", file=sys.stderr)
        return 2
    errs = validate_preset(a.preset, PRESETS[a.preset])
    if errs:
        for e in errs:
            print("REFUSED:", e)
        return 1
    url = API.format(project=a.project)
    _, before, etag = _request("GET", url, token)
    if not etag:
        print("REFUSED: the template read returned no ETag", file=sys.stderr)
        return 1
    print(f"template version BEFORE: {version_of(before)}")
    print(f"current {PARAM}: {current_value(before)!r}")
    errs = preflight(before, a.preset)
    if errs:
        for e in errs:
            print("REFUSED:", e)
        return 1
    new = apply_preset(before, a.preset)
    if without_param(new) != without_param(before):
        print("REFUSED: internal error, the edit touched more than one parameter", file=sys.stderr)
        return 1
    if current_value(before) == PRESETS[a.preset] and (PARAM in (before.get("parameters") or {})) == (PRESETS[a.preset] is not None):
        print(f"no change: {PARAM} is already {a.preset}")
        return 0
    _request("PUT", url + "?validate_only=true", token, new, etag)
    print("validate_only: accepted")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    _, written, _ = _request("PUT", url, token, new, etag)
    _, after, _ = _request("GET", url, token)
    print(f"template version AFTER:  {version_of(after)}")
    errs = verify_readback(before, after, a.preset)
    for e in errs:
        print("READ-BACK FAILED:", e)
    if errs:
        return 1
    bv = (before.get("version") or {}).get("versionNumber", "?")
    print(f"OK: {PARAM} is {a.preset}. Rollback: preset off, or roll the template back to version {bv}.")
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    if out:
        with open(out, "a") as f:
            f.write(f"### conditions_tiles_v1 -> `{a.preset}`\n\n| | |\n|---|---|\n"
                    f"| template version before | {bv} |\n| template version after | {(after.get('version') or {}).get('versionNumber', '?')} |\n"
                    f"| effective modes | `{json.dumps(effective_modes(current_value(after)), sort_keys=True)}` |\n"
                    f"| read-back | every other parameter, group and condition unchanged |\n\n"
                    f"Rollback: run this workflow with `off`, or roll Remote Config back to version {bv}. "
                    f"The Engine picks the change up within its 10-minute cache.\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--preset", required=True)
    w = sub.add_parser("apply")
    w.add_argument("--preset", required=True)
    w.add_argument("--project", required=True)
    w.add_argument("--dry-run", action="store_true", help="read and validate_only; write nothing")
    a = ap.parse_args(argv)
    if a.preset not in PRESETS or "serve" in a.preset:
        print(f"REFUSED: preset must be one of {', '.join(PRESETS)}", file=sys.stderr)
        return 1
    try:
        return {"plan": cmd_plan, "apply": cmd_apply}[a.cmd](a)
    except (Refused, RuntimeError) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
