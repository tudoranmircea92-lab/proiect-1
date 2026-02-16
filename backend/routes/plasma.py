from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import Response

from core.errors import PlasmaApiError
from schemas.plasma import PlasmaStabilityRequest
from services.plasma_service import PlasmaService

router = APIRouter(prefix="/api/plasma", tags=["plasma"])
legacy_router = APIRouter(tags=["plasma-legacy"])


@router.get("/health")
def plasma_health():
    return PlasmaService.health()


@router.get("/columns")
def plasma_columns():
    return PlasmaService.columns().model_dump(mode="json")


@router.post("/stability")
def plasma_stability(payload: PlasmaStabilityRequest):
    if payload.to_ts < payload.from_ts:
        raise PlasmaApiError(
            status_code=400,
            code="PLASMA_INVALID_WINDOW",
            message="Invalid time window",
            details={"hint": "to_ts must be >= from_ts"},
        )
    return PlasmaService.stability(payload).model_dump(mode="json")


@router.get("/stability/export")
def plasma_stability_export(
    from_ts: datetime,
    to_ts: datetime,
    active_threshold: float = 0.0,
    aggregation: str = Query("mean", pattern="^(mean|median)$"),
    group_by: list[str] = Query(default=["device", "plate"]),
    features: list[str] = Query(default=[]),
    product: list[str] = Query(default=[]),
    thickness_mm: list[float] = Query(default=[]),
):
    payload = PlasmaStabilityRequest(
        from_ts=from_ts,
        to_ts=to_ts,
        active_threshold=active_threshold,
        aggregation=aggregation,
        group_by=group_by,
        features=features,
        filters={"product": product, "thickness_mm": thickness_mm},
    )
    csv_content = PlasmaService.export_csv(payload)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="plasma_stability.csv"'},
    )


def _deprecated(path_hint: str):
    raise PlasmaApiError(
        status_code=410,
        code="PLASMA_ENDPOINT_DEPRECATED",
        message="Deprecated endpoint. Use /api/plasma/...",
        details={"hint": f"Use {path_hint}"},
    )


@legacy_router.api_route("/api/plasma_stability", methods=["GET", "POST"], include_in_schema=False)
def plasma_stability_legacy():
    _deprecated("/api/plasma/stability")


@legacy_router.api_route("/api/plasma/export_csv", methods=["GET", "POST"], include_in_schema=False)
def plasma_export_csv_legacy():
    _deprecated("/api/plasma/stability/export")
