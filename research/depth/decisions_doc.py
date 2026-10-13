"""Regenerate docs/brains/depth/DEPTH_MICHAEL_DECISIONS.md from the manifest + log. Deterministic."""
import json, os, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{ROOT}/jobs/depth-brain")
from depth_brain import maturity as M
man = json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/candidates.json"))
fm = M.fleet_metrics(man); ev = M.evaluate(man)
md = f"""# Decisions and actions for Michael (Depth Brain) - generated {datetime.date.today()}

Current: {fm['shiftPossible']} of {fm['totalLakes']} lakes shift-defensible ({fm['verifiedDatum']} verified datum, {fm['inferredOperatorSystem']} TVA inferred); {fm['highConfidence']} HIGH / {fm['mediumConfidence']} MEDIUM / {fm['blocked']} BLOCKED; {fm['pilotVerified']} live (pilot shadow state written 2026-10-14). Research maturity {ev['overall']} (research rubric; **not** an official score; official Depth score NOT_ESTABLISHED).

## Decided (2026-10-14)
| Decision | Outcome |
|---|---|
| Pilot-only shadow write | **Approved and done** (5 lakes; verified by read-back) |
| Control-plane shadow Brain | **Approved**; Engine code committed and verified against live data in dry run; **live `/control/overview` entry needs the control job redeployed (not authorised yet)** |
| `depth-brain-score-v1` | **Not ratified** (proposal only) |
| Orchestration | **Approved to prepare, not to schedule** (prepared, gated off) |
| Lake datum interface | **Approved** (`DEPTH_LAKE_DATUM_DEPENDENCY.md`) |
| MN DNR licence reclassification | **Stays proposed** (dedicated licensing decision later) |
| GLOBathy | Closed |

## Still open - decisions
| # | Decision | Recommendation |
|---|---|---|
| 1 | Redeploy the brain-scores/orchestrator control job from `feat/depth-brain-foundation` so `/control/overview.brains.depth` goes live | after the unmerged base `feat/cost-efficient-scheduling` is dispositioned; it is the prerequisite for any Depth deploy |
| 2 | Ops catalog/page change (Depth active shadow, new scope text) | `DEPTH_OPS_FOLLOWUP.md` |
| 3 | Enable orchestration (`DEPTH_ORCHESTRATION_ENABLED=1`, `/jobs` row) | after 1 and after two clean manual cycles |
| 4 | Dedicated licensing decision (MN first) | `DEPTH_LICENSING_UNLOCK_QUEUE.md` |
| 5 | Merge sequencing for `feat/cost-efficient-scheduling` | before any Depth merge |

## Still open - actions (people / outbound; NOTHING SENT)
| # | Action | Doc |
|---|---|---|
| 1 | Send the **Reclamation** datum confirmation (19 RISE rows) | `DEPTH_RECLAMATION_DATUM_REQUEST.md` |
| 2 | Send the **TVA** datum + bathymetry request | `DEPTH_TVA_DATUM_REQUEST.md` + `DEPTH_SOURCE_REQUEST_QUEUE.md` row 1 |
| 3 | Other datum confirmations (Duke 7, CNPPID, NHDES, SRP, USGS ID, USACE St. Louis/Tulsa) | `DEPTH_DATUM_CONFIRMATION_REQUESTS.md` |
| 4 | Southeast bathymetry requests | `DEPTH_SOURCE_REQUEST_QUEUE.md` |
| 5 | Recruit beta testers for field validation | `DEPTH_FIELD_VALIDATION_PACKETS.md` (Hartwell, Guntersville, Wheeler, Wilson, Pickwick, Fork, Cedar Creek, Gull Lake MN) |
| 6 | Survey-date water levels from contour owners (MN, OH, NE, ND, OK, KS) | `DEPTH_CONTOUR_SOURCE_REFERENCE_POOLS.md` |
| 7 | iOS owner: Guntersville IENC numbers (62% / 2,445 -> 67.2% / 2,133) | `DEPTH_IOS_IENC_CORRECTION.md` |

## Lake Brain (separate session)
{fm['shiftPossible'] - fm['pilotVerified']} defensible Depth lakes have no live Lake state; Lake datum stamping (TVA publishes null); 7 NWPS lakes need a Lake-side rebind (preserved in `DEPTH_LAKE_DATUM_DEPENDENCY.md`).
"""
open(f"{ROOT}/docs/brains/depth/DEPTH_MICHAEL_DECISIONS.md", "w").write(md)
print("ok")
