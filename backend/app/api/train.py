from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.data.schema_contract import detect_target_columns, is_knob_column
from backend.app.schemas.train import ActivateModelRequest, DatasetScanRequest, ExportProcessedRequest, FeatureImportanceResponse, RegistryEntry, TrainRequest, TrainSaveRequest
from backend.app.services.dataset_service import load_datasets, resolve_paths
from backend.app.services.io_utils import SUPPORTED_EXTENSIONS, load_table, read_json
from backend.app.services.registry_service import activate_model, list_entries
from backend.app.services.training_service import train_model
from backend.app.train.data_adapter import build_training_table, detect_schema_metadata, load_color, load_process, split_process_color_paths

router = APIRouter(prefix='/train', tags=['train'])
UPLOAD_DIR = Path('backend/app/data/uploads')


def _persist_uploads(files: list[UploadFile]) -> list[str]:
    if not files:
        return []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored: list[str] = []
    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError('Invalid file type selected. Please upload a .csv, .xlsx, or .parquet file.')
        dest = UPLOAD_DIR / f.filename
        dest.write_bytes(f.file.read())
        stored.append(str(dest))
    return stored


def _build_scan_payload(process_df, color_df=None) -> dict:
    process_meta = detect_schema_metadata(process_df, 'process')
    color_meta = detect_schema_metadata(color_df, 'color') if color_df is not None else None

    detected_targets = color_meta['detected_targets'] if color_meta else detect_target_columns(process_df.columns.tolist())
    detected_knobs = sorted([c for c in process_df.columns if is_knob_column(c)])

    payload = {
        'status': 'Scan successful',
        'message': 'Processing completed',
        'rows': int(len(process_df)),
        'columns': sorted(process_df.columns.tolist()),
        'resolved_paths': [],
        'selected_files': [],
        'preview_rows': process_df.head(5).fillna('').to_dict(orient='records'),
        'keys_found': process_meta['keys_found'],
        'num_rows': process_meta['rows'],
        'num_cols': process_meta['cols'],
        'feature_count': process_meta['feature_count'],
        'detected_knobs': detected_knobs,
        'detected_targets': detected_targets,
        'process_dataset_kind': process_meta['dataset_kind'],
        'color_dataset_kind': color_meta['dataset_kind'] if color_meta else None,
        'detected_plate_col': process_meta['key_columns_detected'].get('plate'),
        'detected_timestamp_col': process_meta['key_columns_detected'].get('file_ts'),
        'compartments': sorted({k.split('.', 1)[0] for k in detected_knobs if '.' in k}),
        'has_product_name': 'product_name' in process_df.columns,
        'missing_product_name_message': "The dataset does not contain a 'product_name' column. You can proceed without this column or update your file to include it." if 'product_name' not in process_df.columns else '',
        'recommended_columns': ['product_name', 'plate', 'file_ts'],
        'schema_summary': {
            'process': process_meta,
            'color': color_meta,
        },
        'warning': '' if 'product_name' in process_df.columns else "Dataset missing 'product_name' column",
    }
    return payload


@router.post('/preview')
@router.post('/scan-preview')
async def preview_uploaded_files(files: list[UploadFile] = File(default_factory=list)):
    try:
        file_paths = _persist_uploads(files)
        previews = []
        for path in file_paths:
            ext = Path(path).suffix.lower()
            if ext not in {'.csv', '.xlsx', '.parquet'}:
                continue
            df = load_table(path)
            previews.append({'file_name': Path(path).name, 'message': 'Showing first 5 rows of your file.', 'columns': df.columns.tolist(), 'rows': df.head(5).fillna('').to_dict(orient='records')})
        return {'previews': previews}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'Invalid File Format: {exc}') from exc


@router.post('/scan')
@router.post('/scan_source')
async def scan_dataset(request: DatasetScanRequest | None = None, files: list[UploadFile] | None = File(default=None), paths: str | None = Form(default=None)):
    try:
        upload_paths = _persist_uploads(files or [])
        parsed_paths = [p.strip() for p in (paths or '').split(',') if p.strip()]
        body_paths = request.paths if request else []
        final_paths = resolve_paths(upload_paths + parsed_paths + body_paths)
        if not final_paths:
            raise ValueError('No valid input files found')

        process_path, color_path = split_process_color_paths(final_paths)
        if not process_path:
            raise ValueError('Process parquet not found')

        process_df = load_process(process_path, mode='auto')
        color_df = load_color(color_path, mode='auto') if color_path else None

        payload = _build_scan_payload(process_df, color_df)
        payload['resolved_paths'] = final_paths
        payload['selected_files'] = [Path(p).name for p in final_paths]
        return payload
    except Exception as exc:
        msg = str(exc)
        if 'Invalid file type selected' in msg:
            raise HTTPException(status_code=400, detail=msg) from exc
        raise HTTPException(status_code=400, detail=f'Invalid File Format: {msg}') from exc


@router.post('/run')
def run_training(request: TrainRequest):
    try:
        if request.dataset_paths:
            paths = resolve_paths(request.dataset_paths)
            process_path, color_path = split_process_color_paths(paths)
        elif request.process_path and request.color_path:
            process_path, color_path = request.process_path, request.color_path
            paths = resolve_paths([process_path, color_path])
        else:
            raise ValueError('Provide dataset_paths or process_path+color_path')

        if not process_path or not color_path:
            raise ValueError('Both process and color datasets are required for new schema training')

        process_df = load_process(process_path, mode='auto')
        color_df = load_color(color_path, mode='auto')
        merged_df, merge_stats = build_training_table(process_df, color_df, key_strategy='auto')

        schema_summary = {
            'process': detect_schema_metadata(process_df, 'process'),
            'color': detect_schema_metadata(color_df, 'color'),
            'resolved_paths': paths,
        }

        output = train_model(
            df=merged_df,
            product_name=request.product_name or 'GENERAL',
            target_columns=request.target_columns,
            model_type=request.model_type,
            split_mode=request.split_mode,
            ratios=request.split_ratios,
            compute_delta_e=request.compute_delta_e,
            schema_summary=schema_summary,
            merge_stats=merge_stats,
        )
        output['preview_rows'] = merged_df.head(5).fillna('').to_dict(orient='records')
        output['schema_summary'] = schema_summary
        output['merge_stats'] = merge_stats
        return output
    except Exception as exc:
        msg = str(exc)
        if 'Network' in msg:
            raise HTTPException(status_code=503, detail='Network Error') from exc
        raise HTTPException(status_code=400, detail=msg) from exc


@router.get('/importance')
def get_importance_by_model(model_id: str):
    entry = next((e for e in list_entries() if e['run_id'] == model_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail='model not found')
    return read_json(entry['artifacts']['importance'], {})


@router.post('/export-processed')
def export_processed_data(request: ExportProcessedRequest):
    try:
        df = load_datasets(resolve_paths(request.dataset_paths))
        out_dir = Path('backend/app/data/exports')
        out_dir.mkdir(parents=True, exist_ok=True)
        if request.file_format == 'xlsx':
            out = out_dir / 'processed_data.xlsx'
            df.to_excel(out, index=False)
            media = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            out = out_dir / 'processed_data.csv'
            df.to_csv(out, index=False)
            media = 'text/csv'
        return FileResponse(out, filename=out.name, media_type=media)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/save')
def save_training_run(request: TrainSaveRequest):
    entry = next((e for e in list_entries() if e['run_id'] == request.run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail='run not found')

    metrics = read_json(entry['artifacts'].get('metrics', ''), {})
    train_config = read_json(entry['artifacts'].get('train_config', ''), {})

    schema_summary = train_config.get('schema_summary', {})
    merge_stats = train_config.get('merge_stats', {})

    report_path = Path(entry['artifacts']['metrics']).with_name('training_report.html')
    html = f"""
<html><body>
  <h1>Training Report {entry['run_id']}</h1>
  <h2>Metrics</h2>
  <pre>{metrics}</pre>
  <h2>Schema summary (scan_source)</h2>
  <pre>{schema_summary}</pre>
  <h2>Merged rows and dropped rows</h2>
  <pre>{merge_stats}</pre>
  <h2>Feature/Knob counts</h2>
  <pre>{{'feature_count': {train_config.get('feature_count', 0)}, 'knob_count': {train_config.get('knob_count', 0)}}}</pre>
</body></html>
"""
    report_path.write_text(html, encoding='utf-8')
    return {'status': 'saved', 'run_id': request.run_id, 'report': str(report_path)}


@router.get('/artifact/{run_id}')
def download_model_artifact(run_id: str):
    entry = next((e for e in list_entries() if e['run_id'] == run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail='run not found')
    model_path = Path(entry['artifacts']['model'])
    if not model_path.exists():
        raise HTTPException(status_code=404, detail='artifact missing')
    return FileResponse(model_path, filename=f'{run_id}_model.joblib', media_type='application/octet-stream')


@router.get('/registry', response_model=list[RegistryEntry])
@router.get('/runs', response_model=list[RegistryEntry])
def get_registry(product_name: str | None = None):
    return list_entries(product_name)


@router.post('/registry/activate')
def set_active(request: ActivateModelRequest):
    try:
        return activate_model(request.run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/importance/{run_id}', response_model=FeatureImportanceResponse)
def get_importance(run_id: str):
    entry = next((e for e in list_entries() if e['run_id'] == run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail='run not found')
    data = read_json(entry['artifacts']['importance'], {'feature_importances': [], 'importance_by_compartment': [], 'total_controllable_share': 0, 'total_context_share': 0})
    return {
        'by_feature': data.get('feature_importances', []),
        'by_compartment': data.get('importance_by_compartment', []),
        'share': {'controllable': data.get('total_controllable_share', 0), 'context': data.get('total_context_share', 0)},
    }
