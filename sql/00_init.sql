-- Extensions and the schemas shared by all areas.
-- Each area (ankara, kadikoy) gets its own schema with its own metric CRS (see 10_area.sql).
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

DROP SCHEMA IF EXISTS src CASCADE;
CREATE SCHEMA src;      -- tabular sources (TÜİK, Kadıköy open data)
DROP SCHEMA IF EXISTS report CASCADE;
CREATE SCHEMA report;   -- results that span areas

CREATE TABLE report.district_population_check (
  area text, district text, tuik_2021 int, worldpop_2025 numeric, ratio numeric,
  PRIMARY KEY (area, district));

-- Turkish place names → comparable keys: "Fenerbahçe Mahallesi" and "FENERBAHÇE MAH." both give FENERBAHCE.
CREATE OR REPLACE FUNCTION src.name_key(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT regexp_replace(
           regexp_replace(
             upper(translate(coalesce(t, ''), 'çğıiöşüâîûÇĞİIÖŞÜÂÎÛ', 'cgiiosuaiuCGIIOSUAIU')),
             '\s+(MAHALLESI|MAHALLE|MAH\.?)\s*$', ''),
           '[^A-Z0-9]', '', 'g')
$$;

-- TÜİK ADNKS district populations (2021), as published in the turkiye-district-gis sources.
CREATE TABLE src.tuik_raw (doc jsonb);

-- Kadıköy Municipality open data (CC BY 3.0).
CREATE TABLE src.kadikoy_areas_raw (mahalle text, adet text, alan_m2 text);
CREATE TABLE src.kadikoy_per_capita_raw (mahalle text, alan_m2 text, nufus_2022 text, kisi_basi_m2 text);

-- "12.345", "12,345.6", "12345" → numeric (Turkish files mix both separators)
CREATE OR REPLACE FUNCTION src.to_num(t text) RETURNS numeric
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT CASE
    WHEN t IS NULL OR btrim(t) = '' THEN NULL
    WHEN btrim(t) ~ '^\d{1,3}(\.\d{3})+(,\d+)?$' THEN replace(replace(btrim(t), '.', ''), ',', '.')::numeric
    WHEN btrim(t) ~ '^\d{1,3}(,\d{3})+(\.\d+)?$' THEN replace(btrim(t), ',', '')::numeric
    WHEN btrim(t) ~ '^\d+,\d+$' THEN replace(btrim(t), ',', '.')::numeric
    WHEN btrim(t) ~ '^\d+(\.\d+)?$' THEN btrim(t)::numeric
  END
$$;
