"""Check the rebuilt environment against the frozen one: Python version, both package sets, the ACOLITE commit and tree,
a clean ACOLITE checkout, and every LUT file's sha256.  Exit 1 on any difference.
  geo/bin/python env/verify_env.py [--json]"""
import hashlib, json, os, platform, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACO = os.path.join(ROOT, "stage11/tools/acolite")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def freeze(python, path=None):
    cmd = [python, "-m", "pip", "freeze", "--disable-pip-version-check"] + (["--path", path] if path else [])
    return sorted(l.strip().lower() for l in subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines() if l.strip())


def want(name): return sorted(l.strip().lower() for l in open(os.path.join(ROOT, "env", name)) if l.strip())


def main():
    lock = json.load(open(os.path.join(ROOT, "env/acolite.lock.json")))
    r = {"python": platform.python_version() == open(os.path.join(ROOT, "env/python-version.txt")).read().strip()}
    r["geo_packages"] = freeze(os.path.join(ROOT, "geo/bin/python")) == want("requirements-geo.txt")
    apy = os.path.join(ACO, "venv/bin/python")
    asp = subprocess.run([apy, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], capture_output=True, text=True).stdout.strip()
    r["acolite_packages"] = freeze(apy, asp) == want("requirements-acolite.txt")
    g = lambda *a: subprocess.run(["git", "-C", os.path.join(ACO, "src"), *a], capture_output=True, text=True).stdout.strip()
    r["acolite_commit"] = g("rev-parse", "HEAD") == lock["commit"]
    r["acolite_tree"] = g("rev-parse", "HEAD^{tree}") == lock["tree"]
    r["acolite_clean"] = g("status", "--porcelain", "--untracked-files=no") == ""
    lut = os.path.join(ACO, "src/data/LUT")
    bad = [f for f, v in lock["lut"].items() if not os.path.isfile(os.path.join(lut, f)) or sha(os.path.join(lut, f)) != v["sha256"]]
    extra = [os.path.relpath(os.path.join(a, f), lut) for a, d, fs in os.walk(lut) for f in fs if os.path.relpath(os.path.join(a, f), lut) not in lock["lut"] and f != ".DS_Store"]
    r["lut_files"] = not bad and not extra
    r["lut_mismatch"], r["lut_extra"] = bad[:10], extra[:10]
    ok = all(v for k, v in r.items() if not isinstance(v, list))
    print(json.dumps({"ENV_OK": ok, **r}, indent=None if "--json" in sys.argv else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
