Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Session record: owner approvals, morning of 2026-10-31

These are the owner-approved items from the morning review. Private identity, IAM and bucket detail is on the Sector_Ops issues, not here.

| Item | Outcome |
|---|---|
| Merge #75 (RRFS/REFS collector fix), regenerate status | Merged (`e3694b42`) with CI green. Regenerating on main produced no diff, so the status was already current. |
| Restart the provider-bakeoff collector from merged main | Done. It now runs from the restored collector checkout at `e3694b42`, in a dedicated environment that includes the Wind research requirements. The previous process lacked numpy and eccodes, which the RRFS step needs. The first hourly cycle is recorded on Sector_Ops #27. |
| #18 D2: record the release approval | This PR. Scope is INTERNAL and CALIBRATION only. The release is not customer-eligible and nothing is promoted. |
| #18 D1: redeploy, then one real CENTRAL run and publish | Job redeployed from main. Baseline exported (unchanged since the 10-29 pilot). The cloud run and publish were **not** done: the Publisher identity cannot be used from this session without an IAM change that was not approved (Sector_Ops #18). A local dry run showed a 56-path plan limited to the pilot lakes and Water Clarity's own nodes. It also showed fleet summaries (`readinessCounts`, `staleLakeCount`) being recomputed from 2 lakes: a decision is required before any publish. |
| #19 S1: deploy brain-publisher in dry-run | Deployed in dry-run mode on the existing Publisher identity. No IAM change, no execution, no scheduler. |

Not done: any other Brain, any schedule resume, any further IAM or rules change, any customer promotion.

## Verification
- Every suite passed on this branch, and the certification run reports nothing failing.
- `build_engineering_status.py --check` passes.

## Afternoon: partial runs never rewrite Water Clarity fleet totals (Sector_Ops #18 D1 finding)

- Approved by the owner in this session: merge #76 (done, `cfd19fbc`; status regenerated on main with no diff), and fix the fleet summaries so a
  partial-lake run updates only its own lakes.
- Finding: a `--lakes` / `--limit` run recomputed `readinessCounts`, `staleLakeCount` and `breakdowns` from the lakes it could see, so the pilot plan
  would have replaced the 621-lake totals with 2-lake values.
- Fix: `run.py` marks a run partial when it covers fewer lakes than the directory, and then leaves `cb.FLEET_TOTALS` out of the registry and health
  records. The artifact builder treats an absent path as unchanged (never a delete), so the published totals stay as the last full run left them.
  A full run is unchanged. The run report records `partialRun` and `fleetTotalsOmitted`.
- Tests: three new cases in `brains/water-clarity/tests/test_clarity_central_mode.py` (full run keeps the totals; `--lakes` and `--limit` runs emit no
  SET or DELETE of a total and do not touch other lakes). They fail without the fix. All suites pass.
- Not done: no deploy, no cloud run, no publish. The job must be redeployed from main before the pilot run.
