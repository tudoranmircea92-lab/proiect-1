from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers.optimizer_routes import router as optimizer_router


app = FastAPI(title="Industrial Web Optimizer", version="2.0.0")
app.include_router(optimizer_router)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "optimizer.html")


@app.get("/optimizer")
def optimizer_page() -> FileResponse:
    return FileResponse(_STATIC_DIR / "optimizer.html")
