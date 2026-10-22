"""Vegetation Brain OFFLINE research tooling: fleet observability manifest builder, agency dataset builders, shared-pass pilot/fleet harnesses,
pre-registered validation gates, the sealed holdout guard and the research maturity rubric. Never imported by the runtime
(brains/vegetation/runtime); never publishes. It may import runtime modules (vegetation_brain)."""
import os as _os
import sys as _sys

HERE = _os.path.dirname(_os.path.abspath(__file__))
RUNTIME = _os.path.abspath(_os.path.join(HERE, "..", "..", "..", "runtime"))          # brains/vegetation/runtime
KNOWLEDGE_DIR = _os.path.join(RUNTIME, "knowledge")                                  # the release the runtime verifies (written only by the builders)
RECORDS = _os.path.join(HERE, "records")                                             # small research records (rubric inputs, frozen preregistration)
if RUNTIME not in _sys.path:
    _sys.path.insert(0, RUNTIME)
