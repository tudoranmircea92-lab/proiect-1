from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_parquet(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    try:
        return pd.read_parquet(p, engine="fastparquet")
    except Exception:
        return pd.read_parquet(p, engine="pyarrow")


def write_json(path: str | Path, payload: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def read_json(path: str | Path, default: dict | None = None) -> dict:
    p = Path(path)
    if not p.exists():
        return default or {}
    return json.loads(p.read_text(encoding="utf-8"))
