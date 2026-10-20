"""Fish Capability V2 through the real score_brains plan: the capability block is written inside /scores/biological-state with NO
score.changed event (the maturity value is untouched), and the default repository state attaches nothing."""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
import score_brains as sb      # noqa: E402
from sector_brain_platform import fish_capability as fc      # noqa: E402

NOW = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)


def test_capability_change_writes_the_block_without_a_score_changed_event():
    bio = {"value": 5.1, "uncapped": 5.1, "scale": 10, "basis": "COMPUTED", "scoreVersion": "biological-state-score-v1", "scoreBreakdown": {"x": {"value": 1}}}
    old = {b: {"value": 1.0, "scoreVersion": "v"} for b in sb.UPSTREAM}
    new = {b: dict(v) for b, v in old.items()}
    old["biological-state"], new["biological-state"] = dict(bio), {**bio, "capability": {"schema": fc.RESULT_SCHEMA, "evaluationId": "fcap-x"}}
    updates, changed = sb.plan_writes(new, {b: {} for b in sb.UPSTREAM}, NOW, None, None, old)
    assert "scores/biological-state" in updates and updates["scores/biological-state"]["value"] == 5.1
    assert not any(k.startswith("activity/") for k in updates)


def test_default_repository_state_attaches_nothing():
    scores = {"biological-state": {"value": 5.1}}
    out, why = fc.attach_capability(scores, {"brains": {"biological-state": {"researchVersion": "2026-10-17.1"}}}, NOW.isoformat(), {})
    assert "capability" not in out["biological-state"] and "INACTIVE" in why


def test_deploy_stages_every_input_the_hook_reads():
    deploy = open(os.path.join(HERE, "..", "brain-orchestrator", "deploy-job.sh")).read()
    for f in ("fish-biological-capability-v2.json", "fish-capability-cohorts-v2.json", "fish-capability-publication.json", "evidence/fish-capability-evidence.json"):
        assert f.split("/")[-1] in deploy, f
        assert os.path.exists(os.path.join(HERE, "..", "..", "docs", "brains", "scoring", f)), f
