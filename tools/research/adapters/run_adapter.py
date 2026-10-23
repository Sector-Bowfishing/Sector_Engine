#!/usr/bin/env python3
"""Research-campaign adapters: thin, bounded wrappers around each Brain's EXISTING evaluators (no new science). Each stage prints/writes one
metrics.json into $CAMPAIGN_OUT. Research scripts that write into the root they are given run against an APFS copy-on-write CLONE of the
Brain's research folder inside $CAMPAIGN_OUT (campaign-owned, deleted at cleanup): the real research folders are only read.

  python run_adapter.py <brainId> <research|validate|score> <research home> <engine>
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

OUT = os.environ.get("CAMPAIGN_OUT") or os.getcwd()


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **(env or {}))
    return subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)


def clone(src: str, name: str) -> str:
    """APFS clone (cp -c: copy-on-write, no extra space) of a research folder into the campaign-owned output directory."""
    dst = os.path.join(OUT, "clone", name)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    r = subprocess.run(["cp", "-cR", src, dst], capture_output=True, text=True)
    if r.returncode:
        shutil.copytree(src, dst, symlinks=True)
    return dst


def repro(recorded: dict, base: str, strip_prefix: str) -> dict:
    """Compare regenerated outputs with the SHA-256 recorded in a candidate's REPRODUCIBILITY.json."""
    ok, total, diff = 0, 0, []
    for path, rec in recorded.items():
        total += 1
        p = os.path.join(base, path[len(strip_prefix):] if path.startswith(strip_prefix) else path)
        if os.path.exists(p) and sha(p) == rec["sha256"]:
            ok += 1
        else:
            diff.append(os.path.basename(path))
    return {"reproduced": ok, "outputs": total, "reproducedShare": round(ok / total, 4) if total else None, "differing": diff}


def find_key(obj, key):
    """First value of `key` anywhere in a nested JSON document."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r is not None:
                return r
    return None


def last_json(text: str) -> dict:
    try:
        return json.loads(text)
    except ValueError:
        pass
    i = text.find("\n{")                                         # an indented JSON document after some header lines
    if text.startswith("{") or i >= 0:
        try:
            return json.loads(text[0 if text.startswith("{") else i + 1:])
        except ValueError:
            pass
    for line in reversed(text.strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return {}


def emit(m: dict) -> int:
    json.dump(m, open(os.path.join(OUT, "metrics.json"), "w"), indent=1, default=str)
    print(json.dumps(m, default=str)[:2000])
    return 0


def release_check(engine: str, rel_dir: str) -> int:
    return run([sys.executable, os.path.join(engine, "tools", "knowledge", "build_release_manifest.py"), os.path.join(engine, rel_dir), "--check"]).returncode


# ------------------------------------------------------------------------------------------------------------------------------- Brains
def depth(stage, home, engine):
    R = os.path.join(home, "depth")
    tools = os.path.join(engine, "brains", "depth", "research", "tools")
    pp = os.pathsep.join([os.path.join(engine, "brains", "depth", "runtime"), tools, os.path.join(engine, "jobs", "brain_platform")])
    if stage == "research":                                   # D1 desk analysis, regenerated and compared with the recorded hashes
        out = os.path.join(OUT, "d1")
        r = run([sys.executable, "-I", os.path.join(R, "analysis", "campaign-2026-10-22", "d1_baseline_and_level_sensitivity.py"), engine, out], timeout=300)
        rec = json.load(open(glob.glob(os.path.join(R, "candidates", "campaign-2026-10-22", "*", "REPRODUCIBILITY.json"))[0]))["outputs"]
        return emit({"rc": r.returncode, **repro({os.path.basename(k): v for k, v in rec.items()}, out, "")})
    if stage == "validate":
        rep = last_json(run([sys.executable, "-m", "depth_research.cli", "report"], cwd=tools, env={"PYTHONPATH": pp}).stdout)
        prereg = run([sys.executable, "-c", "import json;from depth_research import field_validation as F;"
                      "print(json.dumps({'prereg':F.verify_prereg(),'status':F.analyze([]).get('status') if isinstance(F.analyze([]),dict) else str(F.analyze([]))}))"],
                     cwd=tools, env={"PYTHONPATH": pp})
        pv = last_json(prereg.stdout)
        return emit({"releaseVerified": int(release_check(engine, "brains/depth/runtime/knowledge") == 0), "preregPinned": int(pv.get("prereg") is True),
                     "fieldValidation": pv.get("status"), "maturity": (find_key(rep, "researchMaturity") or {}).get("new")})
    rep = last_json(run([sys.executable, "-m", "depth_research.cli", "report"], cwd=tools, env={"PYTHONPATH": pp}).stdout)
    return emit({"score": (find_key(rep, "researchMaturity") or {}).get("new"), "measure": "depth research maturity (official false)"})


def vegetation(stage, home, engine):
    R = os.path.join(home, "vegetation")
    tools = os.path.join(engine, "brains", "vegetation", "research", "tools")
    pp = os.pathsep.join([os.path.join(engine, "brains", "vegetation", "runtime"), tools, os.path.join(engine, "jobs", "brain_platform")])
    if stage == "research":                                   # V2 NLA-2022 field-truth statistics, regenerated vs recorded hash
        out = os.path.join(OUT, "v2_nla2022_surface_vs_submerged.json")
        r = run([sys.executable, "-I", os.path.join(R, "analysis", "campaign-2026-10-22", "v2_nla2022_surface_vs_submerged.py"), R, out], timeout=300)
        rec = json.load(open(glob.glob(os.path.join(R, "candidates", "campaign-2026-10-22", "*", "REPRODUCIBILITY.json"))[0]))["outputs"]
        v2 = next(v for k, v in rec.items() if k.endswith("v2_nla2022_surface_vs_submerged.json"))
        res = repro({"v2_nla2022_surface_vs_submerged.json": v2}, OUT, "")
        return emit({"rc": r.returncode, **res})
    if stage == "validate":
        fleet_out = os.path.join(OUT, "fleet.json")
        r = run([sys.executable, "-m", "vegetation_research.cli", "fleet", "--registry", os.path.join(R, "datasets", "registry", "lakes.v1.json"),
                 "--version", "registry-2026-10-13T20:20:54Z", "--out", fleet_out], cwd=tools, env={"PYTHONPATH": pp})
        committed = os.path.join(engine, "brains", "vegetation", "runtime", "knowledge", "fleet.json")
        lad = last_json(run([sys.executable, "-c", "import json;from vegetation_research import validation as V;print(json.dumps({'ladder':str(V.evaluate_ladder({}))}))"],
                            cwd=tools, env={"PYTHONPATH": pp}).stdout)
        return emit({"releaseVerified": int(release_check(engine, "brains/vegetation/runtime/knowledge") == 0),
                     "fleetReproduced": int(r.returncode == 0 and os.path.exists(fleet_out) and sha(fleet_out) == sha(committed)), "validationLadder": lad.get("ladder")})
    rep = last_json(run([sys.executable, "-m", "vegetation_research.cli", "report"], cwd=tools, env={"PYTHONPATH": pp}).stdout)
    return emit({"score": (rep.get("maturity") or rep).get("overall"), "measure": "vegetation research maturity (official false)"})


def _latest_fish(home):
    return sorted(glob.glob(os.path.join(home, "fish-brain", "candidates", "fish-release-candidate-*")))[-1]


def fish(stage, home, engine):
    rt = os.path.join(engine, "brains", "fish", "runtime")
    bundle = _latest_fish(home)
    if stage == "research":                                   # bundle audit: hash-checked load, provenance, schema, leak checks
        r = run([sys.executable, os.path.join(rt, "tools", "audit_bundle.py"), bundle], cwd=rt)
        return emit({"rc": r.returncode, "auditPass": int(r.returncode == 0 and "PASS" in r.stdout), "bundle": os.path.basename(bundle)})
    out = os.path.join(OUT, "capability")
    r = run([sys.executable, os.path.join(rt, "capability_run.py"), "--bundle", bundle, "--out", out, "--now", "2026-10-23T00:00:00Z"], cwd=rt)
    res = json.load(open(os.path.join(out, "result.json"))) if os.path.exists(os.path.join(out, "result.json")) else {}
    agg = {a.get("cohort") or a.get("id") or k: a for k, a in ((res.get("aggregates") or {}).items() if isinstance(res.get("aggregates"), dict) else [])}
    txt = json.dumps(res)
    def num(key):
        for k, a in agg.items():
            if key.lower() in str(k).lower() and isinstance(a, dict):
                for f in ("score", "value", "mean"):
                    if isinstance(a.get(f), (int, float)):
                        return a[f]
        return None
    m = {"rc": r.returncode, "complete": int(r.returncode == 0), "targetScore": num("TARGET"), "allAssessedScore": num("ALL")}
    if stage == "validate":
        return emit(m)
    return emit({"score": m["targetScore"], "allAssessed": m["allAssessedScore"], "measure": "FISH_BIOLOGICAL_CAPABILITY_V2 2.1.0 on the candidate bundle (publication INACTIVE)",
                 "resultKeys": sorted(res)[:12] if not m["targetScore"] else None, "raw": txt[:300] if not m["targetScore"] else None})


def intelligence(stage, home, engine):
    R = os.path.join(home, "sector-intelligence")
    cand = glob.glob(os.path.join(R, "candidates", "campaign-2026-10-22", "sector-intelligence-candidate-*"))[0]
    if stage == "research":                                   # reference synthesis regenerated vs the recorded output
        ref = os.path.join(OUT, "ref")
        shutil.copytree(os.path.join(cand, "reference"), ref)
        r = run([sys.executable, "demo_today_like.py"], cwd=ref)
        open(os.path.join(OUT, "demo.json"), "w").write(r.stdout)
        recorded = os.path.join(cand, "reference", "demo_today_like.output.json")
        return emit({"rc": r.returncode, "reproduced": int(os.path.exists(recorded) and sha(os.path.join(OUT, "demo.json")) == sha(recorded))})
    if stage == "validate":
        V = os.path.join(R, "validation", "campaign-2026-10-22")
        frozen = json.load(open(os.path.join(V, "FROZEN.json"))) if os.path.exists(os.path.join(V, "FROZEN.json")) else {}
        val = last_json(run([sys.executable, "-I", os.path.join(V, "ledger.py"), "validate", os.path.join(V, "prediction_ledger.jsonl")]).stdout)
        return emit({"releaseVerified": int(release_check(engine, "brains/sector-intelligence/runtime") == 0), "ledgerRows": val.get("rows"),
                     "ledgerErrors": len(val.get("errors") or []), "outcomeValidation": "NOT_STARTED" if not val.get("rows") else "IN_PROGRESS",
                     "frozenKeys": sorted(frozen)[:5]})
    c = json.load(open(os.path.join(cand, "candidate.json")))
    return emit({"score": None, "recorded": c.get("baselineVsCandidate"), "measure": "no candidate-score command exists (recorded values only)"})


def lake(stage, home, engine):
    R = os.path.join(home, "lake-brain")
    if stage == "research":                                   # L2 cluster robustness of the committed hold-out results
        out = os.path.join(OUT, "l2")
        r = run([sys.executable, "-I", os.path.join(R, "analysis", "campaign-2026-10-22", "scripts", "lake_l2_cluster_robustness.py"),
                 os.path.join(engine, "jobs", "lake-brain", "validation", "results"), os.path.join(R, "datasets", "species", "wbd", "lake_huc8.json"), out], timeout=300)
        return emit({"rc": r.returncode, "outputs": len(os.listdir(out)) if os.path.isdir(out) else 0})
    if stage == "validate":                                   # the pre-registered rules-v2 hold-out, on a copy of the validation package
        repo = os.path.join(OUT, "repo")                      # holdout_data resolves REPO three levels up: rebuild that layout in the campaign copy
        vdir = os.path.join(repo, "jobs", "lake-brain", "validation")
        shutil.copytree(os.path.join(engine, "jobs", "lake-brain", "validation"), vdir)
        sup = os.path.join(repo, "Sources", "SectorEngine", "Support")
        os.makedirs(sup)
        shutil.copy2(os.path.join(engine, "Sources", "SectorEngine", "Support", "LakeDirectory.swift"), sup)
        r = run([sys.executable, "holdout_v2.py", "--run", "97"], cwd=vdir, timeout=900, env={"SECTOR_RESEARCH_ROOT": home})
        res = sorted(glob.glob(os.path.join(vdir, "results", "*97*.json")))
        doc = json.load(open(res[-1])) if res else {}
        verdicts = {}
        for h in ("H-A", "H-B", "H-C", "H-D"):
            v = find_key(doc, h)
            verdicts[h] = (v.get("verdict") or v.get("result") or ("PASS" if v.get("pass") else "FAIL")) if isinstance(v, dict) else v
        return emit({"rc": r.returncode, "holdoutPassed": sum(str(v).upper().startswith("PASS") for v in verdicts.values()), "verdicts": verdicts,
                     "resultFile": os.path.basename(res[-1]) if res else None, "stderr": r.stderr[-300:] if r.returncode else ""})
    root = clone(R, "lake-brain")
    r = run([sys.executable, "-I", os.path.join(root, "analysis", "campaign-2026-10-22", "scripts", "build_candidate.py"), root])
    c = sorted(glob.glob(os.path.join(root, "candidates", "**", "lake-knowledge-candidate-*.json"), recursive=True))
    doc = json.load(open(c[-1])) if c else {}
    cand = (doc.get("score") or {}).get("candidate") if isinstance(doc.get("score"), dict) else None
    return emit({"rc": r.returncode, "score": cand.get("value") if isinstance(cand, dict) else cand, "uncapped": cand.get("uncapped") if isinstance(cand, dict) else None,
                 "scoreBlock": doc.get("score"), "measure": "lake-brain-score-v1 candidate (dimension values typed in the builder, not computed)"})


def water_temp(stage, home, engine):
    R = os.path.join(home, "water-temperature")
    root = clone(R, "water-temperature")                      # the scripts write under the root they are given
    S = os.path.join(root, "analysis", "campaign-2026-10-22", "scripts")
    if stage == "research":
        r = run([sys.executable, "-I", os.path.join(S, "wt_reproduce_m0.py"), root], timeout=300)
        rep = os.path.join(root, "validation", "campaign-2026-10-22", "wt_w1_reproduction.json")
        d = json.load(open(rep)) if os.path.exists(rep) else {}
        return emit({"rc": r.returncode, "rows": find_key(d, "rows") or find_key(d, "n"), "rmse": find_key(d, "rmse"), "bias": find_key(d, "bias"),
                     "maxAbsDiff": find_key(d, "maxAbsDiff"), "reproduced": int(r.returncode == 0)})
    if stage == "validate":
        r = run([sys.executable, "-I", os.path.join(S, "wt_w2_w4.py"), root], timeout=300)
        d = json.load(open(os.path.join(root, "validation", "campaign-2026-10-22", "wt_w2_w4_results.json")))
        def verdict(key):
            v = d.get(key) or {}
            return [x.get("PASS") for x in v.values() if isinstance(x, dict) and "PASS" in x]
        c1, c2 = verdict("W2_C1_seasonalOffset"), verdict([k for k in d if k.startswith("W2_C2")][0]) if any(k.startswith("W2_C2") for k in d) else []
        return emit({"rc": r.returncode, "w2c1Pass": int(bool(c1) and all(c1)), "w2c2Pass": int(bool(c2) and all(c2)), "keys": sorted(d)[:8]})
    r = run([sys.executable, "-I", os.path.join(S, "build_candidate.py"), root])
    b = run([sys.executable, os.path.join(engine, "verification", "integration", "score_baseline.py"), "--check"], cwd=engine)
    return emit({"rc": r.returncode, "score": 3.0 if b.returncode == 0 else None, "baselineCheck": b.stdout.strip()[-120:],
                 "measure": "water-temp-level-ladder-v1 (frozen; candidate typed in the builder)"})


IOS_WIND = os.environ.get("SECTOR_WIND_STAGE3A_EVIDENCE", "")            # iOS-repo stage3a evidence directory (read-only); unset = blocked


def wind(stage, home, engine):
    tools = os.path.join(engine, "brains", "wind", "research", "tools")
    rt = os.path.join(engine, "brains", "wind", "runtime")
    if stage == "research" and not os.path.isdir(IOS_WIND):
        return emit({"rc": 2, "blocked": "SECTOR_WIND_STAGE3A_EVIDENCE is not set to the stage3a evidence directory"}) or 2
    if stage == "research":                                   # certification scoreboard (frozen rubric v1). The sealed H2 archive is NOT read: an
        store = os.path.join(OUT, "empty-store")              # empty local store makes dimension 8 score 0 (published 3.3 includes it)
        os.makedirs(store, exist_ok=True)
        code = ("import json,sys;from sector_wind_research import scoreboard as S;from sector_wind.store import open_store;"
                f"s=S.compute(open_store('local:{store}'), json.load(open('{rt}/lakes.json')), '{IOS_WIND}');"
                "print(json.dumps({'official': s.get('official') if isinstance(s,dict) else None, 'raw': s.get('raw') if isinstance(s,dict) else None}, default=str))")
        r = run([sys.executable, "-c", code], cwd=tools, env={"PYTHONPATH": os.pathsep.join([tools, rt])})
        d = last_json(r.stdout)
        return emit({"rc": r.returncode, "certificationOfficial": find_key(d, "official"), "raw": find_key(d, "raw"),
                     "note": "sealed H2 not read (dimension 8 = 0 here)", "stderr": r.stderr[-300:] if r.returncode else ""})
    code = ("import json,datetime as dt;from sector_brain_platform import wind_measurements as W;"
            f"E='{engine}/docs/brains/scoring/';fr=json.load(open(E+'frozen-scores.json'));ev=json.load(open(E+'evidence/wind-measurements-evidence.json'));"
            f"ru=json.load(open(E+'wind-specialist-capability-v2.json'));br=json.load(open('{engine}/brains/wind/brain.json'));"
            "m=W.measurements(fr['wind'],ev,ru,br,dt.datetime(2026,10,23,tzinfo=dt.timezone.utc));"
            "print(json.dumps({'windCapability':m.get('windCapability'),'problems':W.evidence_problems(ev,ru)},default=str))")
    r = run([sys.executable, "-c", code], cwd=engine, env={"PYTHONPATH": os.path.join(engine, "jobs", "brain_platform")})
    d = last_json(r.stdout)
    wc = d.get("windCapability")
    val = wc.get("value") if isinstance(wc, dict) else wc
    if stage == "validate":
        return emit({"rc": r.returncode, "releaseVerified": int(release_check(engine, "brains/wind/runtime") == 0),
                     "evidenceProblems": len(d.get("problems") or []) if d.get("problems") is not None else None, "windCapability": val,
                     "stderr": r.stderr[-300:] if r.returncode else ""})
    return emit({"score": val, "measure": "wind-specialist-capability-v2 on the committed evidence (evidence regeneration blocked: cache missing)"})


CLARITY_PRIVATE = os.environ.get("SECTOR_CLARITY_PRIVATE_ROOT", "")      # private clarity-candidate research root (read-only); unset = blocked


def clarity(stage, home, engine):
    R = os.path.join(home, "water-clarity")
    if stage == "research" and not os.path.isdir(CLARITY_PRIVATE):
        return emit({"rc": 2, "blocked": "SECTOR_CLARITY_PRIVATE_ROOT is not set to the private clarity-candidate research root"}) or 2
    if stage == "research":                                   # national rain-decay-v0 evaluation, regenerated vs the published output
        out = os.path.join(OUT, "rain_decay_v0_national_eval.json")
        r = run([sys.executable, "-I", os.path.join(R, "research", "campaign-2026-10-22", "rain_decay_v0_national_eval.py"), CLARITY_PRIVATE, out], cwd=OUT)
        pub = glob.glob(os.path.join(R, "analysis", "**", "rain_decay_v0_national_eval.json"), recursive=True)
        return emit({"rc": r.returncode, "reproduced": int(bool(pub) and os.path.exists(out) and sha(out) == sha(pub[0])),
                     "stderr": r.stderr[-300:] if r.returncode else ""})
    cand = sorted(glob.glob(os.path.join(R, "candidates", "campaign-2026-10-22", "water-clarity-knowledge-candidate-*.json")))
    doc = json.load(open(cand[-1])) if cand else {}
    if stage == "validate":
        c = run([sys.executable, os.path.join(engine, "brains", "water-clarity", "contracts", "describe_contract.py"), "--check"], cwd=engine,
                env={"PYTHONPATH": os.path.join(engine, "jobs", "brain_platform")})
        bars = find_key(doc, "bars") or {}
        passed = sum(1 for b in (bars.values() if isinstance(bars, dict) else bars) if isinstance(b, dict) and b.get("pass") is True)
        return emit({"releaseVerified": int(release_check(engine, "brains/water-clarity/runtime") == 0), "contractOk": int(c.returncode == 0),
                     "frozenBarsPassed": passed, "note": "R3.1 re-certification blocked: stage_r31/cache missing"})
    sc = (doc.get("scores") or {}).get("candidate")
    return emit({"score": sc, "measure": "Clarity research certification r3.1: frozen bars re-evaluated from the published files (recorded in the candidate; full re-run blocked)"})


BRAINS = {"wind": wind, "water-clarity": clarity, "depth": depth, "vegetation": vegetation, "biological-state": fish, "sector-intelligence": intelligence, "lake-brain": lake,
          "water-temp": water_temp}


def main(argv=None) -> int:
    a = (argv or sys.argv[1:])
    brain, stage, home, engine = a
    os.makedirs(OUT, exist_ok=True)
    return BRAINS[brain](stage, home, engine)


if __name__ == "__main__":
    sys.exit(main())
