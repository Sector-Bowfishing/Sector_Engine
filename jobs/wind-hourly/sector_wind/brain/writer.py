"""Brain RTDB writers for the WindBrain — thin wrappers over the shared Sector Brain Platform
(jobs/brain_platform/sector_brain_platform; docs/brains/BRAIN_PLATFORM_CONTRACT.md).

RtdbWriter: the contract's REST client (4 attempts, 1.5·2^n backoff, retry only on transport/5xx/429,
app-database refusal, illegal-key walk, ownership check for `wind`). `patch()` is ONE multi-path update at
the root, applied atomically. DryRunWriter: the same checks over an in-memory tree (tests, `--dry-run`).

The package is vendored next to main.py by deploy-job.sh; in the repo it is resolved from jobs/brain_platform.
"""
from __future__ import annotations

import os as _os
import sys as _sys

_job_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if not _os.path.isdir(_os.path.join(_job_root, "sector_brain_platform")):
    _sys.path.insert(0, _os.path.join(_job_root, "..", "brain_platform"))

from sector_brain_platform import BrainRtdb, BrainRtdbError, DryRunStore, TokenProvider  # noqa: E402
from sector_brain_platform.ownership import OwnershipError  # noqa: E402
from sector_brain_platform.keys import IllegalKey  # noqa: E402

BRAIN_ID = "wind"
PLATFORM = {"implementation": "sector_brain_platform", "contract": "docs/brains/BRAIN_PLATFORM_CONTRACT.md v1.0", "conformant": True}


class WriteError(RuntimeError):
    pass


class _StaticToken:
    def __init__(self, token: str):
        self._t = token

    def token(self) -> str:
        return self._t


def default_token() -> str:
    """Kept for callers that want a bare token (Cloud Run metadata, else gcloud)."""
    return TokenProvider().token()


class RtdbWriter:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 20.0):
        try:
            self._db = BrainRtdb(base_url, tokens=_StaticToken(token) if token else None, brain_id=BRAIN_ID, timeout_s=timeout)
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

    def get(self, path: str, query: dict | None = None):
        try:
            return self._db.get(path, shallow=bool((query or {}).get("shallow")))
        except BrainRtdbError as e:
            raise WriteError(str(e)) from None

    def delete(self, path: str) -> None:
        self.patch({path: None})


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

    def delete(self, path: str) -> None:
        self.patch({path: None})

    def dump(self, out_path: str) -> None:
        self._store.dump(out_path)
