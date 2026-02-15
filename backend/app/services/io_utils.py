from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS = {".parquet", ".csv", ".xlsx"}


def load_table(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    suffix = p.suffix.lower()
    if suffix == ".parquet":
        try:
            return pd.read_parquet(p, engine="fastparquet")
        except Exception:
            return pd.read_parquet(p, engine="pyarrow")
    if suffix == ".csv":
        return pd.read_csv(p)
    if suffix == ".xlsx":
        return pd.read_excel(p)
    raise ValueError(f"Unsupported file extension: {suffix}")


def write_json(path: str | Path, payload: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def read_json(path: str | Path, default: dict | None = None) -> dict:
    p = Path(path)
    if not p.exists():
        return default or {}
    return json.loads(p.read_text(encoding="utf-8"))
