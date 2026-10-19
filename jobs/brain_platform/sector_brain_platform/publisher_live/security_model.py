"""SEC-1 / SEC-2, repository side: the TARGET write model as data + a fake-enforceable guard.

REPO_READY means: the model, its target RTDB rules file and the denial/success tests exist and pass against FAKE clients.
LIVE_SECURITY_VERIFIED (exit evidence F, X16) is a different, later fact: tested denials under real rules AND real IAM. Nothing here changes either.
"""
from __future__ import annotations

from ..keys import BRAINS
from ..ownership import PLATFORM_ONLY, PLATFORM_WRITER, path_allowed

# Principals (identity CLASSES; never account names)
SPECIALIST, OPS, PUBLISHER, ORCHESTRATOR, SCORER = "specialist", "ops", "publisher", "orchestrator", "scorer"

#: Roots no Publisher write may ever touch, whatever a schema declares.
PUBLISHER_DENIED_ROOTS = frozenset(PLATFORM_ONLY | {"controlRequests"})
PUBLISHER_DENIED_HEALTH = frozenset({"jobs", "engine", "rtdb"})

#: SEC-2: paths that the CURRENT client-side ownership table lets more than one Brain write. They are PLATFORM/ORCHESTRATOR-owned in the target;
#: the Publisher never writes them; legacy writers keep today's behaviour until their own cutover (no runtime change here).
TARGET_PLATFORM_OWNED_COLLISIONS = (
    "lakeFleet/{k}/lakeId",
    "snapshots/{k}/latest/lakeId",
    "health/jobs/{id}",
)
#: SEC-2: Brain-authored process facts that belong to the Orchestrator/health plane in the target.
TARGET_ORCHESTRATOR_HEALTH_FIELDS = ("lastRun", "lastSuccess", "durationMs", "errorCount", "latestError", "deployedVersion", "publishMode")


class AccessDenied(PermissionError):
    pass


def collision_probe_paths() -> dict:
    return {"lakeFleet/{k}/lakeId": "lakeFleet/probe_lake/lakeId", "snapshots/{k}/latest/lakeId": "snapshots/probe_lake/latest/lakeId", "health/jobs/{id}": "health/jobs/probe-job"}


def current_multi_writer_paths() -> dict:
    """{pattern: [brainIds that today's ownership table lets write it]} for the probe set (SEC-2 inventory, computed from the code, not asserted)."""
    return {pat: sorted(b for b in BRAINS if path_allowed(b, p)) for pat, p in collision_probe_paths().items()}


def publisher_key_allowed(brain_id: str, key: str) -> bool:
    """Defence in depth for the live apply. The registry/validators already decided the artifact's paths; this independently refuses anything the Publisher
    must never write, and anything outside the producing Brain's own ownership."""
    s = [x for x in key.strip("/").split("/") if x]
    if not s or brain_id not in BRAINS:
        return False
    if s[0] in PUBLISHER_DENIED_ROOTS:
        return False
    if s[0] == "health" and len(s) > 1 and s[1] in PUBLISHER_DENIED_HEALTH:
        return False
    if s[0] == "brains" and len(s) > 2 and s[2] == "score":
        return False                                           # the scorer's field
    if (len(s) == 3 and s[0] == "lakeFleet" and s[2] == "lakeId") or (len(s) == 4 and s[0] == "snapshots" and s[2:] == ["latest", "lakeId"]):
        return False
    if s[0] == "health" and len(s) >= 4 and s[1] == "brains" and s[3] in TARGET_ORCHESTRATOR_HEALTH_FIELDS:
        return False
    return path_allowed(brain_id, key)


def assert_publisher_keys(brain_id: str, updates: dict) -> None:
    bad = sorted(k for k in updates if not publisher_key_allowed(brain_id, k))
    if bad:
        raise AccessDenied(f"publisher write for {brain_id!r} refused on {bad[:5]}")


def rtdb_write_allowed(principal: str, key: str, *, brain_id: str | None = None, phase: str = "TARGET") -> bool:
    """The principal capability matrix for the Brain database.
    TARGET: only the Publisher writes Brain data; specialists and Ops write nothing; the Orchestrator/scorer write only platform paths.
    CURRENT: documents today's reality (specialists write via the legacy ownership table) so the difference is visible, not hidden."""
    if principal == PUBLISHER:
        return brain_id is not None and publisher_key_allowed(brain_id, key)
    if principal == SPECIALIST:
        return phase == "CURRENT" and brain_id is not None and path_allowed(brain_id, key)
    if principal in (ORCHESTRATOR, SCORER):
        return path_allowed(PLATFORM_WRITER, key)
    return False                                               # ops and anything unknown


class PrincipalGuardedRtdb:
    """Wraps a (fake) RTDB client so a test can act AS a principal and observe denial/success. IAM-bypassing Admin tokens are exactly what this models the
    absence of: with a real database the same matrix must be enforced by rules AND IAM (LIVE_SECURITY_VERIFIED)."""

    def __init__(self, inner, principal: str, *, brain_id: str | None = None, phase: str = "TARGET"):
        self._inner, self.principal, self.brain_id, self.phase = inner, principal, brain_id, phase

    def get(self, path):
        return self._inner.get(path)

    def update(self, updates):
        bad = [k for k in updates if not rtdb_write_allowed(self.principal, k, brain_id=self.brain_id, phase=self.phase)]
        if bad:
            raise AccessDenied(f"{self.principal} may not write {bad[:5]}")
        return self._inner.update(updates)


#: Object-store (history bucket) capability model, enforced in code by storage.ScopedObjectStore and mirrored by IAM later.
STORE_CAPABILITIES = {
    "specialist": {"read": ("artifacts/{ownBrain}/",), "create_only": ("artifacts/{ownBrain}/",), "overwrite": (), "delete": ()},
    "publisher": {"read": ("artifacts/", "publishes/"), "create_only": ("publishes/",), "overwrite": ("publishes/_heads/", "publishes/{brain}/_locks/"), "delete": ()},
    "ops": {"read": (), "create_only": (), "overwrite": (), "delete": ()},
}


def security_plan() -> dict:
    """The machine-readable plan; `platform/security/publisher_security_plan.json` is generated from this and a test keeps them equal."""
    return {
        "standard": "publisher-security-plan-v1",
        "status": "REPO_READY",
        "liveSecurityVerified": False,
        "rtdb": {
            "targetPhase": {"publisher": "write Brain families (validated artifact only)", "specialist": "none", "ops": "none", "orchestrator": "platform paths only", "scorer": "/scores /control /engine/score only"},
            "publisherDeniedRoots": sorted(PUBLISHER_DENIED_ROOTS), "publisherDeniedHealth": sorted(PUBLISHER_DENIED_HEALTH),
            "platformOwnedCollisions": list(TARGET_PLATFORM_OWNED_COLLISIONS), "orchestratorHealthFields": list(TARGET_ORCHESTRATOR_HEALTH_FIELDS),
            "currentMultiWriterPaths": current_multi_writer_paths(),
        },
        "objectStore": {k: {kk: list(vv) for kk, vv in v.items()} for k, v in STORE_CAPABILITIES.items()},
        "iamPlan": ["distinct identity per class (specialist per Brain, publisher, orchestrator, scorer, ops-reader)",
                    "only the publisher identity holds database write on Brain paths",
                    "specialist identities hold create-only on their own artifact prefix and nothing on the database",
                    "publisher identity has no delete on the history bucket; bucket versioning on",
                    "ops identity read-only",
                    "no rule or IAM change is made by this repository change; each step needs separate approval and a tested denial"],
        "liveOnlyEvidence": ["X16 write denial under RTDB rules AND IAM (exit evidence F)"],
    }
