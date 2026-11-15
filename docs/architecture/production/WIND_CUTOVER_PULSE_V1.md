# Wind onto Pulse (b6): cutover plan (PREP, Sector_Ops #51)

**Status: plan only.** Nothing in this document has been run against production, deployed, granted or enabled. Every gated step is Michael's. This plan follows the Owner approval "Wind and Water Temp cutover PREP" (Sector_Ops #51, 2026-11-15), and its pattern is the Lake move (Engine #168, `docs/architecture/production/LAKE_CUTOVER_B1_B7_PULSE_V1.md`).

Identity, bucket and IAM details stay in the private Sector_Ops #51 (step W-H1), not in this public repository.

## Where Wind stands

| Item | State |
|---|---|
| Lease-path entry | `brains/wind/runtime/artifact_entry.py`: the `wind-hourly` ingest into a LOCAL store, the unchanged publish into a `DryRunWriter`, and one sealed `wind-publication-v1` bundle. It never builds a database writer. |
| Staged fragment | `tools/ops/hybrid-stage/wind.json` (Pulse job `wind-central`, primary `pulse`, CENTRAL), readiness 3, blockers listed in it. `hybrid_stage.py check` → `wind: OK`. |
| Flip | Draft PR (do not merge): `hybrid_stage.py apply --brain wind … --write` puts Wind in the runner policy, the watchdog policy and `publication-cutover.json`. |
| Launch answer | **Approved (2026-11-14):** the deterministic NBM forecast, plus the night-time risky-night flag (pW15 ≥ 0.15 while NBM says under 15 mph), which only ever lowers confidence. The flag ships behind its own switch, OFF until a 30-day live shadow passes. |
| NBM points (#90) | Merged, OFF (`WIND_NBM_POINTS` unset). |
| Live lakes | 4: Guntersville, Wheeler, Wilson, Pickwick. Wind also writes `lakes/{k}/profiles/wind` for each nationally profiled lake (about 50). |
| Cadence | Hourly (stale after 1.5 h). Failover is off, so a sleeping Mac mini means stale wind. |

## W-H2: the bookkeeping advances only after the Publisher accepts (design proposal)

**The gap.** `publish()` keeps Wind's own previous state in `brain/wind/last_publish.json`: readiness per lake, `profileShas` (used to skip unchanged national profiles), `lastSuccessfulRun` and the last errors. In artifact mode that file advances when the artifact is **sealed**. If the central path later refuses the hand-off (quarantine, lease lost, Publisher refusal), the next run believes the refused write already happened. It then skips profiles that never reached the database, and fires (or skips) readiness events against a state that was never published. `artifact_entry.py` already restores the file on every path that hands nothing off. The gap is a hand-off that is stored and then refused.

**Proposed fix (recommended): derive the previous state from what is live, not from a local file.**
- In artifact mode, Wind reads its previous state from the database through the existing **read-only** identity, the same `brain-rtdb-read-token` Lake and Water Clarity already use (GET only):
  - the per-lake readiness Wind last published;
  - each national profile's `tableSha256`;
  - the registry's `lastSuccessfulRun`.
- Only a publish the Publisher accepted reaches the database, so "previous" means "accepted" by construction. Nothing has to be committed later.
- `last_publish.json` stays as a local cache and is never the source of truth in artifact mode.
- If the read fails, the run seals nothing (exit 2) rather than guess.
- **Cost:** a handful of GETs per run.
- **Tests:**
  - a refused hand-off followed by a new run re-sends the profiles and events;
  - an accepted hand-off doesn't re-send them;
  - a read failure stores nothing.

**Alternative (A): commit after acceptance.**
- The run writes `last_publish.pending/<artifactId>.json` and restores the committed file.
- At the start of the next run, Pulse promotes the pending file only if the Publisher's record for that `artifactId` is `PUBLISHED`.
- **Downside:** this needs a new read of the Publisher's records from the Mac mini (a new grant) and more moving parts.

**Decision for Michael: W-H2 = recommended (read the live state) or (A).** Building either is code that is OFF until the flip. It goes through an independent review and merges under the standing approvals.

## W-H3: the safety-check lake list (decision for Michael)

The watchdog trips `PUBLISH_OUTSIDE_LAKES` if a Wind publication writes `lakes|lakeFleet|snapshots/<k>/…` for a lake not on Wind's list. Wind writes profiles for every nationally profiled lake, not only the 4 live ones, so the staged list (4 lakes) would halt the first publish.

| Option | List | Effect |
|---|---|---|
| **(1) Recommended** | The 4 live lakes **plus every lake in the national manifest** (`fetch/national/MANIFEST.json`, status PASS/FLAGGED with a table, and in the canonical directory). That's about 50, generated at flip time from the Mac mini's Wind archive and pinned into `wind.json` in the flip PR, so the list is explicit and reviewed. | Nothing is lost. The watchdog still bounds Wind to a known, reviewed set. A new national lake later needs a one-line policy PR. |
| (2) | The 4 live lakes only, and Wind stops writing national profiles in artifact mode (a code change). | The smallest blast radius, but about 50 lakes stop getting Wind profile updates. |
| (3) | The watchdog exempts `lakes/<k>/profiles/wind`. | Changes the safety component itself. Not recommended. |

**Your beta lakes:** Kentucky Lake and Barkley are not Wind live lakes today. Adding live lakes (for example through the #90 points) is a separate, customer-visible step, not part of this move.

## The 7-day comparison (#49), on Pulse (recommended)

The cloud plan would restart the legacy `wind-hourly` writer to compare against, which conflicts with "no cloud runs until Pulse works". On Pulse there is no legacy write to compare with, so the comparison checks what can be checked. It's pre-registered here, before any run.

**Setup:**
- Pulse runs `wind-central` hourly in **shadow**: the artifact is sealed locally, and **hand-off and upload are off** (no lease needed, no Publisher, nothing reaches the database).
- It runs for 7 consecutive days.

**Pass criteria (all must hold):**
1. **Completeness:** at least 95% of hours seal an artifact within 20 minutes of the hour. Every miss is explained (a source outage counts as explained only if the artifact says so honestly).
2. **Determinism:** once a day, re-seal one hour from the same local store with `--skip-ingest`. The write-set hash must be identical.
3. **Skill:** at the 4 live lakes, the sealed analysis wind against METAR truth over the 7 days must be no worse than Wind's recorded validation evidence (`sector_wind/brain/validation_evidence.json`) by more than 10% MAE.
4. **Bounds:** every sealed write set touches only paths Wind owns, and only lakes on the W-H3 list.
5. **Mac mini:** no sleep gaps (`pmset -g log`), and the local archive's growth stays within the retention rule.

**If any criterion fails:** stop, explain it, fix it, and restart the 7 days.

**Decision for Michael: confirm the 7-day comparison runs on Pulse as above** (recommended), or in the cloud (restarts the legacy writer).

## Other prerequisites
- **Archive continuity (decision):** seed the mini's Wind archive once from `gs://sector-wind-candidate/wind/v1` (a one-off read: `brain/wind/last_publish.json`, `fetch/national/MANIFEST.json` and the fetch tables), or start fresh. **Recommended: seed it**, because the national manifest and fetch tables are needed for profiles.
- **Retention:** the local Wind archive grows hourly and is never pruned. **Proposal:**
  - keep the raw NBM/RTMA cutouts for 30 days;
  - keep derived state, fetch tables and manifests forever;
  - a Pulse maintenance job (Mac mini) does the pruning.
- **Power:** the Mac mini must never sleep: `sudo pmset -a sleep 0 disksleep 0` (Michael, Mac mini).
- **Knowledge release (M3):** Wind's `knowledge-release.json` approval is `NOT_RECORDED`. Michael records it, and the digests are re-recorded in a PR. The Publisher refuses an unapproved release.
- **Mac mini work, done by the Mac mini helper** under this approval:
  - the Pulse catalog entry `wind-central` (OFF, lease-only);
  - Wind's runtime reading the NBM v5.0 probability fields (OFF, Sector_Ops #27);
  - local dry runs;
  - the 7-day shadow, once Michael confirms it.

## Gated steps, in order (each Michael's; exact commands are on Sector_Ops #51)
1. **Decisions:** W-H2, W-H3, the 7-day comparison location, archive seeding.
2. **Code (standing approvals):** W-H2, the retention job, and the generated W-H3 list in `wind.json`.
3. **Mac mini:** catalog entry OFF, archive seed, power settings, the 7-day shadow, then the shadow report.
4. **M1 IAM W-H1** (five bindings, idempotent script, on #51).
5. **M3:** record Wind's knowledge release approval.
6. **M4:** merge the flip PR (draft today; it needs the real approvalRef and `--blockers-cleared` once 1–5 are done).
7. **M5:** deploy the Orchestrator and the Publisher from `main`, restating every live switch.
8. **M6:** the first-publish baseline acknowledgement (the Lake `lake-first-publish.sh` pattern).
9. **M7:** `execution_control.py enable … --brains water-clarity,lake-brain,wind`.
10. **M8/M9:** the watched first publish, then a 6-cycle watch.
11. **B6-equivalent:** retire the `wind-hourly` direct writer after 3 clean days, with `CUTOVER_COMPLETE`.

**Halt and roll back (any step):**
- `execution_control.py brain --brain wind --disable`;
- revert the flip PR and redeploy the Orchestrator and the Publisher;
- the Publisher's own rollback, for a bad publish;
- remove the W-H1 bindings using the same condition files.
