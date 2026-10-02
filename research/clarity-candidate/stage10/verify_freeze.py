"""Re-check every frozen file against frozen_manifest.json and FREEZE.json before any fresh run."""
import hashlib, json, os, sys
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
E = os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion")
man = json.load(open(f"{S}/stage10/frozen_manifest.json")); fz = json.load(open(f"{S}/stage10/FREEZE.json"))
canon = hashlib.sha256(json.dumps(man, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
path = lambda k: (f"{E}/jobs/lake-surface/derive_water_surface.py" if "derive_water_surface" in k else
                  f"{E}/docs/data/hydrology/guntersville/stage3a/arm_positions.npz" if "arm_positions" in k else
                  f"{E}/docs/data/hydrology/guntersville/stage3a/arm_zones.json" if "arm_zones" in k else
                  f"{E}/docs/data/hydrology/guntersville/guntersville.arm_cells.json" if "arm_cells" in k else
                  f"{S}/" + k.split(" (")[0])
bad = [k for k, h in man["files"].items() if hashlib.sha256(open(path(k), "rb").read()).hexdigest() != h]
print("manifest", "OK" if canon == fz["manifestSha256"] else "CHANGED", canon[:16], "| frozen at", fz["frozenAtUTC"])
print("files", "all unchanged" if not bad else f"CHANGED: {bad}")
sys.exit(1 if bad or canon != fz["manifestSha256"] else 0)
