from datetime import datetime, timedelta, timezone

from sector_wind import scoreboard as SB
from sector_wind.brain import reliability_gate as RG


class Mem:
    def __init__(self): self.d = {}
    def get_json(self, k): return self.d.get(k)
    def put_json(self, k, v): self.d[k] = v


def test_nothing_happens_before_the_gate_day_and_no_store_access():
    st = Mem()
    assert RG.record_once(st, {}, SB.LIVE_START + timedelta(days=29, hours=23)) == (None, False) and st.d == {}


def test_gate_is_evaluated_once_exactly_like_the_scorer(monkeypatch):
    calls = []
    def fake(store, cfg, now):
        calls.append(now)
        return {"credit": 0.8, "conditions": {"30-day completeness": 0.8, "median age <= 90": 1.0, "fallbacks exercised": 1.0}, "window": "a -> b", "n": 700, "why": "30/30 complete days"}
    monkeypatch.setattr(SB, "dim8", fake)
    st, now = Mem(), SB.LIVE_START + timedelta(days=30, hours=1)
    r, new = RG.record_once(st, {}, now)
    assert new and r["verdict"] == "FAIL" and r["failedConditions"] == ["30-day completeness"] and st.d[RG.KEY] == r
    r2, new2 = RG.record_once(st, {}, now + timedelta(days=3))
    assert not new2 and r2 == r and len(calls) == 1                          # recorded once; never re-evaluated or rewritten
    monkeypatch.setattr(SB, "dim8", lambda *a: {"credit": 1.0, "conditions": {"x": 1.0}, "window": "w", "n": 1, "why": "ok"})
    assert RG.record_once(Mem(), {}, now)[0]["verdict"] == "PASS"
