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

SCHEMA = "sector-research-campaign-v1"
FINDINGS_SCHEMA = "sector-research-findings-v1"
STAGES = ("discover", "acquire", "research", "validate", "candidate", "score", "followup", "cleanup")
ITERATION_STAGES = ("acquire", "research", "validate", "candidate", "score", "followup")   # re-opened by a follow-up iteration
BRAINS = ("biological-state", "wind", "water-clarity", "lake-brain", "water-temp", "sector-intelligence", "depth", "vegetation")
# Cortex research layout assignments (projects/sector/shared/data/research-layout.json); read from Cortex when available
DEFAULT_FOLDERS = {"biological-state": "fish-brain", "wind": "wind-brain", "water-clarity": "water-clarity", "lake-brain": "lake-brain",
                   "water-temp": "water-temperature", "depth": "depth", "vegetation": "vegetation", "sector-intelligence": "sector-intelligence"}
BRAIN_DIRS = {"biological-state": "fish", "lake-brain": "lake", "water-temp": "water-temperature"}
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
def init(home: str, cid: str, brains: list[str] | None = None, max_attempts: int = 2, verification: bool = False, discovery: bool = True) -> dict:
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
        tracks[bid] = {"folder": folder, "dependsOn": deps, "iteration": 1, "followupTargets": None, "acquired": [],
                       "stages": {s: {"status": "PENDING", "attempts": 0} for s in STAGES}}
    st = {"schema": SCHEMA, "campaignId": cid, "createdAt": now_iso(), "home": home, "maxAttempts": max_attempts, "tracks": tracks,
          "verification": bool(verification), "discovery": bool(discovery),          # True only for harness verification: allows the labelled FIXTURE findings
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
    out["gaps"] = {"source": g["source"], "reconstructed": g["reconstructed"], "open": [x.get("id") for x in g["gaps"]]}
    spec = (discovery_cfg().get("brains", {}).get(bid) or {})
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
    return out


def discovery_cfg() -> dict:
    p = os.path.join(HERE, "discovery.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"brains": {}}


def stage_acquire(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    t = st["tracks"][bid]
    spec = dict(discovery_cfg().get("brains", {}).get(bid) or {})
    kind = spec.get("kind")
    if not kind or kind == "upstream":
        return {"connectors": None, "note": "no external connector: this Brain consumes upstream campaign results"}
    if not st.get("discovery", True):
        return {"connectors": kind, "note": "discovery disabled for this campaign"}
    it = t.get("iteration", 1)
    used = set()                                                         # a follow-up iteration looks for OTHER sites
    for a in t.get("acquired") or []:
        for m in (a.get("matched") or {}).values():
            used |= {x["site"] for x in m.get("sites") or []} | ({m["site"]} if m.get("site") else set())
    spec["_usedSites"] = sorted(used)
    gaps = D.load_gaps(ENGINE, c.home, bid, t["folder"], BRAIN_DIRS.get(bid, bid))["gaps"]
    ev = D.Evidence(c.home, t["folder"], c.cid, _fetcher or D.Fetcher())
    try:
        res = D.acquire(kind, ev, c.home, spec, it, t.get("followupTargets"), gaps)
    finally:
        ev.save()
    registered = ev.register(_manifest_lock)
    res = {**res, "iteration": it, "connector": kind, "evidenceRoot": os.path.relpath(ev.root, c.home), "newFiles": ev.new, "evidenceFiles": len(ev.saved()), "registeredInManifest": registered,
           "failures": ev.failures[:20], "failureCount": len(ev.failures)}
    with _lock:                                                          # every iteration's acquisition is kept for the offline analysis
        s2 = c.load()
        acq = [a for a in s2["tracks"][bid].get("acquired") or [] if a.get("iteration") != it] + [res]
        s2["tracks"][bid]["acquired"] = acq
        st["tracks"][bid]["acquired"] = acq
        atomic_json(c.state_path, s2)
    return {k: v for k, v in res.items() if k not in ("matched", "lakes", "species", "gaps")}


def upstream_candidates(st: dict, bid: str) -> dict:
    """Only the Brain's declared dependencies: they finish before it starts, so the analysis is reproducible (no race with sibling tracks)."""
    deps = set(st["tracks"][bid]["dependsOn"])
    return {b: (t["stages"]["candidate"].get("result") or {}) for b, t in st["tracks"].items() if b in deps}


def run_analysis(c: Campaign, st: dict, bid: str) -> dict | None:
    spec = discovery_cfg().get("brains", {}).get(bid) or {}
    if not spec.get("kind"):
        return None
    return D.analyze(spec["kind"], c.home, spec, st["tracks"][bid].get("acquired") or [], upstream_candidates(st, bid))


def stage_research(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    ws = c.workspace(st, bid)
    os.makedirs(ws, exist_ok=True)
    open(os.path.join(ws, OWNER_MARKER), "w").write(json.dumps({"campaignId": c.cid, "brainId": bid, "createdAt": now_iso()}))
    submitted = os.path.join(ws, "findings.json")
    out = {"mode": "agent-findings" if os.path.exists(submitted) else "adapter"}
    run = ad.get("research")
    if run:
        rdir = os.path.join(ws, "research")
        force_rmtree(rdir)                                               # idempotent: a re-run (retry, follow-up iteration) starts clean
        os.makedirs(rdir, exist_ok=True)
        res = run_command(expand(run["cmd"], ctx(c, st, bid, rdir)), cwd=expand([run.get("cwd", "{engine}")], ctx(c, st, bid, rdir))[0], out_dir=rdir,
                          timeout=run.get("timeout", timeout))
        out["adapter"] = {**{k: res[k] for k in ("rc", "seconds")}, "stderrTail": res["stderrTail"][-500:]}
        out["metrics"] = metrics_from(res, rdir)
        atomic_json(os.path.join(ws, "research-metrics.json"), out["metrics"])
        if res["rc"] == 2 and out["metrics"].get("blocked"):           # a missing external input: recorded, the campaign continues
            out["adapterBlocked"] = out["metrics"]["blocked"]
        elif res["rc"] != 0:
            raise RuntimeError(f"research adapter failed rc={res['rc']}: {res['stderrTail'][-300:]}")
    an = run_analysis(c, c.load(), bid)
    if an is not None:
        atomic_json(os.path.join(ws, "discovery-metrics.json"), an["metrics"])
        prior = json.load(open(submitted, encoding="utf-8")) if os.path.exists(submitted) else {"schema": FINDINGS_SCHEMA, "brainId": bid, "findings": []}
        keep = [f for f in prior.get("findings") or [] if not f.get("auto")]     # agent-written findings are kept; auto ones are regenerated
        if an["findings"] or keep:
            atomic_json(submitted, {"schema": FINDINGS_SCHEMA, "brainId": bid, "campaignId": c.cid, "findings": keep + an["findings"]})
        out.update({"discoveryFindings": len(an["findings"]), "weak": an["weak"][:50], "limitations": an["limitations"]})
        if an["findings"]:
            out["mode"] = "discovery" + ("+agent-findings" if keep else "")
    if not os.path.exists(submitted) and ad.get("fixtureFindings") and st.get("verification"):
        # verification only: a controlled fixture standing in for agent-written findings (clearly labelled FIXTURE in the report)
        fx = json.load(open(os.path.join(HERE, ad["fixtureFindings"]), encoding="utf-8"))
        fx = json.loads(json.dumps(fx).replace("{campaign}", c.cid))
        atomic_json(submitted, fx)
        out["mode"] = out["mode"] + "+fixture-findings"
    out["findings"] = len((json.load(open(submitted, encoding="utf-8")) if os.path.exists(submitted) else {}).get("findings") or [])
    return out


def ctx(c: Campaign, st: dict, bid: str, out_dir: str) -> dict:
    return {"engine": ENGINE, "home": c.home, "folder": c.folder(st, bid), "out": out_dir, "campaign": c.cid, "python": sys.executable}


def validate_finding(f: dict, home: str, metrics: dict) -> tuple[str, str]:
    for k in ("id", "claim", "kind", "evidence", "validation"):
        if not f.get(k):
            return "REJECTED", f"schema: missing {k}"
    if f["kind"] not in ("RULE", "PARAMETER", "EVIDENCE", "DATASET"):
        return "REJECTED", f"schema: kind {f['kind']!r}"
    for ev in f["evidence"]:
        p = ev.get("path")
        if not p or not ev.get("sha256"):
            return "REJECTED", "evidence needs a research-home path and sha256 (provenance)"
        full = os.path.join(home, p)
        if not inside(full, home) or not os.path.isfile(full):
            return "REJECTED", f"evidence not found in the research home: {p}"
        if sha256(full) != ev["sha256"]:
            return "REJECTED", f"evidence sha256 mismatch: {p}"
    v = f["validation"]
    val = get_path(metrics, v.get("metric", ""))
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        return "REJECTED", f"validator metric {v.get('metric')!r} not produced by the Brain's validator"
    thr, op = v.get("threshold"), v.get("op", ">=")
    ok = {">=": val >= thr, "<=": val <= thr, ">": val > thr, "<": val < thr, "==": val == thr}.get(op) if isinstance(thr, (int, float)) else None
    if ok is None:
        return "REJECTED", f"validation threshold/op invalid ({op} {thr!r})"
    return ("VALIDATED", f"{v['metric']} = {val} {op} {thr}") if ok else ("REJECTED", f"{v['metric']} = {val} fails {op} {thr}")


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
    if run:
        vdir = os.path.join(ws, "validate")
        force_rmtree(vdir)
        os.makedirs(vdir, exist_ok=True)
        vres = run_command(expand(run["cmd"], ctx(c, st, bid, vdir)), cwd=expand([run.get("cwd", "{engine}")], ctx(c, st, bid, vdir))[0], out_dir=vdir,
                           timeout=run.get("timeout", timeout))
        metrics = metrics_from(vres, vdir)
        if vres["rc"] != 0:
            raise RuntimeError(f"validator failed rc={vres['rc']}: {vres['stderrTail'][-300:]}")
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
        verdict, why = validate_finding(f, c.home, metrics)
        results.append({"id": f.get("id"), "kind": f.get("kind"), "verdict": verdict, "reason": why, "fixture": bool(f.get("fixture"))})
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
    return {"metricsAvailable": sorted(flat), "findings": len(results), "validated": sum(r["verdict"] == "VALIDATED" for r in results),
            "rejected": sum(r["verdict"] == "REJECTED" for r in results), "results": results,
            "validator": {"rc": vres["rc"], "seconds": vres["seconds"]} if vres else None, "discoveryReproducible": reproducible}


def stage_candidate(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    ws = c.workspace(st, bid)
    vpath = os.path.join(ws, "validation.json")
    if not os.path.exists(vpath):
        return {"packaged": False, "reason": "no validation results"}
    val = json.load(open(vpath, encoding="utf-8"))
    ok_ids = {r["id"] for r in val["results"] if r["verdict"] == "VALIDATED"}
    if not ok_ids:
        return {"packaged": False, "reason": "no VALIDATED finding: no candidate is generated (rejections are recorded)"}
    findings = [f for f in json.load(open(os.path.join(ws, "findings.json"), encoding="utf-8"))["findings"] if f.get("id") in ok_ids]
    target = os.path.join(c.folder(st, bid), "candidates", c.cid)
    if inside(target, ENGINE):
        raise RuntimeError("refused: a campaign never writes into the Engine repository (approved memory is promoted by a gated review)")
    staging = target + ".staging"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    atomic_json(os.path.join(staging, "findings.json"), {"schema": FINDINGS_SCHEMA, "brainId": bid, "campaignId": c.cid, "findings": findings})
    atomic_json(os.path.join(staging, "validation.json"), val)
    files = K.describe_files(staging, ["findings.json", "validation.json"])
    rel_id = f"{bid}-research-candidate-{c.cid}"
    manifest = {"schemaVersion": K.SCHEMA_VERSION, "brainId": bid, "releaseId": rel_id, "store": "PACKAGED_IN_IMAGE", "owner": bid,
                "approval": {"status": "NOT_RECORDED", "record": None}, "files": files, "releaseDigest": K.release_digest(files),
                "lifecycle": "CANDIDATE", "note": "Research campaign candidate. NOT approved memory: promotion into a Brain runtime is a separate, "
                                                  "owner/reviewer-gated decision (M-3, G-1); never written by the campaign."}
    atomic_json(os.path.join(staging, K.MANIFEST), manifest)
    rel = K.load_release(staging, bid)                                  # the package verifies exactly like production memory would
    if rel["approvalStatus"] != "NOT_RECORDED":
        raise RuntimeError("refused: a campaign candidate is never approved")
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    return {"packaged": True, "releaseId": rel_id, "releaseDigest": rel["releaseDigest"], "approval": "NOT_RECORDED",
            "path": os.path.relpath(target, c.home), "findings": sorted(ok_ids)}


def stage_score(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    run = ad.get("score")
    before = authoritative_hashes()
    out = {"authoritativeUnchanged": None, "candidateScore": None, "class": "CANDIDATE (non-authoritative)"}
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
    after = authoritative_hashes()
    out["authoritativeUnchanged"] = before == after == st["authoritativeBefore"]
    if not out["authoritativeUnchanged"]:
        raise RuntimeError("an authoritative score artifact changed during the campaign")
    return out


def stage_followup(c: Campaign, st: dict, bid: str, ad: dict, timeout: int) -> dict:
    """Continue investigating weak areas: re-open the iteration stages with the weak targets, bounded by maxIterations."""
    t = st["tracks"][bid]
    res = t["stages"]["research"].get("result") or {}
    val = t["stages"]["validate"].get("result") or {}
    weak = list(res.get("weak") or [])
    rejected = [r["id"] for r in val.get("results") or [] if r["verdict"] == "REJECTED" and not r.get("fixture")]
    spec = discovery_cfg().get("brains", {}).get(bid) or {}
    it, max_it = t.get("iteration", 1), int(discovery_cfg().get("maxIterations", 1))
    hist = {"iteration": it, "weak": weak[:50], "rejected": rejected[:50], "validated": val.get("validated", 0)}
    last = (t.get("acquired") or [{}])[-1]
    unreachable = bool(last.get("failureCount")) and not last.get("newFiles") and not last.get("evidenceFiles")
    if unreachable:                                                      # the sources did not answer: an external-data limitation, not a weak area
        hist["unreachable"] = last.get("failureCount")
    if weak and not unreachable and spec.get("kind") not in (None, "upstream") and it < max_it and st.get("discovery", True):
        targets = None if weak == ["more-lakes"] else weak
        with _lock:
            s2 = c.load()
            tr = s2["tracks"][bid]
            tr["history"] = (tr.get("history") or []) + [hist]
            tr["iteration"], tr["followupTargets"] = it + 1, targets
            for s in ITERATION_STAGES:
                if s != "followup":
                    tr["stages"][s] = {"status": "PENDING", "attempts": 0}
            atomic_json(c.state_path, s2)
        c.log(event="followup", brain=bid, iteration=it + 1, targets=(targets or [])[:20])
        return {"continued": True, "nextIteration": it + 1, "targets": (targets or ["(next batch)"])[:50], **hist}
    with _lock:
        s2 = c.load()
        s2["tracks"][bid]["history"] = (s2["tracks"][bid].get("history") or []) + [hist]
        atomic_json(c.state_path, s2)
    return {"continued": False, "remainingWeak": weak[:50], "reason": "no weak areas" if not weak else
            ("sources unreachable: recorded as an external-data limitation" if unreachable else
             "iteration limit reached: remaining weak areas are reported as gaps" if it >= max_it else "no connector for a follow-up"), **hist}


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
        "Candidate knowledge": (f"{cand.get('releaseId')} (approval NOT_RECORDED; digest {cand.get('releaseDigest')}); validated {val.get('validated', 0)}, "
                                f"rejected {val.get('rejected', 0)}" if cand.get("packaged") else f"none ({cand.get('reason', 'not packaged')}); "
                                f"validated {val.get('validated', 0)}, rejected {val.get('rejected', 0)}"),
        "Backups verified": "no new ARCHIVAL data; existing backups untouched (campaign outputs are ACTIVE and reconstructable)",
        "Deleted": f"{len(deleted)} campaign-owned disposable file(s) under analysis/tmp/{c.cid}",
        "Worktrees": "none created by the campaign harness",
        "Blockers": (f"candidate score {sc.get('candidateScore')} ({sc.get('class')}); authoritative scores unchanged: {sc.get('authoritativeUnchanged')}; "
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
    _fetcher = fetcher or D.Fetcher()
    c = Campaign(home, cid)
    st = c.load()
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


# ------------------------------------------------------------------------------------------------------------------------------- report
def write_report(c: Campaign) -> dict:
    st = c.load()
    rows = []
    for bid, t in st["tracks"].items():
        sg = t["stages"]
        val, cand, sc = (sg["validate"].get("result") or {}), (sg["candidate"].get("result") or {}), (sg["score"].get("result") or {})
        rows.append({"brainId": bid, "folder": t["folder"], "stages": {s: sg[s]["status"] for s in STAGES},
                     "attempts": sum(sg[s]["attempts"] for s in STAGES), "researchMode": (sg["research"].get("result") or {}).get("mode"),
                     "validated": val.get("validated", 0), "rejected": val.get("rejected", 0),
                     "candidate": cand.get("releaseId") if cand.get("packaged") else None, "candidateScore": sc.get("candidateScore"),
                     "authoritativeUnchanged": sc.get("authoritativeUnchanged"), "iterations": t.get("iteration", 1),
                     "evidenceFiles": sum(a.get("evidenceFiles", 0) for a in (t.get("acquired") or [])[-1:]),
                     "acquisitionFailures": sum(a.get("failureCount", 0) for a in t.get("acquired") or []),
                     "gaps": (sg["discover"].get("result") or {}).get("gaps"), "inputs": (sg["discover"].get("result") or {}).get("inputs"),
                     "adapterBlocked": (sg["research"].get("result") or {}).get("adapterBlocked"),
                     "limitations": (sg["research"].get("result") or {}).get("limitations") or [],
                     "remainingWeak": (sg["followup"].get("result") or {}).get("remainingWeak"),
                     "reproducible": val.get("discoveryReproducible"), "impact": sc.get("impact"),
                     "errors": [f"{s}: {sg[s]['error']}" for s in STAGES if sg[s].get("error")]})
    rep = {"schema": "sector-research-campaign-report-v1", "campaignId": c.cid, "generatedAt": now_iso(), "tracks": rows, "verification": st.get("verification"),
           "authoritativeScoresUnchanged": authoritative_hashes() == st["authoritativeBefore"],
           "complete": all(all(v == "DONE" for v in r["stages"].values()) for r in rows)}
    atomic_json(os.path.join(c.dir, "report.json"), rep)
    lines = [f"# Research campaign {c.cid} — consolidated report", "", f"Generated {rep['generatedAt']}. Complete: **{rep['complete']}**. "
             f"Authoritative score artifacts unchanged: **{rep['authoritativeScoresUnchanged']}**. Nothing here is approved memory.", "",
             "| Brain | Stages | Research | Iter. | Evidence files | Validated / rejected | Candidate (approval NOT_RECORDED) | Candidate score | Errors |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['brainId']} | {' '.join(f'{s[:3]}:{v[0]}' for s, v in r['stages'].items())} | {r['researchMode']} | {r['iterations']} | "
                     f"{r['evidenceFiles']} | {r['validated']} / {r['rejected']} | "
                     f"{r['candidate'] or '—'} | {r['candidateScore'] if r['candidateScore'] is not None else '—'} | {'; '.join(r['errors'])[:200] or '—'} |")
    lines += ["", "## Gaps, inputs and limitations", ""]
    for r in rows:
        g, i = r.get("gaps") or {}, r.get("inputs") or {}
        lim = [x.get("limitation") for x in (i.get("limitations") or []) + r["limitations"]] + ([f"adapter blocked: {r['adapterBlocked']}"] if r["adapterBlocked"] else [])
        lines.append(f"- **{r['brainId']}**: gaps from `{g.get('source')}` (reconstructed: {g.get('reconstructed')}; open {len(g.get('open') or [])}); "
                     f"inputs reconstructed {len(i.get('reconstructed') or [])}; remaining weak {len(r['remainingWeak'] or [])}; "
                     f"offline re-validation reproducible: {r['reproducible']}; acquisition failures {r['acquisitionFailures']}"
                     + ("".join(f"\n  - limitation: {x}" for x in lim if x)))
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
    ap.add_argument("cmd", choices=("init", "run", "submit", "status", "report", "brief"))
    ap.add_argument("--campaign", required=True)
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
    if a.cmd == "init":
        st = init(home, a.campaign, [b for b in a.brains.split(",") if b] or None, verification=a.verification)
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
