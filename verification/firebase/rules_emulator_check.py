"""Manual rules check against the Firebase Realtime Database emulator (not a CI test: needs Java and the emulator jar).

The Brain RTDB rules are owned and deployed by Sector Ops (database.rules.json); this repository never carries a copy. Pass the Ops file:

    java -jar ~/.cache/firebase/emulators/firebase-database-emulator-v4.11.2.jar --port 9311 &
    python3 verification/firebase/rules_emulator_check.py /path/to/Sector_Ops/database.rules.json

Records the access facts the Cortex 2.2 audit relies on: clients never write Brain data; allowlisted users read every node, including the
PRIVATE per-lake speciesPresence (FD-11 finding); unallowlisted and anonymous users read nothing. Exit status = number of differences.
"""
import base64, json, sys, urllib.request
B = "http://localhost:9311"; NS = "?ns=audit"
def tok(uid):
    e = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return e({"alg": "none", "typ": "JWT"}) + "." + e({"sub": uid, "user_id": uid, "aud": "audit", "iss": "https://securetoken.google.com/audit", "iat": 1, "exp": 9999999999}) + "."
def req(method, path, auth=None, body=None, owner=False):
    url = f"{B}/{path}.json{NS}" + (f"&auth={auth}" if auth else "")
    r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    if owner: r.add_header("Authorization", "Bearer owner")
    try:
        with urllib.request.urlopen(r) as resp: return resp.status
    except urllib.error.HTTPError as e: return e.code
rules = open(sys.argv[1]).read()
print("load rules", req("PUT", ".settings/rules", body=json.loads(rules), owner=True))
seed = {"access": {"opsUsers": {"allowed": True}}, "lakes": {"L": {"speciesPresence": {"s": {"state": "x"}}, "states": {"wind": {"v": 1}}}},
        "scores": {"wind": {"value": 1}}, "brains": {"wind": {"status": "x"}}, "control": {"fleet": {"L": {"x": 1}}}, "opsPreferences": {"allowed": {"a": 1}}}
print("seed (admin)", req("PUT", "", body=seed, owner=True))
A, O = tok("allowed"), tok("other")
checks = [
 ("allowlisted read /lakes/L/speciesPresence (PRIVATE)", req("GET", "lakes/L/speciesPresence", auth=A), 200),
 ("non-allowlisted read /lakes/L/speciesPresence", req("GET", "lakes/L/speciesPresence", auth=O), 401),
 ("anonymous read /scores", req("GET", "scores"), 401),
 ("allowlisted read /scores/wind", req("GET", "scores/wind", auth=A), 200),
 ("allowlisted write /scores/wind", req("PUT", "scores/wind/value", auth=A, body=9), 401),
 ("allowlisted write /brains/wind", req("PUT", "brains/wind/status", auth=A, body="y"), 401),
 ("allowlisted write /brains/fish", req("PUT", "brains/fish", auth=A, body={"x": 1}), 401),
 ("allowlisted write /lakeFleet/L/lastUpdatedAt", req("PUT", "lakeFleet/L/lastUpdatedAt", auth=A, body="x"), 401),
 ("allowlisted write /control/engineeringStatusV1", req("PUT", "control/engineeringStatusV1", auth=A, body={"x": 1}), 401),
 ("allowlisted read root", req("GET", "", auth=A), 401),
 ("allowlisted write own /opsPreferences", req("PUT", "opsPreferences/allowed/a", auth=A, body=2), 200),
 ("allowlisted write other's /opsPreferences", req("PUT", "opsPreferences/other/a", auth=A, body=2), 401),
]
bad = 0
for name, got, want in checks:
    ok = got == want; bad += not ok
    print(("OK  " if ok else "DIFF"), name, got, "(expected", want, ")")
sys.exit(bad)
