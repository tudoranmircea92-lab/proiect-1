# Glass Coater ML Web App

Production-grade full-stack app for training and using multi-output color models on glass coater datasets.

## Project structure

- `backend/`: FastAPI + Pydantic v2 + scikit-learn training, inference, optimization APIs.
- `frontend/`: React + TypeScript + Vite + Tailwind + Recharts UI.

## Backend quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Frontend quick start

```bash
cd frontend
npm install
npm run dev
```

## Quick Start (Windows)

Use the root script:

```bat
run_all.bat
```

This script:
1. Creates `backend\.venv` if missing.
2. Installs backend requirements.
3. Installs frontend dependencies.
4. Starts backend and frontend in separate terminals.
5. Prints URLs for both services.

## Design enforced

- Targets are fixed to 18 outputs for RG/RF/T and L/a/b mean/std (ABS excluded).
- Features are split into:
  - **Control knobs** (editable and optimizable): power/main gas/segment gas regex groups.
  - **Context numeric + categorical** (included in training/prediction, read-only for optimizer).
- Optimizer uses a freeze mask: only control knobs are decision variables.

## Plasma Stability tab

- New analysis tab computes plasma stability KPIs per cathode with date/time filtering.
- Supports both true timeseries mode and plate-level wide fallback proxies.
- KPI cards, cathode bar chart, trend line chart (if timeseries), heatmap-style table, and CSV/JSON export.

## API endpoints

- `POST /api/data/load` `{path, format}`
- `GET /api/models`
- `POST /api/train` `{config}`
- `POST /api/predict` `{control_knobs, context}`
- `POST /api/optimize` `{targets, constraints, method, bounds, params, seed_control_knobs, seed_context}`
- `POST /api/plasma_stability` `{path_or_dataset_id, mode, date_from, date_to, ...}`
- `GET /api/plasma_stability/export?format=csv|json`
- `GET /api/artifacts/{id}/download`

## Artifacts

Each train run saves:
- `model.pkl`
- `feature_schema.json`
- `target_columns.json`
- `training_report.json`

## Sample config template

- `backend/app/configs/feature_config.json`
