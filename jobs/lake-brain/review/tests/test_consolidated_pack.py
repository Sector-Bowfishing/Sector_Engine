"""Tests for the consolidated packet builder (rule consolidated-selection-v2): hard safety gates vs ranking factors, funnel, best-first order,
diversity, Section B, and the written packet. All data is synthetic (consolidated_helpers.py); nothing is written outside tmp_path."""
import copy
import csv
import json
import os
import re

import pytest

import build_consolidated_pack as C
import consolidated_common as CC
from consolidated_helpers import mk_binding, mk_reg, mk_row, mk_world

REAL_DATA = CC.DATA_DIR


def ev(row, ctx, thr=C.THRESH):
    return dict(C.evaluate(row, ctx, thr))


def test_thresholds_are_the_stated_v2_gates():
    assert C.SELECTION_RULE_ID == "consolidated-selection-v2"
    assert C.THRESH == dict(max_dist_m=150.0, second_diff_ft=2.0, pool_tol_ft=5.0, name_sim=0.6, hist_years=5, obs_age_h=72.0)
    assert not hasattr(C, "RELAX_ORDER") and not hasattr(C, "MIN_A")              # no relaxation machinery: a gate is a gate
    assert sum(C.RANK_WEIGHTS.values()) == 100 and set(C.RANK_WEIGHTS) == {"identity", "coordinate", "operator", "geometry", "duplicate", "datum", "history", "usefulness"}
    assert "NOT A VALIDATION THRESHOLD" in C.__doc__ and "review-candidate" in C.__doc__.lower().replace("\n", " ")


def test_baseline_row_passes_every_gate():
    rows, ctx = mk_world(3)
    r = next(iter(rows.values()))
    got = ev(r, ctx)
    assert list(got) == list(C.CRITERIA_ORDER) and all(got.values()), got


def mutate(fn_row=None, fn_ctx=None):
    rows, ctx = mk_world(3)
    r = next(iter(rows.values()))
    if fn_row:
        fn_row(r, ctx)
    if fn_ctx:
        fn_ctx(r, ctx)
    return r, ctx


GATE_CASES = [
    ("pilot", lambda r, c: c.pilots.add(r["id"]), "not_pilot"),
    ("held", lambda r, c: c.held.add(r["id"]), "not_held"),
    ("coordinate pack", lambda r, c: c.coord_pack.add(r["id"]), "not_in_coordinate_review"),
    ("rec FLAG", lambda r, c: r.__setitem__("rec", "FLAG"), "recommendation_pass_rules_clear"),
    ("rule FAIL", lambda r, c: r["rules"][3].__setitem__("res", "FAIL"), "recommendation_pass_rules_clear"),
    ("rule FLAG (R7)", lambda r, c: r["rules"][6].__setitem__("res", "FLAG"), "recommendation_pass_rules_clear"),
    ("151 m from the outline", lambda r, c: r["dist"].update(m=151.0), "spatial_match"),
    ("no outline", lambda r, c: r["dist"].update(outline=False), "spatial_match"),
    ("registry LOW outline", lambda r, c: c.registry[r["id"]]["geometryConfidence"].update(level="LOW"), "registry_geometry_usable"),
    ("registry MISSING outline", lambda r, c: c.registry[r["id"]]["geometryConfidence"].update(level="MISSING"), "registry_geometry_usable"),
    ("registry identity-risk point", lambda r, c: c.registry[r["id"]].update(pointFlag="identity-risk", location=dict(distanceToShorelineM=0)), "registry_geometry_usable"),
    ("registry off-water point 151 m out", lambda r, c: c.registry[r["id"]].update(pointFlag="off-water", location=dict(distanceToShorelineM=151)), "registry_geometry_usable"),
    ("registry off-water point, no distance", lambda r, c: c.registry[r["id"]].update(pointFlag="off-water"), "registry_geometry_usable"),
    ("not in registry", lambda r, c: c.registry.pop(r["id"]), "registry_geometry_usable"),
    ("pool not high", lambda r, c: r["pool"].update(conf="med"), "independent_confirmation"),
    ("pool basis natural", lambda r, c: r["pool"].update(basis="naturalSurface"), "independent_confirmation"),
    ("pool diff 5.1 ft now", lambda r, c: r["pool"].update(diffNow=-5.1), "independent_confirmation"),
    ("pool diff 5.1 ft median", lambda r, c: r["pool"].update(diff=5.1), "independent_confirmation"),
    ("operator unknown", lambda r, c: r.__setitem__("operator", "none"), "independent_confirmation"),
    ("name similarity 0.59", lambda r, c: r["nameMatch"].update(sim=0.59, station="Totally Other"), "name_similarity"),
    ("history 4 years", lambda r, c: c.table[r["id"]].update(historyCompleteYears=4), "history"),
    ("observation 73 h old", lambda r, c: r["level"].update(ageH=73.0), "observation_age"),
    ("observation age unknown", lambda r, c: r["level"].update(ageH=None), "observation_age"),
    ("warning: relays another agency", lambda r, c: r["recNotes"].append("NOAA/NWS gauge that relays another agency's number (not an independent check)"), "no_attention_warning"),
    ("warning: unknown note", lambda r, c: r["recNotes"].append("something nobody has seen before"), "no_attention_warning"),
    ("warning: river-like name without a second source", lambda r, c: r["recNotes"].append("station name sounds like a river/creek/outlet - confirm it measures the lake"), "no_attention_warning"),
    ("datum: R8 not PASS", lambda r, c: r["rules"][7].__setitem__("res", "FLAG"), "recommendation_pass_rules_clear"),
    ("datum: r7class weak", lambda r, c: r.__setitem__("r7class", "weak"), "no_datum_ambiguity"),
    ("datum: offset", lambda r, c: c.table[r["id"]]["live"][0].__setitem__("datumOffsetFt", 0.31), "no_datum_ambiguity"),
    ("datum: history caveat", lambda r, c: c.table[r["id"]].update(historyNotes=["composite: listed lowest precedence first"]), "no_datum_ambiguity"),
]


@pytest.mark.parametrize("name,edit,criterion", GATE_CASES)
def test_each_gate_removes_its_row(name, edit, criterion):
    r, ctx = mutate(edit)
    failed = [k for k, v in ev(r, ctx).items() if not v]
    assert criterion in failed, (name, failed)
    chosen, rep = C.select_section_a({r["id"]: r}, ctx, target=64)
    assert chosen == [] and rep["shortfall"] == 64                                # a row failing a gate is never selected, never padded in


@pytest.mark.parametrize("name,edit", [
    ("history 5 years", lambda r, c: c.table[r["id"]].update(historyCompleteYears=5)),
    ("history 5 years, tva-guide basis", lambda r, c: c.table[r["id"]].update(historyCompleteYears=5, historyBasis="tva-guide")),
    ("registry MEDIUM outline", lambda r, c: c.registry[r["id"]]["geometryConfidence"].update(level="MEDIUM", score=0.7)),
    ("registry off-water point exactly 150 m from the shoreline", lambda r, c: c.registry[r["id"]].update(pointFlag="off-water", location=dict(distanceToShorelineM=150))),
    ("pool diff 5.0 ft", lambda r, c: r["pool"].update(diffNow=-5.0, diff=5.0)),
    ("observation exactly 72 h", lambda r, c: r["level"].update(ageH=72.0)),
    ("name similarity exactly 0.6", lambda r, c: r["nameMatch"].update(sim=0.6, station="Totally Other")),
    ("stale-by-hours note is informational", lambda r, c: r["recNotes"].append("last reading is 70 h old")),
    ("short-history note is informational", lambda r, c: r["recNotes"].append("short or no public history")),
])
def test_things_that_only_describe_data_richness_do_not_exclude(name, edit):
    r, ctx = mutate(edit)
    assert all(ev(r, ctx).values()), (name, [k for k, v in ev(r, ctx).items() if not v])


def test_history_tiers_and_the_floor():
    assert [C.history_tier(y) for y in (0, 4, 5, 9, 10, 14, 15, 40)] == [None, None, "PROVISIONAL", "PROVISIONAL", "STANDARD", "STANDARD", "FULL", "FULL"]


def test_informational_notes_are_never_warnings_but_the_rest_are_listed():
    r, ctx = mutate(lambda r, c: r["recNotes"].extend(["single agency only (no independent second source)",
                                                          "the station name contains every word of the lake name (research similarity 0.62 is lowered only by extra words or abbreviations)",
                                                          "last reading is 30 h old"]))
    assert ev(r, ctx)["no_attention_warning"]
    assert C.attention_warnings(r) == ["last reading is 30 h old"]                # listed on the card, does not block
    assert C.blocking_warnings(r) == []


def test_second_source_makes_gap_and_name_notes_non_blocking_but_they_stay_listed():
    notes = ["level is -9.0 ft from full pool", "directory full-pool confidence is 'med'", "station name sounds like a river/creek/outlet - confirm it measures the lake", "only a partial name match (similarity 0.62)"]
    r, ctx = mutate(lambda r, c: r["recNotes"].extend(notes))
    assert not ev(r, ctx)["no_attention_warning"]                                   # pool-only confirmation: these notes block
    r["second"] = dict(label="USGS x", name="n", lastFt=1.0, diff=1.9, links=[])
    assert ev(r, ctx)["no_attention_warning"] and C.attention_warnings(r) == notes   # an agreeing second source resolves them; every one is still listed


def test_geometry_gate_function():
    ok = mk_reg()
    assert C.geometry_gate(ok)
    assert C.geometry_gate(mk_reg(geometryConfidence=dict(level="MEDIUM", score=0.6)))
    assert not C.geometry_gate(mk_reg(geometryConfidence=dict(level="LOW", score=0.3)))
    assert not C.geometry_gate({})


def test_independent_second_source_or_operator_pool():
    # second source agrees within 2 ft -> qualifies even with a pool far from the level
    r, ctx = mutate(lambda r, c: (r["pool"].update(diffNow=-30.0, diff=-30.0), r.__setitem__("second", dict(label="USGS x", name="n", lastFt=1.0, diff=2.0, links=[])))[1])
    assert ev(r, ctx)["independent_confirmation"]
    assert C.independent_basis(r, C.THRESH) == "second"
    r["second"]["diff"] = 2.01
    assert not ev(r, ctx)["independent_confirmation"]
    r["pool"].update(diffNow=-1.0, diff=-1.0)
    assert C.independent_basis(r, C.THRESH) == "pool"
    r["second"]["diff"] = 0.2
    assert C.independent_basis(r, C.THRESH) == "second+pool"


def test_name_containment_counts_as_high_similarity():
    r, ctx = mutate(lambda r, c: r["nameMatch"].update(sim=0.5, lake="Synth 1 Lake", station="Synth 1 Lake Dam Pool Forebay"))
    assert ev(r, ctx)["name_similarity"]


def test_funnel_counts_are_cumulative_and_exact():
    rows, ctx = mk_world(10)
    ids = sorted(rows)
    ctx.pilots.add(ids[0])
    rows[ids[1]]["rec"] = "FLAG"
    rows[ids[2]]["level"]["ageH"] = 80.0
    rows[ids[3]]["dist"]["m"] = 400.0
    rows[ids[3]]["level"]["ageH"] = 80.0
    f = C.funnel(rows, ctx)
    steps = {s["criterion"]: s for s in f["steps"]}
    assert f["start"] == 10
    assert steps["not_pilot"]["remaining"] == 9
    assert steps["recommendation_pass_rules_clear"]["remaining"] == 8
    assert steps["spatial_match"]["remaining"] == 7
    assert steps["observation_age"]["remaining"] == 6          # id[2] leaves here; id[3] already left at spatial_match
    assert steps["observation_age"]["failedAlone"] == 2         # id[2] and id[3] both fail this one on its own
    assert len(f["qualifying"]) == 6 and ids[0] not in f["qualifying"]
    assert f["blockedOnlyBy"]["observation_age"] == [ids[2]]    # id[3] fails two gates, id[2] only one
    assert [s["remaining"] for s in f["steps"]] == sorted([s["remaining"] for s in f["steps"]], reverse=True)


def test_qualify_has_no_relaxation_and_never_returns_a_failing_row():
    rows, ctx = mk_world(8)
    ids = sorted(rows)
    rows[ids[0]]["level"]["ageH"] = 73.0
    ok, f = C.qualify(rows, ctx)
    assert len(ok) == 7 and ids[0] not in ok


def test_selection_never_pads_and_reports_the_shortfall():
    rows, ctx = mk_world(12)
    ids = sorted(rows)
    rows[ids[0]]["rec"] = "FLAG"
    chosen, rep = C.select_section_a(rows, ctx, target=64)
    assert len(chosen) == 11 and rep["shortfall"] == 53 and ids[0] not in chosen
    assert rep["qualifying"] == 11 and rep["selected"] == 11


def test_selection_never_contains_pilots_held_or_coordinate_pack_lakes():
    rows, ctx = mk_world(20)
    ids = sorted(rows)
    ctx.pilots.add(ids[0]); ctx.held.add(ids[1]); ctx.coord_pack.add(ids[2])
    chosen, _ = C.select_section_a(rows, ctx, target=64)
    assert not set(chosen) & set(ids[:3]) and len(chosen) == 17


def test_non_sample_rows_come_first_and_sample_rows_are_counted():
    rows, ctx = mk_world(12)
    ids = sorted(rows)
    ctx.sample.update(ids[:4])
    chosen, rep = C.select_section_a(rows, ctx, target=10)
    assert len(chosen) == 10 and rep["sampleRowsUsed"] == 2 and set(ids[4:]) <= set(chosen)
    chosen8, rep8 = C.select_section_a(rows, ctx, target=8)
    assert rep8["sampleRowsUsed"] == 0 and not set(chosen8) & set(ids[:4])
    chosen_all, rep_all = C.select_section_a(rows, ctx, target=64)
    assert rep_all["sampleRowsUsed"] == 4 and len(chosen_all) == 12


def test_selection_is_deterministic_and_seed_sensitive_only_through_ties():
    rows, ctx = mk_world(30)
    a, _ = C.select_section_a(rows, ctx, seed=1, target=10)
    b, _ = C.select_section_a(dict(reversed(list(rows.items()))), ctx, seed=1, target=10)
    assert a == b
    c, _ = C.select_section_a(rows, ctx, seed=2, target=10)
    assert len(set(a)) == 10 and len(set(c)) == 10


def test_diversity_spreads_providers_and_states():
    rows, ctx = mk_world(0)
    # 30 near-identical a2w lakes in state AA, and 4 slightly weaker lakes of other providers/states
    for i in range(30):
        r = mk_row(100 + i, provider="a2w", state="AA")
        rows[r["id"]] = r; ctx.table[r["id"]] = mk_binding(r); ctx.registry[r["id"]] = mk_reg(); ctx.bow[r["id"]] = 5
    for i, (p, s) in enumerate([("cwms", "BB"), ("usgs", "CC"), ("rise", "DD"), ("tva", "EE")]):
        r = mk_row(200 + i, provider=p, state=s)
        r["capability"] = "DIRECT_LAKE_GAUGE"
        r["pool"]["conf"] = "high"
        rows[r["id"]] = r; ctx.table[r["id"]] = mk_binding(r); ctx.registry[r["id"]] = mk_reg(geometryConfidence=dict(level="HIGH", score=0.9)); ctx.bow[r["id"]] = 3
    chosen, _ = C.select_section_a(rows, ctx, target=14)
    assert {rows[l]["provider"] for l in chosen} == {"a2w", "cwms", "usgs", "rise", "tva"}
    import pytest as _p
    mp = _p.MonkeyPatch()
    mp.setattr(C, "DIVERSITY_PENALTY", dict(provider=0.0, state=0.0, kind=0.0, region=0.0))
    try:
        flat, _ = C.select_section_a(rows, ctx, target=14)
    finally:
        mp.undo()
    assert {rows[l]["provider"] for l in flat} == {"a2w"}                       # without the penalty the 30 slightly stronger a2w lakes fill every slot


def test_rank_components_are_bounded_and_weights_sum_to_100():
    assert sum(C.RANK_WEIGHTS.values()) == 100
    rows, ctx = mk_world(3)
    for r in rows.values():
        comp = C.rank_components(r, ctx)
        assert all(0 <= v <= C.RANK_WEIGHTS[k] + 1e-6 for k, v in comp.items()) and set(comp) == set(C.RANK_WEIGHTS)


def test_duplicate_lake_ambiguity_lowers_the_rank():
    rows, ctx = mk_world(2)
    a, b = sorted(rows)
    base = sum(C.rank_components(rows[a], ctx).values())
    ctx.dir_names[C.norm_name(rows[a]["name"])] = 2
    assert sum(C.rank_components(rows[a], ctx).values()) < base
    assert sum(C.rank_components(rows[b], ctx).values()) == sum(C.rank_components(rows[b], ctx).values())


def test_section_b_quota_order_and_spare_flow():
    rows, ctx = mk_world(0)
    cands = {s: {} for s in ("recovered", "mismatch", "held", "flagged")}
    n = 0
    for s, k in (("recovered", 8), ("mismatch", 5), ("held", 0), ("flagged", 12)):
        for i in range(k):
            n += 1
            lid = f"B{n} Lake|ZZ"
            cands[s][lid] = {}
            ctx.bow[lid] = i
    got = C.select_section_b(cands, ctx)
    assert len(got) == 20
    assert [s for s, _ in got].count("recovered") == 8 and [s for s, _ in got].count("mismatch") == 5 and [s for s, _ in got].count("flagged") == 7     # held's 2 spare go to flagged
    rec = [l for s, l in got if s == "recovered"]
    assert [ctx.bow[l] for l in rec] == sorted([ctx.bow[l] for l in rec], reverse=True)      # most useful first


# ------------------------------------------------------------------------------------------------ the written packet
class FakeInp:
    item2loc = {}


def build_pack(tmp_path, with_b=True):
    rows, ctx = mk_world(12, pilots=(), sample=())
    ids = sorted(rows)
    ctx.pilots.add("Synth pilot Lake|ZZ")
    out = tmp_path / "packet"
    flagged, held_rows, recovered = {}, {}, {"bindings": []}
    if with_b:
        fr = mk_row(900, provider="usgs")
        fr["postHoc"] = dict(outcome="PROMOTED by the post-hoc R7h history-envelope rule")
        flagged[fr["id"]] = fr
        ctx.bow[fr["id"]] = 7
        rr = mk_row(901, provider="rise")
        held_rows[rr["id"]] = rr
        ctx.bow[rr["id"]] = 8
        ctx.held.add(rr["id"])
        recovered = dict(bindings=[dict(lakeId=rr["id"], provider="rise", station=rr["station"], series=rr["series"], live=[dict(note="x")], verification=dict(probe={}), historyCompleteYears=20, historyClass="SUFFICIENT")])
        mm = mk_row(902, provider="a2w")
        held_rows[mm["id"]] = mm
        ctx.bow[mm["id"]] = 6
        ctx.held.add(mm["id"])
    disp = dict(lakes={"Synth 902 Lake|ZZ": dict(disposition="NEEDS HUMAN REVIEW", reason="A2W serves only the latest value")} if with_b else {})
    manifest, a, b = C.build(FakeInp(), ctx, rows, str(out), "regsha", 7, dict(), recovered, disp, flagged, held_rows, write=True,
                             held_kind={"Synth 902 Lake|ZZ": "series", "Synth 901 Lake|ZZ": "series"})
    return out, manifest, a, b, ctx


def test_packet_files_manifest_and_nothing_accepted(tmp_path):
    before = set(os.listdir(REAL_DATA))
    out, m, a, b, ctx = build_pack(tmp_path)
    assert sorted(os.listdir(out)) == ["START HERE - README.md", "binding_review_consolidated.csv", "binding_review_consolidated.html", "pack_manifest.json"]
    assert set(os.listdir(REAL_DATA)) == before                                   # the repo data folder is untouched by the builder
    assert not (out / "accepted_batch.json").exists() and not (out / "binding_review_result.json").exists()
    man = json.load(open(out / "pack_manifest.json"))
    assert man["packId"].startswith(CC.PACK_PREFIX) and "WAITING FOR MICHAEL" in man["status"]
    assert man["counts"]["sectionA"] == 12 and man["counts"]["sectionB"] == 3
    assert man["decisions"] == ["ACCEPT", "REJECT", "NEEDS REVIEW"]
    assert [r["id"] for r in man["rows"] if r["section"] == "A"] == [r["id"] for r in a]
    assert all(r["inBindingsTable"] for r in man["rows"] if r["section"] == "A") and not any(r["inBindingsTable"] for r in man["rows"] if r["section"] == "B")
    assert man["funnel"]["start"] == 12 and "recommendation_pass_rules_clear" in [s["criterion"] for s in man["funnel"]["steps"]]


def test_section_b_rows_carry_reason_and_never_count_unless_in_table(tmp_path):
    out, m, a, b, ctx = build_pack(tmp_path)
    assert {r["sourceGroup"] for r in b} == {"recovered", "mismatch", "flagged"}
    for r in b:
        assert r["whyFlagged"] and r["doAfterA"] and "does not count" in r["countsIfAccepted"] and "accepted_batch.json" in r["countsIfAccepted"]
        assert r["inBindingsTable"] is False
    assert all(r["section"] == "A" and r["countsIfAccepted"].startswith("yes") for r in a)


def test_digest_is_stable_and_locks_the_identity_fields(tmp_path):
    out, m, a, b, ctx = build_pack(tmp_path)
    r = a[0]
    core = dict(id=r["id"], section="A", name=r["name"], state=r["state"], provider=r["provider"], identifier=r["identifier"], station=r["station"], series=r["series"], recommendation=r["recommendation"])
    assert CC.row_digest(core) == r["digest"]
    for k, v in (("provider", "zzz-provider"), ("identifier", "other"), ("recommendation", "FLAG"), ("name", "Other"), ("section", "B")):
        assert CC.row_digest(dict(core, **{k: v})) != r["digest"]


def test_html_is_one_file_with_the_required_header_decisions_and_sentence(tmp_path):
    out, m, a, b, ctx = build_pack(tmp_path)
    html = (out / "binding_review_consolidated.html").read_text(encoding="utf-8")
    assert "__DATA_JSON__" not in html and "__PACK_ID__" not in html and m["packId"] in html
    assert "<script src" not in html and "<link " not in html and "@import" not in html          # one self-contained file, no external code or assets
    assert "Section A: accepted " in html and "more needed to reach " in html and "Section B" in html
    assert "Every ACCEPT is me personally accepting that one lake; nothing is extrapolated to a lake I did not decide." in html
    for word in ("Accept", "Reject", "Needs review", "NEEDS REVIEW", "localStorage", "Download my review (CSV)"):
        assert word in html
    payload = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1)
    data = json.loads(payload)
    assert data["packId"] == m["packId"] and len(data["rows"]) == len(a) + len(b)
    assert data["meta"]["neededAccepts"] == 58 and data["meta"]["threshold"] == 63 and data["meta"]["pilots"] == 5
    assert "UNSURE" not in json.dumps(data)            # the vocabulary in the data is ACCEPT / REJECT / NEEDS REVIEW only
    # export columns of the form are the columns the ingest requires
    head = re.search(r'\[("pack_id".*?"exported_at_utc")\]\.join', html).group(1)
    assert [x.strip('"') for x in head.split(", ")] == list(CC.EXPORT_COLUMNS)


def test_csv_readme_and_plain_language(tmp_path):
    out, m, a, b, ctx = build_pack(tmp_path)
    rows = list(csv.DictReader(open(out / "binding_review_consolidated.csv", encoding="utf-8-sig")))
    assert len(rows) == len(a) + len(b) and rows[0]["row_digest"] == a[0]["digest"]
    readme = (out / "START HERE - README.md").read_text()
    for phrase in ("WAITING FOR MICHAEL", "20 to 30 minutes", "Download my review", "ingest_batch_review.py", "Path A", "Path B", "you choose",
                   "personally accepting that one lake", "Nothing is extrapolated", "Section B"):
        assert phrase in readme, phrase
    assert "63" in readme and "58" in readme
    assert "Honest note on size" in readme and "short of 63" in readme and "shortfall 52" in readme       # 12 lakes qualify in this synthetic world, target 64
    assert "| Step (cumulative, in this order) | Lakes left |" in readme and "| after: no datum ambiguity | 12 |" in readme
    assert "review-candidate selection, not a validation threshold" in readme and "the first 58 accepted lakes already cross the 63 threshold" in readme
    assert "best first" in readme and "stop after about 58 ACCEPTs" in readme and "PROVISIONAL" in readme and "Expected historical tier" in readme
    assert "relax" not in readme.lower()


def test_pack_id_depends_on_rows_and_seed():
    r1 = [dict(section="A", id="x", digest="d1")]
    r2 = [dict(section="A", id="x", digest="d2")]
    assert CC.pack_id_for(r1, 1) == CC.pack_id_for(r1, 1) and CC.pack_id_for(r1, 1) != CC.pack_id_for(r2, 1) and CC.pack_id_for(r1, 1) != CC.pack_id_for(r1, 2)


def test_clip_cuts_at_a_word_boundary_and_says_so():
    assert C.clip("a b c", 50) == "a b c"
    out = C.clip("one two three four five six", 12)
    assert out == "one two ..." and "thre" not in out


def test_overlay_recovered_shows_the_recovered_source_not_the_research_one():
    row = mk_row(1, provider="rise")
    b = dict(provider="rise", station="146", series="146", historyCompleteYears=73, historyClass="SUFFICIENT",
             live=[dict(note="USBR RISE daily item 146 (Buffalo Bill Reservoir Dam and Powerplants forebay); replaces research item 152 (South Fork Dike gauge)")],
             verification=dict(probe=dict(lastFt=5359.18, medianFt=5364.34, lastObservationAt="2026-10-12", ageHours=None), directoryFullPoolFt=5393.5, deltaFullPoolFt=-0.44))
    r, note = C.overlay_recovered(row, b, FakeInp())
    assert r["station"] == "146" and r["stationName"] == "Buffalo Bill Reservoir Dam and Powerplants forebay" and r["sourceId"] == "rise: 146"
    assert r["level"]["lastFt"] == 5359.18 and r["pool"]["diffNow"] == round(5359.18 - 5393.5, 3) and r["second"] is None and "replaces research source" in note
    assert any("146" in l["u"] for l in r["links"])
    same = dict(b, station=row["station"])
    r2, note2 = C.overlay_recovered(row, same, FakeInp())
    assert note2 is None and r2 is row


# ------------------------------------------------------------------------------------------------ v2: ordering, tiers, property test
def test_cards_are_best_first_and_the_first_pick_has_the_top_rank():
    rows, ctx = mk_world(20, providers=("a2w",))
    ids = sorted(rows)
    for i, l in enumerate(ids):
        ctx.bow[l] = i % 10                                                    # usefulness varies 0..9
        ctx.table[l]["historyCompleteYears"] = 5 + (i * 7) % 20                # history varies 5..24
    chosen, rep = C.select_section_a(rows, ctx, target=64)
    assert len(chosen) == 20
    base = {l: sum(C.rank_components(rows[l], ctx).values()) for l in ids}
    assert base[chosen[0]] == max(base.values())                               # the first pick carries no diversity penalty
    assert chosen == C.select_section_a(rows, ctx, target=64)[0]
    import pytest as _p
    mp = _p.MonkeyPatch()
    mp.setattr(C, "DIVERSITY_PENALTY", dict(provider=0.0, state=0.0, kind=0.0, region=0.0))
    try:
        flat, _ = C.select_section_a(rows, ctx, target=64)
    finally:
        mp.undo()
    assert [round(base[l], 3) for l in flat] == sorted([round(base[l], 3) for l in flat], reverse=True)      # without diversity the order is exactly best-first


def test_more_history_and_higher_usefulness_rank_higher_and_geometry_high_beats_medium():
    rows, ctx = mk_world(3)
    a, b, c = sorted(rows)
    ctx.table[a]["historyCompleteYears"], ctx.table[b]["historyCompleteYears"] = 20, 5
    assert sum(C.rank_components(rows[a], ctx).values()) > sum(C.rank_components(rows[b], ctx).values())
    ctx.bow[c] = 9
    ctx.bow[b] = 1
    ctx.table[b]["historyCompleteYears"] = ctx.table[c]["historyCompleteYears"] = 12
    assert sum(C.rank_components(rows[c], ctx).values()) > sum(C.rank_components(rows[b], ctx).values())
    ctx.registry[c]["geometryConfidence"] = dict(level="MEDIUM", score=0.6)
    ctx.registry[b]["geometryConfidence"] = dict(level="HIGH", score=0.94)
    ctx.bow[c] = ctx.bow[b] = 5
    assert C.rank_components(rows[b], ctx)["geometry"] > C.rank_components(rows[c], ctx)["geometry"]


def test_no_row_failing_a_gate_is_ever_selected_in_a_mixed_world():
    import random
    rng = random.Random(7)
    rows, ctx = mk_world(120, providers=("a2w", "cwms", "usgs", "rise", "nwps"))
    for l, r in rows.items():
        k = rng.randrange(14)
        if k == 0: r["rec"] = "FLAG"
        elif k == 1: r["dist"]["m"] = 400.0
        elif k == 2: ctx.registry[l]["geometryConfidence"]["level"] = rng.choice(["LOW", "MISSING", "MEDIUM"])
        elif k == 3: r["level"]["ageH"] = rng.choice([73.0, 200.0, 70.0])
        elif k == 4: ctx.table[l]["historyCompleteYears"] = rng.choice([0, 3, 4, 5, 9])
        elif k == 5: r["nameMatch"].update(sim=rng.choice([0.2, 0.59, 0.6]), station="Other Words")
        elif k == 6: ctx.coord_pack.add(l)
        elif k == 7: r["recNotes"].append(rng.choice(["short or no public history", "NOAA/NWS gauge that relays another agency's number (not an independent check)"]))
        elif k == 8: r["pool"].update(diffNow=rng.choice([-6.0, -4.0]), diff=-4.0)
        elif k == 9: ctx.registry[l].update(pointFlag="off-water", location=dict(distanceToShorelineM=rng.choice([10, 500])))
    chosen, rep = C.select_section_a(rows, ctx, target=64)
    assert chosen and len(chosen) == rep["selected"] <= 64
    for l in chosen:
        got = ev(rows[l], ctx)
        assert all(got.values()), (l, [k for k, v in got.items() if not v])
    assert set(chosen) == set(rep["funnel"]["qualifying"]) or len(chosen) == 64
    assert chosen == C.select_section_a(dict(reversed(list(rows.items()))), ctx, target=64)[0]               # deterministic


def test_packet_cards_carry_tier_geometry_and_every_warning(tmp_path):
    rows, ctx = mk_world(6)
    ids = sorted(rows)
    ctx.table[ids[0]]["historyCompleteYears"] = 5
    ctx.table[ids[1]]["historyCompleteYears"] = 12
    ctx.registry[ids[2]]["geometryConfidence"] = dict(level="MEDIUM", score=0.6)
    rows[ids[3]]["recNotes"].append("last reading is 60 h old")
    out = tmp_path / "pk"
    m, a, b = C.build(FakeInp(), ctx, rows, str(out), "sha", 3, dict(), {"bindings": []}, {"lakes": {}}, {}, {}, write=True)
    by = {r["id"]: r for r in a}
    assert by[ids[0]]["historyTier"] == "PROVISIONAL" and by[ids[1]]["historyTier"] == "STANDARD" and by[ids[4]]["historyTier"] == "FULL"
    assert by[ids[2]]["geometry"]["level"] == "MEDIUM" and "MEDIUM" in by[ids[2]]["geometry"]["text"]
    assert by[ids[3]]["warnings"] == ["last reading is 60 h old"]
    assert m["counts"]["sectionAByHistoryTier"] == {"FULL": 4, "PROVISIONAL": 1, "STANDARD": 1} and m["counts"]["sectionAByGeometry"] == {"HIGH": 5, "MEDIUM": 1}
    assert sum(sum(v.values()) for v in m["counts"]["sectionAByProviderAndTier"].values()) == 6
    csvr = {r["lake_id"]: r for r in csv.DictReader(open(out / "binding_review_consolidated.csv", encoding="utf-8-sig"))}
    assert csvr[ids[0]]["history_tier"] == "PROVISIONAL" and csvr[ids[2]]["geometry_confidence"] == "MEDIUM"
    assert [r["seq"] for r in a] == list(range(1, 7)) and [r["id"] for r in a] == [x["id"] for x in m["rows"] if x["section"] == "A"]
    html = (out / "binding_review_consolidated.html").read_text()
    assert "Expected history tier" in html and "best-first" in html and "stop there" in html


def test_section_b_never_repeats_a_section_a_lake(tmp_path):
    rows, ctx = mk_world(4)
    a_id = sorted(rows)[0]
    flagged = {a_id: dict(mk_row(1, provider="a2w"), postHoc=dict(outcome="x"))}                 # a lake that is already in Section A shows up as a B candidate
    flagged[a_id]["id"] = a_id
    m, a, b = C.build(FakeInp(), ctx, rows, str(tmp_path / "pk"), "sha", 3, dict(), {"bindings": []}, {"lakes": {}}, flagged, {}, write=False)
    assert a_id in [r["id"] for r in a] and a_id not in [r["id"] for r in b]
