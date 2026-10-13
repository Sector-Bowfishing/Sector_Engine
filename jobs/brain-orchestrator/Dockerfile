FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 BRAIN_TOKEN_MODE=metadata
# stdlib only. deploy-job.sh stages the repo layout this job relies on (../brain_platform, ../biological-brain,
# ../sector-intelligence-brain, ../brain-scores, ../../docs/brains/scoring/frozen-scores.json) under ./stage.
COPY stage/ ./
WORKDIR /job/jobs/brain-orchestrator
ENTRYPOINT ["python", "orchestrate.py"]
