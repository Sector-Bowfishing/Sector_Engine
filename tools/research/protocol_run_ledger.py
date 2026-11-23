#!/usr/bin/env python3
"""Protocol run ledger: one append-only, hash-chained record per pre-registered research protocol. Stdlib only, no network.

Why it exists
-------------
A pre-registered protocol (RS-18) is only honest if the operator cannot run a step, look at the result and run it again. A write-once guard
that lives in the operator-chosen ``--out`` folder does not do that: a new ``--out`` gives a fresh guard. This ledger lives in the research
folder instead, keyed by the protocol id, so a re-run is refused wherever its outputs are written.

The rule
--------
1. **One ledger per protocol id, in the research folder.** The file is ``<root>/_ledgers/<protocol_id>.jsonl``. ``root`` is the folder that
   ``cortex.py research-path sector/engine <brain|shared>`` returns (pass it in, or set ``SECTOR_RESEARCH_ROOT``). It must already exist and
   must not lie inside any ``--out`` folder (``forbid_under``). The ledger is bound to the protocol document's sha256: a different hash for the
   same id is refused, so editing the protocol after a run needs a new protocol id.
2. **Only run #1 counts.** ``begin`` refuses a (step, key) that has a COMPLETED entry, or a STARTED attempt that was neither completed nor
   aborted (a crash after start is treated as a possible look at the result). A later attempt is allowed only after
   ``abort_before_result``, which is refused once any output was recorded. The first COMPLETED entry is the result
   (``first``/``counts``); there can never be a second.
3. **Inputs are bound before results.** ``bind_inputs`` records input hashes for a (step, key) before that step has a result and refuses to
   re-bind them differently; ``begin`` refuses inputs that differ from the bound ones; ``check_inputs`` refuses any file that changed. Later
   steps bind earlier results with ``require(step, key)`` and compare (for example a fit sha or a selection hash).

Entries
-------
Each line is one JSON object (sorted keys, compact): ``seq``, ``utc``, ``protocol_id``, ``protocol_sha256``, ``step``, ``key``, ``status``
(``STARTED``, ``OUTPUTS_RECORDED``, ``COMPLETED``, ``ABORTED_BEFORE_RESULT``, ``INPUTS_BOUND``), ``run``, ``args``, ``inputs`` {name: sha256},
``outputs`` {name: sha256}, ``result`` (small dict), ``reason``, ``git_commit``, ``git_dirty``, ``host`` and ``prev_entry_sha256`` (sha256 of
the previous line's bytes; 64 zeros for the first). A side file ``<protocol_id>.head.json`` records the last seq and line hash, so editing or
truncating the tail is detected too. Every write takes an exclusive ``fcntl`` lock, re-reads and verifies the chain, appends, flushes and
fsyncs.

Limits (stated, not hidden): this stops accidental and casual re-runs and makes edits detectable. It cannot stop someone who deletes the
ledger and its head together, or who points ``root`` at another folder. Runners should therefore print the ledger head
(``Ledger.head()``) into their reports and keep the ledger in the research folder's manifest and backups.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

ENV_ROOT = "SECTOR_RESEARCH_ROOT"
LEDGER_DIR = "_ledgers"
GENESIS = "0" * 64
TREE_HASH = "sha256-tree-v1"
TREE_SKIP_DIRS = {"__pycache__"}
TREE_SKIP_FILES = {".DS_Store"}
STARTED = "STARTED"
OUTPUTS_RECORDED = "OUTPUTS_RECORDED"
COMPLETED = "COMPLETED"
ABORTED = "ABORTED_BEFORE_RESULT"
INPUTS_BOUND = "INPUTS_BOUND"
STATUSES = (STARTED, OUTPUTS_RECORDED, COMPLETED, ABORTED, INPUTS_BOUND)
RESULT_MAX_BYTES = 8192
FIELDS = ("seq", "utc", "protocol_id", "protocol_sha256", "step", "key", "status", "run", "args", "inputs", "outputs", "result", "reason",
          "git_commit", "git_dirty", "host", "prev_entry_sha256")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_REPO = Path(__file__).resolve().parents[2]


class LedgerRefusal(Exception):
    """The ledger refused an operation. Runners stop; they never catch this to carry on."""


class ChainBroken(LedgerRefusal):
    """The ledger file was edited, truncated or reordered, or does not belong to this protocol."""


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


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


class Ledger:
    """The run ledger of one pre-registered protocol. See the module docstring for the rule."""

    def __init__(self, root, protocol_id: str, protocol_sha256: str, forbid_under: Iterable = (), *, repo=None):
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
        self.dir.mkdir(exist_ok=True)
        with self._locked():
            self._load()  # refuses a broken chain or another protocol hash now, before any work starts

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
        prev = GENESIS
        if entries:
            prev = sha256_bytes(_canon(entries[-1]).encode("ascii"))
        e = {"seq": len(entries) + 1,
             "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
             "protocol_id": self.protocol_id, "protocol_sha256": self.protocol_sha256,
             "step": None, "key": None, "status": None, "run": None, "args": {}, "inputs": {}, "outputs": {}, "result": None,
             "reason": None, "git_commit": self._git[0], "git_dirty": self._git[1], "host": socket.gethostname(),
             "prev_entry_sha256": prev}
        e.update(fields)
        line = _canon(e).encode("ascii")
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        self._write_head(e["seq"], sha256_bytes(line))
        entries.append(e)
        return e

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
            if not isinstance(v, str) or not v:
                raise LedgerRefusal(f"{n} must be a non-empty string")

    def entries(self) -> list:
        with self._locked():
            return [dict(e) for e in self._load()]

    def verify_chain(self) -> int:
        """Verify the whole chain and the head; returns the number of entries. Raises ChainBroken on any break or edit, LedgerRefusal on a
        protocol hash mismatch."""
        with self._locked():
            return len(self._load(repair_head=False))

    def head(self) -> dict:
        """{protocol_id, protocol_sha256, seq, entry_sha256}: print this into run reports so a later reader can check the ledger."""
        with self._locked():
            ents = self._load()
            sha = sha256_bytes(_canon(ents[-1]).encode("ascii")) if ents else GENESIS
            return {"protocol_id": self.protocol_id, "protocol_sha256": self.protocol_sha256, "seq": len(ents), "entry_sha256": sha}

    def first(self, step: str, key: str):
        """The first COMPLETED entry for (step, key), or None."""
        with self._locked():
            done = [e for e in self._of(self._load(), step, key) if e["status"] == COMPLETED]
        return dict(done[0]) if done else None

    def require(self, step: str, key: str) -> dict:
        """The first COMPLETED entry for (step, key); refuses if the step has no result yet."""
        e = self.first(step, key)
        if e is None:
            raise LedgerRefusal(f"{self.protocol_id}: step {step!r} key {key!r} has no COMPLETED run; it must run first")
        return e

    def counts(self, step: str, key: str, run: int | None = None) -> bool:
        """True only for the first COMPLETED run of (step, key). With ``run``, True only when that run is it."""
        e = self.first(step, key)
        return e is not None and (run is None or e["run"] == run)

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
        earlier attempt is still open (started, never completed or aborted), or when ``inputs`` differ from inputs bound for (step, key)."""
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
                                    f"ledger {self.path}); only that run counts and it is never repeated")
            open_ = self._open_attempt(mine)
            if open_ is not None:
                raise LedgerRefusal(f"{self.protocol_id}: {step}/{key} run {open_['run']} STARTED at {open_['utc']} and never completed or "
                                    f"aborted; if no result was produced or seen, call abort_before_result first")
            bound = self._bound(mine)
            for name, h in hashes.items():
                if name in bound and bound[name] != h:
                    raise LedgerRefusal(f"{step}/{key}: input {name!r} differs from the bound input ({bound[name]} -> {h})")
            run = 1 + sum(1 for e in mine if e["status"] == STARTED)
            self._append(ents, step=step, key=key, status=STARTED, run=run, args=args, inputs=hashes)
        return run

    def _require_open(self, ents, step, key, what):
        self._check(step, key)
        open_ = self._open_attempt(self._of(ents, step, key))
        if open_ is None:
            raise LedgerRefusal(f"{what}: {step}/{key} has no open attempt (call begin first)")
        return open_

    @staticmethod
    def _recorded_outputs(mine, run) -> dict:
        out = {}
        for e in mine:
            if e["run"] == run and e["status"] in (OUTPUTS_RECORDED, COMPLETED):
                out.update(e["outputs"])
        return out

    def record_outputs(self, step: str, key: str, outputs: Mapping) -> dict:
        """Record outputs of the open attempt as soon as they are written, before the result summary exists. After this the attempt can
        no longer be aborted. Returns {name: sha256}."""
        hashes = _hashes("outputs", outputs)
        if not hashes:
            raise LedgerRefusal("record_outputs: no outputs")
        with self._locked():
            ents = self._load()
            open_ = self._require_open(ents, step, key, "record_outputs")
            prior = self._recorded_outputs(self._of(ents, step, key), open_["run"])
            for n, h in hashes.items():
                if n in prior and prior[n] != h:
                    raise LedgerRefusal(f"{step}/{key}: output {n!r} was recorded as {prior[n]}, now {h}")
            self._append(ents, step=step, key=key, status=OUTPUTS_RECORDED, run=open_["run"], outputs=hashes)
        return hashes

    def complete(self, step: str, key: str, outputs: Mapping | None = None, result: Mapping | None = None) -> dict:
        """Close the open attempt as COMPLETED with its outputs and a small result summary. Returns the entry."""
        hashes = _hashes("outputs", outputs)
        result = dict(result or {})
        if len(_canon(result)) > RESULT_MAX_BYTES:
            raise LedgerRefusal(f"result summary is larger than {RESULT_MAX_BYTES} bytes; record a file hash in outputs instead")
        with self._locked():
            ents = self._load()
            open_ = self._require_open(ents, step, key, "complete")
            prior = self._recorded_outputs(self._of(ents, step, key), open_["run"])
            for n, h in hashes.items():
                if n in prior and prior[n] != h:
                    raise LedgerRefusal(f"{step}/{key}: output {n!r} was recorded as {prior[n]}, now {h}")
            e = self._append(ents, step=step, key=key, status=COMPLETED, run=open_["run"], outputs={**prior, **hashes}, result=result)
        return dict(e)

    def abort_before_result(self, step: str, key: str, reason: str) -> dict:
        """Close the open attempt without a result, so a later attempt may begin. Refused once any output was recorded."""
        if not isinstance(reason, str) or not reason.strip():
            raise LedgerRefusal("abort_before_result needs a reason")
        with self._locked():
            ents = self._load()
            open_ = self._require_open(ents, step, key, "abort_before_result")
            if self._recorded_outputs(self._of(ents, step, key), open_["run"]):
                raise LedgerRefusal(f"{step}/{key} run {open_['run']} already recorded outputs; it cannot be aborted before a result")
            e = self._append(ents, step=step, key=key, status=ABORTED, run=open_["run"], reason=reason.strip())
        return dict(e)
