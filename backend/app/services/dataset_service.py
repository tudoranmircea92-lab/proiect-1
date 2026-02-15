from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.constants import MANDATORY_COLUMN, PLATE_COLUMN, TIMESTAMP_CANDIDATES, detect_compartments
from app.services.io_utils import load_parquet


@dataclass
class LoadedDataset:
    data: pd.DataFrame
    source: str


def _infer_timestamp_column(columns: list[str]) -> str | None:
    for col in TIMESTAMP_CANDIDATES:
        if col in columns:
            return col
    return None


def load_datasets(paths: list[str]) -> pd.DataFrame:
    if not paths:
        raise ValueError("At least one dataset path is required")
    frames = [load_parquet(path) for path in paths]
    merged = pd.concat(frames, ignore_index=True)
    return merged


def join_process_color(process_path: str, color_path: str, tolerance_minutes: int = 0) -> pd.DataFrame:
    proc = load_parquet(process_path)
    col = load_parquet(color_path)
    proc_ts = _infer_timestamp_column(proc.columns.tolist())
    col_ts = _infer_timestamp_column(col.columns.tolist())
    if proc_ts is None or col_ts is None:
        raise ValueError("Could not infer timestamp columns for join")
    for df, col_name in ((proc, proc_ts), (col, col_ts)):
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    if tolerance_minutes <= 0:
        joined = proc.merge(col, left_on=[PLATE_COLUMN, proc_ts], right_on=[PLATE_COLUMN, col_ts], suffixes=("", "_color"))
    else:
        joined = pd.merge_asof(
            proc.sort_values(proc_ts),
            col.sort_values(col_ts),
            left_on=proc_ts,
            right_on=col_ts,
            by=PLATE_COLUMN,
            tolerance=pd.Timedelta(minutes=tolerance_minutes),
            direction="nearest",
            suffixes=("", "_color"),
        )
    return joined.dropna(how="all")


def summarize_dataset(df: pd.DataFrame, target_columns: list[str] | None = None) -> dict:
    if MANDATORY_COLUMN not in df.columns:
        raise ValueError("Dataset must contain product_name")
    ts_col = _infer_timestamp_column(df.columns.tolist())
    date_min = date_max = None
    if ts_col:
        series = pd.to_datetime(df[ts_col], errors="coerce")
        date_min = series.min()
        date_max = series.max()
    missing = {}
    for target in target_columns or []:
        if target in df.columns:
            missing[target] = float(df[target].isna().mean())
    return {
        "rows": int(len(df)),
        "plates": int(df[PLATE_COLUMN].nunique()) if PLATE_COLUMN in df.columns else 0,
        "date_min": date_min,
        "date_max": date_max,
        "missing_rates": missing,
        "products": sorted(df[MANDATORY_COLUMN].dropna().astype(str).unique().tolist()),
        "compartments": detect_compartments(df.columns.tolist()),
        "columns": sorted(df.columns.tolist()),
    }


def resolve_paths(input_paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in input_paths:
        path = Path(p)
        if path.is_dir():
            out.extend([str(x) for x in path.glob("*.parquet")])
        elif path.is_file() and path.suffix == ".parquet":
            out.append(str(path))
    return sorted(set(out))
