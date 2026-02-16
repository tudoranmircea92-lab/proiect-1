from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.models.schemas import (
    DataLoadResponse,
    LoadDataRequest,
    OptimizeRequest,
    OptimizeResponse,
    PlasmaStabilityRequest,
    PlasmaStabilityResponse,
    PredictRequest,
    PredictResponse,
    TrainRequest,
    TrainResponse,
)
from app.services.data_repository import DataRepository
from app.services.optimization_service import OptimizationService
from app.services.plasma_stability_service import PlasmaStabilityService
from app.services.training_service import TrainingService

router = APIRouter(prefix="/api")
repo = DataRepository()
trainer = TrainingService()
optimizer = OptimizationService(trainer)
plasma = PlasmaStabilityService()


@router.post("/data/load", response_model=DataLoadResponse)
def load_data(payload: LoadDataRequest):
    try:
        repo.load(payload.path, payload.format)
        return repo.profile()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models")
def models_available():
    return {"models": trainer.available_models()}


@router.post("/train", response_model=TrainResponse)
def train(payload: TrainRequest):
    try:
        return trainer.train(repo.get(), payload.config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/artifacts/{artifact_id}/download")
def download_artifacts(artifact_id: str):
    run_dir = Path("backend/app/artifacts_cache/runs") / artifact_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Artifact id not found")

    mem_file = io.BytesIO()
    with zipfile.ZipFile(mem_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in run_dir.glob("*"):
            zf.writestr(file.name, file.read_bytes())
    mem_file.seek(0)
    return StreamingResponse(
        mem_file,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=artifacts_{artifact_id}.zip"},
    )


@router.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    try:
        preds = trainer.predict(payload.control_knobs, payload.context)
        return {"predictions": preds}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(payload: OptimizeRequest):
    try:
        solutions = optimizer.optimize(repo.get(), payload)
        return {"solutions": solutions, "method": payload.method}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plasma_stability", response_model=PlasmaStabilityResponse)
def plasma_stability(payload: PlasmaStabilityRequest):
    try:
        result = plasma.compute(payload, repo.get())
        return {
            "summary": result.summary,
            "per_cathode": result.per_cathode,
            "timeseries": result.timeseries,
            "mode_used": result.mode_used,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/plasma_stability/export")
def plasma_stability_export(format: str = Query("csv", pattern="^(csv|json)$")):
    try:
        media_type, content = plasma.export_last(format)
        return PlainTextResponse(content=content, media_type=media_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/data/seed-plates")
def seed_plates(limit: int = 200):
    try:
        df = repo.get()
    except Exception:
        return {"rows": []}

    schema = trainer.feature_schema
    if not schema:
        return {"rows": []}

    display_cols = [c for c in ["plate", "file_ts", "day"] if c in df.columns]
    control_cols = [c for c in schema.get("control_knobs", []) if c in df.columns]
    context_cols = [c for c in schema.get("context_numeric", []) + schema.get("context_categorical", []) if c in df.columns]

    rows = []
    for _, row in df[display_cols + control_cols + context_cols].head(limit).iterrows():
        rows.append(
            {
                "meta": {k: row.get(k, None) for k in display_cols},
                "control_knobs": {k: row.get(k, None) for k in control_cols},
                "context": {k: row.get(k, None) for k in context_cols},
            }
        )
    return {"rows": rows}


@router.get("/config/feature-regex")
def feature_regex_config():
    path = Path("backend/app/configs/feature_config.json")
    return json.loads(path.read_text(encoding="utf-8"))
