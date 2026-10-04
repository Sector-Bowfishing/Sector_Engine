"""Stage 23 tooling check: the S2C C1 offsets (B11 from the tile's own clear-pixel median, B12 constant) computed from a LAZY
Google Cloud SAFE must equal those Stage 22 computed from the full download (res22_T2 C1 toa_sub). Two Stage 22 T2 S2C scenes."""
import json, os, sys, glob
S = os.environ["CLARITY_RESEARCH_ROOT"]; sys.path[:0] = [f"{S}/stage23", f"{S}/stage21", f"{S}/stage11/tools"]
import run_aco23 as RA, lazy23 as LZ
out = []
for f in sorted(glob.glob(f"{S}/stage22/res22_T2/T2_C_*__C1.json"))[:2]:
    d = json.load(open(f)); name = d["source"]; old = d["toa_sub"]
    inp = LZ.build(name, f"{S}/stage23/lazy_check"); new = RA.offsets(inp); LZ.delete(name, f"{S}/stage23/lazy_check")
    out.append({"product": name, "old": old, "new": {b: new[b] for b in old}, "max_abs_diff": max(abs(old[b] - new[b]) for b in old)}); print(out[-1], flush=True)
json.dump({"checks": out, "identical": all(c["max_abs_diff"] == 0 for c in out)}, open(f"{S}/stage23/check23_offsets.json", "w"), indent=1)
print("IDENTICAL", all(c["max_abs_diff"] == 0 for c in out))
