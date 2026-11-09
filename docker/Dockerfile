# Python + osmium-tool + psql client for the pipeline (the database runs in the "db" service)
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends osmium-tool postgresql-client make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
