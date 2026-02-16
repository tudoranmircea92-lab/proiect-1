from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


@router.get('/health')
def health():
    return {'ok': True, 'routes': ['GET /api/plasma/health', 'POST /api/plasma/stability']}


class PlasmaReq(BaseModel):
    dataset_id: str
    from_ts: str
    to_ts: str
    active_threshold: float = 0.0
    agg: str = 'mean'


@router.post('/stability')
def stability(req: PlasmaReq):
    if not req.dataset_id or not req.from_ts or not req.to_ts:
        raise HTTPException(status_code=400, detail='Missing dataset_id/from/to')

    # placeholder minimal response to prove routing works
    return {
        'interval': {'from': req.from_ts, 'to': req.to_ts, 'rows_used': 0},
        'kpis': {'overall_score': None},
        'per_cathode': [],
        'trends': {'time_bins': [], 'overall_score': []},
    }
