"""Publisher LIVE V1 — the production-capable publication door (REPOSITORY IMPLEMENTATION ONLY).

A SIBLING of the SHADOW package `sector_brain_platform.publisher`: that package keeps its structural no-live-I/O guarantee (import lint, no live mode); this package
reuses its validators/planner/registry and adds the live apply path. Nothing here is enabled: a `LivePublisher` refuses every Brain that has no explicit
`LiveAuthorization`, the production RTDB adapter refuses to construct unless armed, and the platform package does not import this one.
Tests use fake RTDB / object-store clients only. Importing this package performs no I/O.
"""
from .authorization import BrainAuthorization, LiveAuthorization
from .model import LiveResult
from .publisher import LivePublisher, LivePublishResult

__all__ = ["BrainAuthorization", "LiveAuthorization", "LivePublisher", "LivePublishResult", "LiveResult"]
