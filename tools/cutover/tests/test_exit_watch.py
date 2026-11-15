"""exit_watch: GET-only, private captures; X08/X11/X12 verdicts around exactly one publish."""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import exit_watch as W      # noqa: E402

LIVE = {
    "lakeFleet": {"Guntersville_AL": {"slots": {"lake": {"v": 1}, "waterTemp": {"t": 60}}, "riverSystem": "TN"},
                  "Other_TX": {"slots": {"lake": {"v": 9}, "waterTemp": {"t": 70}}}},
    "lakes": {"Guntersville_AL": {"states": {"lake": {"levelFt": 595}, "waterTemp": {"f": 60}}},
              "Other_TX": {"states": {"lake": {"levelFt": 100}}}},
    "snapshots": {"Guntersville_AL": {"latest": {"lakeState": {"x": 1}, "brainVersions": {"lake-brain": "a"}}},
                  "Other_TX": {"latest": {"lakeState": {"x": 2}}}},
    "brains": {"lake-brain": {"status": "ok", "publication": {"publishId": "p1", "status": "COMPLETE"}}, "wind": {"status": "ok"}},
    "validation": {"lake-brain": {"n": 1}},
    "sources": {"cwms": {"lastFetchAt": "t0"}},
    "health": {"brains": {"lake-brain": {"status": "HEALTHY", "staleLakeCount": 0}}},
    "scores": {"lake-brain": {"value": 7.0, "scoreVersion": "v1", "uncapped": 7.2, "basis": "b"}, "wind": {"value": 5.0, "scoreVersion": "v1"}},
    "control": {"execution": {"state": "ENABLED"}},
}


def node(tree, path):
    for p in [x for x in path.strip("/").split("/") if x]:
        tree = tree.get(p) if isinstance(tree, dict) else None
    return tree


def fetcher(tree, seen=None):
    def f(url, path, token, shallow=False):
        if seen is not None:
            seen.append(path)
        v = node(tree, path)
        return {k: True for k in v} if shallow and isinstance(v, dict) else copy.deepcopy(v)
    return f


def cap(tree, tmp, name, monkeypatch):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "t")
    monkeypatch.setattr(W, "inside_git", lambda p: False)
    assert W.main(["capture", "--brain", "lake-brain", "--out", str(tmp / name)], fetch_raw=fetcher(tree)) == 0
    return json.load(open(tmp / name / "fingerprints.json"))


def published(tree):
    t = copy.deepcopy(tree)
    t["lakes"]["Guntersville_AL"]["states"]["lake"]["levelFt"] = 596
    t["brains"]["lake-brain"]["publication"] = {"publishId": "p2", "status": "COMPLETE"}
    return t


RECORD = {"publishId": "p2", "previousPublishId": "p1", "brainId": "lake-brain", "live": True, "result": "PUBLISHED", "status": "COMPLETE",
          "pathSha256": {"lakes/Guntersville_AL/states/lake/levelFt": "x", "brains/lake-brain/publication": "y"}}     # production key form: no leading slash


def test_capture_refuses_inside_git_without_token_and_never_overwrites(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "t")
    monkeypatch.setattr(W, "inside_git", lambda p: True)               # do not depend on where the tests run from
    assert W.main(["capture", "--brain", "lake-brain", "--out", str(tmp_path / "nope")], fetch_raw=fetcher(LIVE)) == 2
    assert not os.path.exists(tmp_path / "nope")
    monkeypatch.setattr(W, "inside_git", lambda p: False)
    monkeypatch.delenv("BRAIN_ACCESS_TOKEN")
    assert W.main(["capture", "--brain", "lake-brain", "--out", str(tmp_path / "c")], fetch_raw=fetcher(LIVE)) == 2
    cap(LIVE, tmp_path, "c", monkeypatch)
    assert W.main(["capture", "--brain", "lake-brain", "--out", str(tmp_path / "c")], fetch_raw=fetcher(LIVE)) == 2
    assert oct(os.stat(tmp_path / "c" / "fingerprints.json").st_mode & 0o777) == "0o600"


def test_capture_fingerprints_the_whole_fleet_at_slot_level(monkeypatch, tmp_path):
    c = cap(LIVE, tmp_path, "c", monkeypatch)
    fp = c["fingerprints"]
    assert c["lakeCount"] == 2 and c["publication"]["publishId"] == "p1" and c["score"]["value"] == 7.0
    assert {"lakes/Other_TX/states/lake", "lakeFleet/Guntersville_AL/slots/waterTemp", "lakeFleet/Guntersville_AL/riverSystem",
            "snapshots/Guntersville_AL/latest/brainVersions/lake-brain", "brains/wind/status", "sources/cwms", "validation/lake-brain"} <= set(fp)


def test_capture_rejects_a_non_firebase_url(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "t")
    assert W.main(["capture", "--brain", "lake-brain", "--out", str(tmp_path / "c"), "--rtdb", "https://example.com"], fetch_raw=fetcher(LIVE)) == 2


def test_a_clean_publish_passes_and_other_writers_are_listed_not_failed(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    t["lakes"]["Other_TX"]["states"]["waterTemp"] = {"f": 71}           # Water Temp's own writer ran in the window
    t["sources"]["cwms"]["lastFetchAt"] = "t1"                            # covered by the record's /sources write (leading-slash form also accepted)
    t["scores"]["wind"]["value"] = 5.5                                    # the scorer ran for another Brain
    after = cap(t, tmp_path, "a", monkeypatch)
    rec = copy.deepcopy(RECORD)
    rec["pathSha256"]["/sources/cwms"] = "z"
    r = W.evaluate("lake-brain", before, after, rec)
    assert r["checks"] == {"X08": "PASS", "X11": "PASS", "X12": "PASS"}, r
    assert r["X08"]["otherWriters"]["water-temp"]["count"] == 1 and r["X08"]["otherWriters"]["scorer"]["count"] == 1
    assert "control" in r["scope"]["after"]


def test_a_lake_owned_change_outside_the_write_set_fails_x08(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    t["lakeFleet"]["Other_TX"]["slots"]["lake"] = {"v": 10}               # a non-pilot lake's Lake slot moved: not in the record
    r = W.evaluate("lake-brain", before, cap(t, tmp_path, "a", monkeypatch), RECORD)
    assert r["checks"]["X08"] == "FAIL" and r["X08"]["ownOutsideWriteSet"] == ["lakeFleet/Other_TX/slots/lake"]


def test_an_unowned_change_needs_review(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    t["lakeFleet"]["Other_TX"]["name"] = "renamed"
    r = W.evaluate("lake-brain", before, cap(t, tmp_path, "a", monkeypatch), RECORD)
    assert r["checks"]["X08"] == "REVIEW" and r["X08"]["unowned"] == ["lakeFleet/Other_TX/name"]


def test_blanked_or_wrongly_healthy_health_fails_x11(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    t["health"]["brains"]["lake-brain"] = {"status": "HEALTHY", "staleLakeCount": 3}      # legitimate under Lake's reviewed-lakes rule: reported, not failed
    assert W.evaluate("lake-brain", before, cap(t, tmp_path, "a0", monkeypatch), RECORD)["checks"]["X11"] == "PASS"
    t["health"]["brains"]["lake-brain"] = {"status": "HEALTHY", "staleLakeCount": 3, "reasons": ["stale gauge"]}
    assert W.evaluate("lake-brain", before, cap(t, tmp_path, "a", monkeypatch), RECORD)["checks"]["X11"] == "FAIL"
    t["health"]["brains"]["lake-brain"] = None
    assert W.evaluate("lake-brain", before, cap(t, tmp_path, "a2", monkeypatch), RECORD)["checks"]["X11"] == "FAIL"


def test_a_score_change_or_a_score_write_fails_x12(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    t["scores"]["lake-brain"]["scoreVersion"] = "v2"
    assert W.evaluate("lake-brain", before, cap(t, tmp_path, "a", monkeypatch), RECORD)["checks"]["X12"] == "FAIL"
    rec = copy.deepcopy(RECORD)
    rec["pathSha256"]["/scores/lake-brain/value"] = "s"
    assert W.evaluate("lake-brain", before, cap(published(LIVE), tmp_path, "a2", monkeypatch), rec)["checks"]["X12"] == "FAIL"


def test_the_verdict_is_inconclusive_unless_exactly_this_publish_is_between_the_captures(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    same = cap(LIVE, tmp_path, "s", monkeypatch)                          # no publish happened
    assert set(W.evaluate("lake-brain", before, same, RECORD)["checks"].values()) == {"INCONCLUSIVE"}
    rec = copy.deepcopy(RECORD)
    rec["previousPublishId"] = "p0"                                       # another publish slipped in before this one
    assert set(W.evaluate("lake-brain", before, cap(published(LIVE), tmp_path, "a", monkeypatch), rec)["checks"].values()) == {"INCONCLUSIVE"}


def test_evaluate_writes_privately_and_exits_non_zero_unless_all_pass(monkeypatch, tmp_path):
    cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    cap(t, tmp_path, "a", monkeypatch)
    json.dump(RECORD, open(tmp_path / "record.json", "w"))
    args = ["evaluate", "--brain", "lake-brain", "--before", str(tmp_path / "b"), "--after", str(tmp_path / "a"), "--record", str(tmp_path / "record.json")]
    assert W.main(args + ["--out", str(tmp_path / "x.json")]) == 0
    assert json.load(open(tmp_path / "x.json"))["checks"]["X08"] == "PASS"
    cap(LIVE, tmp_path, "s", monkeypatch)
    assert W.main(args[:5] + ["--after", str(tmp_path / "s")] + args[7:] + ["--out", str(tmp_path / "y.json")]) == 1


def test_wait_returns_the_new_publish_id_and_times_out_read_only(monkeypatch, capsys):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "t")
    seen = []
    trees = iter([LIVE, LIVE, published(LIVE)])
    cur = {"t": LIVE}

    def f(url, path, token, shallow=False):
        seen.append(path)
        return fetcher(cur["t"])(url, path, token, shallow)
    def sleep(_):
        cur["t"] = next(trees)
    assert W.main(["wait", "--brain", "lake-brain", "--since-publish-id", "p1"], fetch_raw=f, sleep=sleep) == 0
    assert capsys.readouterr().out.strip() == "p2" and set(seen) == {"brains/lake-brain/publication"}
    assert W.main(["wait", "--brain", "lake-brain", "--since-publish-id", "p1", "--timeout-min", "0"], fetch_raw=fetcher(LIVE)) == 3


def test_owner_map():
    assert W.owner("lakes/A/states/waterClarity") == "water-clarity"
    assert W.owner("snapshots/A/latest/lakeState") == "lake-brain"
    assert W.owner("lakeFleet/A/riverSystem") == "lake-brain"
    assert W.owner("brains/lake-brain/publication") == "publisher:lake-brain"
    assert W.owner("health/brains/lake-brain") == "orchestrator" and W.owner("lakeFleet/A/name") is None


def test_changes_outside_the_old_scope_are_seen(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    t["control"]["execution"]["state"] = "PAUSED"                        # a platform root
    t["lakes"]["Ghost_XX"] = {"states": {"lake": {"levelFt": 1}}}         # a lake with no lakeFleet row
    t["lakes"]["Other_TX"]["speciesPresence"] = {"gar": True}             # Lake-owned lake-state-v1 child
    r = W.evaluate("lake-brain", before, cap(t, tmp_path, "a", monkeypatch), RECORD)
    assert r["checks"]["X08"] == "FAIL"
    assert set(r["X08"]["ownOutsideWriteSet"]) == {"lakes/Ghost_XX/states/lake", "lakes/Other_TX/speciesPresence/gar"}
    assert r["X08"]["otherWriters"]["platform:control"]["count"] == 1


def test_an_unowned_change_is_review_never_pass(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    t = published(LIVE)
    t["sources"]["cwms"]["lastFetchAt"] = "t1"                            # not a real SOURCE_OWNERS id and not in the write set
    assert W.evaluate("lake-brain", before, cap(t, tmp_path, "a", monkeypatch), RECORD)["checks"]["X08"] == "REVIEW"


def test_no_score_to_compare_is_inconclusive_not_pass(monkeypatch, tmp_path):
    t0 = copy.deepcopy(LIVE)
    del t0["scores"]["lake-brain"]
    before = cap(t0, tmp_path, "b", monkeypatch)
    t = published(t0)
    assert W.evaluate("lake-brain", before, cap(t, tmp_path, "a", monkeypatch), RECORD)["checks"]["X12"] == "INCONCLUSIVE"


def test_a_failed_or_foreign_record_is_inconclusive(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    after = cap(published(LIVE), tmp_path, "a", monkeypatch)
    for change in ({"status": "FAILED"}, {"brainId": "wind"}, {"live": False}, {"previousPublishId": None}):
        rec = {**RECORD, **change}
        assert set(W.evaluate("lake-brain", before, after, rec)["checks"].values()) == {"INCONCLUSIVE"}, change


def test_a_capture_that_overlaps_a_publish_is_inconclusive(monkeypatch, tmp_path):
    before = cap(LIVE, tmp_path, "b", monkeypatch)
    after = cap(published(LIVE), tmp_path, "a", monkeypatch)
    after["publicationAtStart"] = {"publishId": "p1", "status": "COMPLETE"}
    assert set(W.evaluate("lake-brain", before, after, RECORD)["checks"].values()) == {"INCONCLUSIVE"}
    after["publicationAtStart"] = after["publication"] = {"publishId": "p2", "status": "COMPLETE", "pending": {"x": 1}}
    assert set(W.evaluate("lake-brain", before, after, RECORD)["checks"].values()) == {"INCONCLUSIVE"}


def test_get_issues_a_get_and_never_follows_redirects(monkeypatch):
    seen = {}

    class R:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b'{"a": 1}'

    def open_(req, timeout):
        seen["method"], seen["url"] = req.get_method(), req.full_url
        return R()
    monkeypatch.setattr(W._OPENER, "open", open_)
    assert W.get("https://x.firebaseio.com", "brains/lake-brain", "tok", shallow=True) == {"a": 1}
    assert seen == {"method": "GET", "url": "https://x.firebaseio.com/brains/lake-brain.json?shallow=true"}
    assert any(isinstance(h, W._NoRedirect) for h in W._OPENER.handlers)


def test_the_token_never_reaches_output_or_files(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "SECRET-TOKEN-123")
    monkeypatch.setattr(W, "inside_git", lambda p: False)
    assert W.main(["capture", "--brain", "lake-brain", "--out", str(tmp_path / "c")], fetch_raw=fetcher(LIVE)) == 0
    out = capsys.readouterr()
    assert "SECRET-TOKEN-123" not in out.out + out.err
    assert "SECRET-TOKEN-123" not in open(tmp_path / "c" / "fingerprints.json").read()


def test_evaluate_never_overwrites(monkeypatch, tmp_path):
    cap(LIVE, tmp_path, "b", monkeypatch)
    cap(published(LIVE), tmp_path, "a", monkeypatch)
    json.dump(RECORD, open(tmp_path / "record.json", "w"))
    (tmp_path / "x.json").write_text("{}")
    assert W.main(["evaluate", "--brain", "lake-brain", "--before", str(tmp_path / "b"), "--after", str(tmp_path / "a"),
                   "--record", str(tmp_path / "record.json"), "--out", str(tmp_path / "x.json")]) == 2


def test_wait_survives_a_transient_read_error(monkeypatch, capsys):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "t")
    calls = iter([OSError("boom"), published(LIVE)])

    def f(url, path, token, shallow=False):
        v = next(calls)
        if isinstance(v, Exception):
            raise v
        return fetcher(v)(url, path, token, shallow)
    assert W.main(["wait", "--brain", "lake-brain", "--since-publish-id", "p1"], fetch_raw=f, sleep=lambda _: None) == 0
    assert capsys.readouterr().out.strip() == "p2"
