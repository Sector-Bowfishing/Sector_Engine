FROM python:3.12-slim
WORKDIR /job
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY archive.py ./
ENTRYPOINT ["python", "archive.py"]
