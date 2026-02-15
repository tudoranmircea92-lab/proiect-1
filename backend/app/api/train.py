from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.schemas.train import ActivateModelRequest, DatasetScanRequest, ExportProcessedRequest, FeatureImportanceResponse, RegistryEntry, TrainRequest, TrainSaveRequest
from backend.app.services.dataset_service import join_process_color, load_datasets, resolve_paths, summarize_dataset
from backend.app.services.io_utils import SUPPORTED_EXTENSIONS, load_table, read_json
from backend.app.services.registry_service import activate_model, list_entries
from backend.app.services.training_service import train_model

router = APIRouter(prefix="/train", tags=["train"])
UPLOAD_DIR = Path("backend/app/data/uploads")


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
            raise ValueError("Invalid file type selected. Please upload a .csv, .xlsx, or .parquet file.")
        dest = UPLOAD_DIR / f.filename
        dest.write_bytes(f.file.read())
        stored.append(str(dest))
    return stored


@router.post("/preview")
@router.post("/scan-preview")
async def preview_uploaded_files(files: list[UploadFile] = File(default_factory=list)):
    try:
        file_paths = _persist_uploads(files)
        previews = []
        for path in file_paths:
            ext = Path(path).suffix.lower()
            if ext not in {".csv", ".xlsx"}:
                continue
            df = load_table(path)
            previews.append({"file_name": Path(path).name, "message": "Showing first 5 rows of your file.", "columns": df.columns.tolist(), "rows": df.head(5).fillna("").to_dict(orient="records")})
        return {"previews": previews}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid File Format: {exc}") from exc


@router.post("/scan")
@router.post("/scan_source")
async def scan_dataset(request: DatasetScanRequest | None = None, files: list[UploadFile] | None = File(default=None), paths: str | None = Form(default=None)):
    try:
        upload_paths = _persist_uploads(files or [])
        parsed_paths = [p.strip() for p in (paths or "").split(",") if p.strip()]
        body_paths = request.paths if request else []
        final_paths = resolve_paths(upload_paths + parsed_paths + body_paths)
        df = load_datasets(final_paths)
        summary = summarize_dataset(df)

        preview_rows = df.head(5).fillna("").to_dict(orient="records")
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        stats = {}
        for col in numeric_cols[:20]:
            s = df[col]
            stats[col] = {"mean": float(s.mean()) if not s.empty else 0.0, "std": float(s.std()) if not s.empty else 0.0, "min": float(s.min()) if not s.empty else 0.0, "max": float(s.max()) if not s.empty else 0.0}

        feature_proxy = [{"feature": c, "importance": float(v), "group": "context", "compartment": c.split('.', 1)[0] if '.' in c else 'global'} for c, v in summary.get("missing_rates", {}).items()]
        if not feature_proxy:
            feature_proxy = [{"feature": c, "importance": float(i + 1), "group": "context", "compartment": c.split('.', 1)[0] if '.' in c else 'global'} for i, c in enumerate(summary.get("columns", [])[:12])]
        comp = {}
        for r in feature_proxy:
            comp[r["compartment"]] = comp.get(r["compartment"], 0.0) + r["importance"]
        comp_rows = [{"compartment": k, "importance": float(v)} for k, v in comp.items()]

        summary.update({
            "resolved_paths": final_paths,
            "selected_files": [Path(p).name for p in final_paths],
            "status": "Scan successful",
            "message": "Processing completed",
            "preview_rows": preview_rows,
            "summary_stats": stats,
            "warning": summary.get("missing_product_name_message", "") if not summary.get("has_product_name", True) else "",
            "chart_data": {
                "feature_importance": feature_proxy,
                "importance_by_compartment": comp_rows,
                "total_controllable_share": 0.0,
                "total_context_share": 1.0,
                "metrics": [
                    {"name": "rows", "mae": float(summary.get("rows", 0)), "rmse": float(summary.get("plates", 0)), "deltaE": float(len(summary.get("products", [])))}
                ],
            },
        })
        return summary
    except Exception as exc:
        msg = str(exc)
        if "Invalid file type selected" in msg:
            raise HTTPException(status_code=400, detail=msg) from exc
        raise HTTPException(status_code=400, detail=f"Invalid File Format: {msg}") from exc


@router.post("/run")
def run_training(request: TrainRequest):
    try:
        if request.dataset_paths:
            df = load_datasets(resolve_paths(request.dataset_paths))
        elif request.process_path and request.color_path:
            df = join_process_color(request.process_path, request.color_path, request.join_tolerance_minutes)
        else:
            raise ValueError("Provide dataset_paths or process_path+color_path")

        output = train_model(df=df, product_name=request.product_name or "GENERAL", target_columns=request.target_columns, model_type=request.model_type, split_mode=request.split_mode, ratios=request.split_ratios, compute_delta_e=request.compute_delta_e)
        output["preview_rows"] = df.head(5).fillna("").to_dict(orient="records")
        return output
    except Exception as exc:
        msg = str(exc)
        if "Network" in msg:
            raise HTTPException(status_code=503, detail="Network Error") from exc
        raise HTTPException(status_code=400, detail=msg) from exc


@router.get("/importance")
def get_importance_by_model(model_id: str):
    entry = next((e for e in list_entries() if e["run_id"] == model_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="model not found")
    return read_json(entry["artifacts"]["importance"], {})


@router.post("/export-processed")
def export_processed_data(request: ExportProcessedRequest):
    try:
        df = load_datasets(resolve_paths(request.dataset_paths))
        out_dir = Path("backend/app/data/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        if request.file_format == "xlsx":
            out = out_dir / "processed_data.xlsx"
            df.to_excel(out, index=False)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            out = out_dir / "processed_data.csv"
            df.to_csv(out, index=False)
            media = "text/csv"
        return FileResponse(out, filename=out.name, media_type=media)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/save")
def save_training_run(request: TrainSaveRequest):
    entry = next((e for e in list_entries() if e["run_id"] == request.run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="run not found")
    report_path = Path(entry["artifacts"]["metrics"]).with_name("training_report.html")
    report_path.write_text(f"<html><body><h1>Training Report {entry['run_id']}</h1><pre>{entry['metrics']}</pre></body></html>", encoding="utf-8")
    return {"status": "saved", "run_id": request.run_id, "report": str(report_path)}


@router.get("/artifact/{run_id}")
def download_model_artifact(run_id: str):
    entry = next((e for e in list_entries() if e["run_id"] == run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="run not found")
    model_path = Path(entry["artifacts"]["model"])
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="artifact missing")
    return FileResponse(model_path, filename=f"{run_id}_model.joblib", media_type="application/octet-stream")


@router.get("/registry", response_model=list[RegistryEntry])
@router.get("/runs", response_model=list[RegistryEntry])
def get_registry(product_name: str | None = None):
    return list_entries(product_name)


@router.post("/registry/activate")
def set_active(request: ActivateModelRequest):
    try:
        return activate_model(request.run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/importance/{run_id}", response_model=FeatureImportanceResponse)
def get_importance(run_id: str):
    entry = next((e for e in list_entries() if e["run_id"] == run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="run not found")
    data = read_json(entry["artifacts"]["importance"], {"feature_importances": [], "importance_by_compartment": [], "total_controllable_share": 0, "total_context_share": 0})
    return {
        "by_feature": data.get("feature_importances", []),
        "by_compartment": data.get("importance_by_compartment", []),
        "share": {"controllable": data.get("total_controllable_share", 0), "context": data.get("total_context_share", 0)},
    }
