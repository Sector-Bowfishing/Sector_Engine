"""Run binding for protocol WSW-2026-11-23-R4: one global, append-only run ledger per protocol id. PRIVATE to
wind_strong_wind.py and temporary: it is replaced by the shared tools/research/protocol_run_ledger.py (separate PR) once
that merges.

The runner keeps its one-shot guards here instead of in an output folder, so a second output folder cannot re-run a step
and pick the better result. Standard library only.

    ledger = RunLedger(binding_folder, protocol_id, protocol_sha256)
    with ledger.step("rows", "pw", inputs={...}) as run:      # refused if an earlier attempt was not ABORTED_NO_RESULT
        ...                                                    # an exception here -> ABORTED_NO_RESULT
        run.writing()                                          # from now on an exception -> FAILED
        ... write outputs ...
        run.outputs = {"rows.jsonl": sha}                      # -> COMPLETED
    ledger.completed("rows", "pw")                             # the COMPLETED end line of run #1, or None

Ledger file: <binding_folder>/ledger.jsonl. Each line is one JSON object with `seq`, `at` (UTC), `kind` (START, END,
LOG, REFUSED), `step`, `window` and `prev` = sha256 of the previous line's bytes (the first line chains to
sha256("genesis:<protocolId>:<protocolSha256>")); ledger.head.json holds the line count and the last line's sha256. A
broken chain, a head that does not match, a line from another protocol, or a clock earlier than the newest line makes
every later call refuse. Writes take an exclusive lock and are flushed and fsynced. Limit: someone who rewrites the
whole file and its head consistently is not detected locally; the Sector_Ops #51 posts are the public record.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os

try:
    import fcntl
except ImportError:          # pragma: no cover (non-POSIX)
    fcntl = None

UTC = dt.timezone.utc
EXCLUDED_NAMES = {"__pycache__", ".DS_Store"}
STATUSES = ("COMPLETED", "ABORTED_NO_RESULT", "FAILED")


class LedgerRefused(Exception):
    """A binding rule refused the call."""


# ---------------------------------------------------------------------------------------------------------------- hashing
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(root: str) -> dict:
    """sha256-tree-v1 (Cortex RS-02): sha256 of the sorted lines '<sha256>  <relpath>\\n' over every file under root,
    excluding __pycache__/, .DS_Store and *.tmp. A missing root hashes as an empty tree with exists=False."""
    lines = []
    if os.path.isdir(root):
        for dp, dns, fns in os.walk(root):
            dns[:] = sorted(d for d in dns if d not in EXCLUDED_NAMES)
            for f in fns:
                if f in EXCLUDED_NAMES or f.endswith(".tmp"):
                    continue
                full = os.path.join(dp, f)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                lines.append(f"{sha256_file(full)}  {rel}\n")
    lines.sort()
    return {"hashMethod": "sha256-tree-v1", "collectionSha256": sha256_bytes("".join(lines).encode()), "files": len(lines),
            "exists": os.path.isdir(root)}


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def atomic_write_json(path: str, obj) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    body = json.dumps(obj, indent=1, sort_keys=True).encode()
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "wb") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return sha256_bytes(body)


def write_once_json(path: str, obj) -> str:
    """Write obj once. If the file exists it must hold exactly the same content (canonical JSON), else refuse."""
    if os.path.exists(path):
        have = json.load(open(path))
        if canonical(have) != canonical(obj):
            raise LedgerRefused(f"{os.path.basename(path)} is already recorded with different content; inputs changed")
        return sha256_file(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    body = json.dumps(obj, indent=1, sort_keys=True).encode()
    with open(path, "xb") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    return sha256_bytes(body)


# ----------------------------------------------------------------------------------------------------------------- ledger
class _Run:
    def __init__(self, ledger, step, window, seq, run_number, start_hash):
        self.ledger, self.step, self.window, self.seq, self.run_number = ledger, step, window, seq, run_number
        self.start_hash = start_hash
        self.outputs: dict = {}
        self.result: dict = {}
        self._writing = False
        self.end_line_hash = None

    def writing(self) -> None:
        """Call just before the first output byte is written: an error after this is FAILED, not ABORTED_NO_RESULT."""
        self._writing = True


class RunLedger:
    def __init__(self, folder: str, protocol_id: str, protocol_sha256: str, clock=None):
        self.folder, self.protocol_id, self.protocol_sha256 = folder, protocol_id, protocol_sha256
        self.path = os.path.join(folder, "ledger.jsonl")
        self.head_path = os.path.join(folder, "ledger.head.json")
        self.clock = clock or (lambda: dt.datetime.now(UTC))
        os.makedirs(folder, exist_ok=True)

    # -- reading
    def _genesis(self) -> str:
        return sha256_bytes(f"genesis:{self.protocol_id}:{self.protocol_sha256}".encode())

    def entries(self) -> list[dict]:
        """All lines, with the hash chain and protocol identity verified."""
        if not os.path.exists(self.path):
            return []
        out, prev = [], self._genesis()
        with open(self.path, "rb") as fh:
            for n, raw in enumerate(fh.read().split(b"\n")):
                if not raw:
                    continue
                e = json.loads(raw)
                if e.get("prev") != prev or e.get("protocolId") != self.protocol_id or e.get("seq") != len(out) + 1:
                    raise LedgerRefused(f"run ledger chain broken at line {n + 1}; the ledger was edited or belongs to another protocol")
                e["_hash"] = sha256_bytes(raw)
                out.append(e)
                prev = e["_hash"]
        head = json.load(open(self.head_path)) if os.path.exists(self.head_path) else None
        if (head or {}).get("lines", 0) != len(out) or (out and head.get("lastLineSha256") != out[-1]["_hash"]):
            raise LedgerRefused("run ledger head does not match its last line; the ledger was truncated or edited")
        return out

    def attempts(self, step: str, window: str) -> list[dict]:
        """START lines of a step/window with their final status (STARTED if no END line)."""
        es = self.entries()
        ends = {e["startSeq"]: e for e in es if e["kind"] == "END"}
        out = []
        for e in es:
            if e["kind"] == "START" and e["step"] == step and e["window"] == window:
                end = ends.get(e["seq"])
                out.append({**e, "status": end["status"] if end else "STARTED", "end": end})
        return out

    def completed(self, step: str, window: str) -> dict | None:
        for a in self.attempts(step, window):
            if a["status"] == "COMPLETED":
                return a["end"]
        return None

    # -- writing
    @contextlib.contextmanager
    def _locked(self):
        fh = open(os.path.join(self.folder, ".ledger.lock"), "a")
        try:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_EX)
            yield
        finally:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_UN)
            fh.close()

    def _append(self, obj: dict) -> dict:
        es = self.entries()
        now = self.clock()
        if es and now < dt.datetime.strptime(es[-1]["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC):
            raise LedgerRefused(f"system clock {now:%Y-%m-%dT%H:%M:%SZ} is earlier than the newest ledger line {es[-1]['at']}")
        line = {"seq": len(es) + 1, "at": f"{now:%Y-%m-%dT%H:%M:%SZ}", "protocolId": self.protocol_id,
                "prev": es[-1]["_hash"] if es else self._genesis(), **obj}
        raw = json.dumps(line, sort_keys=True, separators=(",", ":")).encode()
        with open(self.path, "ab") as fh:
            fh.write(raw + b"\n")
            fh.flush()
            os.fsync(fh.fileno())
        line["_hash"] = sha256_bytes(raw)
        atomic_write_json(self.head_path, {"protocolId": self.protocol_id, "lines": line["seq"], "lastLineSha256": line["_hash"]})
        return line

    def log(self, step: str, window: str, status: str, detail: dict | None = None) -> dict:
        """A non-one-shot record (fetch runs, refusals)."""
        with self._locked():
            return self._append({"kind": "REFUSED" if status == "REFUSED" else "LOG", "step": step, "window": window,
                                 "status": status, "detail": detail or {}})

    def refuse(self, step: str, window: str, reason: str):
        """Record the refusal (best effort) and raise."""
        try:
            self.log(step, window, "REFUSED", {"reason": reason})
        except LedgerRefused:
            pass
        raise LedgerRefused(reason)

    @contextlib.contextmanager
    def step(self, step: str, window: str, inputs: dict, one_shot: bool = True):
        with self._locked():
            prior = self.attempts(step, window)
            blocking = [a for a in prior if a["status"] != "ABORTED_NO_RESULT"]
            if one_shot and blocking:
                reason = (f"{step} for {window} already has run #{prior.index(blocking[0]) + 1} ({blocking[0]['status']}); "
                          "only the first run counts")
                self._append({"kind": "REFUSED", "step": step, "window": window, "status": "REFUSED", "detail": {"reason": reason}})
                raise LedgerRefused(reason)
            start = self._append({"kind": "START", "step": step, "window": window, "inputs": inputs, "runNumber": len(prior) + 1})
        run = _Run(self, step, window, start["seq"], start["runNumber"], start["_hash"])
        try:
            yield run
        except BaseException as e:
            status = "FAILED" if run._writing else "ABORTED_NO_RESULT"
            with self._locked():
                self._append({"kind": "END", "step": step, "window": window, "startSeq": start["seq"], "status": status,
                              "error": f"{type(e).__name__}: {e}"[:300]})
            raise
        with self._locked():
            end = self._append({"kind": "END", "step": step, "window": window, "startSeq": start["seq"], "status": "COMPLETED",
                                "outputs": run.outputs, "result": run.result})
        run.end_line_hash = end["_hash"]
