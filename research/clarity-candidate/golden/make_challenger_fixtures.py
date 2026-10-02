"""Reference outputs for the frozen Stage 17 challenger, from the frozen code itself.

Runs the frozen stage17/analysis/dev17.py prefix exactly as stage18/freeze18.py does (development data, outer-fold scene
predictions), then calls dev17's own build() for every development event with the FROZEN challenger parameters
(stage18/engine/challenger17.json: sigma by tier, kappa, n=2 / n>=3 posteriors) and rule16's posteriors - the Stage 18
challenger, M-iuw +-10 d, H0, S-off. Writes golden/challenger17_fixtures.json: per event, the contributing scene list
(the inputs), the Stage 16 product it falls back to, and build()'s output. A port of the challenger (the shadow job's)
must reproduce every output exactly.
  geo/bin/python golden/make_challenger_fixtures.py"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["CLARITY_RESEARCH_ROOT"] = ROOT
S = ROOT
src = open(f"{S}/stage17/analysis/dev17.py").read().split("RES = {}")[0]
sys.argv = ["dev17.py"]; ns = {"__name__": "challenger_fixtures"}; exec(compile(src, "dev17_prefix", "exec"), ns)
EVENTS, build, scene_list, evidence = ns["EVENTS"], ns["build"], ns["scene_list"], ns["evidence"]
CH = json.load(open(f"{S}/stage18/engine/challenger17.json")); R16 = json.load(open(f"{S}/stage16/engine/rule16.json"))
par = {"sig": {int(k): v for k, v in CH["sigma_tier"].items()}, "kappa": CH["kappa_per_day"]}
post = {"post1": {int(b): tuple(v) for b, v in R16["post1"].items()}, "post2": {int(b): tuple(v) for b, v in R16["post2"].items()}}
cal = {"n2": {int(b): tuple(v) for b, v in CH["posteriors_n2"].items()}, "n3": {int(b): tuple(v) for b, v in CH["posteriors_n3"].items()}}
out = []
for e in EVENTS:
    key = (e["id"], "outer", e["fold"])
    sc = scene_list(e, key, 10, "H0", "S-off")
    o = build(e, key, "M-iuw", 10, "H0", "S-off", par, post, cal)
    out.append({"id": e["id"], "scenes": sc, "base": ns["B16"][e["id"]]["o"], "out": json.loads(json.dumps(o, default=str)), "evidence": evidence(o)})
json.dump({"note": __doc__.split("\n\n")[1], "n": len(out), "fixtures": out}, open(f"{S}/golden/challenger17_fixtures.json", "w"))
print(len(out), "events;", sum(1 for f in out if f["out"].get("consensus")), "consensus;", sum(1 for f in out if f["out"].get("n_use", 0) >= 2), "with >= 2 scenes")
