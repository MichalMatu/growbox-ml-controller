# Dwie maszyny deweloperskie — Mac M1 + Raspberry Pi 5

Projekt **growbox-ml-controller** można rozwijać **niezależnie** na:

| Maszyna | Rola typowa |
|---------|-------------|
| **MacBook Air M1** | Kod, panel UI, szybki build/flash, testy lokalne |
| **Raspberry Pi 5 (16 GB)** | Build/flash, testy serial **24/7**, długie audyty (tmux) |

Synchronizacja kodu: **git** (`pull` / `push`). Każda maszyna ma **własny** `.venv`, `build/`, `sdkconfig` i instalację ESP-IDF — artefakty buildu **nie są współdzielone** (są w `.gitignore`).

---

## Zasady współpracy (obie maszyny)

1. **Przed pracą:** `git pull` na maszynie, na której zaczynasz.
2. **Po zmianach:** commit + push; druga maszyna robi `git pull`.
3. **ESP32 pod USB:** fizycznie podłączony do **jednej** maszyny naraz (przenosisz kabel lub zostawiasz na Pi pod audyty).
4. **Port serial:** ustaw per maszyna (patrz tabela poniżej).
5. **Panel + audyt serial:** tylko **jeden** klient na port — przed audytem `disconnect` panelu lub nie uruchamiaj panelu.
6. **Checkpointy audytu** (`build/audit/*.jsonl`): opcjonalnie `scp`/`rsync` między maszynami — nie ma ich w git.

### Porty i zmienne

| | MacBook Air M1 | Raspberry Pi 5 |
|--|----------------|----------------|
| Port typowy | `/dev/cu.usbmodem1101` | `/dev/ttyACM0` lub `/dev/ttyUSB0` |
| `make flash` | `PORT=/dev/cu.usbmodem1101 make flash` | `PORT=/dev/ttyACM0 make flash` |
| Python / audyt | `export GROWBOX_BOARD_PORT=/dev/cu.usbmodem1101` | `export GROWBOX_BOARD_PORT=/dev/ttyACM0` |
| Lista portów | `make ports` | `make ports` |

---

## Setup jednorazowy — MacBook Air M1

```bash
cd ~/Documents/PlatformIO/Projects/ml   # lub inna ścieżka
git clone <url-repo> .                    # jeśli świeży klon
git checkout main

make setup-dev          # venv + pre-commit (opcjonalnie setup bez -dev)

# ESP-IDF 5.5.1 (jeśli jeszcze nie ma)
mkdir -p ~/esp && cd ~/esp
git clone -b v5.5.1 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3
# w każdej nowej sesji terminala:
source ~/esp/esp-idf/export.sh
# lub z katalogu repo:
source scripts/source_idf.sh
```

### Pełny flow na Macu

```bash
source scripts/source_idf.sh
make check-fast                    # lint / format
make test                          # pytest + host C++
PORT=/dev/cu.usbmodem1101 make flash
export GROWBOX_BOARD_PORT=/dev/cu.usbmodem1101
make test-board                    # E2E na płytce

make panel                         # http://127.0.0.1:8765
python -m tools.ml.board_engine_audit --matrix-only
python -m tools.ml.panel_endpoint_audit

make train-quick                   # smoke ML (CI)
make probe-sim                     # fizyka symulatora
```

---

## Setup jednorazowy — Raspberry Pi 5 (16 GB)

Pi ma **ten sam komplet** możliwości co Mac: build, flash, panel, trening, audyty.

### System (Debian / Raspberry Pi OS 64-bit)

```bash
sudo apt update
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0 \
  build-essential

sudo usermod -aG dialout $USER
# wyloguj i zaloguj — dostęp do /dev/ttyACM*
```

### Repo + Python

```bash
git clone https://github.com/MichalMatu/growbox-ml-controller.git ~/ml
cd ~/ml
git checkout main

make setup-dev
```

### ESP-IDF 5.5.1 na Pi (aarch64)

```bash
mkdir -p ~/esp && cd ~/esp
git clone -b v5.5.1 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32s3
```

Dodaj do `~/.bashrc` (opcjonalnie):

```bash
alias get_idf='. ~/esp/esp-idf/export.sh'
```

Pierwszy `make build` na Pi trwa **dłużej** niż na Macu — to normalne. 16 GB RAM wystarcza z zapasem.

### Pełny flow na Pi

```bash
cd ~/ml
source scripts/source_idf.sh

make build
PORT=/dev/ttyACM0 make flash          # dostosuj PORT po: make ports

export GROWBOX_BOARD_PORT=/dev/ttyACM0
make test-board
make test-board-exhaustive            # długi audyt — patrz sekcja poniżej

# panel (opcjonalnie; nie razem z audytem na tym samym porcie)
make panel
```

Testy host C++ i pełny quality gate:

```bash
make test-host
make check-push                       # jak przed push — wolniejsze, wymaga IDF
```

---

## Kontynuacja audytu exhaustive (stan na migracji)

Audyt zatrzymany na Macu; wznawiany na Pi (lub ponownie na Macu — ten sam checkpoint).

| Element | Wartość |
|---------|---------|
| Test | `exhaustive_board_audit` |
| Plan | **460 395** case (`--skip-heavy-over 50000`) |
| Zatrzymano na | **6510** case (~1,4%) — profil **P03** |
| Ostatni case | `P03/X[…]` — `status=ok`, `errors=0` |
| Checkpoint | `build/audit/exhaustive_checkpoint.jsonl` |
| Log | `build/audit/exhaustive_board.log` |
| Raport (koniec) | `build/audit/exhaustive_board_audit.json` |

### Skopiuj checkpoint Mac → Pi (jednorazowo)

Z Maca:

```bash
scp /Users/michal/Documents/PlatformIO/Projects/ml/build/audit/exhaustive_checkpoint.jsonl \
    pi@<adres-pi>:~/ml/build/audit/
# opcjonalnie:
scp build/audit/exhaustive_board.log pi@<adres-pi>:~/ml/build/audit/
```

Na Pi:

```bash
mkdir -p ~/ml/build/audit
wc -l ~/ml/build/audit/exhaustive_checkpoint.jsonl   # oczekiwane: 6510
```

### Wznowienie 24/7 na Pi (tmux)

```bash
tmux new -s audit
cd ~/ml
source scripts/source_idf.sh   # nie wymagane do audytu, ale wygodne w jednej sesji

export GROWBOX_BOARD_PORT=/dev/ttyACM0

.venv/bin/python -m tools.ml.exhaustive_board_audit \
  --port "$GROWBOX_BOARD_PORT" \
  --skip-heavy-over 50000 \
  --checkpoint build/audit/exhaustive_checkpoint.jsonl \
  --report build/audit/exhaustive_board_audit.json \
  2>&1 | tee -a build/audit/exhaustive_board.log
```

Odłączenie SSH: `Ctrl+B`, `D`. Powrót: `tmux attach -t audit`.

Alternatywa: `export GROWBOX_BOARD_PORT=/dev/ttyACM0 && make test-board-exhaustive`

### Postęp i PASS/FAIL

```bash
wc -l build/audit/exhaustive_checkpoint.jsonl
tail -f build/audit/exhaustive_board.log
```

- Wznowienie pomija case ze `status: ok` w checkpoint.
- **PASS** = `error_count: 0` w `exhaustive_board_audit.json`.
- **WARN** = słabe miejsca ML — do przejrzenia, nie blokuje flashu.

Szacowany czas od 6510: **~46 h** @ ~380 ms/case.

---

## Typowy dzień pracy na dwóch maszynach

### Scenariusz A — kodujesz na Macu, Pi testuje w tle

```bash
# Mac
git pull
# ... edycja kodu ...
make check-fast && make test
git commit -am "..." && git push

# Pi (SSH)
git pull
# jeśli zmiana firmware:
source scripts/source_idf.sh && PORT=/dev/ttyACM0 make flash
# audyt już leci w tmux — nie restartuj bez potrzeby
```

### Scenariusz B — kodujesz na Pi

Ten sam schemat — `git push` z Pi, `git pull` na Macu. Obie maszyny mają ESP-IDF i `make flash`.

### Scenariusz C — przenosisz ESP z Pi na Mac

1. Zatrzymaj audyt / monitor na Pi.
2. Odłącz USB, podłącz do Maca.
3. `make ports` — nowy port.
4. `PORT=... make flash` na Macu.

---

## Co jest / nie jest w git

| W git | Lokalnie per maszyna |
|-------|----------------------|
| Źródła, schema, Makefile | `.venv/` |
| Wyeksportowane nagłówki modelu | `build/` (IDF, host-tests, audit) |
| `config/idf/sdkconfig.defaults*` | `sdkconfig` (generowany przy build) |
| | `~/esp/esp-idf/` |
| | checkpointy `build/audit/*.jsonl` |

**Nie commituj** `build/`, `sdkconfig`, `.venv`. Checkpoint audytu przenosisz `scp` tylko gdy wznawiasz na drugiej maszynie.

---

## Po zakończeniu exhaustive

1. Regres na maszynie z ESP:
   ```bash
   export GROWBOX_BOARD_PORT=<port>
   python -m tools.ml.board_engine_audit --matrix-only
   python -m tools.ml.panel_endpoint_audit   # wymaga panelu
   ```
2. Rozszerzenia (dowolna maszyna z ESP + czas):
   - `make test-board-validity-matrix` — 32 768 masek validity
   - `make train-full` + `make flash` — po dopracowaniu symulatora
   - exhaustive bez `--skip-heavy-over` — profile P05/P06 (bardzo długo)

---

## Typowe problemy

| Problem | Rozwiązanie |
|---------|-------------|
| `ESP-IDF niedostępne` | `source ~/esp/esp-idf/export.sh` lub `source scripts/source_idf.sh` |
| `Permission denied` na `/dev/ttyACM0` (Pi) | `usermod -aG dialout`, re-login |
| `multiple access on port` | jeden klient serial; panel disconnect lub stop audytu |
| Build na Pi wolny | pierwszy build długi; `ccache` już w zależnościach apt |
| Różny `sdkconfig` między maszynami | OK — generowany lokalnie z `config/idf/sdkconfig.defaults*` |
| Konflikt po `git pull` | rozwiąż merge; **nie** kopiuj `build/` między maszynami |

---

## Szybka ściąga komend

```bash
# obie maszyny
source scripts/source_idf.sh
make setup-dev          # raz
git pull / git push     # sync

# flash (PORT per maszyna)
PORT=<port> make flash

# audyt (GROWBOX_BOARD_PORT per maszyna)
export GROWBOX_BOARD_PORT=<port>
make test-board-exhaustive

# panel
make panel              # :8765
make ports              # lista USB
```
