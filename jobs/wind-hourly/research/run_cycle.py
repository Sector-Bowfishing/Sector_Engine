"""One validation cycle (run at least weekly; read-only; H2 sealed):
   1. refresh OPERATIONAL METADATA from the live archive (ledger/run summaries, Cloud Run executions, Brain-publish status lines) - never forecast/obs values
   2. reliability audit (valid archive days, valid Brain-publish days, projected gates)
   3. ledger-derived metadata mirror -> CANONICAL rescore (Wind Certification + BWIS)
   4. Ops summary (what Engine would publish) written next to the results
   Results go to Sector_Research_Data/wind-brain/cycles/<UTC timestamp>/ and are printed; nothing is appended to the private score log and the
   Engine's published (frozen) score block is not touched.
  python research/run_cycle.py [--no-refresh]"""
import csv, json, os, subprocess, sys
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
R = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/wind-brain")
META = R + "/live-meta"; B = "gs://sector-wind-candidate/wind/v1"
now = datetime.now(timezone.utc); out = f"{R}/cycles/{now:%Y%m%dT%H%MZ}"; os.makedirs(out, exist_ok=True)
sh = lambda c, **k: subprocess.run(c, shell=True, check=False, capture_output=True, text=True, **k)
if "--no-refresh" not in sys.argv:
    for sub in ("ledger", "runs"):
        sh(f"mkdir -p {META}/{sub} && gcloud storage rsync -r {B}/{sub} {META}/{sub}")
    sh(f"gcloud run jobs executions list --job wind-hourly --region us-central1 --limit 800 --format=json > {META}/executions.json")
    sh(f"""gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="wind-hourly" AND textPayload:"windbrain"' --limit 1000 --freshness=30d --format=json > {META}/brainlogs.json""")
import live_reliability as LR, live_metadata_mirror as LM
rel = LR.audit(META, now); json.dump(rel, open(f"{out}/reliability.json", "w"), indent=1)
LM.build(META, R + "/live-meta-mirror")
sh(f"{sys.executable} {HERE}/canonical_rescore.py {R}/live-meta-mirror {out}/rescore.json", cwd=ROOT)
rescore = json.load(open(f"{out}/rescore.json"))
from sector_wind.brain import ops_summary as OS
frozen = json.load(open(os.path.join(ROOT, "..", "..", "docs", "brains", "scoring", "frozen-scores.json")))
fw = frozen.get("wind") or frozen.get("scores", {}).get("wind") or {}
cov = OS.coverage_from_manifest()
summ = OS.build(now, rescore=rescore, reliability=rel, frozen_score={"value": fw.get("value"), "basis": fw.get("basis", "FROZEN"), "updatedAt": fw.get("scoreUpdatedAt") or fw.get("updatedAt")}, coverage=cov,
                prerequisite_branch={"name": "feat/cost-efficient-scheduling", "merged": subprocess.run("git merge-base --is-ancestor origin/feat/cost-efficient-scheduling origin/main", shell=True, cwd=ROOT).returncode == 0})
json.dump(summ, open(f"{out}/ops_summary.json", "w"), indent=1)
s = rel["summary"]
print(f"cycle {now:%Y-%m-%d %H:%MZ}: valid archive days {s['validArchiveDays']}, brain days {s['validBrainPublishDays']}, failed executions {s['failedExecutions']}, stale {s['staleStatesLogged']}, "
      f"gates {s['projectedArchiveGate']} / {s['projectedBrainPublishGate']}")
c = rescore["certification"]; print(f"certification {c['previous']} -> {c['new']} (raw {c['newRaw']}), BWIS {rescore['bwis']['previous']} -> {rescore['bwis']['new']}; dims changed {list(c['dimensionsChanged'])}; caps {[x['cap'] for x in c['caps']]}")
print("results:", out)
