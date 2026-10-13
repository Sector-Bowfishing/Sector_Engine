"""DRY-RUN writer only. Vegetation has NO live RTDB writer in this phase: a live write needs Michael's explicit approval and a
reviewed change. Resolved from jobs/brain_platform (shared Brain Platform package)."""
from __future__ import annotations

import os as _os
import sys as _sys

_job_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if not _os.path.isdir(_os.path.join(_job_root, "sector_brain_platform")):
    _sys.path.insert(0, _os.path.join(_job_root, "..", "brain_platform"))

from sector_brain_platform import DryRunStore  # noqa: E402
from sector_brain_platform.keys import IllegalKey  # noqa: E402
from sector_brain_platform.ownership import OwnershipError  # noqa: E402

BRAIN_ID = "vegetation"
PLATFORM = {"implementation": "sector_brain_platform", "contract": "docs/brains/BRAIN_PLATFORM_CONTRACT.md v1.0", "conformant": True}


class WriteError(RuntimeError):
    pass


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
