FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt google-cloud-storage==2.18.2
COPY lakes.json main.py knowledge-release.json ./
COPY sector_wind ./sector_wind
COPY sector_brain_platform ./sector_brain_platform
ENTRYPOINT ["python", "main.py"]
CMD ["hourly", "--store", "local:/tmp/archive"]
