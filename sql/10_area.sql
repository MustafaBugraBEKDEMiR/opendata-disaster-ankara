-- Raw tables for one area. psql variables: s (schema name), epsg (metric CRS).
-- build.py fills them with \copy right after this file.
DROP SCHEMA IF EXISTS :"s" CASCADE;
CREATE SCHEMA :"s";
SET search_path = :"s", public;

CREATE TABLE edges_raw (
  way_id bigint, source bigint, target bigint,
  walk boolean, drive_fw boolean, drive_bw boolean,
  speed_kmh real, highway text, wkt text
);
CREATE TABLE cells_raw (cell_id bigint, lon double precision, lat double precision, pop double precision);
CREATE TABLE facility_raw (doc jsonb);
CREATE TABLE admin_raw (doc jsonb);
CREATE TABLE district_raw (doc jsonb);

CREATE TABLE settings (key text PRIMARY KEY, value numeric);
