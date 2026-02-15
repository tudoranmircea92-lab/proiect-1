from __future__ import annotations

from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor


def build_regressor(model_family: str = 'random_forest', training_speed: str = 'quick'):
    model_family = (model_family or 'random_forest').lower()
    training_speed = (training_speed or 'quick').lower()

    if model_family == 'neural_network':
        hidden = (64, 32) if training_speed == 'quick' else (128, 64, 32)
        iters = 250 if training_speed == 'quick' else 600
        return MultiOutputRegressor(
            MLPRegressor(
                hidden_layer_sizes=hidden,
                max_iter=iters,
                random_state=42,
                early_stopping=True,
            )
        )

    n_estimators = 120 if training_speed == 'quick' else 400
    max_depth = 12 if training_speed == 'quick' else None
    return MultiOutputRegressor(
        RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1,
        )
    )
