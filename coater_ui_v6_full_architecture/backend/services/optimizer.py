from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from .ml_feature_builder import detect_available_knobs


@dataclass
class OptimizerInput:
    target: str
    tolerance: float
    mode: str
    active_knobs: List[str]


@dataclass
class Solution:
    rank: int
    deltas: Dict[str, float]
    predicted_target: float
    risk: str
    cost_per_plate: float


class OptimizerService:
    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def optimize(
        self,
        df: pd.DataFrame,
        model,
        optimizer_input: OptimizerInput,
    ) -> List[Solution]:
        knobs = optimizer_input.active_knobs or detect_available_knobs(df.columns)
        if not knobs:
            return []

        baseline = float(df[optimizer_input.target].mean()) if optimizer_input.target in df.columns and not df.empty else 0.0
        pred = float(model.predict(pd.DataFrame([{}]))[0])

        solutions: List[Solution] = []
        step = 0.1 if optimizer_input.mode.upper() == "SAFE" else 0.3

        for i in range(self.top_k):
            deltas = {k: round((i + 1) * step, 3) for k in knobs[:3]}
            predicted_target = baseline + (pred - baseline) * 0.5
            solutions.append(
                Solution(
                    rank=i + 1,
                    deltas=deltas,
                    predicted_target=round(predicted_target, 3),
                    risk="low" if optimizer_input.mode.upper() == "SAFE" else "medium",
                    cost_per_plate=round(sum(abs(v) for v in deltas.values()) * 0.2, 3),
                )
            )
        return solutions
