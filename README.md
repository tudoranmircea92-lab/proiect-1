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

## Design enforced

- Targets are fixed to 18 outputs for RG/RF/T and L/a/b mean/std (ABS excluded).
- Features are split into:
  - **Control knobs** (editable and optimizable): power/main gas/segment gas regex groups.
  - **Context numeric + categorical** (included in training/prediction, read-only for optimizer).
- Optimizer uses a freeze mask: only control knobs are decision variables.

## API endpoints

- `POST /api/data/load` `{path, format}`
- `GET /api/models`
- `POST /api/train` `{config}`
- `POST /api/predict` `{control_knobs, context}`
- `POST /api/optimize` `{targets, constraints, method, bounds, params, seed_control_knobs, seed_context}`
- `GET /api/artifacts/{id}/download`

## Artifacts

Each train run saves:
- `model.pkl`
- `feature_schema.json`
- `target_columns.json`
- `training_report.json`

## Sample config template

- `backend/app/configs/feature_config.json`
