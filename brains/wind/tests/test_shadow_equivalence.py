"""Wind 7-day shadow equivalence, PREPARED (not started): the per-run evidence and the window verifier. Local only, no network, no live system."""
import copy
import datetime as dt
import importlib.util
import json
import os
import re

import pytest

from sector_wind.brain import contract as C
from sector_wind.brain import shadow_equivalence as SE
from sector_wind.brain.publish import publish
from sector_wind.brain.writer import DryRunWriter
from sector_brain_platform.publisher.storage import MemoryObjectStore
from test_brain import CFG, DIRECTORY, NOW, make_store

HERE = os.path.dirname(os.path.abspath(__file__))
WIND = os.path.dirname(HERE)
SHADOW = os.path.join(WIND, "deploy", "shadow-equivalence")
_spec = importlib.util.spec_from_file_location("verify_shadow_equivalence", os.path.join(SHADOW, "verify_shadow_equivalence.py"))
V = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(V)
CFG7 = json.load(open(os.path.join(SHADOW, "shadow-equivalence-7day.json"), encoding="utf-8"))
RUN_AT = C.iso(NOW)


def _view(v):
    """What RTDB would return for a stored value (null keys and empty containers vanish)."""
    if isinstance(v, dict):
        return {k: x for k, x in ((k, _view(x)) for k, x in v.items()) if x not in (None, {}, [])} or None
    if isinstance(v, list):
        return [x for x in (_view(i) for i in v) if x not in (None, {}, [])] or None
    return v


def _get_from(tree):
    def get(key):
        node = tree
        for p in key.strip("/").split("/"):
            if not isinstance(node, dict) or p not in node:
                return None
            node = node[p]
        return _view(copy.deepcopy(node))
    return get


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    inner = DryRunWriter()
    w = SE.RecordingWriter(inner)
    rep = publish(make_store(tmp_path_factory.mktemp("s")), CFG, w, now=NOW, run_summary={"runAt": RUN_AT, "errors": [], "seconds": 90}, directory=DIRECTORY)
    assert rep["ok"], rep["errors"]
    return w, inner


def test_the_recording_writer_changes_nothing_about_the_legacy_write(run):
    w, inner = run
    assert w.patches == [p for p in inner.patches if p] and len(w.patches) > 0


def test_a_faithful_legacy_write_is_equivalent_with_only_expected_differences(run):
    w, inner = run
    rec = SE.evaluate_run(w.patches, _get_from(inner.tree), run_at=RUN_AT, code_version="test@1", execution_id="00000000-0000-4000-8000-000000000001")
    assert rec["verdict"] == "EQUIVALENT_WITH_EXPECTED_DIFFS" and rec["blocking"] == [] and rec["readback"]["errors"] == []
    assert set(rec["openCompatibilityRules"]) <= set(CFG7["pass"]["allowedOpenCompatibilityRules"])


def test_a_stored_value_that_differs_from_the_plan_is_not_equivalent(run):
    w, inner = run
    tree = copy.deepcopy(inner.tree)
    lake = next(iter(tree["lakes"]))
    tree["lakes"][lake]["states"]["wind"]["sustainedMph"] = 99.9
    rec = SE.evaluate_run(w.patches, _get_from(tree), run_at=RUN_AT, code_version="test@1")
    assert rec["verdict"] == "NOT_EQUIVALENT" and "SEMANTIC_MISMATCH" in rec["blocking"]


def test_a_failed_readback_is_an_error_never_equivalent(run):
    w, _ = run
    def broken(key):
        raise OSError("unreachable")
    assert SE.evaluate_run(w.patches, broken, run_at=RUN_AT, code_version="test@1")["verdict"] == "ERROR"
    assert SE.evaluate_run([], broken, run_at=RUN_AT, code_version="test@1")["verdict"] == "NO_LEGACY_WRITE"


def test_evidence_is_digest_only_create_only_and_the_hook_never_raises(run):
    w, inner = run
    rec = SE.evaluate_run(w.patches, _get_from(inner.tree), run_at=RUN_AT, code_version="test@1")
    text = json.dumps(rec)
    assert "sustainedMph" not in text and "gustMph" not in text                             # values never leave the database: paths, classes and digests only
    st = MemoryObjectStore()
    key = SE.store_evidence(st, rec)
    assert key.startswith(SE.PREFIX)
    with pytest.raises(Exception):
        SE.store_evidence(st, rec)                                                          # create-only
    class Broken:
        def put(self, *a, **k):
            raise PermissionError("denied")
    out = SE.safe_record(w, Broken(), now=NOW, code_version="test@1")
    assert out["stored"] is False and "denied" in out["error"]


def test_wind_hourly_records_nothing_unless_the_flag_and_a_bucket_are_deployed():
    src = open(os.path.join(WIND, "runtime", "main.py"), encoding="utf-8").read()
    assert 'os.environ.get("WIND_SHADOW_EQUIVALENCE") == "on" and os.environ.get("WIND_SHADOW_EVIDENCE_BUCKET")' in src
    assert src.index("RecordingWriter(writer)") > src.index("if shadow:")
    sh = open(os.path.join(WIND, "deploy", "deploy-job.sh"), encoding="utf-8").read()
    assert 'WIND_SHADOW_EQUIVALENCE="${WIND_SHADOW_EQUIVALENCE:-off}"' in sh
    assert CFG7["status"] == "PREPARED_NOT_STARTED" and CFG7["approvalRef"] is None


# ------------------------------------------------------------------------------------------------------------- the 7-day verifier
def _rec(t, verdict="EQUIVALENT_WITH_EXPECTED_DIFFS", rules=("health-jobs-wind-hourly",)):
    return {"schema": SE.SCHEMA, "brainId": "wind", "runAt": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "verdict": verdict, "openCompatibilityRules": list(rules), "codeVersion": "c1"}


def _hours(n, start=dt.datetime(2026, 11, 1, 0, 5, tzinfo=dt.timezone.utc), skip=()):
    return [_rec(start + dt.timedelta(hours=h)) for h in range(n) if h not in skip]


def test_seven_full_days_of_equivalent_runs_pass():
    assert V.verify(_hours(24 * 7 + 1), CFG7)["verdict"] == "PASS"


def test_too_short_too_sparse_or_gapped_windows_are_insufficient():
    assert V.verify(_hours(24 * 6), CFG7)["verdict"] == "INSUFFICIENT"
    assert V.verify(_hours(24 * 7 + 1, skip=set(range(10, 60, 2))), CFG7)["verdict"] == "INSUFFICIENT"       # coverage < 90 %
    assert V.verify(_hours(24 * 7 + 1, skip=set(range(50, 58))), CFG7)["verdict"] == "INSUFFICIENT"          # 9 h gap > 6 h
    assert V.verify([], CFG7)["verdict"] == "INSUFFICIENT"


def test_any_non_equivalent_or_error_run_or_unexpected_rule_fails():
    recs = _hours(24 * 7 + 1)
    recs[30] = _rec(dt.datetime(2026, 11, 2, 6, 5, tzinfo=dt.timezone.utc), "NOT_EQUIVALENT")
    assert V.verify(recs, CFG7)["verdict"] == "FAIL"
    recs = _hours(24 * 7 + 1); recs[5]["verdict"] = "ERROR"
    assert V.verify(recs, CFG7)["verdict"] == "FAIL"
    recs = _hours(24 * 7 + 1); recs[7]["openCompatibilityRules"] = ["snapshot-copy-wind"]
    assert V.verify(recs, CFG7)["problems"][0]["kind"] == "UNEXPECTED_OPEN_RULES"


def test_the_verifier_reads_a_directory_and_exits_zero_only_on_pass(tmp_path):
    for r in _hours(24 * 7 + 1):
        (tmp_path / f"{r['runAt'].replace(':', '')}.json").write_text(json.dumps(r))
    assert V.main(["--evidence", str(tmp_path)]) == 0
    assert V.main(["--evidence", str(tmp_path), "--until", "2026-11-03T00:00:00Z"]) == 1
