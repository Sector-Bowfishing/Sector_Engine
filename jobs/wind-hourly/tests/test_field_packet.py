import csv, json, os

import pytest

from sector_wind.brain import field_packet as FP
from sector_wind.brain import field_schema as FS

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "docs", "brains", "wind", "data", "field_pairs_candidates.json")
CAND = {c["lake"]: c for c in json.load(open(DOCS))}


def pairs_for(lake, n=3):
    return [p for p in CAND[lake]["pairs"] if p["type"] == "MIRROR"][:n]


def read(d, f):
    return open(os.path.join(d, f)).read()


def test_packet_is_blinded_and_complete(tmp_path):
    out = tmp_path / "g"
    r = FP.build(CAND["Guntersville|AL"], pairs_for("Guntersville|AL"), "2026-10-20", "mc", str(out), planning_wind={"fromDeg": 225, "mph": 10})
    assert set(r["files"]) == {"MAP-LINKS.txt", "OBSERVER-SHEET.csv", "RECORD-TEMPLATE.json", "SEALED-KEY.json", "SESSION-README.txt"} and r["banks"] == 6
    observer_view = "".join(read(out, f) for f in ("OBSERVER-SHEET.csv", "MAP-LINKS.txt", "SESSION-README.txt"))
    for secret in ("highFetch", "predicted", "HIGH FETCH", "effectiveFetch", "Hm0", "role", "PROTECTED call"):
        assert secret not in observer_view, secret
    sheet_only = read(out, "OBSERVER-SHEET.csv") + read(out, "MAP-LINKS.txt")
    for secret in ("DIRECT", "CROSS", "PROTECTED", "EXPOSED"):            # the vocabulary may appear in the instructions, never as a per-bank hint
        assert secret not in sheet_only.replace("EXPOSED|PROTECTED|UNSURE", ""), secret
    rows = list(csv.DictReader(open(out / "OBSERVER-SHEET.csv")))
    assert [x["bank"] for x in rows] == ["X", "Y"] * 3 and all(x["latitude"] and x["mapLink"].startswith("https://maps.apple.com") for x in rows)
    key = json.load(open(out / "SEALED-KEY.json"))
    assert key["SEALED"] and len(key["banks"]) == 6 and {b["role"] for b in key["banks"]} == {"A", "B"} and all(b["predictedLabel"] for b in key["banks"])
    assert key["planningWind"] == {"fromDeg": 225, "mph": 10} and key["geometryTier"] == "AUDITED"


def test_record_templates_validate_once_filled_and_never_carry_a_prediction(tmp_path):
    out = tmp_path / "h"
    FP.build(CAND["Lake Hartwell|SC"], pairs_for("Lake Hartwell|SC", 2), "2026-10-20", "tester1", str(out), practice=True)
    tpl = json.load(open(out / "RECORD-TEMPLATE.json"))
    assert len(tpl) == 4 and all(t["tags"] == ["practice"] and t["observerSawPrediction"] is False for t in tpl)
    r = dict(tpl[0], observedAtUtc="2026-10-10T20:00:00Z", roughnessObserved="choppy", bankImpactObserved="EXPOSED", boatability="noticeable", observerConfidence=3)
    assert FS.validate_observation(r) == []
    assert "predicted" not in json.dumps(tpl).lower() and "highfetch" not in json.dumps(tpl).lower() and "protected" not in json.dumps(tpl).lower()
    assert "optional on audited" not in read(out, "SESSION-README.txt")          # ESTIMATED lake: only EXPOSED/PROTECTED asked


def test_deterministic_and_the_neutral_order_varies_across_pairs(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        FP.build(CAND["Guntersville|AL"], pairs_for("Guntersville|AL", 6), "2026-10-20", "mc", str(d))
    for f in ("OBSERVER-SHEET.csv", "SEALED-KEY.json", "RECORD-TEMPLATE.json"):
        assert read(a, f) == read(b, f)
    roles_of_x = [x["role"] for x in json.load(open(a / "SEALED-KEY.json"))["banks"] if x["bank"] == "X"]
    assert set(roles_of_x) == {"A", "B"}                                       # X is not always the exposed bank
    c = tmp_path / "c"; FP.build(CAND["Guntersville|AL"], pairs_for("Guntersville|AL", 6), "2026-10-21", "mc", str(c))
    assert read(a, "SEALED-KEY.json") != read(c, "SEALED-KEY.json")


def test_every_candidate_lake_can_be_packaged(tmp_path):
    for i, (lake, c) in enumerate(CAND.items()):
        if c["pairs"]:
            r = FP.build(c, c["pairs"][:2], "2026-10-20", "t", str(tmp_path / f"l{i}"))
            assert r["banks"] == 4
