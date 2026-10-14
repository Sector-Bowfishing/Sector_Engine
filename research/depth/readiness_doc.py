"""Regenerate docs/brains/depth/DEPTH_PRODUCTION_READINESS_MATRIX.md from the manifest, the progress log and fixed status logic. Deterministic."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{ROOT}/jobs/depth-brain")
from depth_brain import maturity as M, score_v1_proposal as S

man = json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/candidates.json"))
fm = M.fleet_metrics(man)
log = [json.loads(l) for l in open(f"{ROOT}/docs/brains/depth/data/depth_progress_log.jsonl") if l.strip()]
ev = M.evaluate(man)
import datetime as dt
sc = S.score_depth_proposal(S.facts_from_manifest(man, live_states=5), dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc))
first, last = log[0]["fleet"], log[-1]["fleet"]
d = lambda k: f"{first.get(k)} -> {last.get(k)}"
rows = [
 ("Brain contract", "PARTIAL", "DEPTH_STATE_CONTRACT.md + 7 golden fixtures + platform ownership/vocabulary conformance; not ratified; slot `depth` reserved; no `jobs.py`/orchestrator/control-plane registration"),
 ("Reference pool", "PARTIAL", f"{fm['totalLakes']} lakes: directory pool usable for the shift on a subset; natural surfaces and low-confidence pools are refused by design; seasonal pools (Hartwell 660 summer / 656 winter) carried as Lake Brain guide context only"),
 ("Datum confidence", "PARTIAL", f"verified datum {fm['verifiedDatum']} (SAME_SOURCE + SAME_DATUM), inferred operator system {fm['inferredOperatorSystem']} (TVA), plausible lakes still blocked {fm['plausibleBlockedByDatum']}; conversions disabled; Duke (8) and 16 Reclamation lakes settled from public data (2026-10-14); NWPS, the narrowed Reclamation list and TVA naming wait on external confirmations"),
 ("Current level", "PARTIAL", f"consumed from Lake Brain `states/lake` (read-only); live for 5 reviewed pilots; {fm['shiftPossible'] - fm['pilotVerified']} defensible lakes await Lake Brain fleet bindings (unmerged); TVA states publish `datum: null`"),
 ("Effective depth (shift)", "PARTIAL", f"engine + tests + live GET-only dry run on all 5 pilots; defensible for {fm['shiftPossible']} of {fm['totalLakes']}; no field/event validation"),
 ("Authoritative contours", "PARTIAL", f"{fm['tierAB']} tier A/B lakes; {fm['licenceAllowedAB']} licensed for customer-derived numbers; ingest pipeline exists only as research scripts; no Southeast contours"),
 ("Shallow zones", "PARTIAL", f"reference shares for {fm['referenceZoneLakes']} lakes; effective zones eligible for {fm['effectiveZoneEligible']} (TWDB: 5 survey reference pools verified + preregistered validation passed; dry/under3 bounds only). Non-TWDB contour lakes FAILED the preregistered validation (4 graded; 5 reference pools verified but none validated) - their contour zones stay withheld; survey-date water levels are needed. NEW: exact depth shares from operator elevation-area ratings, storage-rating derivatives and Reclamation survey tables for {fm['ratingZoneLakes']} lakes ({fm['ratingZoneEligible']} shift-defensible), shares only, tolerance 0.13 (DEPTH_STAGE_AREA_RATING_RULES.md)"),
 ("Fleet coverage", "FAIL", f"shift-defensible {fm['shiftPossible']}/{fm['totalLakes']} ({fm['shiftPossibleShare']:.1%}); live 5; HIGH {fm['highConfidence']}, MEDIUM {fm['mediumConfidence']}, BLOCKED {fm['blocked']}"),
 ("Validation", "PARTIAL", "arithmetic tests; TWDB effective-zone validation preregistered (hash-frozen) and passed on 5 lakes; field validation preregistered, NOT run; `/validation/depth` = NOT_VALIDATED"),
 ("Field truth", "WAITING", "DEPTH_FIELD_VALIDATION_PLAN.md + hash-pinned prereg + analysis tooling ready; needs bowfishers/beta testers and sonar"),
 ("Confidence", "PASS", "sigma components in quadrature, labels, resolvable flag, reasons (components are research estimates, flagged)"),
 ("Provenance", "PASS", "tier, datum assessment + evidence confidence, sources, fingerprint, limitations, licence flags on every state"),
 ("Licensing", "PARTIAL", f"{fm['licenceAllowedAB']} of {fm['tierAB']} tier A/B lakes licensed; MN reclassification proposed (needs Michael sign-off); see DEPTH_LICENSING_UNLOCK_QUEUE.md"),
 ("Freshness", "PASS", "FINGERPRINT plan(); evidenceStale 6 h, refusal 48 h, future refused"),
 ("Cost", "PASS", "full-fleet dry run 2.7 s incl. reads, compute 0.02 s, 43 MB; no new feed (DEPTH_ORCHESTRATION_PLAN.md)"),
 ("Shadow publication", "PASS", "pilot-only (5 lakes) Depth state live in the Brain RTDB since 2026-10-14, read-back verified; /validation/depth NOT_VALIDATED; no score node; fingerprint plan() answers SKIP when inputs are unchanged"),
 ("Orchestration", "PARTIAL", "prepared but DISABLED (not approved for scheduling): run.py --plan/--write, gated in-process executor (DEPTH_ORCHESTRATION_ENABLED=1, set nowhere), brain_plan, image staging; no /jobs row, no schedule"),
 ("Ops visibility", "PARTIAL", "live /brains/depth carries the Engine-computed summary; control-plane SHADOW_BRAINS code verified against live data in dry run (no roll-up changes) but NOT redeployed; Ops catalog still marks Depth future (DEPTH_OPS_FOLLOWUP.md)"),
 ("Official score", "WAITING", f"none; `depth-brain-score-v2` is a PROPOSAL (DEPTH_OFFICIAL_SCORE_DECISION.md; v1 would show {sc['value']} capped today); needs Michael to ratify"),
 ("Intelligence contract", "PARTIAL", "documented + fixtures + reference consumer; Intelligence branch not changed"),
 ("Temp contract", "PARTIAL", "documented"), ("Clarity contract", "PARTIAL", "documented; no modeled depth permitted"), ("Vegetation contract", "PARTIAL", "documented"),
 ("Biological contract", "NOT_REQUIRED", "Intelligence matches preferences to Depth"),
 ("Rollback", "PASS", "nothing live; dry-run default; live write needs --yes-write-shadow; depth-owned paths deletable"),
]
md = [f"# Depth Production Readiness Matrix (generated {log[-1]['at'][:10]})", "",
      "Generated by `research/depth/readiness_doc.py` from the candidate manifest, the progress log and `depth_brain/maturity.py`. **Not production-ready, by design: Depth is a shadow/internal foundation.** "
      "Statuses: PASS / PARTIAL / FAIL / WAITING (needs an external input) / NOT_REQUIRED.", "",
      "## Production policy", "", "Sector standard: overall Brain score >= 8.0 **and** every critical dimension >= 7.5. Depth has **no official score**, so the policy cannot be evaluated canonically; "
      f"the research rubric (NOT a score) is {ev['overall']} with critical dimensions below 7.5: {', '.join(ev['criticalBelowThreshold'])}. "
      f"Proposed critical dimensions for an eventual `depth-brain-score-v1` (Michael ratifies): {', '.join(S.CRITICAL)}. The proposal evaluates today to {sc['value']} (uncapped {sc['uncapped']}); gates: "
      + ", ".join(f"{b['gate']} {b['cap']}" for b in sc['scoreBlockers'] if 'gate' in b) + ".", "",
      "## Matrix", "", "| # | Area | Status | Evidence / gap |", "|---|---|---|---|"]
for i, (a, s, e) in enumerate(rows, 1):
    md.append(f"| {i} | {a} | **{s}** | {e} |")
md += ["", "## What changed this phase", "", "| Metric | Start of phase | Now |", "|---|---|---|",
       f"| Research maturity (research rubric) | {log[0]['overall']} | {log[-1]['overall']} |", f"| Shift-defensible lakes | {d('shiftPossible')} | |",
       f"| Verified datum | {d('verifiedDatum')} | |", f"| High / Medium / Blocked | {first['highConfidence']}/{first['mediumConfidence']}/{first['blocked']} -> {last['highConfidence']}/{last['mediumConfidence']}/{last['blocked']} | |",
       f"| Effective-zone eligible | {d('effectiveZoneEligible')} | |", "",
       "Customer behavior: **unchanged**. No live Depth RTDB write, deployment, schedule, customer API, app or other-Brain change.", "",
       "## Gating items for any promotion", "",
       "1. Datum evidence for the remaining plausible-but-blocked lakes and operator confirmations (TVA datum name, Reclamation, NWS/Lake rebind, Duke series scale).",
       "2. Field validation of effective depth (preregistered).", "3. Lake Brain fleet bindings live so more than 5 Depth lakes publish.",
       "4. Southeast bathymetry requests answered; licence sign-offs (MN first).", "5. Michael decisions: ratify score v1 + critical dimensions, shadow-write approval, orchestration/control-plane registration, Ops catalog change."]
open(f"{ROOT}/docs/brains/depth/DEPTH_PRODUCTION_READINESS_MATRIX.md", "w").write("\n".join(md) + "\n")
print("ok", fm["shiftPossible"], sc["value"])
