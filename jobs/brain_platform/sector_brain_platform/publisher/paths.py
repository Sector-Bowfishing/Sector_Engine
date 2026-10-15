"""Path normalisation and authorised path families (BRAIN_PATH_OWNERSHIP_V1).

A family is an exact-depth pattern. `{name}` matches exactly ONE path segment and may carry a constraint. There is no `**`/prefix wildcard:
a family never silently covers a deeper or shallower path, so a broad permission cannot be granted by accident.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from ..keys import BRAINS
from ..ownership import PLATFORM_WRITER, path_allowed

_ILLEGAL = re.compile(r"[.$#\[\]/\x00-\x1f\x7f]")
LAKE_KEY = re.compile(r"[A-Za-z0-9_]+")
PATH_STATUSES = ("CANONICAL", "DERIVED_PROJECTION", "LEGACY_READER_PRESENT", "RETIREMENT_CANDIDATE", "PLACEHOLDER")
#: Publisher-owned children of /brains/{id}. No artifact may write them, nor replace an ancestor (which would erase them).
RESERVED_BRAIN_CHILDREN = frozenset({"publication", "certification"})
#: Roots no Brain artifact can ever target, whatever a schema declares.
FORBIDDEN_ROOTS = frozenset({"access", "control", "jobs", "scores", "engine", "schemaVersion", "controlRequests"})


class PathError(ValueError):
    pass


def normalize_path(p) -> str:
    """'/a/b' form. Rejects non-strings, relative paths, empty/dot segments, trailing slashes and RTDB-illegal characters."""
    if not isinstance(p, str) or not p.startswith("/") or len(p) < 2:
        raise PathError(f"path must be an absolute string starting with '/': {p!r}")
    segs = p[1:].split("/")
    for s in segs:
        if s == "" or _ILLEGAL.search(s):
            raise PathError(f"illegal path segment {s!r} in {p!r}")
    return "/" + "/".join(segs)


def segments(path: str) -> list[str]:
    return path[1:].split("/")


def to_rtdb_key(path: str) -> str:
    """The root-relative key the platform's multi-path update uses (no leading slash)."""
    return path[1:]


def touches_reserved(path: str) -> bool:
    """True for /brains, /brains/{id} (ancestors of the reserved children) and /brains/{id}/{publication|certification}[/...]."""
    s = segments(path)
    return s[0] == "brains" and (len(s) <= 2 or s[2] in RESERVED_BRAIN_CHILDREN)


Check = Callable[[str], bool]


@dataclass(frozen=True)
class PathFamily:
    pattern: str                                    # '/lakes/{k}/states/wind'
    params: dict = field(default_factory=dict)      # name -> Check; an unlisted {name} matches any legal segment
    status: str = "CANONICAL"
    note: str = ""

    def __post_init__(self):
        normalize_path(self.pattern.replace("{", "x").replace("}", "x"))
        if self.status not in PATH_STATUSES:
            raise ValueError(f"unknown path status {self.status!r}")

    def match(self, path: str) -> bool:
        pat, got = segments(self.pattern), segments(path)
        if len(pat) != len(got):
            return False
        for p, g in zip(pat, got):
            if p.startswith("{") and p.endswith("}"):
                chk = self.params.get(p[1:-1])
                if chk is not None and not chk(g):
                    return False
            elif p != g:
                return False
        return not touches_reserved(path)


def lake_key_check(s: str) -> bool:
    return LAKE_KEY.fullmatch(s) is not None


def one_of(values) -> Check:
    vs = frozenset(values)
    return lambda s: s in vs


def not_in(values) -> Check:
    vs = frozenset(values)
    return lambda s: s not in vs and re.fullmatch(r"[A-Za-z0-9_-]+", s) is not None


def contains(token: str) -> Check:
    return lambda s: token in s


#: Prefixes owned by identities that are not Brains (species identity/policy, platform). Used to NAME a cross-domain attempt.
PROTECTED_ROOTS = {"speciesProfiles": "species", "speciesIndexes": "species-registry", "species": "species",
                   "access": "platform", "control": "platform", "jobs": "platform", "scores": "platform", "engine": "platform"}


def foreign_owner(path: str, submitter: str) -> str | None:
    """Who else would legitimately own `path`? Reuses the live ownership table (ownership.path_allowed) plus the protected roots.
    None = nobody known (unauthorised, but not provably cross-domain). Only used to give the right rejection code."""
    s = segments(path)
    if s[0] in PROTECTED_ROOTS:
        return PROTECTED_ROOTS[s[0]]
    if len(s) >= 3 and s[0] == "lakes" and s[2] == "speciesPresence":
        return "lake-brain"
    for other in list(BRAINS) + [PLATFORM_WRITER]:
        if other != submitter and path_allowed(other, path):
            return other
    return None
