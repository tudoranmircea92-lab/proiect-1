from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core import get_importance

router = APIRouter(prefix='/api', tags=['importance'])


@router.get('/train/{model_id}/importance')
def api_importance(model_id: str):
    try:
        return get_importance(model_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
