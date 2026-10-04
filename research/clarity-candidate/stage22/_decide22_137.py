"""Stage 22 PREREGISTRATION section 7: Decision B, Stage 12 retirement from the nominal-S2C lower-authority path
(N0511/N0512/N0513 and newer nominal baselines). R = the frozen candidate (cand22.json); if it fails, A (raw) is the only
fallback. Inputs: secchi22.json (all S2C truth rows, pools dev/cert/fresh) and eval22.json (held-out TH and T2H pairs).
Writes decide22.json."""
import json, os
S = os.environ["CLARITY_RESEARCH_ROOT"]
Q = json.load(open(f"{S}/stage22/secchi22_137.json")); E = json.load(open(f"{S}/stage22/eval22.json")); SEL = json.load(open(f"{S}/stage22/cand22.json"))["selected"]
PAIRV = {"A": "A", "C3": "C3", "C1": "C1", "K2": "B", "B_stage12": "S12"}          # secchi variant -> pair-evaluation version


def test(R):
    a = Q["pools"]["all"]; r, b = a[R], a["B_stage12"]
    th, t2 = E["sets"]["TH"], E["sets"]["T2H"]; pr, pb = PAIRV[R], "S12"
    c = {"1_bias": abs(r["signed_log_bias_median"]) <= abs(b["signed_log_bias_median"]) - 0.02, "2_harmful": r["harmful"] <= b["harmful"], "3_severe": r["severe"] <= b["severe"],
         "4_operational": r["operational"] >= b["operational"] - 0.02, "5_coverage": r["interval_coverage"] >= b["interval_coverage"] - 0.02,
         "6_state_TH": th[pr]["state_overlap"] >= th[pb]["state_overlap"] - 0.03, "6_state_T2H": t2[pr]["state_overlap"] >= t2[pb]["state_overlap"] - 0.03}
    pools = {}
    for pool in ("dev", "cert", "fresh"):
        rp, bp = Q["pools"][pool][R], Q["pools"][pool]["B_stage12"]
        pools[pool] = abs(rp["signed_log_bias_median"]) <= abs(bp["signed_log_bias_median"]) + 0.03 and rp["harmful"] <= bp["harmful"] + 0.05
    c["7_pools"] = all(pools.values()); c["7_dp_TH"] = abs(th[pr]["dp_median"]) <= 0.05; c["7_dp_T2H"] = abs(t2[pr]["dp_median"]) <= 0.05
    return {"criteria": c, "pools": pools, "passed": all(c.values()),
            "values": {"R": {k: r[k] for k in ("signed_log_bias_median", "harmful", "severe", "operational", "interval_coverage")}, "Stage12": {k: b[k] for k in ("signed_log_bias_median", "harmful", "severe", "operational", "interval_coverage")},
                       "TH": {"R_state": th[pr]["state_overlap"], "S12_state": th[pb]["state_overlap"], "R_dp": th[pr]["dp_median"]}, "T2H": {"R_state": t2[pr]["state_overlap"], "S12_state": t2[pb]["state_overlap"], "R_dp": t2[pr]["dp_median"]}}}


out = {"selected": SEL, "tests": {SEL: test(SEL)}}
if not out["tests"][SEL]["passed"]: out["tests"]["A"] = test("A")
win = next((k for k, v in out["tests"].items() if v["passed"]), None)
out["RETIRE_STAGE12"] = win is not None; out["replacement"] = win
out["scope"] = "nominal operational S2C: N0511, N0512, N0513 and newer nominal equivalents; preliminary N9905/N9906 research products untouched"
json.dump(out, open(f"{S}/stage22/decide22_137.json", "w"), indent=1)
for k, v in out["tests"].items(): print(k, "PASSED" if v["passed"] else "failed", v["criteria"], v["values"])
print("RETIRE STAGE 12:", out["RETIRE_STAGE12"], "replacement", win)
