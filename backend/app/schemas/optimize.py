from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OptimizeRequest(BaseModel):
    product_name: str
    current_state: dict[str, float | int | str]
    target_color: dict[str, float]
    mode: Literal["match_color", "balanced", "minimize_gas", "minimize_energy"] = "balanced"
    top_k_compartments: int = 3
    coverage_threshold: float = 0.8
    include_compartments: list[str] = Field(default_factory=list)
    exclude_compartments: list[str] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    model_run_id: str
    product_name: str
    selected_compartments: list[dict]
    recommendation: dict[str, float]
    deltas: dict[str, float]
    predicted_color: dict[str, float]
    before_color: dict[str, float]
    score: float
    changed_keys: list[str]
    created_at: str


class MachineConfigPatch(BaseModel):
    config: dict = Field(default_factory=dict)
