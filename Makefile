PYTHON ?= python3
PIO ?= pio
VENV ?= .venv

.PHONY: setup train-quick train-full test build upload monitor clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements-lock.txt

train-quick:
	$(VENV)/bin/python -m tools.ml.pipeline --quick

train-full:
	$(VENV)/bin/python -m tools.ml.pipeline --full

test:
	$(VENV)/bin/python -m pytest
	$(PIO) test -e native

build:
	$(PIO) run -e esp32s3-devkitc1-n8

upload:
	$(PIO) run -e esp32s3-devkitc1-n8 -t upload

monitor:
	$(PIO) device monitor -b 115200

clean:
	$(PIO) run -t clean
	rm -rf .pio build .pytest_cache .coverage htmlcov artifacts
