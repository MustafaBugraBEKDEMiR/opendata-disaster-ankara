-- Routable network for one area.
-- psql variables: s, epsg, walk_mps (walking speed, m/s)
SET search_path = :"s", public;

-- One row per road segment between two junctions. Costs are seconds; -1 = not allowed.
CREATE TABLE edges AS
SELECT row_number() OVER ()::bigint             AS id,
       way_id, source, target, walk, drive_fw, drive_bw, speed_kmh, highway,
       ST_GeomFromText(wkt, 4326)                AS geom
FROM edges_raw;

ALTER TABLE edges ADD COLUMN geom_m geometry(LineString, :epsg);
UPDATE edges SET geom_m = ST_Transform(geom, :epsg);
ALTER TABLE edges
  ADD COLUMN length_m   double precision,
  ADD COLUMN walk_s     double precision,
  ADD COLUMN drive_fw_s double precision,
  ADD COLUMN drive_bw_s double precision;
UPDATE edges SET
  length_m   = ST_Length(geom_m),
  walk_s     = CASE WHEN walk     THEN ST_Length(geom_m) / :walk_mps ELSE -1 END,
  drive_fw_s = CASE WHEN drive_fw THEN ST_Length(geom_m) / (speed_kmh / 3.6) ELSE -1 END,
  drive_bw_s = CASE WHEN drive_bw THEN ST_Length(geom_m) / (speed_kmh / 3.6) ELSE -1 END;

ALTER TABLE edges ADD PRIMARY KEY (id),
  ADD CONSTRAINT edges_length_ok CHECK (length_m >= 0),
  ADD CONSTRAINT edges_usable CHECK (walk OR drive_fw OR drive_bw);
CREATE INDEX edges_geom_m_gix ON edges USING gist (geom_m);
CREATE INDEX edges_source_ix ON edges (source);
CREATE INDEX edges_target_ix ON edges (target);

-- Vertices are OSM nodes (id = OSM node id).
CREATE TABLE vertices AS
SELECT DISTINCT ON (id) id, geom_m
FROM (
  SELECT source AS id, ST_StartPoint(geom_m) AS geom_m FROM edges
  UNION ALL
  SELECT target, ST_EndPoint(geom_m) FROM edges
) v
ORDER BY id;
ALTER TABLE vertices ADD PRIMARY KEY (id),
  ALTER COLUMN geom_m TYPE geometry(Point, :epsg),
  ADD COLUMN walk_main  boolean NOT NULL DEFAULT false,
  ADD COLUMN drive_main boolean NOT NULL DEFAULT false;
CREATE INDEX vertices_geom_m_gix ON vertices USING gist (geom_m);

-- Keep the largest connected walking network and the largest strongly connected driving
-- network. Small islands (a mapped courtyard, a cut-off service road) would otherwise
-- "trap" the population cells snapped to them.
WITH comp AS (
  SELECT node, component FROM pgr_connectedComponents(
    format('SELECT id, source, target, walk_s AS cost, walk_s AS reverse_cost FROM %I.edges WHERE walk', :'s'))
), biggest AS (
  SELECT component FROM comp GROUP BY component ORDER BY count(*) DESC LIMIT 1
)
UPDATE vertices v SET walk_main = true
FROM comp JOIN biggest USING (component) WHERE v.id = comp.node;

WITH comp AS (
  SELECT node, component FROM pgr_strongComponents(
    format('SELECT id, source, target, drive_fw_s AS cost, drive_bw_s AS reverse_cost FROM %I.edges
            WHERE drive_fw OR drive_bw', :'s'))
), biggest AS (
  SELECT component FROM comp GROUP BY component ORDER BY count(*) DESC LIMIT 1
)
UPDATE vertices v SET drive_main = true
FROM comp JOIN biggest USING (component) WHERE v.id = comp.node;

ALTER TABLE edges ADD COLUMN walk_main boolean, ADD COLUMN drive_main boolean;
UPDATE edges e SET
  walk_main  = e.walk AND a.walk_main AND b.walk_main,
  drive_main = (e.drive_fw OR e.drive_bw) AND a.drive_main AND b.drive_main
FROM vertices a, vertices b
WHERE a.id = e.source AND b.id = e.target;

ANALYZE edges;
ANALYZE vertices;
