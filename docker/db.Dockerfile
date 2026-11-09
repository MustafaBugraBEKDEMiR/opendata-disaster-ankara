# PostGIS 3.4 + pgRouting on PostgreSQL 16
FROM postgis/postgis:16-3.4
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-16-pgrouting \
    && rm -rf /var/lib/apt/lists/*
