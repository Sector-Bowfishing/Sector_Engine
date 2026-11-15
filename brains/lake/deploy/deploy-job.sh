#!/usr/bin/env bash
#
# lake-brain Cloud Run job: RETIRED (B6, Sector_Ops #48/#51).
#
# The job ran LakeBrainJob as a direct database writer. That writer is retired: Lake runs on Pulse (catalog entry lake-central) via
# runtime/artifact_entry.py, which seals an artifact, and only the central Publisher writes Lake's paths. LakeBrainJob now refuses --rtdb,
# so a redeployed job could only fail. The previous script is in git history (before this change).
set -euo pipefail
echo "✗ lake-brain Cloud Run job retired (B6): Lake publishes through Pulse + the central Publisher. Nothing was deployed." >&2
exit 2
