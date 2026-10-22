"""The declarative Brain-specific truth the kit consumes. Data only: no behaviour is selected by a Brain's name anywhere in the kit."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional


class SpecError(ValueError):
    """The BrainCertSpec itself is incomplete or self-contradictory (a spec problem, never a Brain problem)."""


@dataclass(frozen=True)
class Rejection:
    """A Brain-specific path the Publisher must reject, with the named rejection code."""
    path: str
    code: str


@dataclass(frozen=True)
class BrainCertSpec:
    # ---- identity and location -------------------------------------------------------------------------------------------------------------
    brain_id: str                                   # machine brainId (stable, never renamed)
    directory: str                                  # brains/<directory>
    repo_root: str                                  # absolute path of the repository checkout under test
    # ---- declared truth (what brain.json / the control manifest must say) ----------------------------------------------------------------
    lifecycle: str                                  # brain.json lifecycle == control manifest lifecycle == artifact lineage lifecycle
    workspace_id: str                               # logical research workspace id
    authorized_consumers: tuple = ()
    consumes: tuple = ()                            # EXACT expected brain.json `consumes` (list of dicts)
    providers: tuple = ()                           # EXACT expected provider ids
    cutover_status: str = "SHADOW"
    customer_integration_mode: str = "none"
    runtime_kind: str = "job"
    # ---- package shape ---------------------------------------------------------------------------------------------------------------------
    required_files: tuple = ()                      # repo-relative to the Brain directory
    unique_module_basenames: tuple = ()             # file names that must exist exactly once in the repository, inside the Brain's runtime
    legacy_pointer_dir: Optional[str] = None        # repo-relative dir that must contain only README.md (retirement pointer); None = no legacy dir
    runtime_dir: str = "runtime"
    allowed_runtime_ext: tuple = (".py", ".json")   # runtime package file types (no data/binaries)
    research_files: Optional[tuple] = None          # exact research dir listing (None = do not pin)
    contract_tokens: tuple = ()                     # strings the operating contract must contain (ownership boundaries, caveats)
    contract_required_terms: tuple = ()
    contract_forbidden_terms: tuple = ()
    # ---- published contract / Publisher ----------------------------------------------------------------------------------------------------
    bundle_id: str = ""
    contract_file: str = ""                         # repo-relative to the Brain directory, e.g. contracts/<id>-publication-v1.json
    describe_module: str = "contracts/describe_contract.py"
    registry_schema_id: str = ""                    # a section schema with a /brains/{id}/{child} family
    registry_probe_child: str = "status"
    job_id: str = ""                                # the Brain's job record id (for the /health/jobs rejection)
    plan_root_prefixes: tuple = ()                  # every key of a SHADOW plan must start with one of these (no-prefix slashes)
    extra_rejections: tuple = ()                    # Rejection(...) entries specific to this Brain's domain
    providers_match_registry_sources: bool = False  # True: brain.json providers == the sources the Publisher registration says this Brain acquires
    # ---- direct-write isolation ------------------------------------------------------------------------------------------------------------
    write_call_suffixes: tuple = ("rtdb.update",)   # attribute-call suffixes that are database write primitives in this runtime
    allowed_write_sites: frozenset = frozenset()    # {(file basename, enclosing function, call)} == the direct-write audit table
    forbidden_imports: tuple = ("firebase_admin", "requests", "google.cloud", "pyrebase")
    builder_module: str = ""                        # repo-relative to the Brain directory: the pure artifact builder
    builder_forbidden_imports: tuple = ("os", "urllib", "requests", "subprocess", "random", "uuid", "time", "socket", "shutil", "tempfile", "http")
    builder_forbidden_tokens: tuple = ("open(", "datetime.now", "utcnow", ".environ", "urlopen")
    local_path_regex: str = r"/Users/|/home/[a-z]|\bDesktop/|Sector[ _]Research|Sector_Research_Data|~/|expanduser|SECTOR_RESEARCH_ROOT"
    local_path_exempt_markers: tuple = ()           # a runtime line containing one of these literals is a documented exception (e.g. a deliberately-leaky test constant)
    # ---- architecture gates / score ------------------------------------------------------------------------------------------------------
    arch_findings: tuple = ()                       # ((file basename, invariant), ...) registered-Brain findings that are the carried baseline entries
    baseline_entry_basenames: tuple = ()            # basenames of this Brain's carried legacy-baseline entries
    baseline_carried_from_required: bool = True
    has_score: bool = True                          # False: the Brain has NO Engine readiness score (brain.json must declare none; no /scores path is written)
    score_baseline_substring: Optional[str] = None  # substring `score_baseline.py --check` must print for this Brain; None = score is computed live (no frozen baseline)
    # ---- artifact factory (the only code a Brain must supply) -----------------------------------------------------------------------------
    # artifact_factory(n, generated_at, consumed, rerun) -> sealed publish-artifact-v2 dict.  n = run number (new executionId), generated_at = ISO UTC,
    # consumed = recorder list or None (unknown), rerun = True means "a later run on UNCHANGED inputs after the first was published".
    artifact_factory: Optional[Callable] = None
    changed_artifact_factory: Optional[Callable] = None     # (n, generated_at) -> artifact with a REAL domain change (fingerprint must change)
    release_lineage: tuple = ("NONE", "NONE", "NONE")        # (knowledgeRelease, manifestRef, manifestSha256) the artifact lineage must carry
    expected_review_status: str = "UNREVIEWED"
    expected_validation_status: str = "NOT_VALIDATED"
    consumed_absent_when_unknown: bool = True               # False only for a Brain whose builder derives consumed[] from its own recorded states (declare why in not_applicable docs)
    # ---- documented, justified non-applicability (recorded in the report; never silent) -----------------------------------------------------
    not_applicable: dict = field(default_factory=dict)       # {proof id: reason}

    # ----------------------------------------------------------------------------------------------------------------------------------------
    @property
    def brain_dir(self) -> str:
        return os.path.join(self.repo_root, "brains", self.directory)

    def validate(self) -> "BrainCertSpec":
        missing = [f for f in ("brain_id", "directory", "repo_root", "lifecycle", "workspace_id", "bundle_id", "contract_file", "registry_schema_id", "builder_module")
                   if not getattr(self, f)]
        if missing:
            raise SpecError(f"BrainCertSpec is missing {missing}")
        if self.artifact_factory is None and "ARTIFACT" not in self.not_applicable:
            raise SpecError("artifact_factory is required (or not_applicable['ARTIFACT'] with a reason)")
        if not os.path.isdir(self.brain_dir):
            raise SpecError(f"{self.brain_dir} is not a Brain directory")
        for pid, why in self.not_applicable.items():
            if not (isinstance(why, str) and len(why.split()) >= 4):
                raise SpecError(f"not_applicable[{pid!r}] must carry a real reason")
        return self
