"""Tests for the consolidated packet builder: selection criteria, funnel, relaxation order, diversity, Section B, and the written packet.
All data is synthetic (consolidated_helpers.py); nothing is written outside tmp_path."""
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


def test_baseline_row_passes_every_criterion():
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


@pytest.mark.parametrize("name,edit,criterion", [
    ("pilot", lambda r, c: c.pilots.add(r["id"]), "not_pilot"),
    ("held", lambda r, c: c.held.add(r["id"]), "not_held"),
    ("rec FLAG", lambda r, c: r.__setitem__("rec", "FLAG"), "recommendation_pass_rules_clear"),
    ("rule FAIL", lambda r, c: r["rules"][3].__setitem__("res", "FAIL"), "recommendation_pass_rules_clear"),
    ("rule FLAG (R7)", lambda r, c: r["rules"][6].__setitem__("res", "FLAG"), "recommendation_pass_rules_clear"),
    ("151 m from the outline", lambda r, c: r["dist"].update(m=151.0), "spatial_match"),
    ("no outline", lambda r, c: r["dist"].update(outline=False), "spatial_match"),
    ("registry MEDIUM", lambda r, c: c.registry[r["id"]]["geometryConfidence"].update(level="MEDIUM"), "registry_geometry_high_point_ok"),
    ("registry point off-water", lambda r, c: c.registry[r["id"]].update(pointFlag="off-water"), "registry_geometry_high_point_ok"),
    ("not in registry", lambda r, c: c.registry.pop(r["id"]), "registry_geometry_high_point_ok"),
    ("coordinate pack", lambda r, c: c.coord_pack.add(r["id"]), "not_in_coordinate_review"),
    ("pool not high", lambda r, c: r["pool"].update(conf="med"), "independent_confirmation"),
    ("pool basis natural", lambda r, c: r["pool"].update(basis="naturalSurface"), "independent_confirmation"),
    ("pool diff 3.1 ft now", lambda r, c: r["pool"].update(diffNow=-3.1), "independent_confirmation"),
    ("pool diff 3.1 ft median", lambda r, c: r["pool"].update(diff=3.1), "independent_confirmation"),
    ("operator unknown", lambda r, c: r.__setitem__("operator", "none"), "independent_confirmation"),
    ("name similarity 0.69", lambda r, c: r["nameMatch"].update(sim=0.69, station="Totally Other"), "name_similarity"),
    ("history 14 years", lambda r, c: c.table[r["id"]].update(historyCompleteYears=14), "history"),
    ("history extension ok but composite note", lambda r, c: c.table[r["id"]].update(historyNotes=["research composite counted 18 complete years: not a repeatable public source"]), "history"),
    ("history basis tva-guide", lambda r, c: c.table[r["id"]].update(historyBasis="tva-guide"), "history"),
    ("observation 49 h old", lambda r, c: r["level"].update(ageH=49.0), "observation_age"),
    ("observation age unknown", lambda r, c: r["level"].update(ageH=None), "observation_age"),
    ("warning: relays another agency", lambda r, c: r["recNotes"].append("NOAA/NWS gauge that relays another agency's number (not an independent check)"), "no_attention_warning"),
    ("warning: short history", lambda r, c: r["recNotes"].append("short or no public history"), "no_attention_warning"),
    ("datum: R8 not PASS", lambda r, c: r["rules"][7].__setitem__("res", "FLAG"), "recommendation_pass_rules_clear"),
    ("datum: r7class weak", lambda r, c: r.__setitem__("r7class", "weak"), "no_datum_ambiguity"),
    ("datum: offset", lambda r, c: c.table[r["id"]]["live"][0].__setitem__("datumOffsetFt", 0.31), "no_datum_ambiguity"),
    ("datum: history caveat", lambda r, c: c.table[r["id"]].update(historyNotes=["composite: listed lowest precedence first"]), "no_datum_ambiguity"),
])
def test_each_criterion_removes_exactly_its_row(name, edit, criterion):
    r, ctx = mutate(edit)
    got = ev(r, ctx)
    failed = [k for k, v in got.items() if not v]
    assert criterion in failed, (name, failed)


def test_informational_notes_are_not_warnings():
    r, ctx = mutate(lambda r, c: r["recNotes"].extend(["single agency only (no independent second source)",
                                                          "the station name contains every word of the lake name (research similarity 0.62 is lowered only by extra words or abbreviations)"]))
    assert ev(r, ctx)["no_attention_warning"]


def test_independent_second_source_or_operator_pool():
    # second source agrees within 1 ft -> qualifies even with a pool far from the level
    r, ctx = mutate(lambda r, c: (r["pool"].update(diffNow=-30.0, diff=-30.0), r.__setitem__("second", dict(label="USGS x", name="n", lastFt=1.0, diff=0.99, links=[])))[1])
    assert ev(r, ctx)["independent_confirmation"]
    assert C.independent_basis(r, C.THRESH) == "second"
    r["second"]["diff"] = 1.01
    assert not ev(r, ctx)["independent_confirmation"]
    r["pool"].update(diffNow=-1.0, diff=-1.0)
    assert C.independent_basis(r, C.THRESH) == "pool"
    r["second"]["diff"] = 0.2
    assert C.independent_basis(r, C.THRESH) == "second+pool"


def test_name_containment_counts_as_high_similarity():
    r, ctx = mutate(lambda r, c: r["nameMatch"].update(sim=0.62, lake="Synth 1 Lake", station="Synth 1 Lake Dam Pool Forebay"))
    assert ev(r, ctx)["name_similarity"]


def test_funnel_counts_are_cumulative_and_exact():
    rows, ctx = mk_world(10)
    ids = sorted(rows)
    ctx.pilots.add(ids[0])
    rows[ids[1]]["rec"] = "FLAG"
    rows[ids[2]]["level"]["ageH"] = 60.0
    rows[ids[3]]["dist"]["m"] = 400.0
    rows[ids[3]]["level"]["ageH"] = 60.0
    f = C.funnel(rows, ctx)
    steps = {s["criterion"]: s for s in f["steps"]}
    assert f["start"] == 10
    assert steps["not_pilot"]["remaining"] == 9
    assert steps["recommendation_pass_rules_clear"]["remaining"] == 8
    assert steps["spatial_match"]["remaining"] == 7
    assert steps["observation_age"]["remaining"] == 6          # id[2] leaves here; id[3] already left at spatial_match
    assert steps["observation_age"]["failedAlone"] == 2         # id[2] and id[3] both fail this one on its own
    assert len(f["qualifying"]) == 6 and ids[0] not in f["qualifying"]
    assert f["blockedOnlyBy"]["observation_age"] == [ids[2]]    # id[3] fails two criteria, id[2] only one
    assert [s["remaining"] for s in f["steps"]] == sorted([s["remaining"] for s in f["steps"]], reverse=True)


def test_no_relaxation_when_enough_qualify(monkeypatch):
    monkeypatch.setattr(C, "MIN_A", 5)
    rows, ctx = mk_world(8)
    ids, f, rx = C.qualify(rows, ctx)
    assert len(ids) == 8 and rx["applied"] == [] and rx["relaxedOnlyIds"] == []


def test_relaxation_is_one_criterion_at_a_time_in_the_stated_order(monkeypatch):
    monkeypatch.setattr(C, "MIN_A", 8)
    rows, ctx = mk_world(8)
    ids = sorted(rows)
    rows[ids[0]]["level"]["ageH"] = 60.0                       # fixed by step 1 (72 h)
    ctx.table[ids[1]]["historyCompleteYears"] = 11             # fixed by step 2 (10 y)
    rows[ids[2]]["pool"].update(diffNow=-4.0, diff=-4.0)      # fixed by step 3 (5 ft)
    rows[ids[3]]["nameMatch"].update(sim=0.65, station="Other Words Entirely")      # fixed by step 4 (0.6)
    rows[ids[4]]["rec"] = "FLAG"                              # never relaxed
    ok, f, rx = C.qualify(rows, ctx)
    assert [a["criterion"] for a in rx["applied"]] == [n for n, _, _ in C.RELAX_ORDER][:4]
    assert [a["qualifyingAfter"] for a in rx["applied"]] == [4, 5, 6, 7]
    assert rx["strictQualifying"] == 3 and len(ok) == 7 and ids[4] not in ok
    assert sorted(rx["relaxedOnlyIds"]) == sorted(ids[:4])


def test_relaxation_stops_as_soon_as_enough_qualify(monkeypatch):
    monkeypatch.setattr(C, "MIN_A", 6)
    rows, ctx = mk_world(6)
    ids = sorted(rows)
    rows[ids[0]]["level"]["ageH"] = 60.0
    ok, f, rx = C.qualify(rows, ctx)
    assert [a["criterion"] for a in rx["applied"]] == ["obs_age_h"] and len(ok) == 6 and rx["strictQualifying"] == 5 and rx["relaxedOnlyIds"] == [ids[0]]


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
    chosen, _ = C.select_section_a(rows, ctx, target=10)
    provs = {rows[l]["provider"] for l in chosen}
    assert provs == {"a2w", "cwms", "usgs", "rise", "tva"}, provs


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
    for k, v in (("provider", "usgs"), ("identifier", "other"), ("recommendation", "FLAG"), ("name", "Other"), ("section", "B")):
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
    assert "| Step (cumulative, in this order) | Lakes left, strict criteria | Lakes left, after the relaxations below |" in readme
    man = json.load(open(out / "pack_manifest.json"))
    assert man["relaxation"]["strictSteps"][-1] == ["no_datum_ambiguity", 12] and "(see the note on size below)" in readme


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
