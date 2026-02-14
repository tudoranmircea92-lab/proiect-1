# Industrial Web Optimizer v2

Production-oriented internal web optimizer for factory usage (LAN / Chrome / Edge).

## What is included

- Dataset loading from `.parquet` (primary) and `.csv` (fallback), local or UNC paths.
- Dataset summary: rows, columns, date range/count, devices, compartments, plates count, segment count.
- Column normalization for date/device/plate/compartments.
- Config-driven knob groups/rules from `config/knob_rules.json`.
- Async run manager with progress stages, cancellation, and run history.
- Per-run audit artifacts under `artifacts/YYYY-MM-DD/<run_id>/`.
- Export API for XLSX/CSV/JSON.
- Health endpoint and rotating app logs.

## API

- `GET /api/health`
- `GET /api/config/knob-rules`
- `POST /api/dataset/load`
- `GET /api/context?date=...&plate=...&device=...&strategy=latest|mean`
- `POST /api/run/start`
- `GET /api/run/status/{run_id}`
- `POST /api/run/cancel/{run_id}`
- `GET /api/run/results/{run_id}`
- `GET /api/run/history`
- `GET /api/run/export/{run_id}?format=xlsx|csv|json`

## Install

```bash
python -m pip install -r coater_ui_v6_full_architecture/requirements.txt
```

For parquet support install pandas + pyarrow in your environment.

## Run

```bash
uvicorn coater_ui_v6_full_architecture.backend.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Windows scripts

- `coater_ui_v6_full_architecture/scripts/run_web_local.bat`
- `coater_ui_v6_full_architecture/scripts/run_web_local.ps1`

## Config

- `coater_ui_v6_full_architecture/config/knob_rules.json`

Defines group ordering, wildcard group assignment, and default min/max/step/unit per knob.

## Artifacts per run

Saved in:

- `artifacts/<YYYY-MM-DD>/<run_id>/`

Files:

- `run_summary.json`
- `recommendations.json`
- `recommendations.csv`
- `recommendations.xlsx`
- `knob_changes.json`
- `run_log.txt`

Global logs:

- `logs/app.log`
