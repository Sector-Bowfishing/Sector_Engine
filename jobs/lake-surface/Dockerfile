FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1 \
    GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR \
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif,.TIF \
    GDAL_HTTP_MAX_RETRY=5 \
    GDAL_HTTP_RETRY_DELAY=2
# rasterio's wheel bundles GDAL but links the system expat.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py polygons.geojson.gz ./
ENTRYPOINT ["python", "daily.py"]
