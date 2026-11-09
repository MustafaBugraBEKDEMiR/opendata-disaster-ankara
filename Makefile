# Full pipeline on real data. Needs PG* variables (see README) and osmium-tool.
PY ?= python3

all: download prepare build export

download:
	$(PY) scripts/download.py
prepare:
	$(PY) scripts/prepare.py
build:
	$(PY) scripts/build.py
export:
	$(PY) scripts/export_web.py
	$(PY) scripts/make_figure.py
	$(PY) scripts/make_gif.py
test:
	$(PY) tests/run_tests.py

.PHONY: all download prepare build export test
