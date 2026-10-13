# Depth Maturity Re-evaluation (research rubric; NOT a Brain score)

Two separate things, never mixed:

* **RESEARCH MATURITY** - the research rubric (`docs/depth-brain-research`: `DEPTH_BRAIN_RUBRIC_PROPOSAL.md`), evaluated mechanically by `python -m depth_brain report` from the candidate manifest plus judgment scores that must cite evidence (`jobs/depth-brain/depth_brain/data/maturity_inputs.json`). Every cycle is appended to `docs/brains/depth/data/depth_progress_log.jsonl`; a judgment dimension cannot rise without new `changeEvidence` (anti score-gaming, tested). The coverage dimension is **computed** from the share of lakes with a defensible shift (anchor table), never typed.
* **LIVE BRAIN MATURITY** - Depth has **no official score**. `/scores/depth` does not exist; the platform scorer is untouched; the registry node carries `scoreStatus: NOT_ESTABLISHED`. `depth-brain-score-v1` exists only as a PROPOSAL (`DEPTH_SCORE_V1_PROPOSAL.md`, unwired, tested).

The full history (previous -> new for each cycle: research maturity, shift-defensible lakes, verified datum, HIGH/MEDIUM/BLOCKED, effective-zone eligible) is the table in `DEPTH_CANDIDATE_FLEET.md` (generated) and `depth_progress_log.jsonl`. Production readiness by area is `DEPTH_PRODUCTION_READINESS_MATRIX.md` (generated).

Rules that govern movement of the number: no datum rule was loosened; no conversion enabled; no GLOBathy credit; no tier promotion without evidence; held evidence (RISE, NWPS, Duke) is listed with the external confirmation it needs and is NOT counted.
