-- Population-weighted indicators for the area, its districts and its neighbourhoods.
-- psql variables: s
SET search_path = :"s", public;

-- Every cell × every target. A cell with no time (off the network or > 60 min) keeps NULL.
CREATE TABLE cell_long AS
SELECT c.cell_id, c.pop::numeric AS pop, c.district, c.mahalle_id, t.target, ct.minutes
FROM cell c
CROSS JOIN (VALUES ('walk_assembly_any'), ('walk_assembly_point'), ('walk_park'),
                   ('walk_school'), ('drive_hospital'), ('drive_fire')) t(target)
LEFT JOIN cell_time ct ON ct.cell_id = c.cell_id AND ct.target = t.target;

CREATE TABLE summary AS
WITH g AS (
  SELECT 'area' AS level, :'s'::text AS key, target, pop, minutes FROM cell_long
  UNION ALL
  SELECT 'district', district, target, pop, minutes FROM cell_long
  UNION ALL
  SELECT 'mahalle', mahalle_id::text, target, pop, minutes FROM cell_long WHERE mahalle_id IS NOT NULL
), ranked AS (
  SELECT g.*,
         sum(pop) OVER (PARTITION BY level, key, target
                        ORDER BY coalesce(minutes, 'infinity'::float8)
                        ROWS UNBOUNDED PRECEDING) AS cum_pop,
         sum(pop) OVER (PARTITION BY level, key, target) AS total_pop
  FROM g
)
SELECT level, key, target,
       round(max(total_pop))                                                       AS pop,
       round(100 * coalesce(sum(pop) FILTER (WHERE minutes <= 5), 0) / max(total_pop), 1)        AS pct_le_5,
       round(100 * coalesce(sum(pop) FILTER (WHERE minutes <= 10), 0) / max(total_pop), 1)        AS pct_le_10,
       round(100 * coalesce(sum(pop) FILTER (WHERE minutes <= 15), 0) / max(total_pop), 1)        AS pct_le_15,
       round(100 * coalesce(sum(pop) FILTER (WHERE minutes IS NULL), 0) / max(total_pop), 1) AS pct_unreached,
       round(min(coalesce(minutes, 'infinity')) FILTER (WHERE cum_pop >= total_pop / 2)::numeric, 1) AS median_min
FROM ranked
GROUP BY level, key, target;
ALTER TABLE summary ADD PRIMARY KEY (level, key, target);

-- Candidate assembly-area surface per person, per neighbourhood (parks, school grounds and
-- mapped assembly areas, overlaps counted once).
CREATE TABLE mahalle_space AS
SELECT m.osm_id, m.name, m.district,
       round(ST_Area(m.geom_m)::numeric)                         AS mahalle_m2,
       coalesce(p.pop, 0)                                        AS pop,
       coalesce(round(ST_Area(ST_Intersection(m.geom_m, u.geom))::numeric), 0) AS candidate_m2,
       coalesce(n.n_candidates, 0)                               AS n_candidates
FROM mahalle m
LEFT JOIN LATERAL (
  SELECT ST_Union(f.geom_m) AS geom FROM facility f
  WHERE f.kind IN ('park', 'school', 'assembly_point') AND GeometryType(f.geom_m) <> 'POINT'
    AND ST_Intersects(f.geom_m, m.geom_m)
) u ON true
LEFT JOIN LATERAL (
  SELECT count(*) AS n_candidates FROM facility f
  WHERE f.kind IN ('park', 'school', 'assembly_point')
    AND ST_Intersects(m.geom_m, ST_PointOnSurface(f.geom_m))
) n ON true
LEFT JOIN LATERAL (SELECT round(sum(c.pop)::numeric) AS pop FROM cell c WHERE c.mahalle_id = m.osm_id) p ON true;
ALTER TABLE mahalle_space ADD PRIMARY KEY (osm_id);
