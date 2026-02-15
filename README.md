# Coating Line Optimizer (React + FastAPI)

Industrial-grade web app for training and optimization of coating process color outputs (L*, a*, b*).

## Structure
- `backend/` FastAPI API with training pipeline, registry, optimization engine.
- `frontend/` React + Vite + TypeScript + Tailwind desktop-first UI.
- `start_all.sh` / `start_all.bat` one-command launchers.

## One-command launch
Linux / macOS:
```bash
./start_all.sh
```

Windows:
```bat
start_all.bat
```

## Manual local run (Windows-friendly)
Backend:
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app/data/sample_data_loader.py
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## Core API endpoints
- `POST /train/scan_source` scan parquet input and detect schema metadata.
- `POST /train/run` train control/process multi-output model.
- `POST /train/save` export training report HTML.
- `GET /train/runs` list registered models and active state.
- `POST /optimize/run` run constrained optimization.
- `GET /optimize/results` list optimization history.

## Business rule guarantee
Optimizer modifies **only**:
- `cX.pwr`
- `cX.m1g`, `cX.m2g`, `cX.m3g`
- `cX.s1g` ... `cX.s11g`

All proposals are bounded by `backend/app/data/machine_config.json`.

## API docs
- OpenAPI: `http://127.0.0.1:8000/docs`
