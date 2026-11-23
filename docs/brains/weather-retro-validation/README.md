# Weather retrospective validation (plan §5.4)

| Protocol | sha256 | Status |
|---|---|---|
| [`WX-RETRO-2026-11-23.2.protocol.json`](WX-RETRO-2026-11-23.2.protocol.json) | see `.sha256` sidecar | **PRE-REGISTERED, current.** Runner: `tools/research/weather_retro_validation.py` |
| [`WX-RETRO-2026-11-23.protocol.json`](WX-RETRO-2026-11-23.protocol.json) | `6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8` | **SUPERSEDED** by v2 after the independent review of PR #246, before any data was fetched. Kept byte-for-byte (its hash still verifies); never run. |

Both were committed before any data was fetched. [`MINI_REQUEST_DRAFT.md`](MINI_REQUEST_DRAFT.md) is the draft Mac mini request (not posted). Data never enters this repository.
