# Weather retrospective validation (plan §5.4)

| Protocol | sha256 | Status |
|---|---|---|
| [`WX-RETRO-2026-11-23.5.protocol.json`](WX-RETRO-2026-11-23.5.protocol.json) | `2133b04e9c65d3a10a9a878a92ea206fa1c0745b0023613cf0a74f2ed6f66386` (`.sha256` sidecar) | **PRE-REGISTERED, current.** Runner: `tools/research/weather_retro_validation.py` with the shared run ledger `tools/research/protocol_run_ledger.py` (refuses every other protocol) |
| [`WX-RETRO-2026-11-23.4.protocol.json`](WX-RETRO-2026-11-23.4.protocol.json) | `55f850efe9ebd6dc972df59152667b99a5c49dc26cd87263b049c4ea3e9f314d` | **SUPERSEDED** by .5 to adopt the shared protocol run ledger (#251), before any data was fetched. Kept byte-for-byte; never run. |
| [`WX-RETRO-2026-11-23.3.protocol.json`](WX-RETRO-2026-11-23.3.protocol.json) | `492c1befe2707ce559c5999da7931548e69728c9fffadf16524813efdb5ec7c7` | **SUPERSEDED** by .4 after the third independent review of PR #246 (operator could still choose what is graded), before any data was fetched. Kept byte-for-byte; never run. |
| [`WX-RETRO-2026-11-23.2.protocol.json`](WX-RETRO-2026-11-23.2.protocol.json) | `01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c` | **SUPERSEDED** by .3 after the second independent review of PR #246, before any data was fetched. Kept byte-for-byte; never run. |
| [`WX-RETRO-2026-11-23.protocol.json`](WX-RETRO-2026-11-23.protocol.json) | `6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8` | **SUPERSEDED** by .2 after the first independent review of PR #246, before any data was fetched. Kept byte-for-byte; never run. |

All five were committed before any data was fetched. The .3, .4 and .5 protocol files were each committed alone, before their sidecar, this README and any runner change. [`MINI_REQUEST_DRAFT.md`](MINI_REQUEST_DRAFT.md) is the draft Mac mini request (not posted). Data never enters this repository.
