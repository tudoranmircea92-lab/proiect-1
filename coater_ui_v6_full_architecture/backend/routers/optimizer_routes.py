from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from ..config import load_config
from ..services.data_loader import DataRepository
from ..services.run_manager import RunManager


router = APIRouter(prefix="/api", tags=["industrial-optimizer"])
config = load_config()
repo = DataRepository(dataset_path=Path(config.dataset_path))
runs = RunManager(repo=repo)


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


@router.post("/dataset/load")
def load_dataset(payload: DatasetLoadRequest):
    candidate = Path(payload.path)
    if not candidate.exists():
        return JSONResponse(status_code=400, content={"error": f"Dataset path not found: {payload.path}"})

    repo.set_path(payload.path)
    rows = repo.load()
    if not rows:
        return JSONResponse(status_code=400, content={"error": "Dataset loaded but empty"})

    return {"status": "ok", "summary": repo.summarize(rows)}


@router.get("/context")
def context(
    date: str = Query(default=""),
    plate: str = Query(default=""),
    device: Optional[str] = Query(default=None),
):
    rows = repo.load()
    return repo.get_context(rows=rows, date=date, plate=plate, device=device)


@router.post("/run/start")
def run_start(payload: RunStartRequest):
    rows = repo.load()
    if not rows:
        return JSONResponse(status_code=400, content={"error": "Dataset not loaded"})
    return {"run_id": runs.start(payload.model_dump())}


@router.get("/run/status/{run_id}")
def run_status(run_id: str):
    st = runs.status(run_id)
    if "error" in st:
        raise HTTPException(status_code=404, detail=st)
    return st


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
    if format == "xlsx":
        path = artifacts["xlsx"]
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif format == "json":
        path = artifacts["json"]
        media = "application/json"
    else:
        path = artifacts["csv"]
        media = "text/csv"

    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail={"error": f"Export file missing: {path}"})
    return FileResponse(path=p, media_type=media, filename=p.name)


@router.get("/health/full")
def health_full():
    rows = repo.load()
    return {
        "status": "ok",
        "dataset_loaded": bool(rows),
        "dataset_path": str(repo.dataset_path) if repo.dataset_path else None,
        "rows": len(rows),
    }
