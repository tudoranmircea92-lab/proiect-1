from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.schemas.optimize import MachineConfigPatch, OptimizeRequest, OptimizeResponse
from backend.app.services.config_service import load_machine_config, save_machine_config
from backend.app.services.optimization_service import optimize
from backend.app.services.registry_service import list_optimize_results

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/run", response_model=OptimizeResponse)
def run_optimization(request: OptimizeRequest):
    try:
        return optimize(
            product_name=request.product_name,
            current_state=request.current_state,
            target_color=request.target_color,
            mode=request.mode,
            top_k=request.top_k_compartments,
            coverage_threshold=request.coverage_threshold,
            include_compartments=request.include_compartments,
            exclude_compartments=request.exclude_compartments,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/results")
def get_results(limit: int = 25):
    return {"results": list_optimize_results(limit)}


@router.get("/machine-config")
def get_machine_config():
    return load_machine_config()


@router.put("/machine-config")
def put_machine_config(payload: MachineConfigPatch):
    return save_machine_config(payload.config)
