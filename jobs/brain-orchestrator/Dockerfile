FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 BRAIN_TOKEN_MODE=metadata
# stdlib + numpy (below). deploy-job.sh stages the repo layout this job relies on (../brain_platform, ../biological-brain,
# ../sector-intelligence-brain, ../brain-scores, ../../docs/brains/scoring/frozen-scores.json) under ./stage.
# numpy: required by the Vegetation runtime the internal SHADOW lane runs (brains/vegetation/runtime/requirements.txt: numpy>=2.0)
RUN pip install --no-cache-dir numpy==2.3.4
COPY stage/ ./
WORKDIR /job/jobs/brain-orchestrator
ENTRYPOINT ["python", "orchestrate.py"]
