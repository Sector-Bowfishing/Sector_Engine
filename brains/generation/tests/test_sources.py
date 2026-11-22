"""Source readers on the labelled hand-built fixtures (tests/fixtures/hand-built, index.json `label`): each parses exactly what the source
publishes, converts units, and refuses rather than guesses. Offline."""
import datetime as dt
import json
import os

from generation_brain.http import Response
from generation_brain.sources import cwms, rise, swpa, tva, usgs
from generation_support import FIXTURES, NOW, fetcher


def fx(name):
    return open(os.path.join(FIXTURES, name), "rb").read()


def test_fixtures_are_labelled_hand_built():
    assert json.load(open(os.path.join(FIXTURES, "index.json")))["label"].startswith("HAND-BUILT FIXTURES")


# ---- TVA ------------------------------------------------------------------------------------------------------------------------------------
def test_tva_schedule_windows_carry_the_dams_own_zone_and_end_midnight_on_the_next_day():
    w = tva.parse_schedule(fx("tva-GVDA1-generation-releases.json"))
    assert [x["unitsOn"] for x in w] == [0, 2, 1, 0, 3, 0]
    assert w[0]["start"] == "2026-11-22T06:00:00Z" and w[2] == {"start": "2026-11-22T16:00:00Z", "end": "2026-11-22T21:00:00Z", "unitsOn": 1,
                                                                 "unitsOnIsMinimum": False, "statedBy": "operator"}
    assert w[4]["unitsOnIsMinimum"] is True                                  # "3 or more" is a floor
    assert w[-1]["end"] == "2026-11-23T06:00:00Z"                            # "9 PM - Midnight CST" ends at 24:00


def test_tva_observed_rows_are_hour_ending_and_midnight_is_the_next_day():
    obs = tva.parse_observed(fx("tva-GVDA1-observed-data-48-hours.json"))
    at = [o["at"] for o in obs]
    assert "2026-11-22T06:00:00Z" in at                                      # "11/21 Midnight CST" = 11/22 00:00 CST, never 11/21 00:00
    assert "2026-11-21T06:00:00Z" not in at
    assert obs[-1] == {"at": "2026-11-22T19:00:00Z", "dischargeCfs": 19500.0, "tailwaterFt": 556.18}   # "19,500" comma-grouped


def test_tva_blank_discharge_stays_missing_and_pool_elevation_is_never_read():
    obs = tva.parse_observed(fx("tva-GVDA1-observed-data-48-hours.json"))
    blank = next(o for o in obs if o["at"] == "2026-11-21T12:00:00Z")
    assert "dischargeCfs" not in blank and blank["tailwaterFt"]
    assert all("reservoirFt" not in o and "ReservoirElevation" not in o for o in obs)


def test_tva_html_explorer_page_is_refused_not_parsed():
    assert tva.parse_schedule(fx("tva-explorer.html")) is None and tva.parse_observed(fx("tva-explorer.html")) is None


def test_tva_without_the_json_accept_header_gets_the_explorer_and_fails():
    f = fetcher()
    r = tva.read({"locationId": "GVDA1"}, f, NOW)
    assert r.ok and r.schedule and r.observations
    from generation_brain.fixtures import fixture_transport
    tr = fixture_transport(FIXTURES)
    bad = fetcher(transport=lambda u, h, t: tr(u, {**h, "Accept": "text/html"}, t))
    r2 = tva.read({"locationId": "GVDA1"}, bad, NOW)
    assert not r2.ok and "not JSON" in r2.error


def test_tva_time_helpers():
    assert tva.hour("Midnight") == 0 and tva.hour("Noon") == 12 and tva.hour("12 AM") == 0 and tva.hour("12 PM") == 12 and tva.hour("3 PM") == 15
    assert tva.hour("13 PM") is None and tva.number("32,614") == 32614.0 and tva.number("") is None and tva.number("0") == 0.0


# ---- CWMS -----------------------------------------------------------------------------------------------------------------------------------
def _cwms_transport(files):
    def t(url, headers, timeout):
        for key, name in files.items():
            if key in url:
                return Response(200, fx(name))
        return Response(404, b"")
    return t


def test_cwms_reads_bound_series_and_converts_si():
    f = fetcher(transport=_cwms_transport({"Flow-Out": "cwms-outflow.json", "Flow-Turb": "cwms-turbine-cms.json", "Flow-Spill": "cwms-spill.json",
                                           "Elev-Tail": "cwms-tailwater-m.json"}))
    b = {"office": "SWL", "discharge": "Example_Dam.Flow-Out.Ave.1Hour.1Hour.Rev", "turbine": "Example_Dam.Flow-Turb.Ave.1Hour.1Hour.Rev",
         "spill": "Example_Dam.Flow-Spill.Ave.1Hour.1Hour.Rev", "tailwater": "Example_Dam.Elev-Tail.Inst.1Hour.0.Rev"}
    r = cwms.read(b, f, NOW)
    assert r.ok and r.error is None
    last = r.observations[-1]
    assert last["at"] == "2026-11-22T19:00:00Z" and last["dischargeCfs"] == 14100.0 and last["spillCfs"] == 0.0
    assert abs(last["turbineCfs"] - 399.3 * 35.3146667) < 0.01 and abs(last["tailwaterFt"] - 140.0 * 3.28084) < 0.001
    assert not any(o["at"] == "2026-11-22T20:00:00Z" for o in r.observations)            # a null value is dropped, never zero-filled


def test_cwms_refuses_an_unknown_unit_and_a_modeled_version():
    rows, why = cwms.parse(fx("cwms-bad-unit.json"), "dischargeCfs")
    assert rows is None and "kcfs" in why
    f = fetcher(transport=_cwms_transport({}))
    r = cwms.read({"office": "SWL", "discharge": "X.Flow-Out.Ave.1Hour.1Hour.Fcst-FX"}, f, NOW)
    assert not r.ok and "forecast or modeled" in r.error and f.requests == []


# ---- SWPA -----------------------------------------------------------------------------------------------------------------------------------
def test_swpa_publishes_megawatts_never_units_or_cfs():
    allow = {**fetcher().access, "swpa": {**fetcher().access["swpa"], "status": "ALLOWED"}}
    f = fetcher(access=allow, transport=lambda u, h, t: Response(200, fx("swpa-sun.htm")))
    r = swpa.read({"project": "BSD"}, f, NOW)
    assert r.ok and r.observations == []
    assert all("unitsOn" not in w and w["unitsStated"] is False for w in r.schedule)
    assert [w["generationMw"] for w in r.schedule] == [0.0, 110.0, 55.0, 0.0, 165.0, 0.0]
    assert r.schedule[1]["start"] == "2026-11-22T12:00:00Z"                  # hour-ending row 7 = 6 AM CST


def test_swpa_refuses_a_page_that_does_not_state_todays_date():
    allow = {**fetcher().access, "swpa": {**fetcher().access["swpa"], "status": "ALLOWED"}}
    f = fetcher(access=allow, transport=lambda u, h, t: Response(200, fx("swpa-sun-old.htm")))
    r = swpa.read({"project": "BSD"}, f, NOW)
    assert not r.ok and "an old page is never used" in r.error


def test_swpa_is_not_read_while_its_access_check_is_open():
    f = fetcher(transport=lambda u, h, t: (_ for _ in ()).throw(AssertionError("no request may be made")))
    r = swpa.read({"project": "BSD"}, f, NOW)
    assert not r.ok and "ACCESS_CHECK_REQUIRED" in r.error and f.requests[0][2] == "REFUSED_ACCESS"


def test_central_time_dst_rule():
    assert swpa.central(dt.date(2026, 7, 1)).utcoffset(None) == dt.timedelta(hours=-5)
    assert swpa.central(dt.date(2026, 11, 22)).utcoffset(None) == dt.timedelta(hours=-6)


# ---- RISE / USGS ----------------------------------------------------------------------------------------------------------------------------
def test_rise_drops_zero_placeholders_and_modeled_results():
    obs = rise.parse(fx("rise-release.json"))
    assert [o["dischargeCfs"] for o in obs] == [4100.0, 3900.0]


def test_usgs_reads_one_series_and_refuses_several():
    obs, why = usgs.parse(fx("usgs-00060.json"), "07055660")
    assert why is None and obs[-1] == {"at": "2026-11-22T19:00:00Z", "dischargeCfs": 12800.0}
    obs, why = usgs.parse(fx("usgs-two-series.json"), "07055660")
    assert obs is None and "never merged" in why
    obs, why = usgs.parse(fx("usgs-00060.json"), "00000000")
    assert obs is None and "another site" in why
