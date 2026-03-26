from __future__ import annotations

"""Baseline computation grouped by recipe-like fields."""

from collections import defaultdict
from typing import Any


def build_baselines(plate_rows: list[dict[str, Any]], feature_keys: list[str]) -> dict[tuple[str, float | None], dict[str, float | None]]:
    grouped: dict[tuple[str, float | None], list[dict[str, Any]]] = defaultdict(list)
    for row in plate_rows:
        grouped[(str(row.get("product") or ""), row.get("glassThickness"))].append(row)

    baselines: dict[tuple[str, float | None], dict[str, float | None]] = {}
    for key, rows in grouped.items():
        feats: dict[str, float | None] = {}
        for feat in feature_keys:
            vals = [float(r[feat]) for r in rows if r.get(feat) is not None]
            feats[feat] = sum(vals) / len(vals) if vals else None
        baselines[key] = feats
    return baselines
