#!/bin/zsh
# Scratch-bucket proof of lake_brain_bucket_lifecycle_proposed.json semantics.
# NEVER touches gs://sector-lake-brain. Only creates/uses/deletes gs://sector-lake-brain-lifecycle-scratch-<random>.
#   lifecycle_scratch_test.sh setup      -> creates the scratch bucket (versioned, same settings as the real one), fills it, applies the rule file
#                                           with every day threshold set to 0 (GCS: age 0 is satisfied at the next midnight UTC after creation;
#                                           a config change can take up to 24 h to take effect; the run itself is asynchronous)
#   lifecycle_scratch_test.sh verify B   -> prints every object version, LIVE or NONCURRENT, then PASS/FAIL against the expectation below
#   lifecycle_scratch_test.sh teardown B -> deletes the bucket and its contents
# EXPECTATION once the lifecycle ran: baselines-archive/* gone (live version made noncurrent, then removed);
#   the noncurrent generation of baselines/Lake_A/latest.json gone; the noncurrent generation of history/Lake_A/daily.csv gone;
#   UNCHANGED: live baselines/Lake_A/latest.json, live legacy baselines/ object, live history/Lake_A/daily.csv, history_backup/, presence/,
#   predictions/ (BOTH generations of the overwritten ledger object: the history rule must not match predictions/), decoy prefixes.
set -e
HERE=${0:A:h}
RULES=$HERE/lake_brain_bucket_lifecycle_proposed.json
case "$1" in
setup)
  B=sector-lake-brain-lifecycle-scratch-$(python3 -c "import secrets;print(secrets.token_hex(3))")
  gcloud storage buckets create gs://$B --project=sector-9393c --location=us-central1 --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update gs://$B --versioning
  T=$(mktemp -d); echo '{"x":1}' > $T/a1.json; echo '{"x":2}' > $T/a2.json
  put(){ gcloud storage cp $T/$1.json gs://$B/$2 --content-type=application/json >/dev/null; }
  put a1 baselines/Lake_A/latest.json; put a2 baselines/Lake_A/latest.json; put a1 baselines/Lake_A/legacy_doy15_old.json
  put a1 baselines-archive/Lake_A/ver1.json; put a2 baselines-archive/Lake_A/ver2.json
  put a1 history/Lake_A/daily.csv; put a2 history/Lake_A/daily.csv; put a1 history_backup/Lake_A/daily.x.csv
  put a1 presence/latest.json; put a1 predictions/2026/10/13/p.jsonl; put a2 predictions/2026/10/13/p.jsonl
  put a1 history-baselines/decoy.json; put a1 baselines-archive-keep/Lake_A/keep.json; put a1 history2/decoy.csv
  python3 - $RULES $T/zero.json <<'P'
import json,sys
d=json.load(open(sys.argv[1]))
for r in d["rule"]:
    c=r["condition"]
    if "age" in c: c["age"]=0
    if "daysSinceNoncurrentTime" in c: c["daysSinceNoncurrentTime"]=0
json.dump(d,open(sys.argv[2],"w"))
P
  gcloud storage buckets update gs://$B --lifecycle-file=$T/zero.json
  date -u +"lifecycle applied (all thresholds 0) at %Y-%m-%dT%H:%M:%SZ"
  echo "scratch bucket: $B" ;;
verify)
  gcloud storage ls -a -r --json gs://$2/ | python3 -c "
import json,sys
objs=[(o['metadata']['name'],o['metadata']['generation'],bool(o['metadata'].get('timeDeleted'))) for o in json.load(sys.stdin) if o.get('metadata')]
for n,g,nc in sorted(objs): print(n,g,'NONCURRENT' if nc else 'LIVE')
live={n for n,g,nc in objs if not nc}; nonc=[n for n,g,nc in objs if nc]
must_live={'baselines/Lake_A/latest.json','baselines/Lake_A/legacy_doy15_old.json','history/Lake_A/daily.csv','history_backup/Lake_A/daily.x.csv','presence/latest.json','predictions/2026/10/13/p.jsonl','history-baselines/decoy.json','baselines-archive-keep/Lake_A/keep.json','history2/decoy.csv'}
print('live protected objects present:', must_live<=live)
print('predictions generations intact (2):', sum(1 for n,g,nc in objs if n.startswith('predictions/'))==2)
ran=not any(n.startswith('baselines-archive/') for n in live) and not any(n in ('baselines/Lake_A/latest.json','history/Lake_A/daily.csv') for n in nonc)
print('LIFECYCLE HAS RUN (archive gone, noncurrent latest/history gone):', ran)
"
  ;;
teardown) gcloud storage rm -r gs://$2 ;;
*) sed -n 2,13p $0 ;;
esac
