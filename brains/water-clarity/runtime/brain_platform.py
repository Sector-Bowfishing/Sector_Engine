"""Shim: this brain publishes through the shared Sector Brain Platform
(jobs/brain_platform/sector_brain_platform, contract docs/brains/BRAIN_PLATFORM_CONTRACT.md).

A deployed job carries a vendored copy of the package next to this file (deploy-job.sh --stage-only assembles it); in the repo the package is resolved from
jobs/brain_platform (this file lives at brains/water-clarity/runtime). Nothing brain-specific lives here.
"""
from __future__ import annotations

import os as _os
import sys as _sys

_here = _os.path.dirname(_os.path.abspath(__file__))
if not _os.path.isdir(_os.path.join(_here, "sector_brain_platform")):
    for _rel in (("..", "..", "..", "jobs", "brain_platform"),      # repo layout: brains/water-clarity/runtime
                 ("..", "brain_platform")):                         # legacy flat layout: jobs/<job>/ beside jobs/brain_platform
        _cand = _os.path.normpath(_os.path.join(_here, *_rel))
        if _os.path.isdir(_os.path.join(_cand, "sector_brain_platform")):
            _sys.path.insert(0, _cand)
            break

from sector_brain_platform import *                      # noqa: E402,F401,F403
from sector_brain_platform import rtdb as _rtdb          # noqa: E402

SCHEMA_VERSION = _rtdb.SCHEMA_VERSION
BRAIN_RTDB_URL = _rtdb.BRAIN_RTDB_URL
