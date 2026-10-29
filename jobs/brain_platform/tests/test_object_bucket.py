"""GcsRestObjectStore keeps the object-store contract (generations, create-only, no delete) against an in-process fake of the Cloud Storage JSON API."""
import json
import urllib.parse

import pytest

from sector_brain_platform.object_bucket import GcsRestObjectStore
from sector_brain_platform.publication_coordination import StoreLedger
from sector_brain_platform.publisher.storage import PreconditionFailed, orchestrator_view


class FakeGcs:
    def __init__(self):
        self.o, self.gen = {}, 0
        self.calls = []

    def __call__(self, method, url, body, headers):
        assert headers["Authorization"] == "Bearer T"
        u = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        self.calls.append((method, u.path))
        if method == "POST":
            name = q["name"]
            cur = self.o.get(name, [None, 0])[1]
            if "ifGenerationMatch" in q and int(q["ifGenerationMatch"]) != cur:
                return 412, b"{}"
            self.gen += 1
            self.o[name] = [bytes(body), self.gen]
            return 200, json.dumps({"generation": str(self.gen)}).encode()
        path = urllib.parse.unquote(u.path)
        if path.endswith("/o"):
            items = [{"name": n} for n in sorted(self.o) if n.startswith(q.get("prefix", ""))]
            return 200, json.dumps({"items": items}).encode()
        name = path.split("/o/", 1)[1]
        if name not in self.o:
            return 404, b"{}"
        if q.get("alt") == "media":
            return 200, self.o[name][0]
        return 200, json.dumps({"generation": str(self.o[name][1])}).encode()


class Tok:
    def token(self):
        return "T"


def store():
    return GcsRestObjectStore("b", Tok(), transport=FakeGcs())


def test_contract_create_only_overwrite_by_generation_absent_object_and_list():
    s = store()
    assert s.get("artifacts/wind/x/artifact.json") is None and s.generation("artifacts/wind/x/artifact.json") == 0
    g = s.put("artifacts/wind/x/artifact.json", b"1", if_generation_match=0)
    with pytest.raises(PreconditionFailed):
        s.put("artifacts/wind/x/artifact.json", b"2", if_generation_match=0)           # create-only
    with pytest.raises(PreconditionFailed):
        s.put("artifacts/wind/x/artifact.json", b"2", if_generation_match=g + 99)       # stale generation
    assert s.put("artifacts/wind/x/artifact.json", b"2", if_generation_match=g) > g and s.get("artifacts/wind/x/artifact.json") == b"2"
    assert s.list("artifacts/wind/") == ["artifacts/wind/x/artifact.json"] and not hasattr(s, "delete")


def test_the_ledger_works_over_the_rest_store_through_the_orchestrator_view():
    s = store()
    v = orchestrator_view(s)
    L = StoreLedger(v)
    L.put({"key": "k", "brainId": "wind", "runId": "r", "artifact": {"state": "MISSING"}, "publication": {"outcome": "NOT_REQUESTED", "attempts": 0}})
    assert StoreLedger(orchestrator_view(s)).get("k")["brainId"] == "wind"
    assert any(p.endswith("exports%2Forchestrator%2Fpublication-ledger-v1.json") or "publication-ledger" in p for _, p in s._t.calls)
