PYTHON ?= python3
IDF_PY ?= idf.py
VENV ?= .venv
IDF_BUILD_DIR ?= build/idf
IDF_GATE_BUILD_DIR ?= build/idf-gate
IDF_GATE_SDKCONFIG ?= sdkconfig.defaults
IDF_GATE_PROFILE ?= esp32s3-devkitc1-n8
HOST_BUILD_DIR ?= build/host-tests
N8_BUILD_DIR ?= build/idf-n8
N32R16V_BUILD_DIR ?= build/idf-n32r16v
SDKCONFIG_DEFAULTS ?= sdkconfig.defaults;sdkconfig.defaults.n16r8

.PHONY: setup setup-dev install-hooks check check-fast check-push fmt lint clang-tidy-host \
        idf-gate-build train-quick train-full test test-python test-host panel build build-n8 \
        build-n32r16v flash monitor flash-monitor menuconfig clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements-lock.txt

setup-dev: setup
	$(VENV)/bin/python -m pip install -r requirements-dev.txt
	$(MAKE) install-hooks

install-hooks:
	$(VENV)/bin/pre-commit install
	$(VENV)/bin/pre-commit install --hook-type pre-push

check-fast:
	$(VENV)/bin/pre-commit run --all-files

check: check-fast
	bash scripts/quality_gate_push.sh

check-push:
	bash scripts/quality_gate_push.sh

idf-gate-build:
	bash scripts/idf_gate_build.sh

clang-tidy-host:
	bash scripts/run_clang_tidy_host.sh

fmt:
	$(VENV)/bin/pre-commit run --all-files ruff ruff-format clang-format

lint: check-fast

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

panel:
	$(VENV)/bin/python -m tools.panel --host 127.0.0.1 --port 8765

build:
	$(IDF_PY) -B $(IDF_BUILD_DIR) \
		-D "SDKCONFIG_DEFAULTS=$(SDKCONFIG_DEFAULTS)" \
		-D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n16r8 build

build-n8:
	$(IDF_PY) -B $(N8_BUILD_DIR) \
		-D "SDKCONFIG_DEFAULTS=sdkconfig.defaults" \
		-D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n8 build

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
