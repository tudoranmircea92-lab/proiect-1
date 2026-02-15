from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.core.constants import LEAKAGE_COLUMNS, MANDATORY_COLUMN, PLATE_COLUMN, is_controllable_column, is_process_context_column
from app.services.registry_service import add_entry, ensure_registry_dirs, stamp
from app.services.io_utils import write_json


def _feature_sets(df: pd.DataFrame, targets: list[str], model_type: str) -> tuple[list[str], list[str]]:
    excluded = set(targets) | LEAKAGE_COLUMNS
    included = []
    for col in df.columns:
        if col in excluded:
            continue
        if is_controllable_column(col):
            included.append(col)
        elif col == MANDATORY_COLUMN:
            included.append(col)
        elif model_type == "process" and is_process_context_column(col):
            included.append(col)
    excluded_cols = [c for c in df.columns if c not in included and c not in targets]
    return sorted(set(included)), sorted(set(excluded_cols))


def _split_data(df: pd.DataFrame, split_mode: str, ratios: tuple[float, float, float]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_ratio, val_ratio, _ = ratios
    if split_mode == "group-by-plate" and PLATE_COLUMN in df.columns:
        groups = df[PLATE_COLUMN].dropna().astype(str).unique().tolist()
        cut1 = int(len(groups) * train_ratio)
        cut2 = int(len(groups) * (train_ratio + val_ratio))
        train_groups = set(groups[:cut1])
        val_groups = set(groups[cut1:cut2])
        train = df[df[PLATE_COLUMN].astype(str).isin(train_groups)]
        val = df[df[PLATE_COLUMN].astype(str).isin(val_groups)]
        test = df[~df[PLATE_COLUMN].astype(str).isin(train_groups | val_groups)]
        return train, val, test
    ts_col = "timestamp" if "timestamp" in df.columns else None
    if ts_col:
        df = df.sort_values(ts_col)
    n = len(df)
    cut1 = int(n * train_ratio)
    cut2 = int(n * (train_ratio + val_ratio))
    return df.iloc[:cut1], df.iloc[cut1:cut2], df.iloc[cut2:]


def _delta_e(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(((y_true - y_pred) ** 2).sum(axis=1)).mean())


def train_model(df: pd.DataFrame, product_name: str, target_columns: list[str], model_type: str, split_mode: str, ratios: tuple[float, float, float], compute_delta_e: bool) -> dict:
    scoped_df = df[df[MANDATORY_COLUMN].astype(str) == product_name].copy() if product_name != "GENERAL" else df.copy()
    scoped_df = scoped_df.dropna(subset=target_columns)
    if len(scoped_df) < 20:
        raise ValueError("Not enough rows for training after filters")
    features, excluded = _feature_sets(scoped_df, target_columns, model_type)
    X = scoped_df[features]
    y = scoped_df[target_columns]
    train_df, _, test_df = _split_data(scoped_df, split_mode, ratios)
    X_train = train_df[features]
    y_train = train_df[target_columns]
    X_test = test_df[features]
    y_test = test_df[target_columns]

    num_cols = [c for c in features if c != MANDATORY_COLUMN]
    cat_cols = [c for c in features if c == MANDATORY_COLUMN]
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("ohe", OneHotEncoder(handle_unknown="ignore"))]), cat_cols),
        ]
    )
    model = MultiOutputRegressor(RandomForestRegressor(n_estimators=180, random_state=42, n_jobs=-1))
    pipe = Pipeline([("prep", preprocessor), ("model", model)])
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)

    metrics = {
        "mae": {target_columns[i]: float(mean_absolute_error(y_test.iloc[:, i], y_pred[:, i])) for i in range(len(target_columns))},
        "rmse": {target_columns[i]: float(np.sqrt(mean_squared_error(y_test.iloc[:, i], y_pred[:, i]))) for i in range(len(target_columns))},
        "mae_avg": float(mean_absolute_error(y_test, y_pred)),
        "rmse_avg": float(np.sqrt(mean_squared_error(y_test, y_pred))),
    }
    if compute_delta_e:
        metrics["delta_e"] = _delta_e(y_test.to_numpy(), y_pred)

    perm = permutation_importance(pipe, X_test, y_test.iloc[:, 0], n_repeats=5, random_state=42, n_jobs=-1)
    by_feature = [{"feature": feat, "importance": float(perm.importances_mean[idx])} for idx, feat in enumerate(features)]
    by_feature.sort(key=lambda x: x["importance"], reverse=True)

    run_id = f"{stamp()}_{product_name}_{model_type}".replace(" ", "_")
    run_dir = ensure_registry_dirs(run_id)

    artifact_paths = {
        "model": str(run_dir / "model.joblib"),
        "schema": str(run_dir / "schema.json"),
        "metrics": str(run_dir / "metrics.json"),
        "train_config": str(run_dir / "train_config.json"),
        "feature_groups": str(run_dir / "feature_groups.json"),
        "importance": str(run_dir / "importance.json"),
    }
    joblib.dump(pipe, artifact_paths["model"])
    write_json(artifact_paths["schema"], {"features": features, "targets": target_columns})
    write_json(artifact_paths["metrics"], metrics)
    write_json(
        artifact_paths["train_config"],
        {
            "product_name": product_name,
            "model_type": model_type,
            "split_mode": split_mode,
            "split_ratios": ratios,
            "target_columns": target_columns,
        },
    )
    write_json(artifact_paths["feature_groups"], {f: f.split(".")[0] if "." in f else "global" for f in features})
    write_json(artifact_paths["importance"], {"by_feature": by_feature})

    entry = {
        "run_id": run_id,
        "product_name": product_name,
        "model_type": model_type,
        "created_at": stamp(),
        "metrics": metrics,
        "artifacts": artifact_paths,
    }
    add_entry(entry)
    return {
        "run_id": run_id,
        "product_name": product_name,
        "model_type": model_type,
        "metrics": metrics,
        "included_features": features,
        "excluded_features": excluded,
        "artifacts": artifact_paths,
    }
