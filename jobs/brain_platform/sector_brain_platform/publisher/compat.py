"""Legacy path migration table for Wind (Gate P, F-5/F-6/F-7): every path `wind-hourly` writes today that is NOT plainly Wind-authored domain truth.

Machine-readable on purpose: the equivalence evaluator (equivalence.py) uses it to classify live-only differences, and a test asserts every row has exactly one
classification, a named target owner and a retirement gate. Wind's ownership is NOT widened to cover any of these.

Classification (exactly one per row):
  PLATFORM_OWNED                    belongs to Platform / Lake Registry / Orchestrator; Wind must stop writing it
  DERIVED_COMPATIBILITY_PROJECTION  a copy/derivation of Wind canonical data kept only for a named reader; produced by the Publisher, never authored
  LEGACY_READER_DEPENDENCY          still read by an existing consumer; target owner is not Wind; carried temporarily
  WIND_DOMAIN_TRUTH                 genuinely Wind domain state; Wind authors it (kept deliberately small)
Mechanism (how it gets produced at cutover): WIND_AUTHORED | WIND_AUTHORED_TRANSITIONAL | PUBLISHER_DERIVED | ORCHESTRATOR_DERIVED | STOP_WRITING
Readers are listed from the certification trace (code search); "unverified" means no code reader was found for the exact field, so the retirement gate keeps the
usual 14-step proof. Nothing here retires or deletes anything.
"""
from __future__ import annotations

from dataclasses import dataclass

CLASSIFICATIONS = ("PLATFORM_OWNED", "DERIVED_COMPATIBILITY_PROJECTION", "LEGACY_READER_DEPENDENCY", "WIND_DOMAIN_TRUTH")
MECHANISMS = ("WIND_AUTHORED", "WIND_AUTHORED_TRANSITIONAL", "PUBLISHER_DERIVED", "ORCHESTRATOR_DERIVED", "STOP_WRITING")


@dataclass(frozen=True)
class LegacyRow:
    id: str
    paths: tuple                 # exact node patterns ({k} = one segment); a path matches the row if it equals the pattern or lies beneath it
    classification: str
    current_writer: str
    current_readers: str
    target_owner: str
    target_source: str
    compat_needed: bool          # must something still produce it for an existing reader after cutover?
    mechanism: str
    retirement_gate: str

    def __post_init__(self):
        assert self.classification in CLASSIFICATIONS and self.mechanism in MECHANISMS and self.retirement_gate and self.target_owner, self.id

    def specificity(self, path: str) -> int:
        """Number of leading segments of the best matching pattern (0 = no match). A path matches a pattern when it equals it or lies beneath it."""
        best, qs = 0, path.strip("/").split("/")
        for pat in self.paths:
            ps = pat.strip("/").split("/")
            if len(qs) >= len(ps) and all(a == b or (a.startswith("{") and a.endswith("}")) for a, b in zip(ps, qs)):
                best = max(best, len(ps))
        return best

    def matches(self, path: str) -> bool:
        return self.specificity(path) > 0


_W = "wind-hourly (and the WindBrain CLI)"
LEGACY_PATH_TABLE = (
    LegacyRow("lakefleet-lakeid", ("/lakeFleet/{k}/lakeId",), "PLATFORM_OWNED", _W + "; the field is open to every Brain today",
              "Ops fleet views; Sector Intelligence (lakeFleet/{k})", "Platform Lake Registry", "canonical lake directory (lake identity)", False, "STOP_WRITING",
              "Platform Lake Registry publisher writes lake identity; Wind writer count 0. Existing rows persist untouched, so Wind Phase 2 needs no compatibility"),
    LegacyRow("snapshot-lakeid", ("/snapshots/{k}/latest/lakeId",), "PLATFORM_OWNED", _W + "; written by every Brain", "Ops snapshot-row listener; Sector Intelligence",
              "Platform Lake Registry", "canonical lake directory", False, "STOP_WRITING", "same gate as lakefleet-lakeid; retires with the snapshot row"),
    LegacyRow("snapshot-wind", ("/snapshots/{k}/latest/wind",), "DERIVED_COMPATIBILITY_PROJECTION", _W, "Ops (whole-row listener: lake wind detail, Wind card, Brain page); Sector Intelligence (parked)",
              "Publisher (platform)", "/lakes/{k}/states/wind (rule wind-snapshot-copy-v1, same atomic plan)", True, "PUBLISHER_DERIVED",
              "WIND_SNAPSHOT_MIGRATION_PLAN S2-S7: readers moved, compatibility window, zero readers/writers proven, rollback export, Michael approval"),
    LegacyRow("snapshot-brainversions-wind", ("/snapshots/{k}/latest/brainVersions/wind",), "DERIVED_COMPATIBILITY_PROJECTION", _W,
              "snapshot-row consumers (field-level use unverified)", "Publisher (platform)", "/brains/wind/version (rule wind-snapshot-brainversion-v1)", True, "PUBLISHER_DERIVED",
              "retires with snapshot-wind"),
    LegacyRow("health-jobs-wind-hourly", ("/health/jobs/wind-hourly",), "PLATFORM_OWNED", _W, "Ops (health.jobs card)", "Orchestrator",
              "/jobs/wind-hourly + the execution ledger", True, "ORCHESTRATOR_DERIVED",
              "Ops reads /jobs only (or the Orchestrator writes this compatibility record); zero readers of /health/jobs/*; Wind writer count 0"),
    LegacyRow("health-brains-wind-process", tuple(f"/health/brains/wind/{f}" for f in ("lastRun", "lastSuccess", "durationMs", "errorCount", "latestError", "deployedVersion", "publishMode")),
              "LEGACY_READER_DEPENDENCY", _W, "Ops, Sector Intelligence, score publisher (health/brains)", "Orchestrator (execution / deployment state)",
              "execution ledger + deploy label", True, "ORCHESTRATOR_DERIVED", "readers move to the Orchestrator's execution state; Wind stops authoring these fields (they are process facts, not Wind domain state)"),
    LegacyRow("health-brains-wind-domain", ("/health/brains/wind/status", "/health/brains/wind/staleLakeCount"), "WIND_DOMAIN_TRUTH", _W, "Ops, Sector Intelligence",
              "Wind", "Wind's own evaluation of its evidence (stale lake count, health status)", False, "WIND_AUTHORED", "none: stays Wind-authored (child-level)"),
    LegacyRow("registry-updatedat", ("/brains/wind/updatedAt",), "LEGACY_READER_DEPENDENCY", _W, "Ops registry views", "Publisher (publication metadata)",
              "publication.evaluatedAt", True, "WIND_AUTHORED_TRANSITIONAL", "Ops reads the publication record; then drop from Wind's approved children"),
    LegacyRow("registry-lastsuccessfulrun", ("/brains/wind/lastSuccessfulRun",), "LEGACY_READER_DEPENDENCY", _W, "Orchestrator (dependency freshness), Ops, score publisher",
              "Orchestrator (execution state)", "execution ledger", True, "WIND_AUTHORED_TRANSITIONAL",
              "Orchestrator derives dependency freshness from its own execution records; then drop from Wind's approved children. Note: while this path is volatile-excluded, a SKIP leaves it stale"),
    LegacyRow("registry-lasterror", ("/brains/wind/lastError",), "LEGACY_READER_DEPENDENCY", _W, "Ops registry views", "Orchestrator (execution failure state)",
              "execution ledger", True, "WIND_AUTHORED_TRANSITIONAL",
              "Orchestrator surfaces failures; until then Wind may author it and clear it with an explicit DELETE (reason OPTIONAL_CHILD_CLEARED)"),
    LegacyRow("activity-retention", ("/activity",), "PLATFORM_OWNED", _W + " (best-effort pruning: a GET of the whole /activity node and deletes by age)", "Ops (last 50 events)",
              "Platform maintenance / Orchestrator retention", "a bounded-ring retention job over /activity", False, "STOP_WRITING",
              "a platform retention job exists; Wind's artifact never prunes. Activity is not edited by a Brain after the fact"),
    LegacyRow("activity-wind-events", ("/activity/{event}",), "WIND_DOMAIN_TRUTH", _W, "Ops", "Wind", "Wind's own readiness/version change facts (events containing -wind-)", False, "WIND_AUTHORED",
              "none: append-only domain events stay Wind-authored; score events are Platform's"),
)


def row_for(path: str, table=LEGACY_PATH_TABLE):
    """The most specific row covering `path` (None if none does)."""
    scored = [(r.specificity(path), r) for r in table]
    scored = [x for x in scored if x[0] > 0]
    return max(scored, key=lambda x: x[0])[1] if scored else None
