# Results: Ankara (9 central districts)

*Generated 2026-11-09 by `scripts/export_web.py`. Do not edit by hand.*

## Inputs

|  | value |
|---|---|
| Population (WorldPop 2025, 100 m cells) | 5,324,844 |
| Populated cells | 176,360 |
| Population with no road within 250 m | 55,763 |
| Walkable network (main component) | 206,992 segments, 18,884 km |
| Drivable network (main component) | 169,050 segments |
| Neighbourhoods (OSM admin_level 8) | 467 (cover 99.2 % of the population) |
| Assembly point (OSM emergency=assembly_point) | 14 |
| Park ≥ 1000 m² (OSM leisure=park) | 2,285 |
| School grounds (OSM amenity=school) | 1,116 |
| Hospital (OSM amenity=hospital) | 105 |
| Fire station (OSM amenity=fire_station) | 15 |

Source files: `turkey-latest.osm.pbf` (2026-11-09); `tur_pop_2025_CN_100m_R2025A_v1.tif` (2026-11-09); `geoBoundaries-TUR-ADM2_simplified.geojson` (2026-11-09); `geoBoundaries-TUR-ADM1_simplified.geojson` (2026-11-09); `tuik-adnks-il-ilce.json` (2026-11-09); `kadikoy_mahalle_afet_toplanma_alanlari.csv` (2026-11-09); `kadikoy_kisi_basi_toplanma_alani.xlsx` (2026-11-09)

## Whole study area

Share of the population that reaches the target within the given time, and the population-weighted median.

| Target | ≤ 5 min | ≤ 10 min | ≤ 15 min | not reached ≤ 60 min* | median (min) |
|---|---|---|---|---|---|
| Walk to the nearest assembly-area candidate (park, school or assembly point) | 72.3 % | 86.7 % | 90.3 % | 3.4 % | 2.9 |
| Walk to a mapped assembly point | 0.2 % | 0.5 % | 0.8 % | 96.5 % | > 60 |
| Walk to a park ≥ 1000 m² | 63.4 % | 83.1 % | 88.3 % | 3.7 % | 3.7 |
| Walk to school grounds | 44.7 % | 76.6 % | 85.2 % | 4.0 % | 5.5 |
| Drive to the nearest hospital | 82.7 % | 94.8 % | 96.6 % | 0.8 % | 2.6 |
| Fire engine from the nearest station | 42.6 % | 86.7 % | 96.2 % | 0.8 % | 5.5 |

\* includes population with no road within the snapping distance.

## Districts

Sorted by the share of people within a 10-minute walk of an assembly-area candidate (worst first).

| District | population | walk ≤ 10 min | walk median | hospital ≤ 10 min (car) | hospital median | fire engine ≤ 10 min | fire median |
|---|---|---|---|---|---|---|---|
| Gölbaşı | 154,462 | 49.9 % | 10 | 66.0 % | 6.1 | 54.3 % | 9.4 |
| Sincan | 589,344 | 73.6 % | 2.9 | 84.7 % | 2.7 | 84.8 % | 4.7 |
| Etimesgut | 620,081 | 81.3 % | 2.7 | 94.8 % | 3.5 | 87.0 % | 7.9 |
| Yenimahalle | 735,554 | 83.8 % | 3.2 | 98.2 % | 3.1 | 94.0 % | 5.2 |
| Pursaklar | 166,893 | 88.2 % | 2.6 | 91.2 % | 3.6 | 44.9 % | 10.3 |
| Mamak | 697,829 | 89.7 % | 3.1 | 95.6 % | 2.8 | 77.0 % | 7.2 |
| Çankaya | 965,761 | 91.0 % | 3 | 97.5 % | 2.2 | 92.7 % | 4.9 |
| Altındağ | 432,666 | 91.3 % | 2.9 | 97.4 % | 2.8 | 84.2 % | 4.7 |
| Keçiören | 962,253 | 97.6 % | 2.4 | 99.1 % | 2.1 | 96.7 % | 4.3 |

## Neighbourhoods with the weakest walking access

### Urban neighbourhoods (≥ 10,000 residents)

Sorted by the share of residents within a 10-minute walk of an assembly-area candidate.

| Neighbourhood | district | population | walk ≤ 10 min | walk median | fire median | candidate m² / person |
|---|---|---|---|---|---|---|
| Malıköy Başkent OSB Mahallesi | Sincan | 22,980 | 0.0 % | > 60 | 4 | 0 |
| Ahi Evran OSB Mahallesi | Sincan | 39,463 | 13.5 % | 25.4 | 6.4 | 0.36 |
| İvedikköy Mahallesi | Yenimahalle | 23,023 | 16.8 % | 24.2 | 9.5 | 0.79 |
| Erler Mahallesi | Etimesgut | 30,179 | 17.8 % | 25.6 | 10 | 1.49 |
| Bahçekapı Mahallesi | Etimesgut | 64,837 | 25.4 % | 22.1 | 7.5 | 1.59 |
| Gazi Mahallesi | Yenimahalle | 32,281 | 31.1 % | 14.8 | 6.8 | 26.9 |
| Saraycık Mahallesi | Sincan | 12,131 | 31.9 % | 15.9 | 8 | 2.55 |
| Macun Mahallesi | Yenimahalle | 17,494 | 34.6 % | 14.5 | 5.1 | 1.12 |
| Çiğiltepe Mahallesi | Mamak | 11,579 | 46.7 % | 11.2 | 6.9 | 0.39 |
| Beytepe Mahallesi | Çankaya | 11,936 | 47.6 % | 10.3 | 7.6 | 5.95 |
| Ahlatlıbel Mahallesi | Çankaya | 11,503 | 48.5 % | 11.1 | 10.8 | 34.37 |
| Devlet Mahallesi | Çankaya | 26,900 | 50.3 % | 9.9 | 7.5 | 16.94 |
| Adalet Mahallesi | Sincan | 11,235 | 52.7 % | 9.5 | 13.3 | 0.51 |
| Üniversiteler Mahallesi | Çankaya | 39,014 | 54.0 % | 9.2 | 10.1 | 8.51 |
| Etiler Mahallesi | Etimesgut | 15,395 | 54.4 % | 9.1 | 8.9 | 3.52 |

### All neighbourhoods (≥ 1,000 residents)

Most are former villages on the urban edge (*mahalle* since the 2012 metropolitan law), where OSM rarely maps a school yard or village square, so part of this gap is a mapping gap.

| Neighbourhood | district | population | walk ≤ 10 min | walk median | fire median | candidate m² / person |
|---|---|---|---|---|---|---|
| Yurtbeyi Mahallesi | Gölbaşı | 2,217 | 0.0 % | > 60 | 14.1 | 0 |
| Balıkuyumcu Mahallesi | Etimesgut | 2,239 | 0.0 % | > 60 | 16.7 | 0 |
| Karataş Mahallesi | Çankaya | 1,188 | 0.0 % | > 60 | 17.2 | 0 |
| Şehitali Mahallesi | Etimesgut | 2,879 | 0.0 % | > 60 | 19.7 | 0 |
| Gökçeyurt Mahallesi | Mamak | 6,139 | 0.0 % | > 60 | 17.7 | 0 |
| Tulumtaş Mahallesi | Gölbaşı | 3,987 | 0.0 % | > 60 | 12.4 | 0 |
| Fevziye Mahallesi | Etimesgut | 2,293 | 0.0 % | > 60 | 23.5 | 0 |
| Karacakaya Mahallesi | Yenimahalle | 2,630 | 0.0 % | > 60 | 15.6 | 0 |
| İkizce Mahallesi | Gölbaşı | 1,238 | 0.0 % | > 60 | 24 | 0 |
| Akçaören Mahallesi | Sincan | 2,252 | 0.0 % | > 60 | 11.6 | 0 |

## Streets that would carry the most people on foot

Every resident walks the shortest route to the nearest assembly-area candidate; the load of a street segment is the number of residents whose route uses it. The table shows the busiest segment of each named street. These are the streets where an evacuation would crowd first.

| Street | district | residents on the busiest segment |
|---|---|---|
| ASO Bulvar | Sincan | 26,490 |
| 2473 Caddesi | Etimesgut | 9,334 |
| Oğuz Cadde | Sincan | 9,255 |
| 2500. Cadde | Etimesgut | 9,046 |
| 2551. Cadde | Etimesgut | 7,439 |
| 3890. Cadde | Yenimahalle | 6,990 |
| Altınay Caddesi | Altındağ | 6,494 |
| 158 Sokak | Yenimahalle | 6,425 |
| Cennet Sokak | Keçiören | 6,412 |
| 846. Cadde | Mamak | 6,259 |
| 153 Caddesi | Yenimahalle | 6,241 |
| Ayrık Sokak | Keçiören | 5,863 |
| 32. Sokak | Yenimahalle | 5,770 |
| 33. Sokak | Yenimahalle | 5,345 |
| Kayaş Caddesi | Mamak | 5,288 |

## Check: WorldPop vs TÜİK district totals

WorldPop is a 2025 model estimate, TÜİK ADNKS the 2021 register, so the ratio should be near 1, not exactly 1.

| District | TÜİK 2021 | WorldPop 2025 | ratio |
|---|---|---|---|
| Altındağ | 407,675 | 432,666 | 1.061 |
| Etimesgut | 606,472 | 620,081 | 1.022 |
| Gölbaşı | 142,961 | 154,462 | 1.08 |
| Keçiören | 942,884 | 962,253 | 1.021 |
| Mamak | 682,420 | 697,829 | 1.023 |
| Pursaklar | 159,676 | 166,893 | 1.045 |
| Sincan | 561,411 | 589,344 | 1.05 |
| Yenimahalle | 703,809 | 735,554 | 1.045 |
| Çankaya | 949,265 | 965,761 | 1.017 |

## Validation: Kadıköy (İstanbul)

Kadıköy Municipality publishes the number and surface of its official assembly areas per neighbourhood. The same pipeline derives the candidate surface from OpenStreetMap.

|  | official | this pipeline |
|---|---|---|
| Neighbourhoods | 21 | 21 matched by name |
| Assembly areas / candidates | 150 | 226 |
| Surface (m²) | 1,160,402 | 1,658,872 |
| Rank correlation of surface (Spearman) |  | 0.63 |
| Population (official 2022 / WorldPop 2025) | 483,064 | 487,528 |
| Rank correlation of population (Spearman) |  | 0.95 |

<details><summary>Per neighbourhood</summary>

| Neighbourhood | official areas | official m² | OSM candidates | OSM m² | official pop. 2022 | WorldPop 2025 |
|---|---|---|---|---|---|---|
| ACIBADEM | 14 | 100,119 | 11 | 67,446 | 29,563 | 26,953 |
| BOSTANCI | 15 | 40,313 | 22 | 71,031 | 33,638 | 33,816 |
| CADDEBOSTAN | 5 | 101,060 | 11 | 221,326 | 21,058 | 28,889 |
| CAFERAĞA | 4 | 66,511 | 16 | 193,196 | 22,347 | 20,749 |
| DUMLUPINAR | 4 | 23,773 | 7 | 42,757 | 10,185 | 13,019 |
| ERENKÖY | 4 | 27,098 | 8 | 31,032 | 35,530 | 31,990 |
| EĞİTİM | 6 | 175,287 | 6 | 193,314 | 14,204 | 18,401 |
| FENERBAHÇE | 4 | 9,387 | 15 | 180,377 | 21,405 | 26,866 |
| FENERYOLU | 8 | 16,459 | 6 | 11,856 | 26,542 | 23,347 |
| FİKİRTEPE | 1 | 851.86 | 1 | 2,887 | 12,390 | 11,092 |
| GÖZTEPE | 11 | 146,651 | 19 | 175,539 | 40,858 | 39,643 |
| HASANPAŞA | 6 | 86,531 | 8 | 60,294 | 16,564 | 12,874 |
| KOZYATAĞI | 12 | 24,223 | 8 | 24,395 | 37,743 | 34,372 |
| KOŞUYOLU | 10 | 53,307 | 11 | 41,034 | 6,912 | 10,839 |
| MERDİVENKÖY | 13 | 138,830 | 15 | 42,256 | 32,395 | 30,042 |
| ON DOKUZ MAYIS | 12 | 79,855 | 19 | 108,693 | 32,752 | 31,415 |
| OSMANAĞA | 3 | 24,637 | 5 | 28,375 | 8,652 | 11,374 |
| RASİMPAŞA | 3 | 4,701 | 3 | 4,408 | 13,369 | 13,410 |
| SAHRAYICEDİT | 10 | 34,469 | 19 | 60,553 | 31,423 | 28,175 |
| SUADİYE | 4 | 3,681 | 12 | 88,338 | 27,120 | 29,579 |
| ZÜHTÜPAŞA | 1 | 2,657 | 4 | 9,765 | 8,414 | 10,683 |

</details>

## Assumptions

* Walking speed 4.0 km/h; the straight line from a cell centre to the nearest road (≤ 250 m) is walked at 4.0 km/h.
* Driving at free-flow speed: OSM `maxspeed`, otherwise a default per road class (`scripts/config.py`). No traffic, no road damage.
* A park or school polygon can be entered from every road node within 25 m of it.
* Routing stops at 60 minutes.
