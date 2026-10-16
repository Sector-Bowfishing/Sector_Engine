"""Read-mostly Google Cloud clients for the platform writer: Cloud Scheduler (list), Cloud Run Jobs / executions
(list) and one write — `run_job()` — used by the Orchestrator and the satellite dispatcher to start a job.

stdlib only (urllib) so jobs can vendor the package. Tokens come from `TokenProvider` (metadata server on Cloud
Run, gcloud locally). Nothing here reads secrets, env values or service-account identities into records.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .rtdb import TokenProvider

PROJECT = "sector-9393c"
REGION = "us-central1"
RUN_V1 = "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1"
RUN_V2 = "https://run.googleapis.com/v2"
SCHEDULER_V1 = "https://cloudscheduler.googleapis.com/v1"


class GcpError(RuntimeError):
    pass


def _call(method: str, url: str, tokens: TokenProvider, body: dict | None = None, timeout: float = 30.0):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {tokens.token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        raise GcpError(f"{method} {url.split('?')[0]} -> {e.code}: {e.read().decode(errors='replace')[:200]}") from e
    except urllib.error.URLError as e:
        raise GcpError(f"{method} {url.split('?')[0]}: {e}") from e


def list_scheduler_jobs(tokens: TokenProvider, project: str = PROJECT, region: str = REGION) -> list[dict]:
    out, token = [], None
    while True:
        q = {"pageSize": 100, **({"pageToken": token} if token else {})}
        d = _call("GET", f"{SCHEDULER_V1}/projects/{project}/locations/{region}/jobs?{urllib.parse.urlencode(q)}", tokens)
        out += d.get("jobs") or []
        token = d.get("nextPageToken")
        if not token:
            return out


def list_run_jobs(tokens: TokenProvider, project: str = PROJECT, region: str = REGION) -> list[dict]:
    d = _call("GET", f"{RUN_V1}/namespaces/{project}/jobs?limit=200", tokens)
    return d.get("items") or []


def list_executions(tokens: TokenProvider, job: str, limit: int = 20, project: str = PROJECT) -> list[dict]:
    q = urllib.parse.urlencode({"labelSelector": f"run.googleapis.com/job={job}", "limit": limit})
    d = _call("GET", f"{RUN_V1}/namespaces/{project}/executions?{q}", tokens)
    return d.get("items") or []


def get_service(tokens: TokenProvider, service: str, project: str = PROJECT) -> dict | None:
    try:
        return _call("GET", f"{RUN_V1}/namespaces/{project}/services/{service}", tokens)
    except GcpError as e:
        if "-> 404" in str(e):
            return None
        raise


def running_executions(executions: list[dict]) -> list[str]:
    return [(e.get("metadata") or {}).get("name", "?") for e in executions if not (e.get("status") or {}).get("completionTime")]


def run_job(tokens: TokenProvider, job: str, args: list[str] | None = None, task_count: int | None = None,
            project: str = PROJECT, region: str = REGION) -> dict:
    """Start a Cloud Run job (v2 `jobs.run`) with optional container-arg / task-count overrides. Returns the operation;
    the execution name is in `metadata.name`."""
    body: dict = {}
    if args is not None or task_count is not None:
        ov: dict = {}
        if args is not None:
            ov["containerOverrides"] = [{"args": list(args)}]
        if task_count is not None:
            ov["taskCount"] = int(task_count)
        body["overrides"] = ov
    return _call("POST", f"{RUN_V2}/projects/{project}/locations/{region}/jobs/{job}:run", tokens, body, timeout=60)
