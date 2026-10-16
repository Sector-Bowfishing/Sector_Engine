FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 BRAIN_TOKEN_MODE=metadata
# stdlib only. polygons.geojson.gz is copied in by deploy-job.sh from ../lake-surface so the
# dispatcher and the heavy job read the same outlines; sector_brain_platform is vendored the same way.
COPY dispatch.py polygons.geojson.gz ./
COPY sector_brain_platform ./sector_brain_platform
ENTRYPOINT ["python", "dispatch.py"]
