"""Publisher V1 (SHADOW ONLY). A generic, science-free publishing framework for the Orchestrator platform.

Nothing here can write a live database: see sinks.py and docs/architecture/publisher/PUBLISHER_V1_SHADOW_ARCHITECTURE.md.
Importing this package does no I/O. It is not imported by sector_brain_platform/__init__.py, so no production job loads it.
"""
from .canonical import DEFAULT_VOLATILE, canonical_bytes, output_fingerprint, sha256_ref
from .handoff import ArtifactWriter, ShadowDispatcher, ShadowStack, local_shadow_stack, seal_artifact, seal_bundle
from .model import ENVELOPE_ID, LINEAGE_ID, LiveCapabilityRefused, PublisherMode, Result
from .paths import PathFamily
from .plan import UpdatePlan, build_update_plan
from .publisher import PublishResult, ShadowPublisher, UnknownProducer
from .refs import ArtifactRef
from .registry import Registry, SchemaSpec, default_registry, wind_specs
from .sinks import ShadowSink
from .storage import LocalDirObjectStore, MemoryObjectStore, PublishHistory, ScopedObjectStore, brain_view, publisher_view

__all__ = [n for n in dir() if not n.startswith("_")]
