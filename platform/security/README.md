# platform/security/ — target write-security model (SEC-1 / SEC-2), REPOSITORY SIDE ONLY

**Status: `REPO_READY`. `LIVE_SECURITY_VERIFIED` is NOT claimed.** Nothing in this directory is deployed; no RTDB rule, IAM binding or scheduler was changed.

| File | What it is |
|---|---|
| `publisher_security_plan.json` | machine-readable target model (generated from `sector_brain_platform/publisher_live/security_model.py`; a test keeps them equal) |
| `rtdb.rules.target.json` | the TARGET rules: `.write: false` for every client principal on every domain path; reads only for an Ops-reader claim. Admin/service identities bypass rules, so rules alone never prove write denial |
| `rtdb.rules.customer-copies.PROPOSED.json` | **PROPOSED, not applied** (Sector_Ops #53 spec §5). The target rules plus an explicit `customer` node for the five CUSTOMER-lane copies (`/customer/lakes/{k}/{level,clarity,waterTemp,generationBinding}`, `/customer/wind/outlookModel`): `.read: false` and `.write: false` for every client, which is exactly what `/customer/lakes/{k}/level` has today (it falls under the root deny). The Publisher writes and the customer Engine reads with service identities, which rules do not govern: their access is an IAM grant, approved separately and never described here. Applying this file is the owner's step; Cortex `rules-check` reports 0 findings on it |

Exit evidence F / `PRODUCTION_EXIT_GATE_V1` check **X16** needs, later and separately approved: tested denials (specialist, Ops, cross-domain) and a tested Publisher success under real rules AND real IAM. Concrete identities and bindings stay in the private handoff.
