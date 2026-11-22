"""The access gate and the retry policy of generation_brain.http (no network)."""
from generation_brain.http import Fetcher, Response, TransportError

ACCESS = {"cwms": {"status": "ALLOWED", "agency": "USACE"}, "swpa": {"status": "ACCESS_CHECK_REQUIRED", "agency": "SWPA"}}


def fetcher(transport):
    return Fetcher(ACCESS, transport=transport, sleep=lambda s: None, jitter=lambda: 0.0)


def test_a_provider_that_is_not_allowed_is_never_requested():
    calls = []
    f = fetcher(lambda u, h, t: calls.append(u) or Response(200, b"{}"))
    r = f.get("swpa", "https://www.energy.gov/swpa/sun.htm")
    assert not r.ok and "ACCESS_CHECK_REQUIRED" in r.error and calls == []
    assert not f.get("unknown", "https://example.org").ok and calls == []


def test_one_url_is_read_once_per_run():
    calls = []
    f = fetcher(lambda u, h, t: calls.append(u) or Response(200, b"[]"))
    f.get("cwms", "https://cwms/x")
    f.get("cwms", "https://cwms/x")
    assert calls == ["https://cwms/x"]


def test_transient_failures_are_retried_permanent_ones_are_not():
    seq = iter([Response(503, b""), TransportError("timeout"), Response(200, b"ok")])

    def t(u, h, to):
        x = next(seq)
        if isinstance(x, Exception):
            raise x
        return x
    r = fetcher(t).get("cwms", "https://cwms/a")
    assert r.ok and r.attempts == 3
    calls = []
    r = fetcher(lambda u, h, to: calls.append(1) or Response(404, b"")).get("cwms", "https://cwms/b")
    assert not r.ok and "permanent" in r.error and len(calls) == 1


def test_a_long_retry_after_is_not_waited_for():
    r = fetcher(lambda u, h, t: Response(429, b"", retry_after=600)).get("cwms", "https://cwms/c")
    assert not r.ok and "over the 30 s cap" in r.error and r.attempts == 1
