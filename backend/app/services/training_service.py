from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.core.constants import TARGET_COLUMNS
from app.models.schemas import DataFilter, TrainConfig
from app.utils.feature_selector import select_features


class TrainingService:
    def __init__(self) -> None:
        self.artifacts_root = Path("backend/app/artifacts_cache/runs")
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.current_pipeline: Pipeline | None = None
        self.feature_schema: dict = {}
        self.active_models: dict[str, str] = {}

    def _mode_params(self, training_mode: str) -> dict:
        if training_mode == "fast":
            return {"n_estimators": 120, "max_iter": 120}
        if training_mode == "maximum_accuracy":
            return {"n_estimators": 600, "max_iter": 450}
        return {"n_estimators": 300, "max_iter": 250}

    def _model_for_type(self, model_type: str, training_mode: str):
        params = self._mode_params(training_mode)
        if model_type == "hist_gradient_boosting":
            return MultiOutputRegressor(HistGradientBoostingRegressor(random_state=42, max_iter=params["max_iter"]))
        if model_type == "random_forest":
            return RandomForestRegressor(n_estimators=params["n_estimators"], random_state=42, n_jobs=-1)
        if model_type == "xgboost":
            from xgboost import XGBRegressor  # type: ignore

            return MultiOutputRegressor(XGBRegressor(n_estimators=params["n_estimators"], max_depth=6, learning_rate=0.05, random_state=42))
        if model_type == "lightgbm":
            from lightgbm import LGBMRegressor  # type: ignore

            return MultiOutputRegressor(LGBMRegressor(n_estimators=params["n_estimators"], learning_rate=0.05, random_state=42))
        if model_type == "catboost":
            from catboost import CatBoostRegressor  # type: ignore

            return MultiOutputRegressor(CatBoostRegressor(verbose=0, random_seed=42))
        raise ValueError(f"Unsupported estimator_type: {model_type}")


    def set_active_model(self, product: str, model_id: str) -> dict[str, str]:
        self.active_models[str(product)] = str(model_id)
        return {'product': str(product), 'model_id': str(model_id)}

    def get_active_model(self, product: str) -> dict[str, str | None]:
        return {'product': str(product), 'model_id': self.active_models.get(str(product))}

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

    def train(self, df: pd.DataFrame, config: TrainConfig, dataset_id: str = "", data_filter: DataFilter | None = None) -> dict:
        missing_targets = [c for c in TARGET_COLUMNS if c not in df.columns]
        if missing_targets:
            raise ValueError(f"Missing required target columns: {missing_targets}")

        if data_filter:
            if data_filter.products:
                pcol = next((c for c in df.columns if str(c).lower() in {"product", "product_name", "productcode", "recipe", "part"}), None)
                if pcol:
                    df = df[df[pcol].astype(str).isin({str(x) for x in data_filter.products})]
            if data_filter.thicknesses:
                tcol = next((c for c in df.columns if str(c).lower() in {"thickness", "glassthickness", "nominal_thickness"}), None)
                if tcol:
                    df = df[df[tcol].astype(str).isin({str(x) for x in data_filter.thicknesses})]

        selection = select_features(df, config.features)
        if not selection.selected_features:
            raise ValueError("No feature columns selected with current toggles.")

        train_df = df.dropna(subset=TARGET_COLUMNS).copy()
        dropped_rows = len(df) - len(train_df)
        if train_df.empty:
            raise ValueError("Dataset is empty after dropping rows with missing targets.")

        X = train_df[selection.selected_features].copy()
        y = train_df[TARGET_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0)

        split_windows = None
        if config.split.method == "time":
            ts_col = "file_ts" if "file_ts" in train_df.columns else "ts" if "ts" in train_df.columns else None
            if not ts_col:
                raise ValueError("Time split selected but no file_ts or ts column found.")
            sorted_idx = train_df.assign(_order=pd.to_datetime(train_df[ts_col], errors="coerce")).sort_values("_order").index
            X, y = X.loc[sorted_idx], y.loc[sorted_idx]
            cut = int(len(X) * config.split.ratio)
            X_train, X_val = X.iloc[:cut], X.iloc[cut:]
            y_train, y_val = y.iloc[:cut], y.iloc[cut:]
            split_windows = {
                "train_end": str(train_df.loc[sorted_idx].iloc[max(cut - 1, 0)][ts_col]) if len(sorted_idx) else None,
                "val_start": str(train_df.loc[sorted_idx].iloc[min(cut, len(sorted_idx)-1)][ts_col]) if len(sorted_idx) else None,
                "time_col": ts_col,
            }
        elif config.split.method == "by_product":
            product_col = next((c for c in train_df.columns if str(c).lower() in {"product", "product_name", "productcode", "recipe", "part"}), None)
            if not product_col:
                raise ValueError("by_product split selected but no product column found.")
            groups = train_df[product_col].astype(str).fillna("unknown")
            splitter = GroupShuffleSplit(n_splits=1, train_size=config.split.ratio, random_state=config.split.random_seed)
            train_idx, val_idx = next(splitter.split(X, y, groups=groups))
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        else:
            stratify = None
            if config.split.stratify_by_product:
                product_col = next((c for c in train_df.columns if str(c).lower() in {"product", "product_name", "productcode", "recipe", "part"}), None)
                if product_col:
                    stratify = train_df[product_col].astype(str)
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, train_size=config.split.ratio, random_state=config.split.random_seed, stratify=stratify
            )

        preprocessor = self._build_preprocessor(selection.control_knobs + selection.context_numeric, selection.context_categorical, config.estimator_type)
        model = self._model_for_type(config.estimator_type, config.training_mode)
        pipeline = Pipeline([
            ("preprocessor", preprocessor),
            ("model", model),
        ])

        pipeline.fit(X_train, y_train)
        preds_val = pipeline.predict(X_val)
        preds_train = pipeline.predict(X_train)

        metrics_per_target: dict[str, dict[str, float | None]] = {}
        mae_means, mae_stds = [], []
        mae_l, mae_a, mae_b, all_val = [], [], [], []

        for i, target in enumerate(TARGET_COLUMNS):
            val_mae = float(mean_absolute_error(y_val.iloc[:, i], preds_val[:, i]))
            train_mae = float(mean_absolute_error(y_train.iloc[:, i], preds_train[:, i]))
            val_rmse = float(np.sqrt(mean_squared_error(y_val.iloc[:, i], preds_val[:, i])))
            metrics_per_target[target] = {"train_mae": train_mae, "validation_mae": val_mae, "validation_rmse": val_rmse}
            all_val.append(val_mae)
            if target.startswith("L_"):
                mae_l.append(val_mae)
            if target.startswith("a_"):
                mae_a.append(val_mae)
            if target.startswith("b_"):
                mae_b.append(val_mae)
            (mae_means if target.endswith("_mean") else mae_stds).append(val_mae)

        aggregate_metrics = {
            "mean_mae_means": float(np.mean(mae_means)) if mae_means else None,
            "mean_mae_stds": float(np.mean(mae_stds)) if mae_stds else None,
        }
        metrics_summary = {
            "mae_L": float(np.mean(mae_l)) if mae_l else None,
            "mae_a": float(np.mean(mae_a)) if mae_a else None,
            "mae_b": float(np.mean(mae_b)) if mae_b else None,
            "overall_mean_error": float(np.mean(all_val)) if all_val else None,
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
        (run_dir / "config.json").write_text(json.dumps(config.model_dump(mode="json"), indent=2), encoding="utf-8")
        (run_dir / "metrics.json").write_text(json.dumps({"metrics_per_target": metrics_per_target}, indent=2), encoding="utf-8")
        (run_dir / "feature_list.json").write_text(json.dumps(selection.selected_features, indent=2), encoding="utf-8")
        schema_hash = uuid.uuid5(uuid.NAMESPACE_DNS, json.dumps(schema, sort_keys=True)).hex[:16]
        (run_dir / "schema_hash.txt").write_text(schema_hash, encoding="utf-8")

        trained_at = datetime.now(timezone.utc).isoformat()
        report = {
            "model_id": artifact_id,
            "artifact_id": artifact_id,
            "train_rows": int(len(X_train)),
            "val_rows": int(len(X_val)),
            "feature_count": int(len(selection.selected_features)),
            "knob_count": int(len(selection.control_knobs)),
            "feature_names": selection.selected_features,
            "metrics_per_target": metrics_per_target,
            "metrics_summary": metrics_summary,
            "aggregate_metrics": aggregate_metrics,
            "split_counts": {"train": len(X_train), "val": len(X_val)},
            "dropped_rows_missing_targets": dropped_rows,
            "selected_feature_counts": selection.counts,
            "selected_features": selection.selected_features,
            "estimator_type": config.estimator_type,
            "feature_schema": schema,
            "trained_at": trained_at,
            "dataset_id": dataset_id,
            "random_seed": config.split.random_seed,
            "split_windows": split_windows,
            "schema_hash": schema_hash,
            "artifact_dir": str(run_dir),
        }
        (run_dir / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

        self.current_pipeline = pipeline
        self.feature_schema = schema
        return report

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
