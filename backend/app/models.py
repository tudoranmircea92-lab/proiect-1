from __future__ import annotations

from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor


def build_regressor() -> MultiOutputRegressor:
    return MultiOutputRegressor(RandomForestRegressor(n_estimators=250, random_state=42, n_jobs=-1))
