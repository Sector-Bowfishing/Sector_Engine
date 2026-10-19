# platform/security/ — target write-security model (SEC-1 / SEC-2), REPOSITORY SIDE ONLY

**Status: `REPO_READY`. `LIVE_SECURITY_VERIFIED` is NOT claimed.** Nothing in this directory is deployed; no RTDB rule, IAM binding or scheduler was changed.

| File | What it is |
|---|---|
| `publisher_security_plan.json` | machine-readable target model (generated from `sector_brain_platform/publisher_live/security_model.py`; a test keeps them equal) |
| `rtdb.rules.target.json` | the TARGET rules: `.write: false` for every client principal on every domain path; reads only for an Ops-reader claim. Admin/service identities bypass rules, so rules alone never prove write denial |

Exit evidence F / `PRODUCTION_EXIT_GATE_V1` check **X16** needs, later and separately approved: tested denials (specialist, Ops, cross-domain) and a tested Publisher success under real rules AND real IAM. Concrete identities and bindings stay in the private handoff.
