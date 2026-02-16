from __future__ import annotations

import hashlib
import io
import json
import logging
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from app.models.schemas import (
    DataFilter,
    LoadDataRequest,
    OptimizeRequest,
    PlasmaStabilityRequest,
    PredictRequest,
    TrainRequest,
)
from app.services.data_repository import DataRepository
from app.services.job_service import JobService
from app.services.optimization_service import OptimizationService
from app.services.training_service import TrainingService
from app.services.json_sanitize import count_non_finite, sanitize_jsonable

logger = logging.getLogger("app.api")
router = APIRouter(prefix="/api")
repo = DataRepository()
trainer = TrainingService()
optimizer = OptimizationService(trainer, repo)
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
        return sanitize_jsonable(jobs.get(job_id))
    except KeyError:
        raise HTTPException(status_code=404, detail='Job not found')


@router.post('/data/load')
def data_load(payload: LoadDataRequest):
    job_id = jobs.create()

    def work():
        dataset_id, _ = repo.load(payload.path, payload.format)
        payload = repo.profile(dataset_id)
        bad = count_non_finite(payload)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('data/load non-finite count=%s', bad)
        return sanitize_jsonable(payload)

    jobs.run_async(job_id, lambda: _job(work, [(10, 'Preparing load'), (35, 'Reading file'), (60, 'Profiling columns'), (85, 'Building preview'), (100, 'Done')])(job_id))
    return sanitize_jsonable({'job_id': job_id})


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
        payload = {'dataset_id': dataset_id, 'saved_path': str(save_path), 'format': ext_fmt, 'profile': prof}
        bad = count_non_finite(payload)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('data/upload non-finite count=%s', bad)
        return sanitize_jsonable(payload)

    jobs.run_async(job_id, lambda: _job(work, [(10, 'Uploading'), (35, 'Reading file'), (60, 'Profiling columns'), (85, 'Building preview'), (100, 'Done')])(job_id))
    return sanitize_jsonable({'job_id': job_id})


@router.get('/models')
def models_available():
    payload = {'models': trainer.available_models()}
    return sanitize_jsonable(payload)


@router.post('/train')
def train(payload: TrainRequest):
    job_id = jobs.create()

    def work():
        result = trainer.train(repo.get(payload.dataset_id), payload.config, dataset_id=payload.dataset_id, data_filter=payload.filter)
        return sanitize_jsonable(result)

    jobs.run_async(job_id, lambda: _job(work, [(10, 'Preparing dataset'), (30, 'Building feature matrix'), (55, 'Training model'), (80, 'Evaluating'), (95, 'Saving artifacts'), (100, 'Done')])(job_id))
    return sanitize_jsonable({'job_id': job_id})


@router.post('/predict')
def predict(payload: PredictRequest):
    job_id = jobs.create()

    def _loss(pred: dict[str, float], target, tol, device: str, outputs: str):
        if not target:
            return None
        if outputs == 'b_only':
            t = float(target.b or 0.0)
            tb = float((tol.b if tol else 0.0) or 0.0)
            return float(max(0.0, abs(float(pred.get(f'b_{device}_mean', 0.0)) - t) - tb))
        total = 0.0
        for ch in ['L', 'a', 'b']:
            tv = getattr(target, ch, None)
            if tv is None:
                continue
            tolv = getattr(tol, ch, 0.0) if tol else 0.0
            total += max(0.0, abs(float(pred.get(f'{ch}_{device}_mean', 0.0)) - float(tv)) - float(tolv or 0.0))
        return float(total)

    def work():
        if payload.plate_id:
            if not trainer.feature_schema:
                raise ValueError('Train a model first before prediction.')
            baseline = repo.plate_baseline(payload.dataset_id, payload.plate_id, trainer.feature_schema.get('control_knobs', []), filt=payload.filter)
            row = repo.plate_row(payload.dataset_id, payload.plate_id, filt=payload.filter)
            context = {}
            for k in trainer.feature_schema.get('context_numeric', []):
                v = row.get(k, 0.0)
                context[k] = 0.0 if v is None else float(v) if str(v) not in {'nan', 'NaT'} else 0.0
            for k in trainer.feature_schema.get('context_categorical', []):
                v = row.get(k, '')
                context[k] = '' if v is None else v

            baseline_knobs = {k: float(v) for k, v in baseline['baseline_knobs'].items()}
            edited = dict(baseline_knobs)
            for k, v in (payload.knob_overrides or {}).items():
                if k in edited:
                    edited[k] = float(v)

            pred_baseline_full = trainer.predict(baseline_knobs, context)
            pred_edited_full = trainer.predict(edited, context)
            actual_dev = baseline['actual_color'].get(payload.device, {})

            if payload.outputs == 'b_only':
                actual = {'b': actual_dev.get('b_mean'), 'b_std': actual_dev.get('b_std'), 'b_points': actual_dev.get('b_points', [])}
                pred_baseline = {'b': pred_baseline_full.get(f'b_{payload.device}_mean')}
                pred_edited = {'b': pred_edited_full.get(f'b_{payload.device}_mean')}
            else:
                actual = {
                    'L': actual_dev.get('L_mean'), 'L_std': actual_dev.get('L_std'), 'L_points': actual_dev.get('L_points', []),
                    'a': actual_dev.get('a_mean'), 'a_std': actual_dev.get('a_std'), 'a_points': actual_dev.get('a_points', []),
                    'b': actual_dev.get('b_mean'), 'b_std': actual_dev.get('b_std'), 'b_points': actual_dev.get('b_points', []),
                }
                pred_baseline = {k: pred_baseline_full.get(f'{k}_{payload.device}_mean') for k in ['L', 'a', 'b']}
                pred_edited = {k: pred_edited_full.get(f'{k}_{payload.device}_mean') for k in ['L', 'a', 'b']}

            changes = []
            for k, base in baseline_knobs.items():
                ev = float(edited.get(k, base))
                delta = ev - float(base)
                if abs(delta) < 1e-12:
                    continue
                lk = k.lower().replace('_', '.')
                cath = lk.split('.')[0] if lk.startswith('c') else 'other'
                changes.append({'cathode': cath, 'knob': k, 'baseline': float(base), 'edited': ev, 'delta': delta})

            schema_hash = hashlib.sha256(json.dumps(trainer.feature_schema, sort_keys=True).encode('utf-8')).hexdigest()[:16]
            out = {
                'plate_id': payload.plate_id,
                'device': payload.device,
                'outputs': payload.outputs,
                'actual': actual,
                'pred_baseline': pred_baseline,
                'pred_edited': pred_edited,
                'loss_baseline': _loss(pred_baseline_full, payload.target, payload.tolerance, payload.device, payload.outputs),
                'loss_edited': _loss(pred_edited_full, payload.target, payload.tolerance, payload.device, payload.outputs),
                'knob_changes': changes,
                'used_feature_schema_hash': schema_hash,
            }
            return sanitize_jsonable(out)

        _ = repo.apply_filter(repo.get(payload.dataset_id), payload.filter)
        return sanitize_jsonable({'predictions': trainer.predict(payload.control_knobs, payload.context)})

    jobs.run_async(job_id, lambda: _job(work, [(15, 'Fetching baseline'), (40, 'Building feature row'), (70, 'Predicting'), (100, 'Rendering results')])(job_id))
    return sanitize_jsonable({'job_id': job_id})


@router.post('/optimize')
def optimize(payload: OptimizeRequest):
    job_id = jobs.create()

    def work():
        result = optimizer.optimize(repo.get(payload.dataset_id), payload)
        return sanitize_jsonable(result)

    jobs.run_async(job_id, lambda: _job(work, [(15, 'Preparing search'), (40, 'Running candidates'), (75, 'Scoring solutions'), (95, 'Building report'), (100, 'Done')])(job_id))
    return sanitize_jsonable({'job_id': job_id})


@router.get('/seed_rows')
def seed_rows(dataset_id: str, product: str | None = None, thickness: str | None = None, from_ts: str | None = None, to_ts: str | None = None, limit: int = 300):
    filt = DataFilter(products=[product] if product else [], thicknesses=[thickness] if thickness else [], date_from=from_ts, date_to=to_ts)
    rows = repo.seed_rows(dataset_id, filt=None if not any([product, thickness, from_ts, to_ts]) else filt, limit=limit)
    return sanitize_jsonable({'rows': rows})


@router.get('/plate/{plate_id}/baseline')
def plate_baseline(plate_id: str, dataset_id: str, active_threshold: float = 0.0):
    if not trainer.feature_schema:
        raise HTTPException(status_code=400, detail='Train a model first')
    payload = repo.plate_baseline(dataset_id, plate_id, trainer.feature_schema.get('control_knobs', []), active_threshold=active_threshold)
    return sanitize_jsonable(payload)


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
    return sanitize_jsonable({'rows': rows})




@router.get('/optimize/context')
def optimize_context(dataset_id: str, plate_id: str | None = None, product: str | None = None, thickness: str | None = None, from_ts: str | None = None, to_ts: str | None = None):
    filt = None
    if any([product, thickness, from_ts, to_ts]):
        filt = DataFilter(products=[product] if product else [], thicknesses=[thickness] if thickness else [], date_from=from_ts, date_to=to_ts)

    df = repo.apply_filter(repo.get(dataset_id), filt)
    if df.empty:
        return sanitize_jsonable({'knob_schema': {'cathodes': [], 'gases_main': {'keys': ['main1', 'main2', 'main3'], 'cols': {}}, 'gases_segmented': {'mode': 'none', 'entities': [], 'cols': {}}}})

    row = None
    if plate_id:
        try:
            row = repo.plate_row(dataset_id, plate_id, filt=filt)
        except Exception:
            row = None

    knob_schema = repo.discover_knob_schema(df, row=row)
    out = {'knob_schema': knob_schema}

    if plate_id and trainer.feature_schema:
        try:
            baseline = repo.plate_baseline(dataset_id, plate_id, trainer.feature_schema.get('control_knobs', []), filt=filt)
            out['baseline'] = baseline
        except Exception:
            pass

    return sanitize_jsonable(out)

@router.get('/filters/options')
def filter_options(dataset_id: str):
    df = repo.get(dataset_id)
    prof = repo.profile(dataset_id)
    return sanitize_jsonable({
        'products': prof.get('products', []),
        'thicknesses': prof.get('thicknesses', []),
        'product_column': prof.get('product_column'),
        'thickness_column': prof.get('thickness_column'),
        'rows': len(df),
    })


@router.get('/plates')
def plates(dataset_id: str, product: str | None = None, thickness: str | None = None, date_from: str | None = None, date_to: str | None = None, limit: int = 200):
    filt = {'products': [product] if product else [], 'thicknesses': [thickness] if thickness else [], 'date_from': date_from, 'date_to': date_to}
    rows = repo.plate_rows(dataset_id, filt=None if not any([product, thickness, date_from, date_to]) else DataFilter(**filt), limit=limit)
    return sanitize_jsonable({'rows': rows})


@router.get('/plate/{plate_id}/color')
def plate_color(plate_id: str, dataset_id: str, device: str):
    return sanitize_jsonable(repo.color_profile(dataset_id, plate_id, device))


@router.get('/config/feature-regex')
def feature_regex_config():
    path = Path('backend/app/configs/feature_config.json')
    return sanitize_jsonable(json.loads(path.read_text(encoding='utf-8')))


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
