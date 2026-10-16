"""Wind shadow equivalence evaluator (F-9): compare what is live with what the Publisher WOULD produce, and classify every difference.

Pure and read-only: it takes two in-memory structures (a live subtree and a plan's flat updates) and returns evidence. It never reads or writes a database.
Unknown differences are never normalised away: they are reported as UNKNOWN or SEMANTIC_MISMATCH and make the verdict negative.

Classes
  EXPECTED_MIGRATION_DIFF  explained by a declared rule (Publisher metadata, an explicit retirement, an explicit DELETE)
  SEMANTIC_MISMATCH        both sides have the value (or the target drops a key by replacing a unit) and it differs, outside volatile fields
  LEGACY_ONLY              live has it, target does not, and a legacy-table row says something else must still produce it
  TARGET_ONLY              target has it, live does not
  VOLATILE_ONLY            differs only in a field the schema's volatile contract (or the shared defaults) marks as changing every run
  UNKNOWN                  live-only content no rule or family accounts for
Output carries SHA-256 digests of the compared values, not the values, so it can be kept as certification evidence without leaking live content.
"""
from __future__ import annotations

import re

from .canonical import DEFAULT_VOLATILE, canonical_bytes, sha256_ref
from .compat import LEGACY_PATH_TABLE, row_for
from .model import PublisherMode
from .storage import MemoryObjectStore, PublishHistory

EVALUATOR = "wind-shadow-equivalence-v1"
CLASSES = ("EXPECTED_MIGRATION_DIFF", "SEMANTIC_MISMATCH", "LEGACY_ONLY", "TARGET_ONLY", "VOLATILE_ONLY", "UNKNOWN")
PUBLICATION = re.compile(r"/brains/[^/]+/publication(/|$)")


def _flatten(v, path, out):
    if isinstance(v, dict) and v:
        for k, x in v.items():
            _flatten(x, f"{path}/{k}", out)
    elif isinstance(v, list) and v:
        for i, x in enumerate(v):
            _flatten(x, f"{path}/{i}", out)
    else:
        out[path] = v
    return out


def _walk(tree, parts):
    """Yield (concrete path, node) for a pattern split into parts ({x} = every key)."""
    def rec(node, rest, acc):
        if not rest:
            yield "/" + "/".join(acc), node
            return
        if not isinstance(node, dict):
            return
        head = rest[0]
        if head.startswith("{") and head.endswith("}"):
            for k in sorted(node):
                yield from rec(node[k], rest[1:], acc + [k])
        elif head in node:
            yield from rec(node[head], rest[1:], acc + [head])
    yield from rec(tree, parts, [])


def _sha(v):
    return sha256_ref(canonical_bytes(v))


def scope_patterns(registry, brain_id, table):
    pats = set()
    for sid in registry.schemas_for(brain_id):
        sp = registry.spec(sid)
        pats |= {f.pattern for f in sp.families + sp.delete_families}
        pats |= {pr.target for pr in sp.projections}
    for r in table:
        pats |= {p for p in r.paths if len(p.strip("/").split("/")) > 1}      # a bare root such as /activity is a conceptual row (retention), never enumerated
    pats |= {f"/brains/{brain_id}", f"/health/brains/{brain_id}"}
    return pats


def evaluate_equivalence(live_tree: dict, target_updates: dict, *, registry, brain_id: str = "wind", derived_keys=(), table=LEGACY_PATH_TABLE) -> dict:
    """live_tree: nested dict (a read-only live subset; may be a sanitised fixture). target_updates: the plan's flat {rtdb key: value|None}."""
    specs = [registry.spec(s) for s in registry.schemas_for(brain_id)]
    vol_keys = set(DEFAULT_VOLATILE).union(*(sp.volatile.keys for sp in specs))
    vol_paths = [f for sp in specs for f in sp.volatile.paths]
    derived = {"/" + k for k in derived_keys}
    deletes = {"/" + k for k, v in target_updates.items() if v is None}

    fams = [f for sp in specs for f in sp.families + sp.delete_families]
    live = {}
    for pat in sorted(scope_patterns(registry, brain_id, table)):
        for p, node in _walk(live_tree, pat.strip("/").split("/")):
            owner_fams = [f for f in fams if f.pattern == pat]
            if owner_fams and not any(f.match(p) for f in owner_fams):
                continue                                                          # e.g. an /activity event that is not one of this Brain's
            _flatten(node, p, live)
    target = {}
    set_nodes = set()
    for k, v in target_updates.items():
        if v is not None:
            set_nodes.add("/" + k)
            _flatten(v, "/" + k, target)

    def volatile(path):
        return path.rsplit("/", 1)[-1] in vol_keys or any(f.match(path) for f in vol_paths) or any(path.startswith(f.pattern + "/") for f in vol_paths)

    def under(path, nodes):
        return any(path == n or path.startswith(n + "/") for n in nodes)

    diffs, match = [], 0
    for path in sorted(set(live) | set(target)):
        in_l, in_t = path in live, path in target
        if in_l and in_t:
            if canonical_bytes(live[path]) == canonical_bytes(target[path]):
                match += 1
                continue
            cls, rule = ("VOLATILE_ONLY", "volatile-contract") if volatile(path) else ("SEMANTIC_MISMATCH", "VALUE_DIFFERS")
        elif in_l:
            row = row_for(path, table)
            if volatile(path):
                cls, rule = "VOLATILE_ONLY", "volatile-contract"
            elif under(path, deletes):
                cls, rule = "EXPECTED_MIGRATION_DIFF", "EXPLICIT_DELETE"
            elif row is not None and row.compat_needed:
                cls, rule = "LEGACY_ONLY", row.id
            elif row is not None and row.mechanism == "STOP_WRITING":
                cls, rule = "EXPECTED_MIGRATION_DIFF", row.id
            elif row is not None and row.id == "activity-wind-events":
                cls, rule = "EXPECTED_MIGRATION_DIFF", "APPEND_ONLY_HISTORY"      # an artifact carries only the NEW events; old ones stay
            elif row is not None and row.classification == "WIND_DOMAIN_TRUTH" and not under(path, set_nodes):
                cls, rule = "SEMANTIC_MISMATCH", "DOMAIN_TRUTH_MISSING_IN_TARGET"
            elif under(path, set_nodes):
                cls, rule = "SEMANTIC_MISMATCH", "DROPPED_BY_UNIT_REPLACEMENT"
            else:
                cls, rule = "UNKNOWN", "NO_RULE"
        else:
            if PUBLICATION.match(path):
                cls, rule = "EXPECTED_MIGRATION_DIFF", "PUBLISHER_METADATA"
            elif volatile(path):
                cls, rule = "VOLATILE_ONLY", "volatile-contract"
            elif under(path, derived):
                cls, rule = "TARGET_ONLY", "PUBLISHER_DERIVED"
            else:
                cls, rule = "TARGET_ONLY", "NEW_CONTENT"
        d = {"path": path, "class": cls, "rule": rule, "explained": cls in ("EXPECTED_MIGRATION_DIFF", "VOLATILE_ONLY", "LEGACY_ONLY") or rule == "PUBLISHER_DERIVED"}
        if in_l:
            d["liveSha256"] = _sha(live[path])
        if in_t:
            d["targetSha256"] = _sha(target[path])
        diffs.append(d)

    summary = {c: sum(1 for d in diffs if d["class"] == c) for c in CLASSES}
    summary["MATCH"] = match
    blocking = sorted({d["class"] for d in diffs if d["class"] in ("SEMANTIC_MISMATCH", "UNKNOWN") or (d["class"] == "TARGET_ONLY" and not d["explained"])})
    open_compat = sorted({d["rule"] for d in diffs if d["class"] == "LEGACY_ONLY"})
    return {"evaluator": EVALUATOR, "brainId": brain_id, "summary": summary, "verdict": "NOT_EQUIVALENT" if blocking else "EQUIVALENT_WITH_EXPECTED_DIFFS",
            "blocking": blocking, "openCompatibilityRules": open_compat, "differences": diffs}


def render_target(artifact: dict, registry, producer: str = "wind") -> dict:
    """What the Publisher WOULD publish for `artifact` against an EMPTY baseline (DRY_RUN; nothing is persisted): {"updates", "derivedKeys", "result"}."""
    from .publisher import ShadowPublisher
    from .sinks import ShadowSink
    pub = ShadowPublisher(registry, PublishHistory(MemoryObjectStore()), ShadowSink(), mode=PublisherMode.DRY_RUN)
    r = pub.evaluate(artifact, producer=producer)
    if r.plan is None:
        return {"result": r.result.value, "codes": r.codes, "updates": {}, "derivedKeys": ()}
    return {"result": r.result.value, "codes": [], "updates": dict(r.plan.updates), "derivedKeys": r.plan.derived_keys}
