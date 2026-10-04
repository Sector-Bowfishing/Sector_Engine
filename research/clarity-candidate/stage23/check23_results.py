"""Every task's variant files exist, parse as JSON, and carry no crop-level runner error. -> rerun list (results removed first)."""
import json, os, sys
S = os.environ["CLARITY_RESEARCH_ROOT"]; task, resdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
bad = []
for t in json.load(open(f"{S}/stage23/{task}")):
    ok = True
    for v in t["variants"]:
        f = f"{S}/stage23/{resdir}/{t['run']}__{v}.json"
        try:
            d = json.load(open(f))
            if any(c.get("error") for c in d.get("crops", [])): ok = False
        except Exception: ok = False
    if not ok:
        bad.append(t)
        for v in t["variants"]:
            f = f"{S}/stage23/{resdir}/{t['run']}__{v}.json"
            if os.path.exists(f): os.replace(f, f + ".bad")
json.dump(bad, open(f"{S}/stage23/{out}", "w")); print(task, "to re-run:", len(bad), [t["run"] for t in bad][:10])
