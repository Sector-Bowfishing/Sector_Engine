FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
# rasterio's wheel bundles GDAL but links the system expat.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py *.json ./
ENTRYPOINT ["python", "hourly.py"]
