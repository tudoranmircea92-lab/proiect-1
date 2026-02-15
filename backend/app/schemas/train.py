from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DatasetScanRequest(BaseModel):
    paths: list[str] = Field(default_factory=list)


class DatasetSummary(BaseModel):
    rows: int
    plates: int
    date_min: datetime | None
    date_max: datetime | None
    missing_rates: dict[str, float]
    products: list[str]
    compartments: list[str]
    columns: list[str]
    detected_plate_col: str | None
    detected_timestamp_col: str | None
    detected_targets: list[str]


class TrainRequest(BaseModel):
    dataset_paths: list[str] = Field(default_factory=list)
    process_path: str | None = None
    color_path: str | None = None
    join_tolerance_minutes: int = 0
    split_mode: Literal["time-based", "group-by-plate"] = "time-based"
    split_ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)
    product_name: str
    include_general_model: bool = False
    model_type: Literal["control", "process"] = "process"
    target_columns: list[str]
    compute_delta_e: bool = True


class TrainRunResponse(BaseModel):
    run_id: str
    product_name: str
    model_type: str
    metrics: dict
    included_features: list[str]
    excluded_features: list[str]
    artifacts: dict[str, str]


class TrainSaveRequest(BaseModel):
    run_id: str


class RegistryEntry(BaseModel):
    run_id: str
    product_name: str
    model_type: str
    created_at: str
    is_active: bool
    metrics: dict


class ActivateModelRequest(BaseModel):
    run_id: str


class FeatureImportanceResponse(BaseModel):
    by_feature: list[dict]
    by_compartment: list[dict]
    share: dict[str, float]
