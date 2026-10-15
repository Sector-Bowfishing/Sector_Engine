"""Structural validation stages (BRAIN_READ_WRITE_SECURITY_V1 section 3). Structure and authorization only; never science.

Each stage raises `Rejected` carrying every violation found in that stage. The Publisher runs the stages in order and stops at the first failing one.
"""
from __future__ import annotations

import datetime as dt
import math
import re

from ..keys import IllegalKey, check_keys
from .canonical import canonical_bytes, output_fingerprint
from .model import ENVELOPE_ID, FRESHNESS_STATUSES, LINEAGE_ID, OPS, REVIEW_STATUSES, Rejected, Violation
from .paths import PathError, foreign_owner, normalize_path, touches_reserved
from .registry import ALL_LIFECYCLES, PRODUCTION_LIFECYCLES, VALIDATION_WORDS, Registry, SchemaSpec

from .refs import SHA, UUID4
ISO_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")
SCOPE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,63}")
ENVELOPE_KEYS = {"envelope", "lineage", "mutations", "scope", "freshness", "approvalRef"}
LINEAGE_REQUIRED = ("schema", "brainId", "artifactSchema", "knowledgeRelease", "manifestRef", "manifestSha256", "codeVersion", "executionId",
                    "inputFingerprint", "outputFingerprint", "generatedAt", "lifecycle", "reviewStatus", "validationStatus")
LINEAGE_OPTIONAL = ("artifactId",)
FRESHNESS_KEYS = {"evidenceObservedAt", "inputGeneratedAt", "staleAfter", "expiresAt", "freshnessStatus"}


def parse_time(s) -> dt.datetime | None:
    if not isinstance(s, str) or not ISO_UTC.fullmatch(s):
        return None
    try:
        return dt.datetime.fromisoformat(s[:-1] + "+00:00")
    except ValueError:
        return None


def _one(code, detail, path=None):
    raise Rejected([Violation(code, detail, path)])


# ---- stage 0: shape ------------------------------------------------------------------------------------------------------------------------
def check_shape(raw) -> None:
    if not isinstance(raw, dict):
        _one("MALFORMED", "artifact must be a JSON object")
    try:
        canonical_bytes(raw)
    except ValueError as e:
        _one("NON_FINITE", f"NaN/Infinity is not representable: {e}")
    except TypeError as e:
        _one("MALFORMED", f"artifact is not JSON serialisable: {e}")
    unknown = sorted(set(raw) - ENVELOPE_KEYS)
    if unknown:
        _one("MALFORMED", f"unknown envelope keys {unknown}")
    if raw.get("envelope") != ENVELOPE_ID:
        _one("MALFORMED", f"envelope must be {ENVELOPE_ID!r}")
    if not isinstance(raw.get("lineage"), dict) or not raw["lineage"]:
        _one("LINEAGE_MISSING", "artifact has no lineage block")
    ms = raw.get("mutations")
    if not isinstance(ms, list) or not ms:
        _one("MALFORMED", "mutations must be a non-empty list")
    for i, m in enumerate(ms):
        if not isinstance(m, dict) or set(m) - {"op", "path", "value", "reason"} or m.get("op") not in OPS or "path" not in m:
            _one("MALFORMED", f"mutation #{i} must be {{op: SET|DELETE, path, value|reason}}")
    if "scope" in raw and not (isinstance(raw["scope"], str) and SCOPE.fullmatch(raw["scope"])):
        _one("MALFORMED", "scope must match [A-Za-z0-9_][A-Za-z0-9._-]{0,63}")


# ---- stage 1: brain identity ---------------------------------------------------------------------------------------------------------------
def check_brain(lineage: dict, producer: str, registry: Registry) -> str:
    brain = lineage.get("brainId")
    if not isinstance(brain, str) or brain not in registry.brains:
        _one("UNKNOWN_BRAIN", f"brainId {brain!r} is not a registered Brain")
    if brain != producer:
        _one("IDENTITY_MISMATCH", f"artifact claims brainId {brain!r} but was submitted by {producer!r}")
    return brain


# ---- stage 2: schema -----------------------------------------------------------------------------------------------------------------------
def check_schema(lineage: dict, brain: str, registry: Registry) -> SchemaSpec:
    sid = lineage.get("artifactSchema")
    spec = registry.spec(sid)
    if spec is None:
        _one("UNKNOWN_SCHEMA", f"artifactSchema {sid!r} is not registered")
    if spec.brain_id != brain:
        _one("SCHEMA_BRAIN_MISMATCH", f"schema {sid!r} belongs to {spec.brain_id!r}, not {brain!r}")
    return spec


# ---- stage 3: mutation operations and target paths -------------------------------------------------------------------------------------------
def check_paths(mutations: list[dict], brain: str, spec: SchemaSpec, registry: Registry) -> list[dict]:
    """-> mutations with normalised paths. Collects EVERY path violation so a reviewer sees the whole picture."""
    if len(mutations) > spec.max_mutations:
        _one("OVERSIZE", f"{len(mutations)} mutations exceeds {spec.max_mutations}")
    out, bad = [], []
    for m in mutations:
        try:
            p = normalize_path(m["path"])
        except PathError as e:
            bad.append(Violation("INVALID_PATH", str(e)))
            continue
        delete = m["op"] == "DELETE"
        if p.split("/")[1] == "brains" and p.count("/") <= 2:
            bad.append(Violation("BRAIN_NODE_REPLACEMENT", "a specialist artifact may not replace /brains or a whole /brains/{brainId} node; publish approved CHILD paths", p))
        elif touches_reserved(p):
            bad.append(Violation("RESERVED_PATH", "Publisher-owned (or its ancestor); no artifact may write it", p))
        elif registry.authorizing_family(spec, p, delete=delete) is None:
            if delete and registry.authorizing_family(spec, p) is not None:
                bad.append(Violation("DELETE_NOT_PERMITTED", f"schema {spec.schema_id} does not permit deleting this path", p))
            else:
                owner = foreign_owner(p, brain)
                if owner:
                    bad.append(Violation("CROSS_DOMAIN_PATH", f"path belongs to {owner!r}, not {brain!r}", p))
                else:
                    bad.append(Violation("PATH_NOT_AUTHORIZED", f"no path family of {spec.schema_id} covers this path", p))
        out.append({**m, "path": p})
    if bad:
        raise Rejected(bad)
    paths = sorted(m["path"] for m in out)
    dup = [b for a, b in zip(paths, paths[1:]) if a == b or b.startswith(a + "/")]
    if dup:
        raise Rejected([Violation("OVERLAPPING_PATHS", "paths overlap (a multi-location update cannot write a path and its descendant)", d) for d in dup])
    return out


# ---- stage 4: lineage ----------------------------------------------------------------------------------------------------------------------
def check_lineage(lineage: dict, spec: SchemaSpec, release_resolver=None) -> None:
    missing = [k for k in LINEAGE_REQUIRED if lineage.get(k) in (None, "")]
    if missing:
        _one("LINEAGE_INCOMPLETE", f"missing lineage fields {missing}")
    v = []
    extra = sorted(set(lineage) - set(LINEAGE_REQUIRED) - set(LINEAGE_OPTIONAL))
    if extra:
        v.append(Violation("LINEAGE_INCOMPLETE", f"unknown lineage fields {extra}"))
    if lineage["schema"] != LINEAGE_ID:
        v.append(Violation("LINEAGE_INCOMPLETE", f"lineage.schema must be {LINEAGE_ID!r}"))
    if not (isinstance(lineage["executionId"], str) and UUID4.fullmatch(lineage["executionId"])):
        v.append(Violation("LINEAGE_INCOMPLETE", "executionId must be a UUIDv4"))
    aid = lineage.get("artifactId")
    if aid is not None and not (isinstance(aid, str) and (UUID4.fullmatch(aid) or SHA.fullmatch(aid))):
        v.append(Violation("LINEAGE_INCOMPLETE", "artifactId must be a UUIDv4 or sha256:<hex>"))
    for k in ("inputFingerprint", "outputFingerprint"):
        if not (isinstance(lineage[k], str) and SHA.fullmatch(lineage[k])):
            v.append(Violation("LINEAGE_INCOMPLETE", f"{k} must be sha256:<64 hex>"))
    if parse_time(lineage["generatedAt"]) is None:
        v.append(Violation("LINEAGE_INCOMPLETE", "generatedAt must be ISO-8601 UTC (…Z)"))
    for k in ("knowledgeRelease", "manifestRef", "codeVersion"):
        if not isinstance(lineage[k], str):
            v.append(Violation("LINEAGE_INCOMPLETE", f"{k} must be a string"))
    ms = lineage["manifestSha256"]
    if not (ms == "NONE" or (isinstance(ms, str) and SHA.fullmatch(ms))):
        v.append(Violation("LINEAGE_INCOMPLETE", "manifestSha256 must be 'NONE' or sha256:<64 hex>"))
    if not v:
        none = [lineage[k] == "NONE" for k in ("knowledgeRelease", "manifestRef", "manifestSha256")]
        if any(none) and not all(none):
            v.append(Violation("LINEAGE_INCOMPLETE", "knowledgeRelease, manifestRef and manifestSha256 must be all 'NONE' or all declared"))
        elif all(none) and spec.require_release:
            v.append(Violation("LINEAGE_INCOMPLETE", f"schema {spec.schema_id} requires a canonical release"))
        elif not any(none) and release_resolver is not None:
            if not release_resolver(lineage["knowledgeRelease"], lineage["manifestRef"], lineage["manifestSha256"]):
                v.append(Violation("RELEASE_UNRESOLVED", "knowledgeRelease/manifestRef did not resolve to the declared manifestSha256"))
    if v:
        raise Rejected(v)


# ---- stage 5: lifecycle, review/validation semantics, freshness -------------------------------------------------------------------------------
def check_semantics(raw: dict, spec: SchemaSpec) -> None:
    lin = raw["lineage"]
    lc = lin["lifecycle"]
    if lc not in ALL_LIFECYCLES:
        _one("INVALID_LIFECYCLE", f"lifecycle {lc!r} not in the Brain Model v1 vocabulary")
    if lc not in spec.allowed_lifecycles:
        _one("LIFECYCLE_NOT_AUTHORIZED", f"schema {spec.schema_id} may not publish lifecycle {lc!r}")
    if lc in PRODUCTION_LIFECYCLES and not (isinstance(raw.get("approvalRef"), str) and raw["approvalRef"]):
        _one("LIFECYCLE_NOT_AUTHORIZED", f"lifecycle {lc!r} requires an approvalRef")
    rs, vs = lin["reviewStatus"], lin["validationStatus"]
    if rs not in REVIEW_STATUSES:
        _one("INVALID_STATUS", f"reviewStatus {rs!r} not in {REVIEW_STATUSES}")
    if vs not in VALIDATION_WORDS:
        _one("INVALID_STATUS", f"validationStatus {vs!r} not in the validation/claim-maturity vocabulary")
    if spec.require_review_status and rs == "NOT_APPLICABLE":
        _one("INVALID_STATUS", f"schema {spec.schema_id} requires a real reviewStatus (not NOT_APPLICABLE)")
    if vs == "VALIDATED" and rs != "REVIEWED":
        _one("STATUS_INCONSISTENT", "validationStatus VALIDATED requires reviewStatus REVIEWED")
    fr = raw.get("freshness")
    if fr is None:
        if spec.require_freshness:
            _one("FRESHNESS_MISSING", f"schema {spec.schema_id} requires a freshness block")
        return
    if not isinstance(fr, dict) or set(fr) - FRESHNESS_KEYS or fr.get("freshnessStatus") not in FRESHNESS_STATUSES:
        _one("INVALID_FRESHNESS", f"freshness must use only {sorted(FRESHNESS_KEYS)} with freshnessStatus in {FRESHNESS_STATUSES} (UNKNOWN is a value)")
    times = {}
    for k in FRESHNESS_KEYS - {"freshnessStatus"}:
        if k in fr:
            t = parse_time(fr[k])
            if t is None:
                _one("INVALID_FRESHNESS", f"{k} must be ISO-8601 UTC")
            times[k] = t
    if "staleAfter" in times and "expiresAt" in times and times["staleAfter"] > times["expiresAt"]:
        _one("INVALID_FRESHNESS", "staleAfter must not be after expiresAt")


# ---- stage 5b: values (null / empty never mean delete) ----------------------------------------------------------------------------------------
def _find(v, pred, path=""):
    """First sub-path of `v` satisfying pred, or None."""
    if pred(v):
        return path or "/"
    for k, x in (v.items() if isinstance(v, dict) else enumerate(v) if isinstance(v, list) else ()):
        r = _find(x, pred, f"{path}/{k}")
        if r:
            return r
    return None


def check_values(mutations: list[dict], spec: SchemaSpec, registry: Registry) -> None:
    """RTDB deletes a node written as null and drops empty objects/arrays. Neither may ever happen implicitly, so neither is accepted as a SET value."""
    bad = []
    for m in mutations:
        p = m["path"]
        if m["op"] == "DELETE":
            if "value" in m or not (isinstance(m.get("reason"), str) and m["reason"].strip()):
                bad.append(Violation("INVALID_DELETE", "DELETE takes no value and needs a non-empty reason", p))
            continue
        if "reason" in m:
            bad.append(Violation("MALFORMED", "SET takes no reason", p))
        if m.get("value") is None:
            bad.append(Violation("NULL_VALUE", "SET value is null/missing; null is never an implicit delete (use an explicit DELETE where the schema permits)", p))
            continue
        v = m["value"]
        if _find(v, lambda x: isinstance(x, float) and not math.isfinite(x)):
            bad.append(Violation("NON_FINITE", "NaN/Infinity is not representable; encode UNKNOWN explicitly", p))
        n = _find(v, lambda x: x is None)
        if n:
            bad.append(Violation("NULL_IN_VALUE", f"null inside the value at {n}; encode UNKNOWN as the string 'UNKNOWN', not null", p))
        e = _find(v, lambda x: isinstance(x, (dict, list)) and not x)
        if e:
            bad.append(Violation("EMPTY_VALUE", f"empty object/array at {e} would be dropped by RTDB (an implicit delete)", p))
        try:
            check_keys(v, p)
        except IllegalKey as ex:
            bad.append(Violation("ILLEGAL_KEY", str(ex), p))
        fam = registry.authorizing_family(spec, p)
        want = spec.value_types.get(fam.pattern) if fam else None
        if want is not None and not isinstance(v, want):
            bad.append(Violation("VALUE_TYPE", f"value must be {want.__name__}", p))
    if bad:
        raise Rejected(bad)


def check_size(mutations: list[dict], spec: SchemaSpec) -> None:
    n = len(canonical_bytes(mutations))
    if n > spec.max_bytes:
        _one("OVERSIZE", f"{n} bytes exceeds {spec.max_bytes} for {spec.schema_id}")


# ---- stage 6: fingerprint ------------------------------------------------------------------------------------------------------------------
def verify_fingerprint(lineage: dict, brain: str, spec: SchemaSpec, mutations: list[dict]) -> str:
    fp = output_fingerprint(brain, spec.schema_id, mutations, spec.volatile_extra)
    if lineage["outputFingerprint"] != fp:
        _one("FINGERPRINT_MISMATCH", f"declared {lineage['outputFingerprint']} but the canonical content hashes to {fp}")
    return fp
