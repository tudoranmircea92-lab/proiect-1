import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from routes.plasma import router as plasma_router


def configure_logging() -> None:
    debug = os.getenv("APP_DEBUG", "0") == "1"
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING if not debug else logging.INFO)


configure_logging()
app = FastAPI(title="Glass Coater ML Platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    plasma_router,
    prefix="/api/plasma",
    tags=["plasma"]
)
print("Plasma router mounted at /api/plasma")
app.include_router(router)


@app.middleware("http")
async def json_guard_middleware(request, call_next):
    try:
        return await call_next(request)
    except ValueError as exc:
        if "Out of range float values" in str(exc) or "not JSON compliant" in str(exc):
            return JSONResponse(status_code=500, content={"detail": "Non-JSON-compliant float (NaN/Inf) in response. Fixed by sanitization."})
        raise


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def _startup_log_routes():
    print("[startup] routes:")
    for r in app.routes:
        try:
            methods = ",".join(sorted(getattr(r, "methods", []) or []))
            print(f" - {methods:10s} {r.path}")
        except Exception:
            pass
