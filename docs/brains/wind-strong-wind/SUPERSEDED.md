# WSW-2026-11-23 and WSW-2026-11-23-R2 are superseded (never run)

`WSW-2026-11-23.protocol.json` (sha256 `b9a55721f7a6d2853462c1080bbec384c3a30e3429fce70b10c2872c77449346`) is kept unchanged as a record. It was never run: nothing was fetched, fitted or scored under it, and the runner refuses it.

Its past window (NBM inits 2025-11..2026-04) had already been read: W1 and W1b graded NBM night wind against the same airports for 2025-11-01..2026-09-30, including >= 15 mph POD/FAR (`docs/brains/wind/APP_WIND_SOURCE_REVIEW_V1.md`), and the golden decoder fixture decodes NBM init 2026-03-08 at the frozen stations.

`WSW-2026-11-23-R2.protocol.json` (sha256 `ba05492be82102fdba170b8dd5181ec557505622246e6a780c52a6ffc129633b`) is also kept byte-identical and was never run. Independent review found that its CAL+H1 observation range reached H2 days (2026-10-08), that rows it could not build or forecast were dropped silently instead of counted against the method, and that the fit's sha256 was not required to be posted before the past-window fetch.

The governing protocol is `WSW-2026-11-23-R3.protocol.json` (sidecar `.sha256`, sha256 `82f96596197d6af32e43b9e01ce152e922f3a0c0a42993641993a2da0fda68a2`), registered alone before any runner change and before any data was fetched. The runner pins it and refuses both superseded files.
