-- Per-area check, written to the shared report schema. psql variables: s, province

-- WorldPop (2025 estimate) summed per district vs TÜİK ADNKS (2021 register).
-- Not the same year, so they should be close, not equal; a large gap would point to a
-- clipping or CRS mistake.
INSERT INTO report.district_population_check
WITH tuik AS (
  SELECT src.name_key(i ->> 'ilce_adi') AS k,
         src.to_num(i ->> 'nufus')::int AS tuik_2021
  FROM src.tuik_raw t,
       jsonb_array_elements(t.doc -> 'data') il,
       jsonb_array_elements(il -> 'ilceler') i
  WHERE src.name_key(il ->> 'il_adi') = src.name_key(:'province')
), wp AS (
  SELECT district, round(sum(pop)::numeric) AS worldpop_2025 FROM :"s".cell GROUP BY district
)
SELECT :'s', wp.district, tuik.tuik_2021, wp.worldpop_2025,
       round(wp.worldpop_2025 / NULLIF(tuik.tuik_2021, 0), 3) AS ratio
FROM wp LEFT JOIN tuik ON tuik.k = src.name_key(wp.district)
ORDER BY wp.district;
