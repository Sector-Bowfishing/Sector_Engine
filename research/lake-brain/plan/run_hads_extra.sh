#!/bin/bash
PY=/private/tmp/claude-501/-Users-mcather-Desktop-Development-Sector-Engine/0ae627cc-66ac-4d1d-95fb-676dff164f5a/scratchpad/venv/bin/python
cd /Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/plan
while pgrep -f "hads_fetch.py PETW3" >/dev/null; do sleep 30; done
export HADS_SLEEP=15
$PY hads_fetch.py "FFCQ6"
$PY hads_fetch.py "NKJT1,TMFT1" --from 2022
