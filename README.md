# emergency-access-tr: how fast can people in Ankara reach help after an earthquake?

[![tests](https://github.com/MustafaBugraBEKDEMiR/emergency-access-tr/actions/workflows/ci.yml/badge.svg)](https://github.com/MustafaBugraBEKDEMiR/emergency-access-tr/actions/workflows/ci.yml)
[![build](https://github.com/MustafaBugraBEKDEMiR/emergency-access-tr/actions/workflows/build.yml/badge.svg)](https://github.com/MustafaBugraBEKDEMiR/emergency-access-tr/actions/workflows/build.yml)

For every 100 m of populated land in Ankara's nine central districts, this project computes how many
minutes residents need to:

* **walk to the nearest open space that can serve as an assembly area** (park, school grounds or a mapped assembly point),
* **drive to the nearest hospital**, and
* **be reached by a fire engine** from the nearest fire station,

along the real street network, and then ranks districts and neighbourhoods (*mahalle*) by how many of
their residents are within 5, 10 and 15 minutes. It uses **open data only** and checks itself against
the one official source that is open: Kadıköy Municipality's list of assembly areas.

**Live map:** <https://mustafabugrabekdemir.github.io/emergency-access-tr/> · **All numbers:** [`results/RESULTS.md`](results/RESULTS.md)

<!-- The figure and the findings below are filled in by the build workflow's first run. -->
![Walking time to the nearest assembly-area candidate and fire-engine response time](docs/img/access_map.png)

## Why open data, and what that means

Türkiye's official assembly areas (*toplanma alanları*) are set by AFAD and the municipalities and can be
looked up one address at a time on e-Devlet, but they are not published as a downloadable dataset for
Ankara. Scraping a lookup service is not open data, so this project does not try. Instead it works with
**candidates**, the kinds of open space that assembly areas are usually chosen from:

| Layer | Source | Licence |
|---|---|---|
| Streets, footpaths, one-way rules, speed limits | OpenStreetMap ([Geofabrik](https://download.geofabrik.de/europe/turkey.html) Türkiye extract) | ODbL 1.0 |
| Parks, school grounds, assembly points, hospitals, fire stations | OpenStreetMap | ODbL 1.0 |
| Neighbourhood (*mahalle*) boundaries | OpenStreetMap, `admin_level=8` | ODbL 1.0 |
| Residents per 100 m cell | [WorldPop](https://hub.worldpop.org/) R2025A, 2025, constrained | CC BY 4.0 |
| District boundaries | geoBoundaries, via [turkiye-district-gis](https://github.com/MustafaBugraBEKDEMiR/turkiye-district-gis) | ODbL 1.0 |
| District populations (check) | TÜİK ADNKS 2021, via turkiye-district-gis | public statistics |
| Official assembly areas and population per neighbourhood (validation) | [Kadıköy Belediyesi Açık Veri](https://acikveri.kadikoy.bel.tr) | CC BY 3.0 |

The **validation** step asks the obvious question: *if the official list were open, how close would the
OpenStreetMap candidates be?* For Kadıköy, where it is open, the pipeline compares the official
number and surface of assembly areas per neighbourhood with what it derives from OSM, and the official
2022 population with WorldPop. See [the validation section of the results](results/RESULTS.md#validation-kadıköy-istanbul).

## Method

```
Geofabrik .osm.pbf ──osmium extract──▶ study area ──pyosmium──▶ road graph (split at junctions)
                                                  └─osmium export─▶ facilities, neighbourhoods
WorldPop 100 m GeoTIFF ──rasterio──▶ populated cells
                 │
                 ▼  PostgreSQL 16 · PostGIS 3.4 · pgRouting 3.6  (all logic in sql/)
  11 network      walking graph (undirected) and driving graph (one-way aware), largest components only
  12 places       facilities → entry nodes; each cell snapped to the closest point of the closest edge
  13 access       multi-source Dijkstra: one virtual node joined to every facility, one pgr_drivingDistance
  14 indicators   population-weighted shares within 5/10/15 min and medians, per area/district/mahalle
  20 validation   Kadıköy: official assembly areas vs OSM candidates, official population vs WorldPop
                 │
                 ▼
  docs/data/*.geojson (web map) · results/RESULTS.md · docs/img/access_map.png
```

Details that matter for the numbers:

* **Cells join the network at the closest point of the closest edge**, not at the closest junction, and
  the part of the edge up to each end node is added. On long rural roads, snapping to junctions would
  add hundreds of metres.
* **Parks and school grounds are entered from every street node within 25 m of their outline**, so a large
  park is reachable from all sides rather than from its centroid.
* **Driving respects one-way streets in the right direction:** a fire engine leaves the station
  (station → home), a patient goes to hospital (home → hospital, routed on the reversed graph).
* **Nothing is dropped silently.** Residents with no road within 250 m, or not reached within 60 minutes,
  are reported as "not reached".

| Assumption | Value | Where |
|---|---|---|
| Walking speed after an earthquake | 4 km/h | `WALK_SPEED_KMH` |
| Driving speed | OSM `maxspeed`, else 30–100 km/h by road class; free flow, no damage | `DRIVE_SPEED_DEFAULT` |
| Smallest park counted | 1,000 m² | `MIN_PARK_M2` |
| Max. distance from a cell to a road | 250 m | `MAX_SNAP_M` |
| Routing cut-off | 60 min | `MAX_COST_S` |

All in [`scripts/config.py`](scripts/config.py); change a value and rerun to test the sensitivity.

## Run it

**Docker** (nothing else to install):

```bash
docker compose run --rm pipeline                 # tests on the built-in test grid (~1 min)
docker compose run --rm pipeline make all        # real data: download → prepare → build → export
```

**Without Docker:** PostgreSQL ≥ 14 with PostGIS ≥ 3.1 and pgRouting ≥ 3.4, `osmium-tool`, Python ≥ 3.10.

```bash
pip install -r requirements.txt
export PGHOST=localhost PGUSER=gis PGPASSWORD=gis PGDATABASE=access
python tests/run_tests.py     # test grid
make all                      # download (~0.7 GB), prepare, build, export
```

**On GitHub:** the [`build`](.github/workflows/build.yml) workflow (Actions tab → *Run workflow*) does
the same on a GitHub runner and commits the results; it also reruns monthly with fresh OSM data.

### Tests

[`tests/run_tests.py`](tests/run_tests.py) runs the real pipeline (osmium → Python → every SQL file) on a
hand-made 5 × 5 street grid whose answers can be checked on paper. It is a test fixture, not data. It checks
splitting at junctions, walk/drive permissions, one-way detours (a 6-block detour where the direct
way is 4 blocks), entry from all sides of a park, exact walking and driving times, that unrouted residents are
reported, neighbourhood assignment, Turkish name matching and number parsing.

## Limitations

* **Candidates, not official assembly areas.** A park can be fenced, a school yard locked or too small;
  an official area may be a car park that OSM does not tag as open space. The Kadıköy check shows how
  large this gap is in one district; it does not prove the same for Ankara.
* **OpenStreetMap completeness varies.** Footpaths, school outlines and especially
  `emergency=assembly_point` are mapped unevenly; a gap on the map can be a gap in OSM.
* **Free-flow driving.** No traffic, no debris, no collapsed buildings: post-disaster times will be longer.
  The driving results show the best case of the network's layout.
* **WorldPop is a model.** It distributes census totals to buildings; the TÜİK comparison in the results
  shows how close it is per district.
* **Neighbourhood boundaries** come from OSM and may not match the official MAKS boundaries everywhere.

## Repository layout

```
scripts/   config.py (all settings), download.py, prepare.py, build.py, export_web.py, make_figure.py
sql/       00_init → 14_indicators (per area), 20_validation, 21_report
tests/     run_tests.py (test grid built in code)
docs/      index.html (Leaflet web map), data/ (exported by the build), img/
results/   RESULTS.md, SOURCES.json (URL, size, SHA-256 and date of every input file)
```

Related: [turkiye-district-gis](https://github.com/MustafaBugraBEKDEMiR/turkiye-district-gis) (national district
database this project takes its boundaries from) and [residenceinsys](https://github.com/MustafaBugraBEKDEMiR/residenceinsys)
(who lives in an affected area).

Code: MIT licence. Data: see the table above.

---

## Türkçe özet

Bu proje, Ankara'nın dokuz merkez ilçesinde (Altındağ, Çankaya, Etimesgut, Gölbaşı, Keçiören, Mamak,
Pursaklar, Sincan, Yenimahalle) her 100 m'lik nüfuslu alan için gerçek yol ağı üzerinden şu süreleri hesaplar:

* toplanma alanı olabilecek en yakın açık alana (park, okul bahçesi, haritalanmış toplanma noktası) **yürüme süresi**,
* en yakın **hastaneye araçla** ulaşım süresi,
* en yakın **itfaiye istasyonundan** araç çıkış süresi.

Sonuçlar ilçe ve mahalle bazında, nüfusun yüzde kaçının 5, 10 ve 15 dakika içinde ulaşabildiği şeklinde
özetlenir. Resmî AFAD toplanma alanları Ankara için açık veri olarak yayımlanmadığı için yalnızca
**açık veri** kullanılır (OpenStreetMap, WorldPop) ve bu alanlar "aday" olarak adlandırılır. Bu yaklaşımın
ne kadar isabetli olduğu, resmî verisini açık yayımlayan **Kadıköy** üzerinde test edilir.

Kurulum: `docker compose run --rm pipeline make all`. Tüm analiz SQL'dedir (PostGIS + pgRouting).
Testler, sonuçları kâğıt üzerinde doğrulanabilen küçük bir test ızgarası üzerinde tüm hattı çalıştırır.

**Yazar / Author:** Mustafa Buğra Bekdemir: Geomatics Engineer, M.Sc. student in Management Information Systems (AYBÜ).
