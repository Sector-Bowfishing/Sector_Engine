# Publisher V1 shadow: test report

**Run:** `cd jobs/brain_platform && python -m pytest -q` (pytest in a throw-away virtualenv outside the repo; Python 3.14.8, stdlib-only code).
**Result:** `306 passed` for the whole platform suite = 130 pre-existing (unchanged, still passing) + **176 new**. `jobs/brain-orchestrator`: 24 passed (unchanged). No live system, network, credential or cloud resource was used; tests refuse them.

| File | Tests | Covers |
|---|---|---|
| `tests/test_publisher_shadow.py` | 121 | validation, authorization, fingerprints, SKIP / SHADOW_READY, plan, null/delete, records |
| `tests/test_publisher_storage.py` | 17 | versioned history, immutability, head pointer, linkage, rollback metadata, local-dir persistence |
| `tests/test_publisher_boundary.py` | 9 | shadow-only guarantee |
| `tests/test_publisher_api.py` | 29 | API contract bounds, authorization, no arbitrary mutation |
| `tests/publisher_fixtures.py` | n/a | synthetic lakes/ids only; no real data |

## Required-test mapping
| # | Requirement | Test(s) |
|---|---|---|
| 1 | valid Wind artifact accepted | `test_valid_wind_artifact_is_accepted_and_shadow_ready`, `test_wind_may_target_its_own_registry_sources_health_and_activity_via_their_schemas` |
| 2 | malformed rejected | `test_malformed_artifacts_are_rejected`, `test_unknown_envelope_key_and_extra_mutation_keys_are_malformed` |
| 3 | unknown brainId rejected | `test_unknown_brain_id_is_rejected`, `test_submitter_must_match_artifact_brain_identity`, `test_unregistered_producer_is_an_error_not_a_result` |
| 4 | unknown schema rejected | `test_unknown_schema_is_rejected`, `test_schema_of_another_brain_is_rejected`, `test_other_registered_brains_have_no_schema_yet` |
| 5 | missing lineage rejected | `test_missing_lineage_is_rejected`, `test_incomplete_lineage_is_rejected` (12 fields), `test_ill_formed_lineage_values_are_rejected`, release triplet test |
| 6 | unauthorized Wind path rejected | `test_paths_outside_the_wind_families_fail_closed` (19 paths), `test_a_schema_cannot_borrow_another_schemas_paths`, reserved-children test |
| 7 | Fish path as Wind rejected | `test_fish_path_submitted_as_wind_is_rejected_and_names_the_owner`, `test_wind_cannot_target_other_domains` (`/speciesProfiles/*`, `/species/*`, `speciesPresence`, other slots, scores, control, jobs, access, other Brains' registries) |
| 8 | explicit cross-domain mutation rejected | same, asserts `CROSS_DOMAIN_PATH` and `plan is None` |
| 9 | output fingerprint independently verified | `test_output_fingerprint_is_independently_verified`, `test_fingerprint_ignores_volatile_fields_key_order_and_mutation_order`, `test_fingerprint_binds_brain_and_schema` |
| 10 | unchanged = SKIP | `test_unchanged_output_is_skip_and_generates_no_mutation` |
| 11 | changed = SHADOW_READY | `test_changed_output_is_shadow_ready_again_and_head_advances`, `test_scopes_have_independent_baselines` |
| 12 | deterministic patch | `test_patch_generation_is_deterministic` (mutation order shuffled → identical bytes/hash) |
| 13 | atomic multi-path | `test_multi_path_update_is_one_atomic_plan_with_exactly_the_intended_paths`, `test_failure_in_one_mutation_means_no_plan_and_no_partial_state`, `test_sink_failure_before_commit_leaves_no_published_state`, `test_plan_embeds_everything_needed_so_no_secondary_write_is_required` |
| 14 | null/missing never delete | `test_null_and_empty_values_never_become_implicit_deletes` (7 shapes), `test_missing_set_value_is_not_a_delete`, `test_non_finite_numbers_are_rejected`, `test_absent_data_does_not_delete_what_was_published_before` |
| 15 | explicit delete fails unless permitted | `test_explicit_delete_fails_unless_the_schema_permits_it`, `…is_rendered_only_when_permitted_and_only_for_that_path`, `test_delete_needs_a_reason_and_no_value`, `test_delete_permission_is_per_family_not_global` |
| 16 | shadow never invokes live mutation | all of `test_publisher_boundary.py` |
| 17 | publication record correct | `test_publication_record_is_generated_correctly`, `test_rejected_and_skipped_outcomes_are_in_history_only` |
| 18 | previous-publish linkage | `test_previous_publication_linkage_and_head_generations` |
| 19 | rollback metadata | `test_rollback_metadata_identifies_the_previous_publish_and_artifact` |
| 20 | API cannot do arbitrary mutation | `test_arbitrary_database_writes_are_not_expressible` (9 shapes), `test_params_are_closed_scalar_and_bounded`, `test_every_defined_action_has_a_param_schema_and_no_schema_field_looks_like_a_path_or_payload`, `test_api_module_has_no_database_client_or_publisher_write_path` |
| 21 | CONTROL/REVIEW/RESEARCH bounded | `test_schema_bounds`, `test_review_and_research_schemas_are_separate_from_control`, `test_ungrantable_actions_…`, `test_protected_actions_need_the_exact_confirmation…` |
| 22 | fails closed | `test_paths_outside_the_wind_families_fail_closed`, `test_schema_registration_refuses_forbidden_roots_and_empty_families`, deny-by-default authorizer test |

Extra coverage: lifecycle (`PRODUCTION*` refused for Wind; needs schema permission + `approvalRef`), review/validation consistency, freshness (UNKNOWN is a value), oversize, value type, illegal RTDB keys, overlapping paths, artifact-id immutability, older-than-baseline artifacts, DRY_RUN persists nothing, evaluate-from-store, input not mutated, Wind families ⊆ the live ownership table.

## Not tested (and why)
* Anything live: RTDB, GCS, IAM, rules, Cloud Run, Scheduler, Firebase token verification. None exists in this task or was touched.
* A GCS `ObjectStore` adapter (does not exist; bucket needs approval). Versioning semantics are tested against the in-memory/local implementations that mirror GCS generations.
* Reconciliation of the shadow baseline with live state, rollback *execution*, manifest-last chunking: future work (see cutover requirements).
* Wind-hourly's real output: Publisher V1 was not wired into it. Wind artifacts here are synthetic.
