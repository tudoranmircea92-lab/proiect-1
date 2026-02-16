# Backend (FastAPI)

## Setup
```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Run
```bash
uvicorn backend.app.main:app --reload
```

## APIs
- `POST /api/scan` upload parquet/csv/xlsx and get preview + warning.
- `POST /api/train` train multi-output model and return metrics + importances.
- `GET /api/train/{model_id}/importance` get feature importance payload.
- `POST /api/optimize/run` optimization endpoint.
