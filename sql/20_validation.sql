-- How well does OpenStreetMap stand in for the official list of assembly areas?
-- Kadıköy Municipality publishes, per neighbourhood, the number and the surface of its
-- official assembly areas and its 2022 population. We compare them with what this
-- pipeline derives from OSM (candidate surface) and WorldPop (population).
-- psql variable s = the validation-area schema (kadikoy). Needs 10–14 for it and src.kadikoy_*.

DROP TABLE IF EXISTS report.kadikoy_validation;
CREATE TABLE report.kadikoy_validation AS
WITH official AS (
  SELECT src.name_key(a.mahalle)            AS k,
         btrim(a.mahalle)                   AS mahalle,
         src.to_num(a.adet)::int            AS official_count,
         src.to_num(a.alan_m2)              AS official_m2,
         src.to_num(p.nufus_2022)::int      AS official_pop_2022
  FROM src.kadikoy_areas_raw a
  LEFT JOIN src.kadikoy_per_capita_raw p ON src.name_key(p.mahalle) = src.name_key(a.mahalle)
  WHERE src.name_key(a.mahalle) NOT IN ('', 'MAHALLE', 'MAHALLEADI', 'TOPLAM', 'GENELTOPLAM')
), osm AS (
  SELECT src.name_key(name) AS k, name AS osm_name, n_candidates, candidate_m2, pop AS worldpop_2025
  FROM :"s".mahalle_space
)
SELECT o.mahalle, osm.osm_name, o.official_count, o.official_m2, o.official_pop_2022,
       osm.n_candidates AS osm_candidates, osm.candidate_m2 AS osm_m2, osm.worldpop_2025
FROM official o
LEFT JOIN osm USING (k)
ORDER BY o.mahalle;

DROP TABLE IF EXISTS report.kadikoy_validation_summary;
CREATE TABLE report.kadikoy_validation_summary AS
WITH m AS (SELECT * FROM report.kadikoy_validation WHERE osm_name IS NOT NULL),
r AS (
  SELECT *,
         rank() OVER (ORDER BY official_m2)       AS r_off_m2,
         rank() OVER (ORDER BY osm_m2)            AS r_osm_m2,
         rank() OVER (ORDER BY official_pop_2022) AS r_off_pop,
         rank() OVER (ORDER BY worldpop_2025)     AS r_wp_pop
  FROM m
)
SELECT
  (SELECT count(*) FROM report.kadikoy_validation)                 AS official_mahalle,
  count(*)                                                         AS matched_mahalle,
  sum(official_count)                                              AS official_areas,
  sum(osm_candidates)                                              AS osm_candidates,
  round(sum(official_m2))                                          AS official_m2,
  round(sum(osm_m2))                                               AS osm_m2,
  round(corr(r_off_m2, r_osm_m2)::numeric, 2)                      AS spearman_surface,
  sum(official_pop_2022)                                           AS official_pop_2022,
  round(sum(worldpop_2025))                                        AS worldpop_2025,
  round(corr(r_off_pop, r_wp_pop)::numeric, 2)                     AS spearman_population
FROM r;
