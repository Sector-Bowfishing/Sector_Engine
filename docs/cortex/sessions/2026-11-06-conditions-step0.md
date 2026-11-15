# Session record: conditions consolidation Step 0 (Sector_Ops #53)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine. Date: 2026-11-06. Branch: `feat/conditions-step0-golden-2026-11-06`.

## Scope
Owner approved #53 as the direction ("nothing breaks released apps"). This session covers the Step 0 groundwork that needs no deploy or IAM.

## Done
- **Phone contract** `contracts/phone/conditions-phone-contract-v1.json`: every key and type that iOS 4.1.0 build 28 (`v4.1.0-28`) decodes from `/conditions`. Build 28 decodes strictly: `.iso8601` dates with no fractional seconds, and a missing key or wrong type fails the whole response. Android 4.1.0 (46) parses leniently, so the iOS contract covers it. A `meanings` section freezes what `water`, `waterTempModel.currentF`, `weather.weatherCode` and the other contract fields mean.
- **Golden responses:** 17 production `/conditions` captures from 2026-11-06 in `verification/fixtures/phone-contract/2026-11-06/`, with free text redacted (this is a public repo). The unredacted bodies are in `Sector Research/shared/conditions-golden/2026-11-06/`. All 17 met the contract.
- **CI:** `PhoneContractTests.swift` checks that every golden meets the contract, and that an Engine `ConditionsResponse` round trip keeps every contract value. The validator has negative tests. `verification/test_phone_contract.py` runs the same check in the foundation job.
- **Moon spec** `contracts/moon/moon-v1.json`: the algorithm and 52 vectors generated from the Engine. `MoonSpecTests.swift` checks the Engine against them. iOS, Android and Web tests are still to be added in their repos.
- **Tool** `tools/conditions_golden/capture.py`: capture, redact, and check (`--live` probes production against the contract).

## Findings
- On 2026-11-06 a typical `/conditions` call took about 9.4 s, so the Engine's 9 s per-input deadlines are binding. `water` was absent at Wheeler, Pickwick, Lanier and Champlain. The per-tile watch needs this as its blank-rate baseline.
- Released Android uses the default okhttp User-Agent, which carries no app version, so request logs cannot separate Android versions until a build sends one. iOS build 28 sends its CFNetwork default, `Sector/28`.
- Build 28 shows `waterTempModel.currentF` (modeled) as H2O Temp and `water` (nearest gauge stage) as Level. Brain values for those tiles can reach build 28 only by changing what those fields mean, so they go in additive fields that need an app update.

## Verification
- `swift test`: 107 tests, 0 failures (macOS).
- pytest `verification tools/architecture tools/research`: 298 passed, 6 skipped.
- Cortex data-check, research-check and ops-check: no new findings. The UNREGISTERED_PATH and MAC_LOCAL_RUNTIME_PATH findings are in files this change does not touch.

## Not done / gated
- Nothing pushed, deployed, flagged or IAM-changed. Pushing this branch needs the owner's OK.
- The Linux CI leg (`swift:6.1-jammy`) was not run locally.
