# Coating Line Optimizer (React + FastAPI)

Industrial-grade web app for training and optimization of coating line color outputs (L*, a*, b*).

## Structure

- `backend/` FastAPI API with training pipeline, model registry, relevance, optimization engine.
- `frontend/` React + Vite + TypeScript + Tailwind desktop-first UI.

## Local run (Windows-friendly)

Backend:
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app/data/sample_data_loader.py
uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Business rule guarantee
Optimizer modifies **only** controllable knobs:
- `cX.pwr`
- `cX.m1g`, `cX.m2g`, `cX.m3g`
- `cX.s1g` ... `cX.s11g`

All proposals are validated against `backend/app/data/machine_config.json`.

## API docs
- OpenAPI: `http://127.0.0.1:8000/docs`
