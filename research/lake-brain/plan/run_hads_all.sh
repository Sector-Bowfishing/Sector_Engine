#!/bin/bash
# stage 1: stations with no alternative long source -> full 2011..2026 ; stage 2: USGS-relay stations -> most recent 3-year chunk only (agreement check)
PY=/private/tmp/claude-501/-Users-mcather-Desktop-Development-Sector-Engine/0ae627cc-66ac-4d1d-95fb-676dff164f5a/scratchpad/venv/bin/python
cd /Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/plan
export HADS_SLEEP=12
FULL="LKPA3,WWCG1,TIGG1,WDMG1,SNCG1,CODI2,DKLI2,JRLK1,LKSM7,BADN7,HGRN7,CNDN6,CAYN6,KKPN6,CLEN6,GNVN6,CNLO2,KAWO2,TENO2,SKLO2,SCIR1,BBDS2,GPDN1,MOOV2,PETW3,UTEN5"
RECENT="BRTA3,PSLI1,DIXK2,LDBL1,FFCQ6,TOPN2,INDN6"
$PY hads_fetch.py "$FULL"
$PY hads_fetch.py "$RECENT" --from 2024
