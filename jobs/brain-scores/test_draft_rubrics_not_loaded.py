"""The DRAFT rubrics for the Weather, Moon and Generation Brains (docs/brains/scoring/drafts/*-score-v1.json, status DRAFT) are not loaded by
the scorer. Adopting a rubric or changing a score is the owner's approval (Cortex sector/engine PROJECT.md section 7); until a rubric's status
changes, nothing here may compute, publish or explain a score for these Brains. When one is adopted, its adoption PR changes this test."""
import builtins
import datetime as dt
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import score_brains  # noqa: E402
from score_brains import UPSTREAM, compute  # noqa: E402
from sector_brain_platform import score_engine, score_explanation  # noqa: E402

SCORING = os.path.join(ROOT, "docs", "brains", "scoring")
DRAFT_DIR = os.path.join(SCORING, "drafts")
DRAFTS = {"weather": "weather-score-v1", "moon": "moon-score-v1", "generation": "generation-score-v1"}
SCORER_CODE = [os.path.join(ROOT, "jobs", "brain-scores"), os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform"),
               os.path.join(ROOT, "jobs", "brain-orchestrator")]
NOW = dt.datetime(2026, 11, 23, tzinfo=dt.timezone.utc)
EMPTY_FACTS = {"lake": {}, "biological": {}, "intelligence": {}}


def _draft(version):
    with open(os.path.join(DRAFT_DIR, f"{version}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_drafts_are_marked_draft_unadopted_and_kept_out_of_the_rubric_directory():
    for brain, version in DRAFTS.items():
        d = _draft(version)
        assert d["brainId"] == brain and d["scoreVersion"] == version
        assert d["status"] == "DRAFT" and d["adopted"] is False
        assert d["adoption"]["approvedBy"] is None and d["adoption"]["approvedAt"] is None
        assert sum(x["weight"] for x in d["dimensions"]) == 100
        assert not os.path.exists(os.path.join(SCORING, f"{version}.json"))      # top level = rubrics the baseline hashes


def test_draft_brains_are_not_scored_by_the_publisher():
    assert not set(DRAFTS) & set(UPSTREAM)
    assert set(compute(EMPTY_FACTS, NOW)) == set(UPSTREAM)


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


def test_scores_engine_score_and_explanations_do_not_read_the_scoring_directory(monkeypatch):
    """Record every file opened and every directory listed while the scorer computes all scores, the Engine score and every explanation:
    nothing under drafts/ is opened and the scoring directory is never listed, so no output depends on what that directory contains."""
    opened, listed = [], []
    real_open, real_io_open, real_listdir, real_scandir = builtins.open, io.open, os.listdir, os.scandir

    def rec_open(f, *a, **k):
        opened.append(os.path.abspath(os.fspath(f)) if isinstance(f, (str, bytes, os.PathLike)) else str(f))
        return real_open(f, *a, **k)

    def rec_io_open(f, *a, **k):
        opened.append(os.path.abspath(os.fspath(f)) if isinstance(f, (str, bytes, os.PathLike)) else str(f))
        return real_io_open(f, *a, **k)

    def rec_listdir(p="."):
        listed.append(os.path.abspath(os.fspath(p)))
        return real_listdir(p)

    def rec_scandir(p="."):
        listed.append(os.path.abspath(os.fspath(p)))
        return real_scandir(p)

    monkeypatch.setattr(score_explanation, "_REGISTRY", None)               # force the lazy registry read inside the recording
    monkeypatch.setattr(builtins, "open", rec_open)
    monkeypatch.setattr(io, "open", rec_io_open)
    monkeypatch.setattr(os, "listdir", rec_listdir)
    monkeypatch.setattr(os, "scandir", rec_scandir)
    scores = compute(EMPTY_FACTS, NOW)
    engine = score_engine({}, scores, NOW)
    explanations = {bid: score_explanation.explain(bid, block) for bid, block in scores.items()}
    monkeypatch.undo()

    assert engine["engineScoreVersion"] == "engine-score-v1" and set(explanations) == set(UPSTREAM)
    assert os.path.abspath(score_explanation.REGISTRY_FILE) in opened            # the recorder saw the explanation registry read
    scoring = os.path.abspath(SCORING)
    assert [p for p in opened if p.startswith(os.path.abspath(DRAFT_DIR))] == []
    assert [p for p in listed if p.startswith(scoring)] == []
    assert all(os.path.basename(p) in ("frozen-scores.json",) for p in opened if p.startswith(scoring))
