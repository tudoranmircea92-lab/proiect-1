from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.schemas.train import ActivateModelRequest, DatasetScanRequest, FeatureImportanceResponse, RegistryEntry, TrainRequest, TrainSaveRequest
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
            raise ValueError(f"Invalid file type for {f.filename}. Please select a .csv, .xlsx, or .parquet file.")
        dest = UPLOAD_DIR / f.filename
        dest.write_bytes(f.file.read())
        stored.append(str(dest))
    return stored


@router.post("/preview")
async def preview_uploaded_files(files: list[UploadFile] = File(default_factory=list)):
    try:
        file_paths = _persist_uploads(files)
        previews = []
        for path in file_paths:
            ext = Path(path).suffix.lower()
            if ext not in {".csv", ".xlsx"}:
                continue
            df = load_table(path)
            previews.append(
                {
                    "file_name": Path(path).name,
                    "message": "Showing first 5 rows of your file.",
                    "columns": df.columns.tolist(),
                    "rows": df.head(5).fillna("").to_dict(orient="records"),
                }
            )
        return {"previews": previews}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scan")
@router.post("/scan_source")
async def scan_dataset(
    request: DatasetScanRequest | None = None,
    files: list[UploadFile] | None = File(default=None),
    paths: str | None = Form(default=None),
):
    try:
        upload_paths = _persist_uploads(files or [])
        parsed_paths = [p.strip() for p in (paths or "").split(",") if p.strip()]
        body_paths = request.paths if request else []
        final_paths = resolve_paths(upload_paths + parsed_paths + body_paths)
        df = load_datasets(final_paths)
        summary = summarize_dataset(df)
        summary["resolved_paths"] = final_paths
        summary["selected_files"] = [Path(p).name for p in final_paths]
        return summary
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run")
def run_training(request: TrainRequest):
    try:
        if request.dataset_paths:
            df = load_datasets(resolve_paths(request.dataset_paths))
        elif request.process_path and request.color_path:
            df = join_process_color(request.process_path, request.color_path, request.join_tolerance_minutes)
        else:
            raise ValueError("Provide dataset_paths or process_path+color_path")
        output = train_model(
            df=df,
            product_name=request.product_name,
            target_columns=request.target_columns,
            model_type=request.model_type,
            split_mode=request.split_mode,
            ratios=request.split_ratios,
            compute_delta_e=request.compute_delta_e,
        )
        if request.include_general_model and request.product_name != "GENERAL":
            train_model(
                df=df,
                product_name="GENERAL",
                target_columns=request.target_columns,
                model_type=request.model_type,
                split_mode=request.split_mode,
                ratios=request.split_ratios,
                compute_delta_e=request.compute_delta_e,
            )
        return output
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/save")
def save_training_run(request: TrainSaveRequest):
    entry = next((e for e in list_entries() if e["run_id"] == request.run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="run not found")
    report_path = Path(entry["artifacts"]["metrics"]).with_name("training_report.html")
    html = f"<html><body><h1>Training Report {entry['run_id']}</h1><p>Product: {entry['product_name']}</p><p>Model type: {entry['model_type']}</p><pre>{entry['metrics']}</pre></body></html>"
    report_path.write_text(html, encoding="utf-8")
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
    data = read_json(entry["artifacts"]["importance"], {"by_feature": []})
    feature_groups = read_json(entry["artifacts"]["feature_groups"], {})
    by_comp: dict[str, float] = {}
    controllable, context = 0.0, 0.0
    for row in data["by_feature"]:
        feat = row["feature"]
        imp = max(0.0, row["importance"])
        grp = feature_groups.get(feat, "global")
        by_comp[grp] = by_comp.get(grp, 0.0) + imp
        if "." in feat and any(feat.endswith(s) for s in ["pwr", "m1g", "m2g", "m3g"] + [f"s{i}g" for i in range(1, 12)]):
            controllable += imp
        else:
            context += imp
    by_compartment = [{"compartment": k, "importance": float(v)} for k, v in by_comp.items()]
    by_compartment.sort(key=lambda x: x["importance"], reverse=True)
    total = controllable + context or 1.0
    return {"by_feature": data["by_feature"][:30], "by_compartment": by_compartment, "share": {"controllable": controllable / total, "context": context / total}}
