"""Artifact references: the ONLY thing an API signal carries about an artifact (never its content, never a database path).

Logical private-storage layout (CERT-3; no bucket exists, this is the contract):
  artifacts/{brainId}/{artifactId}/artifact.json     specialist Brain creates (own prefix only, create-only)
  publishes/{brainId}/{publishId}/record.json        Publisher creates (immutable)
  publishes/{brainId}/_heads/{schema}/{scope}.json   Publisher, versioned baseline pointer
  scores/{brainId}/...  exports/...                  reserved prefixes
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..keys import BRAINS
from .model import Rejected, Violation

UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
SHA = re.compile(r"sha256:[0-9a-f]{64}")
SCHEMA_ID = re.compile(r"[a-z][a-z0-9-]{1,78}")
MAX_LOCATION = 200


def artifact_dir(brain_id: str, artifact_id: str) -> str:
    return f"artifacts/{brain_id}/{artifact_id.replace(':', '-')}/"


def artifact_location(brain_id: str, artifact_id: str) -> str:
    return artifact_dir(brain_id, artifact_id) + "artifact.json"


@dataclass(frozen=True)
class ArtifactRef:
    brain_id: str
    artifact_id: str                  # UUIDv4 or sha256:<hex>
    location: str                     # must equal artifact_location(brain_id, artifact_id)
    sha256: str                       # sha256 of the EXACT stored bytes
    execution_id: str                 # must equal lineage.executionId inside the artifact
    expected_schema: str              # must equal lineage.artifactSchema inside the artifact
    request_id: str | None = None

    def validate(self) -> "ArtifactRef":
        def bad(code, detail):
            raise Rejected([Violation(code, detail)])
        if self.brain_id not in BRAINS:
            bad("UNKNOWN_BRAIN", f"brainId {self.brain_id!r} is not a registered Brain")
        if not (isinstance(self.artifact_id, str) and (UUID4.fullmatch(self.artifact_id) or SHA.fullmatch(self.artifact_id))):
            bad("ARTIFACT_REF_INVALID", "artifactId must be a UUIDv4 or sha256:<hex>")
        if not isinstance(self.location, str) or not self.location or len(self.location) > MAX_LOCATION:
            bad("ARTIFACT_REF_INVALID", f"location must be a string of 1..{MAX_LOCATION} characters")
        if not self.location.startswith(f"artifacts/{self.brain_id}/"):
            bad("NAMESPACE_VIOLATION", f"a {self.brain_id!r} request may reference only artifacts/{self.brain_id}/…")
        if self.location != artifact_location(self.brain_id, self.artifact_id):
            bad("ARTIFACT_REF_INVALID", "location is not the canonical location of this artifactId")
        if not (isinstance(self.sha256, str) and SHA.fullmatch(self.sha256)):
            bad("ARTIFACT_REF_INVALID", "artifact hash must be sha256:<64 hex>")
        if not (isinstance(self.execution_id, str) and UUID4.fullmatch(self.execution_id)):
            bad("ARTIFACT_REF_INVALID", "executionId must be a UUIDv4")
        if not (isinstance(self.expected_schema, str) and SCHEMA_ID.fullmatch(self.expected_schema)):
            bad("ARTIFACT_REF_INVALID", "expected schema id is malformed")
        if self.request_id is not None and not (isinstance(self.request_id, str) and UUID4.fullmatch(self.request_id)):
            bad("ARTIFACT_REF_INVALID", "requestId must be a UUIDv4")
        return self
