"""The autonomous research loop: a generated research task is dispatched, executed, ingested and turned into evidence, a follow-up task or an exact blocker;
it is checkpointed, deduplicated, resumable after an interrupted executor, and never ends an investigation by merely writing a task file."""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import campaign as C  # noqa: E402
import taskqueue as TQ  # noqa: E402

D, L = C.D, C.L


@pytest.fixture
def home(tmp_path):
    for bid, folder in C.DEFAULT_FOLDERS.items():
        d = tmp_path / folder
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"brainId": bid, "items": []}))
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "manifest.json").write_text("{}")
    return str(tmp_path)


CFG = {"budget": {"wallSeconds": 3600, "maxAvenues": 10, "stallAvenues": 3},
       "brains": {"water-temp": {"purpose": "t", "weaknesses": [{"id": "G-OPEN", "title": "an open question"}], "avenues": []}}}


class Src(D.Fetcher):
    def __init__(self, home):
        super().__init__(gap=0, home=home)
        self.calls = 0

    def get(self, base, params=None, accept=None):
        self.url(base, params)
        self.calls += 1
        return b"col\n1\n2\n"


def fake_executor(tmp_path, body):
    """A stand-in for the headless Claude executor: writes the result the agent would write."""
    p = tmp_path / "fake_exec.py"
    b = tmp_path / "body.json"
    b.write_text(json.dumps(body))
    p.write_text("import json,sys\nres, bodyf = sys.argv[1], sys.argv[2]\njson.dump(json.load(open(bodyf)), open(res, 'w'))\n")
    return {"command": [sys.executable, str(p), "{result}", str(b)], "timeoutSeconds": 60}


def start(home, monkeypatch, cid="L1"):
    monkeypatch.setattr(C.D, "load_gaps", lambda *a, **k: {"source": "test", "reconstructed": False, "gaps": []})      # only the configured weakness exists
    monkeypatch.setattr(C, "discovery_cfg", lambda: CFG)
    C.init(home, cid, brains=["water-temp"])


def test_enqueue_is_idempotent_and_recovers_an_interrupted_executor(home):
    a = TQ.enqueue(home, "water-temp", "G", "agent-research", "t", "b.json", "c", topic="open-web")
    b = TQ.enqueue(home, "water-temp", "G", "agent-research", "t", "b.json", "c2", topic="open-web")
    assert a["id"] == b["id"] and len(TQ.load(home)["tasks"]) == 1
    TQ.claim(home, a["id"], "claude-cli")                                  # the executor dies here (killed session, context limit)
    assert TQ.counts(home)["CLAIMED"] == 1 and TQ.next_task(home) is None
    assert TQ.recover(home) == 1 and TQ.next_task(home)["id"] == a["id"]     # nothing lost; a DONE task is never re-run
    TQ.complete(home, a["id"], "ok")
    assert TQ.recover(home) == 0 and TQ.next_task(home) is None


def test_failures_are_retried_then_recorded_and_blocks_carry_the_next_source(home):
    t = TQ.enqueue(home, "wind", "G", "agent-research", "t", "b.json", "c", max_attempts=2)
    TQ.claim(home, t["id"], "x"); TQ.fail(home, t["id"], "boom")           # noqa: E702
    assert TQ.load(home)["tasks"][0]["status"] == "QUEUED"
    TQ.claim(home, t["id"], "x"); TQ.fail(home, t["id"], "boom again")     # noqa: E702
    assert TQ.load(home)["tasks"][0]["status"] == "FAILED"
    u = TQ.enqueue(home, "wind", "H", "agent-research", "t", "b.json", "c")
    TQ.block(home, u["id"], "needs owner", "the operator")
    assert [x for x in TQ.load(home)["tasks"] if x["id"] == u["id"]][0]["nextSource"] == "the operator"


def test_exhausted_configured_avenues_queue_agent_research_instead_of_stopping(home, monkeypatch):
    start(home, monkeypatch)
    C.run(home, "L1", adapters={}, fetcher=D.OfflineFetcher())
    t = TQ.load(home)["tasks"]
    assert [x["gap"] for x in t] == ["G-OPEN"] and t[0]["status"] == "QUEUED"
    brief = json.load(open(os.path.join(home, t[0]["brief"])))
    assert "search the open web" in " ".join(brief["how"]) and "alreadyTried" in brief
    led = L.Ledger(os.path.join(home, "water-temperature", "research", "gap-ledger.json"), "water-temp")
    assert led.doc["gaps"]["G-OPEN"]["status"] != "EXHAUSTED" and "queued agent research" in led.doc["gaps"]["G-OPEN"]["nextEvidence"]


def test_loop_executes_the_task_registers_the_source_acquires_the_data_and_queues_the_next_step(home, tmp_path, monkeypatch):
    start(home, monkeypatch)
    res = {"schema": C.RESULT_SCHEMA, "status": "FINDINGS", "summary": "one open dataset", "queriesTried": ["q1", "q2"],
           "datasets": [{"title": "Example telemetry", "publisher": "Example Univ", "url": "https://data.example.org/ds", "directUrl": "https://data.example.org/files/telemetry.csv", "licence": "CC0",
                         "sizeBytes": 1000, "verifiedAccess": True, "relevance": "movement vs temperature", "analysisPlan": "depth by hour"},
                        {"title": "Unverified claim", "directUrl": "https://data.example.org/files/x.csv", "licence": "CC0", "verifiedAccess": False}],
           "ownerActions": [{"id": "agency-creel", "publisher": "State agency", "dataset": "creel records", "access": "request", "verified": False, "addresses": "G-OPEN"}]}
    src = Src(home)
    monkeypatch.setattr(D, "register_source", lambda home, sid, hosts, lic, pur, rat, adapter="http-json", probe=True: (monkeypatch.setattr(D, "ALLOWED_HOSTS", D.ALLOWED_HOSTS + tuple(hosts)), {"id": sid})[1])
    out = C.loop(home, "L1", "claude-cli", max_tasks=3, max_hours=1, adapters={}, fetcher=src, exec_cfg=fake_executor(tmp_path, res))
    assert out["executed"] == 1 and out["log"][0]["status"] == "done"
    assert out["log"][0]["registered"] == ["data.example.org"] and len(out["log"][0]["acquired"]) == 1 and out["log"][0]["ownerActions"] == 1
    assert src.calls == 1                                                  # the unverified dataset was NOT downloaded
    prov = json.load(open(os.path.join(home, "water-temperature", "sources", "L1", "PROVENANCE.json")))["files"]
    assert any(v["connector"] == "agent-datasets" and v["sha256"] for v in prov.values())
    tasks = {t["kind"]: t for t in TQ.load(home)["tasks"]}
    assert tasks["agent-research"]["status"] == "DONE" and tasks["implement-experiment"]["status"] == "QUEUED"        # the investigation continues
    assert os.path.exists(os.path.join(home, "water-temperature", "research", "data-acquisition", "agency-creel.json"))
    led = L.Ledger(os.path.join(home, "water-temperature", "research", "gap-ledger.json"), "water-temp")
    assert any(k.startswith("agent:") for k in led.doc["avenues"]) and led.doc["gaps"]["G-OPEN"]["bestTier"] == "EVIDENCE_LEAD"


def test_no_usable_evidence_becomes_an_exact_blocker_with_the_queries_and_never_repeats(home, tmp_path, monkeypatch):
    start(home, monkeypatch)
    res = {"schema": C.RESULT_SCHEMA, "status": "NO_USABLE_EVIDENCE", "summary": "nothing open", "queriesTried": ["a", "b", "c"], "datasets": [], "nextSource": "agency X holds it"}
    C.loop(home, "L1", "claude-cli", max_tasks=3, max_hours=1, adapters={}, fetcher=Src(home), exec_cfg=fake_executor(tmp_path, res))
    led = L.Ledger(os.path.join(home, "water-temperature", "research", "gap-ledger.json"), "water-temp")
    b = led.doc["gaps"]["G-OPEN"]["blockers"][0]
    assert led.doc["gaps"]["G-OPEN"]["status"] == "BLOCKED_EXTERNAL" and "3 queries" in b["reason"] and b["nextEvidenceSource"] == "agency X holds it"
    assert TQ.counts(home)["DONE"] == 1
    # a later campaign asks again only with the earlier queries listed so the agent does not repeat them
    C.init(home, "L2", brains=["water-temp"])
    C.run(home, "L2", adapters={}, fetcher=D.OfflineFetcher())
    t = [x for x in TQ.load(home)["tasks"] if x["status"] == "DONE"][0]
    assert len(TQ.load(home)["tasks"]) == 1                                 # same question: deduplicated, not asked twice


def test_a_failing_executor_is_retried_then_stops_without_claiming_success(home, tmp_path, monkeypatch):
    start(home, monkeypatch)
    cfg = {"command": [sys.executable, "-c", "import sys; sys.exit(3)"], "timeoutSeconds": 30}
    out = C.loop(home, "L1", "claude-cli", max_tasks=5, max_hours=1, adapters={}, fetcher=Src(home), exec_cfg=cfg)
    t = TQ.load(home)["tasks"][0]
    assert t["status"] == "FAILED" and t["attempts"] == 2 and out["queue"]["DONE"] == 0
    rep = json.load(open(os.path.join(home, "shared", "campaigns", "L1", "report.json")))
    assert rep["researchComplete"] is False


def test_session_executor_hands_the_next_task_to_the_coordinating_session(home, monkeypatch, capsys):
    start(home, monkeypatch)
    out = C.loop(home, "L1", "session", max_tasks=3, max_hours=1, adapters={}, fetcher=D.OfflineFetcher())
    assert out["log"] == [{"dispatch": out["log"][0]["dispatch"], "mode": "session"}] and out["queue"]["QUEUED"] == 1
    assert C.main(["tasks", "next", "--home", home]) == 0
    t = json.loads(capsys.readouterr().out.split("\n", 0)[0])
    assert t["status"] == "CLAIMED" and t["briefContent"]["gapId"] == "G-OPEN" and t["resultSchema"] == C.RESULT_SCHEMA


def test_queue_priority_follows_the_weakest_measured_capability(home, monkeypatch):
    """A capability result feeds the next research decision: the Brain with the lower composite is worked first."""
    monkeypatch.setattr(C.BC, "compute_brain", lambda eng, h, bid, disc, camp, ready: {"current": {"value": {"wind": 0.8, "water-temp": 0.1}.get(bid)}})
    c = C.Campaign(home, "x")
    assert C.capability_priority(c, "water-temp") < C.capability_priority(c, "wind")
    monkeypatch.setattr(C.BC, "compute_brain", lambda *a, **k: {"current": {"value": None}})              # entirely unmeasured counts as weakest
    assert C.capability_priority(c, "wind") < 30
