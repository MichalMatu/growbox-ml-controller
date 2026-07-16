PYTHON ?= python3
VENV ?= .venv
PY := $(VENV)/bin/python
RUN_IDF := bash scripts/run_idf.sh

IDF_BUILD_DIR ?= build/idf
IDF_GATE_BUILD_DIR ?= build/idf-gate
HOST_BUILD_DIR ?= build/host-tests
N8_BUILD_DIR ?= build/idf-n8
N32R16V_BUILD_DIR ?= build/idf-n32r16v
# ESP-IDF defaults live under config/idf/ (local sdkconfig stays at repo root).
SDKCONFIG_DEFAULTS ?= config/idf/sdkconfig.defaults;config/idf/sdkconfig.defaults.n16r8
IDF_BUILD_ARGS := -D "SDKCONFIG_DEFAULTS=$(SDKCONFIG_DEFAULTS)" -D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n16r8

ifdef PORT
IDF_PORT_ARGS := -p $(PORT)
endif

.DEFAULT_GOAL := help

.PHONY: help setup setup-dev install-hooks ensure-venv ensure-idf \
        check check-fast check-push fmt lint clang-tidy-host schema schema-check \
        train-quick train-full probe-sim \
        test-board board-e2e \
        test test-python test-host test-panel test-layout test-visual panel-screenshots \
        panel ports idf-gate-build build build-n8 build-n32r16v rebuild clean-idf \
        flash monitor flash-monitor menuconfig clean

help: ## Lista komend make (domyślny cel)
	@printf '\nGrowbox ML — make targets\n\n'
	@printf '  Firmware (wymaga ESP-IDF — scripts/source_idf.sh):\n'
	@printf '    make build          — kompilacja domyślnego profilu N16R8\n'
	@printf '    make flash          — build + wgranie na płytkę\n'
	@printf '    make flash-monitor  — build + flash + monitor serial\n'
	@printf '    make monitor        — monitor serial (bez buildu)\n'
	@printf '    make rebuild        — wyczyść build/idf i zbuduj od nowa\n'
	@printf '    make menuconfig     — konfiguracja sdkconfig\n'
	@printf '    PORT=/dev/cu.X make flash   — wybór portu USB\n\n'
	@printf '  Panel i serial:\n'
	@printf '    make panel          — serwer panelu http://127.0.0.1:8765\n'
	@printf '    make ports          — lista portów USB (do Połącz w panelu)\n\n'
	@printf '  Testy i jakość:\n'
	@printf '    make test           — pytest + testy host C++\n'
	@printf '    make test-panel     — testy panelu (API + E2E)\n'
	@printf '    make test-layout    — regresja układu UI panelu\n'
	@printf '    make test-visual    — screenshot diff panelu (wymaga setup-dev)\n'
	@printf '    make panel-screenshots — odśwież baseline zrzutów panelu\n'
	@printf '    make check-fast     — lint/format + schema check\n'
	@printf '    make check-push     — pełny quality gate (jak pre-push)\n\n'
	@printf '  Python / ML:\n'
	@printf '    make setup          — venv + requirements-lock.txt\n'
	@printf '    make setup-dev      — setup + dev deps + pre-commit\n'
	@printf '    make train-quick    — smoke treningu (CI; nie produkcja)\n'
	@printf '    make train-full     — pełny trening (po symulatorze)\n'
	@printf '    make probe-sim      — open-loop walidacja fizyki (przed ML)\n'
	@printf '    make schema-check   — zgodność schema z EnvironmentSchema.h\n'
	@printf '    make test-board     — test E2E na płytce (GROWBOX_BOARD_PORT)\n\n'
	@printf '  Inne profile firmware:\n'
	@printf '    make build-n8       — build bez PSRAM (DevKitC N8)\n'
	@printf '    make build-n32r16v  — moduł N32R16V (32 MB flash + PSRAM)\n'
	@printf '    make idf-gate-build — szybki build gate CI (N8)\n\n'
	@printf '  Sprzątanie:\n'
	@printf '    make clean-idf      — usuń tylko build/idf\n'
	@printf '    make clean          — usuń build/, sdkconfig, managed_components\n\n'

ensure-venv:
	@test -x '$(PY)' || { printf 'Brak .venv — uruchom: make setup\n' >&2; exit 1; }

ensure-idf:
	@bash -c 'source scripts/source_idf.sh' 2>/dev/null || { \
		printf 'ESP-IDF niedostępne — uruchom: source ~/esp/esp-idf/export.sh\n' >&2; \
		printf 'albo: source scripts/source_idf.sh\n' >&2; \
		exit 1; \
	}

setup:
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-lock.txt

setup-dev: setup
	$(PY) -m pip install -r requirements-dev.txt
	$(MAKE) install-hooks

install-hooks: ensure-venv
	$(VENV)/bin/pre-commit install
	$(VENV)/bin/pre-commit install --hook-type pre-push

check-fast: ensure-venv
	$(VENV)/bin/pre-commit run --all-files

check: check-fast
	bash scripts/quality_gate_push.sh

check-push:
	bash scripts/quality_gate_push.sh

idf-gate-build:
	bash scripts/idf_gate_build.sh

clang-tidy-host:
	bash scripts/run_clang_tidy_host.sh

fmt: ensure-venv
	$(VENV)/bin/pre-commit run --all-files ruff ruff-format clang-format

lint: check-fast

schema-check: ensure-venv
	bash scripts/check_schema_v3.sh

schema: schema-check

train-quick: ensure-venv
	$(PY) -m tools.ml.pipeline --quick

train-full: ensure-venv
	$(PY) -m tools.ml.pipeline --full

probe-sim: ensure-venv
	$(PY) -m tools.ml.probe_simulator --save-series --out-dir build/sim-probe

test-board: ensure-venv
	$(PY) -m pytest tests/test_board_e2e.py -q

board-e2e: flash test-board

test: test-python test-host

test-python: ensure-venv
	$(PY) -m pytest

test-host:
	cmake -S test/host -B $(HOST_BUILD_DIR)
	cmake --build $(HOST_BUILD_DIR) --parallel
	ctest --test-dir $(HOST_BUILD_DIR) --output-on-failure

test-panel: ensure-venv
	$(PY) -m pytest tests/test_panel.py tests/test_panel_e2e.py tests/test_panel_fixtures.py -q

test-layout: ensure-venv
	$(PY) -m pytest tests/test_panel_layout.py tests/test_panel_tokens.py -q

test-visual: ensure-venv
	$(PY) -m pytest tests/test_panel_visual.py -q

panel-screenshots: ensure-venv
	UPDATE_PANEL_SCREENSHOTS=1 $(PY) -m pytest tests/test_panel_visual.py -q

panel: ensure-venv
	$(PY) -m tools.panel --host 127.0.0.1 --port 8765

ports: ensure-venv
	$(PY) -m serial.tools.list_ports

build: ensure-idf
	$(RUN_IDF) -B $(IDF_BUILD_DIR) $(IDF_BUILD_ARGS) build

build-n8: ensure-idf
	$(RUN_IDF) -B $(N8_BUILD_DIR) \
		-D "SDKCONFIG_DEFAULTS=config/idf/sdkconfig.defaults" \
		-D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n8 build

build-n32r16v: ensure-idf
	$(RUN_IDF) -B $(N32R16V_BUILD_DIR) \
		-D "SDKCONFIG_DEFAULTS=config/idf/sdkconfig.defaults.n32r16v" \
		-D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n32r16v build

rebuild: clean-idf build

clean-idf:
	rm -rf $(IDF_BUILD_DIR)

flash: build
	$(RUN_IDF) -B $(IDF_BUILD_DIR) $(IDF_PORT_ARGS) flash

monitor: ensure-idf
	$(RUN_IDF) -B $(IDF_BUILD_DIR) $(IDF_PORT_ARGS) monitor

flash-monitor: build
	$(RUN_IDF) -B $(IDF_BUILD_DIR) $(IDF_PORT_ARGS) flash monitor

menuconfig: ensure-idf
	$(RUN_IDF) -B $(IDF_BUILD_DIR) menuconfig

clean:
	rm -rf build sdkconfig sdkconfig.old managed_components dependencies.lock
