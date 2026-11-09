-- Districts, neighbourhoods (mahalle), facilities and population cells for one area,
-- each tied to the network. psql variables: s, epsg, min_park_m2, entry_m, max_snap_m
SET search_path = :"s", public;

-- ------------------------------------------------------------------ districts
CREATE TABLE district AS
SELECT doc #>> '{properties,district}' AS name,
       ST_Multi(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(doc ->> 'geometry'), 4326), :epsg))
         ::geometry(MultiPolygon, :epsg) AS geom_m
FROM district_raw;
ALTER TABLE district ADD PRIMARY KEY (name);
CREATE INDEX district_gix ON district USING gist (geom_m);

-- ------------------------------------------------------------------ neighbourhoods (OSM admin_level=8)
-- In Turkish OpenStreetMap, admin_level 8 is the mahalle / köy. Coverage is checked in tests.
CREATE TABLE mahalle AS
WITH poly AS (
  SELECT doc #>> '{properties,name}'                               AS name,
         (doc #>> '{properties,@id}')::bigint                       AS osm_id,
         ST_Multi(ST_MakeValid(ST_Transform(
           ST_SetSRID(ST_GeomFromGeoJSON(doc ->> 'geometry'), 4326), :epsg))) AS geom_m
  FROM admin_raw
  WHERE doc #>> '{properties,boundary}' = 'administrative'
    AND doc #>> '{properties,admin_level}' = '8'
    AND doc #>> '{geometry,type}' IN ('Polygon', 'MultiPolygon')
)
SELECT DISTINCT ON (p.osm_id)
       p.osm_id, p.name, d.name AS district,
       ST_CollectionExtract(p.geom_m, 3)::geometry(MultiPolygon, :epsg) AS geom_m
FROM poly p
JOIN district d ON ST_Intersects(d.geom_m, ST_PointOnSurface(p.geom_m))
WHERE p.name IS NOT NULL
ORDER BY p.osm_id;
ALTER TABLE mahalle ADD PRIMARY KEY (osm_id);
CREATE INDEX mahalle_gix ON mahalle USING gist (geom_m);

-- ------------------------------------------------------------------ facilities
CREATE TABLE facility AS
WITH f AS (
  SELECT doc -> 'properties' AS p,
         ST_MakeValid(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(doc ->> 'geometry'), 4326), :epsg)) AS geom_m
  FROM facility_raw
  WHERE doc #>> '{geometry,type}' IN ('Point', 'Polygon', 'MultiPolygon')
), k AS (
  SELECT CASE
           WHEN p ->> 'emergency' = 'assembly_point' THEN 'assembly_point'
           WHEN p ->> 'amenity'   = 'hospital'       THEN 'hospital'
           WHEN p ->> 'amenity'   = 'fire_station'   THEN 'fire_station'
           WHEN p ->> 'amenity'   = 'school'         THEN 'school'
           WHEN p ->> 'leisure'   = 'park'           THEN 'park'
         END                                                   AS kind,
         left(p ->> '@type', 1) || (p ->> '@id')               AS osm_ref,
         p ->> 'name'                                          AS name,
         geom_m
  FROM f
)
SELECT row_number() OVER (ORDER BY kind, osm_ref)::int AS facility_id, kind, osm_ref, name,
       geom_m::geometry(Geometry, :epsg)                  AS geom_m,
       CASE WHEN GeometryType(geom_m) LIKE '%POLYGON' THEN ST_Area(geom_m) END AS area_m2
FROM k
WHERE kind IS NOT NULL
  AND NOT (kind = 'park' AND (GeometryType(geom_m) = 'POINT' OR ST_Area(geom_m) < :min_park_m2));
ALTER TABLE facility ADD PRIMARY KEY (facility_id);
CREATE INDEX facility_gix ON facility USING gist (geom_m);

-- A hospital mapped both as a node and as a building outline counts once.
DELETE FROM facility pt
USING facility pg
WHERE GeometryType(pt.geom_m) = 'POINT' AND GeometryType(pg.geom_m) <> 'POINT'
  AND pt.kind = pg.kind AND ST_DWithin(pt.geom_m, pg.geom_m, 50);

-- Where a facility is entered from the network: every main-network node within entry_m of
-- the outline (a park can be reached from all sides); otherwise the closest node within 300 m.
CREATE TABLE facility_node (mode text, facility_id int, vertex_id bigint, PRIMARY KEY (mode, facility_id, vertex_id));
INSERT INTO facility_node
SELECT m.mode, f.facility_id, v.id
FROM facility f
CROSS JOIN (VALUES ('walk'), ('drive')) m(mode)
JOIN vertices v ON ST_DWithin(v.geom_m, f.geom_m, :entry_m)
               AND CASE m.mode WHEN 'walk' THEN v.walk_main ELSE v.drive_main END
WHERE GeometryType(f.geom_m) <> 'POINT';

INSERT INTO facility_node
SELECT m.mode, f.facility_id, nn.id
FROM facility f
CROSS JOIN (VALUES ('walk'), ('drive')) m(mode)
CROSS JOIN LATERAL (
  SELECT v.id FROM vertices v
  WHERE CASE m.mode WHEN 'walk' THEN v.walk_main ELSE v.drive_main END
    AND ST_DWithin(v.geom_m, f.geom_m, 300)
  ORDER BY v.geom_m <-> f.geom_m LIMIT 1
) nn
WHERE NOT EXISTS (SELECT 1 FROM facility_node x
                  WHERE x.mode = m.mode AND x.facility_id = f.facility_id);

-- ------------------------------------------------------------------ population cells
-- WorldPop 100 m cell centres. Only cells inside the area's districts are analysed.
CREATE TABLE cell AS
SELECT c.cell_id, c.pop, d.name AS district, NULL::bigint AS mahalle_id,
       ST_Transform(ST_SetSRID(ST_MakePoint(c.lon, c.lat), 4326), :epsg)::geometry(Point, :epsg) AS geom_m
FROM cells_raw c
JOIN district d ON ST_Intersects(d.geom_m, ST_Transform(ST_SetSRID(ST_MakePoint(c.lon, c.lat), 4326), :epsg));
ALTER TABLE cell ADD PRIMARY KEY (cell_id),
  ADD CONSTRAINT cell_pop_positive CHECK (pop > 0);
CREATE INDEX cell_gix ON cell USING gist (geom_m);

UPDATE cell c SET mahalle_id = m.osm_id
FROM mahalle m WHERE ST_Intersects(m.geom_m, c.geom_m);

-- Each cell joins the network at the closest point of the closest usable edge.
-- frac = position of that point along the edge (0 = source, 1 = target).
CREATE TABLE cell_snap (
  cell_id bigint, mode text, edge_id bigint, frac double precision, dist_m double precision,
  PRIMARY KEY (cell_id, mode)
);
INSERT INTO cell_snap
SELECT c.cell_id, 'walk', e.id, ST_LineLocatePoint(e.geom_m, c.geom_m), e.d
FROM cell c
CROSS JOIN LATERAL (
  SELECT id, geom_m, geom_m <-> c.geom_m AS d FROM edges
  WHERE walk_main ORDER BY geom_m <-> c.geom_m LIMIT 1
) e
WHERE e.d <= :max_snap_m;

INSERT INTO cell_snap
SELECT c.cell_id, 'drive', e.id, ST_LineLocatePoint(e.geom_m, c.geom_m), e.d
FROM cell c
CROSS JOIN LATERAL (
  SELECT id, geom_m, geom_m <-> c.geom_m AS d FROM edges
  WHERE drive_main ORDER BY geom_m <-> c.geom_m LIMIT 1
) e
WHERE e.d <= :max_snap_m;

ANALYZE facility; ANALYZE facility_node; ANALYZE cell; ANALYZE cell_snap;
