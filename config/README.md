# Project configuration

| Path | Purpose |
|------|---------|
| `idf/sdkconfig.defaults` | ESP-IDF base defaults (all boards) |
| `idf/sdkconfig.defaults.n16r8` | Default profile (16 MB flash + PSRAM) |
| `idf/sdkconfig.defaults.n32r16v` | 32 MB flash + PSRAM module |
| `../schemas/` | ML / wire data contract (not board Kconfig) |

Local `sdkconfig` is generated at the **repo root** by `idf.py` / `make build` and is gitignored.

Override defaults:

```bash
make build
# or
idf.py -B build/idf \
  -D SDKCONFIG_DEFAULTS="config/idf/sdkconfig.defaults;config/idf/sdkconfig.defaults.n16r8" \
  build
```
