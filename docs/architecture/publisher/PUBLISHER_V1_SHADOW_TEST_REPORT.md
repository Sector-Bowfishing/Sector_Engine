# Publisher V1 shadow: test report

**Run:** `cd jobs/brain_platform && python -m pytest -q` (pytest in a throw-away virtualenv outside the repo; Python 3.14.8, stdlib-only code).
**Result (after the design-closeout follow-up):** `381 passed` for the whole platform suite = 130 pre-existing (unchanged, still passing) + **251 Publisher tests** (176 from the first round, adjusted where the locked decisions changed behaviour, plus 75 added). First-round result was 306 passed. `jobs/brain-orchestrator`: 24 passed (unchanged). No live system, network, credential or cloud resource was used; tests refuse them.

| File | Tests | Covers |
|---|---|---|
| `tests/test_publisher_shadow.py` | 121 | validation, authorization, fingerprints, SKIP / SHADOW_READY, plan, null/delete, records, plan-applies-to-store regression |
| `tests/test_publisher_storage.py` | 17 | versioned history, immutability, head pointer, linkage, rollback metadata, local-dir persistence, new key layout |
| `tests/test_publisher_boundary.py` | 9 | shadow-only guarantee |
| `tests/test_publisher_api.py` | 57 | API contract bounds, authorization, no arbitrary mutation; `SUBMIT_ARTIFACT` reference contract and per-Brain grants |
| `tests/test_publisher_handoff.py` | 37 | artifact handoff by reference, namespace/hash/binding checks, private-namespace access model, ordering rule, `/brains/{id}` child ownership |
| `tests/test_publisher_wind_integration.py` | 10 | the Wind shadow-integration contract through the full handoff + API |
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

## Design-closeout tests (follow-up session): mapping to the 14 requirements
| # | Requirement | Test(s) |
|---|---|---|
| 1 | whole-node `/brains/wind` replacement rejected | `test_whole_node_brains_replacement_is_rejected` (`BRAIN_NODE_REPLACEMENT`), `test_reserved_publisher_children_are_never_writable_even_if_a_schema_declares_them`, Wind integration `/brains/wind` case |
| 2 | allowed Wind child updates accepted | `test_approved_wind_child_updates_are_accepted_one_per_registry_group`, `test_wind_may_target_its_own_registry_sources_health_and_activity_via_their_schemas` |
| 3 | `/brains/wind/publication` cannot be supplied/overwritten | `test_wind_cannot_supply_or_overwrite_publisher_owned_or_foreign_brain_children` (publication, nested publication, certification, unapproved child, nested child, foreign Brain), Wind integration |
| 4 | Publisher adds its own publication metadata | `test_publisher_adds_its_own_publication_metadata_and_it_merges_without_touching_siblings` (plan applied to a store double: siblings and `certification` untouched) |
| 5 | older-than-baseline rejected/diagnosed | `test_older_artifact_is_rejected_with_a_diagnostic_naming_the_baseline`, `…equal_generated_at…`, `…sub_second_precision…`, `…unestablishable_order_fails_closed` (`BASELINE_ORDER_UNKNOWN`), `…future_dated…` (`ARTIFACT_FROM_FUTURE`), `…equal_content_skips_even_when…`, `…ordering_is_per_scope` |
| 6 | artifact reference/hash mismatch rejected | `test_artifact_hash_mismatch_is_rejected_and_nothing_advances`, `…hash_is_over_the_exact_stored_bytes…`, `test_missing_artifact_and_malformed_references`, `test_binding_mismatches_…`, API `test_hash_mismatch_is_caught_when_the_publisher_loads_the_artifact` |
| 7 | API cannot accept arbitrary RTDB paths | `test_arbitrary_database_writes_are_not_expressible`, `test_api_rejects_arbitrary_paths_and_mutation_json_on_artifact_submission`, `test_artifact_params_cannot_smuggle_content_or_paths`, `test_artifact_reference_is_bounded_and_canonical` |
| 8 | API cannot accept arbitrary mutation JSON | same (`mutations`, `updates`, `value`, `plan`, `artifact` rejected) + `test_every_defined_action_has_a_param_schema_and_no_schema_field_looks_like_a_path_or_payload` |
| 9 | Brain may reference only its own namespace | `test_a_brain_may_reference_only_its_own_artifact_namespace`, `test_specialist_access_is_create_only_in_its_own_prefix`, `test_artifact_writer_refuses_other_brains_and_conflicting_rewrites`, `test_publisher_access_reads_artifacts_and_creates_history_only` |
| 10 | Wind cannot submit Fish artifact namespace | `test_wind_cannot_submit_a_fish_artifact_namespace` (three variants: foreign location → `NAMESPACE_VIOLATION`; submitting as Fish → 403; unscoped grant still bound to namespace) |
| 11 | retrieval feeds the same validation path | `test_artifact_retrieval_feeds_the_same_validation_path` (cross-domain, lifecycle, fingerprint, lineage, schema, null), `test_reference_flow_*` |
| 12 | shadow remains incapable of live write | all of `test_publisher_boundary.py` (now also lints `refs.py`, `handoff.py`), `test_shadow_reference_flow_has_no_live_capability`, `test_dry_run_reference_flow_persists_nothing` |
| 13 | atomic patch deterministic | `test_atomic_patch_remains_deterministic_through_the_reference_flow`, `test_wind_plan_is_deterministic_across_independent_runs`, `test_patch_generation_is_deterministic` |
| 14 | existing tests keep passing | whole suite: 130 pre-existing + first-round tests (3 first-round tests were deliberately changed: new storage key layout, `/brains/wind` now `BRAIN_NODE_REPLACEMENT`, `evaluate_stored` replaced by `evaluate_reference`) |

**Defect found by the new tests and fixed:** the plan's embedded publication record contained `pathSha256`, a map keyed by full paths. `/` is not a legal RTDB node key, so a live write would have failed. First-round tests did not apply a plan to a store. Fixed in `plan.py` (history-only fields omitted from the RTDB node; `check_update` run on every plan) with a regression test.
