from __future__ import annotations

"""Color feature engineering on Optoplex/Lambda scalar values."""

from statistics import mean, pstdev
from typing import Any


def _safe_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "std": None, "min": None, "max": None, "range": None}
    return {
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
    }


def build_color_features(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    by_device: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_device.setdefault(str(row.get("device") or "unknown"), []).append(row)

    out: dict[str, float | None] = {}
    for device, drows in by_device.items():
        for metric in ("L", "a", "b", "Y"):
            vals = [float(r[metric]) for r in drows if r.get(metric) is not None]
            stats = _safe_stats(vals)
            for k, v in stats.items():
                out[f"{device}_{metric}_{k}"] = v
        left = [float(r["L"]) for r in drows if r.get("position") in {1, 802} and r.get("L") is not None]
        center = [float(r["L"]) for r in drows if r.get("position") in {2, 1605} and r.get("L") is not None]
        right = [float(r["L"]) for r in drows if r.get("position") in {3, 2407} and r.get("L") is not None]
        out[f"{device}_uniformity_L_range"] = (max(left + center + right) - min(left + center + right)) if (left + center + right) else None
    return out
