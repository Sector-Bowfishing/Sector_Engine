"""Environment helpers shared by the proofs: repository access, the in-memory SHADOW Publisher rig, sealed probe artifacts, the AST write-site scanner."""
from __future__ import annotations

import ast
import datetime as dt
import itertools
import json
import os
import re
import sys
import uuid

GEN = "2026-10-12T06:30:00Z"
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache", "out", ".build", ".venv", "venv"}


def uid(n: int) -> str:
    return str(uuid.UUID(int=n, version=4))


def walk_files(root, exts=None):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if exts is None or f.endswith(tuple(exts) if isinstance(exts, (list, tuple, set)) else exts):
                yield os.path.join(dp, f)


def local_rig(default_brain: str):
    """A local, in-memory SHADOW Publisher stack: (stack, publish). publish(artifact, brain=None) goes through the real handoff (the Brain writes its own artifact;
    the Publisher only reads it). Shared by the kit and by Brain-local tests so no Brain keeps its own copy."""
    from sector_brain_platform.publisher import local_shadow_stack
    ids = itertools.count(1)
    st = local_shadow_stack(clock=lambda: dt.datetime(2026, 10, 15, 0, 0, tzinfo=dt.timezone.utc), id_factory=lambda: uid(next(ids) + 50000))

    def publish(art, brain=None):
        return st.publisher.evaluate_reference(st.writer(brain or default_brain).write(art))
    return st, publish


class Env:
    """Everything a proof needs, derived from the spec. Importing the platform / architecture tooling happens here, once."""

    def __init__(self, spec):
        self.spec = spec.validate()
        self.root = spec.repo_root
        for p in (os.path.join(self.root, "tools", "architecture"),):
            if p not in sys.path:
                sys.path.insert(0, p)
        import jsonschema_lite
        import report
        self.jsonschema_lite, self.report = jsonschema_lite, report
        self._artifact = None

    # ---- files ---------------------------------------------------------------------------------------------------------------------------
    def load(self, *parts):
        with open(os.path.join(self.root, *parts), encoding="utf-8") as fh:
            return json.load(fh)

    def read(self, *parts):
        with open(os.path.join(self.root, *parts), encoding="utf-8") as fh:
            return fh.read()

    @property
    def brain_json(self):
        return self.load("brains", self.spec.directory, "brain.json")

    @property
    def runtime(self):
        return os.path.join(self.spec.brain_dir, self.spec.runtime_dir)

    def rel(self, p):
        return os.path.relpath(p, self.root)

    # ---- artifacts -----------------------------------------------------------------------------------------------------------------------
    def artifact(self, n=1, generated_at=GEN, consumed=None, rerun=False):
        return self.spec.artifact_factory(n, generated_at, consumed, rerun)

    @property
    def registry(self):
        from sector_brain_platform.publisher import default_registry
        return default_registry()

    def bundle_specs(self):
        reg = self.registry
        return [reg.spec(s) for s in reg.bundle(self.spec.bundle_id).sections]

    def rig(self):
        return local_rig(self.spec.brain_id)

    def sealed(self, mutations, schema=None, freshness=None, lifecycle=None, brain_id=None, bundle_id=None, n=9):
        """A correctly sealed single-section bundle carrying arbitrary mutations (for rejection tests). Lineage release fields are copied from the Brain's own artifact."""
        from sector_brain_platform.publisher import default_registry, seal_bundle
        lin = self.artifact()["lineage"]
        sec = {"artifactSchema": schema or self.spec.registry_schema_id, "mutations": mutations}
        if freshness:
            sec["freshness"] = freshness
        return seal_bundle(brain_id=brain_id or self.spec.brain_id, bundle_id=bundle_id or self.spec.bundle_id, sections=[sec], lifecycle=lifecycle or self.spec.lifecycle,
                           review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at=GEN, execution_id=uid(n), code_version="kit@1",
                           input_fingerprint="sha256:" + "cd" * 32, knowledge_release=lin["knowledgeRelease"], manifest_ref=lin["manifestRef"],
                           manifest_sha256=lin["manifestSha256"], registry=default_registry())

    def bundle_id_of(self, brain_id):
        """The registered bundle id of another Brain (read from the registry, never by name)."""
        reg = self.registry
        return next(b.bundle_id for b in reg._bundles.values() if b.brain_id == brain_id)

    def other_registered_brains(self):
        """Brains (other than this one) that have a Publisher registration: picked from the registry, never by name."""
        reg = self.registry
        return sorted(b for b in reg.brains if b != self.spec.brain_id and reg.schemas_for(b))


# ---- AST: direct-write sites ------------------------------------------------------------------------------------------------------------
def write_sites(path, suffixes, write_methods=("update", "put", "patch", "post", "set", "delete")):
    """{(file basename, enclosing function, call)} for every call whose dotted name ends with one of `suffixes` (database write primitives)."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    sites = set()

    def visit(node, fn):
        for ch in ast.iter_child_nodes(node):
            f = ch.name if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            if isinstance(ch, ast.Call) and isinstance(ch.func, ast.Attribute) and ch.func.attr in write_methods:
                full = ast.unparse(ch.func)
                if full.split(".")[0] not in ("os", "json", "shutil") and any(full.endswith(s) for s in suffixes):
                    sites.add((os.path.basename(path), fn or "<module>", full))
            visit(ch, f)
    visit(tree, None)
    return sites


def imported_roots(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    return ({a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and not n.level})


def normalise_family(p: str) -> str:
    return re.sub(r"\{[a-zA-Z]+\}", "{}", p)
