"""Where a rendered plan goes. In Publisher V1 there is exactly one sink: the ShadowSink, which keeps the plan in memory.

The capability boundary is structural: this package contains no database client, no HTTP, no subprocess, no credentials (a test lints the imports),
`PublisherMode` has no live member, and the Publisher refuses any sink that is not a ShadowSink or that exposes a write-shaped method.
"""
from __future__ import annotations

from .model import LiveCapabilityRefused
from .plan import UpdatePlan

WRITE_SHAPED = ("update", "patch", "put", "set", "delete", "write", "commit")


class ShadowSink:
    """Collects (plan, record) pairs. Never performs I/O. `live_mutations` is a constant, not a counter that could be bumped."""
    live = False
    live_mutations = 0

    def __init__(self):
        self.submitted: list[tuple[UpdatePlan, dict]] = []

    def submit(self, plan: UpdatePlan, record: dict) -> dict:
        self.submitted.append((plan, record))
        return {"live": False, "accepted": True, "publishId": record["publishId"], "paths": plan.path_count}


def require_shadow_sink(sink) -> ShadowSink:
    if not isinstance(sink, ShadowSink):
        raise LiveCapabilityRefused(f"the shadow Publisher accepts only a ShadowSink, got {type(sink).__name__}")
    leaked = [n for n in WRITE_SHAPED if callable(getattr(sink, n, None))]
    if leaked:
        raise LiveCapabilityRefused(f"sink exposes write-shaped methods {leaked}; refused")
    return sink
