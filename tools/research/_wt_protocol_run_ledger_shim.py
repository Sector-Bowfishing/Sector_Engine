"""Minimal vendored shim of the shared run ledger (tools/research/protocol_run_ledger.py, branch
research/protocol-run-ledger-2026-11-23), used by the Water Temp protected-truth runner only until that module is on main.
Same API: Ledger(root, protocol_id, protocol_sha256) with begin / complete / abort_before_result / first / require /
bind_inputs / check_inputs / verify_chain, plus sha256_file and sha256_tree. Delete this file once the shared module merges.

The ledger is one append-only JSON-lines file per protocol id at <root>/_ledgers/<protocol_id>.jsonl. Every entry carries the
sha256 of the previous entry, so an edit or a deleted line breaks verify_chain(). Only run #1 of a (step, key) counts: begin()
refuses a second run unless every earlier run was aborted before it produced a result.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

GENESIS = "0" * 64


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(root: str) -> str:
    """sha256-tree-v1: sha256 of the sorted lines '<sha256>  <relpath>\\n' (POSIX relpaths; __pycache__ and .DS_Store skipped)."""
    lines = []
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for f in sorted(files):
            if f == ".DS_Store":
                continue
            p = os.path.join(d, f)
            lines.append(f"{sha256_file(p)}  {os.path.relpath(p, root).replace(os.sep, '/')}\n")
    return hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


class LedgerError(SystemExit):
    pass


class Ledger:
    def __init__(self, root: str, protocol_id: str, protocol_sha256: str):
        if not root:
            raise LedgerError("REFUSED: no research root for the run ledger")
        self.root = os.path.abspath(root)
        self.protocol_id = protocol_id
        self.protocol_sha256 = protocol_sha256
        self.path = os.path.join(self.root, "_ledgers", f"{protocol_id}.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.verify_chain()

    # ---------------------------------------------------------------------------------------------------- storage
    def _entries(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    @staticmethod
    def _digest(entry: dict) -> str:
        body = {k: v for k, v in entry.items() if k != "hash"}
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def verify_chain(self) -> int:
        prev = GENESIS
        entries = self._entries()
        for i, e in enumerate(entries):
            if e.get("prev") != prev or e.get("hash") != self._digest(e) or e.get("seq") != i:
                raise LedgerError(f"REFUSED: run ledger {os.path.basename(self.path)} is broken at entry {i}")
            if e.get("protocolId") != self.protocol_id or e.get("protocolSha256") != self.protocol_sha256:
                raise LedgerError(f"REFUSED: run ledger entry {i} belongs to a different protocol")
            prev = e["hash"]
        return len(entries)

    def _append(self, **fields) -> dict:
        entries = self._entries()
        e = {"seq": len(entries), "prev": entries[-1]["hash"] if entries else GENESIS, "protocolId": self.protocol_id,
             "protocolSha256": self.protocol_sha256, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **fields}
        e["hash"] = self._digest(e)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return e

    def _runs(self, step: str, key: str) -> list[dict]:
        runs = {}
        for e in self._entries():
            if e.get("step") == step and e.get("key") == key:
                r = runs.setdefault(e["run"], {"run": e["run"]})
                r[e["event"]] = e
        return [runs[k] for k in sorted(runs)]

    # ---------------------------------------------------------------------------------------------------- API
    def begin(self, step: str, key: str, args: dict | None = None, inputs: dict | None = None) -> int:
        self.verify_chain()
        runs = self._runs(step, key)
        for r in runs:
            if "abort" not in r:
                raise LedgerError(f"REFUSED: {step} for {key} already ran (run #{r['run']}); only run #1 counts")
        n = len(runs) + 1
        self._append(step=step, key=key, run=n, event="begin", args=args or {}, inputs=inputs or {})
        return n

    def _open_run(self, step: str, key: str) -> dict:
        runs = self._runs(step, key)
        if not runs or "begin" not in runs[-1] or "complete" in runs[-1] or "abort" in runs[-1]:
            raise LedgerError(f"REFUSED: no open run for {step} {key}")
        return runs[-1]

    def complete(self, step: str, key: str, outputs: dict | None = None, result: dict | None = None) -> None:
        r = self._open_run(step, key)
        self._append(step=step, key=key, run=r["run"], event="complete", outputs=outputs or {}, result=result or {})

    def abort_before_result(self, step: str, key: str, reason: str) -> None:
        r = self._open_run(step, key)
        self._append(step=step, key=key, run=r["run"], event="abort", reason=reason)

    def first(self, step: str, key: str) -> dict | None:
        """The completed counting run of (step, key), or None."""
        for r in self._runs(step, key):
            if "complete" in r:
                return {"run": r["run"], **r["begin"], "outputs": r["complete"].get("outputs", {}), "result": r["complete"].get("result", {}),
                        "bound": r.get("bind", {}).get("files", {})}
        return None

    def require(self, step: str, key: str) -> dict:
        f = self.first(step, key)
        if f is None:
            raise LedgerError(f"REFUSED: {step} for {key} is not recorded as complete in the run ledger")
        return f

    def bind_inputs(self, step: str, key: str, files: dict) -> dict:
        """Record {name: path} as {name: sha256} for the open run of (step, key)."""
        r = self._open_run(step, key)
        hashes = {name: sha256_file(path) for name, path in sorted(files.items())}
        self._append(step=step, key=key, run=r["run"], event="bind", files=hashes)
        return hashes

    def check_inputs(self, step: str, key: str, files: dict) -> dict:
        """Refuse unless {name: path} equals, name for name and hash for hash, what the completed run of (step, key) bound."""
        bound = self.require(step, key)["bound"]
        if set(files) != set(bound):
            raise LedgerError(f"REFUSED: the files differ from those {step} recorded "
                              f"(missing {sorted(set(bound) - set(files))[:3]}, extra {sorted(set(files) - set(bound))[:3]})")
        for name, path in files.items():
            if sha256_file(path) != bound[name]:
                raise LedgerError(f"REFUSED: {name} changed after {step} recorded it")
        return bound
