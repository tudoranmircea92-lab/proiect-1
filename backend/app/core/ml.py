from __future__ import annotations

import uuid

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from backend.app.core.constants import LEAKAGE_COLUMNS, MANDATORY_COLUMN, is_controllable_column
from backend.app.core.feature_importance import calculate_feature_importance
from backend.app.models import build_regressor
from backend.app.services.dataset_service import load_datasets, resolve_paths
from backend.app.services.io_utils import load_table

MODEL_STORE: dict[str, dict] = {}


def scan_files(paths: list[str]) -> dict:
    final_paths = resolve_paths(paths)
    if not final_paths:
        raise ValueError('No supported files found')
    frames = [load_table(p) for p in final_paths]
    df = pd.concat(frames, ignore_index=True)
    warning = '' if MANDATORY_COLUMN in df.columns else "Dataset missing 'product_name' column"
    return {
        'status': 'success',
        'row_count': int(len(df)),
        'columns': df.columns.tolist(),
        'preview': df.head(5).fillna('').to_dict(orient='records'),
        'warning': warning,
        'resolved_paths': final_paths,
    }


def _prepare_features(df: pd.DataFrame, target_columns: list[str], model_type: str) -> pd.DataFrame:
    excluded = set(target_columns) | set(LEAKAGE_COLUMNS)
    features = []
    for c in df.columns:
        if c in excluded:
            continue
        if model_type == 'control' and not is_controllable_column(c):
            continue
        if c == MANDATORY_COLUMN:
            continue
        features.append(c)
    X = df[features].copy()
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = X[col].astype('category').cat.codes
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
    return X


def train_model(dataset_paths: list[str], product_name: str | None, model_type: str, target_columns: list[str]) -> dict:
    df = load_datasets(resolve_paths(dataset_paths))
    if MANDATORY_COLUMN not in df.columns:
        df[MANDATORY_COLUMN] = 'GENERAL'

    scoped = df.copy()
    if product_name:
        filtered = df[df[MANDATORY_COLUMN].astype(str) == str(product_name)].copy()
        if len(filtered) > 0:
            scoped = filtered

    scoped = scoped.dropna(subset=target_columns)
    if len(scoped) < 10:
        raise ValueError('Not enough rows for training')

    X = _prepare_features(scoped, target_columns, model_type)
    y = scoped[target_columns].copy()

    split = int(len(scoped) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = build_regressor()
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    training_metrics = {
        'MAE_L': float(mean_absolute_error(y_test.iloc[:, 0], pred[:, 0])) if len(target_columns) > 0 else 0.0,
        'MAE_a': float(mean_absolute_error(y_test.iloc[:, 1], pred[:, 1])) if len(target_columns) > 1 else 0.0,
        'MAE_b': float(mean_absolute_error(y_test.iloc[:, 2], pred[:, 2])) if len(target_columns) > 2 else 0.0,
        'ΔE': float(np.sqrt(((y_test.to_numpy() - pred) ** 2).sum(axis=1)).mean()) if len(target_columns) >= 3 else 0.0,
    }

    importance = calculate_feature_importance(model, X, X.columns.tolist())
    model_id = str(uuid.uuid4())
    MODEL_STORE[model_id] = {'model': model, 'importance': importance}

    return {
        'status': 'success',
        'training_metrics': training_metrics,
        **importance,
        'model_id': model_id,
        'preview_rows': scoped.head(5).fillna('').to_dict(orient='records'),
    }


def get_importance(model_id: str) -> dict:
    if model_id not in MODEL_STORE:
        raise ValueError('model_id not found')
    return MODEL_STORE[model_id]['importance']
