"""Wind measurements activation switch: OFF unless the job runs with WIND_MEASUREMENTS=on; the image stages every input the
evaluator reads, and in that image layout the scorer attaches the measurements without touching the certification score."""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import orchestrate as o  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEPLOY = open(os.path.join(HERE, "..", "deploy-job.sh")).read()
READS = ("docs/brains/scoring/wind-specialist-capability-v2.json", "docs/brains/scoring/evidence/wind-measurements-evidence.json")


def test_switch_defaults_off():
    assert "--wind-measurements" not in o.score_cmd({})
    for v in ("off", "1", "true", "ON", "yes"):
        assert "--wind-measurements" not in o.score_cmd({"WIND_MEASUREMENTS": v})
    cmd = o.score_cmd({"WIND_MEASUREMENTS": "on"})
    assert cmd[-3:] == ["--write", "--if-changed", "--wind-measurements"] and cmd[1].endswith("score_brains.py")


def test_deploy_defaults_off_and_passes_the_switch():
    assert 'WIND_MEASUREMENTS="${WIND_MEASUREMENTS:-off}"' in DEPLOY
    assert "WIND_MEASUREMENTS=$WIND_MEASUREMENTS" in DEPLOY.split("--set-env-vars", 1)[1].split("\n", 1)[0]
    assert 'must be on or off' in DEPLOY


def test_deploy_stages_every_input_the_evaluator_reads():
    sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
    from sector_brain_platform import wind_measurements as W
    read = {os.path.relpath(p, W.ROOT) for p in (W.RUBRIC_PATH, W.EVIDENCE_PATH)}
    assert read == set(READS)
    assert os.path.relpath(W.BRAIN_JSON, W.ROOT) == "brains/wind/brain.json" and 'cp "$b/brain.json"' in DEPLOY


def test_image_layout_attaches_measurements(tmp_path):
    """Mirror the staged layout for the scorer (deploy-job.sh 'stage the repo layout') and run the real attach there."""
    for rel in READS:
        assert f'"$ROOT/{rel}"' in DEPLOY, rel
    stage = tmp_path / "stage"
    shutil.copytree(os.path.join(ROOT, "jobs", "brain_platform"), stage / "jobs" / "brain_platform", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (stage / "jobs" / "brain-scores").mkdir(parents=True)
    shutil.copy(os.path.join(ROOT, "jobs", "brain-scores", "score_brains.py"), stage / "jobs" / "brain-scores")
    for rel in ("docs/brains/scoring/frozen-scores.json",) + READS + ("brains/wind/brain.json",):
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), stage / rel)
    code = """
import json, sys, datetime as dt
sys.path.insert(0, '.')
import score_brains
from sector_brain_platform import frozen_score
fr = score_brains.rtdb_safe(json.load(open(score_brains.FROZEN)))
s = {b: {'value': 1.0, 'scale': 10, 'basis': 'COMPUTED', 'scoreVersion': 'v1', 'scoreBreakdown': {}, 'scoreBlockers': []} for b in score_brains.UPSTREAM}
s['wind'] = frozen_score(fr['wind'])
w = score_brains.attach_wind_measurements(s, {'health': {}}, dt.datetime(2026, 10, 19, 22, tzinfo=dt.timezone.utc))['wind']
m = w['measurements']
print(json.dumps({'value': w['value'], 'cap': m['windCapability']['value'], 'status': m['windCapability']['rubricStatus'],
                  'sc': m['scientificConfidence']['overall'], 'pr': m['productionReadiness']['overall'], 'consistency': m.get('consistency', [])}))
"""
    r = subprocess.run([sys.executable, "-c", code], cwd=stage / "jobs" / "brain-scores", capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"value": 3.3, "cap": 6.7, "status": "ADOPTED", "sc": "LIMITED", "pr": "NOT_READY", "consistency": []}


def test_missing_evidence_in_image_is_held_not_attached(tmp_path, capsys):
    sys.path.insert(0, os.path.join(ROOT, "jobs", "brain-scores"))
    import datetime as dt
    import score_brains
    from sector_brain_platform import frozen_score, wind_measurements as W
    real = W.load_all
    W.load_all = lambda: (real()[0], None, real()[2])
    try:
        fr = score_brains.rtdb_safe(json.load(open(score_brains.FROZEN)))
        s = {"wind": frozen_score(fr["wind"])}
        out = score_brains.attach_wind_measurements(s, {"health": {}}, dt.datetime(2026, 10, 19, 22, tzinfo=dt.timezone.utc))
    finally:
        W.load_all = real
    assert "measurements" not in out["wind"] and "HELD" in capsys.readouterr().out
