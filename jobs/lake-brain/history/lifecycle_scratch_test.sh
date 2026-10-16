#!/bin/zsh
# Scratch-bucket proof of baselines_lifecycle.json semantics (never touches gs://sector-lake-brain).
#   lifecycle_scratch_test.sh setup     -> creates gs://sector-lake-brain-scratch-<rand> (versioned), fills it, applies the rule file
#                                          with all day thresholds set to 0 (so the next GCS lifecycle run, up to ~24 h later, acts)
#   lifecycle_scratch_test.sh verify B  -> prints every object version and whether it is LIVE or NONCURRENT
#   lifecycle_scratch_test.sh teardown B-> deletes the bucket
# EXPECTED after the lifecycle ran: baselines-archive/* no longer LIVE then gone; the noncurrent baselines/Lake_A/latest.json
# generation gone; EVERYTHING else (live latest.json, legacy baselines object, history/ both generations, history_backup/,
# presence/, predictions/, decoy prefixes) unchanged.
set -e
HERE=${0:A:h}
case "$1" in
setup)
  B=sector-lake-brain-scratch-$(python3 -c "import secrets;print(secrets.token_hex(3))")
  gcloud storage buckets create gs://$B --project=sector-9393c --location=us-central1 --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update gs://$B --versioning
  T=$(mktemp -d); echo '{"x":1}' > $T/a1.json; echo '{"x":2}' > $T/a2.json
  put(){ gcloud storage cp $T/$1.json gs://$B/$2 --content-type=application/json >/dev/null; }
  put a1 baselines/Lake_A/latest.json; put a2 baselines/Lake_A/latest.json; put a1 baselines/Lake_A/legacy_doy15_old.json
  put a1 baselines-archive/Lake_A/ver1.json; put a2 baselines-archive/Lake_A/ver2.json
  put a1 history/Lake_A/daily.csv; put a2 history/Lake_A/daily.csv; put a1 history_backup/Lake_A/daily.x.csv
  put a1 presence/latest.json; put a1 predictions/Lake_A/p.json; put a1 history-baselines/decoy.json; put a1 baselines-archive-keep/Lake_A/keep.json
  python3 - $HERE/baselines_lifecycle.json $T/zero.json <<'P'
import json,sys
d=json.load(open(sys.argv[1]))
for r in d["rule"]:
    c=r["condition"]
    if "age" in c: c["age"]=0
    if "daysSinceNoncurrentTime" in c: c["daysSinceNoncurrentTime"]=0
json.dump(d,open(sys.argv[2],"w"))
P
  gcloud storage buckets update gs://$B --lifecycle-file=$T/zero.json
  echo "scratch bucket: $B" ;;
verify)
  gcloud storage ls -a -r --json gs://$2/ | python3 -c "
import json,sys
for o in json.load(sys.stdin):
    m=o.get('metadata')
    if m: print(m['name'], m['generation'], 'LIVE' if not m.get('timeDeleted') else 'NONCURRENT')" ;;
teardown) gcloud storage rm -r gs://$2 ;;
*) sed -n 2,12p $0 ;;
esac
