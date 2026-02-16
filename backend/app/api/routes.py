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
    LoadDataRequest,
    OptimizeRequest,
    PlasmaStabilityRequest,
    PredictRequest,
    TrainRequest,
)
from app.services.data_repository import DataRepository
from app.services.job_service import JobService
from app.services.optimization_service import OptimizationService
from app.services.plasma_stability_service import PlasmaStabilityService
from app.services.training_service import TrainingService

logger = logging.getLogger("app.api")
router = APIRouter(prefix="/api")
repo = DataRepository()
trainer = TrainingService()
optimizer = OptimizationService(trainer)
plasma = PlasmaStabilityService()
jobs = JobService()


def _job(data_func, stages: list[tuple[int, str]]):
    def runner(job_id: str):
        for p, s in stages[:-1]:
            jobs.update(job_id, progress=p, stage=s)
            time.sleep(0.05)
        result = data_func()
        jobs.update(job_id, progress=stages[-1][0], stage=stages[-1][1], result=result)
        return result

    return runner


@router.get('/jobs/{job_id}')
def get_job(job_id: str):
    try:
        return jobs.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Job not found')


@router.post('/data/load')
def data_load(payload: LoadDataRequest):
    job_id = jobs.create()

    def work():
        dataset_id, _ = repo.load(payload.path, payload.format)
        return repo.profile(dataset_id)

    jobs.run_async(job_id, lambda: _job(work, [(10, 'Preparing load'), (35, 'Reading file'), (60, 'Profiling columns'), (85, 'Building preview'), (100, 'Done')])(job_id))
    return {'job_id': job_id}


@router.post('/data/upload')
async def data_upload(file: UploadFile = File(...), format: str = Form('auto')):
    upload_dir = Path('backend/workspace/uploads')
    upload_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    clean_name = file.filename or 'dataset.bin'
    save_path = upload_dir / f'{ts}_{clean_name}'
    with save_path.open('wb') as f:
        f.write(await file.read())

    job_id = jobs.create()

    def work():
        fmt = format if format in {'auto', 'csv', 'parquet'} else 'auto'
        dataset_id, _ = repo.register_uploaded(str(save_path), fmt)
        prof = repo.profile(dataset_id)
        ext_fmt = 'parquet' if save_path.suffix.lower() in {'.parquet', '.pq'} else 'csv'
        return {'dataset_id': dataset_id, 'saved_path': str(save_path), 'format': ext_fmt, 'profile': prof}

    jobs.run_async(job_id, lambda: _job(work, [(10, 'Uploading'), (35, 'Reading file'), (60, 'Profiling columns'), (85, 'Building preview'), (100, 'Done')])(job_id))
    return {'job_id': job_id}


@router.get('/models')
def models_available():
    return {'models': trainer.available_models()}


@router.post('/train')
def train(payload: TrainRequest):
    job_id = jobs.create()

    def work():
        result = trainer.train(repo.get(payload.dataset_id), payload.config)
        return result

    jobs.run_async(job_id, lambda: _job(work, [(10, 'Preparing dataset'), (30, 'Building feature matrix'), (55, 'Training model'), (80, 'Evaluating'), (95, 'Saving artifacts'), (100, 'Done')])(job_id))
    return {'job_id': job_id}


@router.post('/predict')
def predict(payload: PredictRequest):
    job_id = jobs.create()

    def work():
        _ = repo.get(payload.dataset_id)
        return {'predictions': trainer.predict(payload.control_knobs, payload.context)}

    jobs.run_async(job_id, lambda: _job(work, [(15, 'Preparing input'), (55, 'Running model'), (100, 'Done')])(job_id))
    return {'job_id': job_id}


@router.post('/optimize')
def optimize(payload: OptimizeRequest):
    job_id = jobs.create()

    def work():
        return {'solutions': optimizer.optimize(repo.get(payload.dataset_id), payload), 'method': payload.method}

    jobs.run_async(job_id, lambda: _job(work, [(15, 'Preparing search'), (40, 'Running candidates'), (75, 'Scoring solutions'), (95, 'Building report'), (100, 'Done')])(job_id))
    return {'job_id': job_id}


@router.post('/plasma_stability')
def plasma_stability(payload: PlasmaStabilityRequest):
    job_id = jobs.create()

    def work():
        df = repo.get(payload.dataset_id) if payload.dataset_id else repo.get()
        result = plasma.compute(payload, df)
        return {'summary': result.summary, 'per_cathode': result.per_cathode, 'timeseries': result.timeseries, 'mode_used': result.mode_used}

    jobs.run_async(job_id, lambda: _job(work, [(15, 'Preparing analysis'), (45, 'Computing metrics'), (80, 'Aggregating KPIs'), (100, 'Done')])(job_id))
    return {'job_id': job_id}


@router.get('/plasma_stability/export')
def plasma_stability_export(format: str = Query('csv', pattern='^(csv|json)$')):
    try:
        media_type, content = plasma.export_last(format)
        return PlainTextResponse(content=content, media_type=media_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/data/seed-plates')
def seed_plates(dataset_id: str, limit: int = 200):
    try:
        df = repo.get(dataset_id)
    except Exception:
        return {'rows': []}

    schema = trainer.feature_schema
    if not schema:
        return {'rows': []}

    display_cols = [c for c in ['plate', 'file_ts', 'day'] if c in df.columns]
    control_cols = [c for c in schema.get('control_knobs', []) if c in df.columns]
    context_cols = [c for c in schema.get('context_numeric', []) + schema.get('context_categorical', []) if c in df.columns]

    rows = []
    for _, row in df[display_cols + control_cols + context_cols].head(limit).iterrows():
        rows.append({'meta': {k: row.get(k, None) for k in display_cols}, 'control_knobs': {k: row.get(k, None) for k in control_cols}, 'context': {k: row.get(k, None) for k in context_cols}})
    return {'rows': rows}


@router.get('/config/feature-regex')
def feature_regex_config():
    path = Path('backend/app/configs/feature_config.json')
    return json.loads(path.read_text(encoding='utf-8'))


@router.get('/artifacts/{artifact_id}/download')
def download_artifacts(artifact_id: str):
    run_dir = Path('backend/app/artifacts_cache/runs') / artifact_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail='Artifact id not found')

    mem_file = io.BytesIO()
    with zipfile.ZipFile(mem_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for file in run_dir.glob('*'):
            zf.writestr(file.name, file.read_bytes())
    mem_file.seek(0)
    return StreamingResponse(mem_file, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename=artifacts_{artifact_id}.zip'})
