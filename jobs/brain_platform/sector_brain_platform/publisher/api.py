"""Orchestrator API contract (CERT-1; BRAIN_READ_WRITE_SECURITY_V1 section 4). Contract + shadow handler only; nothing is deployed.

Flow: authenticated caller -> coarse authorization -> request schema validation -> fine authorization (incl. per-Brain grants) -> Orchestrator workflow.
SUBMIT_ARTIFACT carries an artifact REFERENCE (id, location, hash, executionId, expected schema), never content: the Publisher loads and validates the artifact itself.
There is NO request field that carries a database path, a value, an update map or a mutation, and the handler holds no database client:
the only thing it can do with an accepted request is hand a validated record to an injected workflow. "Write this JSON to this path" has
no representation in this contract, so it cannot be expressed, let alone authorised.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from ..keys import BRAINS
from . import refs
from .model import Rejected
from .validate import UUID4

API_VERSION = "orchestrator-api-v1"
KINDS = ("CONTROL", "REVIEW", "RESEARCH", "ARTIFACT")
MAX_REQUEST_BYTES = 16 * 1024
MAX_PARAMS = 8
#: Mirrors orchestration.REQUEST_ACTIONS / PROTECTED_ACTIONS (kept literal so this module needs no import of orchestration).
CONTROL_ACTIONS = ("RUN_NOW", "PAUSE", "RESUME", "SET_MANUAL")
PROTECTED_CONTROL_ACTIONS = ("CHANGE_PROTECTED_SCHEDULE", "DISABLE_VALIDATION_CAPTURE")           # need confirm.by == caller and the exact phrase
#: Never grantable through the API, whoever asks and whatever the allowlist says (security doc section 4).
NOT_GRANTABLE = ("SET_ENGINE_MODE", "ACTIVATE_PRODUCTION", "PUBLISH_CUSTOMER", "PROMOTE_LIFECYCLE")
REVIEW_ACTIONS = ("SUBMIT_REVIEW", "ACCEPT_RULE", "REJECT_RULE")
RESEARCH_ACTIONS = ("RESEARCH_GAP",)
ARTIFACT_ACTIONS = ("SUBMIT_ARTIFACT",)
ACTIONS = {"CONTROL": CONTROL_ACTIONS + PROTECTED_CONTROL_ACTIONS, "REVIEW": REVIEW_ACTIONS, "RESEARCH": RESEARCH_ACTIONS,
           "ARTIFACT": ARTIFACT_ACTIONS}
# RUN_BRAIN in the design vocabulary is CONTROL/RUN_NOW (the existing orchestration action name is kept; there is no second spelling).
TOP_KEYS = {"apiVersion", "requestId", "requestKind", "brainId", "action", "params", "confirm"}
ID_TEXT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,79}")


@dataclass(frozen=True)
class Field:
    kind: type = str
    required: bool = False
    max_len: int = 200
    pattern: re.Pattern | None = None
    enum: tuple | None = None


#: Per-action parameter schemas. Scalars only (str/int/bool): no nested objects, no free-form JSON, bounded lengths.
PARAMS = {
    "RUN_NOW": {"scope": Field(str, True, 64, re.compile(r"[A-Za-z0-9_-]{1,64}"))},
    "PAUSE": {"reason": Field(str, False, 500)}, "RESUME": {"reason": Field(str, False, 500)}, "SET_MANUAL": {"reason": Field(str, False, 500)},
    "CHANGE_PROTECTED_SCHEDULE": {"jobId": Field(str, True, 80, ID_TEXT), "reason": Field(str, True, 500)},
    "DISABLE_VALIDATION_CAPTURE": {"reason": Field(str, True, 500)},
    "SUBMIT_REVIEW": {"itemId": Field(str, True, 80, ID_TEXT), "verdict": Field(str, True, 20, enum=("APPROVE", "REJECT", "NEEDS_WORK")), "note": Field(str, False, 2000)},
    "ACCEPT_RULE": {"ruleId": Field(str, True, 80, ID_TEXT), "note": Field(str, False, 2000)},
    "REJECT_RULE": {"ruleId": Field(str, True, 80, ID_TEXT), "note": Field(str, True, 2000)},
    "SUBMIT_ARTIFACT": {"artifactId": Field(str, True, 80), "artifactRef": Field(str, True, refs.MAX_LOCATION), "artifactSha256": Field(str, True, 71),
                        "executionId": Field(str, True, 36), "expectedSchema": Field(str, True, 80)},
    "RESEARCH_GAP": {"topic": Field(str, True, 200), "detail": Field(str, False, 4000), "priority": Field(int, False, enum=(1, 2, 3)),
                     "speciesId": Field(str, False, 80, re.compile(r"[a-z][a-z0-9_]{1,79}")), "lakeKey": Field(str, False, 120, re.compile(r"[A-Za-z0-9_]{1,120}"))},
}
assert all(a in PARAMS for acts in ACTIONS.values() for a in acts)


@dataclass(frozen=True)
class Caller:
    """Produced by the authentication layer (Firebase ID token verification in production). `caller_id` is opaque; never store a real user id in the repo."""
    caller_id: str


@dataclass(frozen=True)
class ApiRequest:
    request_id: str
    kind: str
    brain_id: str
    action: str
    params: dict
    requested_by: str
    confirmed: bool = False


class Authenticator(Protocol):
    def authenticate(self, credential) -> Caller | None: ...


class Dispatcher(Protocol):
    """The Orchestrator workflow entry points. Production implements these; they are the only thing an accepted request reaches."""
    def control(self, request: ApiRequest) -> dict: ...
    def review(self, request: ApiRequest) -> dict: ...
    def research(self, request: ApiRequest) -> dict: ...
    def artifact(self, request: ApiRequest) -> dict: ...


class AllowlistAuthorizer:
    """caller_id -> {kind: set(entries)}. An entry is `ACTION` (any Brain) or `ACTION@brainId` (that Brain only). Deny by default.
    NOT_GRANTABLE actions never reach this table (rejected at validation, and a grant naming one cannot be constructed)."""

    def __init__(self, grants: dict):
        self._g = {c: {k: frozenset(a) for k, a in kinds.items()} for c, kinds in grants.items()}
        for c, kinds in self._g.items():
            for k, acts in kinds.items():
                bad = {a for a in acts if a.split("@")[0] not in ACTIONS.get(k, ()) or ("@" in a and a.split("@")[1] not in BRAINS)}
                if bad:
                    raise ValueError(f"grant for {c}/{k} lists actions or Brains the API does not define: {sorted(bad)}")

    def may_use_api(self, caller: Caller) -> bool:
        return caller.caller_id in self._g

    def may(self, caller: Caller, kind: str, action: str, brain_id: str) -> bool:
        have = self._g.get(caller.caller_id, {}).get(kind, ())
        return action in have or f"{action}@{brain_id}" in have


@dataclass
class ApiResponse:
    status: int                       # 200 accepted | 400 invalid | 401 unauthenticated | 403 forbidden
    outcome: str                      # ACCEPTED | INVALID | UNAUTHENTICATED | FORBIDDEN | NEEDS_CONFIRMATION
    code: str = ""
    detail: str = ""
    request_id: str | None = None
    result: dict = field(default_factory=dict)


def confirm_phrase(action: str, brain_id: str) -> str:
    return f"CONFIRM {action} {brain_id}"


def validate_request(body, caller: Caller) -> ApiRequest:
    """Strict, bounded request validation. Raises ValueError(code, detail)."""
    def bad(code, detail):
        raise ValueError(code, detail)
    if not isinstance(body, dict):
        bad("MALFORMED", "request must be a JSON object")
    unknown = sorted(set(body) - TOP_KEYS)
    if unknown:
        bad("UNKNOWN_FIELD", f"unknown request fields {unknown} (the API accepts no database paths, values or mutations)")
    if body.get("apiVersion") != API_VERSION:
        bad("MALFORMED", f"apiVersion must be {API_VERSION!r}")
    rid = body.get("requestId")
    if not (isinstance(rid, str) and UUID4.fullmatch(rid)):
        bad("MALFORMED", "requestId must be a UUIDv4")
    kind, action, brain = body.get("requestKind"), body.get("action"), body.get("brainId")
    if kind not in KINDS:
        bad("UNKNOWN_KIND", f"requestKind must be one of {KINDS}")
    if action in NOT_GRANTABLE:
        bad("NOT_GRANTABLE", f"{action} is never available through the API")
    if action not in ACTIONS[kind]:
        bad("UNKNOWN_ACTION", f"{kind} actions: {ACTIONS[kind]}")
    if brain not in BRAINS:
        bad("UNKNOWN_BRAIN", f"brainId must be one of the registered Brains")
    params = body.get("params", {})
    if not isinstance(params, dict) or len(params) > MAX_PARAMS:
        bad("MALFORMED", f"params must be an object with at most {MAX_PARAMS} entries")
    schema = PARAMS[action]
    extra = sorted(set(params) - set(schema))
    if extra:
        bad("UNKNOWN_PARAM", f"{action} does not accept {extra}")
    for name, f in schema.items():
        if name not in params:
            if f.required:
                bad("MISSING_PARAM", f"{action} requires {name!r}")
            continue
        v = params[name]
        if type(v) is not f.kind:                                  # bool is not an int here
            bad("PARAM_TYPE", f"{name} must be {f.kind.__name__}")
        if f.kind is str and (len(v) > f.max_len or len(v) == 0):
            bad("PARAM_BOUNDS", f"{name} must be 1..{f.max_len} characters")
        if f.pattern is not None and not f.pattern.fullmatch(v):
            bad("PARAM_FORMAT", f"{name} has an invalid format")
        if f.enum is not None and v not in f.enum:
            bad("PARAM_ENUM", f"{name} must be one of {f.enum}")
    if action == "SUBMIT_ARTIFACT":
        try:       # the signal identifies an artifact in the caller's OWN namespace; it carries no content and no database path
            refs.ArtifactRef(brain, params["artifactId"], params["artifactRef"], params["artifactSha256"], params["executionId"], params["expectedSchema"], rid).validate()
        except Rejected as e:
            bad(e.violations[0]["code"], e.violations[0]["detail"])
    confirmed = False
    if action in PROTECTED_CONTROL_ACTIONS:
        c = body.get("confirm")
        confirmed = isinstance(c, dict) and set(c) == {"by", "phrase"} and c["by"] == caller.caller_id and c["phrase"] == confirm_phrase(action, brain)
    elif "confirm" in body:
        bad("UNKNOWN_FIELD", f"{action} takes no confirm block")
    return ApiRequest(rid, kind, brain, action, dict(params), caller.caller_id, confirmed)


class OrchestratorApi:
    def __init__(self, authenticator: Authenticator, authorizer: AllowlistAuthorizer, dispatcher: Dispatcher):
        self._authn, self._authz, self._dispatch = authenticator, authorizer, dispatcher

    def handle(self, credential, body) -> ApiResponse:
        caller = self._authn.authenticate(credential)
        if caller is None:
            return ApiResponse(401, "UNAUTHENTICATED", "UNAUTHENTICATED")
        if not self._authz.may_use_api(caller):
            return ApiResponse(403, "FORBIDDEN", "NOT_ALLOWLISTED")
        try:
            req = validate_request(body, caller)
        except ValueError as e:
            code, detail = e.args if len(e.args) == 2 else ("MALFORMED", str(e))
            return ApiResponse(400, "INVALID", code, detail, body.get("requestId") if isinstance(body, dict) and isinstance(body.get("requestId"), str) else None)
        if not self._authz.may(caller, req.kind, req.action, req.brain_id):
            return ApiResponse(403, "FORBIDDEN", "ACTION_NOT_GRANTED", f"{req.action} on {req.brain_id}", req.request_id)
        if req.action in PROTECTED_CONTROL_ACTIONS and not req.confirmed:
            return ApiResponse(200, "NEEDS_CONFIRMATION", "CONFIRM_REQUIRED", f"resubmit with confirm = {{by: <caller>, phrase: {confirm_phrase(req.action, req.brain_id)!r}}}",
                               req.request_id)
        out = {"CONTROL": self._dispatch.control, "REVIEW": self._dispatch.review, "RESEARCH": self._dispatch.research,
               "ARTIFACT": self._dispatch.artifact}[req.kind](req)
        return ApiResponse(200, "ACCEPTED", "", "", req.request_id, out if isinstance(out, dict) else {})
