# Backend

FastAPI app serving data loading, training, prediction, optimization, and plasma stability.

Run:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Quick plasma route check (should return **400** for missing required fields, not 404):

```bash
curl -X POST http://127.0.0.1:8000/api/plasma/stability -H "Content-Type: application/json" -d "{}"
```
