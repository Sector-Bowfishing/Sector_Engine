"""Brain RTDB rules checks against the Firebase Realtime Database emulator (Cortex 2.2 FD-11 / PL-08).

The rules are owned and deployed by Sector Ops (`database.rules.json`); this repository never carries a copy. Pass the Ops file:

    java -jar ~/.cache/firebase/emulators/firebase-database-emulator-v4.11.2.jar --port 9311 &
    python3 verification/firebase/rules_emulator_check.py /path/to/Sector_Ops/database.rules.json             # the deployed rules
    python3 verification/firebase/rules_emulator_check.py /path/to/Sector_Ops/database.rules.json --proposed  # + least-privilege speciesPresence

`--proposed` applies `propose_species_presence_rules()` in memory: the same proposal the Sector Ops session is asked to make (no rules file here is
deployable). The pytest wrapper `test_rules_emulator.py` runs both when SECTOR_OPS_RULES and an emulator are available, and skips otherwise.
Exit status = number of differences.
"""
from __future__ import annotations

import base64
import copy
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:9311"
NS = "?ns=audit"
OPS = "auth != null && root.child('access').child('opsUsers').child(auth.uid).val() === true"
PRIVATE = OPS + " && root.child('access').child('privateResearchUsers').child(auth.uid).val() === true"
LAKE_CHILDREN_OPS = ("brain", "states", "profiles", "validation")      # what Ops and the dashboards read under /lakes/{k}; speciesPresence is separate


def propose_species_presence_rules(rules: dict) -> dict:
    """Least privilege for PRIVATE /lakes/{k}/speciesPresence. RTDB read grants cascade, so the /lakes grant moves down to the named children and
    speciesPresence gets its own narrower allowlist (/access/privateResearchUsers/{uid}). Writes stay closed; server writers are unaffected."""
    r = copy.deepcopy(rules)
    root = r["rules"]
    root["lakes"] = {".write": False, "$k": {**{c: {".read": OPS, ".write": False} for c in LAKE_CHILDREN_OPS},
                                             "speciesPresence": {".read": PRIVATE, ".write": False}}}
    root.setdefault("access", {})["privateResearchUsers"] = {"$uid": {".read": "auth != null && auth.uid === $uid", ".write": False}}
    return r


def _tok(uid: str) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")     # noqa: E731  (unsigned: the emulator accepts it)
    return enc({"alg": "none", "typ": "JWT"}) + "." + enc({"sub": uid, "user_id": uid, "aud": "audit", "iss": "https://securetoken.google.com/audit",
                                                         "iat": 1, "exp": 9999999999}) + "."


def _req(method: str, path: str, auth: str | None = None, body=None, owner: bool = False, base: str = BASE) -> int:
    url = f"{base}/{path}.json{NS}" + (f"&auth={auth}" if auth else "")
    r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    if owner:
        r.add_header("Authorization", "Bearer owner")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def run(rules: dict, proposed: bool, base: str = BASE) -> list[tuple[str, int, int]]:
    """-> [(check, got, expected)] for the deployed rules (proposed=False) or the proposal (True)."""
    if proposed:
        rules = propose_species_presence_rules(rules)
    assert _req("PUT", ".settings/rules", body=rules, owner=True, base=base) == 200
    seed = {"access": {"opsUsers": {"ops": True, "research": True}, "privateResearchUsers": {"research": True}},
            "lakes": {"L": {"speciesPresence": {"s": {"state": "x"}}, "states": {"wind": {"v": 1}}, "brain": {"speciesPresenceSummary": {"recordCount": 1}}}},
            "scores": {"wind": {"value": 1}}, "brains": {"wind": {"status": "x"}}, "control": {"fleet": {"L": {"x": 1}}},
            "opsPreferences": {"ops": {"a": 1}}}
    assert _req("PUT", "", body=seed, owner=True, base=base) == 200
    ops, research, other = _tok("ops"), _tok("research"), _tok("other")
    g = lambda p, a: _req("GET", p, auth=a, base=base)                      # noqa: E731
    w = lambda p, a, v: _req("PUT", p, auth=a, body=v, base=base)            # noqa: E731
    out = [
        ("non-allowlisted read /lakes/L/speciesPresence", g("lakes/L/speciesPresence", other), 401),
        ("anonymous read /scores", g("scores", None), 401),
        ("allowlisted read /scores/wind", g("scores/wind", ops), 200),
        ("allowlisted read /lakes/L/brain (sanitized summary)", g("lakes/L/brain", ops), 200),
        ("allowlisted write /scores/wind", w("scores/wind/value", ops, 9), 401),
        ("allowlisted write /brains/wind", w("brains/wind/status", ops, "y"), 401),
        ("allowlisted write /brains/fish", w("brains/fish", ops, {"x": 1}), 401),
        ("allowlisted write /lakeFleet/L/lastUpdatedAt", w("lakeFleet/L/lastUpdatedAt", ops, "x"), 401),
        ("allowlisted write /control/engineeringStatusV1", w("control/engineeringStatusV1", ops, {"x": 1}), 401),
        ("allowlisted write /lakes/L/speciesPresence", w("lakes/L/speciesPresence/s", research, {"x": 1}), 401),
        ("allowlisted read root", g("", ops), 401),
        ("allowlisted write own /opsPreferences", w("opsPreferences/ops/a", ops, 2), 200),
        ("allowlisted write other's /opsPreferences", w("opsPreferences/other/a", ops, 2), 401),
    ]
    if proposed:
        out += [("ops-only user read /lakes/L/speciesPresence (PRIVATE)", g("lakes/L/speciesPresence", ops), 401),
                ("private-research user read /lakes/L/speciesPresence", g("lakes/L/speciesPresence", research), 200),
                ("ops user read /lakes/L/states", g("lakes/L/states", ops), 200),
                ("ops user read whole /lakes/L (no reader does this)", g("lakes/L", ops), 401),
                ("user reads own privateResearchUsers flag", g("access/privateResearchUsers/research", research), 200),
                ("user reads another's privateResearchUsers flag", g("access/privateResearchUsers/research", ops), 401)]
    else:
        out += [("allowlisted read /lakes/L/speciesPresence (PRIVATE; FD-11 finding)", g("lakes/L/speciesPresence", ops), 200)]
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    proposed = "--proposed" in argv
    path = [a for a in argv if not a.startswith("--")][0]
    with open(path, encoding="utf-8") as fh:
        rules = json.load(fh)
    bad = 0
    for mode in ([False, True] if proposed else [False]):
        print("== proposed (least-privilege speciesPresence)" if mode else "== deployed rules")
        for name, got, want in run(rules, mode):
            bad += got != want
            print(("OK  " if got == want else "DIFF"), name, got, f"(expected {want})")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
