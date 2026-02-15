from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.optimize import router as optimize_router
from backend.app.api.train import router as train_router
from backend.app.api.importance import router as importance_router
from backend.app.api.train_v2 import router as train_v2_router
from backend.app.api.scan import router as scan_router

app = FastAPI(title="Coating Optimizer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(train_router)
app.include_router(optimize_router)
app.include_router(scan_router)
app.include_router(train_v2_router)
app.include_router(importance_router)
app.include_router(train_router, prefix="/api")
app.include_router(optimize_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
