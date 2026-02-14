from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from ..config import load_config
from ..services.data_loader import DataRepository
from ..services.knob_rules import KnobRules
from ..services.optimizer_api import RunInput, detect_knobs, detect_targets, run_optimizer, verify_application
from ..services.run_manager import RunManager


router = APIRouter(prefix="/api", tags=["industrial-optimizer"])
config = load_config()
repo = DataRepository(dataset_path=Path(config.dataset_path))
runs = RunManager(repo=repo)
knob_rules = KnobRules()


class DatasetLoadRequest(BaseModel):
    path: str


class RunStartRequest(BaseModel):
    date: str
    plate: str
    device: Optional[str] = None
    compartments: List[str] = Field(default_factory=list)
    target: Dict[str, float] = Field(default_factory=lambda: {"L": 0.0, "a": 0.0, "b": 0.0})
    tolerances: Dict[str, float] = Field(default_factory=lambda: {"deltaE": 1.0})
    knob_bounds: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class OptimizerRunRequest(BaseModel):
    product_name: Optional[str] = None
    day: Optional[str] = None
    plate: Optional[str] = None
    target: str
    tolerance: float = Field(default=1.0)
    mode: str = Field(default="SAFE")
    train_new_model: bool = True
    use_existing_model: bool = False
    allowed_knobs: List[str] = Field(default_factory=list)
    price_kwh: float = 0.15
    price_gas: float = 1.0


class OptimizerVerifyRequest(BaseModel):
    plate_id: str
    target: str
    predicted_profile: List[float]


def _error(status: int, message: str, details: Optional[Dict[str, Any]] = None):
    payload: Dict[str, Any] = {"error": message}
    if details:
        payload["details"] = details
    return JSONResponse(status_code=status, content=payload)


@router.get("/health")
def health():
    rows = repo.load()
    return {"status": "ok", "dataset_loaded": bool(rows), "run_count": len(runs.history())}


@router.get("/config/knob-rules")
def knob_rules_config():
    return knob_rules.all()


@router.post("/dataset/load")
def load_dataset(payload: DatasetLoadRequest):
    candidate = Path(payload.path)
    if not candidate.exists():
        return _error(400, f"Dataset path not found: {payload.path}")

    try:
        repo.set_path(payload.path)
        rows = repo.load()
    except Exception as exc:
        return _error(400, "Failed to load dataset", {"exception": str(exc)})

    if not rows:
        return _error(400, "Dataset loaded but empty")

    required = ["day", "plate_id", "device"]
    missing = [col for col in required if col not in rows[0]]
    if missing:
        return _error(400, "Required columns missing after normalization", {"missing": missing})

    return {"status": "ok", "summary": repo.summarize(rows)}


@router.get("/context")
def context(
    date: str = Query(default=""),
    plate: str = Query(default=""),
    device: Optional[str] = Query(default=None),
    strategy: str = Query(default="latest", pattern="^(latest|mean)$"),
):
    rows = repo.load()
    return repo.get_context(rows=rows, date=date, plate=plate, device=device, strategy=strategy)


@router.post("/run/start")
def run_start(payload: RunStartRequest):
    rows = repo.load()
    if not rows:
        return _error(400, "Dataset not loaded")
    if payload.date and payload.date not in {str(r.get("day", "")) for r in rows}:
        return _error(400, "Invalid date", {"date": payload.date})
    if payload.plate and payload.plate not in {str(r.get("plate_id", "")) for r in rows}:
        return _error(400, "Invalid plate", {"plate": payload.plate})
    return {"run_id": runs.start(payload.model_dump())}


@router.get("/run/status/{run_id}")
def run_status(run_id: str):
    st = runs.status(run_id)
    if "error" in st:
        raise HTTPException(status_code=404, detail=st)
    return st


@router.get("/run/history")
def run_history():
    return {"runs": runs.history()}


@router.post("/run/cancel/{run_id}")
def run_cancel(run_id: str):
    out = runs.cancel(run_id)
    if "error" in out:
        raise HTTPException(status_code=404, detail=out)
    return out


@router.get("/run/results/{run_id}")
def run_results(run_id: str):
    out = runs.results(run_id)
    if "error" in out:
        raise HTTPException(status_code=404, detail=out)
    return out


@router.get("/run/export/{run_id}")
def run_export(run_id: str, format: str = Query(pattern="^(xlsx|json|csv)$")):
    result = runs.results(run_id)
    if "artifacts" not in result:
        raise HTTPException(status_code=400, detail={"error": "Run results not ready"})
    artifacts = result["artifacts"]
    path = artifacts[format]
    media = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
        "csv": "text/csv",
    }[format]
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail={"error": f"Export file missing: {path}"})
    return FileResponse(path=p, media_type=media, filename=p.name)


@router.get("/optimizer/targets")
def optimizer_targets():
    rows = repo.load()
    return {"targets": detect_targets(rows)}


@router.get("/optimizer/knobs")
def optimizer_knobs(
    product_name: Optional[str] = Query(default=None),
    day: Optional[str] = Query(default=None),
    plate: Optional[str] = Query(default=None),
):
    rows = repo.load()
    if not rows:
        return _error(400, "Dataset not loaded")
    filtered = rows
    if product_name:
        filtered = [r for r in filtered if str(r.get("product_name") or r.get("product") or "") == product_name]
    if day:
        filtered = [r for r in filtered if str(r.get("day") or "") == day]
    if plate:
        filtered = [r for r in filtered if str(r.get("plate_id") or "") == plate]
    groups = detect_knobs(filtered if filtered else rows)
    current = (filtered[-1] if filtered else rows[-1])
    return {
        "compartments": groups,
        "current_values": {k: current.get(k) for comp in groups.values() for arr in comp.values() for k in arr},
    }


@router.post("/optimizer/run")
def optimizer_run(payload: OptimizerRunRequest):
    rows = repo.load()
    if not rows:
        return _error(400, "Dataset not loaded")
    try:
        out = run_optimizer(
            rows,
            RunInput(
                product=payload.product_name,
                day=payload.day,
                plate=payload.plate,
                target=payload.target,
                tolerance=payload.tolerance,
                mode=payload.mode,
                train_new_model=payload.train_new_model,
                use_existing_model=payload.use_existing_model,
                allowed_knobs=payload.allowed_knobs,
                price_kwh=payload.price_kwh,
                price_gas=payload.price_gas,
            ),
        )
    except Exception as exc:
        return _error(400, "Optimizer run failed", {"exception": str(exc)})
    return out


@router.post("/optimizer/verify")
def optimizer_verify(payload: OptimizerVerifyRequest):
    rows = repo.load()
    if not rows:
        return _error(400, "Dataset not loaded")
    try:
        out = verify_application(rows, payload.plate_id, payload.target, payload.predicted_profile)
    except Exception as exc:
        return _error(400, "Verification failed", {"exception": str(exc)})
    return out
