FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt google-cloud-storage==2.18.2
COPY lakes.json main.py ./
COPY sector_wind ./sector_wind
ENTRYPOINT ["python", "main.py"]
CMD ["hourly", "--store", "local:/tmp/archive"]
