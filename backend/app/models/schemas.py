from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoadDataRequest(BaseModel):
    path: str
    format: Literal["auto", "csv", "parquet"] = "auto"


class FeatureToggleConfig(BaseModel):
    include_power: bool = True
    include_main_gas: bool = True
    include_main_gas_alt: bool = True
    include_segment_gas: bool = True
    include_context_numeric: bool = True
    include_context_categorical: bool = True
    include_context_keyword_allowlist: bool = True


class SplitConfig(BaseModel):
    method: Literal["time", "random"] = "time"
    ratio: float = Field(default=0.8, ge=0.5, le=0.95)
    random_seed: int = 42


class TrainConfig(BaseModel):
    model_type: Literal[
        "hist_gradient_boosting",
        "random_forest",
        "xgboost",
        "lightgbm",
        "catboost",
    ] = "hist_gradient_boosting"
    split: SplitConfig = SplitConfig()
    features: FeatureToggleConfig = FeatureToggleConfig()


class TrainRequest(BaseModel):
    config: TrainConfig


class PredictRequest(BaseModel):
    control_knobs: dict[str, float]
    context: dict[str, Any]


class DeviceTarget(BaseModel):
    L: float
    a: float
    b: float


class StdConstraints(BaseModel):
    L: float | None = None
    a: float | None = None
    b: float | None = None


class OptimizeTargets(BaseModel):
    RG: DeviceTarget | None = None
    RF: DeviceTarget | None = None
    T: DeviceTarget | None = None


class OptimizeConstraints(BaseModel):
    RG: StdConstraints | None = None
    RF: StdConstraints | None = None
    T: StdConstraints | None = None


class OptimizeBounds(BaseModel):
    pwr_pct: float = Field(default=5.0, ge=0, le=50)
    gas_pct: float = Field(default=5.0, ge=0, le=50)


class OptimizeParams(BaseModel):
    k_neighbors: int = Field(default=5, ge=1, le=100)
    n_iterations: int = Field(default=300, ge=20, le=5000)
    n_solutions: int = Field(default=5, ge=1, le=20)
    device_weights: dict[str, float] = Field(default_factory=lambda: {"RG": 1.0, "RF": 1.0, "T": 1.0})


class OptimizeRequest(BaseModel):
    targets: OptimizeTargets
    constraints: OptimizeConstraints | None = None
    method: Literal["nn", "search"] = "nn"
    bounds: OptimizeBounds = OptimizeBounds()
    params: OptimizeParams = OptimizeParams()
    seed_plate: str | None = None
    seed_control_knobs: dict[str, float] | None = None
    seed_context: dict[str, Any] | None = None
    match_context_mode: bool = False


class Solution(BaseModel):
    rank: int
    loss: float
    control_knobs: dict[str, float]
    predicted: dict[str, float]
    deltas_vs_seed: dict[str, float]


class OptimizeResponse(BaseModel):
    solutions: list[Solution]
    method: str


class DataLoadResponse(BaseModel):
    rows: int
    columns: int
    preview: list[dict[str, Any]]
    grouped_columns: dict[str, list[str]]
    missing_summary: dict[str, int]


class TrainResponse(BaseModel):
    artifact_id: str
    metrics_per_target: dict[str, dict[str, float]]
    aggregate_metrics: dict[str, float]
    split_counts: dict[str, int]
    dropped_rows_missing_targets: int
    selected_feature_counts: dict[str, int]
    selected_features: list[str]
    model_type: str


class PredictResponse(BaseModel):
    predictions: dict[str, float]
