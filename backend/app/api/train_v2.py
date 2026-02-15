from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core import train_model
from backend.app.schemas import TrainPayload

router = APIRouter(prefix='/api', tags=['train'])


@router.post('/train')
def api_train(payload: TrainPayload):
    try:
        return train_model(
            dataset_paths=payload.dataset_paths,
            product_name=payload.product_name,
            model_type=payload.model_type,
            target_columns=payload.target_columns,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
