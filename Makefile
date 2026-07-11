PYTHON ?= python3
IDF_PY ?= idf.py
VENV ?= .venv
IDF_BUILD_DIR ?= build/idf
HOST_BUILD_DIR ?= build/host-tests
N32R16V_BUILD_DIR ?= build/idf-n32r16v

.PHONY: setup train-quick train-full test test-python test-host build build-n32r16v \
        flash monitor flash-monitor menuconfig clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements-lock.txt

train-quick:
	$(VENV)/bin/python -m tools.ml.pipeline --quick

train-full:
	$(VENV)/bin/python -m tools.ml.pipeline --full

test: test-python test-host

test-python:
	$(VENV)/bin/python -m pytest

test-host:
	cmake -S test/host -B $(HOST_BUILD_DIR)
	cmake --build $(HOST_BUILD_DIR) --parallel
	ctest --test-dir $(HOST_BUILD_DIR) --output-on-failure

build:
	$(IDF_PY) -B $(IDF_BUILD_DIR) -D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n8 build

build-n32r16v:
	$(IDF_PY) -B $(N32R16V_BUILD_DIR) \
		-D "SDKCONFIG_DEFAULTS=sdkconfig.defaults.n32r16v" \
		-D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n32r16v build

flash:
	$(IDF_PY) -B $(IDF_BUILD_DIR) flash

monitor:
	$(IDF_PY) -B $(IDF_BUILD_DIR) monitor

flash-monitor:
	$(IDF_PY) -B $(IDF_BUILD_DIR) flash monitor

menuconfig:
	$(IDF_PY) -B $(IDF_BUILD_DIR) menuconfig

clean:
	rm -rf build sdkconfig sdkconfig.old managed_components dependencies.lock
