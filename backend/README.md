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


## Plasma contract-first smoke checklist

Run backend from the repository backend directory:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Then verify locally:

```bash
curl -i http://127.0.0.1:8000/api/plasma/health
curl -i -X POST http://127.0.0.1:8000/api/plasma/stability \
  -H "Content-Type: application/json" \
  -d '{"from_ts":"2026-02-09T13:47:00","to_ts":"2026-02-16T13:47:00","active_threshold":0.0,"aggregation":"mean","group_by":["device","plate"],"features":["c4.pwr"],"filters":{"product":[],"thickness_mm":[]}}'
```

OpenAPI contract check:

```bash
pytest -q backend/tests/test_plasma_contract.py
```

Expected:
- `/api/plasma/health`, `/api/plasma/columns`, `/api/plasma/stability`, `/api/plasma/stability/export` exist in docs.
- Legacy endpoints (e.g. `/api/plasma_stability`) return `410 Gone` with a deprecation hint.
