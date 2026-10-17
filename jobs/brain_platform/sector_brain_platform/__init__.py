"""Sector Brain Platform — the shared Python implementation of docs/brains/BRAIN_PLATFORM_CONTRACT.md.

One package for every Python brain (Water Clarity, Biological, Sector Intelligence, and Wind once
it migrates off its adapter). stdlib-only on purpose, so a job can vendor it with a single copy.

Modules
  keys        lake keys, collisions, illegal-key walk, brain/slot table
  timeutil    ISO-8601 UTC helpers
  enums       the closed vocabularies (section 3 of the contract)
  activity    event ids, event records, own-brain pruning by `at`
  freshness   the per-state freshness envelope (section 4)
  health      run health from counts (section 3)
  ownership   shared-field ownership checks (section 5) and source owners (section 6)
  rtdb        the REST client: retries, schema gate, app-db refusal, dry-run store (section 8)
  failure     the standard failure write path (section 10)
  jobs        the Engine-owned /jobs/{jobId} contract (jobs-v1) and its one sync path
  gcp         Cloud Scheduler / Cloud Run reads and the single job-start write (stdlib)
  signals     the Shared Signal Registry (definitions only; consumers declare themselves in brain.json)
  dependency_declarations  declared dependencies discovered from brains/*/brain.json (the one Brain-owned source)
  execution_health         G1: generic execution / job / cadence health (process only)
  dependency_health        G2: dependency availability + evidence freshness (never from lastSuccessfulRun)
  brain_health             brain-health-v1 read model for Ops/Canvas (control/healthV1)
  consumption              ACTUAL consumption lineage recorded at the RTDB client (consumed[] on execution records / artifacts)
"""
from .keys import lake_key, lake_keys, key_collisions, check_keys, check_update, IllegalKey, BRAINS, slot_for, snapshot_field_for
from .timeutil import iso, parse_time, age_hours
from .enums import (HEALTH, READINESS, READINESS_LADDER, BRAIN_STATUS, MODEL_LIFECYCLE, VERSION_STATUS, STATE_KIND,
                    STALENESS_MODEL, SEVERITY, ACTIVITY_KIND, is_promotion, normalize_model_lifecycle, normalize_state_kind)
from .activity import event_id, event, prune_activity
from .freshness import freshness
from .health import run_health
from .ownership import OwnershipError, path_allowed, assert_owned, source_owner
from .rtdb import BrainRtdb, BrainRtdbError, TokenProvider, DryRunStore, check_schema, should_retry, backoff_seconds, SCHEMA_VERSION, BRAIN_RTDB_URL
from .failure import failure_writes
from .orchestrator import plan as orchestrate, decide as orchestrator_decide, descriptor_gaps
from .beta import beta_readiness, BETA_VERSION
from .control import overview, brain_summary, fleet_rollup, fleet_summary, brain_stale, CONTROL_VERSION
from .jobs import MANIFEST as JOB_MANIFEST, JOBS_CONTRACT_VERSION, job_record, build_records, changed_paths as jobs_changed_paths, cron_runs_per_day
from .scoring import score_lake, score_biological, score_intelligence, frozen_score, ladder, finish, dim, score_engine

from . import model_v1, fingerprint as fingerprints, publication, dependencies, field_validation, control_contract
from . import signals, dependency_declarations, execution_health, dependency_health, brain_health   # G1/G2 health + freshness (brain-health-v1)
from . import consumption                                                                        # actual consumption lineage (consumption-lineage-v1)
from .consumption import ConsumptionRecorder
from .model_v1 import ModelError, validate_claim, bounded_workers
from .publication import judge as judge_score, apply_guard as guard_scores, score_content

__all__ = [n for n in dir() if not n.startswith("_")]
