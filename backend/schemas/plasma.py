from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PlasmaHealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["plasma"]
    version: str
    time: datetime


class PlasmaColumnsResponse(BaseModel):
    time_column: str
    available_columns: list[str]
    defaults: dict[str, Any]


class PlasmaStabilityFilters(BaseModel):
    product: list[str] = Field(default_factory=list)
    thickness_mm: list[float] = Field(default_factory=list)


class PlasmaStabilityRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_ts: datetime = Field(validation_alias=AliasChoices("from_ts", "from"))
    to_ts: datetime = Field(validation_alias=AliasChoices("to_ts", "to"))
    active_threshold: float = 0.0
    aggregation: Literal["mean", "median"] = Field(default="mean", validation_alias=AliasChoices("aggregation", "agg"))
    group_by: list[str] = Field(default_factory=lambda: ["device", "plate"])
    features: list[str] = Field(default_factory=list)
    filters: PlasmaStabilityFilters = Field(default_factory=PlasmaStabilityFilters)


class PlasmaSeriesPoint(BaseModel):
    ts: datetime
    value: float
    is_active: bool
    meta: dict[str, Any] = Field(default_factory=dict)


class PlasmaStabilityResponse(BaseModel):
    window: dict[str, datetime]
    params: dict[str, Any]
    score: float
    score_details: dict[str, Any]
    series: list[PlasmaSeriesPoint]
    warnings: list[str]
    row_count: int
