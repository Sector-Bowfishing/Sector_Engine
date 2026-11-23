"""The DRAFT rubrics for the Weather, Moon and Generation Brains (docs/brains/scoring/*-score-v1.json, status DRAFT) are not loaded by the
scorer. Adopting a rubric or changing a score is the owner's approval (Cortex sector/engine PROJECT.md section 7); until a rubric's status
changes, nothing here may compute, publish or explain a score for these Brains. When one is adopted, its adoption PR changes this test."""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import score_brains  # noqa: E402
from score_brains import UPSTREAM, compute  # noqa: E402

SCORING = os.path.join(ROOT, "docs", "brains", "scoring")
DRAFTS = {"weather": "weather-score-v1", "moon": "moon-score-v1", "generation": "generation-score-v1"}
SCORER_CODE = [os.path.join(ROOT, "jobs", "brain-scores"), os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform"),
               os.path.join(ROOT, "jobs", "brain-orchestrator")]
NOW = dt.datetime(2026, 11, 23, tzinfo=dt.timezone.utc)


def _draft(version):
    with open(os.path.join(SCORING, f"{version}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_drafts_are_marked_draft_and_unadopted():
    for brain, version in DRAFTS.items():
        d = _draft(version)
        assert d["brainId"] == brain and d["scoreVersion"] == version
        assert d["status"] == "DRAFT" and d["adopted"] is False
        assert d["adoption"]["approvedBy"] is None and d["adoption"]["approvedAt"] is None
        assert sum(x["weight"] for x in d["dimensions"]) == 100


def test_draft_brains_are_not_scored_by_the_publisher():
    assert not set(DRAFTS) & set(UPSTREAM)
    facts = {"lake": {}, "biological": {}, "intelligence": {}}
    assert set(compute(facts, NOW)) == set(UPSTREAM)


def test_no_frozen_score_and_no_improvement_entries_for_draft_brains():
    with open(os.path.join(SCORING, "frozen-scores.json"), encoding="utf-8") as fh:
        assert not set(DRAFTS) & set(json.load(fh))
    with open(os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform", "score_improvements_v1.json"), encoding="utf-8") as fh:
        assert not set(DRAFTS) & set(json.load(fh)["brains"])


def test_no_scorer_code_names_a_draft_rubric():
    offenders = []
    for base in SCORER_CODE:
        for dirpath, _, files in os.walk(base):
            for f in files:
                if not f.endswith(".py") or f == os.path.basename(__file__):
                    continue
                p = os.path.join(dirpath, f)
                with open(p, encoding="utf-8") as fh:
                    text = fh.read()
                offenders += [f"{os.path.relpath(p, ROOT)}: {v}" for v in DRAFTS.values() if v in text]
    assert offenders == []
    assert score_brains.FROZEN.endswith("frozen-scores.json")
