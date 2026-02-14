from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..config import AppConfig, load_config
from ..services.data_loader import DataRepository
from ..services.ml_feature_builder import default_feature_columns
from ..services.ml_train import create_model, train_model
from ..services.model_registry import ModelRegistry
from ..services.optimizer import OptimizerInput, OptimizerService


router = APIRouter(prefix="/optimizer", tags=["optimizer"])


class OptimizeRequest(BaseModel):
    product: str
    day: Optional[str] = None
    plate_ids: Optional[List[str]] = None
    target: str
    tolerance: float = Field(default=0.1, ge=0)
    mode: str = Field(default="SAFE")
    train_new_model: bool = True
    active_knobs: List[str] = Field(default_factory=list)


class VerifyRequest(BaseModel):
    plate_id: str
    predicted: float
    realized: float


def get_config() -> AppConfig:
    return load_config()


@router.post("/run")
def run_optimizer(payload: OptimizeRequest, cfg: AppConfig = Depends(get_config)):
    repo = DataRepository(dataset_path=Path(cfg.dataset_path))
    df = repo.load()
    subset = repo.filter_context(df, payload.product, payload.day, payload.plate_ids)

    features = default_feature_columns(subset.columns.tolist(), payload.target) if not subset.empty else []

    train_info = train_model(subset, features, payload.target) if payload.train_new_model else None
    model = create_model(subset, payload.target)

    registry = ModelRegistry(cfg.models_dir)
    registry.save_metadata(
        name=f"{payload.product}_{payload.target}",
        payload={
            "target": payload.target,
            "mode": payload.mode,
            "metric": train_info.metric if train_info else None,
            "features": features,
        },
    )

    svc = OptimizerService(top_k=cfg.optimizer.get("top_k_solutions", 3))
    solutions = svc.optimize(
        subset,
        model,
        OptimizerInput(
            target=payload.target,
            tolerance=payload.tolerance,
            mode=payload.mode,
            active_knobs=payload.active_knobs,
        ),
    )

    return {
        "count": len(solutions),
        "solutions": [s.__dict__ for s in solutions],
        "train": None if train_info is None else train_info.__dict__,
    }


@router.post("/verify")
def verify_applied(payload: VerifyRequest):
    error = payload.realized - payload.predicted
    status = "ok" if abs(error) <= 0.1 else "drift"
    return {"plate_id": payload.plate_id, "error": round(error, 4), "status": status}
