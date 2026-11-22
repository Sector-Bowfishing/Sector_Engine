"""Generation Brain (CALIBRATION, internal only). Dam releases and generation from official operator and agency data.

Generation owns what a dam is releasing or generating now (units on, discharge, spill, MW) and the operator's published schedule. It never owns
the pool level (Lake Brain), water clarity, fish behaviour or any combination of these (Sector Intelligence), and it never estimates a value
no source measured or published.

The shared platform package is vendored next to the runtime at deploy time; in the repo it is resolved from jobs/brain_platform
(this package lives at brains/generation/runtime/generation_brain)."""
import os as _os
import sys as _sys

_runtime = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if not _os.path.isdir(_os.path.join(_runtime, "sector_brain_platform")):
    _platform = _os.path.normpath(_os.path.join(_runtime, "..", "..", "..", "jobs", "brain_platform"))
    if _os.path.isdir(_platform) and _platform not in _sys.path:
        _sys.path.insert(0, _platform)
