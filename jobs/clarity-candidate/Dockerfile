# The Current Clarity candidate shadow job (UNCERTIFIED). The image is the frozen research environment:
# Python 3.12.8, the pinned packages (research/clarity-candidate/env), ACOLITE f73cbe7 with its 269 LUTs, the frozen
# research tree, and the job. Built from the staging folder deploy-job.sh assembles; the build fails unless
# env/verify_env.py passes (package sets, ACOLITE commit and tree, every LUT sha256).
FROM python:3.12.8-slim-bookworm
# rasterio's wheel bundles GDAL but links the system expat; git is for the ACOLITE commit check.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    CLARITY_RESEARCH_ROOT=/job/research/clarity-candidate
WORKDIR /job
COPY research/clarity-candidate/env/ /job/research/clarity-candidate/env/
RUN R=$CLARITY_RESEARCH_ROOT \
 && python -m venv $R/geo \
 && $R/geo/bin/pip install -q --no-deps --only-binary=:all: -r $R/env/requirements-geo.txt \
 && $R/geo/bin/python -m venv $R/stage11/tools/acolite/venv \
 && $R/geo/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])" \
      > "$($R/stage11/tools/acolite/venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")/_geo_env.pth" \
 && $R/stage11/tools/acolite/venv/bin/pip install -q --no-deps --only-binary=:all: -r $R/env/requirements-acolite.txt
COPY research/ /job/research/
COPY jobs/clarity-candidate/ /job/jobs/clarity-candidate/
RUN git config --global --add safe.directory '*' \
 && $CLARITY_RESEARCH_ROOT/geo/bin/python $CLARITY_RESEARCH_ROOT/env/verify_env.py
ARG JOB_COMMIT=dev
ENV JOB_COMMIT=$JOB_COMMIT
ENTRYPOINT ["/job/research/clarity-candidate/geo/bin/python", "/job/jobs/clarity-candidate/shadow.py"]
