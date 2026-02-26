# Live DuckDB ingest (v1) + Node.js UI

Sistem Python pentru extracție live din fișiere process + Optoplex, cu upsert idempotent în DuckDB și matching întârziat (process-first), plus interfață Node.js (tab: **Create DB Live**).

## 1) Cerințe

- Python 3.10+
- Node.js 18+
- npm

## 2) Setup Python

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install duckdb pytest
```

## 3) Setup UI Node.js

```powershell
cd web
npm install
cd ..
```

## 4) Pornire interfață

```powershell
cd web
npm start
```

Deschide în browser: `http://localhost:3000`.

## 5) Tab „Create DB Live”

UI are browse pentru:
- Optoplex directory
- Process directory
- DuckDB file
- Archive directory
- Log file

Backend browse endpoint:

`GET /api/browse?path=...`

Suportă local paths + UNC paths (în mediu Windows). Erorile de permisiuni sunt întoarse în răspuns JSON, fără crash.

## 6) Rulare ingest

### Din UI

UI pornește backend-ul Python cu:

```bash
python -m scripts.run_live_db ...
```

### Direct CLI

```powershell
python -m scripts.run_live_db --optoplex-dir D:\optoplex --process-dir D:\process --db-path D:\data\coater.duckdb
```

One shot:

```powershell
python -m scripts.run_live_db --optoplex-dir D:\optoplex --process-dir D:\process --db-path D:\data\coater.duckdb --one-shot
```

## 7) Reguli importante implementate

- `--db-path` trebuie să fie fișier `.duckdb` (nu director). Altfel, eroare clară.
- Pipeline-ul rulează **doar din folderul zilei curente**:
  - `base/YYYY/MM/DD`
  - exemplu: `optoplex/2026/02/26`, `process/2026/02/26`
- Nu se scanează istoric și nu se face `os.walk` pe root.
- Dacă folderul de azi nu există: log `No folder for today yet.` și retry la următorul poll.
- La schimbarea datei (midnight rollover): comută automat pe noul `YYYY/MM/DD`.

## 8) Poll behavior + idempotency

Fiecare poll:
- re-scan doar folderul de azi pentru process + optoplex
- detectează fișiere noi
- verifică `ingested_files`:
  - dacă `file_path` există și `mtime` neschimbat => skip
  - altfel => procesează + upsert idempotent

Tabela nouă:

- `ingested_files(file_path TEXT PRIMARY KEY, file_mtime TIMESTAMP, ingested_at TIMESTAMP)`

## 9) Tabele DuckDB

### L0_INGEST
- `file_registry`
- `pairing_log`
- `orphan_optoplex`
- `ingest_runs`
- `ingested_files`

### L1_RAW
- `raw_process_long` (key: `plate,event_time,Location`)
- `raw_optoplex_long` (key: `plate,stamp,device_norm,position`)

### L2_OPERATIONAL
- `plate_core` (key: `plate,event_time`)
- `optics_summary` (key: `plate,event_time`)
- `compartment_state_long` (key: `plate,event_time,Location`)
- `zone_summary` (key: `plate,event_time`)
- `risk_summary` (key: `plate,event_time`)

### L3_MODEL hooks (neobligatorii pentru ingest)
- `model_features_plate` (key: `plate,event_time`)
- `model_targets_plate` (key: `plate,event_time`)
- `model_training_color` (view, creat doar dacă există ambele tabele)

## 10) Teste

```bash
pytest -q
```
