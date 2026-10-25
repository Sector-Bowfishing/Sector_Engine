#!/usr/bin/env python3
"""Sector eight-Brain research campaign harness: the deterministic spine one Claude Code session uses to run, check, resume and clean up a
research campaign across all eight Brains (owner directive 2026-10-23, research automation verification). Stdlib only.

It is NOT a second orchestrator and it never touches production: no cloud, no Firebase, no Engine runtime knowledge, no approval.
It coordinates what already exists:
  - research folders: the Cortex research layout (assignments, folder layout, retention classes, closeout sections; RS-01..RS-09)
  - track order: each Brain's brain.json operations.execution.dependsOn (Intelligence after the specialists, Depth/Vegetation after Lake)
  - validation / candidate scores: each Brain's OWN existing evaluators, registered in tools/research/adapters.json
  - candidate packaging: sector_brain_platform.knowledge_release (the same immutable, digest-verified format; approval NOT_RECORDED)

Per track, stages run in order and are checkpointed atomically in <research home>/shared/campaigns/<id>/state.json:
  discover   load the Brain's manifest, classify existing evidence (items by retention / folder), prior campaigns and closeouts; load the open
             gaps (Engine GAPS.json, or RECONSTRUCTED into <folder>/research/GAPS.generated.json when missing); check the declared research
             inputs (present / reconstructed / recorded limitation: a missing input never stops the campaign)
  acquire    the Brain's discovery connectors (tools/research/discovery.py + discovery.json) download legitimate public evidence from allowlisted
             hosts only into <folder>/sources/<campaign>/ with provenance, registered in manifest.json. This coordinator stage is the ONLY
             place with network access; adapters stay blocked. A failed request is recorded, never fatal.
  research   the Brain's research adapter (deterministic evaluator run; an adapter BLOCKED on a missing external input is recorded, not fatal),
             the OFFLINE discovery analysis of the acquired evidence (auto-generated findings with pre-declared thresholds), and any
             agent-written findings (`submit`): findings.json in the track's campaign-owned workspace <folder>/analysis/tmp/<campaign>/
  validate   every finding: schema, evidence that exists in the research home with a matching sha256, and the Brain's validator metric against
             the finding's declared threshold -> VALIDATED or REJECTED (with the reason). Nothing is ever approved here.
  candidate  validated findings -> <folder>/candidates/<campaign>/ as a knowledge-release package (approval NOT_RECORDED), verified by load_release
  score      the Brain's candidate-score adapter (non-authoritative) + the discovery score impact; authoritative score artifacts are hashed
             before and after (must not change)
  followup   weak areas (rejected findings, unmatched targets, too little evidence) re-open acquire..followup for another, wider iteration,
             bounded by discovery.json maxIterations; what stays weak is reported as a gap / limitation
  cleanup    delete ONLY the campaign-owned workspace (marker file), register retained outputs in manifest.json, write the RS-05 closeout
Then `report` writes one consolidated REPORT.md / report.json for the campaign.

Recovery: rerunning `run` resumes from the checkpoint; DONE stages are skipped, an interrupted (RUNNING) stage is re-run (stages are idempotent:
outputs are written to a temp path and renamed), failures are retried up to max_attempts, and one track's failure never stops the others.

  python3 tools/research/campaign.py init   --campaign C [--home DIR] [--brains a,b]
  python3 tools/research/campaign.py run    --campaign C [--home DIR] [--parallel 3] [--timeout 600] [--offline]
  python3 tools/research/campaign.py submit --campaign C --brain B --findings F.json      (agent-written findings for one track)
  python3 tools/research/campaign.py status --campaign C
  python3 tools/research/campaign.py report --campaign C
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ENGINE, "jobs", "brain_platform"))
from sector_brain_platform import knowledge_release as K  # noqa: E402
import discovery as D  # noqa: E402
import experiments as X  # noqa: E402
import ledger as L  # noqa: E402
import bowfishing_capability as BC  # noqa: E402
import taskqueue as TQ  # noqa: E402

SCHEMA = "sector-research-campaign-v1"
FINDINGS_SCHEMA = "sector-research-findings-v1"
STAGES = ("discover", "acquire", "research", "validate", "candidate", "score", "followup", "cleanup")
ITERATION_STAGES = ("acquire", "research", "validate", "candidate", "score", "followup")   # re-opened by a follow-up iteration
BRAINS = ("biological-state", "wind", "water-clarity", "lake-brain", "water-temp", "sector-intelligence", "depth", "vegetation")
# Cortex research layout assignments (projects/sector/shared/data/research-layout.json); read from Cortex when available
DEFAULT_FOLDERS = {"biological-state": "fish-brain", "wind": "wind-brain", "water-clarity": "water-clarity", "lake-brain": "lake-brain",
                   "water-temp": "water-temperature", "depth": "depth", "vegetation": "vegetation", "sector-intelligence": "sector-intelligence"}
BRAIN_DIRS = {"biological-state": "fish", "lake-brain": "lake", "water-temp": "water-temperature"}
try:                                                                       # a Brain registered in discovery.json with a research folder joins the coordinator with no code change
    for _b, _spec in json.load(open(os.path.join(HERE, "discovery.json"), encoding="utf-8")).get("brains", {}).items():
        if _b not in DEFAULT_FOLDERS and _spec.get("folder"):
            DEFAULT_FOLDERS[_b] = _spec["folder"]
            BRAINS = BRAINS + (_b,)
            if _spec.get("dir"):
                BRAIN_DIRS[_b] = _spec["dir"]
except (OSError, ValueError):
    pass
CLOSEOUT_SECTIONS = ("Preserved results", "Manifests updated", "Candidate knowledge", "Backups verified", "Deleted", "Worktrees", "Blockers")
OWNER_MARKER = ".campaign-owned"
# local authoritative score artifacts; a campaign must leave them byte-identical (the live /scores node is never read or written here)
AUTHORITATIVE = ("docs/brains/scoring/frozen-scores.json", "docs/brains/scoring/engine-score-v1.json",
                 "docs/cortex/engineering-status/engineering-status.json")
BLOCKED_ENV = {"BRAIN_RTDB_URL": "http://127.0.0.1:9/blocked-by-research-campaign", "SECTOR_WIND_BRAIN_RTDB_URL": "http://127.0.0.1:9/blocked",
               "BRAIN_TOKEN_MODE": "disabled", "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
               "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "NO_PROXY": "", "no_proxy": "",
               "SECTOR_RESEARCH_CAMPAIGN": "1", "SECTOR_WIND_GCS_APPROVED": "no"}
STRIP_ENV = ("GOOGLE_APPLICATION_CREDENTIALS", "CLOUDSDK_AUTH_ACCESS_TOKEN_FILE", "FIREBASE_TOKEN", "GOOGLE_CLOUD_PROJECT")
_lock = threading.Lock()
_manifest_lock = threading.Lock()
_fetcher: D.Fetcher | None = None                                       # set by run(); tests and --offline use D.OfflineFetcher


# ------------------------------------------------------------------------------------------------------------------------------- basics
def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def research_home(arg: str | None) -> str:
    """--home, else SECTOR_RESEARCH_HOME, else the Cortex research layout's researchRoot (CORTEX_HOME). No hard-coded machine path."""
    if arg or os.environ.get("SECTOR_RESEARCH_HOME"):
        return os.path.abspath(os.path.expanduser(arg or os.environ["SECTOR_RESEARCH_HOME"]))
    layout = os.path.join(os.environ.get("CORTEX_HOME", ""), "projects", "sector", "shared", "data", "research-layout.json")
    if os.path.exists(layout):
        return os.path.abspath(os.path.expanduser(json.load(open(layout, encoding="utf-8"))["researchRoot"]))
    raise SystemExit("research home unknown: pass --home, or set SECTOR_RESEARCH_HOME or CORTEX_HOME")


def force_rmtree(path: str) -> None:
    """Delete a campaign-owned tree even when it holds read-only files or folders (APFS clones keep the research home's permissions, and
    some research snapshots are deliberately write-protected). Callers have already proven ownership of `path`."""
    import stat

    def onerror(func, p, _exc):
        parent = os.path.dirname(p)
        for q in (parent, p):
            try:
                os.chmod(q, os.stat(q).st_mode | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRUSR)
            except OSError:
                pass
        func(p)
    if os.path.lexists(path):
        shutil.rmtree(path, onerror=onerror)


def inside(path: str, root: str) -> bool:
    p, r = os.path.realpath(path), os.path.realpath(root)
    return p == r or p.startswith(r + os.sep)


class Campaign:
    def __init__(self, home: str, cid: str):
        self.home, self.cid = home, cid
        self.dir = os.path.join(home, "shared", "campaigns", cid)
        self.state_path = os.path.join(self.dir, "state.json")
        self.events = os.path.join(self.dir, "events.jsonl")

    # ---- state
    def load(self) -> dict:
        with open(self.state_path, encoding="utf-8") as fh:
            return json.load(fh)

    def save(self, st: dict) -> None:
        with _lock:
            st["updatedAt"] = now_iso()
            atomic_json(self.state_path, st)

    def log(self, **ev) -> None:
        with _lock, open(self.events, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now_iso(), **ev}, ensure_ascii=False) + "\n")

    def folder(self, st: dict, bid: str) -> str:
        return os.path.join(self.home, st["tracks"][bid]["folder"])

    def workspace(self, st: dict, bid: str) -> str:
        return os.path.join(self.folder(st, bid), "analysis", "tmp", self.cid)


def load_adapters(path: str | None = None) -> dict:
    with open(path or os.path.join(HERE, "adapters.json"), encoding="utf-8") as fh:
        return json.load(fh)["adapters"]


def brain_dependencies(bid: str) -> list[str]:
    p = os.path.join(ENGINE, "brains", BRAIN_DIRS.get(bid, bid), "brain.json")
    try:
        return list(json.load(open(p, encoding="utf-8"))["operations"]["execution"]["dependsOn"])
    except (OSError, KeyError, ValueError):
        return []


def authoritative_hashes() -> dict:
    return {p: (sha256(os.path.join(ENGINE, p)) if os.path.exists(os.path.join(ENGINE, p)) else None) for p in AUTHORITATIVE}


# ------------------------------------------------------------------------------------------------------------------------------- init
def init(home: str, cid: str, brains: list[str] | None = None, max_attempts: int = 2, verification: bool = False, discovery: bool = True,
         budget_overrides: dict | None = None) -> dict:
    c = Campaign(home, cid)
    if os.path.exists(c.state_path):
        raise SystemExit(f"campaign {cid} already exists: resume it with `run`")
    tracks = {}
    for bid in brains or BRAINS:
        if bid not in DEFAULT_FOLDERS:
            raise SystemExit(f"unknown Brain {bid}")
        folder = DEFAULT_FOLDERS[bid]
        if not os.path.isdir(os.path.join(home, folder)):
            raise SystemExit(f"research folder missing: {os.path.join(home, folder)} (RS-01)")
        deps = [d for d in brain_dependencies(bid) if d in (brains or BRAINS)]
        tracks[bid] = {"folder": folder, "dependsOn": deps, "iteration": 1, "followupTargets": None, "avenue": None, "acquired": [],
                       "stages": {s: {"status": "PENDING", "attempts": 0} for s in STAGES}}
    st = {"schema": SCHEMA, "campaignId": cid, "createdAt": now_iso(), "home": home, "maxAttempts": max_attempts, "tracks": tracks,
          "verification": bool(verification), "discovery": bool(discovery), "budget": budget_overrides or {},          # True only for harness verification: allows the labelled FIXTURE findings
          "authoritativeBefore": authoritative_hashes(), "boundary": {"network": "blocked for adapters; the acquire stage reaches allowlisted "
                                                                                  f"public research sources only ({', '.join(D.ALLOWED_HOSTS)})",
                                                                       "firebase": "never written",
                                                                       "engineKnowledge": "never written", "approval": "never set"}}
    c.save(st)
    c.log(event="init", brains=list(tracks))
    return st


# ------------------------------------------------------------------------------------------------------------------------------- adapters
def run_command(cmd: list[str], cwd: str, out_dir: str, timeout: int, extra_env: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    env.update(BLOCKED_ENV)
    env["CLOUDSDK_CONFIG"] = os.path.join(out_dir, ".no-gcloud")          # no cloud credentials inside a campaign task
    env["CAMPAIGN_OUT"] = out_dir
    env.update(extra_env or {})
    os.makedirs(env["CLOUDSDK_CONFIG"], exist_ok=True)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = 124, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), f"timeout after {timeout}s"
    return {"rc": rc, "seconds": round(time.time() - t0, 2), "stdoutTail": out[-4000:], "stderrTail": err[-2000:]}


def expand(cmd: list[str], ctx: dict) -> list[str]:
    return [x.format(**ctx) for x in cmd]


def metrics_from(res: dict, out_dir: str) -> dict:
    """An adapter reports metrics in $CAMPAIGN_OUT/metrics.json, or as the last JSON object printed on stdout."""
    p = os.path.join(out_dir, "metrics.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    for line in reversed((res.get("stdoutTail") or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {}


def get_path(obj, dotted: str):
    for part in dotted.split("."):
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


# ------------------------------------------------------------------------------------------------------------------------------- stages
def avenues_for(bid: str) -> list[dict]:
    """The Brain's research avenues in priority order (discovery.json `avenues`); a Brain with only a connector gets primary + widen."""
    spec = discovery_cfg().get("brains", {}).get(bid) or {}
    if spec.get("avenues"):
        return [dict(a) for a in spec["avenues"]]
    kind = spec.get("kind")
    if kind == "upstream":
        return [{"id": "upstream", "run": "upstream", "kind": "upstream", "gaps": []}]
    if not kind:
        return []
    return [{"id": "primary", "run": "connector", "kind": kind, "iter": 1, "gaps": []},
            {"id": "widen", "run": "connector", "kind": kind, "iter": 2, "when": "weak", "gaps": []}]


def brain_spec(bid: str) -> dict:
    return {k: v for k, v in (discovery_cfg().get("brains", {}).get(bid) or {}).items() if k != "avenues"}


def exp_spec(bid: str, av: dict) -> dict:
    return {**brain_spec(bid), **(av.get("params") or {}), "params": {**brain_spec(bid), **(av.get("params") or {})}, "avenueId": av["id"], **{k: v for k, v in av.items() if k in ("rung",)}}


def budget(st: dict) -> dict:
    return {**(discovery_cfg().get("budget") or {}), **(st.get("budget") or {})}


def ledger(c: Campaign, st: dict, bid: str) -> L.Ledger:
    return L.Ledger(os.path.join(c.folder(st, bid), "research", "gap-ledger.json"), bid)


def stage_discover(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    folder = c.folder(st, bid)
    m = json.load(open(os.path.join(folder, "manifest.json"), encoding="utf-8"))
    items = m.get("items") or []
    by_ret: dict = {}
    by_dir: dict = {}
    for it in items:
        by_ret[it.get("retention") or "UNCLASSIFIED"] = by_ret.get(it.get("retention") or "UNCLASSIFIED", 0) + 1
        p = it.get("workspacePath") or it.get("canonicalWorkspacePath") or it.get("path") or ""
        top = p.split("/")[0] if p else "?"
        by_dir[top] = by_dir.get(top, 0) + 1
    closeouts = sorted(os.listdir(os.path.join(folder, "closeouts"))) if os.path.isdir(os.path.join(folder, "closeouts")) else []
    candidates = sorted(os.listdir(os.path.join(folder, "candidates"))) if os.path.isdir(os.path.join(folder, "candidates")) else []
    shared = json.load(open(os.path.join(c.home, "shared", "manifest.json"), encoding="utf-8")) if os.path.exists(os.path.join(c.home, "shared", "manifest.json")) else {}
    shared_refs = [i.get("id") for i in shared.get("items") or [] if bid in json.dumps(i)][:20]
    out = {"manifestItems": len(items), "byRetention": by_ret, "byTopFolder": by_dir, "priorTasks": [t.get("id") for t in m.get("tasks") or []],
           "closeouts": closeouts[-5:], "existingCandidates": candidates[-5:], "sharedEvidence": shared_refs}
    if ad is None:                                                       # brief() preview: no side effects
        return out
    g = D.load_gaps(ENGINE, c.home, bid, st["tracks"][bid]["folder"], BRAIN_DIRS.get(bid, bid))
    weaknesses = [{"id": w["id"], "title": w["title"], "source": w.get("evidence", "campaign configuration"), "nextEvidence": w.get("nextEvidence")} for w in (brain_spec(bid).get("weaknesses") or [])]
    if not g["gaps"] and not weaknesses:                                 # a Brain with no gap list yet (a newly onboarded one): its first gap is to define its gaps
        weaknesses = [{"id": re.sub(r"[^A-Z]", "", bid.upper()) + "-DISC-FIRST", "title": "Define and investigate this Brain's first scientific gaps: " + (brain_spec(bid).get("purpose") or bid),
                       "source": "campaign: no GAPS.json or generated gaps exist", "nextEvidence": "an agent research task (see research/agent-tasks) or a reviewed GAPS.json for the Brain"}]
    led = ledger(c, st, bid)
    led.sync(g["gaps"] + weaknesses)
    led.reopen_exhausted()                                               # a new campaign gives exhausted gaps a fresh chance (new sources, new experiments)
    avs = avenues_for(bid)
    nxt = L.next_avenue(avs, led, [], set(), c.cid)
    led.save()
    out["gaps"] = {"source": g["source"], "reconstructed": g["reconstructed"], "open": [x.get("id") for x in g["gaps"]], "discovered": [w["id"] for w in weaknesses],
                   "ledger": {k: v["status"] for k, v in led.doc["gaps"].items()}}
    spec = brain_spec(bid)
    inp = D.check_inputs(ENGINE, c.home, spec.get("inputs") or [])
    for r in inp["reconstructed"]:                                       # RS-02: a reconstructed input is registered like any other evidence
        with _manifest_lock:
            mm = json.load(open(os.path.join(folder, "manifest.json"), encoding="utf-8"))
            rel = os.path.relpath(os.path.join(c.home, r["input"]), folder)
            mm["items"] = [i for i in mm.get("items") or [] if i.get("workspacePath") != rel] + [
                {"id": f"{c.cid}:input:{rel}", "workspacePath": rel, "sha256": r["sha256"], "retention": "RECONSTRUCTABLE", "source": r["from"],
                 "provenance": f"tools/research/discovery.py check_inputs (campaign {c.cid})", "reconstruction": r["from"]}]
            atomic_json(os.path.join(folder, "manifest.json"), mm)
    out["inputs"] = inp
    out["avenues"] = [a["id"] for a in avs]
    with _lock:                                                          # first avenue of this campaign
        s2 = c.load()
        tr = s2["tracks"][bid]
        if tr.get("avenue") is None and nxt:
            tr["avenue"], tr["followupTargets"] = nxt[0], nxt[1]
        atomic_json(c.state_path, s2)
    return out


def input_env(c: Campaign, bid: str) -> dict:
    """Environment for a Brain's evaluators: private inputs found locally (discovery.json inputs[].search) are connected automatically."""
    try:
        return D.check_inputs(ENGINE, c.home, brain_spec(bid).get("inputs") or []).get("env") or {}
    except (OSError, ValueError):
        return {}


def discovery_cfg() -> dict:
    p = os.path.join(HERE, "discovery.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"brains": {}}


def stage_acquire(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    t = c.load()["tracks"][bid]
    av = t.get("avenue")
    if not av:
        return {"avenue": None, "note": "no actionable avenue: nothing to acquire"}
    if not st.get("discovery", True):
        return {"avenue": av["id"], "note": "discovery disabled for this campaign"}
    key = L.avenue_key(av, t.get("followupTargets") if av.get("when") == "weak" else None)
    if av["run"] == "upstream":
        entry = {"avenue": av["id"], "avenueKey": key, "avenueRun": "upstream", "shas": [], "evidenceFiles": 0, "newFiles": 0, "failureCount": 0}
    else:
        spec = brain_spec(bid)
        targets = t.get("followupTargets") if av.get("when") == "weak" else None
        used = set()                                                     # a follow-up iteration looks for OTHER sites
        for a in t.get("acquired") or []:
            for m in (a.get("matched") or {}).values():
                used |= {x["site"] for x in m.get("sites") or []} | ({m["site"]} if m.get("site") else set())
        spec["_usedSites"] = sorted(used)
        gaps = [g for g in D.load_gaps(ENGINE, c.home, bid, t["folder"], BRAIN_DIRS.get(bid, bid))["gaps"]]
        ev = D.Evidence(c.home, t["folder"], c.cid, _fetcher or D.Fetcher(home=c.home))
        try:
            if av["run"] == "connector":
                res = D.acquire(av["kind"], ev, c.home, spec, av.get("iter", 1), targets, gaps)
            else:
                res = X.EXPERIMENTS[av["experiment"]]["acquire"](ev, c.home, exp_spec(bid, av), av.get("iter", 1), targets, gaps)
        finally:
            ev.save()
        registered = ev.register(_manifest_lock)
        shas = sorted({ev.prov["files"][r]["sha256"] for r in ev.prov["files"] if ev.prov["files"][r].get("sha256")})
        entry = {**res, "avenue": av["id"], "avenueKey": key, "avenueRun": av["run"], "connector": av.get("kind"), "evidenceRoot": os.path.relpath(ev.root, c.home),
                 "newFiles": ev.new, "reusedFiles": getattr(ev, "reused", 0), "bytes": sum(p.get("bytes", 0) for p in ev.saved().values()), "evidenceFiles": len(ev.saved()), "registeredInManifest": registered, "shas": shas,
                 "failures": ev.failures[:20], "failureCount": len(ev.failures)}
    with _lock:                                                          # every avenue's acquisition is kept for the offline analysis
        s2 = c.load()
        acq = [a for a in s2["tracks"][bid].get("acquired") or [] if a.get("avenueKey") != key] + [entry]
        s2["tracks"][bid]["acquired"] = acq
        st["tracks"][bid]["acquired"] = acq
        atomic_json(c.state_path, s2)
    return {k: v for k, v in entry.items() if k not in ("matched", "lakes", "species", "gaps", "files", "shas", "rejected")}


def upstream_candidates(st: dict, bid: str) -> dict:
    """Only the Brain's declared dependencies: they finish before it starts, so the analysis is reproducible (no race with sibling tracks)."""
    deps = set(st["tracks"][bid]["dependsOn"])
    return {b: (t["stages"]["candidate"].get("result") or {}) for b, t in st["tracks"].items() if b in deps}


def run_analysis(c: Campaign, st: dict, bid: str) -> dict | None:
    """Offline analysis of everything acquired so far: the primary connector, upstream integration and every experiment avenue that ran."""
    t = st["tracks"][bid]
    spec = brain_spec(bid)
    avs = {a["id"]: a for a in avenues_for(bid)}
    acq = t.get("acquired") or []
    if not avs:
        return None
    merged = {"metrics": {}, "findings": [], "weak": [], "limitations": [], "weakByAvenue": {}, "owner": [], "agentTasks": [], "integration": []}

    def take(av_id, r):
        av = avs.get(av_id) or {}
        for f in r.get("findings") or []:
            f.setdefault("addresses", list(av.get("gaps") or []))
            f.setdefault("avenue", av_id)
            if av.get("resolves"):
                f.setdefault("resolves", list(av["resolves"]))
        merged["findings"] += r.get("findings") or []
        merged["limitations"] += r.get("limitations") or []
        merged["weakByAvenue"][av_id] = list(r.get("weak") or [])
        merged["owner"] += [{**o, "avenue": av_id} for o in r.get("owner") or []]
        merged["agentTasks"] += r.get("agentTasks") or []
        if r.get("integration"):
            merged["integration"].append(r["integration"])
    conn = [a for a in acq if a.get("avenueRun") == "connector"]
    if conn:
        r = D.analyze(conn[0]["connector"], c.home, spec, conn, None)
        merged["metrics"].update(r["metrics"])
        take(conn[0]["avenue"], r)                                       # one analysis serves all connector avenues (primary + widen)
        for a in conn:
            merged["weakByAvenue"][a["avenue"]] = []
        merged["weakByAvenue"][conn[-1]["avenue"]] = list(r["weak"])
    if any(a.get("avenueRun") == "upstream" for a in acq):
        r = D.analyze("upstream", c.home, spec, [], upstream_candidates(st, bid))
        merged["metrics"].update(r["metrics"])
        take("upstream", r)
    for av_id in sorted({a["avenue"] for a in acq if a.get("avenueRun") == "experiment"}):
        av = avs.get(av_id)
        if not av:
            continue
        mine = [a for a in acq if a["avenue"] == av_id]
        try:
            r = X.EXPERIMENTS[av["experiment"]]["analyze"](c.home, exp_spec(bid, av), mine, acq, upstream_candidates(st, bid))
        except (OSError, KeyError, ValueError, IndexError, TypeError) as e:        # failure isolation per avenue: a missing input or a bad source never stops the Brain
            missing = isinstance(e, FileNotFoundError)
            r = {"metrics": {"error": f"{type(e).__name__}: {str(e)[:160]}"}, "findings": [], "weak": [], "owner": [],
                 "limitations": [{"limitation": f"avenue {av_id} could not run: " + (f"input missing ({os.path.basename(getattr(e, 'filename', '') or '') or e})" if missing else f"{type(e).__name__}: {str(e)[:120]}"),
                                  "kind": "external" if missing else "avenue-error", "gap": (av.get("gaps") or [""])[0],
                                  "nextSource": "restore or reconstruct the missing research input (see the input limitation); the avenue is retried only in a later campaign"}]}
        merged["metrics"].setdefault("exp", {})[av_id] = r["metrics"]
        take(av_id, r)
    return merged


def stage_research(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    ws = c.workspace(st, bid)
    os.makedirs(ws, exist_ok=True)
    open(os.path.join(ws, OWNER_MARKER), "w").write(json.dumps({"campaignId": c.cid, "brainId": bid, "createdAt": now_iso()}))
    submitted = os.path.join(ws, "findings.json")
    out = {"mode": "agent-findings" if os.path.exists(submitted) else "adapter"}
    run = ad.get("research")
    rm = os.path.join(ws, "research-metrics.json")
    if run and not os.path.exists(rm):                                   # the Brain's evaluator runs once per campaign (its inputs do not change between avenues)
        rdir = os.path.join(ws, "research")
        force_rmtree(rdir)                                               # idempotent: a re-run (retry) starts clean
        os.makedirs(rdir, exist_ok=True)
        res = run_command(expand(run["cmd"], ctx(c, st, bid, rdir)), cwd=expand([run.get("cwd", "{engine}")], ctx(c, st, bid, rdir))[0], out_dir=rdir,
                          timeout=run.get("timeout", timeout), extra_env=input_env(c, bid))
        out["adapter"] = {**{k: res[k] for k in ("rc", "seconds")}, "stderrTail": res["stderrTail"][-500:]}
        metrics = metrics_from(res, rdir)
        if res["rc"] == 2 and metrics.get("blocked"):                    # a missing external input: recorded, the campaign continues
            out["adapterBlocked"] = metrics["blocked"]
        elif res["rc"] != 0:
            raise RuntimeError(f"research adapter failed rc={res['rc']}: {res['stderrTail'][-300:]}")
        atomic_json(rm, metrics)
    elif os.path.exists(rm):
        prev = json.load(open(rm, encoding="utf-8"))
        if prev.get("blocked"):
            out["adapterBlocked"] = prev["blocked"]
    if os.path.exists(rm):
        out["metrics"] = json.load(open(rm, encoding="utf-8"))
    if not os.path.exists(submitted) and ad.get("fixtureFindings") and st.get("verification"):
        # verification only: a controlled fixture standing in for agent-written findings (clearly labelled FIXTURE in the report)
        fx = json.load(open(os.path.join(HERE, ad["fixtureFindings"]), encoding="utf-8"))
        fx = json.loads(json.dumps(fx).replace("{campaign}", c.cid))
        atomic_json(submitted, fx)
        out["mode"] = out["mode"] + "+fixture-findings"
    an = run_analysis(c, c.load(), bid)
    if an is not None:
        atomic_json(os.path.join(ws, "discovery-metrics.json"), an["metrics"])
        prior = json.load(open(submitted, encoding="utf-8")) if os.path.exists(submitted) else {"schema": FINDINGS_SCHEMA, "brainId": bid, "findings": []}
        keep = [f for f in prior.get("findings") or [] if not f.get("auto")]     # agent-written findings are kept; auto ones are regenerated
        if an["findings"] or keep:
            atomic_json(submitted, {"schema": FINDINGS_SCHEMA, "brainId": bid, "campaignId": c.cid, "findings": keep + an["findings"]})
        cur = (c.load()["tracks"][bid].get("avenue") or {}).get("id")
        out.update({"discoveryFindings": len(an["findings"]), "weak": an["weakByAvenue"].get(cur, [])[:50], "limitations": an["limitations"],
                    "owner": an["owner"], "agentTasks": an["agentTasks"][:10], "integration": an["integration"]})
        if an["findings"]:
            out["mode"] = "discovery" + ("+agent-findings" if keep else "")
    out["findings"] = len((json.load(open(submitted, encoding="utf-8")) if os.path.exists(submitted) else {}).get("findings") or [])
    return out


def ctx(c: Campaign, st: dict, bid: str, out_dir: str) -> dict:
    return {"engine": ENGINE, "home": c.home, "folder": c.folder(st, bid), "out": out_dir, "campaign": c.cid, "python": sys.executable}


def _cmp(val, op, thr):
    if not isinstance(val, (int, float)) or isinstance(val, bool) or not isinstance(thr, (int, float)):
        return None
    return {">=": val >= thr, "<=": val <= thr, ">": val > thr, "<": val < thr, "==": val == thr}.get(op)


def validate_finding(f: dict, home: str, metrics: dict) -> tuple[str, str, dict | None]:
    """VALIDATED only when the claim is backed by hashed evidence AND meets what its tier means. Returns (verdict, reason, measured)."""
    for k in ("id", "claim", "kind", "evidence", "validation"):
        if not f.get(k):
            return "REJECTED", f"schema: missing {k}", None
    if f["kind"] not in ("RULE", "PARAMETER", "EVIDENCE", "DATASET"):
        return "REJECTED", f"schema: kind {f['kind']!r}", None
    tier = f.get("tier") or "EVIDENCE_LEAD"
    if tier not in L.RANK:
        return "REJECTED", f"schema: tier {tier!r}", None
    for ev in f["evidence"]:
        p = ev.get("path")
        if not p or not ev.get("sha256"):
            return "REJECTED", "evidence needs a research-home path and sha256 (provenance)", None
        full = os.path.join(home, p)
        if not inside(full, home) or not os.path.isfile(full):
            return "REJECTED", f"evidence not found in the research home: {p}", None
        if sha256(full) != ev["sha256"]:
            return "REJECTED", f"evidence sha256 mismatch: {p}", None
    v = f["validation"]
    val = get_path(metrics, v.get("metric", ""))
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        return "REJECTED", f"validator metric {v.get('metric')!r} not produced by the Brain's validator", None
    ok = _cmp(val, v.get("op", ">="), v.get("threshold"))
    if ok is None:
        return "REJECTED", f"validation threshold/op invalid ({v.get('op')} {v.get('threshold')!r})", None
    if not ok:
        return "REJECTED", f"{v['metric']} = {val} fails {v.get('op', '>=')} {v['threshold']}", None
    why = f"{v['metric']} = {val} {v.get('op', '>=')} {v['threshold']}"
    measured = None
    cap = f.get("capability")
    if tier == "INDEPENDENTLY_VALIDATED" and not cap:
        return "REJECTED", "an independently validated improvement needs a capability test on data not used to build it", None
    if L.rank(tier) >= L.rank("CANDIDATE_CHANGE"):
        ch = f.get("change") or {}
        missing = [k for k in L.CHANGE_FIELDS if not ch.get(k)]
        if missing:
            return "REJECTED", f"a {tier} finding must document the change: missing {', '.join(missing)}", None
    if cap:
        for tst in cap.get("tests") or []:
            r = _cmp(get_path(metrics, tst["metric"]), tst.get("op", ">="), tst.get("threshold"))
            if r is None:
                return "REJECTED", f"capability test metric {tst['metric']!r} not produced", None
            if not r:
                return "REJECTED", f"capability test failed: {tst['metric']} = {get_path(metrics, tst['metric'])} not {tst.get('op', '>=')} {tst.get('threshold')}", None
        b, cn, n = get_path(metrics, cap["baselineMetric"]), get_path(metrics, cap["candidateMetric"]), get_path(metrics, cap.get("nMetric", ""))
        if not all(isinstance(x, (int, float)) for x in (b, cn)):
            return "REJECTED", "capability baseline/candidate metrics not produced", None
        delta = (b - cn) if cap.get("direction") == "lower_better" else (cn - b)
        improved = delta >= cap.get("minDelta", 0) and (not cap.get("minN") or (isinstance(n, (int, float)) and n >= cap["minN"])) and \
            (tier == "INDEPENDENTLY_VALIDATED" or cap.get("kind") == "coverage")
        measured = {"capability": cap.get("name"), "kind": cap.get("kind"), "baselineKind": cap.get("baselineKind"), "baseline": b, "candidate": cn, "delta": round(delta, 4), "n": n,
                    "direction": cap.get("direction"), "improved": bool(improved)}
        why += f"; {cap.get('name')}: {b} -> {cn} (delta {round(delta, 4)}, n={n})"
    return "VALIDATED", why, measured


def stage_validate(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    ws = c.workspace(st, bid)
    fpath = os.path.join(ws, "findings.json")
    if not os.path.exists(fpath):
        return {"findings": 0, "validated": 0, "rejected": 0, "metricsAvailable": [], "note": "no findings submitted for this track"}
    doc = json.load(open(fpath, encoding="utf-8"))
    if doc.get("schema") != FINDINGS_SCHEMA or doc.get("brainId") != bid:
        raise RuntimeError("findings.json is not a sector-research-findings-v1 document for this Brain")
    metrics = {}
    run = ad.get("validate")
    vres = None
    vdir = os.path.join(ws, "validate")
    if run:
        vok = os.path.join(vdir, ".ok")
        if not os.path.exists(vok):                                      # the Brain's validator runs once per campaign; its result is reused by later avenues
            force_rmtree(vdir)
            os.makedirs(vdir, exist_ok=True)
            vres = run_command(expand(run["cmd"], ctx(c, st, bid, vdir)), cwd=expand([run.get("cwd", "{engine}")], ctx(c, st, bid, vdir))[0], out_dir=vdir,
                               timeout=run.get("timeout", timeout))
            metrics = metrics_from(vres, vdir)
            if vres["rc"] != 0:
                raise RuntimeError(f"validator failed rc={vres['rc']}: {vres['stderrTail'][-300:]}")
            open(vok, "w").write("ok")
        else:
            metrics = metrics_from({"stdoutTail": ""}, vdir)
    rm = os.path.join(ws, "research-metrics.json")
    if os.path.exists(rm):
        metrics = {"research": json.load(open(rm, encoding="utf-8")), **metrics}
    dm = os.path.join(ws, "discovery-metrics.json")
    reproducible = None
    if os.path.exists(dm):                                               # independent offline re-run from the saved, hashed evidence
        again = run_analysis(c, c.load(), bid)
        reproducible = again is not None and json.dumps(again["metrics"], sort_keys=True) == json.dumps(json.load(open(dm, encoding="utf-8")), sort_keys=True)
        metrics = {**metrics, "discovery": again["metrics"] if reproducible else {}}
    results = []
    for f in doc.get("findings") or []:
        verdict, why, measured = validate_finding(f, c.home, metrics)
        results.append({"id": f.get("id"), "kind": f.get("kind"), "tier": f.get("tier") or "EVIDENCE_LEAD", "verdict": verdict, "reason": why, "fixture": bool(f.get("fixture")),
                        "measured": measured, "addresses": f.get("addresses") or [], "resolves": f.get("resolves") or [], "avenue": f.get("avenue"),
                        "hypothesis": bool(f.get("change")) and verdict == "REJECTED"})
    atomic_json(os.path.join(ws, "validation.json"), {"campaignId": c.cid, "brainId": bid, "validator": run and run["cmd"], "metrics": metrics,
                                                      "results": results, "at": now_iso()})
    flat = []
    def walk(o, pre=""):
        for k, v in (o.items() if isinstance(o, dict) else []):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                flat.append(pre + k)
            elif isinstance(v, dict):
                walk(v, pre + k + ".")
    walk(metrics)
    ok = [r for r in results if r["verdict"] == "VALIDATED" and not r["fixture"]]
    by_tier: dict = {}
    for r in ok:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
    return {"metricsAvailable": sorted(flat), "findings": len(results), "validated": sum(r["verdict"] == "VALIDATED" for r in results),
            "rejected": sum(r["verdict"] == "REJECTED" for r in results), "results": results, "validatedByTier": by_tier,
            "scientificSupport": sum(1 for r in ok if L.rank(r["tier"]) >= L.rank("SCIENTIFIC_SUPPORT")),
            "improvements": [r["id"] for r in ok if (r["measured"] or {}).get("improved")],
            "validator": {"rc": vres["rc"], "seconds": vres["seconds"]} if vres else None, "discoveryReproducible": reproducible}


def stage_candidate(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    """Package validated findings. Scientific improvement and administrative packaging are different: a package with no validated candidate
    change is labelled EVIDENCE_ONLY and never counts as an improved Brain. Rejected hypotheses are preserved with their numbers."""
    ws = c.workspace(st, bid)
    vpath = os.path.join(ws, "validation.json")
    if not os.path.exists(vpath):
        return {"packaged": False, "reason": "no validation results"}
    val = json.load(open(vpath, encoding="utf-8"))
    ok_ids = {r["id"] for r in val["results"] if r["verdict"] == "VALIDATED"}
    if not ok_ids:
        return {"packaged": False, "reason": "no VALIDATED finding: no candidate is generated (rejections are recorded)"}
    allf = json.load(open(os.path.join(ws, "findings.json"), encoding="utf-8"))["findings"]
    findings = [f for f in allf if f.get("id") in ok_ids]
    res = {r["id"]: r for r in val["results"]}
    changes = [{"id": f["id"], "tier": f.get("tier"), "claim": f["claim"], **f["change"], "measured": res[f["id"]]["measured"] or {"improved": False}, "addresses": f.get("addresses") or []}
               for f in findings if L.rank(f.get("tier")) >= L.rank("CANDIDATE_CHANGE") and f.get("change") and not f.get("fixture")]
    rejected = [{"id": f["id"], "tier": f.get("tier"), "claim": f["claim"], **f["change"], "rejectedBecause": res[f["id"]]["reason"]}
                for f in allf if f.get("change") and res.get(f["id"], {}).get("verdict") == "REJECTED"]
    improved = [x["id"] for x in changes if x["measured"].get("improved")]
    lifecycle = "CANDIDATE" if changes else "EVIDENCE_ONLY"
    target = os.path.join(c.folder(st, bid), "candidates", c.cid)
    if inside(target, ENGINE):
        raise RuntimeError("refused: a campaign never writes into the Engine repository (approved memory is promoted by a gated review)")
    staging = target + ".staging"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    atomic_json(os.path.join(staging, "findings.json"), {"schema": FINDINGS_SCHEMA, "brainId": bid, "campaignId": c.cid, "findings": findings})
    atomic_json(os.path.join(staging, "validation.json"), val)
    names = ["findings.json", "validation.json"]
    if changes:
        atomic_json(os.path.join(staging, "candidate-changes.json"), {"schema": "sector-candidate-changes-v1", "brainId": bid, "campaignId": c.cid, "changes": changes})
        names.append("candidate-changes.json")
    if rejected:
        atomic_json(os.path.join(staging, "rejected-hypotheses.json"), {"schema": "sector-rejected-hypotheses-v1", "brainId": bid, "campaignId": c.cid, "hypotheses": rejected})
        names.append("rejected-hypotheses.json")
    diff = [f"# Scientific difference — {bid} — {c.cid}", ""]
    if changes:
        for x in changes:
            m = x["measured"]
            diff += [f"## {x['id']} ({x['tier']})", f"- Change: {x['scientificChange']}", f"- Previous: {x['previous']}",
                     f"- Proposed: {json.dumps(x['proposed'])[:600]}", f"- Evidence: {x['evidenceSummary']}", f"- Validation method: {x['validationMethod']}",
                     f"- Validation results: {json.dumps(x['validationResults'])}", f"- Measured: {json.dumps(m)}", f"- Practical effect: {x['practicalEffect']}",
                     f"- Score impact: {x['scoreImpact']}", f"- Limitations: {x['limitations']}", ""]
    else:
        diff += ["**None.** This package contains evidence only (acquired, quality-checked or literature-lead findings). It changes no rule, parameter or boundary and "
                 "does not improve this Brain. It is administrative packaging of evidence.", ""]
    if rejected:
        diff += ["## Rejected hypotheses (preserved)", *[f"- {x['id']}: {x['rejectedBecause']}" for x in rejected], ""]
    open(os.path.join(staging, "SCIENTIFIC_DIFFERENCE.md"), "w", encoding="utf-8").write("\n".join(diff))
    names.append("SCIENTIFIC_DIFFERENCE.md")
    files = K.describe_files(staging, names)
    rel_id = f"{bid}-research-candidate-{c.cid}"
    manifest = {"schemaVersion": K.SCHEMA_VERSION, "brainId": bid, "releaseId": rel_id, "store": "PACKAGED_IN_IMAGE", "owner": bid,
                "approval": {"status": "NOT_RECORDED", "record": None}, "files": files, "releaseDigest": K.release_digest(files),
                "lifecycle": lifecycle, "note": "Research campaign candidate. NOT approved memory: promotion into a Brain runtime is a separate, "
                                                "owner/reviewer-gated decision (M-3, G-1); never written by the campaign."}
    atomic_json(os.path.join(staging, K.MANIFEST), manifest)
    rel = K.load_release(staging, bid)                                  # the package verifies exactly like production memory would
    if rel["approvalStatus"] != "NOT_RECORDED":
        raise RuntimeError("refused: a campaign candidate is never approved")
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    return {"packaged": True, "releaseId": rel_id, "releaseDigest": rel["releaseDigest"], "approval": "NOT_RECORDED", "lifecycle": lifecycle,
            "scientificChanges": len(changes), "improvements": improved, "rejectedHypotheses": len(rejected),
            "path": os.path.relpath(target, c.home), "findings": sorted(ok_ids)}


def stage_score(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    """The Brain's own candidate score (non-authoritative) and the MEASURED capability change. The adapter score is the Brain's rubric evaluator
    run unchanged: it moves only if the rubric's inputs moved. Capability improvements are reported immediately and separately from it; an
    engineering score is a different thing and is never touched here."""
    run = ad.get("score")
    before = authoritative_hashes()
    out = {"authoritativeUnchanged": None, "candidateScore": None, "class": "SCIENTIFIC CANDIDATE (non-authoritative; engineering score is separate)"}
    if run:
        sdir = os.path.join(c.workspace(st, bid), "score")
        force_rmtree(sdir)
        os.makedirs(sdir, exist_ok=True)
        res = run_command(expand(run["cmd"], ctx(c, st, bid, sdir)), cwd=expand([run.get("cwd", "{engine}")], ctx(c, st, bid, sdir))[0], out_dir=sdir,
                          timeout=run.get("timeout", timeout))
        m = metrics_from(res, sdir)
        if res["rc"] != 0:
            raise RuntimeError(f"score adapter failed rc={res['rc']}: {res['stderrTail'][-300:]}")
        out.update({"candidateScore": get_path(m, run.get("value", "score")), "measure": run.get("measure"), "seconds": res["seconds"]})
    dm = os.path.join(c.workspace(st, bid), "discovery-metrics.json")
    if os.path.exists(dm):
        out["impact"] = json.load(open(dm, encoding="utf-8")).get("scoreImpact")
    val = st["tracks"][bid]["stages"]["validate"].get("result") or {}
    out["capabilityChanges"] = [{"finding": r["id"], **(r["measured"] or {})} for r in val.get("results") or []
                                if r["verdict"] == "VALIDATED" and r["measured"] and (r["measured"].get("improved") or (r["measured"].get("delta") or 0) > 0)]
    after = authoritative_hashes()
    out["authoritativeUnchanged"] = before == after == st["authoritativeBefore"]
    try:
        out["authoritativeBaseline"] = (json.load(open(os.path.join(ENGINE, "docs", "brains", "scoring", "frozen-scores.json"), encoding="utf-8")).get(bid) or {}).get("value")
    except (OSError, ValueError):
        out["authoritativeBaseline"] = None
    if not out["authoritativeUnchanged"]:
        raise RuntimeError("an authoritative score artifact changed during the campaign")
    return out


def capability_priority(c: Campaign, bid: str) -> int:
    """Research follows the weakest measured capability: a Brain whose bowfishing capability composite is low (or entirely unmeasured) is worked first. 10 = most urgent."""
    try:
        rp = os.path.join(c.home, "shared", "pilot", "guntersville-v1", "PILOT_V1_READINESS.json")
        ready = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else None
        v = BC.compute_brain(ENGINE, c.home, bid, discovery_cfg(), None, ready)["current"]
        comp = v["value"] if v["value"] is not None else 0.0
        return 10 + int(70 * comp) + TQ.BRAIN_PRIORITY.get(bid, 90) // 20
    except (OSError, ValueError, KeyError, StopIteration):
        return TQ.BRAIN_PRIORITY.get(bid, 90)


def write_agent_task(c: Campaign, st: dict, bid: str, gid: str, gap: dict, tried: list | None = None) -> str:
    """A self-contained brief for an agent (a coordinating Claude session or a subagent) to investigate a gap no configured avenue covers: find legitimate
    downloadable evidence anywhere, register the source, analyse it, and deliver findings through the same validator (tiers, hashes, thresholds)."""
    folder = c.folder(st, bid)
    p = os.path.join(folder, "research", "agent-tasks", D.safe_key(gid) + ".json")
    charter = {}
    cp = os.path.join(ENGINE, "brains", BRAIN_DIRS.get(bid, bid), "research", "CHARTER.json")
    if os.path.exists(cp):
        charter = json.load(open(cp, encoding="utf-8"))
    prior = []
    rp = os.path.join(folder, "research", "agent-results")
    if os.path.isdir(rp):                                                # what earlier agent runs already searched: never repeat it
        for fn in sorted(os.listdir(rp)):
            try:
                r = json.load(open(os.path.join(rp, fn), encoding="utf-8"))
                if r.get("gapId") == gid:
                    prior.append({"task": r.get("taskId"), "queriesTried": r.get("queriesTried"), "status": r.get("status"), "summary": r.get("summary")})
            except (OSError, ValueError):
                pass
    task = {"schema": "sector-agent-research-task-v1", "brainId": bid, "gapId": gid, "gap": gap.get("title"), "status": "OPEN", "createdBy": c.cid, "alreadyTried": {"avenues": tried or [], "priorAgentRuns": prior},
            "bowfishingPurpose": charter.get("bowfishingPurpose"), "priorityQuestions": charter.get("priorityQuestions"), "fitForPurposeTargets": charter.get("fitForPurpose"),
            "how": ["search the open web (scientific data repositories, agencies, journals' data supplements) for datasets that could resolve the gap; verify each landing page or API before relying on it",
                    "register an allowed host with `campaign.py register-source` (https, licence, purpose, rationale) or record an owner-action if access needs the owner",
                    "download within limits, hash and register the evidence; analyse it offline; pre-declare thresholds before looking at results",
                    "deliver findings with `campaign.py submit` (schema sector-research-findings-v1, tiers, change documentation); unsupported conclusions are rejected and kept as rejected hypotheses",
                    "if the evidence cannot resolve a validation or access restriction, record the exact limitation and move on"],
            "mustNot": ["treat a missing connector as no evidence", "invent a score", "open sealed or protected holdouts", "approve or publish anything"]}
    os.makedirs(os.path.dirname(p), exist_ok=True)
    atomic_json(p, task)
    return os.path.relpath(p, c.home)


def score_display(bid: str, sc: dict) -> str:
    """R1/R2: a typed constant is never printed as a result; every candidate score names its rubric, source and whether it can move."""
    m = brain_spec(bid).get("scoreMeta") or {}
    v = sc.get("candidateScore")
    shown = "not a result (typed constant)" if m.get("source") == "TYPED_NOT_COMPUTED" else ("—" if v is None else str(v))
    deltas = "; ".join(f"{x.get('capability')}: {x.get('baseline')} -> {x.get('candidate')}" for x in sc.get("capabilityChanges") or []) or "no measured capability change"
    return (f"scientific candidate, non-authoritative: {shown} [{m.get('rubricId', '?')}, class {m.get('class', '?')}, {m.get('source', 'unlabelled')}; "
            f"movable: {m.get('movable', 'unknown')}; measured: {deltas}]")


def classify(c: Campaign, st: dict, bid: str, led: L.Ledger, why_stop: str) -> dict:
    """Honest per-Brain outcome of an improvement campaign: IMPROVED, STALLED, BLOCKED or BUDGET_REACHED. Evidence alone is never IMPROVED."""
    t = st["tracks"][bid]
    mine = {k: v for k, v in led.doc["avenues"].items() if v["campaign"] == c.cid}
    improved = [v["id"] for k, v in mine.items() if v["outcome"] == "IMPROVED"]
    gaps = led.doc["gaps"]
    actionable = [g for g, v in gaps.items() if v["status"] in L.ACTIONABLE]
    blocked = [g for g, v in gaps.items() if v["status"].startswith("BLOCKED")]
    exhausted = [g for g, v in gaps.items() if v["status"] == "EXHAUSTED"]
    nexts = sorted({b["nextEvidenceSource"] for g in blocked for b in gaps[g]["blockers"]})
    for g, v in gaps.items():                                            # a gap left open with no recorded blocker still needs its next evidence source named
        if v["status"] in L.ACTIONABLE + ("EXHAUSTED",) and not v["blockers"]:
            nexts.append(f"{g}: " + (v.get("nextEvidence") or "no avenue is configured that can move this gap - register a source or experiment for it in tools/research/discovery.json"))
    nexts = sorted(set(nexts))
    gained = sorted({v["bestTier"] for v in mine.values() if v.get("bestTier")}, key=L.rank)
    if improved:
        outcome = "IMPROVED"
    elif why_stop == "budget":
        outcome = "BUDGET_REACHED"
    elif blocked and not actionable and not exhausted:
        outcome = "BLOCKED"
    else:
        outcome = "STALLED"
    reason = {"IMPROVED": f"{len(improved)} measured capability improvement(s): {', '.join(improved)}",
              "BUDGET_REACHED": "the research budget ended with actionable avenues still untried",
              "BLOCKED": "every remaining gap needs external data or an owner approval",
              "STALLED": "no avenue left that could move a remaining gap" if not why_stop == "no-progress" else "consecutive avenues produced no new evidence and no new validated finding"}[outcome]
    untried = [a["id"] for a in avenues_for(bid) if not any(k.startswith(a["id"] + ":") and v["campaign"] == c.cid for k, v in led.doc["avenues"].items())]
    return {"outcome": outcome, "reason": reason, "improvements": improved, "evidenceTiersReached": gained, "avenuesRun": len(mine),
            "gaps": {g: v["status"] for g, v in gaps.items()}, "actionableGaps": actionable, "blockedGaps": blocked, "nextEvidenceSources": nexts,
            "improvementCampaignSuccessful": outcome == "IMPROVED", "untriedAvenues": untried}


def stage_followup(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    """Decide from the persistent gap ledger - not from a connector's own sanity check - whether research continues: record what the last
    avenue achieved, then run the next untried avenue for a still-actionable gap, within the declared budget. Stops only as IMPROVED-with-
    nothing-left, STALLED, BLOCKED or BUDGET_REACHED, each with its exact reason."""
    t = c.load()["tracks"][bid]
    led = ledger(c, st, bid)
    av = t.get("avenue")
    res = st["tracks"][bid]["stages"]["research"].get("result") or {}
    val = st["tracks"][bid]["stages"]["validate"].get("result") or {}
    avs = avenues_for(bid)
    if av:
        targets = t.get("followupTargets") if av.get("when") == "weak" else None
        key = L.avenue_key(av, targets)
        entry = next((a for a in t.get("acquired") or [] if a.get("avenueKey") == key), {})
        mine = [r for r in val.get("results") or [] if r.get("avenue") == av["id"]]
        okm = [r for r in mine if r["verdict"] == "VALIDATED" and not r["fixture"]]
        new_ev = led.seen_evidence(entry.get("shas") or [])
        for r in okm:
            led.touch(r["addresses"], r["tier"], r["id"], set(r["resolves"]), bool((r["measured"] or {}).get("improved")))
        best = max((r["tier"] for r in okm), key=L.rank, default=None)
        outcome = "IMPROVED" if any((r["measured"] or {}).get("improved") for r in okm) else ("EVIDENCE" if okm else "NO_RESULT")
        if entry.get("failureCount") and not entry.get("evidenceFiles") and av["run"] != "upstream":
            outcome = "SOURCES_UNREACHABLE"
        new_f = led.seen_findings([f"{av['id']}:{r['id']}" for r in okm])
        rh = hashlib.sha256(json.dumps(sorted((r["id"], r["verdict"], r["reason"]) for r in mine)).encode()).hexdigest()[:16] if okm else ""   # failed searches carry no result
        led.record(key, av, c.cid, outcome, best, new_ev, "; ".join(r["reason"][:120] for r in mine[:2]), new_f, rh)
        led.doc["avenues"][key]["acquiring"] = bool(av.get("acquiring", av.get("run") == "connector" or av.get("experiment") in ("dataset-search", "lake-cwms")))
        for o in res.get("owner") or []:
            if o.get("avenue") == av["id"]:
                rec = D.owner_action(c.home, t["folder"], c.cid, o["id"], o.get("gap") or "", o["publisher"], o["dataset"], o["access"], bool(o.get("verified")), o.get("checked") or [], o["addresses"])
                led.block(o.get("gap") or (av.get("gaps") or [""])[0], "external", f"{o['dataset']} ({rec['path']})", f"{o['publisher']}: {o['access']}", c.cid)
        for lim in res.get("limitations") or []:
            if lim.get("kind") in ("external", "approval") and lim.get("gap"):
                led.block(lim["gap"], lim["kind"], lim["limitation"], lim.get("nextSource") or "owner action (see limitation)", c.cid)
        for g, v in list(led.doc["gaps"].items()):                      # a gap served by an avenue that found nothing stays INVESTIGATING, never closed
            if av["id"] and g in (av.get("gaps") or []) and v["status"] == "OPEN":
                v["status"] = "INVESTIGATING"
    improved_ladders = {a["ladder"] for a in avs if a.get("ladder") and any(k.startswith(a["id"] + ":") and v["outcome"] == "IMPROVED" and v["campaign"] == c.cid
                                                                             for k, v in led.doc["avenues"].items())}
    last_weak = list(res.get("weak") or [])
    runs = [v for v in led.doc["avenues"].values() if v["campaign"] == c.cid]
    b = budget(st)
    why_stop, nxt = "", None
    if time.time() > st.get("deadline", float("inf")):
        why_stop = "budget"
    elif len(runs) >= int(b.get("maxAvenues", 50)):
        why_stop = "budget"
    elif sum(a.get("bytes", 0) for a in (t.get("acquired") or [])[-1:]) > int(b.get("maxBytesPerBrain", 5e8)):
        why_stop = "budget"
    else:
        # stall detection guards ACQUISITION loops (downloads and searches). Deterministic analysis avenues are finite and always get their turn.
        acq_runs = [v for v in runs if v.get("acquiring")]
        tail = acq_runs[-int(b.get("stallAvenues", 3)):]
        if len(tail) >= int(b.get("stallAvenues", 3)) and all(v["newEvidence"] == 0 and v.get("newFindings", 0) == 0 and not v.get("changed") and v["outcome"] != "IMPROVED" for v in tail):
            why_stop = "no-progress"
        else:
            nxt = L.next_avenue(avs, led, last_weak, improved_ladders, c.cid) if st.get("discovery", True) else None
    hist = {"avenue": (av or {}).get("id"), "outcome": led.doc["avenues"].get(L.avenue_key(av, t.get("followupTargets") if av.get("when") == "weak" else None), {}).get("outcome") if av else None,
            "validated": val.get("validated", 0), "scientificSupport": val.get("scientificSupport", 0), "improvements": val.get("improvements", [])}
    if nxt and not why_stop:
        led.save()
        with _lock:
            s2 = c.load()
            tr = s2["tracks"][bid]
            tr["history"] = (tr.get("history") or []) + [hist]
            tr["avenue"], tr["followupTargets"], tr["iteration"] = nxt[0], nxt[1], t.get("iteration", 1) + 1
            for s in ITERATION_STAGES:
                if s != "followup":
                    tr["stages"][s] = {"status": "PENDING", "attempts": 0}
            atomic_json(c.state_path, s2)
        c.log(event="followup", brain=bid, next=nxt[0]["id"], targets=(nxt[1] or [])[:20])
        return {"continued": True, "nextAvenue": nxt[0]["id"], "targets": (nxt[1] or [])[:50], **hist}
    served = {g for a in avs for g in a.get("gaps") or []}
    tried = sorted({v["id"] for v in led.doc["avenues"].values()})
    for g in list(led.actionable()):                                    # a gap NO avenue serves, or whose configured avenues are all used up, is not finished:
        if "GEN-CLOSEOUT" in g or g in (brain_spec(bid).get("internalGaps") or []):      # closeout fragments and internal contract fixes are not open-web research questions
            continue
        gp = led.doc["gaps"][g]                                         # the coordinator QUEUES executable agent research (open web beyond the configured sources)
        task = write_agent_task(c, st, bid, g, gp, tried)
        qt = TQ.enqueue(c.home, bid, g, "agent-research", f"{bid}: {gp.get('title')}", task, c.cid, topic="open-web", priority=capability_priority(c, bid))
        gp["nextEvidence"] = f"queued agent research {qt['id']} ({qt['status']}): {task}"
    cls = classify(c, st, bid, led, why_stop)
    if cls["outcome"] in ("STALLED",):                                  # exhausted means: every configured avenue was tried - never that nothing exists
        for g in list(led.actionable()):
            if g in served and not any(t["gap"] == g and t["brain"] == bid and t["status"] in ("QUEUED", "CLAIMED") for t in TQ.load(c.home)["tasks"]):
                led.exhaust(g, f"all {len(avs)} configured avenues and the queued agent research were used up; register a new source or experiment to continue")
        cls = classify(c, st, bid, led, why_stop)
    led.save()
    with _lock:
        s2 = c.load()
        s2["tracks"][bid]["history"] = (s2["tracks"][bid].get("history") or []) + [hist]
        s2["tracks"][bid]["outcome"] = cls
        atomic_json(c.state_path, s2)
    return {"continued": False, "stop": why_stop or "no actionable avenue remains", **cls, **hist}


def stage_cleanup(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    folder = c.folder(st, bid)
    ws = c.workspace(st, bid)
    deleted, kept_bytes = [], 0
    marker = os.path.join(ws, OWNER_MARKER)
    if os.path.isdir(ws):
        owner = json.load(open(marker, encoding="utf-8")) if os.path.exists(marker) else {}
        if owner.get("campaignId") != c.cid or not inside(ws, os.path.join(folder, "analysis", "tmp")):
            raise RuntimeError(f"refused: {ws} is not owned by campaign {c.cid}; nothing deleted")
        for root, _, files in os.walk(ws):
            for f in files:
                deleted.append(os.path.relpath(os.path.join(root, f), c.home))
        force_rmtree(ws)
    tmp = os.path.join(folder, "analysis", "tmp")
    if os.path.isdir(tmp) and not os.listdir(tmp):
        os.rmdir(tmp)
    # retained outputs -> manifest (RS-02) and task record (RS-05)
    mpath = os.path.join(folder, "manifest.json")
    m = json.load(open(mpath, encoding="utf-8"))
    cand = st["tracks"][bid]["stages"]["candidate"].get("result") or {}
    added = []
    if cand.get("packaged"):
        cdir = os.path.join(c.home, cand["path"])
        for f in sorted(os.listdir(cdir)):
            full = os.path.join(cdir, f)
            iid = f"{c.cid}:{f}"
            m["items"] = [i for i in m.get("items") or [] if i.get("id") != iid]
            m["items"].append({"id": iid, "workspacePath": os.path.relpath(full, folder), "sha256": sha256(full), "bytes": os.path.getsize(full),
                               "source": f"research campaign {c.cid}", "provenance": "tools/research/campaign.py (validated findings only)",
                               "retention": "ACTIVE", "version": cand["releaseId"], "license": "internal research",
                               "reconstruction": "re-run the campaign from its findings and validation inputs"})
            kept_bytes += os.path.getsize(full)
            added.append(iid)
    closeout_rel = os.path.join("closeouts", f"{dt.date.today().isoformat()}-{c.cid}.md")
    m["tasks"] = [t for t in m.get("tasks") or [] if t.get("id") != c.cid] + [{"id": c.cid, "status": "DONE", "closeout": closeout_rel,
                                                                                "finishedAt": now_iso()}]
    m["lastUpdated"] = now_iso()
    atomic_json(mpath, m)
    val = st["tracks"][bid]["stages"]["validate"].get("result") or {}
    sc = st["tracks"][bid]["stages"]["score"].get("result") or {}
    body = {
        "Preserved results": f"{len(added)} retained file(s) registered in manifest.json ({kept_bytes} bytes): {', '.join(added) or 'none'}; "
                             f"acquired evidence: {sum(a.get('evidenceFiles', 0) for a in (st['tracks'][bid].get('acquired') or [])[-1:])} source file(s) "
                             f"under {((st['tracks'][bid].get('acquired') or [{}])[-1].get('evidenceRoot') or 'sources/' + c.cid)} (RECONSTRUCTABLE, provenance in PROVENANCE.json)",
        "Manifests updated": f"{os.path.relpath(mpath, c.home)}: items + task {c.cid} (DONE)",
        "Candidate knowledge": (f"{cand.get('releaseId')} [{cand.get('lifecycle')}: {cand.get('scientificChanges', 0)} scientific change(s), "
                                f"{cand.get('rejectedHypotheses', 0)} rejected hypothesis] (approval NOT_RECORDED; digest {cand.get('releaseDigest')}); validated "
                                f"{val.get('validated', 0)}, rejected {val.get('rejected', 0)}" if cand.get("packaged") else f"none ({cand.get('reason', 'not packaged')}); "
                                f"validated {val.get('validated', 0)}, rejected {val.get('rejected', 0)}") +
                                f". Scientific candidate score (NON-AUTHORITATIVE, {(brain_spec(bid).get('scoreMeta') or {}).get('source', 'unlabelled')}; engineering score is separate): "
                                f"{score_display(bid, sc)}; authoritative scores unchanged: {sc.get('authoritativeUnchanged')}",
        "Backups verified": "no new ARCHIVAL data; existing backups untouched (campaign outputs are ACTIVE and reconstructable)",
        "Deleted": f"{len(deleted)} campaign-owned disposable file(s) under analysis/tmp/{c.cid}",
        "Worktrees": "none created by the campaign harness",
        "Blockers": (f"research outcome {(st['tracks'][bid].get('outcome') or {}).get('outcome')}: {(st['tracks'][bid].get('outcome') or {}).get('reason')}; "
                     f"next evidence: {'; '.join((st['tracks'][bid].get('outcome') or {}).get('nextEvidenceSources') or []) or 'none recorded'}; "
                     "promotion to approved memory needs owner/reviewer approval (M-3, G-1)"),
    }
    text = f"# Research closeout — {bid} — campaign {c.cid}\n\n" + "\n".join(f"## {k}\n\n{v}\n" for k, v in body.items())
    os.makedirs(os.path.join(folder, "closeouts"), exist_ok=True)
    open(os.path.join(folder, closeout_rel), "w", encoding="utf-8").write(text)
    return {"deleted": len(deleted), "retained": added, "closeout": os.path.join(st["tracks"][bid]["folder"], closeout_rel)}


STAGE_FN = {"discover": stage_discover, "acquire": stage_acquire, "research": stage_research, "validate": stage_validate,
            "candidate": stage_candidate, "score": stage_score, "followup": stage_followup, "cleanup": stage_cleanup}


# ------------------------------------------------------------------------------------------------------------------------------- runner
def run_track(c: Campaign, bid: str, adapters: dict, timeout: int) -> str:
    st = c.load()
    ad = adapters.get(bid) or {}
    s_i = 0
    while s_i < len(STAGES):
        s = STAGES[s_i]
        s_i += 1
        crash = os.environ.get("CAMPAIGN_CRASH_AT")                      # test hook: simulate an interruption (process killed mid-stage)
        with _lock:
            st = c.load()
            rec = st["tracks"][bid]["stages"][s]
            if rec["status"] == "DONE":
                continue
            if rec["status"] == "FAILED" and rec["attempts"] >= st["maxAttempts"]:
                return "FAILED"
            rec.update({"status": "RUNNING", "attempts": rec["attempts"] + 1, "startedAt": now_iso()})
            st["updatedAt"] = now_iso()
            atomic_json(c.state_path, st)
        c.log(event="stage-start", brain=bid, stage=s, attempt=rec["attempts"])
        if crash == f"{bid}:{s}":
            os._exit(137)
        try:
            result = STAGE_FN[s](c, st, bid, ad, timeout)
            status, err = "DONE", None
        except Exception as e:                                          # failure isolation: this track stops, the others continue
            result, status, err = None, "FAILED", f"{type(e).__name__}: {e}"[:600]
        with _lock:
            st = c.load()
            rec = st["tracks"][bid]["stages"][s]
            rec.update({"status": status, "finishedAt": now_iso(), "result": result, "error": err})
            if s == "followup" and (result or {}).get("continued"):     # the next iteration evaluates its own follow-up
                rec.update({"status": "PENDING", "attempts": 0})
            st["updatedAt"] = now_iso()
            atomic_json(c.state_path, st)
        c.log(event="stage-end", brain=bid, stage=s, status=status, error=err)
        if status == "FAILED":
            return "RETRY" if rec["attempts"] < st["maxAttempts"] else "FAILED"
        if s == "followup" and (result or {}).get("continued"):
            s_i = STAGES.index("acquire")                                # the next iteration (its stages were re-opened)
    return "DONE"


def run(home: str, cid: str, parallel: int = 3, timeout: int = 600, adapters: dict | None = None, fetcher: D.Fetcher | None = None,
        retry_failed: bool = False) -> dict:
    global _fetcher
    _fetcher = fetcher or D.Fetcher(home=home)
    c = Campaign(home, cid)
    st = c.load()
    if "deadline" not in st:                                             # the research window starts with the first run and survives resumes
        st["deadline"] = time.time() + float(budget(st).get("wallSeconds", 8 * 3600))
        st["startedAt"] = now_iso()
    adapters = adapters if adapters is not None else load_adapters()
    # an interrupted run leaves RUNNING stages: they are re-run (idempotent)
    for t in st["tracks"].values():
        for s in t["stages"].values():
            if s["status"] == "RUNNING":
                s["status"] = "INTERRUPTED"
            if retry_failed and s["status"] == "FAILED":                 # after a fix: re-open only what failed; DONE work is kept
                s.update({"status": "PENDING", "attempts": 0, "retriedAfterFailure": s.get("error")})
    c.save(st)
    c.log(event="run", parallel=parallel)
    finished: dict = {}
    pending = set(st["tracks"])
    with cf.ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        futs: dict = {}
        while pending or futs:
            for bid in sorted(pending):
                deps = st["tracks"][bid]["dependsOn"]
                if all(finished.get(d) in ("DONE", "FAILED") for d in deps):     # a failed dependency does not block (its gaps are reported)
                    futs[ex.submit(run_track, c, bid, adapters, timeout)] = bid
                    pending.discard(bid)
            if not futs:
                break
            done, _ = cf.wait(list(futs), return_when=cf.FIRST_COMPLETED)
            for f in done:
                bid = futs.pop(f)
                r = f.result()
                if r == "RETRY":
                    pending.add(bid)
                else:
                    finished[bid] = r
    write_report(c)
    return finished


# ------------------------------------------------------------------------------------------------------------------------------- autonomous loop
RESULT_SCHEMA = "sector-agent-result-v1"
DEFAULT_EXECUTOR = {"name": "claude-cli", "maxBudgetUsd": 2.0, "timeoutSeconds": 1500,
                    "command": ["claude", "-p", "{prompt}", "--allowedTools", "WebSearch", "WebFetch", "Write", "Read", "--add-dir", "{work}", "--permission-mode", "dontAsk",
                                "--max-budget-usd", "{budget}", "--no-session-persistence", "--output-format", "text"]}


def result_prompt(t: dict, brief: dict, result_path: str) -> str:
    return ("You are a research agent for Sector, a BOWFISHING intelligence system (shooting rough fish with a bow at night in shallow water, in US reservoirs and rivers). "
            "Investigate the gap below by searching the open web for LEGITIMATE, OPEN, DOWNLOADABLE data or published evidence that could close it. Verify every source by opening it (publisher, exact URL, direct "
            "file/API URL, licence, size, date range, coverage, whether login is needed). Do not download files larger than 5 MB. Prefer data that bears on real bowfishing outcomes (where fish are, when "
            "they use accessible shallow water, visibility, conditions); transferable studies are evidence, not validation. Do not repeat anything in `alreadyTried`. Never invent a source or a result.\n\n"
            f"TASK (JSON):\n{json.dumps({**brief, 'taskId': t['id']}, indent=1)[:6000]}\n\n"
            f"Write ONLY a JSON file to {result_path} with this shape (schema {RESULT_SCHEMA}):\n"
            '{"schema": "sector-agent-result-v1", "taskId": "<id>", "gapId": "<gap>", "status": "FINDINGS | NO_USABLE_EVIDENCE | BLOCKED", "summary": "...", "queriesTried": ["..."], '
            '"datasets": [{"title": "...", "publisher": "...", "url": "<landing page>", "directUrl": "<direct https file or API url or null>", "licence": "...", "sizeBytes": 0, "dateRange": "...", '
            '"coverage": "...", "verifiedAccess": true, "relevance": "how it bears on the gap", "analysisPlan": "columns and the test to run"}], '
            '"ownerActions": [{"id": "...", "publisher": "...", "dataset": "...", "access": "...", "verified": false, "addresses": "..."}], "limitations": ["..."], "nextSource": "..."}\n'
            "Mark verifiedAccess true only if you fetched it yourself. When nothing usable exists say NO_USABLE_EVIDENCE with the queries you tried. After writing the file reply with one line.")


def execute_task(home: str, t: dict, cfg: dict) -> tuple[str, str | None]:
    """Run ONE agent task with the configured executor. Returns ('ok'|'error', detail). The executor writes work/result.json; nothing else is trusted."""
    work = os.path.join(home, "shared", "queue", "work", t["id"])
    os.makedirs(work, exist_ok=True)
    result = os.path.join(work, "result.json")
    if os.path.exists(result):
        os.remove(result)
    brief = json.load(open(os.path.join(home, t["brief"]), encoding="utf-8")) if os.path.exists(os.path.join(home, t["brief"])) else {}
    prompt = result_prompt(t, brief, result)
    pf = os.path.join(work, "prompt.txt")
    open(pf, "w", encoding="utf-8").write(prompt)
    cmd = [x.format(prompt=prompt, prompt_file=pf, work=work, result=result, task=t["id"], budget=cfg.get("maxBudgetUsd", 2.0), brief=os.path.join(home, t["brief"])) for x in cfg["command"]]
    try:
        p = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=cfg.get("timeoutSeconds", 1500))
    except (subprocess.TimeoutExpired, OSError) as e:
        return "error", f"executor {type(e).__name__}: {str(e)[:200]}"
    open(os.path.join(work, "executor.log"), "w", encoding="utf-8").write((p.stdout or "")[-4000:] + "\n--stderr--\n" + (p.stderr or "")[-2000:])
    if not os.path.exists(result):
        return "error", f"executor rc={p.returncode} wrote no result.json: {(p.stderr or p.stdout or '')[-200:]}"
    return "ok", result


def ingest_result(home: str, cid: str, t: dict, res: dict) -> dict:
    """Turn an agent result into ledger evidence, registered sources, acquired files, owner actions and FOLLOW-UP TASKS. A task never ends with just a file: it ends with
    evidence, a next task, or an exact blocker with the queries already tried."""
    if res.get("schema") != RESULT_SCHEMA or res.get("status") not in ("FINDINGS", "NO_USABLE_EVIDENCE", "BLOCKED"):
        raise ValueError("not a sector-agent-result-v1 document")
    bid, gid = t["brain"], t["gap"]
    folder = DEFAULT_FOLDERS[bid]
    fdir = os.path.join(home, folder)
    led = L.Ledger(os.path.join(fdir, "research", "gap-ledger.json"), bid)
    res = {**res, "taskId": t["id"], "gapId": gid}
    atomic_json(os.path.join(fdir, "research", "agent-results", t["id"] + ".json"), res)
    out = {"acquired": [], "registered": [], "ownerActions": 0, "followUps": []}
    ev = D.Evidence(home, folder, cid, _fetcher or D.Fetcher(home=home))
    for i, d in enumerate((res.get("datasets") or [])[:6]):
        url = d.get("directUrl")
        if not (url and d.get("verifiedAccess") and str(url).startswith("https://") and d.get("licence")):
            if d.get("url"):
                out["ownerActions"] += 0
            continue
        host = url.split("/")[2].split(":")[0].lower()
        if host not in D.allowed_hosts(home):
            try:                                                       # the explicit, controlled registration mechanism - same checks as the CLI
                D.register_source(home, "agent-" + re.sub(r"[^a-z0-9]+", "-", host), [host], str(d["licence"]), d.get("title") or host,
                                  f"found by agent task {t['id']} for gap {gid}: {str(d.get('relevance'))[:200]}")
                out["registered"].append(host)
            except ValueError as e:
                led.block(gid, "external", f"source {host} refused registration: {e}", f"owner review of {d.get('url')}", cid)
                continue
        if int(d.get("sizeBytes") or 0) > D.MAX_BYTES:
            led.block(gid, "external", f"dataset {d.get('title')} is {d.get('sizeBytes')} bytes (over the {D.MAX_BYTES} limit)", f"owner decision to download {url}", cid)
            continue
        rel = ev.fetch("agent-datasets", f"{t['id']}_{i}_{re.sub(r'[^A-Za-z0-9._-]+', '_', url.rsplit('/', 1)[-1])[:60] or 'data'}", url, None, purpose=f"agent task {t['id']}: {d.get('title')}")
        if rel:
            out["acquired"].append({"path": rel, "title": d.get("title"), "analysisPlan": d.get("analysisPlan")})
    ev.save()
    ev.register(_manifest_lock)
    for o in res.get("ownerActions") or []:
        rec = D.owner_action(home, folder, cid, o["id"], gid, o["publisher"], o["dataset"], o["access"], bool(o.get("verified")), [t["id"]], o.get("addresses") or gid)
        led.block(gid, "external", f"{o['dataset']} ({rec['path']})", f"{o['publisher']}: {o['access']}", cid)
        out["ownerActions"] += 1
    n_new = led.seen_evidence([D.sha256(os.path.join(home, a["path"])) for a in out["acquired"]])
    led.record(f"agent:{t['id']}", {"id": f"agent-{t['id']}", "run": "agent", "gaps": [gid]}, cid, "EVIDENCE" if (out["acquired"] or res.get("datasets")) else "NO_RESULT",
               "ACQUIRED" if out["acquired"] else ("EVIDENCE_LEAD" if res.get("datasets") else None), n_new, str(res.get("summary") or "")[:200])
    if res.get("datasets"):
        led.touch([gid], "EVIDENCE_LEAD", t["id"], set(), False)
    for n, a in enumerate(out["acquired"][:2]):                          # the next executable step: turn the dataset into a reviewed, re-runnable experiment
        bp = os.path.join(fdir, "research", "agent-tasks", f"{t['id']}-experiment-{n}.json")
        atomic_json(bp, {"schema": "sector-agent-research-task-v1", "brainId": bid, "gapId": gid, "kind": "implement-experiment", "dataset": a,
                         "instructions": ["pre-declare thresholds before examining the data", "implement an offline, deterministic experiment (experiments.py + discovery.json avenue) that the validator re-runs from the hashed file",
                                          "state the baseline honestly; match confounders; keep rejected hypotheses", "if the dataset cannot support a test, record the exact reason as a limitation"],
                         "analysisPlan": a.get("analysisPlan"), "from": t["id"]})
        ft = TQ.enqueue(home, bid, gid, "implement-experiment", f"implement experiment on {a.get('title')}", os.path.relpath(bp, home), cid, topic=a["path"], payload={"dataset": a["path"]})
        out["followUps"].append(ft["id"])
    if res["status"] in ("NO_USABLE_EVIDENCE", "BLOCKED") or not (res.get("datasets") or res.get("ownerActions")):
        led.block(gid, "external", f"agent research found no usable evidence ({len(res.get('queriesTried') or [])} queries recorded in {t['id']})",
                  str(res.get("nextSource") or "a source type not yet searched; see alreadyTried in the next task brief"), cid)
    led.save()
    return out


def loop(home: str, cid: str, executor: str = "claude-cli", max_tasks: int = 10, max_hours: float = 6.0, parallel: int = 3, timeout: int = 1800, adapters: dict | None = None,
         fetcher=None, exec_cfg: dict | None = None) -> dict:
    """Run -> execute queued research -> ingest -> reassess, until the queue is drained, the task/time budget ends, or only session-only work remains."""
    global _fetcher
    _fetcher = fetcher or _fetcher or D.Fetcher(home=home)
    rec = TQ.recover(home)
    fin = run(home, cid, parallel, timeout, adapters, _fetcher, retry_failed=True)
    cfg = {**DEFAULT_EXECUTOR, **(exec_cfg or discovery_cfg().get("executor") or {})}
    t_end, done, log = time.time() + max_hours * 3600, 0, []
    while executor != "none" and done < max_tasks and time.time() < t_end:
        t = TQ.next_task(home, ("agent-research",))
        if t is None:
            break
        if executor == "session":                                        # the coordinating Claude session executes it (subagent) and records it with `tasks done`
            log.append({"dispatch": t["id"], "mode": "session"})
            break
        TQ.claim(home, t["id"], executor)
        status, detail = execute_task(home, t, cfg)
        if status != "ok":
            TQ.fail(home, t["id"], detail or "executor error")
            log.append({"task": t["id"], "status": "failed", "detail": (detail or "")[:120]})
        else:
            try:
                ing = ingest_result(home, cid, t, json.load(open(detail, encoding="utf-8")))
                TQ.complete(home, t["id"], f"acquired {len(ing['acquired'])}, owner actions {ing['ownerActions']}, follow-ups {len(ing['followUps'])}", os.path.relpath(detail, home))
                log.append({"task": t["id"], "status": "done", **ing})
            except (ValueError, KeyError, OSError) as e:
                TQ.fail(home, t["id"], f"bad result: {type(e).__name__}: {str(e)[:150]}")
                log.append({"task": t["id"], "status": "failed", "detail": str(e)[:120]})
        done += 1
    write_report(Campaign(home, cid))
    return {"recoveredClaims": rec, "tracks": fin, "executed": done, "queue": TQ.counts(home), "log": log}


# ------------------------------------------------------------------------------------------------------------------------------- report
def write_report(c: Campaign) -> dict:
    st = c.load()
    rows = []
    for bid, t in st["tracks"].items():
        sg = t["stages"]
        val, cand, sc = (sg["validate"].get("result") or {}), (sg["candidate"].get("result") or {}), (sg["score"].get("result") or {})
        fol = sg["followup"].get("result") or {}
        out = t.get("outcome") or {}
        owners = []
        d = os.path.join(c.home, t["folder"], "research", "data-acquisition")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                try:
                    o = json.load(open(os.path.join(d, fn), encoding="utf-8"))
                    if o.get("campaign") == c.cid:
                        owners.append({"id": o["id"], "gap": o["gap"], "publisher": o["publisher"], "dataset": o["dataset"], "access": o["accessInstructions"],
                                       "verified": o["accessVerified"], "addresses": o["wouldAddress"]})
                except (ValueError, OSError):
                    continue
        rows.append({"brainId": bid, "folder": t["folder"], "stages": {s: sg[s]["status"] for s in STAGES},
                     "executionComplete": all(sg[s]["status"] == "DONE" for s in STAGES),
                     "outcome": out.get("outcome"), "outcomeReason": out.get("reason"), "improvementCampaignSuccessful": bool(out.get("improvementCampaignSuccessful")),
                     "avenuesRun": out.get("avenuesRun"), "evidenceTiersReached": out.get("evidenceTiersReached"), "stop": fol.get("stop"),
                     "attempts": sum(sg[s]["attempts"] for s in STAGES), "researchMode": (sg["research"].get("result") or {}).get("mode"),
                     "validated": val.get("validated", 0), "rejected": val.get("rejected", 0), "validatedByTier": val.get("validatedByTier") or {},
                     "scientificSupport": val.get("scientificSupport", 0), "improvements": val.get("improvements") or [],
                     "candidate": cand.get("releaseId") if cand.get("packaged") else None, "lifecycle": cand.get("lifecycle"),
                     "scientificChanges": cand.get("scientificChanges", 0), "rejectedHypotheses": cand.get("rejectedHypotheses", 0),
                     "candidateScore": None if (brain_spec(bid).get("scoreMeta") or {}).get("source") == "TYPED_NOT_COMPUTED" else sc.get("candidateScore"),   # SC-11: a typed constant is not a result
                     "typedConstantOmitted": (brain_spec(bid).get("scoreMeta") or {}).get("source") == "TYPED_NOT_COMPUTED", "scoreMeasure": sc.get("measure"), "scoreMeta": {**(brain_spec(bid).get("scoreMeta") or {}), "derivation": (brain_spec(bid).get("scoreMeta") or {}).get("source"),
                                   "baseline": (brain_spec(bid).get("scoreMeta") or {}).get("baseline", sc.get("authoritativeBaseline"))},
                     "scoreLabel": score_display(bid, sc), "capabilityChanges": sc.get("capabilityChanges") or [],
                     "authoritativeUnchanged": sc.get("authoritativeUnchanged"), "iterations": t.get("iteration", 1),
                     "evidenceFiles": sum(a.get("evidenceFiles", 0) for a in (t.get("acquired") or [])[-1:]),
                     "acquisitionFailures": sum(a.get("failureCount", 0) for a in t.get("acquired") or []),
                     "gaps": out.get("gaps") or {}, "nextEvidenceSources": out.get("nextEvidenceSources") or [], "ownerActions": owners,
                     "inputs": (sg["discover"].get("result") or {}).get("inputs"), "adapterBlocked": (sg["research"].get("result") or {}).get("adapterBlocked"),
                     "limitations": (sg["research"].get("result") or {}).get("limitations") or [], "history": t.get("history") or [],
                     "reproducible": val.get("discoveryReproducible"), "impact": sc.get("impact"), "agentTasks": (sg["research"].get("result") or {}).get("agentTasks") or [],
                     "integration": (sg["research"].get("result") or {}).get("integration") or [],
                     "errors": [f"{s}: {sg[s]['error']}" for s in STAGES if sg[s].get("error")]})
    n_ok = sum(r["improvementCampaignSuccessful"] for r in rows)
    open_gaps = {r["brainId"]: [g for g, s in r["gaps"].items() if s in L.ACTIONABLE] for r in rows}
    rep = {"schema": "sector-research-campaign-report-v2", "campaignId": c.cid, "generatedAt": now_iso(), "tracks": rows, "verification": st.get("verification"),
           "authoritativeScoresUnchanged": authoritative_hashes() == st["authoritativeBefore"],
           "complete": all(r["executionComplete"] for r in rows),            # EXECUTION complete: every stage ran. Not research complete.
           "executionComplete": all(r["executionComplete"] for r in rows), "improvementCampaignsSuccessful": n_ok, "brains": len(rows),
           "researchComplete": all(r["gaps"] and all(v == "RESOLVED_PENDING_APPROVAL" for v in r["gaps"].values()) for r in rows),   # blocked/exhausted is NOT complete
           "openGapsByBrain": open_gaps, "unresolvedGapsByBrain": {r["brainId"]: [g for g, v in r["gaps"].items() if v != "RESOLVED_PENDING_APPROVAL"] for r in rows}}
    atomic_json(os.path.join(c.dir, "report.json"), rep)
    lines = [f"# Research campaign {c.cid} — consolidated report", "",
             f"Generated {rep['generatedAt']}. **Execution complete: {rep['executionComplete']}** (every stage ran) — this is NOT research complete. "
             f"**Successful improvement campaigns: {n_ok}/{len(rows)}** (only a measured, independently validated capability improvement counts). "
             f"Research complete: **{rep['researchComplete']}**. Authoritative score artifacts unchanged: **{rep['authoritativeScoresUnchanged']}**. Nothing here is approved memory.", "",
             "Scores below are SCIENTIFIC CANDIDATE values from each Brain's own evaluator, non-authoritative. Engineering scores are a separate measure and are not touched.", "",
             "## Outcome per Brain", "", "| Brain | Outcome | Avenues | Best evidence tier | Validated by tier | Measured improvements | Package | Candidate score |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        tiers = r["evidenceTiersReached"] or []
        lines.append(f"| {r['brainId']} | **{r['outcome']}** — {r['outcomeReason']} | {r['avenuesRun']} | {tiers[-1] if tiers else '—'} | "
                     f"{', '.join(f'{k}:{v}' for k, v in r['validatedByTier'].items()) or '—'} | {', '.join(r['improvements']) or 'none'} | "
                     f"{r['lifecycle'] or '—'} ({r['scientificChanges']} change(s), {r['rejectedHypotheses']} rejected hypothesis) | "
                     f"{r['scoreLabel']} |")
    lines += ["", "## Measured capability changes (candidate only)", ""]
    any_cap = False
    for r in rows:
        for ch in r["capabilityChanges"]:
            any_cap = True
            lines.append(f"- **{r['brainId']} / {ch['finding']}** — {ch.get('capability')}: {ch.get('baseline')} -> {ch.get('candidate')} (delta {ch.get('delta')}, n={ch.get('n')}, {ch.get('kind')}; "
                         f"{'counts as an improvement' if ch.get('improved') else 'candidate change, NOT counted as an improvement (not independently validated)'}). Score impact: {(r.get('impact') or {}).get('score', 'see candidate package')}")
    if not any_cap:
        lines.append("- None. No Brain showed a measured capability change in this campaign.")
    lines += ["", "## Execution and stages", "", "| Brain | Stages | Evidence files | Validated / rejected | Errors |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['brainId']} | {' '.join(f'{s[:3]}:{v[0]}' for s, v in r['stages'].items())} | {r['evidenceFiles']} | {r['validated']} / {r['rejected']} | {'; '.join(r['errors'])[:200] or '—'} |")
    lines += ["", "## Gap ledger, blockers and what would move each Brain", ""]
    for r in rows:
        stat = {}
        for g, s in r["gaps"].items():
            stat.setdefault(s, []).append(g)
        lines.append(f"- **{r['brainId']}** ({r['outcome']}): " + "; ".join(f"{s}: {', '.join(gs)}" for s, gs in sorted(stat.items())))
        for n in r["nextEvidenceSources"]:
            lines.append(f"  - next evidence source: {n}")
        for o in r["ownerActions"]:
            lines.append(f"  - owner action `{o['id']}` ({'access verified' if o['verified'] else 'access NOT verified'}): {o['publisher']} — {o['dataset']} — would address {o['addresses']}")
        for lim in (r["inputs"] or {}).get("limitations") or []:
            lines.append(f"  - input limitation: {lim.get('limitation')}")
        if r["adapterBlocked"]:
            lines.append(f"  - evaluator blocked: {r['adapterBlocked']}")
        for it in r["integration"]:
            lines.append(f"  - integration proposal: {it['producer']} -> {it['consumer']}: {it['expectedBenefit']} ({it['status']})")
        for tsk in r["agentTasks"][:3]:
            lines.append(f"  - agent task: {tsk['task']}")
    open(os.path.join(c.dir, "REPORT.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return rep


# ------------------------------------------------------------------------------------------------------------------------------- brief
def brief(home: str, cid: str, bid: str) -> str:
    """The research brief one agent receives for one track: where to work, what exists, what is open, and the exact contract for findings."""
    c = Campaign(home, cid)
    st = c.load()
    t = st["tracks"][bid]
    folder = c.folder(st, bid)
    disc = (t["stages"]["discover"].get("result") or stage_discover(c, st, bid, None, 60))
    gaps_p = os.path.join(ENGINE, "brains", BRAIN_DIRS.get(bid, bid), "research", "GAPS.json")
    gaps = json.load(open(gaps_p, encoding="utf-8")) if os.path.exists(gaps_p) else {}
    open_gaps = [g for g in (gaps.get("gaps") or []) if str(g.get("status", "")).upper() not in ("CLOSED", "DONE", "RESOLVED")][:15]
    metrics = sorted(((t["stages"]["validate"].get("result") or {}).get("metricsAvailable") or []))
    lines = [f"# Research brief — {bid} — campaign {cid}", "",
             f"- Research folder (Cortex RS-01): `{folder}`; write ONLY there (sources/, datasets/, research/, analysis/) or in `analysis/tmp/{cid}/`.",
             f"- Existing evidence: {disc.get('manifestItems')} manifest items {disc.get('byRetention')}; prior tasks {disc.get('priorTasks')}; "
             f"closeouts {disc.get('closeouts')}; existing candidates {disc.get('existingCandidates')}. Reuse before downloading (RS-03, DEV-06).",
             f"- Depends on: {t['dependsOn'] or 'none'} (Intelligence consumes the specialists' results; it never invents their outputs).",
             f"- Open research gaps ({os.path.relpath(gaps_p, ENGINE)}): " + ("; ".join(f"{g.get('id')}: {str(g.get('title') or g.get('summary') or '')[:90]}" for g in open_gaps) or "none recorded"),
             "", "## Contract", "",
             f"Write `analysis/tmp/{cid}/findings.json` (schema `{FINDINGS_SCHEMA}`), then run "
             f"`python3 tools/research/campaign.py submit --campaign {cid} --brain {bid} --findings <file>`. Each finding:",
             "`{id, claim, kind: RULE|PARAMETER|EVIDENCE|DATASET, evidence: [{path (relative to the research home), sha256}], method, "
             "validation: {metric, op, threshold}}`.",
             "- Evidence must be saved in the research folder and registered in its manifest.json (sha256, source, retrieval date, license, retention).",
             "- `validation.metric` must be a metric the Brain's validator produces (below), or a new validator added to "
             "tools/research/adapters/run_adapter.py in the same campaign (reviewed code, deterministic, offline). Unverifiable findings are REJECTED.",
             f"- Metrics the {bid} validator produced in this campaign: {metrics or 'run the campaign once to list them'}.",
             "- Never: write to Firebase / Cloud, change an Engine runtime knowledge file, set an approval, change a score file, or use sealed holdouts.",
             "- Candidate knowledge is packaged by the harness with approval NOT_RECORDED; promotion is a reviewer/owner decision (M-3, G-1)."]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("init", "run", "submit", "status", "report", "brief", "register-source", "loop", "tasks"))
    ap.add_argument("sub", nargs="?", help="tasks: list | next | done | fail | block | recover")
    ap.add_argument("--executor", default="claude-cli", choices=("claude-cli", "session", "none"))
    ap.add_argument("--max-tasks", type=int, default=10)
    ap.add_argument("--max-hours", type=float, default=6.0)
    ap.add_argument("--id")
    ap.add_argument("--result")
    ap.add_argument("--error", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--next-source", default="")
    ap.add_argument("--campaign", default="-")
    ap.add_argument("--budget-hours", type=float, help="init: research window (wall clock) for this campaign")
    ap.add_argument("--max-avenues", type=int, help="init: maximum research avenues per Brain")
    ap.add_argument("--source-id")
    ap.add_argument("--host", action="append")
    ap.add_argument("--licence")
    ap.add_argument("--purpose")
    ap.add_argument("--rationale")
    ap.add_argument("--home")
    ap.add_argument("--brains", default="")
    ap.add_argument("--brain")
    ap.add_argument("--findings")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--adapters")
    ap.add_argument("--verification", action="store_true", help="init: a harness verification campaign (labelled fixture findings allowed)")
    ap.add_argument("--retry-failed", action="store_true", help="run: re-open FAILED stages (after a fix); finished stages are kept")
    ap.add_argument("--offline", action="store_true", help="run: no network acquisition (every connector request fails and is recorded)")
    a = ap.parse_args(argv)
    home = research_home(a.home)
    c = Campaign(home, a.campaign)
    if a.cmd == "tasks":
        if a.sub == "list" or not a.sub:
            print(json.dumps({"counts": TQ.counts(home), "tasks": [{k: t[k] for k in ("id", "brain", "gap", "kind", "status", "priority", "attempts", "title")} for t in TQ.load(home)["tasks"]]}, indent=1))
        elif a.sub == "next":
            t = TQ.next_task(home)
            if t:
                t = TQ.claim(home, t["id"], "session")
                print(json.dumps({**t, "briefContent": json.load(open(os.path.join(home, t["brief"]), encoding="utf-8")), "resultSchema": RESULT_SCHEMA}, indent=1))
        elif a.sub == "done":
            t = next(x for x in TQ.load(home)["tasks"] if x["id"] == a.id)
            if t["kind"] == "agent-research":
                ing = ingest_result(home, a.campaign, t, json.load(open(a.result, encoding="utf-8")))
                TQ.complete(home, a.id, f"acquired {len(ing['acquired'])}, owner actions {ing['ownerActions']}, follow-ups {len(ing['followUps'])}", a.result)
                print(json.dumps(ing, indent=1))
            else:
                TQ.complete(home, a.id, a.reason or "implemented", a.result)
        elif a.sub == "fail":
            TQ.fail(home, a.id, a.error)
        elif a.sub == "block":
            TQ.block(home, a.id, a.reason, a.next_source)
        elif a.sub == "recover":
            print(TQ.recover(home))
        return 0
    if a.cmd == "loop":
        print(json.dumps(loop(home, a.campaign, a.executor, a.max_tasks, a.max_hours, a.parallel, a.timeout, load_adapters(a.adapters), D.OfflineFetcher() if a.offline else None), indent=1, default=str))
        return 0
    if a.cmd == "register-source":
        print(json.dumps(D.register_source(home, a.source_id, a.host, a.licence, a.purpose, a.rationale), indent=1))
        return 0
    if a.cmd == "init":
        bo = {**({"wallSeconds": int(a.budget_hours * 3600)} if a.budget_hours else {}), **({"maxAvenues": a.max_avenues} if a.max_avenues else {})}
        st = init(home, a.campaign, [b for b in a.brains.split(",") if b] or None, verification=a.verification, budget_overrides=bo)
        print(f"initialized {a.campaign}: {len(st['tracks'])} tracks in {c.dir}")
    elif a.cmd == "run":
        fin = run(home, a.campaign, a.parallel, a.timeout, load_adapters(a.adapters), D.OfflineFetcher() if a.offline else None,
                  a.retry_failed)
        print(json.dumps(fin))
        print(open(os.path.join(c.dir, "REPORT.md"), encoding="utf-8").read())
    elif a.cmd == "submit":
        st = c.load()
        doc = json.load(open(a.findings, encoding="utf-8"))
        if doc.get("schema") != FINDINGS_SCHEMA or doc.get("brainId") != a.brain:
            print("refused: not a sector-research-findings-v1 document for this Brain", file=sys.stderr)
            return 2
        ws = c.workspace(st, a.brain)
        os.makedirs(ws, exist_ok=True)
        open(os.path.join(ws, OWNER_MARKER), "w").write(json.dumps({"campaignId": c.cid, "brainId": a.brain, "createdAt": now_iso()}))
        atomic_json(os.path.join(ws, "findings.json"), doc)
        for s in ("validate", "candidate", "score", "cleanup"):          # new findings re-open the downstream stages
            st["tracks"][a.brain]["stages"][s] = {"status": "PENDING", "attempts": 0}
        c.save(st)
        c.log(event="submit", brain=a.brain, findings=len(doc.get("findings") or []))
        print(f"submitted {len(doc.get('findings') or [])} finding(s) for {a.brain}")
    elif a.cmd == "brief":
        print(brief(home, a.campaign, a.brain))
    elif a.cmd == "status":
        st = c.load()
        for bid, t in st["tracks"].items():
            print(f"{bid:20s} " + " ".join(f"{s}:{v['status']}" for s, v in t["stages"].items()))
    else:
        print(json.dumps(write_report(c), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
