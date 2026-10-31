FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 BRAIN_TOKEN_MODE=metadata
# stdlib only. deploy-job.sh stages: publish_job.py, the shared Brain Platform, the reviewed publication-cutover.json and releases/<brainId>/ (each CENTRAL
# Brain's packaged knowledge release, verified file by file by PackagedReleaseResolver before anything is published).
COPY publish_job.py publication-cutover.json ./
COPY sector_brain_platform ./sector_brain_platform
COPY releases ./releases
ENTRYPOINT ["python", "publish_job.py"]
