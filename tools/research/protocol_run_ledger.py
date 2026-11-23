#!/usr/bin/env python3
"""Protocol run ledger: one append-only, hash-chained record per pre-registered research protocol, with a public trail of comments on
Sector_Ops #51. Stdlib only. The only network use is reading that issue's comments through the ``gh`` CLI.

Why it exists
-------------
A pre-registered protocol (RS-18) is only honest if a step is not run, looked at and run again. A write-once guard in the operator-chosen
``--out`` folder does not do that (a new ``--out`` is a fresh guard), and neither does a local file alone (a new folder, a deleted ledger or
a restored snapshot each look like a fresh run #1). This module keeps a ledger in the research folder and requires public, timestamped
``Run anchor:`` / ``Run start:`` / ``Run result:`` comments on #51 that a local copy cannot take back.

Threat model
------------
**It stops** accidental re-runs, and re-runs by an honest-but-careless or non-disclosing session or agent that uses this API as written:
the same command again, a new ``--out``, a new process, a new research folder, a deleted ledger, a ledger rolled back to a snapshot, a
reopen with a different declared set of result steps, a deleted ledger replaced by one with a corrected set of result steps, a copied
ledger. Such a re-run is refused, or its result is recorded with ``counted: false`` and is visible as a second comment in the public
trail. No step of any kind runs before this ledger's anchor, which names the declared result steps, is the protocol's earliest anchor
on #51, so a ledger cannot produce values first and be replaced by a "corrected" one that anchors afterwards.

**It does NOT stop a deliberate actor** holding the same GitHub or filesystem credentials. The gh identity that posted a comment can edit
or delete its own comments, and GitHub's REST API does not expose edit history; anyone who can write the research folder can forge
ledger lines and recompute the hash chain and head file. The hash chain only detects accidental corruption and careless edits. The real
assurance against a deliberate actor is the public #51 trail plus human review. Within that limit the module adds detection aids:
edited records are refused (see ``_screen``), the ledger records the id and body sha256 of each anchor, start and result comment it
confirmed, and a ``Run result:`` comment posted after ``complete()`` lets ``audit(check_external=True)`` detect a ledger tail that was
forged afterwards, as long as the comments still exist. **Edit screening and its blast radius:** a recorded comment is "edited" when its
body sha256 differs from the recorded one; an unrecorded comment is "edited" when ``updated_at`` is more than 2 s after ``created_at``
(GitHub can bump ``updated_at`` without an edit), and it matters only if it names this protocol id as an exact token. One such edit blocks
every further step of THIS protocol (recovery: a new protocol id, after human review on #51); other protocols are unaffected. An unrecorded
comment edited so that it no longer names the protocol id is not detected (edit history is not readable over REST). **Runners and
agents must never edit a #51 comment that names a protocol id**; a correction is a new comment, and a mistake goes to human review. Other limits: ``for_brain`` trusts the Cortex it is given; GitHub's timestamps are
trusted; "abort only before seeing values" cannot be enforced and is a review check every runner must pass.

The rule
--------
1. **One ledger per protocol id, in the research folder** (``<root>/_ledgers/<protocol_id>.jsonl``). Runners open it with
   ``Ledger.for_brain(brain, protocol_id, protocol_sha256, result_steps=RESULT_STEPS)``; the root comes from ``cortex.py research-path``
   (a differing ``SECTOR_RESEARCH_ROOT`` is refused), must not lie inside any ``--out`` folder, and must equal the root in the genesis entry.
   The ledger is bound to the protocol sha256: a changed protocol needs a new protocol id. The anchor line carries the protocol sha256,
   and an anchor is refused if the same sha256 was anchored earlier under a different protocol id: the identical protocol cannot be
   re-run under a new id (a genuinely new version has a new sha256).
2. **Result steps are declared, not chosen per call.** ``result_steps`` is a module constant of the runner, recorded in the genesis entry
   and in the anchor comment; a reopen with a different set is refused. ``begin`` treats a step as result-producing exactly when it is in
   that set. A non-result ``begin`` is refused if #51 has any ``Run start:`` for that step.
3. **Anchor before ANY step.** The genesis entry carries a random 128-bit nonce, the protocol id and sha256, the root, the result steps,
   the host and the time; ``anchor()`` is its sha256. Post ``post_anchor_text()`` on #51: its first line is
   ``Run anchor: <protocol_id> <anchor> <result steps, sorted, comma-joined, or "-"> <protocol_sha256>``. Every ``begin`` (result step or not) refuses unless
   the earliest ``Run anchor:`` for the protocol id carries this ledger's anchor and result steps and predates the ledger's first start.
4. **Start record per result step.** After ``begin``, post ``start_text(step, key)`` and call ``confirm_started(step, key)`` before computing.
   The ``Run start:`` comments for (protocol, step, key) are counted by distinct hash, so identical copies (a repost during listing lag)
   count once: the only hash present must be THIS attempt's STARTED hash. None listed yet means "wait and retry confirm_started(); do NOT
   repost". Any other hash is REPEAT (``REPEAT_DETECTED`` entry, ``RepeatDetected`` raised). ``complete()`` re-reads #51 and records
   ``counted: false`` unless this attempt's hash is still the only one. So a second start (another hash) appearing before ``complete()``
   means neither attempt counts; only a start that completed before a second one appeared counts. After ``complete()``, post ``result_text(step, key)``
   (``Run result: <protocol> <step> <key> <completed_entry_sha256> <result_sha256>``) and call ``confirm_result(step, key)``, which
   records the comment's id and body sha256.
5. **Only the first counted run counts.** ``begin`` refuses a (step, key) with any COMPLETED entry. A STARTED entry with no end is
   terminal: recovery is a new protocol id, after human review on #51. ``abort_before_result`` (same object, no output, no result) allows a retry with the next attempt
   number; once a ``Run start:`` is public, a retry is a REPEAT. ``first``/``counts``/``require`` accept only counted COMPLETED entries of
   result steps.
6. **Inputs are bound before results** (``bind_inputs``, ``check_inputs``; ``begin`` refuses inputs that differ from bound ones).

Entries
-------
One JSON object per line (sorted keys, compact): ``seq``, ``utc``, ``protocol_id``, ``protocol_sha256``, ``step``, ``key``, ``status``
(``LEDGER_OPENED`` first and only first, ``INPUTS_BOUND``, ``STARTED``, ``START_CONFIRMED``, ``REPEAT_DETECTED``, ``OUTPUTS_RECORDED``,
``COMPLETED``, ``RESULT_CONFIRMED``, ``ABORTED_BEFORE_RESULT``), ``run``, ``args``, ``inputs``, ``outputs``, ``result``, ``reason``, ``result_producing``,
``counted``, ``external`` (comment ids, URLs and body sha256 on #51), ``git_commit``, ``git_dirty``, ``host``, ``prev_entry_sha256``. A head file
``<protocol_id>.head.json`` records the last seq and line hash. Writes take an exclusive ``fcntl`` lock, re-verify the chain, append
(looping on short writes) and fsync. Runners print ``audit()`` into their reports.
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
RESULT_CONFIRMED = "RESULT_CONFIRMED"
ABORTED = "ABORTED_BEFORE_RESULT"
STATUSES = (LEDGER_OPENED, INPUTS_BOUND, STARTED, START_CONFIRMED, REPEAT_DETECTED, OUTPUTS_RECORDED, COMPLETED, RESULT_CONFIRMED, ABORTED)
ANCHOR_PREFIX = "Run anchor:"
START_PREFIX = "Run start:"
RESULT_PREFIX = "Run result:"
EDIT_GRACE_SECONDS = 2
_PUNCT = "`'\"()[]{}<>,;:."
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

    def __init__(self, root, protocol_id: str, protocol_sha256: str, forbid_under: Iterable = (), *, result_steps: frozenset,
                 repo=None, gh=None, anchor_repo: str = ANCHOR_REPO, anchor_issue: int = ANCHOR_ISSUE, _opened_by=None):
        """Plain constructor with an explicit ``root``, for tests and tooling. Runners use ``Ledger.for_brain``. ``result_steps`` is the
        runner's declared set of result-producing step names (a module constant), recorded in the genesis entry."""
        if isinstance(result_steps, (str, bytes)) or not isinstance(result_steps, (set, frozenset, tuple, list)):
            raise LedgerRefusal("result_steps must be a frozenset of step names declared by the runner")
        for st in result_steps:
            if not isinstance(st, str) or not _TOKEN.match(st):
                raise LedgerRefusal(f"result_steps: invalid step name {st!r}")
        self.result_steps = frozenset(result_steps)
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
                          "root": str(self.root), "host": socket.gethostname(), "resolvedBy": "explicit-root", "brain": None,
                          "resultSteps": sorted(self.result_steps)}
                opened.update(_opened_by or {})
                self._append(ents, status=LEDGER_OPENED, result=opened)
            elif ents[0]["result"].get("root") != str(self.root):
                raise ChainBroken(f"{self.path}: this ledger was opened for root {ents[0]['result'].get('root')!r}, not {str(self.root)!r}; "
                                  f"a copied or moved ledger is refused")
            elif ents[0]["result"].get("resultSteps") != sorted(self.result_steps):
                raise LedgerRefusal(f"{self.path}: this ledger declared result steps {ents[0]['result'].get('resultSteps')}, not "
                                    f"{sorted(self.result_steps)}; result steps are fixed when the ledger is opened")

    @classmethod
    def for_brain(cls, brain: str, protocol_id: str, protocol_sha256: str, repo=".", forbid_under: Iterable = (), *,
                  result_steps: frozenset, cortex_home=None, pack: str = CORTEX_PACK, **kwargs) -> "Ledger":
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
        return cls(resolved, protocol_id, protocol_sha256, forbid_under, result_steps=result_steps, repo=Path(repo).resolve(), **kwargs,
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
                                    f"{self.protocol_sha256}; a changed protocol needs a new protocol id, after human review on #51")
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

    def _fetch(self) -> list:
        raw = self._gh(f"repos/{self.anchor_repo}/issues/{self.anchor_issue}/comments?per_page=100")
        return [c for c in _json_arrays(raw) if isinstance(c, dict) and c.get("created_at")]

    @staticmethod
    def _body_sha(c) -> str:
        return sha256_bytes((c.get("body") or "").encode("utf-8"))

    @staticmethod
    def _edited_after_grace(c) -> bool:
        u = c.get("updated_at")
        return u is not None and (_parse_time(u) - _parse_time(c["created_at"])).total_seconds() > EDIT_GRACE_SECONDS

    @staticmethod
    def _tokens(body: str) -> set:
        return {t.strip(_PUNCT) for t in (body or "").split()}

    @staticmethod
    def _recorded_refs(ents) -> dict:
        """{comment id: recorded body sha256 (None for refs recorded without one)} for every comment the ledger recorded."""
        refs = {}
        for e in ents:
            ext = e["external"] or {}
            for r in [ext.get("anchor"), ext.get("start"), ext.get("result")] + list(ext.get("starts") or []):
                if r and r.get("id") is not None:
                    refs[r["id"]] = r.get("body_sha256") or refs.get(r["id"])
        return refs

    def _screen(self, ents, comments) -> list:
        """Refuse edited records (edit history is not readable over REST, so an edit is treated as a possible edit-away): a recorded
        comment whose body sha256 differs from the recorded one, and an unrecorded comment naming this protocol id as an exact token whose
        ``updated_at`` is more than EDIT_GRACE_SECONDS after ``created_at``. The blast radius is this protocol only."""
        recorded = self._recorded_refs(ents)
        for c in comments:
            cid = c.get("id")
            why = None
            if cid in recorded and recorded[cid] is not None:
                if self._body_sha(c) != recorded[cid]:
                    why = "its body differs from the body recorded in this ledger"
            elif self._edited_after_grace(c) and (cid in recorded or self.protocol_id in self._tokens(c.get("body"))):
                why = "it is recorded in this ledger" if cid in recorded else f"it names {self.protocol_id}"
            if why:
                raise LedgerRefusal(f"comment {cid} on {self.anchor_repo}#{self.anchor_issue} was edited (created {c['created_at']}, "
                                    f"updated {c.get('updated_at')}) and {why}; edited records are refused for {self.protocol_id}")
        return comments

    def _comments(self, ents) -> list:
        return self._screen(ents, self._fetch())

    def _matching(self, comments, prefix, tokens, nhash: int = 1) -> list:
        """Comments whose first line is ``<prefix> <tokens...> <nhash values>``, earliest first: (time, id, value(s), comment)."""
        n = len(prefix.split())
        hits = []
        for c in comments:
            first = (c.get("body") or "").lstrip().split("\n", 1)[0].split()
            if len(first) == n + len(tokens) + nhash and " ".join(first[:n]) == prefix and first[n:n + len(tokens)] == list(tokens):
                vals = [v.lower() if _HEX.match(v.lower()) else v for v in first[n + len(tokens):]]
                hits.append((_parse_time(c["created_at"]), c.get("id") or 0, vals[0] if nhash == 1 else vals, c))
        return sorted(hits, key=lambda t: (t[0], t[1]))

    @staticmethod
    def _ref(c) -> dict:
        return {"id": c.get("id"), "url": c.get("html_url"), "created_at": c.get("created_at"),
                "body_sha256": sha256_bytes((c.get("body") or "").encode("utf-8"))}

    @staticmethod
    def _anchor_lines(comments) -> list:
        """Every ``Run anchor:`` comment, any protocol: (time, id, tokens after the prefix, comment), earliest first."""
        out = []
        for c in comments:
            first = (c.get("body") or "").lstrip().split("\n", 1)[0].split()
            if first[:2] == ANCHOR_PREFIX.split() and len(first) > 2:
                out.append((_parse_time(c["created_at"]), c.get("id") or 0, first[2:], c))
        return sorted(out, key=lambda t: (t[0], t[1]))

    def _check_anchor(self, ents, comments, start_utc: str | None) -> dict:
        a = self._anchor_of(ents)
        lines = self._anchor_lines(comments)
        hits = [t for t in lines if t[2][0] == self.protocol_id]
        if not hits:
            raise LedgerRefusal(f"no `{ANCHOR_PREFIX} {self.protocol_id}` comment on {self.anchor_repo}#{self.anchor_issue}; post "
                                f"post_anchor_text() there before any step")
        created, cid, toks, c = hits[0]
        posted = toks[1].lower() if len(toks) > 1 else None
        if posted != a:
            raise LedgerRefusal(f"the earliest anchor for {self.protocol_id} on {self.anchor_repo}#{self.anchor_issue} is {posted} "
                                f"(comment {c.get('id')}), not this ledger's {a}; this ledger is not the protocol's run ledger (a later "
                                f"anchor is not accepted while the earliest one exists; recovery is a new protocol id, after human review on #51)")
        declared = self._steps_csv(ents[0]["result"].get("resultSteps") or [])
        steps = toks[2] if len(toks) == 4 else None
        if steps != declared:
            raise LedgerRefusal(f"the earliest anchor for {self.protocol_id} (comment {c.get('id')}) declares result steps {steps!r}, but this "
                                f"ledger's genesis declares {declared!r}; refused")
        psha = toks[3].lower() if len(toks) == 4 else None
        if psha != self.protocol_sha256:
            raise LedgerRefusal(f"the earliest anchor for {self.protocol_id} (comment {c.get('id')}) carries protocol sha256 {psha!r}, not "
                                f"{self.protocol_sha256}; refused")
        for t in lines:
            if (t[0], t[1]) >= (created, cid):
                break
            if len(t[2]) == 4 and t[2][3].lower() == self.protocol_sha256 and t[2][0] != self.protocol_id:
                raise LedgerRefusal(f"protocol sha256 {self.protocol_sha256} was anchored earlier under protocol id {t[2][0]!r} (comment "
                                    f"{t[3].get('id')}); the identical protocol cannot be re-run under a new id. A genuinely new version "
                                    f"has a new sha256; otherwise recovery is a new protocol id, after human review on #51")
        starts = [e["utc"] for e in ents if e["status"] == STARTED]
        bound = starts[0] if starts else start_utc
        if bound is not None and not created < _parse_time(bound):
            raise LedgerRefusal(f"anchor comment {c.get('id')} was created at {c['created_at']}, not before the ledger's first start "
                                f"({bound}); the anchor must be posted before any step runs")
        return {"anchor": a, "comment_id": c.get("id"), "created_at": c["created_at"], "url": c.get("html_url"),
                "body_sha256": self._body_sha(c)}

    @staticmethod
    def _steps_csv(steps) -> str:
        return ",".join(sorted(steps)) or "-"

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
        """The comment to post on Sector_Ops #51 before any step; first line
        ``Run anchor: <protocol_id> <anchor> <result steps> <protocol_sha256>``."""
        with self._locked():
            ents = self._load()
        a, g = self._anchor_of(ents), ents[0]
        return (f"{ANCHOR_PREFIX} {self.protocol_id} {a} {self._steps_csv(g['result'].get('resultSteps') or [])} "
                f"{self.protocol_sha256}\n\n"
                f"- protocol sha256: `{self.protocol_sha256}`\n"
                f"- ledger: `{LEDGER_DIR}/{self.protocol_id}.jsonl` under the research root `{g['result'].get('root')}`\n"
                f"- host: `{g['host']}`; genesis UTC: `{g['utc']}`; resolved by: `{g['result'].get('resolvedBy')}`\n\n"
                f"The earliest `{ANCHOR_PREFIX}` comment for this protocol id is the binding record; a later one is not accepted while it exists. "
                f"Do not edit or delete this comment.\n")

    def require_external_anchor(self, repo: str | None = None, issue: int | None = None) -> dict:
        """Refuse unless the earliest ``Run anchor:`` comment for this protocol id on ``repo``#``issue`` (default Sector_Ops #51) carries
        this ledger's anchor, result steps and protocol sha256 (not anchored earlier under another id), is unedited and predates the ledger's first STARTED entry. A gh failure refuses."""
        if repo is not None:
            self.anchor_repo = repo
        if issue is not None:
            self.anchor_issue = int(issue)
        with self._locked():
            ents = self._load()
            return self._check_anchor(ents, self._comments(ents), _now())

    def start_text(self, step: str, key: str) -> str:
        """The comment to post on #51 right after ``begin`` of a result-producing step; first line
        ``Run start: <protocol_id> <step> <key> <started_entry_sha256>``."""
        with self._locked():
            ents = self._load()
            st = self._my_started(ents, step, key, "start_text")
        return (f"{START_PREFIX} {self.protocol_id} {step} {key} {self._entry_sha(st)}\n\n"
                f"- attempt {st['run']} started `{st['utc']}` on `{st['host']}`; ledger anchor `{self._anchor_of(ents)}`\n\n"
                f"Only one start hash may exist for this protocol, step and key; another hash marks a repeat. "
                f"Do not edit or delete this comment.\n")

    def _starts(self, comments, step, key) -> list:
        return self._matching(comments, START_PREFIX, [self.protocol_id, step, key])

    def confirm_started(self, step: str, key: str) -> dict:
        """Call right after posting ``start_text``. ``Run start:`` comments for (protocol, step, key) are counted by distinct hash; the only
        hash present must be this attempt's STARTED hash. None listed yet: wait and retry, do NOT repost. Another hash is REPEAT: a
        REPEAT_DETECTED entry is written and RepeatDetected raised. The recorded ref is the earliest comment carrying this hash."""
        with self._locked():
            ents = self._load()
            st = self._my_started(ents, step, key, "confirm_started")
            mine = self._of(ents, step, key)
            if any(e["status"] == START_CONFIRMED and e["run"] == st["run"] for e in mine):
                raise LedgerRefusal(f"{step}/{key} run {st['run']} is already confirmed")
            comments = self._comments(ents)
            anchor = self._check_anchor(ents, comments, None)
            hits = self._starts(comments, step, key)
            h = self._entry_sha(st)
            if not hits:
                raise LedgerRefusal(f"`{START_PREFIX} {self.protocol_id} {step} {key}` on {self.anchor_repo}#{self.anchor_issue}: "
                                    f"not listed yet: wait and retry confirm_started(); do NOT repost")
            distinct = sorted({t[2] for t in hits})
            if distinct != [h]:
                ext = {"anchor": self._ref_from(anchor), "starts": [self._ref(t[3]) | {"sha": t[2]} for t in hits]}
                self._append(ents, step=step, key=key, status=REPEAT_DETECTED, run=st["run"], external=ext,
                             reason=f"{len(distinct)} distinct Run start hash(es) {distinct}; this attempt {h}")
                raise RepeatDetected(f"REPEAT: {self.protocol_id} {step}/{key} has {len(distinct)} distinct `{START_PREFIX}` hash(es) and "
                                     f"{'one is' if h in distinct else 'none is'} this attempt's {h}; the step was started more than once (a "
                                     f"re-run, a new folder or a restored snapshot). Refused; any result of this step does not count")
            ext = {"anchor": self._ref_from(anchor), "start": self._ref(hits[0][3])}
            return dict(self._append(ents, step=step, key=key, status=START_CONFIRMED, run=st["run"], external=ext))

    @staticmethod
    def _ref_from(anchor: dict) -> dict:
        return {"id": anchor["comment_id"], "url": anchor["url"], "created_at": anchor["created_at"], "sha": anchor["anchor"],
                "body_sha256": anchor["body_sha256"]}

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
                                f"terminal, and recovery is a new protocol id, after human review on #51")
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

    def _completed(self, ents, step, key):
        return next((e for e in self._of(ents, step, key) if e["status"] == COMPLETED), None)

    def first(self, step: str, key: str):
        """The COMPLETED entry of a result step (step, key) if it counts, else None."""
        with self._locked():
            e = self._completed(self._load(), step, key)
        return dict(e) if e is not None and step in self.result_steps and e["counted"] is True else None

    def require(self, step: str, key: str) -> dict:
        """The counted COMPLETED entry of a result step (step, key); refuses otherwise."""
        if step not in self.result_steps:
            raise LedgerRefusal(f"{self.protocol_id}: {step!r} is not a declared result step")
        with self._locked():
            e = self._completed(self._load(), step, key)
        if e is None:
            raise LedgerRefusal(f"{self.protocol_id}: step {step!r} key {key!r} has no COMPLETED run; it must run first")
        if e["counted"] is not True:
            raise LedgerRefusal(f"{self.protocol_id}: step {step!r} key {key!r} completed as a REPEAT and does not count")
        return dict(e)

    def counts(self, step: str, key: str, run: int | None = None) -> bool:
        """True only for the counted COMPLETED run of a result step. With ``run``, only when that run is it."""
        e = self.first(step, key)
        return e is not None and (run is None or e["run"] == run)

    def result_text(self, step: str, key: str) -> str:
        """The comment to post on #51 after ``complete()`` of a result step; first line
        ``Run result: <protocol_id> <step> <key> <completed_entry_sha256> <result_sha256>``."""
        self._check(step, key)
        with self._locked():
            e = self._completed(self._load(), step, key)
        if e is None or step not in self.result_steps:
            raise LedgerRefusal(f"result_text: {step}/{key} has no COMPLETED result step")
        rs = sha256_bytes(_canon(e["result"]).encode("ascii"))
        return (f"{RESULT_PREFIX} {self.protocol_id} {step} {key} {self._entry_sha(e)} {rs}\n\n"
                f"- run {e['run']}, counted: `{str(e['counted']).lower()}`, completed `{e['utc']}`\n\n"
                f"Lets anyone check later that the ledger's result was not rewritten. Do not edit or delete this comment.\n")

    def confirm_result(self, step: str, key: str) -> dict:
        """Call right after posting ``result_text``. Refuses unless exactly one ``Run result:`` exists for (protocol, step, key) and it
        carries the COMPLETED entry's hash and result hash (identical copies count once); records the earliest such comment's id and body
        sha256 (RESULT_CONFIRMED). None listed yet: wait and retry, do NOT repost."""
        self._check(step, key)
        with self._locked():
            ents = self._load()
            e = self._completed(ents, step, key)
            if e is None or step not in self.result_steps:
                raise LedgerRefusal(f"confirm_result: {step}/{key} has no COMPLETED result step")
            if any(x["status"] == RESULT_CONFIRMED for x in self._of(ents, step, key)):
                raise LedgerRefusal(f"confirm_result: {step}/{key} is already confirmed")
            hits = self._matching(self._comments(ents), RESULT_PREFIX, [self.protocol_id, step, key], 2)
            want = [self._entry_sha(e), sha256_bytes(_canon(e["result"]).encode("ascii"))]
            if not hits:
                raise LedgerRefusal(f"confirm_result: `{RESULT_PREFIX} {self.protocol_id} {step} {key}` not listed yet: wait and retry "
                                    f"confirm_result(); do NOT repost")
            distinct = sorted({tuple(h[2]) for h in hits})
            if distinct != [tuple(want)]:
                raise LedgerRefusal(f"confirm_result: {step}/{key} needs every `{RESULT_PREFIX}` comment to carry {want}; found "
                                    f"{[list(d) for d in distinct]}")
            return dict(self._append(ents, step=step, key=key, status=RESULT_CONFIRMED, run=e["run"],
                                     external={"result": self._ref(hits[0][3])}))

    def audit(self, check_external: bool = False) -> dict:
        """A summary for run reports: anchor, head and every result-step COMPLETED / REPEAT_DETECTED entry with its #51 comment ids. With
        ``check_external``, re-reads #51 and lists ``findings``: an edited record; a recorded comment that is missing or no longer starts
        with ``Run ``; the anchor no longer the earliest; not exactly one ``Run start:`` carrying the attempt's STARTED hash; a missing,
        repeated or mismatching ``Run result:`` (a ledger tail forged after the comment was posted shows up here). Detection only, and only
        while the comments exist."""
        with self._locked():
            ents = self._load()
        steps = []
        for e in ents:
            if e["status"] in (COMPLETED, REPEAT_DETECTED) and e["step"] in self.result_steps:
                st = next(x for x in ents if x["status"] == STARTED and x["step"] == e["step"] and x["key"] == e["key"] and x["run"] == e["run"])
                steps.append({"step": e["step"], "key": e["key"], "run": e["run"], "status": e["status"], "counted": e["counted"],
                              "external": e["external"], "started_sha256": self._entry_sha(st), "entry_sha256": self._entry_sha(e),
                              "result_sha256": sha256_bytes(_canon(e["result"]).encode("ascii")) if e["status"] == COMPLETED else None})
        out = {"protocol_id": self.protocol_id, "protocol_sha256": self.protocol_sha256, "ledger": str(self.path),
               "result_steps": sorted(self.result_steps), "anchor": self._anchor_of(ents),
               "head": {"seq": len(ents), "entry_sha256": self._entry_sha(ents[-1])}, "steps": steps,
               "issue": f"{self.anchor_repo}#{self.anchor_issue}"}
        if not check_external:
            return out
        try:
            comments = self._fetch()
        except LedgerRefusal as e:
            out["findings"] = [f"EXTERNAL_UNCHECKED: {e}"]
            return out
        findings = []
        try:
            self._screen(ents, comments)
        except LedgerRefusal as e:
            findings.append(f"EDITED: {e}")
        try:
            self._check_anchor(ents, comments, None)
        except LedgerRefusal as e:
            findings.append(f"ANCHOR: {e}")
        by_id = {c.get("id"): c for c in comments}
        for i, sha in sorted(self._recorded_refs(ents).items()):
            c = by_id.get(i)
            if c is None:
                findings.append(f"MISSING_COMMENT: recorded comment {i} no longer exists")
                continue
            if sha is not None and self._body_sha(c) != sha:
                findings.append(f"BODY_CHANGED: recorded comment {i} no longer has the recorded body")
            if not (c.get("body") or "").lstrip().startswith("Run "):
                findings.append(f"EDITED_AWAY: recorded comment {i} no longer starts with `Run `")
        for s_ in steps:
            if s_["status"] != COMPLETED:
                continue
            tag = f"{s_['step']}/{s_['key']}"
            starts = sorted({t[2] for t in self._starts(comments, s_["step"], s_["key"])})
            if len(starts) != 1:
                findings.append(f"START_COUNT: {tag} has {len(starts)} distinct `{START_PREFIX}` hashes")
            elif starts[0] != s_["started_sha256"]:
                findings.append(f"START_MISMATCH: {tag} `{START_PREFIX}` carries {starts[0]}, the ledger's STARTED is {s_['started_sha256']}")
            res = sorted({tuple(t[2]) for t in self._matching(comments, RESULT_PREFIX, [self.protocol_id, s_["step"], s_["key"]], 2)})
            if not res:
                findings.append(f"RESULT_MISSING: {tag} has no `{RESULT_PREFIX}` comment")
            elif len(res) > 1:
                findings.append(f"RESULT_COUNT: {tag} has {len(res)} distinct `{RESULT_PREFIX}` values")
            elif list(res[0]) != [s_["entry_sha256"], s_["result_sha256"]]:
                findings.append(f"RESULT_MISMATCH: {tag} `{RESULT_PREFIX}` carries {list(res[0])}, the ledger has "
                                f"{[s_['entry_sha256'], s_['result_sha256']]} (the ledger tail or the comment changed)")
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

    def begin(self, step: str, key: str, args: Mapping | None = None, inputs: Mapping | None = None) -> int:
        """Record a STARTED attempt and return its attempt number (1 for the first). Refused when (step, key) has a COMPLETED run, when an
        earlier attempt has no end (terminal: the only recovery is a new protocol id, after human review on #51), when ``inputs`` differ from inputs bound for
        (step, key), or #51 refuses: every step needs this ledger's anchor to be the protocol's earliest; a result step (one in
        ``result_steps``) then needs ``start_text`` posted and ``confirm_started`` before it computes anything; a non-result step is
        refused if #51 has a ``Run start:`` for it."""
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
                                    f"aborted; a STARTED entry with no end is terminal for this step, and recovery is a new protocol id, after human review on #51")
            bound = self._bound(mine)
            for name, h in hashes.items():
                if name in bound and bound[name] != h:
                    raise LedgerRefusal(f"{step}/{key}: input {name!r} differs from the bound input ({bound[name]} -> {h})")
            result_producing = step in self.result_steps
            comments = self._comments(ents)
            self._check_anchor(ents, comments, _now())  # every step, result or not: no values before this ledger is anchored
            if not result_producing:
                hits = self._matching(comments, START_PREFIX, [self.protocol_id, step], 2)
                if hits:
                    raise LedgerRefusal(f"{step} is not a result step, but #51 has {len(hits)} `{START_PREFIX} {self.protocol_id} {step}` "
                                        f"comment(s); refused")
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
            comments = self._comments(ents)
            hits = self._starts(comments, step, key)
            h = self._entry_sha(st)
            n = len({t[2] for t in hits})
            repeat = {t[2] for t in hits} != {h} or any(e["status"] == REPEAT_DETECTED for e in mine)
            ext = dict(conf["external"], startCommentsAtComplete=n, startSha=h)
            e = self._append(ents, step=step, key=key, status=COMPLETED, run=st["run"], outputs={**prior, **hashes}, result=result,
                             counted=not repeat, external=ext,
                             reason=(f"REPEAT: {n} distinct `{START_PREFIX}` hash(es) at completion, not only this attempt's STARTED hash; "
                                     f"this result does not count" if repeat else None))
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
