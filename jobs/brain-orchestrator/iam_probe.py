#!/usr/bin/env python3
"""Least-privilege probe for the Water Clarity pilot: runs real allowed/denied operations AS the intended identities (impersonated, no key files) and reports what happened.

Only operations that must be DENIED are attempted as writes, so a correct configuration leaves production untouched. If a write that must be denied SUCCEEDS the probe removes
what it wrote, reports FAIL and exits non-zero (the pilot halts). RTDB probe path: /_iamprobe (not a Brain path); storage probes target prefixes the identity must not own.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT, DB, BUCKET = "sector-9393c", "https://sector-brain.firebaseio.com", "sector-9393c-brain-artifacts"
CLARITY = f"clarity-brain-job@{PROJECT}.iam.gserviceaccount.com"
PUBLISHER = f"sector-publisher@{PROJECT}.iam.gserviceaccount.com"
SCOPES = "https://www.googleapis.com/auth/firebase.database,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/devstorage.read_write"


def token(sa):
    o = subprocess.run(["gcloud", "auth", "print-access-token", f"--impersonate-service-account={sa}", f"--scopes={SCOPES}"], capture_output=True, text=True)
    if o.returncode:
        raise SystemExit(f"cannot impersonate {sa}: {o.stderr.strip()[:200]}")
    return o.stdout.strip()


def http(method, url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:200]


def rtdb(method, path, tok, payload=None):
    return http(method, f"{DB}/{path}.json?" + urllib.parse.urlencode({"access_token": tok}), None if payload is None else json.dumps(payload).encode(), {"Content-Type": "application/json"})


def gcs_create(tok, name):
    u = f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o?uploadType=media&ifGenerationMatch=0&name={urllib.parse.quote(name, safe='')}"
    return http("POST", u, b'{"probe":true}', {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})


def gcs_delete(tok, name):
    return http("DELETE", f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{urllib.parse.quote(name, safe='')}", None, {"Authorization": f"Bearer {tok}"})


def main():
    results, wrote = [], []

    def expect(identity, op, want_denied, status, detail=""):
        denied = status in (401, 403)
        ok = denied if want_denied else (200 <= status < 300)
        results.append({"identity": identity.split("@")[0], "operation": op, "expected": "DENIED" if want_denied else "ALLOWED", "httpStatus": status, "pass": ok})
        return ok
    tc, tp = token(CLARITY), token(PUBLISHER)

    # Water Clarity job identity: reads yes, canonical/any RTDB writes no, artifacts of other Brains no, Publisher history no
    expect(CLARITY, "RTDB read /brains/water-clarity/status", False, rtdb("GET", "brains/water-clarity/status", tc)[0])
    s, _ = rtdb("PUT", "_iamprobe/clarity", tc, {"p": 1})
    if expect(CLARITY, "RTDB write /_iamprobe/clarity", True, s) is False and 200 <= s < 300:
        rtdb("DELETE", "_iamprobe/clarity", tc); wrote.append("rtdb:_iamprobe/clarity")
    s, _ = rtdb("PATCH", "brains/water-clarity", tc, {"_iamprobe": 1})
    if not expect(CLARITY, "RTDB write /brains/water-clarity (canonical Brain intelligence)", True, s) and 200 <= s < 300:
        wrote.append("rtdb:brains/water-clarity/_iamprobe")
    for name, want in (("artifacts/wind/_iamprobe/x", True), ("publishes/water-clarity/_iamprobe/x", True), ("exports/orchestrator/_iamprobe/x", True)):
        s, _ = gcs_create(tc, name)
        if not expect(CLARITY, f"GCS create {name}", want, s) and 200 <= s < 300:
            wrote.append("gcs:" + name)
    # Publisher identity: may write RTDB (proved by the real publication) but never the Brains' artifacts, orchestrator records or another prefix
    for name in ("artifacts/water-clarity/_iamprobe/x", "exports/orchestrator/_iamprobe/x", "scores/_iamprobe/x"):
        s, _ = gcs_create(tp, name)
        if not expect(PUBLISHER, f"GCS create {name}", True, s) and 200 <= s < 300:
            wrote.append("gcs:" + name)
    expect(PUBLISHER, "RTDB read /brains/water-clarity/status", False, rtdb("GET", "brains/water-clarity/status", tp)[0])
    for w in wrote:                                    # a denied write that succeeded: remove it, then fail loudly
        kind, path = w.split(":", 1)
        if kind == "rtdb":
            rtdb("DELETE", path, token(CLARITY) if False else tp)
        else:
            gcs_delete(tp if "publisher" in path else tc, path)
    print(json.dumps(results, indent=1))
    bad = [r for r in results if not r["pass"]]
    print(f"{len(results) - len(bad)}/{len(results)} probes behaved as required" + (f"; FAILED: {[b['operation'] for b in bad]}; unexpected writes cleaned: {wrote}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
