"""Depth Brain (SHADOW / internal). Effective-depth shift first; contour zones where real evidence exists.

Depth owns environmental depth state. It never owns the lake level (Lake Brain), fish depth preference (Biological), vegetation, clarity,
or any combination of these (Sector Intelligence).

The shared platform package is vendored next to the runtime at deploy time; in the repo it is resolved from jobs/brain_platform
(this package lives at brains/depth/runtime/depth_brain)."""
import os as _os
import sys as _sys

_runtime = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if not _os.path.isdir(_os.path.join(_runtime, "sector_brain_platform")):
    _platform = _os.path.normpath(_os.path.join(_runtime, "..", "..", "..", "jobs", "brain_platform"))
    if _os.path.isdir(_platform) and _platform not in _sys.path:
        _sys.path.insert(0, _platform)
