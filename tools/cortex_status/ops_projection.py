#!/usr/bin/env python3
"""Build the SANITIZED Sector Ops projection (contracts/schemas/engineering-status-ops-v1.schema.json) of an engineering-status-v1 report.

  python3 tools/cortex_status/ops_projection.py --report R.json [--ci ci.json] --out P.json      # build + validate + sanitize-check
  python3 tools/cortex_status/ops_projection.py --report R.json --check                            # exit 1 if a projection would leak

The projection keeps only what a browser dashboard may show: statuses, closed labels, proof results, counts and short human summaries. It drops
every evidence string, and REFUSES (exit 1) when any kept text matches a forbidden pattern (the Sector Ops public-bundle scanner's patterns plus
repository file paths and branch names), so a leak is fixed at its source instead of being redacted silently. It requires a commit-stamped report
(CI `build_engineering_status.py --emit ... --commit $GITHUB_SHA`). This tool has NO write capability: publishing the projection to Sector Ops
(proposed /control/engineeringStatusV1) is a separate, gated decision (production Firebase write)."""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHEMA = os.path.join(ROOT, "contracts", "schemas", "engineering-status-ops-v1.schema.json")
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
from jsonschema_lite import validate  # noqa: E402

FORBIDDEN = [
    ("gs:// URI", r"gs://"), ("local path", r"/Users/[A-Za-z0-9._-]+|Desktop/Development|Library/Caches|Application Support|/home/[a-z]"),
    ("private resource", r"sector-biology-private|sector-lake-brain|sector-wind-candidate|sector-water-temp-archive|sector-clarity-candidate|run-sources-sector-9393c|gcf-(v2-)?sources-"),
    ("credential", r"private_key|BEGIN [A-Z ]*PRIVATE KEY|client_secret|ghp_|github_pat_|AKIA[0-9A-Z]{8}|ya29\.|xox[abpr]-|sk-ant-|iam\.gserviceaccount\.com"),
    ("repository file path", r"\b[\w.-]+/[\w./{}-]*\.(py|json|md|swift|sh|yml|yaml|txt|csv)\b|\b(docs|brains|jobs|tools|contracts|Sources|Tests)/[\w./-]+"),
    ("branch or repository name", r"\b(cortex|feat|fix|docs|cert|security)/[\w.-]+-\d{4}|Sector-Bowfishing|Sector_Engine"),
    ("image or digest", r"sha256:[0-9a-f]{12}|brain-jobs:[0-9a-f]+|@sha256"),
]


def project(report: dict, ci: dict | None = None) -> dict:
    src = report["source"]
    commit = src["evaluatedCommit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SystemExit("the report is not commit-stamped (needs a full 40-hex evaluatedCommit from CI --emit --commit $GITHUB_SHA)")
    gen = {"sourceCommit": commit, "sourceDigest": src["sourceDigest"], "certificationCurrent": bool(src.get("certificationCurrent")),
           "evaluatedAt": src["evaluatedAt"], "reportSchemaVersion": report["schemaVersion"]}
    if ci:
        gen["ci"] = {k: ci[k] for k in ("result", "passed", "failed", "pending") if k in ci}
    brains = []
    for b in report["brains"]:
        cert = {"status": b["structuralCertification"]["status"], "proofs": b.get("certificationProofs", {})}
        if b.get("certificationMutations"):
            cert["mutationsPassed"] = b["certificationMutations"].get("passed", 0)
            cert["mutationsFailed"] = b["certificationMutations"].get("failed", 0)
        brains.append({
            "brainId": b["brainId"], "lifecycle": b["lifecycle"], "packageStatus": b["packageStatus"],
            "statusLayers": {k: {"status": v["status"], "label": v["label"]} for k, v in b["statusLayers"].items()},     # evidence strings dropped
            "certification": cert,
            "memory": {m["check"]: {"branch": m["branch"], "production": m["production"]} for m in b["memory"]},        # evidence strings dropped
            "requirements": b.get("requirements", {}),
            "structuralProblems": b.get("structuralProblems", []), "scienceDependencies": b.get("scienceDependencies", []),
            "nextWork": b.get("nextWork", []), "blockers": b.get("blockers", [])})
    st = report["standards"]
    out = {"schema": "engineering-status-ops-v1", "schemaVersion": "1.0.0", "reportId": report["reportId"], "generatedFrom": gen,
           "standards": {"framework": st["framework"], "version": st["version"], "pin": st["pin"]}, "statusVocabulary": report["statusVocabulary"],
           "brains": brains,
           "decisions": [{k: d[k] for k in ("id", "class", "title", "brains") if k in d} for d in report["decisions"]]}
    if report.get("changes"):
        out["recentChanges"] = [{"commit": c["commit"][:12], "summary": _commit_summary(c["summary"])} for c in report["changes"][:20]]
    return out


def _commit_summary(text: str) -> str:
    """Commit subjects are immutable history, so they are the ONE place paths are normalized rather than refused:
    brains/<dir> -> <dir>; any other repository path -> [path]. The result is still leak-checked like every other field."""
    t = re.sub(r"\bbrains/([a-z][a-z-]*)\b(?!/)", r"\1", text)
    t = re.sub(r"\b[\w.-]+(?:/[\w.{}-]+)+\b", "[path]", t)
    return t[:240]


def leaks(obj, path="") -> list[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += leaks(k, f"{path}/<key>") + leaks(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += leaks(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        if path.endswith("/sourceDigest"):
            return out                                        # the content digest is provenance, not an artifact reference
        for name, rx in FORBIDDEN:
            if re.search(rx, obj):
                out.append(f"{path}: {name}: {obj[:80]!r}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--ci")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--out")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    proj = project(json.load(open(a.report, encoding="utf-8")), json.load(open(a.ci, encoding="utf-8")) if a.ci else None)
    errs = list(validate(proj, json.load(open(SCHEMA, encoding="utf-8"))))
    bad = leaks(proj)
    if errs or bad:
        print("REFUSED: the Sector Ops projection is not publishable:\n" + "\n".join((errs + bad)[:30]))
        return 1
    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(proj, indent=2, sort_keys=True) + "\n")
        print(f"wrote {a.out} ({proj['reportId']} @ {proj['generatedFrom']['sourceCommit'][:12]}; {len(json.dumps(proj))} bytes; sanitized)")
    else:
        print(f"OK: projection of {proj['reportId']} is schema-valid and leak-free")
    return 0


if __name__ == "__main__":
    sys.exit(main())
