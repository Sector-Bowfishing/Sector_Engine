"""Moon and Night Light Brain (CALIBRATION, not scheduled, no live writer): tonight's moon, sun, twilight and on-water darkness for every directory lake.

The shared platform package is vendored next to the runtime at deploy time; in the repo it is resolved from jobs/brain_platform (this package lives at
brains/moon/runtime/moon_brain)."""
import os as _os
import sys as _sys

_runtime = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if not _os.path.isdir(_os.path.join(_runtime, "sector_brain_platform")):
    _platform = _os.path.normpath(_os.path.join(_runtime, "..", "..", "..", "jobs", "brain_platform"))
    if _os.path.isdir(_platform) and _platform not in _sys.path:
        _sys.path.insert(0, _platform)
