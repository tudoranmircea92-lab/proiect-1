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
    method: Literal["time", "random", "by_product"] = "time"
    ratio: float = Field(default=0.8, ge=0.5, le=0.95)
    random_seed: int = 42
    stratify_by_product: bool = False


class DataFilter(BaseModel):
    products: list[str] = Field(default_factory=list)
    thicknesses: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None


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
    filter: DataFilter | None = None


class PredictRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: str
    model_id: str | None = None
    plate_id: str | None = None
    device: Literal["RG", "RF", "T"] = "RG"
    outputs: Literal["b_only", "lab"] = "b_only"
    knob_overrides: dict[str, float] = Field(default_factory=dict)
    target: DeviceTarget | None = None
    tolerance: DeviceTarget | None = None
    control_knobs: dict[str, float] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    filter: DataFilter | None = None


class DeviceTarget(BaseModel):
    L: float | None = None
    a: float | None = None
    b: float | None = None


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
    plate_id: str | None = None
    device: Literal["RG", "RF", "T"] = "RG"
    metric_group: Literal["lab", "b_only"] = "b_only"
    targets: DeviceTarget | OptimizeTargets
    tolerances: DeviceTarget | None = None
    tol_deltaE: float | None = None
    baseline_source: Literal["actual", "nearest_neighbor", "median_product"] = "actual"
    knob_groups: dict[str, bool] = Field(default_factory=lambda: {"power": True, "main_gas": True, "segment_gas": True})
    active_threshold: float = 0.0
    filter: DataFilter | None = None
    lambda_knob_change: float = 0.2
    lambda_smoothness: float = 0.1
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


class PlasmaWeights(BaseModel):
    vacuum: float = 0.7
    uniform_cur: float = 0.7
    uniform_pwr: float = 0.7


class PlasmaStabilityRequest(BaseModel):
    dataset_id: str | None = None
    timestamp_col: Literal["auto", "ts", "file_ts"] = "auto"
    from_ts: str = Field(validation_alias=AliasChoices("from_ts", "from", "date_from"), serialization_alias="from")
    to_ts: str = Field(validation_alias=AliasChoices("to_ts", "to", "date_to"), serialization_alias="to")
    active_threshold: float = 0.0
    agg: Literal["mean", "median"] = "mean"
    weights: PlasmaWeights = PlasmaWeights()
    bins: Literal["auto"] | int = "auto"
    show_inactive: bool = False
    filter: DataFilter | None = None


class PlasmaStabilityResponse(BaseModel):
    interval: dict[str, Any]
    kpis: dict[str, float | None]
    per_cathode: list[dict[str, Any]]
    trends: dict[str, list[Any]]
    data_notes: dict[str, Any] | None = None


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
    actual: dict[str, float | None]
    pred_baseline: dict[str, float | None]
    pred_edited: dict[str, float | None]
    loss_baseline: float | None
    loss_edited: float | None
    knob_changes: list[dict[str, float | str]]
    used_feature_schema_hash: str
