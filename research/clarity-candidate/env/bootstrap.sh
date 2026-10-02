#!/usr/bin/env bash
# Rebuild the frozen Current Clarity research environment inside research/clarity-candidate (all gitignored):
#   geo/                          Python 3.12.8 venv from env/requirements-geo.txt
#   stage11/tools/acolite/venv/   ACOLITE venv (sees geo's site-packages) from env/requirements-acolite.txt
#   stage11/tools/acolite/src/    ACOLITE at the pinned commit, LUTs verified file by file against env/acolite.lock.json
#
#   PYTHON=python3.12 ACOLITE_SRC=<git url|path> ACOLITE_LUT_FROM=<dir|gs://...> env/bootstrap.sh
# then:  env/verify_env.py   and   golden/golden_test.py all
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3.12}"
ACO_SRC="${ACOLITE_SRC:-https://github.com/acolite/acolite}"
LUT_FROM="${ACOLITE_LUT_FROM:-gs://sector-clarity-candidate/acolite/f73cbe7/LUT}"
COMMIT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["commit"])' "$ROOT/env/acolite.lock.json")"
ACO="$ROOT/stage11/tools/acolite"

want="$(cat "$ROOT/env/python-version.txt")"; have="$("$PY" -c 'import platform; print(platform.python_version())')"
[ "$want" = "$have" ] || { echo "bootstrap: need Python $want, $PY is $have" >&2; exit 1; }

[ -x "$ROOT/geo/bin/python" ] || "$PY" -m venv "$ROOT/geo"
"$ROOT/geo/bin/python" -m pip install -q --disable-pip-version-check --no-deps --only-binary=:all: -r "$ROOT/env/requirements-geo.txt"

[ -x "$ACO/venv/bin/python" ] || "$ROOT/geo/bin/python" -m venv "$ACO/venv"
GSP="$("$ROOT/geo/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
ASP="$("$ACO/venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
echo "$GSP" > "$ASP/_geo_env.pth"
"$ACO/venv/bin/python" -m pip install -q --disable-pip-version-check --no-deps --only-binary=:all: -r "$ROOT/env/requirements-acolite.txt"

if [ ! -d "$ACO/src/.git" ]; then
  git init -q "$ACO/src"
  git -C "$ACO/src" fetch -q --depth 1 "$ACO_SRC" "$COMMIT"
fi
git -C "$ACO/src" -c advice.detachedHead=false checkout -q "$COMMIT"

if [ ! -d "$ACO/src/data/LUT" ]; then
  case "$LUT_FROM" in
    gs://*) CLOUDSDK_STORAGE_SLICED_OBJECT_DOWNLOAD_THRESHOLD=0 gcloud storage cp -r "$LUT_FROM" "$ACO/src/data/" ;;
    *)      cp -R "$LUT_FROM" "$ACO/src/data/LUT" ;;
  esac
fi
"$ROOT/geo/bin/python" "$ROOT/env/verify_env.py"
