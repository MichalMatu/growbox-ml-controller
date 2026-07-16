# Kontynuacja audytu exhaustive na Raspberry Pi 5

Projekt przeniesiony z **MacBook Air M1** na **Raspberry Pi 5 (16 GB RAM)**. Pi działa 24/7 — audyt na płytce ESP może lecieć bez przerwy (Mac usypiał i przerywał test).

## Co było w toku

| Element | Wartość |
|---------|---------|
| Test | `exhaustive_board_audit` — CONFIG_MATRIX × siatki wartości czujników × previous |
| Plan | **460 395** case (z `--skip-heavy-over 50000`) |
| Zatrzymano na | **6510** case (~1,4%) — profil **P03** |
| Ostatni case | `P03/X[…]` — `status=ok`, `errors=0` |
| Checkpoint | `build/audit/exhaustive_checkpoint.jsonl` |
| Log | `build/audit/exhaustive_board.log` |
| Raport (po zakończeniu) | `build/audit/exhaustive_board_audit.json` |

Test zatrzymany celowo na Macu (`pkill` / SIGTERM). Checkpoint **nie jest w git** (`build/` w `.gitignore`) — trzeba go skopiować ręcznie na Pi.

## Różnice Mac M1 → Pi 5

| | MacBook Air M1 | Raspberry Pi 5 |
|--|----------------|----------------|
| Port USB serial | `/dev/cu.usbmodem1101` | zwykle `/dev/ttyACM0` lub `/dev/ttyUSB0` |
| Zmienna środowiska | `GROWBOX_BOARD_PORT` | to samo |
| Panel | opcjonalnie `:8765` | **nie uruchamiaj** podczas audytu (jeden klient na serial) |
| Czas do końca | ~46 h @ ~380 ms/case | ten sam порядок wielkości |

## Przygotowanie na Pi (jednorazowo)

```bash
# klon repo (ta sama gałąź co na Macu)
git clone <url-repo> ~/ml
cd ~/ml
git checkout agent/migrate-firmware-to-esp-idf   # lub aktualna gałąź

make setup

# grupa dialout (serial)
sudo usermod -aG dialout $USER
# wyloguj i zaloguj ponownie

# ESP32 pod USB — sprawdź port
ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

### Skopiuj checkpoint z Maca

Z Maca (dostosuj host i ścieżkę):

```bash
scp /Users/michal/Documents/PlatformIO/Projects/ml/build/audit/exhaustive_checkpoint.jsonl \
    pi@<adres-pi>:~/ml/build/audit/
```

Opcjonalnie log:

```bash
scp build/audit/exhaustive_board.log pi@<adres-pi>:~/ml/build/audit/
```

Na Pi:

```bash
mkdir -p ~/ml/build/audit
wc -l ~/ml/build/audit/exhaustive_checkpoint.jsonl   # oczekiwane: 6510
```

## Wznowienie audytu (24/7)

Uruchom w **tmux** (przeżyje rozłączenie SSH):

```bash
tmux new -s audit
cd ~/ml

export GROWBOX_BOARD_PORT=/dev/ttyACM0   # dostosuj do ls /dev/ttyACM*

.venv/bin/python -m tools.ml.exhaustive_board_audit \
  --port "$GROWBOX_BOARD_PORT" \
  --skip-heavy-over 50000 \
  --checkpoint build/audit/exhaustive_checkpoint.jsonl \
  --report build/audit/exhaustive_board_audit.json \
  2>&1 | tee -a build/audit/exhaustive_board.log
```

Odłączenie od SSH: `Ctrl+B`, potem `D`.
Powrót: `tmux attach -t audit`

Alternatywa przez Makefile:

```bash
export GROWBOX_BOARD_PORT=/dev/ttyACM0
make test-board-exhaustive
```

(make domyślnie używa `/dev/cu.usbmodem1101` — na Pi **musisz** ustawić `GROWBOX_BOARD_PORT`.)

## Jak działa wznowienie

- Skrypt czyta `exhaustive_checkpoint.jsonl` i **pomija** case ze `status: ok`.
- Case ze `fail` / `error` (timeout serial, reset ESP) zostaną **powtórzone** po restarcie.
- Raport JSON powstaje **na końcu** biegu; postęp na żywo:

```bash
wc -l build/audit/exhaustive_checkpoint.jsonl
tail -f build/audit/exhaustive_board.log
```

Co ~50 case w logu: `[N] P03/X[…] e=0 w=0 379ms` — `e` = błędy, `w` = warny ML.

## PASS / FAIL

| Wynik | Znaczenie |
|-------|-----------|
| **PASS** | `error_count: 0` w `exhaustive_board_audit.json` |
| **WARN** | ML nie zareagował na oczywisty off-target — do przejrzenia, nie blokuje flashu |
| **FAIL** | `error_count > 0` — safety, schema lub firmware |

## Po zakończeniu exhaustive

1. Szybki regres (opcjonalnie na Pi lub Macu po flashu):
   - `python -m tools.ml.board_engine_audit --matrix-only`
   - `python -m tools.ml.panel_endpoint_audit`
2. Rozszerzenia (kolejność dowolna):
   - `validity_matrix_audit` — 32 768 masek validity (~3–5 h)
   - `make train-full` + flash — po dopracowaniu symulatora
   - exhaustive **bez** `--skip-heavy-over` — tylko jeśli potrzebne profile P05/P06 (bardzo długo)

## Typowe problemy na Pi

| Problem | Rozwiązanie |
|---------|-------------|
| `Permission denied` na `/dev/ttyACM0` | `usermod -aG dialout`, re-login |
| `multiple access on port` | zatrzymaj panel / inny monitor serial |
| timeout po resecie ESP | poczekaj ~2 s, uruchom ponownie — checkpoint wznawia |
| brak portu po odłączeniu USB | powered hub USB; `dmesg \| tail` |

## Flash i build firmware

Na Pi **nie jest wymagane** do samego audytu. Firmware wgrany na ESP z Maca wystarczy. Build (`make flash`) można dalej robić na Macu z ESP-IDF; Pi służy głównie do **testów serial 24/7**.
