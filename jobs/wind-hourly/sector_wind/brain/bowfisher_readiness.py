"""Read-only BOWFISHER WIND READINESS scorecard. NOT the canonical score and never published as one.

Three things are tracked separately: the canonical score (official, owned by the scorer + shared orchestrator), per-capability claim maturity,
and this practical view. The headline answers one question: would I use this before choosing which side of the lake to bowfish?
Maturity words: READY / VERIFIED / VALIDATED (done) > CALIBRATION / IN_PROGRESS (evidence accumulating) > NOT_VALIDATED / WITHHELD (do not rely)."""
from __future__ import annotations

DONE = ("READY", "VERIFIED", "VALIDATED")
ACCUMULATING = ("IN_PROGRESS", "CALIBRATION")

CAPABILITIES = (  # key, label, claim level, layer
    ("providerSpeed", "Provider wind speed", 1, 1), ("providerDirection", "Provider wind direction", 1, 1), ("providerGust", "Provider gust (display)", 1, 1),
    ("forecastReliability", "Forecast reliability (prospective)", 2, 2), ("fetch", "Fetch / direction relative to bank", 2, 3),
    ("bankExposure", "Bank exposure (protected / partial / exposed)", 3, 3), ("surfaceChop", "Surface / chop (calm / moderate / rough)", 3, 4),
    ("tonight", "Tonight recommendation", 3, 5), ("confidenceRefusal", "Confidence and refusal (UNKNOWN works)", 2, 5),
)
REQUIRED_FOR_YES = ("providerSpeed", "providerDirection", "forecastReliability", "fetch", "bankExposure", "confidenceRefusal")


def build(maturity: dict, canonical: dict, reliability: dict, notes: dict | None = None) -> dict:
    notes = notes or {}
    rows = [{"key": k, "capability": lbl, "claimLevel": lvl, "layer": layer, "maturity": maturity.get(k, "NOT_VALIDATED"), "note": notes.get(k)} for k, lbl, lvl, layer in CAPABILITIES]
    m = {r["key"]: r["maturity"] for r in rows}
    if all(m[k] in DONE for k in REQUIRED_FOR_YES) and m["surfaceChop"] in DONE + ("WITHHELD",):
        answer, why = "YES", "Every required capability is verified or validated and surface is validated or honestly withheld."
    elif all(m[k] in DONE + ACCUMULATING for k in ("providerSpeed", "providerDirection", "fetch")) and m["providerSpeed"] in DONE and m["providerDirection"] in DONE:
        lacking = [r["capability"] for r in rows if r["key"] in REQUIRED_FOR_YES and r["maturity"] not in DONE]
        answer, why = "PARTIALLY", "Trust the wind (speed, direction, gust display) and the shoreline geometry; treat bank calls as advisory until validated. Not yet done: " + "; ".join(lacking) + "."
    else:
        answer, why = "NO", "Provider wind is not verified."
    return {"schema": "bowfisher-wind-readiness-v1", "isCanonical": False, "wouldUseToChooseSide": answer, "because": why, "capabilities": rows,
            "canonicalScore": canonical, "reliability": reliability,
            "separation": "canonical score = official value; readiness = practical capability; claim maturity = per capability. Never substitute one for another."}


def render(r: dict) -> str:
    L = [f"# Bowfisher Wind Readiness (read-only; NOT the canonical score)", "",
         f"**Would I use this before choosing which side of the lake to bowfish? {r['wouldUseToChooseSide']}**", "", r["because"], "",
         "| Layer | Capability | Claim level | Maturity | Note |", "|---:|---|---:|---|---|"]
    L += [f"| {c['layer']} | {c['capability']} | {c['claimLevel']} | {c['maturity']} | {c['note'] or ''} |" for c in sorted(r["capabilities"], key=lambda c: c["layer"])]
    L += ["", f"Canonical score: {r['canonicalScore']}", f"Reliability: {r['reliability']}"]
    return "\n".join(L) + "\n"
