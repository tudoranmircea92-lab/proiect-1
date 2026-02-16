from __future__ import annotations

import json
import uuid
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.core.constants import TARGET_COLUMNS
from app.models.schemas import TrainConfig
from app.utils.feature_selector import select_features


class TrainingService:
    def __init__(self) -> None:
        self.artifacts_root = Path("backend/app/artifacts_cache/runs")
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.current_pipeline: Pipeline | None = None
        self.feature_schema: dict = {}

    def _model_for_type(self, model_type: str):
        if model_type == "hist_gradient_boosting":
            return MultiOutputRegressor(HistGradientBoostingRegressor(random_state=42))
        if model_type == "random_forest":
            return RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
        if model_type == "xgboost":
            from xgboost import XGBRegressor  # type: ignore

            return MultiOutputRegressor(XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05, random_state=42))
        if model_type == "lightgbm":
            from lightgbm import LGBMRegressor  # type: ignore

            return MultiOutputRegressor(LGBMRegressor(n_estimators=300, learning_rate=0.05, random_state=42))
        if model_type == "catboost":
            from catboost import CatBoostRegressor  # type: ignore

            return MultiOutputRegressor(CatBoostRegressor(verbose=0, random_seed=42))
        raise ValueError(f"Unsupported estimator_type: {model_type}")

    def available_models(self) -> list[str]:
        models = ["hist_gradient_boosting", "random_forest"]
        for pkg, name in [("xgboost", "xgboost"), ("lightgbm", "lightgbm"), ("catboost", "catboost")]:
            try:
                __import__(pkg)
                models.append(name)
            except Exception:
                continue
        return models

    def _build_preprocessor(self, num_cols: list[str], cat_cols: list[str], model_type: str) -> ColumnTransformer:
        use_scaler = model_type in {"hist_gradient_boosting", "xgboost", "lightgbm", "catboost"}
        numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
        if use_scaler:
            numeric_steps.append(("scaler", StandardScaler()))

        numeric_pipeline = Pipeline(steps=numeric_steps)
        categorical_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]
        )

        return ColumnTransformer(
            transformers=[
                ("num", numeric_pipeline, num_cols),
                ("cat", categorical_pipeline, cat_cols),
            ],
            remainder="drop",
        )

    def train(self, df: pd.DataFrame, config: TrainConfig) -> dict:
        missing_targets = [c for c in TARGET_COLUMNS if c not in df.columns]
        if missing_targets:
            raise ValueError(f"Missing required target columns: {missing_targets}")

        selection = select_features(df, config.features)
        if not selection.selected_features:
            raise ValueError("No feature columns selected with current toggles.")

        train_df = df.dropna(subset=TARGET_COLUMNS).copy()
        dropped_rows = len(df) - len(train_df)
        if train_df.empty:
            raise ValueError("Dataset is empty after dropping rows with missing targets.")

        X = train_df[selection.selected_features].copy()
        y = train_df[TARGET_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0)

        if config.split.method == "time":
            ts_col = "file_ts" if "file_ts" in train_df.columns else "ts" if "ts" in train_df.columns else None
            if not ts_col:
                raise ValueError("Time split selected but no file_ts or ts column found.")
            sorted_idx = train_df.assign(_order=pd.to_datetime(train_df[ts_col], errors="coerce")).sort_values("_order").index
            X, y = X.loc[sorted_idx], y.loc[sorted_idx]
            cut = int(len(X) * config.split.ratio)
            X_train, X_val = X.iloc[:cut], X.iloc[cut:]
            y_train, y_val = y.iloc[:cut], y.iloc[cut:]
        else:
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, train_size=config.split.ratio, random_state=config.split.random_seed
            )

        preprocessor = self._build_preprocessor(selection.control_knobs + selection.context_numeric, selection.context_categorical, config.estimator_type)
        model = self._model_for_type(config.estimator_type)
        pipeline = Pipeline([
            ("preprocessor", preprocessor),
            ("model", model),
        ])

        pipeline.fit(X_train, y_train)
        preds = pipeline.predict(X_val)

        metrics_per_target: dict[str, dict[str, float]] = {}
        mae_means, mae_stds = [], []
        for i, target in enumerate(TARGET_COLUMNS):
            mae = float(mean_absolute_error(y_val.iloc[:, i], preds[:, i]))
            rmse = float(np.sqrt(mean_squared_error(y_val.iloc[:, i], preds[:, i])))
            metrics_per_target[target] = {"mae": mae, "rmse": rmse}
            (mae_means if target.endswith("_mean") else mae_stds).append(mae)

        aggregate_metrics = {
            "mean_mae_means": float(np.mean(mae_means)),
            "mean_mae_stds": float(np.mean(mae_stds)),
        }

        artifact_id = uuid.uuid4().hex[:10]
        run_dir = self.artifacts_root / artifact_id
        run_dir.mkdir(parents=True, exist_ok=True)

        schema = {
            "control_knobs": selection.control_knobs,
            "context_numeric": selection.context_numeric,
            "context_categorical": selection.context_categorical,
            "keyword_forced_context": selection.keyword_forced_context,
            "selected_features": selection.selected_features,
        }

        joblib.dump(pipeline, run_dir / "model.pkl")
        (run_dir / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
        (run_dir / "target_columns.json").write_text(json.dumps(TARGET_COLUMNS, indent=2), encoding="utf-8")

        report = {
            "metrics_per_target": metrics_per_target,
            "aggregate_metrics": aggregate_metrics,
            "split_counts": {"train": len(X_train), "val": len(X_val)},
            "dropped_rows_missing_targets": dropped_rows,
            "selected_feature_counts": selection.counts,
            "selected_features": selection.selected_features,
            "estimator_type": config.estimator_type,
            "feature_schema": schema,
        }
        (run_dir / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

        self.current_pipeline = pipeline
        self.feature_schema = schema
        return {"artifact_id": artifact_id, **report}

    def predict(self, control_knobs: dict[str, float], context: dict[str, object]) -> dict[str, float]:
        if self.current_pipeline is None or not self.feature_schema:
            raise ValueError("Model not trained yet.")

        row: dict[str, object] = {}
        for k in self.feature_schema["control_knobs"]:
            row[k] = float(control_knobs.get(k, 0.0))
        for k in self.feature_schema["context_numeric"]:
            val = context.get(k, 0.0)
            row[k] = 0.0 if val is None else float(val)
        for k in self.feature_schema["context_categorical"]:
            row[k] = context.get(k, "")

        X = pd.DataFrame([row])
        preds = self.current_pipeline.predict(X)[0]
        return {target: float(preds[idx]) for idx, target in enumerate(TARGET_COLUMNS)}
