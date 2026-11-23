"""Brain RTDB writers for the Moon and Night Light Brain: thin wrappers over the shared Sector Brain Platform (Brain Platform Contract v1.0), the
same shape as the Depth and Generation writers. RtdbWriter is constructed ONLY by `run.py --write`, which first requires an APPROVED knowledge
release AND MOON_WRITE_APPROVED=1 (operator intent); `patch()` is one atomic multi-path update with the platform's ownership check for `moon`.
DryRunWriter: the same checks over an in-memory tree (tests, --dry-run). Resolved from jobs/brain_platform (vendored beside run.py in the job image)."""
from __future__ import annotations

import moon_brain  # noqa: F401  (bootstraps the shared platform path)
from sector_brain_platform import BrainRtdb, BrainRtdbError, DryRunStore  # noqa: E402
from sector_brain_platform.keys import IllegalKey  # noqa: E402
from sector_brain_platform.ownership import OwnershipError  # noqa: E402

BRAIN_ID = "moon"
PLATFORM = {"implementation": "sector_brain_platform", "contract": "Brain Platform Contract v1.0", "conformant": True}


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
        if not updates:
            return
        try:
            self._db.update(updates)
        except (BrainRtdbError, OwnershipError, IllegalKey, ValueError) as e:
            raise WriteError(str(e)) from None

    def get(self, path: str, query: dict | None = None):
        try:
            return self._db.get(path, shallow=bool((query or {}).get("shallow")))
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

    def get(self, path: str, query: dict | None = None):
        return self._store.get(path, shallow=bool((query or {}).get("shallow")))

    def dump(self, out_path: str) -> None:
        self._store.dump(out_path)
