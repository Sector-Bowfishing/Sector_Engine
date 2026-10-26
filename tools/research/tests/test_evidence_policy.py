"""Evidence policy (owner directive 2026-10-26): owner-collected field data is OPTIONAL, never mandatory, in the Brain gap lists, the research automation and the
templates every future Brain is created from. Existing observations still count as evidence; nothing here fabricates validation."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import discovery as D  # noqa: E402
import evidence_policy as EP  # noqa: E402
import ledger as L  # noqa: E402


def _gap_files():
    return sorted(glob.glob(os.path.join(REPO, "brains", "*", "research", "GAPS*.json")))


def test_policy_declares_field_data_optional():
    p = EP.load()
    assert p["mandatoryFieldTesting"] is False and p["fieldDataRole"] == "OPTIONAL_EVIDENCE"
    assert {"independent-historical-holdout", "public-dataset-comparison", "literature-synthesis", "reproducible-analysis"} <= set(EP.validation_methods())


def test_recognises_owner_collected_data_but_not_existing_records():
    for t in ("24 site-nights", "collect with a handheld anemometer", "sonar transects at the pilot lake", "bowfishing trip logs", "owner declines the field campaign", "no field outcomes: no species is validated"):
        assert EP.is_owner_collected(t), t
    for t in ("USGS LTRM day/night electrofishing", "state agency creel surveys", "NOAA NDBC buoy archive", "TWDB effective zones", "USACE eHydro survey footprint", "public ArcGIS feature service for dated survey footprints"):
        assert not EP.is_owner_collected(t), t


def test_no_brain_or_template_gap_requires_owner_field_data():
    files = _gap_files()
    assert len(files) >= 9                                           # eight Brains and the template every future Brain starts from
    for f in files:
        for g in json.load(open(f))["gaps"]:
            h = g.get("humanOrFieldValidationRequired") or {}
            assert not (h.get("required") and EP.is_owner_collected(h.get("what"))), (f, g["id"])
            assert not EP.is_owner_collected(g.get("stopCondition")), (f, g["id"], "stop condition depends on owner-collected data")
            assert not EP.is_owner_collected(g.get("title")) or "need" not in g["title"].lower(), (f, g["id"])


def test_the_named_gaps_no_longer_carry_a_field_quota():
    txt = "".join(open(f).read() for f in _gap_files())
    assert "0 of 24 required" not in txt and "0 of 36 required" not in txt
    assert "compared with a field outcome" not in txt


def test_template_gap_inherits_the_rule():
    t = json.load(open(os.path.join(REPO, "brains", "_template", "research", "GAPS.template.json")))["gaps"][0]
    assert t["humanOrFieldValidationRequired"]["required"] is False and t["humanOrFieldValidationRequired"]["fieldDataRole"] == "OPTIONAL_EVIDENCE"


def test_ledger_ignores_owner_collected_blockers_but_keeps_real_ones(tmp_path):
    led = L.Ledger(str(tmp_path / "l.json"), "wind")
    led.sync([{"id": "G1", "title": "t"}, {"id": "G2", "title": "t"}])
    led.block("G1", "external", "paired observations: 24 site-nights", "Sector field collection (owner): handheld anemometer", "c1")
    assert led.status("G1") == "OPEN" and led.doc["gaps"]["G1"]["blockers"] == [] and led.doc["gaps"]["G1"]["optionalData"]
    led.block("G2", "external", "dataset needs a licence agreement", "publisher portal", "c1")
    assert led.status("G2") == "BLOCKED_EXTERNAL"


def test_existing_ledgers_are_migrated_not_deleted(tmp_path):
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"schema": "sector-gap-ledger-v1", "brainId": "wind", "avenues": {}, "evidence": [], "gaps": {
        "G1": {"status": "BLOCKED_EXTERNAL", "blockers": [{"kind": "external", "reason": "24 site-nights", "nextEvidenceSource": "Sector field collection (owner)"}]},
        "G2": {"status": "BLOCKED_EXTERNAL", "blockers": [{"kind": "external", "reason": "24 site-nights", "nextEvidenceSource": "x"},
                                                           {"kind": "external", "reason": "needs licence", "nextEvidenceSource": "portal"}]}}}))
    led = L.Ledger(str(p), "wind")
    assert led.status("G1") == "INVESTIGATING" and led.doc["gaps"]["G1"]["optionalData"][0]["reason"] == "24 site-nights"
    assert led.status("G2") == "BLOCKED_EXTERNAL" and len(led.doc["gaps"]["G2"]["blockers"]) == 1


def test_owner_action_for_field_collection_is_optional_and_non_blocking(tmp_path):
    rec = D.owner_action(str(tmp_path), "wind-brain", "c1", "wind-bank-site-nights", "WIND-VAL-001", "Sector field collection (owner)", "24 site-nights",
                         "handheld anemometer", False, [], "exposure ordering")
    assert rec["status"] == "OPTIONAL_OWNER_DATA" and rec["blocksResearch"] is False
    rec = D.owner_action(str(tmp_path), "wind-brain", "c1", "agency-x", "WIND-EVI-001", "Agency X", "a cache of the private clarity root", "restore from the private backup", False, [], "x")
    assert rec["status"] == "OWNER_ACTION_REQUIRED" and rec["blocksResearch"] is True


def test_agent_briefs_carry_the_policy():
    import campaign as C
    assert "EVIDENCE POLICY" in C.result_prompt({"id": "T1"}, {}, "/tmp/r.json")
