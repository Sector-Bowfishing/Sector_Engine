"""F-9: Wind shadow equivalence evaluator + the F-5/F-6/F-7 legacy path table. Fixtures are synthetic; the evaluator works on in-memory data only."""
import copy
import json

import pytest

from gatep_fixtures import bundle, lake_section, registry_section, source_section
from publisher_fixtures import LAKE_A, LAKE_B
from sector_brain_platform.publisher import default_registry
from sector_brain_platform.publisher.compat import CLASSIFICATIONS, LEGACY_PATH_TABLE, MECHANISMS, row_for
from sector_brain_platform.publisher.equivalence import CLASSES, EVALUATOR, evaluate_equivalence, render_target

REG = default_registry()


def put(tree, path, value):
    parts = path.strip("/").split("/")
    for p in parts[:-1]:
        tree = tree.setdefault(p, {})
    tree[parts[-1]] = copy.deepcopy(value)


def live_from(art, legacy=True, **tweak):
    """A synthetic 'live' tree = what the current writer would have stored for `art`, plus the legacy extras it also writes."""
    t = render_target(art, REG)
    live = {}
    for k, v in t["updates"].items():
        if k != "brains/wind/publication" and v is not None:
            put(live, k, v)
    if legacy:
        for k in (LAKE_A, LAKE_B):
            put(live, f"lakeFleet/{k}/lakeId", k)
            put(live, f"snapshots/{k}/latest/lakeId", k)
        put(live, "health/jobs/wind-hourly", {"status": "HEALTHY", "lastRun": "2026-10-15T03:00:00Z", "kind": "Cloud Run Job"})
        for f, v in (("lastRun", "2026-10-15T03:00:00Z"), ("lastSuccess", "2026-10-15T03:00:00Z"), ("durationMs", 900), ("errorCount", 0), ("deployedVersion", "main@abc")):
            put(live, f"health/brains/wind/{f}", v)
        put(live, "activity/1000-wind-0", {"kind": "brain.version"})
        put(live, "activity/1001-water-temp-0", {"kind": "run.failed"})           # another Brain's event: must not be judged
    for path, v in tweak.items():
        put(live, path, v)
    return live


def ev(live, art):
    t = render_target(art, REG)
    return evaluate_equivalence(live, t["updates"], registry=REG, derived_keys=t["derivedKeys"]), t


def by_class(rep):
    out = {}
    for d in rep["differences"]:
        out.setdefault(d["class"], []).append(d)
    return out


def test_known_differences_are_classified_and_the_verdict_is_equivalent():
    art = bundle(1)
    live = live_from(art, **{"brains/wind/lastSuccessfulRun": "2026-10-14T00:00:00Z", "brains/wind/updatedAt": "2026-10-14T00:00:00Z"})
    rep, _ = ev(live, art)
    c = by_class(rep)
    assert rep["evaluator"] == EVALUATOR and rep["verdict"] == "EQUIVALENT_WITH_EXPECTED_DIFFS" and rep["blocking"] == []
    assert {d["path"] for d in c["VOLATILE_ONLY"]} == {"/brains/wind/lastSuccessfulRun", "/brains/wind/updatedAt", "/health/brains/wind/durationMs"}     # durationMs: shared default
    assert {d["rule"] for d in c["EXPECTED_MIGRATION_DIFF"]} == {"lakefleet-lakeid", "snapshot-lakeid", "PUBLISHER_METADATA", "APPEND_ONLY_HISTORY"}
    assert {d["rule"] for d in c["LEGACY_ONLY"]} == {"health-jobs-wind-hourly", "health-brains-wind-process"} == set(rep["openCompatibilityRules"])
    assert not [d for d in rep["differences"] if "water-temp" in d["path"]]                      # another Brain's activity is out of scope
    assert rep["summary"]["MATCH"] > 10 and set(rep["summary"]) == set(CLASSES) | {"MATCH"}


def test_publisher_metadata_and_derived_projections_are_explained_target_only_or_equal():
    art = bundle(1)
    rep, t = ev(live_from(art, legacy=False), art)
    c = by_class(rep)
    pub = [d for d in c["EXPECTED_MIGRATION_DIFF"] if d["rule"] == "PUBLISHER_METADATA"]
    assert pub and all(d["path"].startswith("/brains/wind/publication") and "liveSha256" not in d for d in pub)
    assert rep["verdict"] == "EQUIVALENT_WITH_EXPECTED_DIFFS" and "SEMANTIC_MISMATCH" not in c and "UNKNOWN" not in c


def test_a_changed_domain_value_is_a_semantic_mismatch_and_blocks():
    art = bundle(1)
    live = live_from(art)
    changed = bundle(2, sections=[lake_section(speed=9.9), registry_section(), source_section()])
    rep, _ = ev(live, changed)
    mm = by_class(rep)["SEMANTIC_MISMATCH"]
    assert rep["verdict"] == "NOT_EQUIVALENT" and "SEMANTIC_MISMATCH" in rep["blocking"]
    assert {d["path"] for d in mm} >= {f"/lakes/{LAKE_A}/states/wind/windMS", f"/snapshots/{LAKE_A}/latest/wind/windMS"}
    assert all("liveSha256" in d and "targetSha256" in d and d["liveSha256"] != d["targetSha256"] for d in mm)


def test_unknown_live_content_is_never_normalised_away():
    art = bundle(1)
    rep, _ = ev(live_from(art, **{"brains/wind/mysteryChild": {"x": 1}, "health/brains/wind/surprise": 7}), art)
    unk = by_class(rep)["UNKNOWN"]
    assert {d["path"] for d in unk} == {"/brains/wind/mysteryChild/x", "/health/brains/wind/surprise"}
    assert rep["verdict"] == "NOT_EQUIVALENT" and "UNKNOWN" in rep["blocking"]


def test_target_only_content_is_reported_and_unexplained_target_only_blocks():
    art = bundle(1)
    live = live_from(art)
    grown = bundle(2, sections=[lake_section(extra=[{"op": "SET", "path": f"/lakes/{LAKE_A}/profiles/wind", "value": {"p": 1}}]), registry_section(), source_section()])
    rep, _ = ev(live, grown)
    to = [d for d in by_class(rep)["TARGET_ONLY"] if not d["explained"]]
    assert to and rep["verdict"] == "NOT_EQUIVALENT" and "TARGET_ONLY" in rep["blocking"]


def test_unit_replacement_that_drops_a_live_key_is_a_semantic_mismatch():
    art = bundle(1)
    live = live_from(art, **{f"lakes/{LAKE_A}/states/wind/extraLiveKey": "kept-today"})
    rep, _ = ev(live, art)
    assert any(d["rule"] == "DROPPED_BY_UNIT_REPLACEMENT" and d["path"].endswith("extraLiveKey") for d in by_class(rep)["SEMANTIC_MISMATCH"])


def test_explicit_delete_is_an_expected_diff_and_domain_truth_missing_is_not():
    art = bundle(1)
    live = live_from(art)
    put(live, f"lakes/{LAKE_B}/validation/wind", {"status": "OLD"})
    deleting = bundle(2, sections=[lake_section(), registry_section(), source_section(),
                                   {"artifactSchema": "wind-lake-state-v1", "scope": "evidence", "freshness": {"freshnessStatus": "UNKNOWN"},
                                    "mutations": [{"op": "DELETE", "path": f"/lakes/{LAKE_B}/validation/wind", "reason": "EVIDENCE_REMOVED"}]}])
    rep, _ = ev(live, deleting)
    assert any(d["rule"] == "EXPLICIT_DELETE" and d["path"] == f"/lakes/{LAKE_B}/validation/wind/status" for d in by_class(rep)["EXPECTED_MIGRATION_DIFF"])
    live2 = live_from(art); put(live2, "health/brains/wind/status", "WARNING"); del live2["health"]["brains"]["wind"]["status"]
    live2["health"]["brains"]["wind"]["staleLakeCount"] = 3
    rep2, _ = ev(live2, bundle(3, sections=[lake_section(), registry_section(), source_section()]))
    assert by_class(rep2)["SEMANTIC_MISMATCH"][0]["path"] == "/health/brains/wind/staleLakeCount"


def test_output_is_machine_readable_deterministic_and_carries_no_raw_values():
    art = bundle(1)
    live = live_from(art, **{"brains/wind/lastSuccessfulRun": "SECRET-LOOKING-LIVE-VALUE"})
    r1, t = ev(live, art)
    shuffled_live = json.loads(json.dumps(live, sort_keys=True))
    shuffled_updates = dict(reversed(list(t["updates"].items())))
    r2 = evaluate_equivalence(shuffled_live, shuffled_updates, registry=REG, derived_keys=tuple(reversed(t["derivedKeys"])))
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    text = json.dumps(r1)
    assert "SECRET-LOOKING-LIVE-VALUE" not in text and "kind" not in {k for d in r1["differences"] for k in d} and "sha256:" in text
    assert [d["path"] for d in r1["differences"]] == sorted(d["path"] for d in r1["differences"])


def test_a_publisher_rejection_yields_no_target_rather_than_a_fake_equivalence():
    bad = bundle(1); bad["sections"][0]["mutations"].append({"op": "SET", "path": "/speciesProfiles/x", "value": {"a": 1}})
    t = render_target(bad, REG)
    assert t["result"] == "REJECTED" and t["updates"] == {} and "CROSS_DOMAIN_PATH" in t["codes"]


# ---------------- legacy path table (F-5 / F-6 / F-7) --------------------------------------------------------------------------------------------
def test_every_row_has_exactly_one_valid_classification_owner_mechanism_and_gate():
    ids = [r.id for r in LEGACY_PATH_TABLE]
    assert len(ids) == len(set(ids))
    for r in LEGACY_PATH_TABLE:
        assert r.classification in CLASSIFICATIONS and r.mechanism in MECHANISMS and r.target_owner and r.retirement_gate and r.current_writer and r.current_readers


def test_platform_owned_and_derived_rows_are_not_authorable_by_wind():
    from publisher_fixtures import make
    for r in LEGACY_PATH_TABLE:
        if r.classification in ("PLATFORM_OWNED", "DERIVED_COMPATIBILITY_PROJECTION"):
            for pat in r.paths:
                if len(pat.strip("/").split("/")) < 2:
                    continue
                path = pat.replace("{k}", LAKE_A).replace("{event}", "x-wind-0")
                if r.id == "activity-wind-events":
                    continue
                sec = {"artifactSchema": "wind-lake-state-v1", "scope": "s", "freshness": {"freshnessStatus": "FRESH"}, "mutations": [{"op": "SET", "path": path, "value": {"x": 1}}]}
                res = make()[0].evaluate(bundle(1, sections=[sec]), producer="wind")
                assert res.is_rejection, (r.id, path)


def test_wind_domain_truth_is_small_and_authorable_and_transitional_rows_are_flagged():
    domain = [r for r in LEGACY_PATH_TABLE if r.classification == "WIND_DOMAIN_TRUTH"]
    assert {r.id for r in domain} == {"health-brains-wind-domain", "activity-wind-events"} and all(r.mechanism == "WIND_AUTHORED" and not r.compat_needed for r in domain)
    assert {r.id for r in LEGACY_PATH_TABLE if r.mechanism == "WIND_AUTHORED_TRANSITIONAL"} == {"registry-updatedat", "registry-lastsuccessfulrun", "registry-lasterror"}
    assert row_for("/health/brains/wind/lastRun").id == "health-brains-wind-process" and row_for("/health/brains/wind/status").id == "health-brains-wind-domain"
    assert row_for("/nothing/here") is None


def test_projection_rows_match_the_registered_publisher_rules():
    rules = {p.id for sp in (REG.spec(s) for s in REG.schemas_for("wind")) for p in sp.projections}
    assert rules == {"wind-snapshot-copy-v1", "wind-snapshot-brainversion-v1"}
    for r in LEGACY_PATH_TABLE:
        if r.mechanism == "PUBLISHER_DERIVED":
            assert any(rid in r.target_source for rid in rules), r.id
