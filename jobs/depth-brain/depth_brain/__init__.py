"""Depth Brain (SHADOW / internal). Effective-depth shift first; contour zones where real evidence exists.

Depth owns environmental depth state. It never owns the lake level (Lake Brain), fish depth preference
(Biological), vegetation, clarity, or any combination of these (Sector Intelligence).

The shared platform package is vendored next to the job at deploy time; in the repo it is resolved from jobs/brain_platform."""
import os as _os
import sys as _sys

_job_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if not _os.path.isdir(_os.path.join(_job_root, "sector_brain_platform")):
    _sys.path.insert(0, _os.path.join(_job_root, "..", "brain_platform"))
