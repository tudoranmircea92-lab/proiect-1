from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


@router.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "plasma",
        "routes": ["GET /api/plasma/health", "POST /api/plasma/stability"],
    }


class PlasmaStabilityRequest(BaseModel):
    dataset_id: Optional[str] = None
    from_ts: str
    to_ts: str
    active_threshold: float = 0.0
    aggregation: str = "median"


@router.post("/stability")
def stability(req: PlasmaStabilityRequest) -> Dict[str, Any]:
    return {
        "interval": {"from": req.from_ts, "to": req.to_ts, "rows_used": 0},
        "kpis": {"overall_score": None},
        "per_cathode": [],
        "trends": {"time_bins": [], "overall_score": []},
    }
