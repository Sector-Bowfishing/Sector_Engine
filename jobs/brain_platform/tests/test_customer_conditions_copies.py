"""The Publisher's conditions-consolidation CUSTOMER-lane copies (Sector_Ops #53 spec §5): clarity, waterTemp, generationBinding, wind outlookModel.
Pure planners; nothing writes. Each sits behind its own env switch, default off, and mirrors the level copy's gates and UNKNOWN overwrite."""
import copy
import datetime as dt
import json
import os
import re

import pytest

from sector_brain_platform.publisher_live import customer_copies as CC
from sector_brain_platform.publisher_live import customer_clarity as CL
from sector_brain_platform.publisher_live import customer_generation_binding as GB
from sector_brain_platform.publisher_live import customer_water_temp as WT
from sector_brain_platform.publisher_live import customer_wind_outlook_model as WM

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CLARITY_BASELINE = json.load(open(os.path.join(ROOT, "brains", "water-clarity", "tests", "golden", "clarity_science_baseline.json")))
CLARITY_GOLDEN = CLARITY_BASELINE["scenarios"]
CLARITY_STALE_H = CLARITY_BASELINE["registry"]["staleAfterHours"]                         # 26
WT_GOLDEN = json.load(open(os.path.join(ROOT, "brains", "water-temperature", "tests", "golden", "water_temp_run_updates.json")))
SWIFT = os.path.join(ROOT, "Sources", "SectorEngine", "API")
ON = {v: "1" for v in CC.SWITCHES.values()}
RUN = dict(runner="pulse", publish_id="7def2674")


def swift_copy_fields(fname):
    s = open(os.path.join(SWIFT, fname)).read()
    block = s[s.index("struct CustomerCopy"):]
    block = block[:block.index("}")]
    return set(re.findall(r"let (\w+):", block))


def test_every_switch_is_the_spec_name_and_defaults_off():
    assert CC.SWITCHES == {"clarity": "PUBLISHER_CUSTOMER_CLARITY", "waterTemp": "PUBLISHER_CUSTOMER_WATER_TEMP",
                           "generationBinding": "PUBLISHER_CUSTOMER_GENERATION_BINDING", "windOutlookModel": "PUBLISHER_CUSTOMER_WIND_MODEL"}
    for name, var in CC.SWITCHES.items():
        assert not CC.enabled(name, None) and not CC.enabled(name, {}) and not CC.enabled(name, {var: "true"}) and not CC.enabled(name, {var: "0"}) and CC.enabled(name, {var: "1"})


@pytest.mark.parametrize("env", [None, {}, {"PUBLISHER_CUSTOMER_CLARITY": "0", "PUBLISHER_CUSTOMER_WIND_MODEL": "on"}])
def test_switch_off_computes_nothing_new(env):
    assert CL.plan(clarity_updates("gaugeFalling"), {}, readiness="BETA", now=CL_NOW, env=env, **RUN) == ({}, {})
    assert WT.plan(WT_GOLDEN, {}, readiness="BETA", now=WT_NOW, env=env, **RUN) == ({}, {})
    assert GB.plan(bound_contract(), {}, readiness="BETA", env=env) == ({}, {})
    assert WM.plan(wind_updates(), None, readiness="BETA", now=WIND_NOW, env=env) == ({}, "NOT_ENABLED")
    assert WM.plan(wind_updates(), {}, readiness="BETA", now=WIND_NOW, env=env) == ({}, "NOT_ENABLED")


def test_switch_off_withdraws_every_live_copy_once_with_unknown():
    off = {}
    cl = cl_plan(clarity_updates("gaugeFalling", "guntersvilleRain"))[0]
    w, why = CL.plan(clarity_updates("gaugeFalling"), cl, readiness="BETA", now=CL_NOW, env=off, **RUN)
    assert {p: c["status"] for p, c in w.items()} == {p: "UNKNOWN" for p in cl} and set(why.values()) == {"NOT_ENABLED"}
    assert CL.plan({}, {**cl, **w}, readiness="BETA", now=CL_NOW, env=off, **RUN)[0] == {}           # already UNKNOWN: not rewritten
    wt = wt_plan()[0]
    assert {p: c["status"] for p, c in WT.plan(WT_GOLDEN, wt, readiness="BETA", now=WT_NOW, env=off, **RUN)[0].items()} == {p: "UNKNOWN" for p in wt}
    gb = gb_plan()[0]
    w, why = GB.plan(bound_contract(), gb, readiness="BETA", env=off)
    assert {p: c["status"] for p, c in w.items()} == {p: "UNKNOWN" for p in gb} and why == {"Guntersville|AL": "NOT_ENABLED"}
    wm = wm_plan(wind_updates())[0][WM.PATH]
    assert WM.plan(wind_updates(), wm, readiness="BETA", now=WIND_NOW, env=off) == ({WM.PATH: WM.unknown_copy()}, "NOT_ENABLED")
    assert WM.plan(wind_updates(), WM.unknown_copy(), readiness="BETA", now=WIND_NOW, env=off) == ({}, "NOT_ENABLED")


def test_each_switch_turns_on_only_its_own_copy():
    only_wind = {"PUBLISHER_CUSTOMER_WIND_MODEL": "1"}
    assert CL.plan(clarity_updates("gaugeFalling"), {}, readiness="BETA", now=CL_NOW, env=only_wind, **RUN)[0] == {}
    assert WM.plan(wind_updates(), None, readiness="BETA", now=WIND_NOW, env=only_wind)[1] == "AVAILABLE"


def test_an_unknown_runner_is_refused():
    with pytest.raises(ValueError):
        CL.unknown_copy("x", runner="laptop", publish_id="p")


# ---------- clarity ----------
CL_NOW = dt.datetime(2026, 10, 12, 12, 0, tzinfo=dt.timezone.utc)


def clarity_updates(*names):
    u = {"brains/water-clarity/staleAfterHours": CLARITY_STALE_H}
    for n in names:
        for k, v in CLARITY_GOLDEN[n]["lakeWrites"].items():
            u[k.lstrip("/")] = copy.deepcopy(v)
    return u


def cl_plan(u, previous=None, readiness="BETA", now=CL_NOW):
    return CL.plan(u, previous or {}, readiness=readiness, now=now, env=ON, **RUN)


def test_clarity_observed_is_available_with_its_range_and_modeled_is_an_estimate():
    writes, why = cl_plan(clarity_updates("gaugeFalling", "guntersvilleRain"))
    a = writes[CL.copy_path("Gauge A|AL")]
    assert CL.copy_path("Guntersville|AL") == "customer/lakes/Guntersville_AL/clarity"
    assert a == {"schema": "sector-customer-clarity-v1", "lakeId": "Gauge A|AL", "status": "AVAILABLE", "centralFt": 3.21, "lowFt": 1.33, "highFt": 4.45,
                 "confidence": "medium", "observedAt": "2026-10-12T06:12:03Z", "freshUntil": "2026-10-13T08:12:03Z", "runner": "pulse", "publishId": "7def2674"}
    g = writes[CL.copy_path("Guntersville|AL")]
    assert g["status"] == "ESTIMATE" and g["centralFt"] == 2.52 and g["confidence"] == "low"
    assert "lowFt" not in g and "highFt" not in g                                    # absent in the state: absent in the copy, never invented
    assert why == {"Gauge A|AL": "AVAILABLE", "Guntersville|AL": "ESTIMATE"}


def test_an_old_evaluation_republished_by_a_new_run_is_stale():
    """freshUntil is run time + staleAfterHours; a new run restating a 4-day-old evaluation must not look fresh."""
    u = clarity_updates("gaugeFalling")
    st = u["lakes/Gauge_A_AL/states/waterClarity"]
    st["evaluationTime"] = "2026-10-08T12:00:00Z"                                          # 4 days before CL_NOW
    st["freshness"].update(generatedAt="2026-10-12T11:30:00Z", freshUntil="2026-10-13T13:30:00Z")
    before = {CL.copy_path("Gauge A|AL"): {"schema": CL.SCHEMA, "lakeId": "Gauge A|AL", "status": "AVAILABLE"}}
    writes, why = cl_plan(u, previous=before)
    assert why["Gauge A|AL"] == "STALE" and writes[CL.copy_path("Gauge A|AL")]["status"] == "UNKNOWN"
    no_rule = clarity_updates("gaugeFalling"); del no_rule["brains/water-clarity/staleAfterHours"]
    assert cl_plan(no_rule) == ({}, {"Gauge A|AL": "STALE"})                                   # without the Brain's rule: fail closed


def test_future_source_times_are_refused_beyond_ten_minutes():
    u = clarity_updates("gaugeFalling")
    u["lakes/Gauge_A_AL/states/waterClarity"]["evaluationTime"] = "2026-10-12T12:10:01Z"
    assert cl_plan(u)[1]["Gauge A|AL"] == "STALE"
    u["lakes/Gauge_A_AL/states/waterClarity"]["evaluationTime"] = "2026-10-12T12:10:00Z"   # exactly 10 min: allowed
    assert cl_plan(u)[1]["Gauge A|AL"] == "AVAILABLE"
    w = copy.deepcopy(WT_GOLDEN)
    w["lakes/Guntersville_AL/states/waterTemp"]["lastObservationAt"] = "2026-07-15T03:10:01Z"
    assert wt_plan(w)[1]["Guntersville|AL"] == "STALE"
    assert wm_plan(wind_updates(decidedAt="2026-11-10T12:10:01Z")) == ({}, "STALE")
    assert wm_plan(wind_updates(decidedAt="2026-11-10T12:10:00Z"))[1] == "AVAILABLE"


def test_empty_lake_id_returns_early():
    assert CL.copy_for({"lakeId": ""}, "", readiness="BETA", stale_hours=26, now=CL_NOW, **RUN) == (None, "NO_PUBLICATION")
    assert WT.copy_for({"lakeId": ""}, "", readiness="BETA", stale_hours=6, now=WT_NOW, **RUN) == (None, "NO_PUBLICATION")
    assert GB.copy_for({"lakeId": ""}, "", readiness="BETA", updated=None) == (None, "NO_PUBLICATION")


def test_clarity_observed_at_is_the_evaluation_time_never_the_run_time():
    c = cl_plan(clarity_updates("gaugeFalling"))[0][CL.copy_path("Gauge A|AL")]
    st = clarity_updates("gaugeFalling")["lakes/Gauge_A_AL/states/waterClarity"]
    assert c["observedAt"] == st["evaluationTime"] != st["generatedAt"]


@pytest.mark.parametrize("scenario,reason", [("noRain", "NO_SOURCE"), ("malformed", "STALE"), ("partial", "STALE")])
def test_clarity_fallback_unavailable_and_timeless_states_get_no_copy(scenario, reason):
    writes, why = cl_plan(clarity_updates(scenario))
    assert writes == {} and list(why.values()) == [reason]


@pytest.mark.parametrize("change,reason", [
    ({"freshness": {"stale": True, "freshUntil": "2026-10-13T08:30:00Z"}}, "STALE"),
    ({"freshness": {"stale": False, "evidenceStale": True, "freshUntil": "2026-10-13T08:30:00Z"}}, "STALE"),
    ({"freshness": {"stale": False, "freshUntil": "2026-10-12T11:59:00Z"}}, "STALE"),
    ({"freshness": {"stale": False, "freshUntil": "2026-10-13T08:30:00"}}, "STALE"),       # zoneless: never guessed
    ({"clarityFt": None}, "NO_VALUE"),
    ({"clarityFt": float("nan")}, "NO_VALUE"),
    ({"kind": "modeled"}, "NO_SOURCE"),                                                   # observed basis labelled modeled is neither
])
def test_clarity_each_failing_gate_writes_no_copy(change, reason):
    u = clarity_updates("gaugeFalling")
    u["lakes/Gauge_A_AL/states/waterClarity"].update(change)
    writes, why = cl_plan(u)
    assert writes == {} and why["Gauge A|AL"] == reason


@pytest.mark.parametrize("readiness", ["CALIBRATION", "PROFILED", None, "beta"])
def test_clarity_below_beta_writes_no_copy(readiness):
    writes, why = cl_plan(clarity_updates("gaugeFalling"), readiness=readiness)
    assert writes == {} and set(why.values()) == {"CLARITY_NOT_BETA"}


def test_a_state_whose_stored_lake_id_differs_never_writes_the_other_lakes_copy():
    """Lake keys are lossy: a state under Gauge_A_AL whose stored lakeId is another lake is that lake's state, never Gauge A|AL's."""
    before = cl_plan(clarity_updates("gaugeFalling"))[0]
    u = clarity_updates("gaugeFalling")
    u["lakes/Gauge_A_AL/states/waterClarity"]["lakeId"] = "Gauge A AL"                     # same key, different lake
    writes, why = cl_plan(u, previous=before)
    assert writes[CL.copy_path("Gauge A|AL")]["status"] == "UNKNOWN" and why["Gauge A|AL"] == "NO_PUBLICATION"
    assert CL.copy_for(u["lakes/Gauge_A_AL/states/waterClarity"], "Gauge A|AL", readiness="BETA", stale_hours=26, now=CL_NOW, **RUN) == (None, "NO_PUBLICATION")
    w = copy.deepcopy(WT_GOLDEN)
    w["lakes/Guntersville_AL/states/waterTemp"]["lakeId"] = "Guntersville AL"
    assert WT.copy_for(w["lakes/Guntersville_AL/states/waterTemp"], "Guntersville|AL", readiness="BETA", stale_hours=6, now=WT_NOW, **RUN) == (None, "NO_PUBLICATION")


def test_clarity_that_stops_passing_gets_unknown_once():
    before = cl_plan(clarity_updates("gaugeFalling"))[0]
    writes, _ = cl_plan(clarity_updates("gaugeFalling"), previous=before, readiness="CALIBRATION")
    assert writes == {CL.copy_path("Gauge A|AL"): {"schema": CL.SCHEMA, "lakeId": "Gauge A|AL", "status": "UNKNOWN", "runner": "pulse", "publishId": "7def2674"}}
    assert cl_plan(clarity_updates("gaugeFalling"), previous={**before, **writes}, readiness="CALIBRATION")[0] == {}
    gone, why = cl_plan({}, previous=before)                                              # the lake left the write set entirely
    assert gone[CL.copy_path("Gauge A|AL")]["status"] == "UNKNOWN" and why["Gauge A|AL"] == "NO_PUBLICATION"


# ---------- water temp ----------
WT_NOW = dt.datetime(2026, 7, 15, 3, 0, tzinfo=dt.timezone.utc)


def wt_plan(u=WT_GOLDEN, previous=None, readiness="BETA", now=WT_NOW):
    return WT.plan(u, previous or {}, readiness=readiness, now=now, env=ON, **RUN)


def test_water_temp_measured_is_available_with_the_brains_own_freshness():
    writes, why = wt_plan()
    assert WT.stale_after_hours(WT_GOLDEN) == 6
    assert writes == {WT.copy_path("Guntersville|AL"): {"schema": "sector-customer-water-temp-v1", "lakeId": "Guntersville|AL", "status": "AVAILABLE",
                      "valueF": 80.6, "kind": "measured", "observedAt": "2026-07-15T01:00:00Z", "freshUntil": "2026-07-15T07:00:00Z",
                      "runner": "pulse", "publishId": "7def2674"}}
    assert why == {"Guntersville|AL": "AVAILABLE", "Lake Hartwell|SC": "NO_OBSERVATION_TIME", "Wheeler|AL": "NO_OBSERVATION_TIME"}   # the modeled gap


@pytest.mark.parametrize("change,reason", [
    ({"stale": True}, "STALE"),
    ({"evidenceStale": True}, "STALE"),
    ({"evidenceStale": None}, "STALE"),
    ({"lastObservationAt": None}, "NO_OBSERVATION_TIME"),
    ({"lastObservationAt": "2026-07-14T20:59:00Z"}, "STALE"),                              # observation + 6 h is before now
    ({"currentTempF": None}, "NO_VALUE"),
    ({"unit": "degC"}, "NO_VALUE"),
    ({"kind": "unavailable"}, "NO_SOURCE"),
])
def test_water_temp_each_failing_gate_writes_no_copy(change, reason):
    u = copy.deepcopy(WT_GOLDEN)
    u["lakes/Guntersville_AL/states/waterTemp"].update(change)
    writes, why = wt_plan(u)
    assert writes == {} and why["Guntersville|AL"] == reason


def test_water_temp_without_the_brains_stale_rule_writes_nothing_and_below_beta_clears():
    u = copy.deepcopy(WT_GOLDEN)
    del u["brains/water-temp"]
    assert wt_plan(u)[0] == {} and wt_plan(u)[1]["Guntersville|AL"] == "STALE"
    before = wt_plan()[0]
    cleared = wt_plan(previous=before, readiness="CALIBRATION")[0]
    assert {p: c["status"] for p, c in cleared.items()} == {WT.copy_path("Guntersville|AL"): "UNKNOWN"}


# ---------- generation binding ----------
def bound_contract():
    c = GB.load_contract()
    for r in c["reviewed"]:
        if r["lakeId"] == "Guntersville|AL":
            r["damBinding"] = {"operatorId": "tva", "damId": "tva:GUH", "damName": "Guntersville Dam", "tvaCode": "GUH"}
    return c


def gb_plan(contract=None, previous=None, readiness="BETA"):
    return GB.plan(contract if contract is not None else bound_contract(), previous or {}, readiness=readiness, env=ON)


def test_generation_binding_today_has_no_dam_binding_so_nothing_is_written():
    writes, why = GB.plan(GB.load_contract(), {}, readiness="BETA", env=ON)
    assert writes == {} and set(why.values()) == {"NO_DAM_BINDING"} and len(why) == 5        # the documented Lake gap


def test_generation_binding_copies_only_the_published_dam_binding():
    writes, why = gb_plan()
    assert GB.copy_path("Guntersville|AL") == "customer/lakes/Guntersville_AL/generationBinding"
    assert writes == {GB.copy_path("Guntersville|AL"): {"schema": "sector-customer-generation-binding-v1", "lakeId": "Guntersville|AL", "operatorId": "tva",
                      "damId": "tva:GUH", "damName": "Guntersville Dam", "tvaCode": "GUH", "updatedAt": "2026-10-13T00:00:00Z"}}
    assert why["Wheeler|AL"] == "NO_DAM_BINDING"
    c = bound_contract(); c["reviewedAt"] = "2026-11-01T10:00:00Z"
    assert gb_plan(c)[0][GB.copy_path("Guntersville|AL")]["updatedAt"] == "2026-11-01T10:00:00Z"
    c["reviewedAt"] = "2026-11-01T10:00:00"                                                # zoneless: unparseable, never assumed UTC
    assert gb_plan(c) == ({}, {lid: "NO_REVIEW_TIME" for lid in GB._records(c)})


@pytest.mark.parametrize("mutate,reason", [
    (lambda c: c.update(bindingVersion="unversioned"), "NO_REVIEW_TIME"),
    (lambda c: c["reviewed"][0]["damBinding"].pop("damName"), "NO_VALUE"),
    (lambda c: c["reviewed"][0]["damBinding"].update(operatorId=""), "NO_VALUE"),
])
def test_generation_binding_gates(mutate, reason):
    c = bound_contract()
    assert c["reviewed"][0]["lakeId"] == "Guntersville|AL"
    mutate(c)
    writes, why = gb_plan(c)
    assert writes == {} and why["Guntersville|AL"] == reason


def test_generation_binding_wrong_contract_or_demoted_lake_clears_old_copies():
    before = gb_plan()[0]
    for bad in ({**bound_contract(), "schema": "reviewed-lake-bindings-v2"}, {**bound_contract(), "owner": "water-temp"}, {}):
        writes, _ = gb_plan(bad, previous=before)
        assert {p: c["status"] for p, c in writes.items()} == {GB.copy_path("Guntersville|AL"): "UNKNOWN"}
    writes, why = gb_plan(previous=before, readiness="CALIBRATION")
    assert writes[GB.copy_path("Guntersville|AL")]["status"] == "UNKNOWN" and why["Guntersville|AL"] == "LAKE_NOT_BETA"


# ---------- wind outlook model ----------
WIND_NOW = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)


def wind_updates(**block):
    b = {"tonight": "best_match", "nights2to7": "ncep_nbm_conus", "decidedBy": "owner (Sector_Ops #44)", "evidence": "W1 NBM night point wind SUPPORTED",
         "decidedAt": "2026-11-05T12:00:00Z", **block}
    return {"brains/wind/activeProductionModel": {"modelId": "open-meteo-best-match", "outlookModel": b}}


def wm_plan(u, previous=None, readiness="BETA", now=WIND_NOW):
    return WM.plan(u, previous, readiness=readiness, now=now, env=ON)


def test_wind_outlook_model_copy():
    writes, why = wm_plan(wind_updates())
    assert writes == {"customer/wind/outlookModel": {"schema": "sector-customer-wind-outlook-model-v1", "tonight": "best_match", "nights2to7": "ncep_nbm_conus",
                      "decidedBy": "owner (Sector_Ops #44)", "evidence": "W1 NBM night point wind SUPPORTED", "updatedAt": "2026-11-05T12:00:00Z"}}
    assert why == "AVAILABLE"


def test_wind_today_publishes_no_decision():
    import importlib.util
    spec = importlib.util.spec_from_file_location("wind_contract", os.path.join(ROOT, "brains", "wind", "runtime", "sector_wind", "brain", "contract.py"))
    WC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(WC)                                                            # the Wind Brain's real activeProductionModel
    assert wm_plan({"brains/wind/activeProductionModel": WC.PRODUCTION_MODEL}) == ({}, "NO_PUBLICATION")


@pytest.mark.parametrize("block,reason", [
    ({"tonight": "ncep_nbm_conus"}, "NO_VALUE"),                                           # WS-5
    ({"nights2to7": "gfs_global"}, "NO_VALUE"),
    ({"decidedBy": ""}, "NO_VALUE"),
    ({"decidedAt": "2026-10-27T11:59:00Z"}, "STALE"),                                      # older than 14 days
    ({"decidedAt": "2026-11-05T12:00:00"}, "STALE"),                                       # zoneless
])
def test_wind_gates(block, reason):
    assert wm_plan(wind_updates(**block)) == ({}, reason)


def test_wind_decision_that_stops_passing_gets_unknown_once():
    before = wm_plan(wind_updates())[0]["customer/wind/outlookModel"]
    assert wm_plan(wind_updates(), previous=before, readiness="CALIBRATION") == ({"customer/wind/outlookModel": {"schema": WM.SCHEMA, "status": "UNKNOWN"}}, "WIND_NOT_BETA")
    assert wm_plan(wind_updates(), previous={"schema": WM.SCHEMA, "status": "UNKNOWN"}, readiness="CALIBRATION") == ({}, "WIND_NOT_BETA")


# ---------- the Engine reads what the Publisher writes ----------
@pytest.mark.parametrize("fname,copy_fn", [
    ("ClarityBrainOutput.swift", lambda: cl_plan(clarity_updates("gaugeFalling"))[0][CL.copy_path("Gauge A|AL")]),
    ("WaterTempBrainOutput.swift", lambda: wt_plan()[0][WT.copy_path("Guntersville|AL")]),
    ("GenerationBindingOutput.swift", lambda: gb_plan()[0][GB.copy_path("Guntersville|AL")]),
    ("WindOutlookModelOutput.swift", lambda: wm_plan(wind_updates())[0]["customer/wind/outlookModel"]),
])
def test_publisher_copy_fields_are_exactly_what_the_engine_decodes(fname, copy_fn):
    c = copy_fn()
    fields = swift_copy_fields(fname)
    assert set(c) <= fields, set(c) - fields
    schema = re.search(r'copySchema = "([^"]+)"', open(os.path.join(SWIFT, fname)).read()).group(1)
    assert c["schema"] == schema


def test_copy_paths_match_the_engine():
    s = open(os.path.join(SWIFT, "WindOutlookModelOutput.swift")).read()
    assert f'copyPath = "{WM.PATH}"' in s
    for fname, mod in (("ClarityBrainOutput.swift", CL), ("WaterTempBrainOutput.swift", WT), ("GenerationBindingOutput.swift", GB)):
        tail = re.search(r'"customer/lakes/\\\(BrainPlatform\.lakeKey\(lakeId\)\)/(\w+)"', open(os.path.join(SWIFT, fname)).read()).group(1)
        assert mod.copy_path("A|B").endswith("/" + tail)


# ---------- registration ----------
def test_every_copy_path_is_a_registered_placeholder_customer_family_and_in_the_matrix():
    from sector_brain_platform.publisher.paths import CUSTOMER_COPY_FAMILIES
    from sector_brain_platform.publisher.registry import default_registry
    written = [CL.copy_path("Guntersville|AL"), WT.copy_path("Guntersville|AL"), GB.copy_path("Guntersville|AL"), WM.PATH,
               "customer/lakes/Guntersville_AL/level"]
    for p in written:
        fams = [f for f in CUSTOMER_COPY_FAMILIES if f.match("/" + p)]
        assert len(fams) == 1 and fams[0].status == "PLACEHOLDER", p
    assert not any(f.match("/customer/lakes/Guntersville_AL/states") for f in CUSTOMER_COPY_FAMILIES)
    for spec in default_registry()._specs.values():                                        # no Brain artifact can target a customer copy
        assert not any(fam.pattern.startswith("/customer/") for fam in spec.families + spec.delete_families), spec.schema_id
    matrix = json.load(open(os.path.join(ROOT, "docs", "architecture", "data", "RTDB_PATH_OWNERSHIP_MATRIX.json")))
    rows = {r["path"]: r for r in matrix["paths"]}
    md = open(os.path.join(ROOT, "docs", "architecture", "data", "RTDB_PATH_OWNERSHIP_MATRIX.md")).read()
    for f in CUSTOMER_COPY_FAMILIES:
        path = f.pattern.replace("{k}", "{lakeKey}")
        assert rows[path]["targetOwner"] == "platform.publisher-live" and rows[path]["problem"].startswith("PLACEHOLDER")
        assert f"| `{f.pattern}` |" in md


def test_the_proposed_rules_deny_every_client_on_every_copy_and_change_nothing_else():
    sec = os.path.join(ROOT, "platform", "security")
    target = json.load(open(os.path.join(sec, "rtdb.rules.target.json")))["rules"]
    proposed = json.load(open(os.path.join(sec, "rtdb.rules.customer-copies.PROPOSED.json")))["rules"]
    assert "customer" not in target                                                       # the target (and today) has no customer grant: root deny
    assert {k: v for k, v in proposed.items() if k != "customer"} == target
    cust = proposed["customer"]

    def grants(node):
        for k, v in node.items():
            if k in (".read", ".write"):
                assert v is False, k
            elif isinstance(v, dict):
                grants(v)
    grants(cust)
    assert set(cust["lakes"]["$lakeKey"]) == {"level", "clarity", "waterTemp", "generationBinding"} and set(cust["wind"]) == {"outlookModel"}
