"""
Settings shared by all scripts. Change the study area or the assumptions here.

Every assumption that changes a result is a named constant below, so the README
can quote it and a reader can rerun the analysis with another value.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"      # downloaded source files (not committed, see .gitignore)
WORK = ROOT / "data" / "work"    # intermediate files written by prepare.py
DOCS_DATA = ROOT / "docs" / "data"
RESULTS = ROOT / "results"

# --------------------------------------------------------------------------- study area
# The nine central (metropolitan core) districts of Ankara.
STUDY = {
    "key": "ankara",
    "label": "Ankara (9 central districts)",
    "province": "Ankara",
    "districts": ["Altındağ", "Çankaya", "Etimesgut", "Gölbaşı", "Keçiören",
                  "Mamak", "Pursaklar", "Sincan", "Yenimahalle"],
    "epsg": 5255,                # TUREF / TM33, metric CRS for Ankara (central meridian 33°E)
    "network_buffer_m": 2000,    # roads this far outside the districts are kept, so edge cells route correctly
}

# Kadıköy (İstanbul) publishes its official assembly areas per neighbourhood as open data.
# It is used only to check how well OpenStreetMap stands in for the official list.
VALIDATION = {
    "key": "kadikoy",
    "label": "Kadıköy (İstanbul)",
    "province": "İstanbul",
    "districts": ["Kadıköy"],
    "epsg": 5254,                # TUREF / TM30 (central meridian 30°E)
    "network_buffer_m": 500,
}

# --------------------------------------------------------------------------- assumptions
WALK_SPEED_KMH = 4.0        # walking speed after an earthquake (crowds, debris, elderly people)
DRIVE_SPEED_DEFAULT = {     # free-flow km/h when OSM has no usable maxspeed tag
    "motorway": 100, "motorway_link": 60, "trunk": 80, "trunk_link": 50,
    "primary": 60, "primary_link": 40, "secondary": 50, "secondary_link": 40,
    "tertiary": 40, "tertiary_link": 30, "unclassified": 30, "residential": 30,
    "living_street": 10, "service": 20,
}
SNAP_SPEED_KMH = 4.0        # the straight line from a cell centre to the nearest road is walked
MAX_SNAP_M = 250            # population cells farther than this from any road are reported, not routed
FACILITY_ENTRY_M = 25       # a park/school polygon can be entered from every road node this close to it
MAX_COST_S = 3600           # routing stops after 60 min; slower cells are reported as "> 60 min"
THRESHOLDS_MIN = [5, 10, 15]
MIN_PARK_M2 = 1000          # parks smaller than this are not counted as assembly-area candidates
WEB_GRID_M = 500            # cell size of the web-map grid (the analysis itself uses the 100 m WorldPop grid)

# --------------------------------------------------------------------------- sources
DISTRICT_GIS = ("https://raw.githubusercontent.com/MustafaBugraBEKDEMiR/turkiye-district-gis/"
                "005873a/data/raw/")
SOURCES = {
    "osm_pbf": {
        "url": "https://download.geofabrik.de/europe/turkey-latest.osm.pbf",
        "file": "turkey-latest.osm.pbf",
        "licence": "© OpenStreetMap contributors, ODbL 1.0",
    },
    "worldpop": {
        "url": ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/TUR/"
                "v1/100m/constrained/tur_pop_2025_CN_100m_R2025A_v1.tif"),
        "file": "tur_pop_2025_CN_100m_R2025A_v1.tif",
        "licence": "WorldPop R2025A, CC BY 4.0",
    },
    "districts": {
        "url": DISTRICT_GIS + "geoBoundaries-TUR-ADM2_simplified.geojson",
        "file": "geoBoundaries-TUR-ADM2_simplified.geojson",
        "licence": "geoBoundaries gbOpen (OpenStreetMap), ODbL 1.0",
    },
    "provinces": {
        "url": DISTRICT_GIS + "geoBoundaries-TUR-ADM1_simplified.geojson",
        "file": "geoBoundaries-TUR-ADM1_simplified.geojson",
        "licence": "geoBoundaries gbOpen (OpenStreetMap), ODbL 1.0",
    },
    "tuik_districts": {
        "url": DISTRICT_GIS + "tuik-adnks-il-ilce.json",
        "file": "tuik-adnks-il-ilce.json",
        "licence": "TÜİK ADNKS 2021 (public statistics)",
    },
    "kadikoy_areas": {
        "url": ("https://acikveri.kadikoy.bel.tr/dataset/7955961c-298a-4121-92d2-c77c53b2783c/"
                "resource/9328e758-cc03-4945-a4d9-17381d0e3a8b/download/"
                "mahalle_afet_toplanma_alanlari_miktari.csv"),
        "file": "kadikoy_mahalle_afet_toplanma_alanlari.csv",
        "licence": "Kadıköy Belediyesi Açık Veri, CC BY 3.0",
    },
    "kadikoy_per_capita": {
        "url": ("https://acikveri.kadikoy.bel.tr/dataset/fe07be6d-970b-414a-b2d2-00abcf4a334a/"
                "resource/541872aa-acd5-483a-bb79-0bf69b789f4b/download/"
                "mahallelere_gore_kisi_basi_toplanma_alani.xlsx"),
        "file": "kadikoy_kisi_basi_toplanma_alani.xlsx",
        "licence": "Kadıköy Belediyesi Açık Veri, CC BY 3.0",
    },
}

# Facility kinds. "assembly" kinds are candidates for a post-earthquake assembly area.
FACILITY_KINDS = {
    "assembly_point": {"assembly": True,  "label": "Assembly point (OSM emergency=assembly_point)"},
    "park":           {"assembly": True,  "label": f"Park ≥ {MIN_PARK_M2} m² (OSM leisure=park)"},
    "school":         {"assembly": True,  "label": "School grounds (OSM amenity=school)"},
    "hospital":       {"assembly": False, "label": "Hospital (OSM amenity=hospital)"},
    "fire_station":   {"assembly": False, "label": "Fire station (OSM amenity=fire_station)"},
}
