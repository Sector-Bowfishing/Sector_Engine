# Autonomous research for bowfishing intelligence (V1, corrected 2026-10-23)

Sector Brains are **bowfishing intelligence systems**, not research projects. A campaign exists to make a Brain's bowfishing predictions more accurate, better covered, better validated or more honestly bounded. A run that downloads evidence, finishes its stages and improves nothing is **not** a successful improvement campaign, and the report says so.

This replaces the first discovery model (fixed two iterations, "no weak areas" decided by a connector's own sanity check). Cloud Brain execution stays PAUSED. Nothing here approves, publishes or writes to Firebase.

## Why the first overnight campaign failed

| Symptom (research-campaign-2026-10-23) | Cause in the code |
|---|---|
| Finished in 132 s, all eight tracks DONE | Every stage "succeeded" because the stages only downloaded and counted; nothing did scientific work |
| Fish with 3 open gaps reported "no weak areas" | `weak` came from the connector's own check (GBIF records < 200), never from the Brain's gaps |
| Datasets and literature leads marked VALIDATED | A finding was validated by a size or count threshold; nothing distinguished data from evidence from a rule |
| Eight candidate packages, zero improvements | Packaging ran whether or not anything changed, and the score adapters re-ran unchanged evaluators |
| Tracks stopped at one or two iterations | A fixed `maxIterations`; no budget, no ledger, no list of what had been tried |
| Certification and evidence paths not tied to tasks | Missing inputs were limitations in a report, never avenues to pursue |

## The model

**1. Evidence tiers are not interchangeable** (`ledger.TIERS`): ACQUIRED, QUALITY_CHECKED, EVIDENCE_LEAD, SCIENTIFIC_SUPPORT, CANDIDATE_CHANGE, INDEPENDENTLY_VALIDATED. A validated dataset is QUALITY_CHECKED; a literature hit is an EVIDENCE_LEAD; neither resolves a gap. A CANDIDATE_CHANGE must document the exact change (previous behaviour, proposed behaviour, evidence, validation method and results, practical effect, score impact, limitations). INDEPENDENTLY_VALIDATED means the candidate beats the baseline on data **not used to build it**, with tests pre-declared in `discovery.json`; the validator recomputes both numbers from the hashed evidence.

**2. A persistent gap ledger** per Brain (`<folder>/research/gap-ledger.json`): OPEN, INVESTIGATING, PARTIAL, BLOCKED_EXTERNAL, BLOCKED_APPROVAL, EXHAUSTED, RESOLVED_PENDING_APPROVAL, with every avenue tried (never repeated within a campaign). Only an independently validated, measured improvement that explicitly `resolves` a gap resolves it, and even then only as a *candidate* (authoritative scores change through approval). EXHAUSTED means every configured avenue was tried, never that no evidence exists; a new campaign reopens exhausted gaps and external blocks.

**3. Persistent investigation, bounded** (`discovery.json` `budget`): wall-clock window (default 8 h), avenues per Brain, bytes per Brain. After each avenue the coordinator records what it achieved, then runs the next untried avenue for a gap that is still actionable. Stall detection stops *acquisition* loops that bring no new evidence, no new validated finding and no changed result for three consecutive avenues. The campaign stops only as IMPROVED, STALLED, BLOCKED or BUDGET_REACHED, and never to use up the window.

**4. Outcome per Brain**: IMPROVED (a measured improvement; coverage gains count as coverage only), STALLED (no avenue left that could move a remaining gap, or no progress), BLOCKED (everything remaining needs external data or an approval), BUDGET_REACHED (actionable avenues remain). Every STALLED/BLOCKED outcome lists the exact reason and the next actionable evidence source. The report separates *execution complete* (every stage ran) from *research complete* (every gap resolved, almost never true).

**5. Avenues** (`discovery.json` `avenues`, tried in order): connectors (USGS, WQP, Open-Meteo, GBIF, Crossref), candidate-rule experiments, alternate sources, dataset search, owner-action records. A hypothesis **ladder** tries successively richer corrections and stops at the first measured improvement; each failure is kept as a rejected hypothesis with its numbers. A hypothesis added after seeing results must be validated on data not used to choose it.

**6. Honest packaging**: a package with no validated candidate change is labelled `EVIDENCE_ONLY` (administrative) and never counts as an improved Brain. A package with changes holds `candidate-changes.json`, `rejected-hypotheses.json` and `SCIENTIFIC_DIFFERENCE.md`. Approval is always NOT_RECORDED.

**7. Controlled source registration** (`tools/research/sources.json` for reviewed sources, `campaign.py register-source` for a research-home overlay): https, public DNS names only (no IP literals, no cloud or Firebase hosts), a licence, a purpose and a rationale are required. A host is never allowed because a document or response mentions it. Evidence already collected is reused across campaigns. A read-only `sources/` is never modified. What the system cannot fetch becomes an **owner-action record** (`<folder>/research/data-acquisition/`): publisher, access instructions with a verified flag, what was checked, which gap it would address.

**8. Scores**: candidate scores are labelled *scientific, non-authoritative*, with rubric, source (computed, recorded, or typed constant) and whether the score can move at all. A typed constant is never printed as a result. Engineering scores are a separate measure and are not touched. See `SCORING_CONTRACT_AUDIT_V1.md` for what each rubric really measures.

## Launching a substantial unattended campaign

```
# once per session: Python 3.12 with numpy; optional private inputs (otherwise those evaluators are recorded as blocked, not fatal)
export SECTOR_RESEARCH_HOME="$HOME/Desktop/Development/Sector Research"
python3 tools/research/campaign.py init   --campaign <id> --budget-hours 8 [--max-avenues 40] [--brains a,b]
python3 tools/research/campaign.py run    --campaign <id> --parallel 3 --timeout 1200
python3 tools/research/campaign.py run    --campaign <id> --retry-failed       # after a fix: only FAILED stages re-run
python3 tools/research/campaign.py status --campaign <id>
python3 tools/research/campaign.py report --campaign <id>
python3 tools/research/campaign.py register-source --source-id X --host data.example.org --licence "CC0" --purpose "..." --rationale "..."
```

- **Checkpoint**: `$SECTOR_RESEARCH_HOME/shared/campaigns/<id>/state.json` plus `events.jsonl`. After any interruption, run the same `run` command: finished stages and finished avenues are not repeated; the interrupted stage re-runs.
- **Read the result**: `REPORT.md` (outcome per Brain, measured capability changes, gap ledger, owner actions) and `report.json`. A run with `0/8` successful improvement campaigns is a valid, honest result.
- **Agent work**: literature and dataset leads produce *agent tasks* in the report. Read them, write findings with `campaign.py brief` / `submit` (they go through the same validator and tiers), then `run` again.
- **Never**: set an approval, write to Firebase or the Engine, open a sealed or protected holdout (Water Temp Stage 3C.3 values, Wind H2, Vegetation's one-shot holdout), or resume a Cloud scheduler.
