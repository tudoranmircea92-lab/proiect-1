from __future__ import annotations

import os
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from app.models.schemas import DataFilter
from app.utils.feature_selector import detect_groups


PRODUCT_CANDIDATES = ["product", "product_name", "productCode", "recipe", "part"]
THICKNESS_CANDIDATES = ["thickness", "glassThickness", "nominal_thickness"]
TS_CANDIDATES = ["file_ts", "ts", "timestamp", "time"]
PLATE_CANDIDATES = ["plate", "plate_id", "plateId"]


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

    def _first_existing(self, df: pd.DataFrame, candidates: list[str]) -> str | None:
        cols_lower = {c.lower(): c for c in df.columns}
        for c in candidates:
            if c in df.columns:
                return c
            if c.lower() in cols_lower:
                return cols_lower[c.lower()]
        return None

    def product_col(self, df: pd.DataFrame) -> str | None:
        return self._first_existing(df, PRODUCT_CANDIDATES)

    def thickness_col(self, df: pd.DataFrame) -> str | None:
        return self._first_existing(df, THICKNESS_CANDIDATES)

    def ts_col(self, df: pd.DataFrame) -> str | None:
        return self._first_existing(df, TS_CANDIDATES)

    def plate_col(self, df: pd.DataFrame) -> str | None:
        return self._first_existing(df, PLATE_CANDIDATES)

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

    def apply_filter(self, df: pd.DataFrame, filt: DataFilter | None) -> pd.DataFrame:
        if not filt:
            return df

        out = df
        product_col = self.product_col(out)
        if filt.products and product_col:
            wanted = {str(x) for x in filt.products}
            out = out[out[product_col].astype(str).isin(wanted)]

        thickness_col = self.thickness_col(out)
        if filt.thicknesses and thickness_col:
            wanted = {str(x) for x in filt.thicknesses}
            out = out[out[thickness_col].astype(str).isin(wanted)]

        ts_col = self.ts_col(out)
        if ts_col and (filt.date_from or filt.date_to):
            ts = pd.to_datetime(out[ts_col], errors="coerce")
            if filt.date_from:
                out = out[ts >= pd.to_datetime(filt.date_from, errors="coerce")]
            if filt.date_to:
                out = out[ts <= pd.to_datetime(filt.date_to, errors="coerce")]

        return out

    def profile(self, dataset_id: str) -> dict:
        df = self.get(dataset_id)
        grouped = detect_groups(df, include_debug=self.debug_enabled)
        knob_debug = grouped.pop("knob_debug", {})
        missing_summary = {col: int(df[col].isna().sum()) for col in df.columns}
        preview_df = df.head(20).copy()
        preview_df.replace([np.inf, -np.inf], np.nan, inplace=True)
        safe_preview = preview_df.where(pd.notna(preview_df), None)

        prod_col = self.product_col(df)
        thick_col = self.thickness_col(df)
        products = sorted(df[prod_col].dropna().astype(str).unique().tolist()) if prod_col else []
        thicknesses = sorted(df[thick_col].dropna().astype(str).unique().tolist()) if thick_col else []

        out = {
            "dataset_id": dataset_id,
            "saved_path": self.dataset_paths.get(dataset_id),
            "rows": len(df),
            "columns": len(df.columns),
            "preview": safe_preview.to_dict(orient="records"),
            "grouped_columns": grouped,
            "missing_summary": missing_summary,
            "products": products,
            "thicknesses": thicknesses,
            "product_column": prod_col,
            "thickness_column": thick_col,
        }
        if self.debug_enabled:
            out["debug"] = knob_debug
        return out

    def plate_rows(self, dataset_id: str, filt: DataFilter | None = None, limit: int = 200) -> list[dict]:
        df = self.apply_filter(self.get(dataset_id), filt)
        plate_col = self.plate_col(df)
        if not plate_col:
            return []

        prod_col = self.product_col(df)
        thick_col = self.thickness_col(df)
        ts_col = self.ts_col(df)

        cols = [plate_col]
        if ts_col:
            cols.append(ts_col)
        if prod_col:
            cols.append(prod_col)
        if thick_col:
            cols.append(thick_col)

        rows = []
        for _, row in df[cols].drop_duplicates(subset=[plate_col]).head(limit).iterrows():
            rows.append({
                "plate": str(row.get(plate_col, "")),
                "ts": row.get(ts_col) if ts_col else None,
                "product": str(row.get(prod_col, "")) if prod_col else "",
                "thickness": str(row.get(thick_col, "")) if thick_col else "",
            })
        return rows

    def color_profile(self, dataset_id: str, plate_id: str, device: str) -> dict:
        df = self.get(dataset_id)
        plate_col = self.plate_col(df)
        if not plate_col:
            raise ValueError("No plate column in dataset")

        sub = df[df[plate_col].astype(str) == str(plate_id)]
        if sub.empty:
            raise ValueError(f"Plate '{plate_id}' not found")
        row = sub.iloc[0]

        def mean_std_points(ch: str):
            mean_col = f"{ch}_{device}_mean"
            std_col = f"{ch}_{device}_std"
            points = []
            for i in range(1, 10):
                c = f"{ch}_{device}_p{i}"
                if c in sub.columns:
                    val = pd.to_numeric(sub.iloc[0].get(c), errors="coerce")
                    if pd.notna(val):
                        points.append(float(val))
            return {
                "mean": float(pd.to_numeric(row.get(mean_col), errors="coerce")) if mean_col in sub.columns and pd.notna(pd.to_numeric(row.get(mean_col), errors="coerce")) else None,
                "std": float(pd.to_numeric(row.get(std_col), errors="coerce")) if std_col in sub.columns and pd.notna(pd.to_numeric(row.get(std_col), errors="coerce")) else None,
                "points": points,
            }

        L = mean_std_points("L")
        a = mean_std_points("a")
        b = mean_std_points("b")
        return {
            "L_mean": L["mean"], "L_std": L["std"], "L_points": L["points"],
            "a_mean": a["mean"], "a_std": a["std"], "a_points": a["points"],
            "b_mean": b["mean"], "b_std": b["std"], "b_points": b["points"],
        }


    def seed_rows(self, dataset_id: str, filt: DataFilter | None = None, limit: int = 300) -> list[dict]:
        return self.plate_rows(dataset_id, filt=filt, limit=limit)

    def plate_row(self, dataset_id: str, plate_id: str, filt: DataFilter | None = None) -> pd.Series:
        df = self.apply_filter(self.get(dataset_id), filt)
        plate_col = self.plate_col(df)
        if not plate_col:
            raise ValueError("No plate column in dataset")
        matched = df[df[plate_col].astype(str) == str(plate_id)]
        if matched.empty:
            raise ValueError(f"Plate '{plate_id}' not found")
        return matched.iloc[0]

    def plate_baseline(self, dataset_id: str, plate_id: str, control_knobs: list[str], filt: DataFilter | None = None, active_threshold: float = 0.0) -> dict:
        row = self.plate_row(dataset_id, plate_id, filt=filt)
        df = self.apply_filter(self.get(dataset_id), filt)
        ts_col = self.ts_col(df)
        prod_col = self.product_col(df)
        thick_col = self.thickness_col(df)

        available_knobs = [k for k in control_knobs if k in df.columns and df[k].notna().any()]
        baseline_knobs: dict[str, float] = {}
        active_cathodes: list[str] = []
        seen = set()
        for k in available_knobs:
            v = pd.to_numeric(row.get(k), errors="coerce")
            baseline_knobs[k] = float(v) if pd.notna(v) else 0.0
            lk = k.lower().replace('_', '.')
            if lk.endswith('.pwr'):
                cath = lk.split('.pwr')[0]
                if baseline_knobs[k] > active_threshold and cath not in seen:
                    seen.add(cath)
                    active_cathodes.append(cath)

        actual = {dev: self.color_profile(dataset_id, plate_id, dev) for dev in ["RG", "RF", "T"]}
        return {
            "plate_id": str(plate_id),
            "ts": row.get(ts_col) if ts_col else None,
            "product": str(row.get(prod_col, "")) if prod_col else "",
            "thickness": str(row.get(thick_col, "")) if thick_col else "",
            "active_cathodes": active_cathodes,
            "baseline_knobs": baseline_knobs,
            "actual_color": actual,
        }
