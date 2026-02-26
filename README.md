# Live DuckDB ingest (v1) + Node.js UI

Sistem Python pentru extracție live din fișiere process + Optoplex, cu upsert idempotent în DuckDB și matching întârziat (process-first), plus interfață Node.js (tab: **Create DB Live**).

## 1) Cerințe

- Python 3.10+
- Node.js 18+
- npm

---

## 2) Setup Python

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install duckdb pytest
```

---

## 3) Setup UI Node.js

```powershell
cd web
npm install
cd ..
```

---

## 4) Pornire interfață

```powershell
cd web
npm start
```

Deschide în browser:

- `http://localhost:3000`

Interfața are acum un singur tab activ:

- **Create DB Live**

Acest tab pornește/oprește pipeline-ul Python `scripts/run_live_db.py` cu parametrii introduși în formular.

---

## 5) Ce completezi în tab-ul “Create DB Live”

- `Python executable` (ex: `python` sau path complet la `.venv\Scripts\python.exe`)
- `Optoplex directory` (ex: `D:\optoplex`)
- `Process directory` (ex: `D:\process`)
- `DuckDB path` (ex: `D:\data\coater.duckdb`)
- `Poll seconds` (default `10`)
- `Match window minutes` (default `10`)
- `Archive directory` (opțional)
- `Log file` (opțional)
- `One shot` (`true` / `false`)

Apoi:

- **Start** pentru pornire
- **Stop** pentru oprire

Status + ultimele loguri apar în UI.

---

## 6) Rulare directă (fără UI)

```powershell
python scripts/run_live_db.py --optoplex-dir D:\optoplex --process-dir D:\process --db-path D:\data\coater.duckdb
```

One shot:

```powershell
python scripts/run_live_db.py --optoplex-dir D:\optoplex --process-dir D:\process --db-path D:\data\coater.duckdb --one-shot
```

Cu arhivare + log:

```powershell
python scripts/run_live_db.py --optoplex-dir D:\optoplex --process-dir D:\process --db-path D:\data\coater.duckdb --archive-dir D:\archive --log-file D:\logs\live_db.log
```

---

## 7) Comportament live

- Polling loop (`--poll-seconds`, default 10).
- Fișier complet: există și are dimensiune stabilă la 2 verificări consecutive.
- Retry parse/write: 3 încercări.
- Single-instance lock: `<db>.lock`.
- Procesare tranzacțională per run; rollback la eroare.

---

## 8) Structură module

- `live_db/watch.py` – polling + file completion + lock.
- `live_db/parse_process.py` – parser process CSV.
- `live_db/parse_optoplex.py` – parser Optoplex CSV (ignore Spectrum, poziții dinamice, encoding fallback).
- `live_db/pairing.py` – matching logic + status.
- `live_db/build_operational.py` – compartimente, zone, risc, summary optic.
- `live_db/build_model.py` – feature/target tables (fără ML activ).
- `live_db/store.py` – schema + `MERGE` idempotent.
- `scripts/run_live_db.py` – orchestrare end-to-end.
- `web/src/server.js` + `web/public/index.html` – UI Node.js.

---

## 9) Tabele DuckDB

### L0_INGEST
- `file_registry`
- `pairing_log`
- `orphan_optoplex`
- `ingest_runs`

### L1_RAW
- `raw_process_long` (key: `plate,event_time,Location`)
- `raw_optoplex_long` (key: `plate,stamp,device_norm,position`)

### L2_OPERATIONAL
- `plate_core` (key: `plate,event_time`)
- `optics_summary` (key: `plate,event_time`)
- `compartment_state_long` (key: `plate,event_time,Location`)
- `zone_summary` (key: `plate,event_time`)
- `risk_summary` (key: `plate,event_time`)

### L3_MODEL
- `model_features_plate` (key: `plate,event_time`)
- `model_targets_plate` (key: `plate,event_time`)
- `model_training_color` (view)

---

## 10) Edge cases tratate

- `process_only`, `color_only`, `paired`, `late_color_matched`, `expired_unmatched`.
- Orfani Optoplex păstrați în `orphan_optoplex` și rematch la apariția process.
- Process-first: `plate_core` există chiar fără culoare.
- Segmente dinamice (`nomGasSegment` 5/10/11), fără stocare `Seg1..Seg11` în operational.
- Main gases parser 1..5, operational folosește 1..3.
- Ramp gases 1..3 incluse explicit.

---

## 11) Teste

```bash
pytest -q
```
