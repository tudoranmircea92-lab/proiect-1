# Industrial Web Optimizer

Web app for industrial optimizer workflows (LAN/factory PC), built with FastAPI + static SPA.

## Features

- Load dataset from local path or UNC share (`\\server\share\file.csv`).
- Select context: date, plate, device, compartments.
- Configure targets (`L*`, `a*`, `b*`) + tolerance (`ΔE`).
- Knobs panel grouped by compartment and category (power, gases, segment gases, vacuum/process, water).
- Async optimization runs with progress polling + cancel endpoint.
- Top 3 recommendations with knob deltas and predicted `Δa*`, `Δb*`, `ΔE`.
- Audit artifacts per run in `artifacts/<YYYY-MM-DD>/<run_id>/`.
- Export run results as XLSX/CSV/JSON.

## API

- `POST /api/dataset/load`
- `GET /api/context`
- `POST /api/run/start`
- `GET /api/run/status/{run_id}`
- `POST /api/run/cancel/{run_id}`
- `GET /api/run/results/{run_id}`
- `GET /api/run/export/{run_id}?format=xlsx|json|csv`

## Prerequisites

```bash
python -m pip install -r coater_ui_v6_full_architecture/requirements.txt
```

## Run locally

```bash
uvicorn coater_ui_v6_full_architecture.backend.app:app --host 0.0.0.0 --port 8000
```

Open browser:
- `http://localhost:8000`

## Windows helper scripts

- `coater_ui_v6_full_architecture/scripts/run_web_local.bat`
- `coater_ui_v6_full_architecture/scripts/run_web_local.ps1`

These scripts start the server on `0.0.0.0:8000` and open the browser.

## UNC path usage

In UI field **Dataset path**, use:

```text
\\server\share\dataset.csv
```

Then click **Load dataset**.

## Audit artifacts per run

Each run writes:

- `run_summary.json`
- `recommendations.csv`
- `recommendations.xlsx`
- `recommendations.json`
- `knob_changes.json`
- `run_log.txt`

under `artifacts/<YYYY-MM-DD>/<run_id>/`.

App-wide logs are in:

- `logs/app.log`
