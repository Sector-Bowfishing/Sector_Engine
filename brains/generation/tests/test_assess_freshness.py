"""Release status rules and the adaptive refresh cadence (pure). Hand-built inputs; each case states the rule it pins."""
import datetime as dt

from generation_brain import contract as C
from generation_brain.assess import assess, transitions
from generation_brain.freshness import decide, due, schedule_fingerprint
from generation_brain.sources import Reading

NOW = dt.datetime(2026, 11, 22, 20, 0, tzinfo=dt.timezone.utc)


def t(h, m=0):
    return C.iso(NOW + dt.timedelta(hours=h, minutes=m))


def win(a, b, units=None, mw=None):
    w = {"start": t(a), "end": t(b), "statedBy": "operator"}
    if units is not None:
        w["unitsOn"], w["unitsOnIsMinimum"] = units, False
    if mw is not None:
        w["generationMw"] = mw
    return w


def reading(provider, obs=(), schedule=(), cadence=60, lag=60):
    return Reading(provider, provider.upper(), True, None, list(obs), list(schedule), [provider], cadence, lag)


def test_measured_turbine_flow_is_generating_and_spill_is_flagged():
    a = assess([reading("cwms", [{"at": t(-1), "dischargeCfs": 9000.0, "turbineCfs": 7000.0, "spillCfs": 2000.0}], cadence=60, lag=120)], NOW)
    r = a["release"]
    assert a["kind"] == C.OBSERVED and r["status"] == C.GENERATING and r["generating"] is True and r["spilling"] is True and r["statusBasis"] == "MEASURED"


def test_measured_zero_is_off_and_spill_only_is_spilling():
    assert assess([reading("cwms", [{"at": t(-1), "dischargeCfs": 0.0}])], NOW)["release"]["status"] == C.OFF
    assert assess([reading("cwms", [{"at": t(-1), "dischargeCfs": 500.0, "turbineCfs": 0.0, "spillCfs": 500.0}])], NOW)["release"]["status"] == C.SPILLING


def test_tva_outflow_with_units_scheduled_this_hour_is_generating_and_without_is_releasing():
    obs = [{"at": t(-1), "dischargeCfs": 19500.0}]
    a = assess([reading("tva", obs, [win(-4, 1, units=1), win(1, 3, units=0)])], NOW)
    assert a["release"]["status"] == C.GENERATING and a["release"]["statusBasis"] == "MEASURED_AND_SCHEDULE"
    b = assess([reading("tva", obs, [win(-4, 1, units=0)])], NOW)
    assert b["release"]["status"] == C.RELEASING and b["release"]["generating"] is False


def test_stale_measurement_falls_back_to_the_schedule_and_says_so():
    a = assess([reading("tva", [{"at": t(-6), "dischargeCfs": 19500.0}], [win(-1, 2, units=2)])], NOW)     # ceiling 60 + 3x60 = 4 h
    assert a["kind"] == C.SCHEDULE_ONLY and a["release"]["status"] == C.GENERATING and a["release"]["statusBasis"] == "SCHEDULE"
    assert a["release"]["dischargeCfs"] is None and "schedule for this hour" in a["gaps"][0]


def test_nothing_current_is_unknown_never_off():
    a = assess([reading("tva", [{"at": t(-30), "dischargeCfs": 0.0}])], NOW)
    assert a["kind"] == C.UNAVAILABLE and a["release"]["status"] == C.UNKNOWN


def test_a_downstream_gauge_is_labelled_and_the_operator_wins_when_both_are_current():
    g = assess([reading("usgs", [{"at": t(-1), "dischargeCfs": 3000.0}])], NOW)
    assert g["release"]["downstreamGauge"] is True and "not the dam's own release" in g["gaps"][0]
    both = assess([reading("usgs", [{"at": t(-1), "dischargeCfs": 3000.0}]), reading("cwms", [{"at": t(-1), "dischargeCfs": 3500.0}], lag=120)], NOW)
    assert both["release"]["source"] == "cwms" and both["release"]["dischargeCfs"] == 3500.0


def test_megawatts_are_never_turned_into_units():
    a = assess([reading("swpa", [], [win(-1, 2, mw=110.0)], cadence=1440, lag=0)], NOW)
    assert a["release"]["status"] == C.GENERATING and a["schedule"]["unitsStated"] is False and "unitsOn" not in a["schedule"]["windows"][0]


def test_transitions_name_the_next_start_and_stop():
    s = [win(-2, 1, units=1), win(1, 3, units=0), win(3, 7, units=3), win(7, 10, units=0)]
    tr = transitions(s, NOW)
    assert tr == {"nextReleaseStartAt": t(3), "nextShutdownAt": t(1), "scheduleCoversUntil": t(10)}


def _decide(a, prev=None):
    return decide(a, prev, NOW)


def test_tier_transition_when_a_stop_is_within_two_hours():
    a = assess([reading("tva", [{"at": t(-1), "dischargeCfs": 19500.0}], [win(-4, 1, units=1), win(1, 30, units=0)])], NOW)
    f = _decide(a)
    assert f["tier"] == C.TIER_TRANSITION and f["recheckMinutes"] == 60 and "stops generation" in f["reason"]


def test_tier_transition_when_the_schedule_changed_or_the_status_changed():
    s = [win(-4, 30, units=1)]
    a = assess([reading("tva", [{"at": t(-1), "dischargeCfs": 19500.0}], s)], NOW)
    prev = {"release": {"status": C.GENERATING}, "provenance": {"scheduleFingerprint": "old"}}
    assert _decide(a, prev)["tier"] == C.TIER_TRANSITION and "schedule changed" in _decide(a, prev)["reason"]
    prev2 = {"release": {"status": C.OFF}, "provenance": {"scheduleFingerprint": schedule_fingerprint(a["schedule"])}}
    assert "OFF -> GENERATING" in _decide(a, prev2)["reason"]


def test_tier_transition_on_a_measured_jump():
    obs = [{"at": t(-h), "dischargeCfs": 3000.0} for h in range(8, 3, -1)] + [{"at": t(-1), "dischargeCfs": 14000.0}]
    f = _decide(assess([reading("cwms", obs, lag=120)], NOW))
    assert f["tier"] == C.TIER_TRANSITION and "+11000 cfs" in f["reason"]


def test_active_steady_unknown_cadence_and_the_hourly_floor():
    steady_obs = [{"at": t(-h), "dischargeCfs": 14000.0} for h in range(6, 0, -1)]
    active = _decide(assess([reading("cwms", steady_obs, lag=120)], NOW))
    assert active["tier"] == C.TIER_ACTIVE and active["recheckMinutes"] == 120
    off = [{"at": t(-h), "dischargeCfs": 0.0} for h in range(6, 0, -1)]
    st = _decide(assess([reading("cwms", off, lag=120)], NOW))
    assert st["tier"] == C.TIER_STEADY and st["recheckMinutes"] == 180
    soon = _decide(assess([reading("tva", off, [win(-5, 3, units=0), win(3, 20, units=2)])], NOW))      # start in 3 h -> 2 h, not 3 h
    assert soon["tier"] == C.TIER_STEADY and soon["recheckMinutes"] == 120
    unk = _decide(assess([], NOW))
    assert unk["tier"] == C.TIER_UNKNOWN and unk["recheckMinutes"] == 120 and unk["stale"] is True
    for f in (active, st, soon, unk):
        assert f["recheckMinutes"] >= 60                                     # owner rule: never more than hourly


def test_fresh_until_is_bounded_by_the_source_ceiling_and_held_to_the_refresh_latency():
    a = assess([reading("cwms", [{"at": t(-1), "dischargeCfs": 14000.0}], cadence=60, lag=120)], NOW)
    f = _decide(a)
    assert f["freshUntil"] == t(2, 30)                                       # max(reading+120, now+150) < ceiling (reading+300)
    b = assess([reading("cwms", [{"at": t(-4, -30), "dischargeCfs": 14000.0}], cadence=60, lag=120)], NOW)
    assert _decide(b)["freshUntil"] == t(0, 30)                              # the source's stale limit wins (lag 120 + 3 x 60)


def test_schedule_only_state_is_current_until_the_window_ends_at_most_six_hours():
    a = assess([reading("tva", [], [win(-1, 2, units=2), win(2, 30, units=0)])], NOW)
    assert _decide(a)["freshUntil"] == t(2)


def test_due_honours_next_check_with_the_planner_tolerance():
    assert due(None, NOW) is True
    assert due({"freshness": {"nextCheckAt": t(0, 9)}}, NOW) is True
    assert due({"freshness": {"nextCheckAt": t(0, 30)}}, NOW) is False
