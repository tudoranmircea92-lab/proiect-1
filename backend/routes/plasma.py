from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

@router.get("/health")
def plasma_health():
    return {
        "ok": True,
        "service": "plasma",
        "routes": [
            "GET /api/plasma/health",
            "POST /api/plasma/stability"
        ]
    }

class PlasmaRequest(BaseModel):
    dataset_id: str | None = None
    from_ts: str
    to_ts: str
    active_threshold: float = 0.0
    aggregation: str = "median"

@router.post("/stability")
def plasma_stability(req: PlasmaRequest):
    return {
        "interval": {
            "from": req.from_ts,
            "to": req.to_ts,
            "rows_used": 0
        },
        "kpis": {
            "overall_score": None
        },
        "per_cathode": [],
        "trends": {
            "time_bins": [],
            "overall_score": []
        }
    }
