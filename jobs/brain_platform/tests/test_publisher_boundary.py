"""The shadow guarantee (requirement 16): the Publisher cannot reach a live database, by construction, and tests prove it rather than comment on it."""
import ast
import os
import re
import socket
import subprocess
import sys
import urllib.request

import pytest

from publisher_fixtures import make, wind_artifact
from sector_brain_platform import DryRunStore
from sector_brain_platform.publisher import LiveCapabilityRefused, PublisherMode, ShadowPublisher, ShadowSink, default_registry, PublishHistory, MemoryObjectStore, Result
from sector_brain_platform.publisher import api as api_mod

PKG = os.path.join(os.path.dirname(__file__), "..", "sector_brain_platform", "publisher")
FORBIDDEN_IMPORTS = {"urllib", "urllib.request", "http", "http.client", "socket", "ssl", "subprocess", "requests", "httpx", "aiohttp", "firebase_admin", "google",
                     "boto3", "os", "shutil"}
FORBIDDEN_SIBLINGS = {"rtdb", "gcp", "jobs", "control", "control_state", "orchestration", "orchestrator", "failure"}      # the live-write / cloud-start modules


def _imports(path):
    tree = ast.parse(open(path).read())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mod = ("." * n.level) + (n.module or "")
            out.add(mod)
            if n.level == 2 and n.module is None:
                out |= {".." + a.name for a in n.names}
    return out


def _modules():
    return [f for f in sorted(os.listdir(PKG)) if f.endswith(".py")]


def test_no_publisher_module_imports_a_network_process_credential_or_live_write_module():
    bad = []
    for f in _modules():
        for imp in _imports(os.path.join(PKG, f)):
            root = imp.lstrip(".")
            if imp.startswith("..") and root.split(".")[0] in FORBIDDEN_SIBLINGS:
                bad.append((f, imp))
            if not imp.startswith(".") and (imp in FORBIDDEN_IMPORTS or imp.split(".")[0] in FORBIDDEN_IMPORTS):
                bad.append((f, imp))
    assert bad == [], bad


def test_no_publisher_source_mentions_a_live_endpoint_token_or_http_verb_helper():
    needles = ["firebaseio", "sector-brain", "access_token", "BrainRtdb", "TokenProvider", "metadata.google", "gcloud", "urlopen", "PATCH"]
    hits = []
    for f in _modules():
        text = open(os.path.join(PKG, f)).read()
        hits += [(f, n) for n in needles if n in text]
        hits += [(f, "urllib Request(") for _ in re.findall(r"(?<![A-Za-z])Request\(", text)]
    assert hits == [], hits


def test_package_is_not_imported_by_the_platform_package_so_no_production_job_loads_it():
    init = open(os.path.join(PKG, "..", "__init__.py")).read()
    assert "publisher" not in init
    code = "import sys; sys.path.insert(0, %r); import sector_brain_platform; print('sector_brain_platform.publisher' in sys.modules)" % os.path.abspath(os.path.join(PKG, "..", ".."))
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip() == "False"


def test_publisher_mode_has_no_live_member():
    assert set(PublisherMode.__members__) == {"SHADOW", "DRY_RUN"}
    assert {r.name for r in Result} == {"SKIP", "SHADOW_READY", "REJECTED", "FAILED_VALIDATION"}            # and no PUBLISHED


def test_live_capable_objects_cannot_be_injected_as_a_sink():
    hist = PublishHistory(MemoryObjectStore())
    for live_like in (DryRunStore(), object(), lambda *a: None, "sink"):
        with pytest.raises(LiveCapabilityRefused):
            ShadowPublisher(default_registry(), hist, live_like)

    class Sneaky(ShadowSink):
        def update(self, updates):               # a write-shaped method on an otherwise-valid subclass
            raise AssertionError("must never be callable")
    with pytest.raises(LiveCapabilityRefused):
        ShadowPublisher(default_registry(), hist, Sneaky())
    with pytest.raises(TypeError):
        ShadowPublisher(default_registry(), hist, ShadowSink(), mode="SHADOW")


def test_full_shadow_flow_performs_no_network_process_or_socket_activity(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("shadow Publisher attempted live I/O")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    pub, hist, sink = make()
    out = [pub.evaluate(wind_artifact(n=1), producer="wind"), pub.evaluate(wind_artifact(n=2, speed=9.0, minutes=30), producer="wind"),
           pub.evaluate(wind_artifact(n=3, lifecycle="PRODUCTION", minutes=40), producer="wind")]
    assert [r.result.value for r in out] == ["SHADOW_READY", "SHADOW_READY", "REJECTED"]
    assert sink.live_mutations == 0 and all(r.live_mutations == 0 for r in out) and ShadowSink.live is False


def test_the_environment_cannot_switch_the_publisher_to_live(monkeypatch):
    for k, v in (("BRAIN_WRITE", "1"), ("PUBLISHER_LIVE", "true"), ("BRAIN_ACCESS_TOKEN", "x"), ("CLOUD_RUN_JOB", "wind-hourly"), ("SECTOR_PUBLISH_LIVE", "1")):
        monkeypatch.setenv(k, v)
    pub, _, sink = make()
    assert pub.evaluate(wind_artifact(), producer="wind").live_mutations == 0
    assert not any(callable(getattr(sink, n, None)) for n in ("update", "patch", "put", "set", "delete", "write", "commit"))


def test_shadow_plan_is_data_only_and_json_serialisable():
    import json
    r = make()[0].evaluate(wind_artifact(), producer="wind")
    json.dumps(r.plan.updates)
    assert not callable(r.plan.updates) and type(r.plan.updates) is dict


def test_api_module_has_no_database_client_or_publisher_write_path():
    imps = _imports(os.path.join(PKG, "api.py"))
    assert not {i for i in imps if i.lstrip(".").split(".")[0] in {"rtdb", "storage", "sinks", "publisher", "plan", "gcp", "jobs"} | FORBIDDEN_IMPORTS}, imps
    assert api_mod.API_VERSION == "orchestrator-api-v1"
