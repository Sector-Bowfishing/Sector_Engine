"""Brain RTDB writers for the Weather Brain: thin wrappers over the shared Sector Brain Platform (jobs/brain_platform/sector_brain_platform;
Brain Platform Contract v1.0), the same shape as the Depth and Generation writers.

RtdbWriter: the contract's REST client (4 attempts, 1.5*2^n backoff, retry only on transport/5xx/429, app-database refusal, illegal-key walk,
ownership check for `weather`). `patch()` is ONE multi-path update at the root, applied atomically. It is constructed ONLY by `run.py --write`,
which first requires an APPROVED knowledge release AND WEATHER_WRITE_APPROVED=1 (operator intent). DryRunWriter: the same checks over an
in-memory tree (tests, `--dry-run`).

The platform package is vendored next to run.py by deploy/deploy-job.sh; in the repo it is resolved from jobs/brain_platform."""
from __future__ import annotations

import os as _os
import sys as _sys

_runtime = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if not _os.path.isdir(_os.path.join(_runtime, "sector_brain_platform")):
    _platform = _os.path.normpath(_os.path.join(_runtime, "..", "..", "..", "jobs", "brain_platform"))
    if _os.path.isdir(_platform) and _platform not in _sys.path:
        _sys.path.insert(0, _platform)

from sector_brain_platform import BrainRtdb, BrainRtdbError, DryRunStore  # noqa: E402
from sector_brain_platform.keys import IllegalKey  # noqa: E402
from sector_brain_platform.ownership import OwnershipError  # noqa: E402

BRAIN_ID = "weather"


class WriteError(RuntimeError):
    pass


class RtdbWriter:
    def __init__(self, base_url: str, timeout: float = 20.0):
        try:
            self._db = BrainRtdb(base_url, brain_id=BRAIN_ID, timeout_s=timeout)
        except ValueError as e:                       # app database or not the dedicated sector-brain instance
            raise WriteError(str(e)) from None
        self.base = self._db.url

    def patch(self, updates: dict) -> None:
        """Atomic multi-path update at the root. Keys are absolute paths without a leading slash."""
        if not updates:
            return
        try:
            self._db.update(updates)
        except (BrainRtdbError, OwnershipError, IllegalKey, ValueError) as e:
            raise WriteError(str(e)) from None

    def get(self, path: str):
        try:
            return self._db.get(path)
        except BrainRtdbError as e:
            raise WriteError(str(e)) from None


class DryRunWriter:
    def __init__(self, tree: dict | None = None):
        self._store = DryRunStore(tree if tree is not None else {}, brain_id=BRAIN_ID)

    @property
    def tree(self) -> dict:
        return self._store.tree

    @property
    def patches(self) -> list:
        return self._store.patches

    def patch(self, updates: dict) -> None:
        if not updates:
            return
        try:
            self._store.update(updates)
        except (OwnershipError, IllegalKey, ValueError) as e:
            raise WriteError(str(e)) from None

    def get(self, path: str):
        return self._store.get(path)

    def dump(self, out_path: str) -> None:
        self._store.dump(out_path)
