"""Rule ablation for the v1.1 extensions: number of bound lakes (core + flagged class, before R7h and history) with all v1.1 rules ON, with each rule removed, and with each rule alone on top of v1."""
import json, collections
from common2 import *
import verify2 as W2, verify11 as V11
RULES = ("R1b", "R2b", "R2c", "R2d", "R4b", "R5b", "R8b", "R8c", "RGL", "RI", "R1c")
BOUND = ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG")
def count(fl):
    res, lakes, rows, cands = W2.run(fl)
    b = V11.best_per_lake(res)
    core = {k for k, v in b.items() if v["status"] in ("VERIFIED", "VERIFIED_CORROBORATED")}
    flag = {k for k, v in b.items() if v["status"] == "VERIFIED_FLAG"}
    return core, flag
allon = {r: 1 for r in RULES}; alloff = {r: 0 for r in RULES}
out = {}
c, f = count(alloff); out["v1_only"] = dict(core=len(c), flag=len(f), bound=len(c | f)); base = c | f
c, f = count(allon); out["all_on"] = dict(core=len(c), flag=len(f), bound=len(c | f)); full = c | f
for r in RULES:
    c, f = count({**allon, r: 0}); out[f"minus_{r}"] = dict(core=len(c), flag=len(f), bound=len(c | f), marginal=len(full) - len(c | f), lost=sorted(full - (c | f)))
    c, f = count({**alloff, r: 1}); out[f"only_{r}"] = dict(core=len(c), flag=len(f), bound=len(c | f), gain=len((c | f) - base), lakes=sorted((c | f) - base))
json.dump(out, open(f"{B2}/ablation.json", "w"), indent=1)
for k, v in out.items():
    print(k, {a: b for a, b in v.items() if a not in ("lost", "lakes")}, v.get("lost") or v.get("lakes") or "")
