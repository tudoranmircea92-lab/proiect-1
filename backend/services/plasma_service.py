from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
from typing import Any

from schemas.plasma import PlasmaColumnsResponse, PlasmaStabilityRequest, PlasmaStabilityResponse


class PlasmaService:
    VERSION = "1.0.0"

    @staticmethod
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "plasma",
            "version": PlasmaService.VERSION,
            "time": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def columns() -> PlasmaColumnsResponse:
        return PlasmaColumnsResponse(
            time_column="file_ts",
            available_columns=["c4.pwr", "c4.cur", "c4.volt", "file_ts", "plate", "device"],
            defaults={
                "active_threshold": 0.0,
                "aggregation": "mean",
                "group_by": ["device", "plate"],
            },
        )

    @staticmethod
    def stability(payload: PlasmaStabilityRequest) -> PlasmaStabilityResponse:
        # Placeholder deterministic output aligned to contract.
        return PlasmaStabilityResponse(
            window={"from_ts": payload.from_ts, "to_ts": payload.to_ts},
            params={
                "from_ts": payload.from_ts.isoformat(),
                "to_ts": payload.to_ts.isoformat(),
                "active_threshold": payload.active_threshold,
                "aggregation": payload.aggregation,
                "group_by": payload.group_by,
                "features": payload.features,
                "filters": payload.filters.model_dump(),
            },
            score=0.0,
            score_details={
                "method": "contract_placeholder",
                "threshold": payload.active_threshold,
            },
            series=[],
            warnings=[],
            row_count=0,
        )

    @staticmethod
    def export_csv(payload: PlasmaStabilityRequest) -> str:
        data = PlasmaService.stability(payload)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["from_ts", "to_ts", "score", "row_count", "aggregation", "active_threshold"])
        writer.writerow([
            data.window["from_ts"].isoformat(),
            data.window["to_ts"].isoformat(),
            data.score,
            data.row_count,
            payload.aggregation,
            payload.active_threshold,
        ])
        return out.getvalue()
