# Industrial Web Optimizer v2

Production-ready optimizer UI/API for engineering decision support.

## Frontend

- `/optimizer` (also `/`) serves:
  - `backend/static/optimizer.html`
  - `backend/static/optimizer.js`
  - `backend/static/optimizer.css`

## Core optimizer endpoints

- `GET /api/optimizer/targets`
- `GET /api/optimizer/knobs?product_name=&day=&plate=`
- `POST /api/optimizer/run`
- `POST /api/optimizer/verify`

## Additional platform endpoints

- `POST /api/dataset/load`
- `GET /api/context?date=&plate=&device=&strategy=latest|mean`
- `GET /api/health`
- `GET /api/run/history`
- `GET /api/run/status/{run_id}`
- `POST /api/run/cancel/{run_id}`
- `GET /api/run/results/{run_id}`
- `GET /api/run/export/{run_id}?format=xlsx|csv|json`

## Run

```bash
python -m pip install -r coater_ui_v6_full_architecture/requirements.txt
uvicorn coater_ui_v6_full_architecture.backend.app:app --host 0.0.0.0 --port 8000
```

Open:

- `http://localhost:8000/optimizer`

## Config

Knob grouping/defaults file:

- `coater_ui_v6_full_architecture/config/knob_rules.json`
