#!/usr/bin/env python3
"""Protocol run ledger: one append-only, hash-chained record per pre-registered research protocol, pinned by public comments on
Sector_Ops #51. Stdlib only. The only network use is reading that issue's comments through the ``gh`` CLI.

Why it exists
-------------
A pre-registered protocol (RS-18) is only honest if the operator cannot run a step, look at the result and run it again. A write-once guard
in the operator-chosen ``--out`` folder does not do that: a new ``--out`` gives a fresh guard. A guard in a local folder alone does not
either: a new folder, a deleted ledger or a ledger restored from a snapshot each look like a fresh run #1. This module keeps a local ledger
in the research folder AND requires public, timestamped comments on Sector_Ops #51 that a local copy cannot take back.

Threat model (what it stops, and what it does not)
--------------------------------------------------
Stops, by refusing the step or by marking its result as not counting:
- **Accidental re-runs**: the same command run twice, a new ``--out`` folder, a new process.
- **Undisclosed re-runs by a session or agent**: a re-run from a new research folder, a deleted ledger, or a ledger rolled back to an
  earlier snapshot. Each of these needs a new ``Run anchor:`` or ``Run start:`` comment on #51; the earliest comment wins, so the re-run is
  refused or marked REPEAT, visibly and permanently in the public issue.
- **Local tampering**: edits, reordering or truncation of the ledger file (hash chain plus a head file).
- **Edited public records**: an anchor or start comment whose ``updated_at`` differs from ``created_at`` is refused, as is any edited comment
  that mentions the protocol id.

Does NOT stop (stated limits, not guarantees):
- **Deliberate deletion of public records.** Someone with rights to delete comments on #51 (an admin) can remove the earliest anchor or
  start comment, after which a later one looks earliest. Nothing inside the repository can prevent that. Mitigation: every result-producing
  COMPLETED entry records the ids and URLs of its anchor and start comments, and ``audit(check_external=True)`` reports any that no longer
  exist, so the deletion is detectable by anyone holding the ledger or a report that printed ``audit()``.
- **Abort after seeing values.** ``abort_before_result`` cannot know whether the operator looked at values. Every runner must pass a review
  check that it records outputs (``record_outputs``) as soon as they are written and never aborts after computing a result; the ledger
  cannot enforce it.
- **A forged Cortex.** ``for_brain`` trusts the ``cortex_home`` (or ``$CORTEX_HOME``) it is given to resolve the research folder.
- **GitHub itself**: comment timestamps are taken as GitHub records them; who posted a comment is not checked.

The rule
--------
1. **One ledger per protocol id, in the research folder.** ``<root>/_ledgers/<protocol_id>.jsonl``. Runners open it with
   ``Ledger.for_brain(brain, protocol_id, protocol_sha256)``, which takes ``root`` from ``cortex.py research-path sector/engine <brain>`` and
   refuses a ``SECTOR_RESEARCH_ROOT`` that differs. (``Ledger(root, ...)`` is for tests.) The root must exist, must not lie inside any
   ``--out`` folder (``forbid_under``), and must equal the root recorded in the ledger's first entry (a copied ledger is refused). The ledger
   is bound to the protocol sha256: a changed protocol needs a new protocol id.
2. **Anchor before results.** The first entry (``LEDGER_OPENED``) carries a random 128-bit nonce, the protocol id and sha256, the resolved
   root, the host and the UTC time; ``anchor()`` is its sha256. Post ``post_anchor_text()`` (``Run anchor: <protocol_id> <anchor>``) on #51.
   ``begin(..., result_producing=True)`` (the default) refuses unless the **earliest** ``Run anchor:`` comment for the protocol id carries this
   ledger's anchor and predates the ledger's first result-producing start. Steps that cannot see results (a fetch) pass
   ``result_producing=False``: they may run before the anchor, and may not record outputs before completion or a result summary.
3. **Start record per step.** ``begin`` of a result-producing step writes STARTED. The runner then posts ``start_text(step, key)``
   (``Run start: <protocol_id> <step> <key> <started_entry_sha256>``) on #51 and calls ``confirm_started(step, key)`` before computing
   anything. It refuses unless exactly one ``Run start:`` comment exists for (protocol, step, key) and it carries this attempt's STARTED hash.
   More than one is **REPEAT**: the step is refused, a ``REPEAT_DETECTED`` entry is written, and any later ``complete()`` of that
   (step, key) is recorded with ``counted: false``. ``complete()`` re-checks #51 and also marks the result not counting if a second
   ``Run start:`` appeared meanwhile. A rollback to an earlier snapshot therefore produces a second ``Run start:`` and is detected.
4. **Only the first run counts.** ``begin`` refuses a (step, key) with a COMPLETED entry. A STARTED entry with no end (process killed,
   machine rebooted) is **terminal**: recovery is a new protocol id. ``abort_before_result`` is the in-process exit for a failure before any
   result, allowed only from the ``Ledger`` object that began the attempt and only while no output and no result were recorded; a retry
   gets the next attempt number. For a result-producing step a retry is clean only if the aborted attempt never posted a ``Run start:``
   comment; once one is public, the retry's own ``Run start:`` is a second one and the retry is a REPEAT. ``counts`` is True only for the first COMPLETED run with ``counted: true``; ``require`` refuses a
   result that does not count.
5. **Inputs are bound before results.** ``bind_inputs`` before the step has a result; ``begin`` refuses inputs that differ from bound ones;
   ``check_inputs`` refuses any changed file. Later steps bind earlier results with ``require(step, key)`` and compare.

Entries
-------
One JSON object per line (sorted keys, compact): ``seq``, ``utc``, ``protocol_id``, ``protocol_sha256``, ``step``, ``key``, ``status``
(``LEDGER_OPENED`` first and only first, ``INPUTS_BOUND``, ``STARTED``, ``START_CONFIRMED``, ``REPEAT_DETECTED``, ``OUTPUTS_RECORDED``,
``COMPLETED``, ``ABORTED_BEFORE_RESULT``), ``run``, ``args``, ``inputs`` {name: sha256}, ``outputs`` {name: sha256}, ``result``, ``reason``,
``result_producing``, ``counted``, ``external`` (comment ids and URLs on #51), ``git_commit``, ``git_dirty``, ``host``,
``prev_entry_sha256``. A head file ``<protocol_id>.head.json`` records the last seq and line hash. Every write takes an exclusive ``fcntl``
lock, re-reads and verifies the chain, appends and fsyncs. Runners print ``audit()`` into their reports.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping

ENV_ROOT = "SECTOR_RESEARCH_ROOT"
ENV_CORTEX = "CORTEX_HOME"
CORTEX_PACK = "sector/engine"
LEDGER_DIR = "_ledgers"
GENESIS = "0" * 64
TREE_HASH = "sha256-tree-v1"
TREE_SKIP_DIRS = {"__pycache__"}
TREE_SKIP_FILES = {".DS_Store"}
LEDGER_OPENED = "LEDGER_OPENED"
INPUTS_BOUND = "INPUTS_BOUND"
STARTED = "STARTED"
START_CONFIRMED = "START_CONFIRMED"
REPEAT_DETECTED = "REPEAT_DETECTED"
OUTPUTS_RECORDED = "OUTPUTS_RECORDED"
COMPLETED = "COMPLETED"
ABORTED = "ABORTED_BEFORE_RESULT"
STATUSES = (LEDGER_OPENED, INPUTS_BOUND, STARTED, START_CONFIRMED, REPEAT_DETECTED, OUTPUTS_RECORDED, COMPLETED, ABORTED)
ANCHOR_PREFIX = "Run anchor:"
START_PREFIX = "Run start:"
ANCHOR_REPO = "Sector-Bowfishing/Sector_Ops"
ANCHOR_ISSUE = 51
RESULT_MAX_BYTES = 8192
FIELDS = ("seq", "utc", "protocol_id", "protocol_sha256", "step", "key", "status", "run", "args", "inputs", "outputs", "result", "reason",
          "result_producing", "counted", "external", "git_commit", "git_dirty", "host", "prev_entry_sha256")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TOKEN = re.compile(r"^\S{1,200}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_REPO = Path(__file__).resolve().parents[2]


class LedgerRefusal(Exception):
    """The ledger refused an operation. Runners stop; they never catch this to carry on."""


class ChainBroken(LedgerRefusal):
    """The ledger file was edited, truncated, reordered or copied, or does not belong to this protocol."""


class RepeatDetected(LedgerRefusal):
    """More than one ``Run start:`` comment exists for (protocol, step, key): the step was started more than once."""


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(directory) -> str:
    """sha256-tree-v1 (research.md RS-02, same recipe as Cortex ``research-check``): sha256 of the sorted UTF-8 lines
    ``<sha256>  <relpath>\\n``, relpath POSIX and relative to ``directory``, every file except ``__pycache__/`` and ``.DS_Store``."""
    base = Path(directory)
    if not base.is_dir():
        raise LedgerRefusal(f"sha256_tree: not a directory: {base}")
    lines = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in TREE_SKIP_DIRS]
        for f in filenames:
            if f not in TREE_SKIP_FILES:
                fp = Path(dirpath) / f
                lines.append(f"{sha256_file(fp)}  {fp.relative_to(base).as_posix()}\n")
    return sha256_bytes("".join(sorted(lines)).encode("utf-8"))


def _hash_value(name, value) -> str:
    """A recorded hash: a Path (file or directory) is hashed now; a str must already be a lowercase sha256."""
    if isinstance(value, os.PathLike):
        p = Path(value)
        if p.is_dir():
            return sha256_tree(p)
        if p.is_file():
            return sha256_file(p)
        raise LedgerRefusal(f"{name}: no such file or directory: {p}")
    if isinstance(value, str) and _HEX.match(value):
        return value
    raise LedgerRefusal(f"{name}: expected a Path or a lowercase sha256 hex string, got {value!r}")


def _hashes(kind, mapping) -> dict:
    if mapping is None:
        return {}
    if not isinstance(mapping, Mapping):
        raise LedgerRefusal(f"{kind} must be a dict of name -> sha256 or Path")
    out = {}
    for name, value in mapping.items():
        if not isinstance(name, str) or not name:
            raise LedgerRefusal(f"{kind}: names must be non-empty strings")
        out[name] = _hash_value(f"{kind}[{name}]", value)
    return out


def _canon(obj) -> str:
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise LedgerRefusal(f"not JSON-serialisable: {e}") from None


def _git(repo: Path):
    try:
        sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        if sha.returncode != 0:
            return None, None
        st = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True,
                            timeout=20)
        return sha.stdout.strip() or None, (bool(st.stdout.strip()) if st.returncode == 0 else None)
    except (OSError, subprocess.SubprocessError):
        return None, None


def _gh_api(path: str) -> str:
    """``gh api --paginate <path>`` stdout. Raises LedgerRefusal when gh is missing or fails: the public record is never assumed."""
    try:
        r = subprocess.run(["gh", "api", "--paginate", path], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        raise LedgerRefusal(f"gh api unavailable ({e}); the public record cannot be checked, so the step is refused") from None
    if r.returncode != 0:
        raise LedgerRefusal(f"gh api {path} failed (exit {r.returncode}): {r.stderr.strip()[:300]}; the step is refused")
    return r.stdout


def _json_arrays(text: str) -> list:
    """Parse ``gh api --paginate`` output: one or more concatenated JSON arrays."""
    dec, i, out = json.JSONDecoder(), 0, []
    text = text.strip()
    while i < len(text):
        try:
            obj, j = dec.raw_decode(text, i)
        except ValueError:
            raise LedgerRefusal("gh api returned output that is not JSON; the step is refused") from None
        if not isinstance(obj, list):
            raise LedgerRefusal("gh api returned JSON that is not a list of comments; the step is refused")
        out.extend(obj)
        i = j
        while i < len(text) and text[i].isspace():
            i += 1
    return out


def _parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _write_all(fd: int, data: bytes):
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise OSError("short write to the ledger")
        view = view[n:]


class Ledger:
    """The run ledger of one pre-registered protocol. See the module docstring for the rule and the threat model."""

    def __init__(self, root, protocol_id: str, protocol_sha256: str, forbid_under: Iterable = (), *, repo=None, gh=None,
                 anchor_repo: str = ANCHOR_REPO, anchor_issue: int = ANCHOR_ISSUE, _opened_by=None):
        """Plain constructor with an explicit ``root``, for tests and tooling. Runners use ``Ledger.for_brain``."""
        env = os.environ.get(ENV_ROOT) or None
        if root is None and env is None:
            raise LedgerRefusal(f"no research root: pass the folder `cortex.py research-path` returns, or set {ENV_ROOT}")
        if root is not None and env is not None and Path(root).resolve() != Path(env).resolve():
            raise LedgerRefusal(f"root {root} differs from {ENV_ROOT}={env}; two ledgers for one protocol are refused")
        self.root = Path(root if root is not None else env).expanduser().resolve()
        if not self.root.is_dir():
            raise LedgerRefusal(f"research root does not exist: {self.root} (resolve it with `cortex.py research-path`)")
        if not isinstance(protocol_id, str) or not _ID.match(protocol_id):
            raise LedgerRefusal(f"invalid protocol_id {protocol_id!r} (letters, digits, '.', '_', '-'; max 128)")
        if not isinstance(protocol_sha256, str) or not _HEX.match(protocol_sha256):
            raise LedgerRefusal("protocol_sha256 must be a lowercase sha256 hex string")
        for out in forbid_under or ():
            if out is None:
                continue
            o = Path(out).expanduser().resolve()
            if _inside(self.root, o):
                raise LedgerRefusal(f"research root {self.root} is inside the --out folder {o}; the ledger must not live with the outputs")
        self.protocol_id = protocol_id
        self.protocol_sha256 = protocol_sha256
        self.repo = Path(repo) if repo is not None else _REPO
        self.dir = self.root / LEDGER_DIR
        self.path = self.dir / f"{protocol_id}.jsonl"
        self.head_path = self.dir / f"{protocol_id}.head.json"
        self.lock_path = self.dir / f"{protocol_id}.lock"
        self._git = None
        self._gh = gh or _gh_api  # injectable for tests: callable(api_path) -> stdout of `gh api --paginate`
        self.anchor_repo, self.anchor_issue = anchor_repo, int(anchor_issue)
        self._mine = {}  # (step, key) -> attempt begun by THIS object; only it may confirm, record outputs, complete or abort
        self.dir.mkdir(exist_ok=True)
        with self._locked():
            ents = self._load()  # refuses a broken chain or another protocol hash now, before any work starts
            if not ents:
                opened = {"nonce": secrets.token_hex(16), "protocol_id": protocol_id, "protocol_sha256": protocol_sha256,
                          "root": str(self.root), "host": socket.gethostname(), "resolvedBy": "explicit-root", "brain": None}
                opened.update(_opened_by or {})
                self._append(ents, status=LEDGER_OPENED, result=opened)
            elif ents[0]["result"].get("root") != str(self.root):
                raise ChainBroken(f"{self.path}: this ledger was opened for root {ents[0]['result'].get('root')!r}, not {str(self.root)!r}; "
                                  f"a copied or moved ledger is refused")

    @classmethod
    def for_brain(cls, brain: str, protocol_id: str, protocol_sha256: str, repo=".", forbid_under: Iterable = (), *, cortex_home=None,
                  pack: str = CORTEX_PACK, **kwargs) -> "Ledger":
        """The runner constructor. Resolves the root with ``cortex.py research-path <pack> <brain>`` (Cortex at ``cortex_home`` or
        ``$CORTEX_HOME``, run in ``repo``). ``SECTOR_RESEARCH_ROOT``, if set, must equal that output. It trusts the Cortex it is given."""
        if not isinstance(brain, str) or not _ID.match(brain):
            raise LedgerRefusal(f"invalid brain {brain!r}")
        home = cortex_home or os.environ.get(ENV_CORTEX)
        if not home:
            raise LedgerRefusal(f"Cortex location unknown: pass cortex_home or set {ENV_CORTEX}; the root is never guessed")
        tool = Path(home).expanduser() / "tools" / "cortex.py"
        if not tool.is_file():
            raise LedgerRefusal(f"no Cortex tool at {tool}")
        cmd = [sys.executable, str(tool), "research-path", pack, brain]
        try:
            r = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            raise LedgerRefusal(f"research-path failed: {e}") from None
        paths = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith("#")]
        if r.returncode != 0 or not paths:
            raise LedgerRefusal(f"research-path {pack} {brain} failed (exit {r.returncode}): {(r.stderr or r.stdout).strip()[:300]}")
        resolved = Path(paths[0]).expanduser().resolve()
        env = os.environ.get(ENV_ROOT)
        if env and Path(env).expanduser().resolve() != resolved:
            raise LedgerRefusal(f"{ENV_ROOT}={env} is not the research-path folder for {brain} ({resolved}); refused")
        return cls(resolved, protocol_id, protocol_sha256, forbid_under, repo=Path(repo).resolve(), **kwargs,
                   _opened_by={"resolvedBy": "cortex-research-path", "brain": brain, "pack": pack, "root": str(resolved)})

    # ---------- locking, reading, verifying ----------
    @contextlib.contextmanager
    def _locked(self):
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _load(self, repair_head: bool = True) -> list:
        """Read and verify the whole ledger (call under the lock). Returns the entries."""
        raw = self.path.read_bytes() if self.path.exists() else b""
        head = None
        if self.head_path.exists():
            try:
                head = json.loads(self.head_path.read_text())
            except ValueError:
                raise ChainBroken(f"{self.head_path}: unreadable head file") from None
        if raw and not raw.endswith(b"\n"):
            raise ChainBroken(f"{self.path}: last line is incomplete (interrupted write or edit); investigate before any further run")
        lines = raw.split(b"\n")[:-1] if raw else []
        entries, prev = [], GENESIS
        for i, line in enumerate(lines, start=1):
            try:
                e = json.loads(line)
            except ValueError:
                raise ChainBroken(f"{self.path}: line {i} is not JSON") from None
            if not isinstance(e, dict) or tuple(sorted(e)) != tuple(sorted(FIELDS)):
                raise ChainBroken(f"{self.path}: line {i} does not have the ledger fields")
            if _canon(e).encode("ascii") != line:
                raise ChainBroken(f"{self.path}: line {i} is not in canonical form (edited)")
            if e["seq"] != i:
                raise ChainBroken(f"{self.path}: line {i} has seq {e['seq']} (entries removed or reordered)")
            if e["prev_entry_sha256"] != prev:
                raise ChainBroken(f"{self.path}: line {i} does not chain to line {i - 1} (an earlier entry was edited or removed)")
            if e["protocol_id"] != self.protocol_id:
                raise ChainBroken(f"{self.path}: line {i} belongs to protocol {e['protocol_id']!r}")
            if e["protocol_sha256"] != self.protocol_sha256:
                raise LedgerRefusal(f"protocol {self.protocol_id} is registered with sha256 {e['protocol_sha256']}, not "
                                    f"{self.protocol_sha256}; a changed protocol needs a new protocol id")
            if (e["status"] == LEDGER_OPENED) != (i == 1):
                raise ChainBroken(f"{self.path}: line {i}: LEDGER_OPENED must be the first entry and only the first")
            if e["status"] not in STATUSES:
                raise ChainBroken(f"{self.path}: line {i} has unknown status {e['status']!r}")
            entries.append(e)
            prev = sha256_bytes(line)
        if not entries:
            if head is not None and head.get("seq", 0) != 0:
                raise ChainBroken(f"{self.path}: ledger is missing or empty but its head records seq {head.get('seq')}")
            return entries
        last = entries[-1]["seq"]
        if head is None or (head.get("seq"), head.get("entry_sha256")) != (last, prev):
            prev_of_last = entries[-1]["prev_entry_sha256"]
            behind_by_one = head is None and last == 1 or (
                head is not None and head.get("seq") == last - 1 and head.get("entry_sha256") == prev_of_last)
            if behind_by_one and repair_head:
                self._write_head(last, prev)  # the process stopped between the append and the head update
            else:
                raise ChainBroken(f"{self.path}: tail does not match {self.head_path.name} (the last entries were edited or removed)")
        return entries

    def _write_head(self, seq: int, entry_sha: str):
        tmp = self.head_path.with_name(f"{self.head_path.name}.{os.getpid()}.tmp")
        with open(tmp, "w") as f:
            f.write(_canon({"protocol_id": self.protocol_id, "seq": seq, "entry_sha256": entry_sha}) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.head_path)
        dfd = os.open(self.dir, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def _append(self, entries: list, **fields) -> dict:
        if self._git is None:
            self._git = _git(self.repo)
        prev = sha256_bytes(_canon(entries[-1]).encode("ascii")) if entries else GENESIS
        e = {"seq": len(entries) + 1,
             "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
             "protocol_id": self.protocol_id, "protocol_sha256": self.protocol_sha256,
             "step": None, "key": None, "status": None, "run": None, "args": {}, "inputs": {}, "outputs": {}, "result": None,
             "reason": None, "result_producing": None, "counted": None, "external": None, "git_commit": self._git[0],
             "git_dirty": self._git[1], "host": socket.gethostname(), "prev_entry_sha256": prev}
        e.update(fields)
        line = _canon(e).encode("ascii")
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            _write_all(fd, line + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        self._write_head(e["seq"], sha256_bytes(line))
        entries.append(e)
        return e

    # ---------- the public record on #51 ----------
    def _anchor_of(self, ents) -> str:
        if not ents or ents[0]["status"] != LEDGER_OPENED:
            raise ChainBroken(f"{self.path}: first entry is not LEDGER_OPENED")
        return sha256_bytes(_canon(ents[0]).encode("ascii"))

    @staticmethod
    def _entry_sha(e) -> str:
        return sha256_bytes(_canon(e).encode("ascii"))

    def _comments(self) -> list:
        raw = self._gh(f"repos/{self.anchor_repo}/issues/{self.anchor_issue}/comments?per_page=100")
        out = []
        for c in _json_arrays(raw):
            if not isinstance(c, dict) or not c.get("created_at"):
                continue
            body = c.get("body") or ""
            edited = c.get("updated_at") not in (None, c["created_at"])
            if edited and self.protocol_id in body:
                raise LedgerRefusal(f"comment {c.get('id')} on {self.anchor_repo}#{self.anchor_issue} mentions {self.protocol_id} and was "
                                    f"edited (created {c['created_at']}, updated {c.get('updated_at')}); edited records are refused")
            out.append(c)
        return out

    def _matching(self, comments, prefix, tokens) -> list:
        """Comments whose first line is ``<prefix> <tokens...> <hash>``, earliest first."""
        n = len(prefix.split())
        hits = []
        for c in comments:
            first = (c.get("body") or "").lstrip().split("\n", 1)[0].split()
            if len(first) == n + len(tokens) + 1 and " ".join(first[:n]) == prefix and first[n:n + len(tokens)] == list(tokens):
                hits.append((_parse_time(c["created_at"]), c.get("id") or 0, first[-1].lower(), c))
        return sorted(hits, key=lambda t: (t[0], t[1]))

    @staticmethod
    def _ref(c) -> dict:
        return {"id": c.get("id"), "url": c.get("html_url"), "created_at": c.get("created_at")}

    def _check_anchor(self, ents, comments, start_utc: str | None) -> dict:
        a = self._anchor_of(ents)
        hits = self._matching(comments, ANCHOR_PREFIX, [self.protocol_id])
        if not hits:
            raise LedgerRefusal(f"no `{ANCHOR_PREFIX} {self.protocol_id}` comment on {self.anchor_repo}#{self.anchor_issue}; post "
                                f"post_anchor_text() there before any result-producing step")
        created, _, posted, c = hits[0]
        if posted != a:
            raise LedgerRefusal(f"the earliest anchor for {self.protocol_id} on {self.anchor_repo}#{self.anchor_issue} is {posted} "
                                f"(comment {c.get('id')}), not this ledger's {a}; this ledger is not the protocol's run ledger (a later "
                                f"anchor is not accepted while the earliest one exists; a fresh ledger needs a new protocol id)")
        starts = [e["utc"] for e in ents if e["status"] == STARTED and e["result_producing"]]
        bound = starts[0] if starts else start_utc
        if bound is not None and not created < _parse_time(bound):
            raise LedgerRefusal(f"anchor comment {c.get('id')} was created at {c['created_at']}, not before the first result-producing "
                                f"start ({bound}); the anchor must be posted before results can be seen")
        return {"anchor": a, "comment_id": c.get("id"), "created_at": c["created_at"], "url": c.get("html_url")}

    def anchor(self) -> str:
        """sha256 of the ledger's first line (the LEDGER_OPENED genesis with its random nonce)."""
        with self._locked():
            return self._anchor_of(self._load())

    def verify_anchor(self, expected_hash: str) -> str:
        """Refuse unless the first entry's hash equals ``expected_hash``. Returns the anchor."""
        a = self.anchor()
        if not isinstance(expected_hash, str) or a != expected_hash.strip().lower():
            raise ChainBroken(f"{self.path}: anchor {a} does not match the posted anchor {expected_hash!r}; this ledger is invalid")
        return a

    def post_anchor_text(self) -> str:
        """The comment to post on Sector_Ops #51 before any result-producing step; first line ``Run anchor: <protocol_id> <anchor>``."""
        with self._locked():
            ents = self._load()
        a, g = self._anchor_of(ents), ents[0]
        return (f"{ANCHOR_PREFIX} {self.protocol_id} {a}\n\n"
                f"- protocol sha256: `{self.protocol_sha256}`\n"
                f"- ledger: `{LEDGER_DIR}/{self.protocol_id}.jsonl` under the research root `{g['result'].get('root')}`\n"
                f"- host: `{g['host']}`; genesis UTC: `{g['utc']}`; resolved by: `{g['result'].get('resolvedBy')}`\n\n"
                f"The earliest `{ANCHOR_PREFIX}` comment for this protocol id is the binding record; a later one is not accepted while it exists. "
                f"Do not edit or delete this comment.\n")

    def require_external_anchor(self, repo: str | None = None, issue: int | None = None) -> dict:
        """Refuse unless the earliest ``Run anchor:`` comment for this protocol id on ``repo``#``issue`` (default Sector_Ops #51) carries
        this ledger's anchor, is unedited and predates the first result-producing STARTED entry. A gh failure refuses."""
        if repo is not None:
            self.anchor_repo = repo
        if issue is not None:
            self.anchor_issue = int(issue)
        with self._locked():
            ents = self._load()
            return self._check_anchor(ents, self._comments(), _now())

    def start_text(self, step: str, key: str) -> str:
        """The comment to post on #51 right after ``begin`` of a result-producing step; first line
        ``Run start: <protocol_id> <step> <key> <started_entry_sha256>``."""
        with self._locked():
            ents = self._load()
            st = self._my_started(ents, step, key, "start_text")
        return (f"{START_PREFIX} {self.protocol_id} {step} {key} {self._entry_sha(st)}\n\n"
                f"- attempt {st['run']} started `{st['utc']}` on `{st['host']}`; ledger anchor `{self._anchor_of(ents)}`\n\n"
                f"Only one `{START_PREFIX}` comment may exist for this protocol, step and key; a second one marks a repeat. "
                f"Do not edit or delete this comment.\n")

    def _starts(self, comments, step, key) -> list:
        return self._matching(comments, START_PREFIX, [self.protocol_id, step, key])

    def confirm_started(self, step: str, key: str) -> dict:
        """Call right after posting ``start_text``. Refuses unless exactly one ``Run start:`` comment exists for (protocol, step, key)
        and it carries this attempt's STARTED hash. More than one is REPEAT: a REPEAT_DETECTED entry is written and RepeatDetected raised."""
        with self._locked():
            ents = self._load()
            st = self._my_started(ents, step, key, "confirm_started")
            mine = self._of(ents, step, key)
            if any(e["status"] == START_CONFIRMED and e["run"] == st["run"] for e in mine):
                raise LedgerRefusal(f"{step}/{key} run {st['run']} is already confirmed")
            comments = self._comments()
            anchor = self._check_anchor(ents, comments, None)
            hits = self._starts(comments, step, key)
            h = self._entry_sha(st)
            if not hits:
                raise LedgerRefusal(f"no `{START_PREFIX} {self.protocol_id} {step} {key}` comment on {self.anchor_repo}#{self.anchor_issue}; "
                                    f"post start_text() there first")
            if len(hits) > 1 or hits[0][2] != h:
                ext = {"anchor": self._ref_from(anchor), "starts": [self._ref(t[3]) | {"sha": t[2]} for t in hits]}
                self._append(ents, step=step, key=key, status=REPEAT_DETECTED, run=st["run"], external=ext,
                             reason=f"{len(hits)} Run start comment(s); earliest carries {hits[0][2]}, this attempt {h}")
                raise RepeatDetected(f"REPEAT: {self.protocol_id} {step}/{key} has {len(hits)} `{START_PREFIX}` comment(s) and the earliest "
                                     f"is {'not ' if hits[0][2] != h else ''}this attempt's; the step was started before (a re-run, a new "
                                     f"folder or a restored snapshot). Refused; any result of this step does not count")
            ext = {"anchor": self._ref_from(anchor), "start": self._ref(hits[0][3])}
            return dict(self._append(ents, step=step, key=key, status=START_CONFIRMED, run=st["run"], external=ext))

    @staticmethod
    def _ref_from(anchor: dict) -> dict:
        return {"id": anchor["comment_id"], "url": anchor["url"], "created_at": anchor["created_at"], "sha": anchor["anchor"]}

    # ---------- queries ----------
    @staticmethod
    def _of(entries, step, key):
        return [e for e in entries if e["step"] == step and e["key"] == key]

    @staticmethod
    def _open_attempt(mine):
        """The latest STARTED attempt if it is still open (not COMPLETED, not ABORTED), else None."""
        starts = [e for e in mine if e["status"] == STARTED]
        if not starts:
            return None
        run = starts[-1]["run"]
        closed = any(e["run"] == run and e["status"] in (COMPLETED, ABORTED) for e in mine)
        return None if closed else starts[-1]

    @staticmethod
    def _check(step, key):
        for n, v in (("step", step), ("key", key)):
            if not isinstance(v, str) or not _TOKEN.match(v):
                raise LedgerRefusal(f"{n} must be a non-empty string without whitespace (max 200)")

    def _my_started(self, ents, step, key, what) -> dict:
        self._check(step, key)
        open_ = self._open_attempt(self._of(ents, step, key))
        if open_ is None:
            raise LedgerRefusal(f"{what}: {step}/{key} has no open attempt (call begin first)")
        if self._mine.get((step, key)) != open_["run"]:
            raise LedgerRefusal(f"{what}: {step}/{key} run {open_['run']} was begun by another process; a STARTED entry with no end is "
                                f"terminal, and recovery is a new protocol id")
        return open_

    def entries(self) -> list:
        with self._locked():
            return [dict(e) for e in self._load()]

    def verify_chain(self) -> int:
        """Verify the whole chain and the head; returns the number of entries. Raises ChainBroken on any break or edit, LedgerRefusal on a
        protocol hash mismatch."""
        with self._locked():
            return len(self._load(repair_head=False))

    def head(self) -> dict:
        """{protocol_id, protocol_sha256, seq, entry_sha256}."""
        with self._locked():
            ents = self._load()
            sha = self._entry_sha(ents[-1]) if ents else GENESIS
            return {"protocol_id": self.protocol_id, "protocol_sha256": self.protocol_sha256, "seq": len(ents), "entry_sha256": sha}

    def first(self, step: str, key: str):
        """The first COMPLETED entry for (step, key), or None. Check ``counted`` (or use ``counts``/``require``)."""
        with self._locked():
            done = [e for e in self._of(self._load(), step, key) if e["status"] == COMPLETED]
        return dict(done[0]) if done else None

    def require(self, step: str, key: str) -> dict:
        """The first COMPLETED entry for (step, key); refuses if the step has no result yet or its result does not count (REPEAT)."""
        e = self.first(step, key)
        if e is None:
            raise LedgerRefusal(f"{self.protocol_id}: step {step!r} key {key!r} has no COMPLETED run; it must run first")
        if e["counted"] is not True:
            raise LedgerRefusal(f"{self.protocol_id}: step {step!r} key {key!r} completed as a REPEAT and does not count")
        return e

    def counts(self, step: str, key: str, run: int | None = None) -> bool:
        """True only for the first COMPLETED run of (step, key), and only if it counts. With ``run``, only when that run is it."""
        e = self.first(step, key)
        return e is not None and e["counted"] is True and (run is None or e["run"] == run)

    def audit(self, check_external: bool = False) -> dict:
        """A summary for run reports: anchor, head and every COMPLETED / REPEAT_DETECTED entry with its #51 comment ids. With
        ``check_external``, re-reads #51 and lists ``findings`` (a recorded comment missing or edited, the anchor no longer the earliest,
        more than one Run start for a completed step). Missing comments are how a deletion of the public record becomes visible."""
        with self._locked():
            ents = self._load()
        steps = [{"step": e["step"], "key": e["key"], "run": e["run"], "status": e["status"], "counted": e["counted"],
                  "external": e["external"]} for e in ents if e["status"] in (COMPLETED, REPEAT_DETECTED)]
        out = {"protocol_id": self.protocol_id, "protocol_sha256": self.protocol_sha256, "ledger": str(self.path),
               "anchor": self._anchor_of(ents), "head": {"seq": len(ents), "entry_sha256": self._entry_sha(ents[-1])}, "steps": steps,
               "issue": f"{self.anchor_repo}#{self.anchor_issue}"}
        if not check_external:
            return out
        findings = []
        try:
            comments = self._comments()
        except LedgerRefusal as e:
            out["findings"] = [f"EXTERNAL_UNCHECKED: {e}"]
            return out
        by_id = {c.get("id"): c for c in comments}
        try:
            self._check_anchor(ents, comments, None)
        except LedgerRefusal as e:
            findings.append(f"ANCHOR: {e}")
        for s in steps:
            ext = s["external"] or {}
            refs = [ext.get("anchor")] + ([ext["start"]] if ext.get("start") else []) + list(ext.get("starts") or [])
            for r in refs:
                if r and r.get("id") not in by_id:
                    findings.append(f"MISSING_COMMENT: {s['step']}/{s['key']} comment {r.get('id')} ({r.get('url')}) no longer exists")
            if s["status"] == COMPLETED and s["external"]:
                n = len(self._starts(comments, s["step"], s["key"]))
                if n != 1:
                    findings.append(f"START_COUNT: {s['step']}/{s['key']} has {n} `{START_PREFIX}` comments")
        out["findings"] = findings
        return out

    # ---------- writes ----------
    def bind_inputs(self, step: str, key: str, files: Mapping) -> dict:
        """Hash ``files`` ({name: Path}, or {name: sha256}) and record them for (step, key) before it has a result. Binding the same hashes
        again is a no-op; different hashes, or binding after a result, are refused. Returns {name: sha256}."""
        self._check(step, key)
        hashes = _hashes("files", files)
        if not hashes:
            raise LedgerRefusal("bind_inputs: no files")
        with self._locked():
            ents = self._load()
            mine = self._of(ents, step, key)
            if any(e["status"] == COMPLETED for e in mine):
                raise LedgerRefusal(f"{step}/{key}: already has a result; inputs are bound before results, not after")
            bound = self._bound(mine)
            for name, h in hashes.items():
                if name in bound and bound[name] != h:
                    raise LedgerRefusal(f"{step}/{key}: input {name!r} was bound as {bound[name]}, now {h}")
            new = {n: h for n, h in hashes.items() if n not in bound}
            if new:
                self._append(ents, step=step, key=key, status=INPUTS_BOUND, inputs=new)
        return hashes

    @staticmethod
    def _bound(mine) -> dict:
        bound = {}
        for e in mine:
            if e["status"] == INPUTS_BOUND:
                bound.update(e["inputs"])
        return bound

    def check_inputs(self, step: str, key: str, files: Mapping) -> dict:
        """Refuse if any of ``files`` differs from what ``bind_inputs`` recorded for (step, key), or was never bound. Returns the hashes."""
        self._check(step, key)
        hashes = _hashes("files", files)
        with self._locked():
            bound = self._bound(self._of(self._load(), step, key))
        if not bound:
            raise LedgerRefusal(f"{step}/{key}: no inputs were bound")
        for name, h in hashes.items():
            if name not in bound:
                raise LedgerRefusal(f"{step}/{key}: input {name!r} was never bound")
            if bound[name] != h:
                raise LedgerRefusal(f"{step}/{key}: input {name!r} changed since it was bound ({bound[name]} -> {h})")
        return hashes

    def begin(self, step: str, key: str, args: Mapping | None = None, inputs: Mapping | None = None, *,
              result_producing: bool = True) -> int:
        """Record a STARTED attempt and return its attempt number (1 for the first). Refused when (step, key) has a COMPLETED run, when an
        earlier attempt has no end (terminal: a new protocol id is the only recovery), when ``inputs`` differ from inputs bound for
        (step, key), or, for a result-producing step (the default), when the anchor check refuses. A result-producing step then needs
        ``start_text`` posted on #51 and ``confirm_started`` before it computes anything."""
        self._check(step, key)
        args = dict(args or {})
        _canon(args)
        hashes = _hashes("inputs", inputs)
        with self._locked():
            ents = self._load()
            mine = self._of(ents, step, key)
            done = [e for e in mine if e["status"] == COMPLETED]
            if done:
                raise LedgerRefusal(f"{self.protocol_id}: {step}/{key} already ran (run {done[0]['run']} COMPLETED at {done[0]['utc']}, "
                                    f"ledger {self.path}); only that run counts; a re-run is refused")
            open_ = self._open_attempt(mine)
            if open_ is not None:
                raise LedgerRefusal(f"{self.protocol_id}: {step}/{key} run {open_['run']} STARTED at {open_['utc']} and never completed or "
                                    f"aborted; a STARTED entry with no end is terminal for this step, and recovery is a new protocol id")
            bound = self._bound(mine)
            for name, h in hashes.items():
                if name in bound and bound[name] != h:
                    raise LedgerRefusal(f"{step}/{key}: input {name!r} differs from the bound input ({bound[name]} -> {h})")
            if result_producing:
                self._check_anchor(ents, self._comments(), _now())
            run = 1 + sum(1 for e in mine if e["status"] == STARTED)
            self._append(ents, step=step, key=key, status=STARTED, run=run, args=args, inputs=hashes,
                         result_producing=bool(result_producing))
            self._mine[(step, key)] = run
        return run

    @staticmethod
    def _recorded_outputs(mine, run) -> dict:
        out = {}
        for e in mine:
            if e["run"] == run and e["status"] in (OUTPUTS_RECORDED, COMPLETED):
                out.update(e["outputs"])
        return out

    def _confirmed(self, mine, run):
        return next((e for e in mine if e["status"] == START_CONFIRMED and e["run"] == run), None)

    def record_outputs(self, step: str, key: str, outputs: Mapping) -> dict:
        """Record outputs of the open result-producing attempt as soon as they are written, before the result summary exists. After this
        the attempt can no longer be aborted. Refused for an attempt that is not result-producing or not confirmed. Returns the hashes."""
        hashes = _hashes("outputs", outputs)
        if not hashes:
            raise LedgerRefusal("record_outputs: no outputs")
        with self._locked():
            ents = self._load()
            st = self._my_started(ents, step, key, "record_outputs")
            mine = self._of(ents, step, key)
            if not st["result_producing"]:
                raise LedgerRefusal(f"record_outputs: {step}/{key} is not result-producing; its outputs go in complete()")
            if self._confirmed(mine, st["run"]) is None:
                raise LedgerRefusal(f"record_outputs: {step}/{key} run {st['run']} has no confirmed `{START_PREFIX}` record")
            prior = self._recorded_outputs(mine, st["run"])
            for n, h in hashes.items():
                if n in prior and prior[n] != h:
                    raise LedgerRefusal(f"{step}/{key}: output {n!r} was recorded as {prior[n]}, now {h}")
            self._append(ents, step=step, key=key, status=OUTPUTS_RECORDED, run=st["run"], outputs=hashes)
        return hashes

    def complete(self, step: str, key: str, outputs: Mapping | None = None, result: Mapping | None = None) -> dict:
        """Close the open attempt as COMPLETED. A result-producing attempt needs ``confirm_started`` first; #51 is re-read, and the entry
        records the anchor and start comment ids, with ``counted: false`` if the step is a REPEAT. A non-result attempt takes outputs
        only (no result summary). A gh failure refuses (the same object may call complete again later). Returns the entry."""
        hashes = _hashes("outputs", outputs)
        result = dict(result or {})
        if len(_canon(result)) > RESULT_MAX_BYTES:
            raise LedgerRefusal(f"result summary is larger than {RESULT_MAX_BYTES} bytes; record a file hash in outputs instead")
        with self._locked():
            ents = self._load()
            st = self._my_started(ents, step, key, "complete")
            mine = self._of(ents, step, key)
            prior = self._recorded_outputs(mine, st["run"])
            for n, h in hashes.items():
                if n in prior and prior[n] != h:
                    raise LedgerRefusal(f"{step}/{key}: output {n!r} was recorded as {prior[n]}, now {h}")
            if not st["result_producing"]:
                if result:
                    raise LedgerRefusal(f"complete: {step}/{key} is not result-producing; it may not record a result summary")
                e = self._append(ents, step=step, key=key, status=COMPLETED, run=st["run"], outputs={**prior, **hashes}, result={},
                                 counted=True)
                return dict(e)
            conf = self._confirmed(mine, st["run"])
            if conf is None:
                raise LedgerRefusal(f"complete: {step}/{key} run {st['run']} has no confirmed `{START_PREFIX}` record (post start_text, then "
                                    f"call confirm_started before computing)")
            comments = self._comments()
            n = len(self._starts(comments, step, key))
            repeat = n != 1 or any(e["status"] == REPEAT_DETECTED for e in mine)
            ext = dict(conf["external"], startCommentsAtComplete=n)
            e = self._append(ents, step=step, key=key, status=COMPLETED, run=st["run"], outputs={**prior, **hashes}, result=result,
                             counted=not repeat, external=ext,
                             reason=(f"REPEAT: {n} `{START_PREFIX}` comments at completion; this result does not count" if repeat else None))
        return dict(e)

    def abort_before_result(self, step: str, key: str, reason: str) -> dict:
        """Close the open attempt without a result, so a later attempt may begin. Refused once any output or result was recorded. Whether
        values were seen cannot be checked here: never call this after computing a result (a review check for every runner)."""
        if not isinstance(reason, str) or not reason.strip():
            raise LedgerRefusal("abort_before_result needs a reason")
        with self._locked():
            ents = self._load()
            st = self._my_started(ents, step, key, "abort_before_result")
            mine = self._of(ents, step, key)
            if self._recorded_outputs(mine, st["run"]) or any(e["run"] == st["run"] and e["result"] for e in mine):
                raise LedgerRefusal(f"{step}/{key} run {st['run']} already recorded outputs or a result; it cannot be aborted before a result")
            e = self._append(ents, step=step, key=key, status=ABORTED, run=st["run"], reason=reason.strip())
        return dict(e)
