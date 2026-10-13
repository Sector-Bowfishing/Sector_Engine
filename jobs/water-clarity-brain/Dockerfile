FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 BRAIN_TOKEN_MODE=metadata
# stdlib only: no requirements. polygons.geojson.gz is copied in by deploy-job.sh
# from ../lake-surface so both jobs read the same outlines.
COPY *.py catalog.json polygons.geojson.gz ./
COPY sector_brain_platform ./sector_brain_platform
ENTRYPOINT ["python", "run.py"]
