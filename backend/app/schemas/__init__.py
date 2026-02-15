from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TrainPayload(BaseModel):
    dataset_paths: list[str] = Field(default_factory=list)
    product_name: str | None = None
    model_type: str = 'process'
    target_columns: list[str] = Field(default_factory=lambda: ['L_star_RG_mean', 'a_star_RG_mean', 'b_star_RG_mean'])

    input_scope: Literal['all_devices', 'selected_physical'] = 'all_devices'
    color_scope: Literal['all', 'subset'] = 'all'
    selected_color_target: str | None = None
    physical_params: list[str] = Field(default_factory=list)

    training_method: Literal['all_data', 'subset_recent', 'per_product', 'filtered'] = 'all_data'
    subset_ratio: float = 0.3
    date_from: str | None = None
    date_to: str | None = None

    optimizable_scope: Literal['controllable_only', 'all'] = 'all'
    manual_overrides: dict[str, float] = Field(default_factory=dict)

    metric_mode: Literal['mae', 'rmse', 'combined'] = 'mae'
    metric_subset_product: str | None = None

    model_family: Literal['random_forest', 'neural_network'] = 'random_forest'
    training_speed: Literal['quick', 'detailed'] = 'quick'
    cross_validation: bool = False
    cv_folds: int = 3


class OptimizePayload(BaseModel):
    model_id: str
    current_state: dict[str, float]
    target_color: dict[str, float]


__all__ = ['TrainPayload', 'OptimizePayload']
