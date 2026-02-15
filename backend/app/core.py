from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from backend.app.core.constants import LEAKAGE_COLUMNS, MANDATORY_COLUMN, is_controllable_column
from backend.app.models import build_regressor
from backend.app.services.dataset_service import load_datasets, resolve_paths
from backend.app.services.io_utils import SUPPORTED_EXTENSIONS, load_table


@dataclass
class TrainedModel:
    model_id: str
    model: object
    features: list[str]
    targets: list[str]
    importance_payload: dict


MODEL_STORE: dict[str, TrainedModel] = {}


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


def train_model(dataset_paths: list[str], product_name: str | None, model_type: str, target_columns: list[str]) -> dict:
    df = load_datasets(resolve_paths(dataset_paths))
    if MANDATORY_COLUMN not in df.columns:
        df[MANDATORY_COLUMN] = 'GENERAL'
    if product_name:
        scoped = df[df[MANDATORY_COLUMN].astype(str) == str(product_name)].copy()
        if len(scoped) == 0:
            scoped = df.copy()
    else:
        scoped = df.copy()

    scoped = scoped.dropna(subset=target_columns)
    if len(scoped) < 10:
        raise ValueError('Not enough rows for training')

    excluded = set(target_columns) | LEAKAGE_COLUMNS
    features = []
    for c in scoped.columns:
        if c in excluded:
            continue
        if model_type == 'control' and not is_controllable_column(c):
            continue
        features.append(c)

    X = scoped[features].copy()
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = X[col].astype('category').cat.codes
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)

    y = scoped[target_columns].copy()
    split = int(len(scoped) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = build_regressor()
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    mae = {target_columns[i]: float(mean_absolute_error(y_test.iloc[:, i], pred[:, i])) for i in range(len(target_columns))}
    delta_e = float(np.sqrt(((y_test.to_numpy() - pred) ** 2).sum(axis=1)).mean()) if len(target_columns) >= 3 else 0.0

    importances = np.mean(np.vstack([est.feature_importances_ for est in model.estimators_]), axis=0)
    rows = []
    by_comp: dict[str, float] = {}
    csum = xsum = 0.0
    for feat, imp in zip(features, importances):
        group = 'controllable' if is_controllable_column(feat) else 'context'
        comp = feat.split('.', 1)[0] if '.' in feat else 'global'
        val = float(max(0.0, imp))
        rows.append({'feature': feat, 'importance': val, 'group': group, 'compartment': comp})
        by_comp[comp] = by_comp.get(comp, 0.0) + val
        if group == 'controllable':
            csum += val
        else:
            xsum += val
    rows.sort(key=lambda x: x['importance'], reverse=True)
    comp_rows = sorted([{'compartment': k, 'importance': float(v)} for k, v in by_comp.items()], key=lambda x: x['importance'], reverse=True)
    total = csum + xsum or 1.0

    model_id = str(uuid.uuid4())
    payload = {
        'feature_importances': rows,
        'importance_by_compartment': comp_rows,
        'total_controllable_share': csum / total,
        'total_context_share': xsum / total,
    }
    MODEL_STORE[model_id] = TrainedModel(model_id=model_id, model=model, features=features, targets=target_columns, importance_payload=payload)

    return {
        'status': 'success',
        'training_metrics': {
            'MAE_L': mae.get(target_columns[0], 0.0) if len(target_columns) > 0 else 0.0,
            'MAE_a': mae.get(target_columns[1], 0.0) if len(target_columns) > 1 else 0.0,
            'MAE_b': mae.get(target_columns[2], 0.0) if len(target_columns) > 2 else 0.0,
            'ΔE': delta_e,
        },
        **payload,
        'model_id': model_id,
        'preview_rows': scoped.head(5).fillna('').to_dict(orient='records'),
    }


def get_importance(model_id: str) -> dict:
    if model_id not in MODEL_STORE:
        raise ValueError('model_id not found')
    return MODEL_STORE[model_id].importance_payload
