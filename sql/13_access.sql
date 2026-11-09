-- Travel time from every population cell to the nearest facility of each kind, and the
-- shortest-path tree behind it (so every route can be drawn and every street's load counted).
-- psql variables: s, snap_mps (speed on the cell → road connector), max_cost_s
SET search_path = :"s", public;

-- Time (s) from every network node to the nearest facility of the given kinds, with the
-- next node (pred) and edge on the way.
--   mode 'walk'  : undirected, walking speed
--   mode 'drive' : directed; inward = node → facility (to a hospital),
--                  outward = facility → node (a fire engine leaving its station)
-- Multi-source trick: one virtual vertex (-1) joined to every facility entry node at zero
-- cost, then a single Dijkstra (pgr_drivingDistance) from it. pred = -1 marks an entry node.
DROP FUNCTION IF EXISTS report.access_nodes(text, text[], text, boolean, double precision);
CREATE FUNCTION report.access_nodes(
  sch text, kinds text[], mode text, inward boolean, max_cost double precision)
RETURNS TABLE (vertex_id bigint, cost_s double precision, pred bigint, edge_id bigint, depth bigint)
LANGUAGE plpgsql AS $$
DECLARE
  net text;
  kinds_sql text := quote_literal(kinds::text);
BEGIN
  IF mode = 'walk' THEN
    net := format('SELECT id, source, target, walk_s AS cost, walk_s AS reverse_cost
                   FROM %I.edges WHERE walk_main', sch);
  ELSIF inward THEN       -- reversed graph: distances *to* the facilities
    net := format('SELECT id, source, target, drive_bw_s AS cost, drive_fw_s AS reverse_cost
                   FROM %I.edges WHERE drive_main', sch);
  ELSE
    net := format('SELECT id, source, target, drive_fw_s AS cost, drive_bw_s AS reverse_cost
                   FROM %I.edges WHERE drive_main', sch);
  END IF;
  net := net || format(
    ' UNION ALL
      SELECT -row_number() OVER (), -1::bigint, fn.vertex_id, 0::float8, -1::float8
      FROM (SELECT DISTINCT n.vertex_id
            FROM %1$I.facility_node n JOIN %1$I.facility f USING (facility_id)
            WHERE n.mode = %2$L AND f.kind = ANY (%3$s::text[])) fn', sch, mode, kinds_sql);
  RETURN QUERY
    SELECT d.node, d.agg_cost, d.pred, CASE WHEN d.edge < 0 THEN NULL ELSE d.edge END, d.depth
    FROM pgr_drivingDistance(net, -1::bigint, max_cost, true) d
    WHERE d.node <> -1;
END $$;

CREATE TABLE node_access (target text, vertex_id bigint, cost_s double precision,
                          pred bigint, edge_id bigint, depth bigint,
                          PRIMARY KEY (target, vertex_id));

INSERT INTO node_access SELECT 'walk_assembly_any', * FROM report.access_nodes(:'s', '{assembly_point,park,school}', 'walk', false, :max_cost_s);
INSERT INTO node_access SELECT 'walk_assembly_point', * FROM report.access_nodes(:'s', '{assembly_point}', 'walk', false, :max_cost_s);
INSERT INTO node_access SELECT 'walk_park',      * FROM report.access_nodes(:'s', '{park}',   'walk', false, :max_cost_s);
INSERT INTO node_access SELECT 'walk_school',    * FROM report.access_nodes(:'s', '{school}', 'walk', false, :max_cost_s);
INSERT INTO node_access SELECT 'drive_hospital', * FROM report.access_nodes(:'s', '{hospital}', 'drive', true, :max_cost_s);
INSERT INTO node_access SELECT 'drive_fire',     * FROM report.access_nodes(:'s', '{fire_station}', 'drive', false, :max_cost_s);
ANALYZE node_access;

-- A cell's time = connector (straight line to the road, walked) + the part of its edge up
-- to one end node + that node's time. "via" = the end node the route goes through.
-- For driving only directions allowed on the edge count:
--   hospital (cell → hospital): leave the edge forwards to its target or backwards to its source
--   fire (station → cell): arrive on the edge from its source (forwards) or its target (backwards)
CREATE TABLE cell_time (cell_id bigint, target text, minutes double precision, via bigint,
                        PRIMARY KEY (cell_id, target));

WITH opt AS (
  SELECT s.cell_id, t.target, s.dist_m / :snap_mps AS conn_s,
         CASE WHEN t.target LIKE 'walk%'        THEN s.frac * e.walk_s + a.cost_s
              WHEN t.target = 'drive_hospital' THEN CASE WHEN e.drive_bw THEN s.frac * e.drive_bw_s + a.cost_s END
              ELSE                                    CASE WHEN e.drive_fw THEN a.cost_s + s.frac * e.drive_fw_s END
         END AS via_source,
         CASE WHEN t.target LIKE 'walk%'        THEN (1 - s.frac) * e.walk_s + b.cost_s
              WHEN t.target = 'drive_hospital' THEN CASE WHEN e.drive_fw THEN (1 - s.frac) * e.drive_fw_s + b.cost_s END
              ELSE                                    CASE WHEN e.drive_bw THEN b.cost_s + (1 - s.frac) * e.drive_bw_s END
         END AS via_target,
         e.source, e.target AS tgt
  FROM cell_snap s
  JOIN edges e ON e.id = s.edge_id
  JOIN (VALUES ('walk_assembly_any', 'walk'), ('walk_assembly_point', 'walk'), ('walk_park', 'walk'),
               ('walk_school', 'walk'), ('drive_hospital', 'drive'), ('drive_fire', 'drive')) t(target, mode)
    ON t.mode = s.mode
  LEFT JOIN node_access a ON a.target = t.target AND a.vertex_id = e.source
  LEFT JOIN node_access b ON b.target = t.target AND b.vertex_id = e.target
)
INSERT INTO cell_time
SELECT cell_id, target,
       (conn_s + LEAST(via_source, via_target)) / 60,
       CASE WHEN via_target IS NULL OR via_source <= via_target THEN source ELSE tgt END
FROM opt
WHERE via_source IS NOT NULL OR via_target IS NOT NULL;

-- Cells with no row here are off the network or not reached within max_cost_s ("> 60 min").
ANALYZE cell_time;
