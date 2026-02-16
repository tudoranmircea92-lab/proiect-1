from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.utils.feature_selector import detect_groups


class DataRepository:
    def __init__(self) -> None:
        self.df: pd.DataFrame | None = None
        self.path: str | None = None
        self.cache_dir = Path("backend/app/artifacts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load(self, path: str, fmt: str = "auto") -> pd.DataFrame:
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

        self.df = df
        self.path = str(source)
        self._cache(df)
        return df

    def _cache(self, df: pd.DataFrame) -> None:
        cached_path = self.cache_dir / "cached_dataset.parquet"
        df.to_parquet(cached_path, index=False)

    def get(self) -> pd.DataFrame:
        if self.df is None:
            raise ValueError("No dataset loaded. Use /api/data/load first.")
        return self.df

    def profile(self, preview_rows: int = 20) -> dict:
        df = self.get()
        grouped = detect_groups(df)
        knob_debug = grouped.pop("knob_debug", {})
        missing_summary = {col: int(df[col].isna().sum()) for col in df.columns}
        safe_preview = df.head(preview_rows).copy()
        safe_preview = safe_preview.where(pd.notna(safe_preview), None)
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "preview": safe_preview.to_dict(orient="records"),
            "grouped_columns": grouped,
            "missing_summary": missing_summary,
            "debug": knob_debug,
        }
