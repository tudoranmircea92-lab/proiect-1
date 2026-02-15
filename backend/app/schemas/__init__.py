from __future__ import annotations

from pydantic import BaseModel, Field


class TrainPayload(BaseModel):
    dataset_paths: list[str] = Field(default_factory=list)
    product_name: str | None = None
    model_type: str = 'process'
    target_columns: list[str] = Field(default_factory=lambda: ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean'])


class OptimizePayload(BaseModel):
    model_id: str
    current_state: dict[str, float]
    target_color: dict[str, float]


__all__ = ['TrainPayload', 'OptimizePayload']
