from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.train import ActivateModelRequest, DatasetScanRequest, FeatureImportanceResponse, RegistryEntry, TrainRequest
from app.services.dataset_service import join_process_color, load_datasets, resolve_paths, summarize_dataset
from app.services.io_utils import read_json
from app.services.registry_service import activate_model, list_entries
from app.services.training_service import train_model

router = APIRouter(prefix="/train", tags=["train"])


@router.post("/scan")
def scan_dataset(request: DatasetScanRequest):
    try:
        paths = resolve_paths(request.paths)
        df = load_datasets(paths)
        return summarize_dataset(df)
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


@router.get("/registry", response_model=list[RegistryEntry])
def get_registry(product_name: str | None = None):
    return [
        {
            **e,
            "is_active": False,
        }
        for e in list_entries(product_name)
    ]


@router.post("/registry/activate")
def set_active(request: ActivateModelRequest):
    try:
        return activate_model(request.run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/importance/{run_id}", response_model=FeatureImportanceResponse)
def get_importance(run_id: str):
    entries = list_entries()
    entry = next((e for e in entries if e["run_id"] == run_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="run not found")
    data = read_json(entry["artifacts"]["importance"], {"by_feature": []})
    feature_groups = read_json(entry["artifacts"]["feature_groups"], {})
    by_comp = {}
    controllable = 0.0
    context = 0.0
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
    return {
        "by_feature": data["by_feature"][:30],
        "by_compartment": by_compartment,
        "share": {"controllable": controllable / total, "context": context / total},
    }
