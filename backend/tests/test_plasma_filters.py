from __future__ import annotations

import pandas as pd

from app.models.schemas import DataFilter, PlasmaStabilityRequest
from app.services.plasma_stability_service import PlasmaStabilityService


def test_filter_interval_applies_product_and_thickness_and_time_window():
    df = pd.DataFrame(
        [
            {"ts": "2026-02-16T08:42:00", "product": "PLT 4S EVO", "thickness_mm": 4.0, "c4.pwr": 10.0},
            {"ts": "2026-02-16T08:43:00", "product": "PLT 4S EVO", "thickness_mm": 4.0, "c4.pwr": 11.0},
            {"ts": "2026-02-16T08:43:00", "product": "OTHER", "thickness_mm": 8.0, "c4.pwr": 12.0},
        ]
    )

    req = PlasmaStabilityRequest(
        from_ts="2026-02-16T08:42:00",
        to_ts="2026-02-16T08:43:00",
        timestamp_col="auto",
        filter=DataFilter(products=["PLT 4S EVO"], thicknesses=["4", "4.0"]),
    )

    svc = PlasmaStabilityService()
    filtered, ts_col = svc._filter_interval(df, req)

    assert ts_col == "ts"
    assert len(filtered) == 2
    assert set(filtered["product"].astype(str).unique()) == {"PLT 4S EVO"}


def test_filter_interval_uses_glass_thickness_mm_when_thickness_mm_absent():
    df = pd.DataFrame(
        [
            {"ts": "2026-02-16T08:42:00", "product": "PLT 4S EVO", "glassThickness_mm": 3.9, "c4.pwr": 10.0},
            {"ts": "2026-02-16T08:43:00", "product": "PLT 4S EVO", "glassThickness_mm": 4.0, "c4.pwr": 11.0},
        ]
    )

    req = PlasmaStabilityRequest(
        from_ts="2026-02-16T08:40:00",
        to_ts="2026-02-16T08:50:00",
        timestamp_col="auto",
        filter=DataFilter(products=["PLT 4S EVO"], thicknesses=["4"]),
    )

    svc = PlasmaStabilityService()
    filtered, _ = svc._filter_interval(df, req)

    assert len(filtered) == 1
    assert float(filtered.iloc[0]["glassThickness_mm"]) == 4.0
