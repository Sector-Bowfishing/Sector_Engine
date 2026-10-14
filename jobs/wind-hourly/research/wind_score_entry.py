"""Generate the Engine score block for Wind FROM THE CANONICAL SCORER (never typed by hand).

  python research/wind_score_entry.py --refresh --emit PATH_TO_FROZEN_SCORES.json [--record RECORD.json]

1. (--refresh) re-pull operational metadata (ledger, run summaries, executions, Brain-publish status lines) - never forecast/obs values;
2. rebuild the ledger-derived metadata mirror and run `sector_wind.scoreboard.compute` (frozen rubric v1) and `sector_wind.bowfishing_score` (BWIS v1);
3. write the platform score block for `wind` into a copy of frozen-scores.json (every other entry byte-identical) and a publication record.
The rubric, thresholds and evidence files are untouched; H2 stays sealed (skill dimensions read the frozen CAL+H1 evidence file only)."""
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
R = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/wind-brain"); META = R + "/live-meta"; B = "gs://sector-wind-candidate/wind/v1"
DOCS = os.path.expanduser("~/Desktop/Development/iOS/sector-wind/docs/intelligence/wind")
sh = lambda c, **k: subprocess.run(c, shell=True, capture_output=True, text=True, **k)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
args = sys.argv[1:]
emit = args[args.index("--emit") + 1]; record = args[args.index("--record") + 1] if "--record" in args else None
now = datetime.now(timezone.utc)
if "--refresh" in args:
    for sub in ("ledger", "runs"):
        sh(f"mkdir -p {META}/{sub} && gcloud storage rsync -r {B}/{sub} {META}/{sub}")
    sh(f"gcloud run jobs executions list --job wind-hourly --region us-central1 --limit 800 --format=json > {META}/executions.json")
    sh(f"""gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="wind-hourly" AND textPayload:"windbrain"' --limit 1000 --freshness=30d --format=json > {META}/brainlogs.json""")
import live_reliability as LR, live_metadata_mirror as LM
rel = LR.audit(META, now)["summary"]
LM.build(META, R + "/live-meta-mirror")
out_json = f"{R}/out/score_refresh_{now:%Y%m%dT%H%MZ}.json"
r = sh(f"{sys.executable} {HERE}/canonical_rescore.py {R}/live-meta-mirror {out_json}", cwd=ROOT)
if r.returncode:
    raise SystemExit("scorer failed: " + r.stderr[-500:])
res = json.load(open(out_json)); c = res["certification"]
dims = c["dimensions"]
breakdown = {}
for k, d in dims.items():
    breakdown[d["name"]] = {"value": round(10 * d["credit"], 2), "weight": d["weight"], "points": d["points"],
                           "status": "SCORED", "evidence": d["why"]}
blockers = [{"gate": "fieldValidation", "cap": cp["cap"], "why": cp["rule"] + " (certification cap; not binding while the score is below the cap)"} for cp in c["caps"]]
blockers += [{"gate": "liveReliability", "why": f"{rel['validArchiveDays']} of 30 valid live archive days; projected gate {rel['projectedArchiveGate']}"},
             {"gate": "h2", "why": "H2 holdout sealed until 2027-01-01; no live skill is scored before then"},
             {"gate": "rubric", "why": "dimension 1 and 3 event gates (>= 15 mph, >= 20 kt) score 0; exposure and surface (40 pts) need bank-pair truth"}]
entry = {"value": c["new"], "scale": 10, "basis": "COMPUTED", "scoreVersion": "wind-certification-rubric-v1",
         "scoreRubric": "frozen rubric v1 (code-derived scoreboard: jobs/wind-hourly/sector_wind/scoreboard.py) - evidence: frozen CAL+H1 skill file + live reliability ledger metadata",
         "scoreUpdatedAt": res["computedAt"], "completenessPct": 100, "uncapped": c["newRaw"], "rawPoints": c["rawPoints"],
         "scoreBreakdown": breakdown, "scoreBlockers": blockers,
         "nextScoreOpportunity": "Reliability grows automatically with valid live days (dimension 8, +8 at 30 days); bank-scale exposure + surface validation under Evidence Addendum v1 (dimensions 6/7, +40) and an over-water reference are the other movers",
         "secondary": {"bowfishingWindIntelligenceScore": res["bwis"]["new"], "definition": "BWIS v1 (frozen definition sha256 21e2a326...)", "total": res["bwis"]["newTotal"]},
         "note": "certification score of the candidate pipeline, not of production wind (customers get Open-Meteo Best Match)",
         "evidence": {"metadataThrough": rel["asOf"], "validArchiveDays": rel["validArchiveDays"], "evidenceFileSha": sha(DOCS + "/stage3a/evidence/v50_corpus_validation.json"),
                      "scorerCode": subprocess.run("git rev-parse --short HEAD", shell=True, cwd=ROOT, capture_output=True, text=True).stdout.strip()}}
txt = open(emit).read(); fz = json.loads(txt); old = fz.get("wind", {})
# splice ONLY the wind object into the original text so every other entry stays byte-identical (formatting included)
i = txt.index('"wind": {'); j = txt.index("{", i); depth, k, instr, esc = 0, j, False, False
while True:
    ch = txt[k]
    if instr:
        esc = (not esc) and ch == "\\"
        if ch == '"' and not esc: instr = False
    else:
        if ch == '"': instr = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: break
    k += 1
block = json.dumps(entry, indent=2, ensure_ascii=False).replace("\n", "\n  ")
open(emit, "w").write(txt[:j] + block + txt[k + 1:])
assert {x: y for x, y in json.load(open(emit)).items() if x != "wind"} == {x: y for x, y in fz.items() if x != "wind"}
rec = {"publishedAtPlanned": None, "scorerComputedAt": res["computedAt"], "oldPublished": {"value": old.get("value"), "basis": old.get("basis"), "scoreUpdatedAt": old.get("scoreUpdatedAt")},
       "new": {"value": entry["value"], "raw": c["newRaw"], "rawPoints": c["rawPoints"], "basis": entry["basis"], "scoreVersion": entry["scoreVersion"]},
       "bwis": {"previous": res["bwis"]["previous"], "new": res["bwis"]["new"], "total": res["bwis"]["newTotal"]},
       "dimensionChanges": c["dimensionsChanged"], "dimensionsUnchanged": c["dimensionsUnchanged"], "caps": c["caps"], "evidence": entry["evidence"], "reliability": rel}
if record:
    json.dump(rec, open(record, "w"), indent=1, default=str)
print(json.dumps({"old": rec["oldPublished"], "new": rec["new"], "bwis": rec["bwis"], "dimensionChanges": rec["dimensionChanges"]}, indent=1, default=str))
