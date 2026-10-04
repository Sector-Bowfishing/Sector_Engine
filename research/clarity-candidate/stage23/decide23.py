"""Stage 23 section 8 (PREREGISTRATION_STAGE23.md): the authority decision from eval23.json (sections 3-6, sensor-to-sensor)
and secchi23.json (section 7). Writes decide23.json."""
import json, os, hashlib
S = os.environ["CLARITY_RESEARCH_ROOT"]
F = json.load(open(f"{S}/stage23/FREEZE_STAGE23.json"))
assert hashlib.sha256(open(f"{S}/stage23/PREREGISTRATION_STAGE23.md", "rb").read()).hexdigest() == F["prereg_sha256"]
E = json.load(open(f"{S}/stage23/eval23.json")); Q = json.load(open(f"{S}/stage23/secchi23.json"))
sd = E["sensor_decision"]; sq = Q["checks_sun_ge25"]
if not (sd["floor_usable"] and sd["TH25"]): outcome = "B"
elif sd["T2H25"] and sd["T2N"] and all(sd["baselines"].values()) and sq["PASSED"]: outcome = "A"
else: outcome = "C"
why = []
if not sd["floor_usable"]: why.append("floor not usable")
if not sd["TH25"]: why.append("TH25 failed: " + ", ".join(k for k, v in E["strata"]["TH25"]["criteria"].items() if not v))
for s_ in ("T2H25", "T2N"):
    if not sd[s_]: why.append(f"{s_} failed: " + ", ".join(k for k, v in E["strata"][s_]["criteria"].items() if not v))
for b, v in sd["baselines"].items():
    if not v: why.append(f"{b}: " + ", ".join(k for k, x in E["baselines"][b]["criteria"].items() if not x))
for k in ("harmful_le_ref_plus_0.05", "severe_le_0.02", "bias_within_0.05_of_ref"):
    if not sq[k]: why.append(f"Secchi >= 25: {k} failed ({sq['values']})")
out = {"outcome": outcome, "label": {"A": "CONDITIONAL FULL AUTHORITY", "B": "LOWER AUTHORITY", "C": "PARTIAL / DIRECTIONAL"}[outcome],
       "sensor": sd, "secchi_checks": sq, "reasons": why, "low_sun_authority": "LOWER",
       "scope": "nominal S2C C3 (N0511, N0512, N0513 and later nominal equivalents), sun >= 25 deg, all normal quality gates"}
json.dump(out, open(f"{S}/stage23/decide23.json", "w"), indent=1)
print("OUTCOME", outcome, out["label"]); [print(" -", w) for w in why]
