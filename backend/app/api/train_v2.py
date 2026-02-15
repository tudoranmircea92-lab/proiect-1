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
            input_scope=payload.input_scope,
            color_scope=payload.color_scope,
            selected_color_target=payload.selected_color_target,
            physical_params=payload.physical_params,
            training_method=payload.training_method,
            subset_ratio=payload.subset_ratio,
            date_from=payload.date_from,
            date_to=payload.date_to,
            optimizable_scope=payload.optimizable_scope,
            manual_overrides=payload.manual_overrides,
            metric_mode=payload.metric_mode,
            metric_subset_product=payload.metric_subset_product,
            model_family=payload.model_family,
            training_speed=payload.training_speed,
            cross_validation=payload.cross_validation,
            cv_folds=payload.cv_folds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
