"""Rubric v2 (evidence policy 2026-10-26): dimensions 6-7 accept any pre-declared validation method, v1 is unchanged, nothing is fabricated."""
import json

from sector_wind_research import scoreboard as S

ENTRY = {"exposure": {"n": 40, "concordance": 0.80, "lakes": 2, "quadrants": 3, "sufficient": True},
         "surface": {"n": 60, "exact": 0.60, "within1": 0.90, "severe": 0.05, "sufficient": True}}


def _ledger(tmp_path, **extra):
    p = tmp_path / "certification.jsonl"
    p.write_text(json.dumps({**ENTRY, **extra}) + "\n")
    return [str(p)]


def test_v1_default_is_unchanged(tmp_path):
    d = S.dims_6_7([str(tmp_path / "none*.jsonl")])
    assert d[6]["credit"] == 0 and "no field data" in d[6]["why"]


def test_v2_without_entries_earns_nothing(tmp_path):
    d = S.dims_6_7([str(tmp_path / "none*.jsonl")], rubric="v2")
    assert d[6]["credit"] == 0 and d[7]["credit"] == 0 and "accepted-method" in d[6]["why"]


def test_v2_public_historical_entry_earns_the_same_curves_as_v1(tmp_path):
    v2 = S.dims_6_7(_ledger(tmp_path, method="public-dataset-comparison", predeclared=True), rubric="v2")
    v1 = S.dims_6_7(_ledger(tmp_path))
    assert v2[6]["credit"] == v1[6]["credit"] and v2[7]["credit"] == v1[7]["credit"]
    assert v2[6]["credit"] > 0.99 and v2[7]["credit"] > 0.99


def test_v2_ignores_entries_without_an_accepted_predeclared_method(tmp_path):
    assert S.dims_6_7(_ledger(tmp_path), rubric="v2")[6]["credit"] == 0
    assert S.dims_6_7(_ledger(tmp_path, method="vibes", predeclared=True), rubric="v2")[6]["credit"] == 0
    assert S.dims_6_7(_ledger(tmp_path, method="public-dataset-comparison", predeclared=False), rubric="v2")[6]["credit"] == 0


def test_v2_caps_do_not_demand_field_validation():
    dims = {6: {"credit": 0}, 7: {"credit": 0}}
    assert "accepted method" in S.caps(dims, {"measuredStationComparisons": 1}, "v2")[0]["rule"]
    assert S.caps(dims, {"measuredStationComparisons": 1})[0]["rule"] == "Exposure or surface never field-validated"
