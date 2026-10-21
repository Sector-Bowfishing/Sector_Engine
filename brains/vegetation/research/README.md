# Vegetation research

Offline only. `tools/vegetation_research` builds the fleet observability manifest and the agency datasets (writing them changes the knowledge release: regenerate `runtime/knowledge/knowledge-release.json` with a new release id), runs the shared-pass pilot/fleet harnesses (dry-run only), holds the preregistered gates and the sealed holdout guard, and evaluates the research maturity rubric (never published). `tools/vegetation_research/records/` holds the rubric inputs and a frozen copy of the validation preregistration. `GAPS.json` lists open gaps.
