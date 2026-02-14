from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass
class TrainResult:
    model_name: str
    metric: float
    features: List[str]


class MeanPredictor:
    def __init__(self, mean_value: float):
        self.mean_value = float(mean_value)

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        return np.full(shape=(len(rows),), fill_value=self.mean_value)


def train_model(df: pd.DataFrame, features: List[str], target: str) -> TrainResult:
    if df.empty or target not in df.columns:
        return TrainResult(model_name="mean_predictor", metric=0.0, features=features)

    y = df[target].dropna()
    metric = float(y.std()) if len(y) > 1 else 0.0
    return TrainResult(model_name="mean_predictor", metric=metric, features=features)


def create_model(df: pd.DataFrame, target: str) -> MeanPredictor:
    if df.empty or target not in df.columns:
        return MeanPredictor(0.0)
    return MeanPredictor(float(df[target].mean()))
