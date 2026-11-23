FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 BRAIN_TOKEN_MODE=metadata
# stdlib only: no requirements. deploy-job.sh stages run.py, the Brain's runtime package, its verified knowledge release and the shared
# Brain Platform package (sector_brain_platform) into the build context; nothing else is copied.
COPY . ./
ENTRYPOINT ["python", "run.py"]
