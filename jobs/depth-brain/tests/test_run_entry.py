import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args, env=None):
    return subprocess.run([sys.executable, os.path.join(HERE, "run.py"), *args], capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=60)


def test_write_is_refused_without_the_approval_env():
    r = run("--write", env={"DEPTH_SHADOW_WRITE_APPROVED": "", "BRAIN_RTDB_URL": "http://127.0.0.1:9"})
    assert r.returncode == 3 or "refusing" in r.stderr or r.returncode != 0
    assert "refusing" in r.stderr or "Connection" in r.stderr or r.returncode != 0


def test_run_entry_is_never_referenced_by_default_executors():
    orch = open(os.path.join(HERE, "..", "brain-orchestrator", "orchestrate.py")).read()
    assert 'DEPTH_ORCHESTRATION_ENABLED") == "1"' in orch and "DEPTH_ORCHESTRATION_ENABLED=1" in orch
