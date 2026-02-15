from __future__ import annotations

import math

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.multioutput import MultiOutputRegressor

from backend.app.core.constants import LEAKAGE_COLUMNS, MANDATORY_COLUMN, PLATE_COLUMN, is_controllable_column
from backend.app.services.io_utils import write_json
from backend.app.services.registry_service import add_entry, ensure_registry_dirs, stamp


def _ensure_product_column(df: pd.DataFrame) -> pd.DataFrame:
    if MANDATORY_COLUMN not in df.columns:
        out = df.copy()
        out[MANDATORY_COLUMN] = "GENERAL"
        return out
    return df


def _feature_sets(df: pd.DataFrame, targets: list[str], model_type: str) -> tuple[list[str], list[str]]:
    excluded = set(targets) | LEAKAGE_COLUMNS
    included: list[str] = []
    for col in df.columns:
        if col in excluded:
            continue
        if is_controllable_column(col):
            included.append(col)
        elif model_type == "process" and col != MANDATORY_COLUMN:
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


def _encode_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object" or str(out[col].dtype).startswith("category"):
            out[col] = out[col].astype("category").cat.codes
        out[col] = pd.to_numeric(out[col], errors="coerce")
        out[col] = out[col].fillna(out[col].median() if not out[col].dropna().empty else 0)
    return out


def _delta_e(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(((y_true - y_pred) ** 2).sum(axis=1)).mean())


def _importance_payload(features: list[str], importances: np.ndarray) -> dict:
    rows = []
    by_comp: dict[str, float] = {}
    cont_sum = 0.0
    ctx_sum = 0.0
    for feat, imp in zip(features, importances):
        group = "controllable" if is_controllable_column(feat) else "context"
        compartment = feat.split(".", 1)[0] if "." in feat else "global"
        value = float(max(0.0, imp))
        rows.append({"feature": feat, "importance": value, "group": group, "compartment": compartment})
        by_comp[compartment] = by_comp.get(compartment, 0.0) + value
        if group == "controllable":
            cont_sum += value
        else:
            ctx_sum += value
    rows.sort(key=lambda x: x["importance"], reverse=True)
    comp_rows = [{"compartment": k, "importance": float(v)} for k, v in by_comp.items()]
    comp_rows.sort(key=lambda x: x["importance"], reverse=True)
    total = cont_sum + ctx_sum or 1.0
    return {
        "feature_importances": rows,
        "importance_by_compartment": comp_rows,
        "total_controllable_share": cont_sum / total,
        "total_context_share": ctx_sum / total,
    }


def train_model(df: pd.DataFrame, product_name: str, target_columns: list[str], model_type: str, split_mode: str, ratios: tuple[float, float, float], compute_delta_e: bool) -> dict:
    df = _ensure_product_column(df)
    scoped_df = df[df[MANDATORY_COLUMN].astype(str) == product_name].copy() if product_name != "GENERAL" else df.copy()
    if len(scoped_df) == 0 and product_name != "GENERAL":
        scoped_df = df.copy()
        product_name = "GENERAL"
    scoped_df = scoped_df.dropna(subset=target_columns)
    if len(scoped_df) < 20:
        raise ValueError("Not enough rows for training after filters")

    features, excluded = _feature_sets(scoped_df, target_columns, model_type)
    train_df, _, test_df = _split_data(scoped_df, split_mode, ratios)

    X_train = _encode_features(train_df[features])
    X_test = _encode_features(test_df[features])
    y_train = train_df[target_columns]
    y_test = test_df[target_columns]

    base = RandomForestRegressor(n_estimators=220, random_state=42, n_jobs=-1)
    model = MultiOutputRegressor(base)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    metrics = {
        "mae": {target_columns[i]: float(mean_absolute_error(y_test.iloc[:, i], y_pred[:, i])) for i in range(len(target_columns))},
        "rmse": {target_columns[i]: float(math.sqrt(mean_squared_error(y_test.iloc[:, i], y_pred[:, i]))) for i in range(len(target_columns))},
        "MAE_L": float(mean_absolute_error(y_test.iloc[:, 0], y_pred[:, 0])) if len(target_columns) > 0 else 0.0,
        "MAE_a": float(mean_absolute_error(y_test.iloc[:, 1], y_pred[:, 1])) if len(target_columns) > 1 else 0.0,
        "MAE_b": float(mean_absolute_error(y_test.iloc[:, 2], y_pred[:, 2])) if len(target_columns) > 2 else 0.0,
    }
    if compute_delta_e and len(target_columns) >= 3:
        metrics["ΔE"] = _delta_e(y_test.to_numpy(), y_pred)

    importances = np.mean(np.vstack([est.feature_importances_ for est in model.estimators_]), axis=0)
    importance_payload = _importance_payload(features, importances)

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
    joblib.dump(model, artifact_paths["model"])
    write_json(artifact_paths["schema"], {"features": features, "targets": target_columns})
    write_json(artifact_paths["metrics"], metrics)
    write_json(artifact_paths["train_config"], {"product_name": product_name, "model_type": model_type, "split_mode": split_mode, "split_ratios": ratios, "target_columns": target_columns})
    write_json(artifact_paths["feature_groups"], {f: f.split(".")[0] if "." in f else "global" for f in features})
    write_json(artifact_paths["importance"], importance_payload)

    add_entry({"run_id": run_id, "product_name": product_name, "model_type": model_type, "created_at": stamp(), "metrics": metrics, "artifacts": artifact_paths})

    return {
        "run_id": run_id,
        "product_name": product_name,
        "model_type": model_type,
        "metrics": metrics,
        "included_features": features,
        "excluded_features": excluded,
        "artifacts": artifact_paths,
        **importance_payload,
    }
