"""Wind certification refresh gate: only newer, eligible live-reliability evidence refreshes automatically; everything else is HELD;
other frozen entries stay byte-identical; history is append-only."""
import copy
import datetime as dt
import json
import os

import pytest

from sector_brain_platform import wind_score_refresh as R

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FROZEN_PATH = os.path.join(ROOT, "docs", "brains", "scoring", "frozen-scores.json")
CUR = json.load(open(FROZEN_PATH))["wind"]
NOW = dt.datetime(2026, 10, 20, 6, 0, tzinfo=dt.timezone.utc)


def candidate(days=11, through="2026-10-20T05:00:00Z"):
    """The block the canonical generator would emit with more valid live days (same rubric arithmetic as scoreboard.dim8)."""
    c = copy.deepcopy(CUR)
    d = c["scoreBreakdown"]["Freshness/reliability"]
    credit = days / 30
    d["value"] = round(10 * credit, 2); d["points"] = round(8 * credit, 2)
    d["evidence"] = d["evidence"].replace("5/30", f"{days}/30")
    c["rawPoints"] = round(sum(v["points"] for v in c["scoreBreakdown"].values()), 2)
    c["uncapped"] = round(c["rawPoints"] / 10, 2)
    c["value"] = round(min([c["uncapped"]] + [b["cap"] for b in c["scoreBlockers"] if "cap" in b]), 1)
    c["scoreUpdatedAt"] = through
    c["evidence"] = {**c["evidence"], "metadataThrough": through, "validArchiveDays": days}
    return c


def test_current_block_reproduces_itself():
    assert R.reproduce(CUR) == []


def test_newer_reliability_evidence_is_accepted():
    c = candidate()
    r = R.admit(CUR, c, NOW)
    assert r["decision"] == "ACCEPT" and r["moved"] == ["Freshness/reliability"]
    assert r["old"]["value"] == 3.3 and r["new"]["value"] == 3.4          # 34.25 raw, as the Oct 19 audit computed for 11 days


def test_unchanged_is_no_change():
    c = copy.deepcopy(CUR)
    c["evidence"] = {**c["evidence"], "metadataThrough": "2026-10-20T05:00:00Z"}
    assert R.admit(CUR, c, NOW)["decision"] == "NO_CHANGE"


@pytest.mark.parametrize("mutate,why", [
    (lambda c: c.update(scoreVersion="wind-certification-rubric-v2"), "rubric must stay"),
    (lambda c: c.update(basis="HYPOTHETICAL"), "basis"),
    (lambda c: c.update(note="hypothetical S4 simulation"), "hypothetical"),
    (lambda c: c.update(value=5.0), "arithmetic"),
    (lambda c: c["scoreBreakdown"]["Exposure (field)"].update(value=5.0, points=10.0) or c.update(rawPoints=c["rawPoints"] + 10,
                                                                                                   uncapped=round((c["rawPoints"] + 10) / 10, 2),
                                                                                                   value=round((c["rawPoints"] + 10) / 10, 1)), "certification review"),
    (lambda c: c["scoreBreakdown"]["Wind speed"].update(weight=20), "weight"),
    (lambda c: c["evidence"].update(evidenceFileSha="ffff"), "skill evidence file changed"),
    (lambda c: c["evidence"].update(metadataThrough="2026-10-13T21:00:00Z"), "not newer"),
    (lambda c: c["evidence"].update(metadataThrough="2026-10-17T00:00:00Z"), "stale"),
    (lambda c: c["evidence"].update(validArchiveDays=3), "fell"),
    (lambda c: c["evidence"].pop("scorerCode"), "scorerCode missing"),
])
def test_ineligible_candidates_are_held(mutate, why):
    c = candidate(); mutate(c)
    r = R.admit(CUR, c, NOW)
    assert r["decision"] == "HOLD" and any(why in x for x in r["reasons"]), r["reasons"]


def test_h2_note_before_unseal():
    c = candidate(); c["evidence"]["evidenceFileSha"] = "ffff"
    assert any("H2 sealed" in x for x in R.admit(CUR, c, NOW)["reasons"])


def test_refresh_write_splices_wind_only_and_appends_history(tmp_path):
    fz, hist = tmp_path / "frozen.json", tmp_path / "hist.jsonl"
    raw = open(FROZEN_PATH).read()
    fz.write_text(raw)
    line = R.refresh(str(fz), str(hist), candidate(), NOW, write=False)
    assert line["decision"] == "ACCEPT" and fz.read_text() == raw and not hist.exists()          # dry run writes nothing
    line = R.refresh(str(fz), str(hist), candidate(), NOW, write=True)
    after = json.loads(fz.read_text())
    assert after["wind"]["value"] == 3.4
    assert {k: v for k, v in after.items() if k != "wind"} == {k: v for k, v in json.loads(raw).items() if k != "wind"}
    i, j = raw.index('"water-temp"'), raw.index('"wind": {')
    assert fz.read_text()[i:j] == raw[i:j]                                                   # other entries byte-identical
    held = R.refresh(str(fz), str(hist), candidate(days=2, through="2026-10-20T05:30:00Z"), NOW, write=True)
    assert held["decision"] == "HOLD" and json.loads(fz.read_text())["wind"]["value"] == 3.4   # HOLD never touches the block
    lines = [json.loads(x) for x in hist.read_text().splitlines()]
    assert [x["decision"] for x in lines] == ["ACCEPT", "HOLD"] and lines[1]["previousEvaluationId"] == lines[0]["evaluationId"]


def test_repository_frozen_block_untouched_by_tests():
    assert json.load(open(FROZEN_PATH))["wind"]["value"] == 3.3
