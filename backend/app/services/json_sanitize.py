from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def _sanitize_scalar(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        fx = float(x)
        return fx if math.isfinite(fx) else None
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, (datetime, date, pd.Timestamp)):
        try:
            return x.isoformat()
        except Exception:
            return str(x)
    if isinstance(x, np.ndarray):
        if np.issubdtype(x.dtype, np.number):
            arr = np.where(np.isfinite(x), x, np.nan)
            return sanitize_jsonable(arr.tolist())
        return sanitize_jsonable(x.tolist())
    return x


def sanitize_jsonable(obj: Any) -> Any:
    obj = _sanitize_scalar(obj)
    if isinstance(obj, dict):
        return {str(k): sanitize_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_jsonable(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        safe = obj.copy()
        safe.replace([np.inf, -np.inf], np.nan, inplace=True)
        return sanitize_jsonable(safe.to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        safe = obj.replace([np.inf, -np.inf], np.nan)
        return sanitize_jsonable(safe.to_list())
    return obj


def count_non_finite(obj: Any) -> int:
    if isinstance(obj, dict):
        return sum(count_non_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple, set)):
        return sum(count_non_finite(v) for v in obj)
    if isinstance(obj, (np.floating, float)):
        try:
            return 0 if math.isfinite(float(obj)) else 1
        except Exception:
            return 0
    if isinstance(obj, np.ndarray) and np.issubdtype(obj.dtype, np.number):
        return int(np.size(obj) - np.isfinite(obj).sum())
    return 0
