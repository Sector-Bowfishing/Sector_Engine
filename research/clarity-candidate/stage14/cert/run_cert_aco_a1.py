"""Addendum A1 (I/O only): run_cert_aco.py unchanged, except the L1C fetch skips the TCI preview image, which ACOLITE
never reads (sentinel2/safe_test indexes it; l1_convert uses only the sensor bands B01-B12/B8A and the MSK_DETFOO masks).
  python run_cert_aco_a1.py TASKS_JSON RESDIR [--workers N] [--limit N]"""
import sys, runpy
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
_fetch = SAFE.fetch
SAFE.fetch = lambda name, skip=("HTML/", "rep_info/", "preview", "_TCI.jp2"): _fetch(name, skip)
runpy.run_path(f"{S}/stage14/cert/run_cert_aco.py", run_name="__main__")
