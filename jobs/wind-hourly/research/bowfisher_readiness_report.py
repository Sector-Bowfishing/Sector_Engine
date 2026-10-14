"""Write the read-only bowfisher readiness scorecard from the current facts. Does not touch the canonical score.
  python research/bowfisher_readiness_report.py OUT_DIR RELIABILITY_DAYS"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind.brain import bowfisher_readiness as BR

out, days = sys.argv[1], int(sys.argv[2])
maturity = {"providerSpeed": "VERIFIED", "providerDirection": "VERIFIED", "providerGust": "VERIFIED", "forecastReliability": "IN_PROGRESS", "fetch": "VALIDATED",
            "bankExposure": "CALIBRATION", "surfaceChop": "NOT_VALIDATED", "tonight": "CALIBRATION", "confidenceRefusal": "VERIFIED"}
notes = {"providerGust": "forecast runs low in strong wind; display only", "forecastReliability": f"{days}/30 prospective days",
         "bankExposure": "v2 rules frozen; field truth pending", "surfaceChop": "classes defined; field truth pending", "tonight": "internal only",
         "confidenceRefusal": "UNKNOWN for point-only / below-resolution / light wind / boundary banks"}
r = BR.build(maturity, {"displayed": 3.3, "raw": 3.29, "v2SimulationNonOfficial": 4.42}, {"validDays": days, "target": 30, "projectedGate": "2026-11-07"}, notes)
os.makedirs(out, exist_ok=True)
json.dump(r, open(os.path.join(out, "bowfisher_readiness.json"), "w"), indent=1)
open(os.path.join(out, "BOWFISHER_WIND_READINESS.md"), "w").write(BR.render(r)); print(BR.render(r))
