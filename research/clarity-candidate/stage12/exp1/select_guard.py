"""Stage 12 Part 1 inland-turbidity guard sample (fixed before any Stage 12 result): corpus rows with same-day
satellite pass and same-day in-situ turbidity, dated <= 2025-12-31, not Guntersville (set G, or inside the
Guntersville box used in Stage 11), one row per lake group, random order with seed 12, first 60.
Also lists the Stage 11 representative stations that are not Guntersville. Writes guard.json."""
import json, random
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
rows = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]
def gunt(x):
    return x["set"] == "G" or (34.27 <= x["lat"] <= 35.06 and -86.42 <= x["lon"] <= -85.60)
cand = [x for x in rows if x.get("turb") is not None and x.get("dt") == 0 and not gunt(x)]
cand.sort(key=lambda x: x["id"]); random.Random(12).shuffle(cand)
seen, pick = set(), []
for x in cand:
    if x["lake"] in seen: continue
    seen.add(x["lake"]); pick.append(x)
    if len(pick) == 60: break
jobs = {}
for x in pick:
    jobs[f"guard_{x['id'].replace(':', '_').replace('|', '_')}"] = {"job": f"guard_{x['id'].replace(':', '_').replace('|', '_')}", "c1": x["item"],
        "lat": x["lat"], "lon": x["lon"], "points": [[x["lat"], x["lon"], x["id"]]]}
repr_jobs = [j for j in json.load(open(f"{S}/stage11/ac/jobs_repr.json")) if "guntersville" not in j["classes"]]
byid = {x["id"]: x for x in rows}
repr_keep = []
for j in repr_jobs:
    pts = [p for p in j["points"] if p[2] in byid and not gunt(byid[p[2]])]
    if pts: repr_keep.append({**j, "points": pts})
json.dump({"guard": list(jobs.values()), "repr": repr_keep, "n_candidates": len(cand)}, open(f"{S}/stage12/exp1/guard.json", "w"), indent=1)
print(len(cand), "candidates;", len(jobs), "guard jobs;", len(repr_keep), "repr jobs,", sum(len(j["points"]) for j in repr_keep), "repr stations")
