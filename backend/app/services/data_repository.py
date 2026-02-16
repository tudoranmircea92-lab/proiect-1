from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd

from app.utils.feature_selector import detect_groups


class DataRepository:
    def __init__(self) -> None:
        self.datasets: dict[str, pd.DataFrame] = {}
        self.dataset_paths: dict[str, str] = {}
        self.current_dataset_id: str | None = None
        self.cache_dir = Path("backend/app/artifacts_cache")
        self.upload_dir = Path("backend/workspace/uploads")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.debug_enabled = os.getenv("APP_DEBUG", "0") == "1"

    def _new_id(self) -> str:
        return uuid.uuid4().hex[:10]

    def load(self, path: str, fmt: str = "auto") -> tuple[str, pd.DataFrame]:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"Dataset not found at path: {path}")

        if fmt == "auto":
            fmt = "parquet" if source.suffix.lower() in {".parquet", ".pq"} else "csv"

        if fmt == "parquet":
            df = pd.read_parquet(source)
        elif fmt == "csv":
            df = pd.read_csv(source)
        else:
            raise ValueError(f"Unsupported format '{fmt}'")

        dataset_id = self._new_id()
        self.datasets[dataset_id] = df
        self.dataset_paths[dataset_id] = str(source)
        self.current_dataset_id = dataset_id
        self._cache(df)
        return dataset_id, df

    def register_uploaded(self, saved_path: str, fmt: str = "auto") -> tuple[str, pd.DataFrame]:
        return self.load(saved_path, fmt)

    def _cache(self, df: pd.DataFrame) -> None:
        cached_path = self.cache_dir / "cached_dataset.parquet"
        df.to_parquet(cached_path, index=False)

    def get(self, dataset_id: str | None = None) -> pd.DataFrame:
        did = dataset_id or self.current_dataset_id
        if not did or did not in self.datasets:
            raise ValueError("No dataset loaded. Use /api/data/upload or /api/data/load first.")
        return self.datasets[did]

    def profile(self, dataset_id: str) -> dict:
        df = self.get(dataset_id)
        grouped = detect_groups(df, include_debug=self.debug_enabled)
        knob_debug = grouped.pop("knob_debug", {})
        missing_summary = {col: int(df[col].isna().sum()) for col in df.columns}
        safe_preview = df.head(20).copy().where(pd.notna(df.head(20)), None)

        out = {
            "dataset_id": dataset_id,
            "saved_path": self.dataset_paths.get(dataset_id),
            "rows": len(df),
            "columns": len(df.columns),
            "preview": safe_preview.to_dict(orient="records"),
            "grouped_columns": grouped,
            "missing_summary": missing_summary,
        }
        if self.debug_enabled:
            out["debug"] = knob_debug
        return out
