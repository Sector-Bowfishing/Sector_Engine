"""provider_bakeoff `cycle`: one pass of the loop's body (collect, then the RRFS check), for a scheduler that starts the collector hourly
(Pulse on the Mac mini, Sector_Ops #51). A failed collect must not skip the RRFS check, exactly as in `loop`."""
import sector_wind_research.provider_bakeoff as B
import sector_wind_research.rrfs as R


def test_cycle_runs_collect_then_rrfs(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(B, "collect", lambda now=None: calls.append("collect"))
    monkeypatch.setattr(R, "collect", lambda *a, **k: calls.append("rrfs") or [{"status": "archived", "init": "x"}, {"status": "not published"}])
    B.cycle()
    assert calls == ["collect", "rrfs"]
    out = capsys.readouterr().out
    assert "RRFS" in out and out.count("RRFS") == 1          # 'not published' cycles are not printed, as in loop


def test_a_failed_collect_still_runs_rrfs(monkeypatch, capsys):
    calls = []

    def boom(now=None):
        raise RuntimeError("provider down")
    monkeypatch.setattr(B, "collect", boom)
    monkeypatch.setattr(R, "collect", lambda *a, **k: calls.append("rrfs") or [])
    B.cycle()
    assert calls == ["rrfs"] and "collect failed" in capsys.readouterr().out
