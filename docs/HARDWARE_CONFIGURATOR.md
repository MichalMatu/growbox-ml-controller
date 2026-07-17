# Hardware configurator (web) — założenia

## Cel produktu

Klient (lub operator) opisuje **swój growbox** zgodnie z kontraktem **v4**:

- które donice, czujniki i aktuatory są zainstalowane,
- limity sprzętowe (W, m³/h, g/h, flow…),
- cele (targets) i ewentualnie stan startowy,

oraz **eksportuje JSON** używalny później jako scenariusz / seed pod trening i board (`load_scenario`).

**Nie jest to** w tej fazie: cyfrowy bliźniak 3D, live serial, teacher, trening ML w przeglądarce.

## SSOT

| Warstwa | Plik |
|---------|------|
| Kontrakt (zakresy, path, kolejność ML) | `schemas/environment-controller.json` |
| Znaczenie pól pod UI | `docs/SCHEMA_V4_FIELD_GUIDE.md` |
| Reguły agenta / dev | `Agents.md` |

Schema **v4 nie jest „zamrożona na zawsze”** — konfigurator będzie ujawniał potrzebne poprawki.
Zmiany breaking → świadoma nowa wersja schema + regeneracja artefaktów board/ML.

## Scope MVP (ta linia pracy)

**In:**

- Frontend edytujący podzbiór / pełnię pól v4 w logicznych grupach UI.
- Walidacja po stronie FE (min/max, available → zerowanie limitów).
- Import / export JSON (plik, wklejka, localStorage).
- Opcjonalnie: wczytanie statycznego schema JSON z `/schemas/...` bez API.

**Out (później lub inne branche):**

- Backend API, auth, baza profili w chmurze.
- Podłączenie płytki (to zostaje w **panelu admin**).
- Symulator PyVista / twin 3D.
- Pipeline train / teacher w tym UI.

## Panel admin vs konfigurator

| | Panel (`tools/panel`) | Konfigurator hardware |
|--|----------------------|------------------------|
| Zadanie | Board live, diagnostyka, load_scenario | Opis setupu sprzętowego |
| Serial | Tak | Nie (MVP) |
| Użytkownik | Lab / serwis | Klient / setup |
| Output | Sterowanie + scenario na board | JSON profilu / scenario |

Współdzielą **język danych v4**, niekoniecznie ten sam ekran ani framework.

## Framework

**Nie wybrany na start.** Najpierw model pól i kart UI.
Dopuszczalne: vanilla (jak panel), Vite, Svelte, React — decyzja po pierwszej mapie ekranów.

## Kolejność pracy

1. Guide pól + reguły Agents (ten branch / faza).
2. Szkielet UI grup Chamber / Sensors / Pots / Outputs.
3. Export JSON zgodny ze shape nominal scenario.
4. Dopiero potem backend / train / board import.

## Źródła z innych branchy (opcjonalnie, później)

- `GrowboxProfile` / `profile_to_payload` — adapter Python pod train.
- Panel form layout — wzorce kart donic.
- Twin 3D — **nie** wymagany do konfiguratora.

Nie blokują startu edytora na czystym `main` + schema v4.
