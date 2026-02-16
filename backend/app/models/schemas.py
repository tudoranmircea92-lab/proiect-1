from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(populate_by_name=True)
    estimator_type: Literal["hist_gradient_boosting", "random_forest", "xgboost", "lightgbm", "catboost"] = Field(
        default="hist_gradient_boosting",
        validation_alias=AliasChoices("estimator_type", "model_type"),
        serialization_alias="estimator_type",
    )
    training_mode: Literal["fast", "balanced", "maximum_accuracy"] = "balanced"
    split: SplitConfig = SplitConfig()
    features: FeatureToggleConfig = FeatureToggleConfig()


class TrainRequest(BaseModel):
    dataset_id: str
    config: TrainConfig


class PredictRequest(BaseModel):
    dataset_id: str
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
    dataset_id: str
    targets: OptimizeTargets
    constraints: OptimizeConstraints | None = None
    method: Literal["nn", "search"] = "nn"
    bounds: OptimizeBounds = OptimizeBounds()
    params: OptimizeParams = OptimizeParams()
    seed_plate: str | None = None
    seed_control_knobs: dict[str, float] | None = None
    seed_context: dict[str, Any] | None = None


class Solution(BaseModel):
    rank: int
    loss: float
    control_knobs: dict[str, float]
    predicted: dict[str, float]
    deltas_vs_seed: dict[str, float]


class OptimizeResponse(BaseModel):
    solutions: list[Solution]
    method: str


class PlasmaStabilityRequest(BaseModel):
    dataset_id: str | None = None
    path_or_dataset_id: str | None = None
    mode: Literal["auto", "timeseries", "wide_auto"] = "auto"
    date_from: str
    date_to: str
    time_from: str | None = None
    time_to: str | None = None
    active_threshold: float = 0.0
    metrics: list[str] = Field(default_factory=lambda: ["cv_power", "cv_current", "vacuum_cv", "uniformity_cv_power", "uniformity_cv_current"])
    rolling_window_sec: int = 30
    agg: Literal["mean", "median"] = "mean"
    weights: dict[str, float] = Field(default_factory=lambda: {
        "cv_power": 1.0,
        "cv_current": 1.0,
        "ripple_power": 0.5,
        "ripple_current": 0.5,
        "vacuum_cv": 0.5,
        "uniformity_cv_power": 0.7,
        "uniformity_cv_current": 0.7,
    })
    show_inactive: bool = False


class PlasmaStabilityResponse(BaseModel):
    summary: dict[str, float]
    per_cathode: list[dict[str, Any]]
    timeseries: dict[str, list[dict[str, Any]]]
    mode_used: str


class DataLoadResponse(BaseModel):
    dataset_id: str
    saved_path: str | None = None
    rows: int
    columns: int
    preview: list[dict[str, Any]]
    grouped_columns: dict[str, list[str]]
    missing_summary: dict[str, int]
    debug: dict[str, Any] | None = None


class DataUploadResponse(BaseModel):
    dataset_id: str
    saved_path: str
    format: str
    profile: DataLoadResponse


class TrainResponse(BaseModel):
    model_id: str
    artifact_id: str
    train_rows: int
    val_rows: int
    feature_count: int
    knob_count: int
    feature_names: list[str]
    metrics_per_target: dict[str, dict[str, float | None]]
    metrics_summary: dict[str, float | None]
    aggregate_metrics: dict[str, float | None]
    split_counts: dict[str, int]
    dropped_rows_missing_targets: int
    selected_feature_counts: dict[str, int]
    selected_features: list[str]
    estimator_type: str
    trained_at: str
    dataset_id: str
    random_seed: int


class PredictResponse(BaseModel):
    predictions: dict[str, float]
