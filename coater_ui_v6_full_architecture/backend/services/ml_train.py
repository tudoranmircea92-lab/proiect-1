from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TrainResult:
    model_name: str
    metric: float
    features: List[str]


class MeanPredictor:
    def __init__(self, mean_value: float):
        self.mean_value = float(mean_value)

    def predict(self, n_rows: int = 1) -> List[float]:
        return [self.mean_value for _ in range(n_rows)]


def train_model(rows: List[dict], features: List[str], target: str) -> TrainResult:
    vals = []
    for row in rows:
        try:
            vals.append(float(row.get(target, "")))
        except Exception:
            continue
    if not vals:
        return TrainResult(model_name="mean_predictor", metric=0.0, features=features)
    mean_v = sum(vals) / len(vals)
    spread = sum(abs(x - mean_v) for x in vals) / len(vals)
    return TrainResult(model_name="mean_predictor", metric=round(spread, 6), features=features)


def create_model(rows: List[dict], target: str) -> MeanPredictor:
    vals = []
    for row in rows:
        try:
            vals.append(float(row.get(target, "")))
        except Exception:
            continue
    return MeanPredictor(sum(vals) / len(vals) if vals else 0.0)
