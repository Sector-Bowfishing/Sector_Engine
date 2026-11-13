# Session record: Remote Config ETag fix in conditions_tiles_flag.py (Sector_Ops #51 / #53)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-09. Branch: `fix/remote-config-etag-gzip-2026-11-09`.

## Incident
`set-conditions-tiles.yml` (Actions run 42556167551, preset=off, 2026-11-09 03:24Z) refused with "REFUSED: the template read returned no ETag".
It refused safely: nothing was written. The cause is in the Firebase Remote Config REST documentation: the ETag "isn't properly returned in
cases where the request doesn't specify a compression type".

## Fix
- `_request` sends `Accept-Encoding: gzip` on every request.
- The body is gunzipped when the response says `Content-Encoding: gzip`, on both the success and the error path. The error path still prints
  only the HTTP code and Google's error status.
- Everything else is unchanged. A missing ETag still refuses before any write.

## Verification
- `tools/deploy`: 49 passed, 5 new: the header is sent, a gzip body plus ETag is parsed, a plain body still works, a gzip error body gives
  the status only, and a missing ETag refuses with no write.
- Not verifiable here: the live API. The main session re-runs `set-conditions-tiles.yml` with `preset=off` after the merge.
