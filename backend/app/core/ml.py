from __future__ import annotations

import uuid

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import KFold

from backend.app.core.constants import LEAKAGE_COLUMNS, MANDATORY_COLUMN, TIMESTAMP_CANDIDATES, is_controllable_column
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


def _date_column(df: pd.DataFrame) -> str | None:
    for col in TIMESTAMP_CANDIDATES:
        if col in df.columns:
            return col
    return None


def _apply_training_method(df: pd.DataFrame, training_method: str, subset_ratio: float, date_from: str | None, date_to: str | None, product_name: str | None) -> pd.DataFrame:
    scoped = df.copy()
    if training_method == 'per_product' and product_name:
        filtered = scoped[scoped[MANDATORY_COLUMN].astype(str) == str(product_name)].copy()
        if len(filtered) > 0:
            scoped = filtered
    elif training_method == 'subset_recent':
        ratio = min(1.0, max(0.05, float(subset_ratio or 0.3)))
        n = max(10, int(len(scoped) * ratio))
        date_col = _date_column(scoped)
        if date_col:
            scoped[date_col] = pd.to_datetime(scoped[date_col], errors='coerce')
            scoped = scoped.sort_values(by=date_col).tail(n)
        else:
            scoped = scoped.tail(n)
    elif training_method == 'filtered':
        date_col = _date_column(scoped)
        if date_col and (date_from or date_to):
            scoped[date_col] = pd.to_datetime(scoped[date_col], errors='coerce')
            if date_from:
                scoped = scoped[scoped[date_col] >= pd.to_datetime(date_from, errors='coerce')]
            if date_to:
                scoped = scoped[scoped[date_col] <= pd.to_datetime(date_to, errors='coerce')]

    return scoped.copy()


def _prepare_features(
    df: pd.DataFrame,
    target_columns: list[str],
    model_type: str,
    physical_params: list[str] | None = None,
    input_scope: str = 'all_devices',
    optimizable_scope: str = 'all',
) -> pd.DataFrame:
    excluded = set(target_columns) | set(LEAKAGE_COLUMNS)
    features = []
    requested = set(physical_params or [])

    for c in df.columns:
        if c in excluded or c == MANDATORY_COLUMN:
            continue
        if optimizable_scope == 'controllable_only' and not is_controllable_column(c):
            continue
        if model_type == 'control' and not is_controllable_column(c):
            continue
        if input_scope == 'selected_physical' and requested and c not in requested:
            continue
        features.append(c)

    if not features:
        raise ValueError('No feature columns available after applying filters')

    X = df[features].copy()
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = X[col].astype('category').cat.codes
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
    return X


def _metric_payload(y_true: np.ndarray, y_pred: np.ndarray, target_columns: list[str], metric_mode: str) -> dict:
    payload = {}
    if y_true.size == 0:
        return {'MAE_L': 0.0, 'MAE_a': 0.0, 'MAE_b': 0.0, 'ΔE': 0.0}

    maes = [float(mean_absolute_error(y_true[:, i], y_pred[:, i])) for i in range(y_true.shape[1])]
    rmses = [float(np.sqrt(mean_squared_error(y_true[:, i], y_pred[:, i]))) for i in range(y_true.shape[1])]

    payload['MAE_L'] = maes[0] if len(maes) > 0 else 0.0
    payload['MAE_a'] = maes[1] if len(maes) > 1 else 0.0
    payload['MAE_b'] = maes[2] if len(maes) > 2 else 0.0
    payload['ΔE'] = float(np.sqrt(((y_true - y_pred) ** 2).sum(axis=1)).mean()) if y_true.shape[1] >= 3 else 0.0

    if metric_mode in {'rmse', 'combined'}:
        payload['RMSE_L'] = rmses[0] if len(rmses) > 0 else 0.0
        payload['RMSE_a'] = rmses[1] if len(rmses) > 1 else 0.0
        payload['RMSE_b'] = rmses[2] if len(rmses) > 2 else 0.0
    if metric_mode == 'combined':
        payload['combined_score'] = float(np.mean(maes + rmses)) if (maes + rmses) else 0.0
    return payload


def train_model(
    dataset_paths: list[str],
    product_name: str | None,
    model_type: str,
    target_columns: list[str],
    input_scope: str = 'all_devices',
    color_scope: str = 'all',
    selected_color_target: str | None = None,
    physical_params: list[str] | None = None,
    training_method: str = 'all_data',
    subset_ratio: float = 0.3,
    date_from: str | None = None,
    date_to: str | None = None,
    optimizable_scope: str = 'all',
    manual_overrides: dict[str, float] | None = None,
    metric_mode: str = 'mae',
    metric_subset_product: str | None = None,
    model_family: str = 'random_forest',
    training_speed: str = 'quick',
    cross_validation: bool = False,
    cv_folds: int = 3,
) -> dict:
    df = load_datasets(resolve_paths(dataset_paths))
    if MANDATORY_COLUMN not in df.columns:
        df[MANDATORY_COLUMN] = 'GENERAL'

    if color_scope == 'subset' and selected_color_target:
        if selected_color_target not in target_columns:
            raise ValueError(f'selected_color_target {selected_color_target} not in target_columns')
        target_columns = [selected_color_target]

    scoped = _apply_training_method(df, training_method, subset_ratio, date_from, date_to, product_name)
    scoped = scoped.dropna(subset=target_columns)

    if manual_overrides:
        for key, value in manual_overrides.items():
            if key in scoped.columns:
                scoped[key] = value

    if len(scoped) < 10:
        raise ValueError('Not enough rows for training')

    X = _prepare_features(scoped, target_columns, model_type, physical_params, input_scope, optimizable_scope)
    y = scoped[target_columns].copy()

    split = max(1, int(len(scoped) * 0.8))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = build_regressor(model_family=model_family, training_speed=training_speed)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    test_mask = np.ones(len(y_test), dtype=bool)
    if metric_subset_product and MANDATORY_COLUMN in scoped.columns:
        test_products = scoped.iloc[split:][MANDATORY_COLUMN].astype(str).to_numpy()
        test_mask = test_products == str(metric_subset_product)
        if not test_mask.any():
            test_mask = np.ones(len(y_test), dtype=bool)

    y_true_np = y_test.to_numpy()[test_mask]
    y_pred_np = np.asarray(pred)[test_mask]
    training_metrics = _metric_payload(y_true_np, y_pred_np, target_columns, metric_mode)

    cv_score = None
    if cross_validation and len(X_train) >= max(10, cv_folds):
        k = max(2, min(int(cv_folds), 8, len(X_train)))
        kf = KFold(n_splits=k, shuffle=True, random_state=42)
        fold_scores = []
        for tr_idx, val_idx in kf.split(X_train):
            m = clone(model)
            m.fit(X_train.iloc[tr_idx], y_train.iloc[tr_idx])
            cv_pred = m.predict(X_train.iloc[val_idx])
            fold_mae = mean_absolute_error(y_train.iloc[val_idx].to_numpy(), np.asarray(cv_pred))
            fold_scores.append(float(fold_mae))
        cv_score = float(np.mean(fold_scores)) if fold_scores else None

    importance = calculate_feature_importance(model, X, X.columns.tolist())
    model_id = str(uuid.uuid4())
    MODEL_STORE[model_id] = {'model': model, 'importance': importance}

    return {
        'status': 'success',
        'training_metrics': training_metrics,
        'training_options': {
            'input_scope': input_scope,
            'color_scope': color_scope,
            'selected_color_target': selected_color_target,
            'training_method': training_method,
            'optimizable_scope': optimizable_scope,
            'metric_mode': metric_mode,
            'model_family': model_family,
            'training_speed': training_speed,
            'cross_validation': cross_validation,
            'cv_score_mae': cv_score,
        },
        **importance,
        'model_id': model_id,
        'preview_rows': scoped.head(5).fillna('').to_dict(orient='records'),
    }


def get_importance(model_id: str) -> dict:
    if model_id not in MODEL_STORE:
        raise ValueError('model_id not found')
    return MODEL_STORE[model_id]['importance']
