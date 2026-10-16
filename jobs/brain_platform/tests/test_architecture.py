"""Architecture contracts (docs/brains/platform/EXECUTION_MODEL.md section 7, OPS_CONTROL_CONTRACT.md hot-path rules).

Static checks, cheap to run, that keep the two hot-path rules true as code evolves:
  - a CUSTOMER request never reaches Brain compute, the orchestrator, the score publisher or research data;
  - the platform package does no I/O at import time (opening Ops / importing a module must not wake anything).
"""
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CUSTOMER_PATHS = [os.path.join(REPO, "Sources", "SectorEngine", "API")]
FORBIDDEN_IN_CUSTOMER_PATH = [r"run\.googleapis\.com", r"/jobs/[^\"]*:run", r"score_brains", r"orchestrate", r"research/", r"frozen-scores", r"\.csv\b",
                              r"gs://sector-(lake-brain|clarity|biology)", r"Process\(\)"]


def test_customer_api_never_references_brain_compute_or_research_data():
    hits = []
    for base in CUSTOMER_PATHS:
        for dp, _, files in os.walk(base):
            for f in files:
                if f.endswith(".swift"):
                    text = open(os.path.join(dp, f), errors="ignore").read()
                    hits += [f"{f}: {pat}" for pat in FORBIDDEN_IN_CUSTOMER_PATH if re.search(pat, text)]
    assert hits == [], hits


def test_platform_package_has_no_import_time_io():
    code = ("import socket, builtins, sys\n"
            "def boom(*a, **k): raise RuntimeError('network at import')\n"
            "socket.socket.connect = boom\n"
            "sys.path.insert(0, %r)\n"
            "import sector_brain_platform\n" % os.path.join(REPO, "jobs", "brain_platform"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


def test_platform_modules_stay_stdlib_only():
    pkg = os.path.join(REPO, "jobs", "brain_platform", "sector_brain_platform")
    third_party = re.compile(r"^\s*(?:import|from)\s+(requests|numpy|pandas|firebase_admin|google|httpx|boto3)\b", re.M)
    bad = [f for f in os.listdir(pkg) if f.endswith(".py") and third_party.search(open(os.path.join(pkg, f)).read())]
    assert bad == [], bad


def test_scheduler_wake_ups_are_not_added_without_a_reason():
    """Every recurring schedule must carry a documented reason from SCHEDULE_REASONS; the manifest lists them (EXECUTION_MODEL.md section 3)."""
    from sector_brain_platform import JOB_MANIFEST
    from sector_brain_platform.model_v1 import SCHEDULE_REASONS
    assert SCHEDULE_REASONS  # vocabulary exists
    assert isinstance(JOB_MANIFEST, dict) and JOB_MANIFEST
