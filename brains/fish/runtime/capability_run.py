"""Fish Biological Capability V2: local, deterministic entry point (Sector Pulse / Mac mini / developer). Writes LOCAL files only.

  python3 capability_run.py --bundle /path/to/private/bundle --out out/                       # evaluate the release the bundle's latest.json names
  python3 capability_run.py --bundle B --out out/ --previous out_prev/result.json              # + change record with exact deltas
  python3 capability_run.py --bundle B --out out/ --overlay candidate.json                     # evaluate a CANDIDATE knowledge overlay (never adopted)
  python3 capability_run.py --bundle B --out out/ --reference-cases cases.json --expect-manifest-sha <sha>

Steps: verify + load the private knowledge release (hash-checked, fail closed) -> optional candidate overlay -> Fish evaluator executes the runtime
(evidence, no points) -> the SHARED platform scorer validates the evidence and computes species scores, aggregates and the research backlog.
Outputs: evidence.json (private: rule ids), result.json, report.md. Exit 0 = both aggregates COMPLETE, 3 = an aggregate INCOMPLETE, 2 = invalid input.
No network, no LLM, no credentials, no RTDB. Nothing is published: the result is a CANDIDATE until the rubric, cohorts and a publication path are approved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import biological_brain as bb      # noqa: E402
import brain_platform  # noqa: E402,F401  (puts the shared platform package on the path)
import capability_eval as ce      # noqa: E402
import rules as rl      # noqa: E402
import run      # noqa: E402
from sector_brain_platform import fish_capability as fc      # noqa: E402

REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_RUBRIC = os.path.join(REPO, "docs", "brains", "scoring", "fish-biological-capability-v2.json")
DEFAULT_COHORTS = os.path.join(REPO, "docs", "brains", "scoring", "fish-capability-cohorts-v2.json")
BRAIN_JSON = os.path.join(REPO, "brains", "fish", "brain.json")
OVERLAY_STATUS = "HYPOTHETICAL_CANDIDATE"


def apply_overlay(ruleset: rl.RuleSet, overlay: dict) -> tuple[rl.RuleSet, dict]:
    """A CANDIDATE knowledge change, evaluated without adopting it: added rules, reviewer season assertions, retirements. Validated fail-closed by RuleSet."""
    if overlay.get("status") != OVERLAY_STATUS:
        raise SystemExit(f"overlay status must be {OVERLAY_STATUS} (an overlay is never adopted knowledge)")
    oid = overlay.get("overlayId")
    if not oid:
        raise SystemExit("overlay needs overlayId")
    rules_ = list(ruleset.rules) + list(overlay.get("addRules") or [])
    retired = [{"ruleId": k[0], "ruleVersion": k[1], **v} for k, v in ruleset.retired.items()] + list(overlay.get("retire") or [])
    sa = dict(ruleset.season_assertions) | dict(overlay.get("seasonAssertions") or {})
    rs = rl.RuleSet(rules_, f"{ruleset.rules_version}+{oid}", source=f"{ruleset.source}+overlay", retired=retired, season_assertions=sa)
    meta = {"id": oid, "status": OVERLAY_STATUS, "description": overlay.get("description"), "sha256": hashlib.sha256(ce.canonical(overlay)).hexdigest()}
    return rs, meta


def code_version() -> str | None:
    try:
        sha = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "-C", HERE, "status", "--porcelain", "--", "."], capture_output=True, text=True, timeout=5).stdout.strip()
        return (sha + ("+dirty" if dirty else "")) if sha else None
    except Exception:
        return None


def evaluate_bundle(bundle_dir: str, *, rubric: dict, cohorts: dict, overlay: dict | None = None, reference_cases: list | None = None,
                    evaluated_at: str | None = None, expect_manifest_sha: str | None = None, include_code_version: bool = True) -> dict:
    b = bb.load_bundle(run.local_reader(bundle_dir))
    sha = b.pointer.get("manifestSha256")
    if expect_manifest_sha and sha != expect_manifest_sha:
        raise SystemExit(f"knowledge release {b.research_version} manifest {sha} != expected {expect_manifest_sha}: refusing to evaluate")
    ruleset = b.ruleset
    if ruleset is None:
        raise SystemExit("the knowledge release has no valid rule set")
    knowledge = {"researchVersion": b.research_version, "rulesVersion": ruleset.rules_version, "manifestSha256": sha, "overlay": None}
    if overlay:
        ruleset, meta = apply_overlay(ruleset, overlay)
        knowledge |= {"overlay": meta, "rulesVersion": ruleset.rules_version}
    cards = {k.split("/", 1)[1][:-5]: json.loads(v) for k, v in b.files.items() if k.startswith("movement/") and k.endswith(".json")}
    obs = b.files.get("validation/observations.jsonl", b"")
    n_obs = sum(1 for line in obs.decode().splitlines() if line.strip())
    brain = json.load(open(BRAIN_JSON)) if os.path.exists(BRAIN_JSON) else None
    return ce.evaluate(ruleset=ruleset, profiles=b.profiles, cohorts=cohorts, knowledge=knowledge, movement_cards=cards, discrepancies=b.discrepancies,
                       reference_cases=reference_cases, brain=brain, observations=n_obs, capability_status=(b.capability or {}).get("status"),
                       evaluated_at=evaluated_at, code_version=code_version() if include_code_version else None)


def _f(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


def report_md(res: dict) -> str:
    """Human-readable summary of a result (no rule ids, no evidence text)."""
    L = []
    br = res["brain"]
    L.append(f"# Fish Brain biological capability ({res['rubricId']} {res['rubricVersion']})\n")
    L.append(f"Evaluation `{res['evaluationId']}` · knowledge `{res['knowledgeVersion']}` · cohorts `{res['cohortsVersion']}` · authority **{res['authority']['status']}** · publication **{res['authority']['publication']}** · {res['outcomeKind']}\n")
    L.append("| Measure | Value | Status |\n|---|---:|---|")
    o = br["overallBiologicalCapability"]
    L.append(f"| Overall biological capability ({o['definition']}) | {_f(o['display'])} | {o['status']} |")
    for k, lab in (("targetSpeciesCapability", "TARGET species capability"), ("allAssessedSpeciesCapability", "All assessed species capability")):
        v = br.get(k) or {}
        L.append(f"| {lab} | {_f(v.get('display'))} | {v.get('status')} |")
    m = br.get("maturityScore") or {}
    L.append(f"| Maturity score ({m.get('rubric', 'biological-state-score-v1')}, separate) | {_f(m.get('value'))} | {m.get('basis', 'unchanged')} |")
    L.append(f"| Scientific confidence | - | {br['scientificConfidence']['status']} |")
    L.append(f"| Production readiness | - | {(br.get('productionReadiness') or {}).get('status')} |\n")
    for cid, a in res["aggregates"].items():
        L.append(f"**{cid}** ({a['eligibleSpecies']} eligible, {a['evaluated']} evaluated, {a['completenessPct']}% complete): value {_f(a.get('value'), 2)}; "
                 f"below 5.0: {a.get('below5')}; below 7.0: {a.get('below7')}; >=5.0: {a.get('pctAtLeast5')}%; >=7.0: {a.get('pctAtLeast7')}%; "
                 f"lowest {a.get('lowest', {}).get('speciesId')} {_f(a.get('lowestScore'), 2)}; highest {a.get('highest', {}).get('speciesId')} {_f((a.get('highest') or {}).get('score'), 2)}; "
                 f"bottom quartile {_f(a.get('bottomQuartileMean'), 2)}")
        if a.get("categoryAverages"):
            L.append("  category averages: " + ", ".join(f"{c} {_f(v, 2)}/{a['categoryMax'][c]}" for c, v in a["categoryAverages"].items()))
        L.append("")
    cats = None
    L.append("## Species\n")
    for sid, s in sorted(res["species"].items(), key=lambda kv: (fc.ROLE_TIER.get(kv[1].get("role"), 3), -(kv[1].get("capabilityScore") or -1), kv[0])):
        if s.get("capabilityScore") is None:
            L.append(f"- **{sid}** ({s.get('role')}): {s['evaluationStatus']} - {s.get('reason')}")
            continue
        cats = cats or list(s["categoryScores"])
        cs = " · ".join(f"{c} {_f(s['categoryScores'][c]['earned'], 2)}/{s['categoryScores'][c]['max']:g}" for c in cats)
        L.append(f"- **{sid}** ({s.get('role')}): **{_f(s['capabilityScore'], 2)}** (knowledge score species-v2 {s.get('knowledgeScoreSpeciesV2')}) - {cs}")
    L.append("\n## Research backlog (top 12)\n")
    L.append("| # | Species | Role | Score | Connectable from existing knowledge | Needs new research | Action |\n|---:|---|---|---:|---:|---:|---|")
    for r in res["researchBacklog"][:12]:
        L.append(f"| {r['rank']} | {r['speciesId']} | {r.get('role')} | {_f(r.get('currentScore'), 2)} | {_f(r.get('connectableFromExistingKnowledge'), 2)} | {_f(r.get('needsNewResearch'), 2)} | {r['recommendedNextAction']} |")
    if res.get("changeRecord"):
        cr = res["changeRecord"]
        L.append("\n## Change record\n")
        L.append(f"from `{cr['from']['evaluationId']}` ({cr['from']['knowledgeVersion']}) to `{cr['to']['evaluationId']}` ({cr['to']['knowledgeVersion']}); comparable: {cr['comparable']}\n")
        for r in cr.get("species") or []:
            L.append(f"- {r['speciesId']}: {r['from']} -> {r['to']} (delta {r['delta']}); categories {r.get('categoryDeltas')}")
        for k, v in (cr.get("aggregates") or {}).items():
            L.append(f"- aggregate {k}: {v['from']} -> {v['to']} (delta {v['delta']})")
    L.append("\n## Limitations\n")
    L += [f"- {x}" for x in res.get("limitations") or []]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", required=True, help="private knowledge release root (latest.json + releases/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rubric", default=DEFAULT_RUBRIC)
    ap.add_argument("--cohorts", default=DEFAULT_COHORTS)
    ap.add_argument("--reference-cases", help="JSON list of reference cases (PROPOSED cases are reported, never scored)")
    ap.add_argument("--overlay", help="HYPOTHETICAL_CANDIDATE knowledge overlay JSON")
    ap.add_argument("--previous", help="a previous result.json for the change record")
    ap.add_argument("--maturity", help="JSON score block of the existing maturity score, displayed verbatim")
    ap.add_argument("--expect-manifest-sha", help="refuse unless the knowledge release manifest has this sha256")
    ap.add_argument("--now", help="ISO time recorded as evaluatedAt/generatedAt (default: now)")
    a = ap.parse_args(argv)
    rubric, cohorts = fc.load_json(a.rubric), fc.load_json(a.cohorts)
    errs = fc.validate_rubric(rubric)
    if errs:
        print(json.dumps({"error": "invalid rubric", "problems": errs}, indent=1))
        return 2
    now = a.now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases = json.load(open(a.reference_cases)) if a.reference_cases else None
    overlay = json.load(open(a.overlay)) if a.overlay else None
    ev = evaluate_bundle(a.bundle, rubric=rubric, cohorts=cohorts, overlay=overlay, reference_cases=cases, evaluated_at=now, expect_manifest_sha=a.expect_manifest_sha)
    prev = json.load(open(a.previous)) if a.previous else None
    mat = json.load(open(a.maturity)) if a.maturity else None
    try:
        res = fc.build_result(ev, rubric, cohorts, generated_at=now, previous=prev, maturity=mat)
    except ValueError as ex:
        print(json.dumps({"error": str(ex)}, indent=1))
        return 2
    os.makedirs(a.out, exist_ok=True)
    for name, obj in (("evidence.json", ev), ("result.json", res)):
        with open(os.path.join(a.out, name), "w") as fh:
            json.dump(obj, fh, indent=1, ensure_ascii=False, sort_keys=True)
    with open(os.path.join(a.out, "report.md"), "w") as fh:
        fh.write(report_md(res))
    summary = {"evaluationId": res["evaluationId"], "knowledgeVersion": res["knowledgeVersion"], "authority": res["authority"]["status"],
               "aggregates": {k: {"value": v["value"], "status": v["status"], "evaluated": v["evaluated"], "eligible": v["eligibleSpecies"]} for k, v in res["aggregates"].items()},
               "out": a.out}
    print(json.dumps(summary, indent=1))
    return 0 if all(v["status"] == "COMPLETE" for v in res["aggregates"].values()) else 3


if __name__ == "__main__":
    raise SystemExit(main())
