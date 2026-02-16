from __future__ import annotations

import io
import json
import logging
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.models.schemas import (
    DataLoadResponse,
    DataUploadResponse,
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

logger = logging.getLogger("app.api")
router = APIRouter(prefix="/api")
repo = DataRepository()
trainer = TrainingService()
optimizer = OptimizationService(trainer)
plasma = PlasmaStabilityService()


@router.post("/data/load", response_model=DataLoadResponse)
def load_data(payload: LoadDataRequest):
    try:
        dataset_id, _ = repo.load(payload.path, payload.format)
        logger.info("Loaded dataset from path into dataset_id=%s", dataset_id)
        return repo.profile(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/data/upload", response_model=DataUploadResponse)
async def upload_data(file: UploadFile = File(...), format: str = Form("auto")):
    try:
        upload_dir = Path("backend/workspace/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        clean_name = file.filename or "dataset.bin"
        save_path = upload_dir / f"{ts}_{clean_name}"
        with save_path.open("wb") as f:
            f.write(await file.read())

        fmt = format if format in {"auto", "csv", "parquet"} else "auto"
        dataset_id, _ = repo.register_uploaded(str(save_path), fmt)
        prof = repo.profile(dataset_id)
        ext_fmt = "parquet" if save_path.suffix.lower() in {".parquet", ".pq"} else "csv"
        logger.info("Uploaded dataset stored at %s as dataset_id=%s", save_path, dataset_id)
        return {"dataset_id": dataset_id, "saved_path": str(save_path), "format": ext_fmt, "profile": prof}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models")
def models_available():
    return {"models": trainer.available_models()}


@router.post("/train", response_model=TrainResponse)
def train(payload: TrainRequest):
    try:
        return trainer.train(repo.get(payload.dataset_id), payload.config)
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
    return StreamingResponse(mem_file, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename=artifacts_{artifact_id}.zip"})


@router.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    try:
        _ = repo.get(payload.dataset_id)
        preds = trainer.predict(payload.control_knobs, payload.context)
        return {"predictions": preds}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(payload: OptimizeRequest):
    try:
        solutions = optimizer.optimize(repo.get(payload.dataset_id), payload)
        return {"solutions": solutions, "method": payload.method}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plasma_stability", response_model=PlasmaStabilityResponse)
def plasma_stability(payload: PlasmaStabilityRequest):
    try:
        df = repo.get(payload.dataset_id) if payload.dataset_id else repo.get()
        result = plasma.compute(payload, df)
        return {"summary": result.summary, "per_cathode": result.per_cathode, "timeseries": result.timeseries, "mode_used": result.mode_used}
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
def seed_plates(dataset_id: str, limit: int = 200):
    try:
        df = repo.get(dataset_id)
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
        rows.append({"meta": {k: row.get(k, None) for k in display_cols}, "control_knobs": {k: row.get(k, None) for k in control_cols}, "context": {k: row.get(k, None) for k in context_cols}})
    return {"rows": rows}


@router.get("/config/feature-regex")
def feature_regex_config():
    path = Path("backend/app/configs/feature_config.json")
    return json.loads(path.read_text(encoding="utf-8"))
