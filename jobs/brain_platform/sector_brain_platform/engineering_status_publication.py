"""Publication gate for the Sector Ops engineering-status projection (`engineering-status-ops-v1`) at /control/engineeringStatusV1.

ONE sanitizer and ONE gate, shared by the producer (tools/cortex_status/ops_projection.py, CI) and the only writer (the orchestrator control plane,
`orchestrate.py --publish-engineering-status`, OFF by default: decision O-1). Stdlib only; no network, no clock (callers pass `now`).

The orchestrator image carries the projection produced at the exact commit it was built from (deploy staging). `gate()` returns the document to
publish: the validated projection, or an explicit UNAVAILABLE document saying why. It never publishes an unmerged branch, a projection whose
certification belongs to other code, a projection of a commit other than the deployed one, or a leaking field. Publishing UNAVAILABLE (instead of
writing nothing) keeps an older status from looking current."""
from __future__ import annotations

import json
import os
import re

NODE = "control/engineeringStatusV1"
SCHEMA = "engineering-status-ops-v1"
SUPPORTED_MAJOR = "1"
LAYERS = ("canonicalStructure", "structuralCertification", "scientificValidation", "approvedMemoryRelease", "operationalReadiness",
          "productionActivation", "customerConsumable")
STAGED_FILE = "engineering-status-ops.json"            # staged next to the platform package in the orchestrator image (deploy-job.sh)

# The Sector Ops public-bundle scanner's patterns plus repository paths, branch/repository names and image digests.
FORBIDDEN = (
    ("gs:// URI", r"gs://"), ("local path", r"/Users/[A-Za-z0-9._-]+|Desktop/Development|Library/Caches|Application Support|/home/[a-z]"),
    ("private resource", r"sector-biology-private|sector-lake-brain|sector-wind-candidate|sector-water-temp-archive|sector-clarity-candidate|run-sources-sector-9393c|gcf-(v2-)?sources-"),
    ("credential", r"private_key|BEGIN [A-Z ]*PRIVATE KEY|client_secret|ghp_|github_pat_|AKIA[0-9A-Z]{8}|ya29\.|xox[abpr]-|sk-ant-|iam\.gserviceaccount\.com"),
    ("repository file path", r"\b[\w.-]+/[\w./{}-]*\.(py|json|md|swift|sh|yml|yaml|txt|csv)\b|\b(docs|brains|jobs|tools|contracts|Sources|Tests)/[\w./-]+"),
    ("branch or repository name", r"\b(cortex|feat|fix|docs|cert|security)/[\w.-]+-\d{4}|Sector-Bowfishing|Sector_Engine"),
    ("image or digest", r"sha256:[0-9a-f]{12}|brain-jobs:[0-9a-f]+|@sha256"),
)
SAFE_KEYS = ("/sourceDigest",)                              # provenance value that is not an artifact reference
BRANCH_KEYS = ("/sourceBranch",)                             # the git ref is shown on purpose: exempt from the branch-name rule only


def leaks(obj, path: str = "") -> list[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += leaks(k, f"{path}/<key>") + leaks(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += leaks(v, f"{path}[{i}]")
    elif isinstance(obj, str) and not path.endswith(SAFE_KEYS):
        for name, rx in FORBIDDEN:
            if name == "branch or repository name" and path.endswith(BRANCH_KEYS):
                continue
            if re.search(rx, obj):
                out.append(f"{path}: {name}")
    return out


def problems(doc: dict) -> list[str]:
    """Structural contract checks that need no schema engine (the full JSON-schema validation runs where the projection is produced)."""
    p = []
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return [f"not an {SCHEMA} document"]
    if str(doc.get("schemaVersion", "")).split(".")[0] != SUPPORTED_MAJOR:
        p.append(f"unsupported schemaVersion {doc.get('schemaVersion')!r}")
    g = doc.get("generatedFrom") or {}
    if not re.fullmatch(r"[0-9a-f]{40}", str(g.get("sourceCommit", ""))):
        p.append("generatedFrom.sourceCommit is not a full commit id")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(g.get("sourceDigest", ""))):
        p.append("generatedFrom.sourceDigest missing")
    brains = doc.get("brains") or []
    if len(brains) < 8:
        p.append(f"{len(brains)} Brains (expected all registered Brains)")
    for b in brains:
        if set((b.get("statusLayers") or {})) != set(LAYERS):
            p.append(f"{b.get('brainId')}: status layers incomplete")
    return p + leaks(doc)


def unavailable(reason: str, now_iso: str, *, deployment_version: str | None = None) -> dict:
    return {"schema": SCHEMA, "schemaVersion": "1.2.0", "state": "UNAVAILABLE", "reason": reason[:240], "checkedAt": now_iso,
            **({"publishedBy": {"component": "brain-orchestrator", "deploymentVersion": deployment_version}} if deployment_version else {})}


def gate(doc: dict | None, *, deployed_commit: str | None, now_iso: str, deployment_version: str | None = None) -> dict:
    """-> the document to write at NODE. AVAILABLE only when every rule holds; otherwise UNAVAILABLE with the reason."""
    if doc is None:
        return unavailable("no engineering-status projection in this image", now_iso, deployment_version=deployment_version)
    bad = problems(doc)
    if bad:
        return unavailable("projection rejected: " + "; ".join(bad[:3]), now_iso, deployment_version=deployment_version)
    g = doc["generatedFrom"]
    if g.get("codeState") != "MAIN_COMMIT":
        return unavailable(f"projection describes {g.get('codeState') or 'unknown'} code, not a commit on main", now_iso, deployment_version=deployment_version)
    if not g.get("certificationCurrent"):
        return unavailable("certification run does not belong to this code", now_iso, deployment_version=deployment_version)
    if not deployed_commit or not g["sourceCommit"].startswith(deployed_commit):
        return unavailable("projection commit does not match the deployed commit", now_iso, deployment_version=deployment_version)
    return {**doc, "state": "AVAILABLE", "checkedAt": now_iso,
            "publishedBy": {"component": "brain-orchestrator", "deploymentVersion": deployment_version}}


def load_staged(base_dir: str) -> dict | None:
    p = os.path.join(base_dir, STAGED_FILE)
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"schema": "unreadable"}                            # -> UNAVAILABLE "projection rejected"


def deployed_commit(deployment_version: str | None) -> str | None:
    """`brain-orchestrator@<12-hex commit>` (deploy-job.sh DEPLOYMENT_VERSION) -> the commit prefix."""
    m = re.search(r"@([0-9a-f]{7,40})$", deployment_version or "")
    return m.group(1) if m else None
